"""Trip-grain contribution analysis. Pure functions; no Streamlit dependency."""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP

import numpy as np
import pandas as pd

from .load import DEST_REQUIRED, TRIP_REQUIRED


TRIP_NUMBERS = ["Id", "OrganizationId", "DriverId", "TripCost", "TripDriverCost", "StopTime", "StopTimeCost", "StopTimeDriverCost", "TotalDistanceByMeter", "IsIntercity", "ServiceType", "TripType", "ContractType", "OriginCityId", "TotalMlPrice", "TotalSnapPrice", "PredictTripCost", "PredictDriverCost"]
EXCLUDED_ORGANIZATION_NAME = "سرویس تست رایگان"
FARE_DEDUCTION_RATE = 0.078  # Exact coefficient explicitly specified by the user.
FARE_RETAINED_RATE = 1 - FARE_DEDUCTION_RATE
DEST_NUMBERS = ["Id", "TripId", "DestinationCost", "DestinationCostWithoutStopTime", "StopTimeDestinationCost", "StopTime", "FreeStopTimeByMinutes", "SnapPrice", "MlPrice"]


def ratio(numerator, denominator):
    return float(numerator / denominator) if pd.notna(denominator) and denominator != 0 else np.nan


def source_money(value):
    """Match SQL CAST(... AS DECIMAL(18,2)), including half-away-from-zero rounding."""
    if pd.isna(value):
        return np.nan
    amount = Decimal(str(value)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    if abs(amount) >= Decimal("10000000000000000"):
        raise ValueError("Source amount exceeds DECIMAL(18,2).")
    return float(amount)


def money_sum(values):
    known = values.dropna()
    return float(sum((Decimal(str(value)) for value in known), Decimal(0))) if len(known) else np.nan


def dimension_labels(trips: pd.DataFrame, id_column: str, name_column: str, fallback: str) -> dict:
    """Keep IDs as identities, using readable names with unambiguous fallbacks."""
    entities = trips.loc[trips[id_column].notna(), [id_column, name_column]].drop_duplicates(id_column).copy()
    names = entities[name_column].astype("string").str.strip().replace("", pd.NA)
    names = names.fillna(entities[id_column].map(lambda value: f"{fallback} {int(value)}"))
    repeated_names = names.duplicated(keep=False)
    names.loc[repeated_names] = names[repeated_names] + entities.loc[repeated_names,id_column].map(lambda value: f" ({int(value)})")
    return dict(zip(entities[id_column], names))


def prepare_trips(raw: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    missing = TRIP_REQUIRED - set(raw.columns)
    if missing:
        raise ValueError(f"Trips missing columns: {', '.join(sorted(missing))}")
    trips = raw.copy()
    # Enforce the same business scope for non-SQL inputs and prepared snapshots.
    excluded = trips.get("OrganizationName", pd.Series(pd.NA, index=trips.index, dtype="string")).astype("string").str.strip().eq(EXCLUDED_ORGANIZATION_NAME).fillna(False)
    excluded_rows = int(excluded.sum())
    trips = trips.loc[~excluded].copy()
    for name in TRIP_NUMBERS:
        if name not in trips:
            trips[name] = np.nan
        trips[name] = pd.to_numeric(trips[name], errors="coerce")
    for name in ("StartDateTime", "EndDateTime"):
        trips[name] = pd.to_datetime(trips[name], errors="coerce")
    diagnostics = {
        "raw_trip_rows": len(raw),
        "excluded_organization_rows": excluded_rows,
        "non_numeric_trip_ids": int(trips.Id.isna().sum()),
        "duplicate_trip_rows": int(trips.loc[trips.Id.notna(), "Id"].duplicated().sum()),
    }
    # The authoritative daily query includes every source row, including duplicate IDs,
    # missing timestamps, zero/negative amounts, and independently NULL money inputs.
    trips["TripCost"] = trips.TripCost.map(source_money)
    trips["TripDriverCost"] = trips.TripDriverCost.map(source_money)
    trips["source_trip_charge"] = trips.TripCost
    trips["passenger_fare"] = trips.TripCost.map(lambda v: float(Decimal(str(v)) * Decimal("0.922")) if pd.notna(v) else np.nan)
    trips["fare_deduction"] = trips.TripCost - trips.passenger_fare
    trips["driver_payout"] = trips.TripDriverCost
    diagnostics["not_completed_or_not_financial"] = 0
    trips["service_hours"] = (trips.EndDateTime - trips.StartDateTime).dt.total_seconds() / 3600
    diagnostics["nonpositive_duration"] = int((trips.service_hours <= 0).sum())
    diagnostics["very_long_duration_over_72h"] = int((trips.service_hours > 72).sum())
    trips.loc[(trips.service_hours <= 0) | (trips.service_hours > 72), "service_hours"] = np.nan
    trips["contribution"] = trips.passenger_fare - trips.driver_payout
    trips["margin"] = trips.contribution / trips.passenger_fare
    trips["date"] = trips.StartDateTime.dt.date
    trips["loss"] = trips.contribution < 0
    for name in ("OrganizationName", "OriginCityName"):
        if name not in trips:
            trips[name] = pd.NA
    diagnostics["eligible_trips"] = len(trips)
    return trips, diagnostics


def prepare_destinations(raw: pd.DataFrame, trips: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    missing = DEST_REQUIRED - set(raw.columns)
    if missing:
        raise ValueError(f"Destinations missing columns: {', '.join(sorted(missing))}")
    dest = raw.copy()
    for name in DEST_NUMBERS:
        if name not in dest:
            dest[name] = np.nan
        dest[name] = pd.to_numeric(dest[name], errors="coerce")
    diagnostic = {"raw_destination_rows": len(dest), "duplicate_destination_rows": int(dest.loc[dest.Id.notna(), "Id"].duplicated().sum())}
    dest = dest[dest.Id.notna() & ~dest.Id.duplicated(keep=False)].copy()
    dest = dest[dest.TripId.isin(trips.Id)].copy()
    diagnostic["matched_destination_rows"] = len(dest)
    if dest.empty:
        return dest, pd.DataFrame(columns=["TripId"]), diagnostic
    dest["component_valid"] = (dest[["DestinationCost", "DestinationCostWithoutStopTime", "StopTimeDestinationCost"]].notna().all(axis=1)
                              & np.isclose(dest.DestinationCost, dest.DestinationCostWithoutStopTime + dest.StopTimeDestinationCost, atol=1, rtol=0))
    groups = dest.groupby("TripId")
    # Built-in reductions avoid calling Python once per trip for every sum.
    # min_count=1 preserves unknown amounts rather than replacing them with zero.
    amounts = groups[["DestinationCost", "DestinationCostWithoutStopTime", "StopTimeDestinationCost",
                      "FreeStopTimeByMinutes", "SnapPrice", "MlPrice"]].sum(min_count=1).rename(columns={
        "DestinationCost": "destination_charge", "DestinationCostWithoutStopTime": "route_charge",
        "StopTimeDestinationCost": "destination_stop_charge", "FreeStopTimeByMinutes": "free_stop_minutes",
        "SnapPrice": "snap_total", "MlPrice": "ml_total",
    })
    counts = groups.agg(
        destinations=("Id", "size"),
        price_rows=("DestinationCost", "count"), route_rows=("DestinationCostWithoutStopTime", "count"),
        stop_rows=("StopTimeDestinationCost", "count"),
        valid_component_rows=("component_valid", "sum"),
    )
    positive_prices = dest[["TripId"]].assign(snap_rows=dest.SnapPrice.gt(0), ml_rows=dest.MlPrice.gt(0))
    positive_counts = positive_prices.groupby("TripId")[["snap_rows", "ml_rows"]].sum()
    aggregated = counts.join(amounts).join(positive_counts).reset_index()
    unique_trips = trips[trips.Id.notna() & ~trips.Id.duplicated(keep=False)]
    aggregated = aggregated.merge(unique_trips[["Id", "passenger_fare", "source_trip_charge", "StopTimeCost"]], left_on="TripId", right_on="Id", how="left").drop(columns="Id")
    aggregated["fully_priced"] = (aggregated.price_rows == aggregated.destinations) & (aggregated.route_rows == aggregated.destinations) & (aggregated.stop_rows == aggregated.destinations)
    aggregated["component_ok"] = aggregated.fully_priced & (aggregated.valid_component_rows == aggregated.destinations)
    # Destination charges reconcile to gross charges, not insurance-exclusive passenger_fare.
    aggregated["source_charge_matches"] = aggregated.component_ok & np.isclose(aggregated.source_trip_charge, aggregated.destination_charge, atol=1, rtol=0)
    aggregated["snap_comparable"] = aggregated.component_ok & (aggregated.snap_rows == aggregated.destinations) & (aggregated.snap_total > 0)
    aggregated["ml_comparable"] = aggregated.component_ok & (aggregated.ml_rows == aggregated.destinations) & (aggregated.ml_total > 0)
    diagnostic["destination_covered_trips"] = len(aggregated)
    diagnostic["reconciled_trips"] = int(aggregated.source_charge_matches.sum())
    diagnostic["snap_comparable_trips"] = int(aggregated.snap_comparable.sum())
    return dest, aggregated, diagnostic


def summarize(frame: pd.DataFrame) -> dict:
    if frame.empty:
        return {k: np.nan for k in ("trips", "passenger_fare", "driver_payout", "contribution", "margin", "hours", "profit_per_hour", "passenger_fare_per_hour", "driver_payout_per_hour", "hour_coverage", "loss_trips", "loss_rate", "gross_losses", "median_trip_profit")}
    passenger_fare = money_sum(frame.passenger_fare)
    driver_payout = money_sum(frame.driver_payout)
    contribution = passenger_fare - driver_payout
    valid_hours = frame[frame.service_hours.notna()]
    hours = valid_hours.service_hours.sum(min_count=1)
    losses = frame.loc[frame.loss, "contribution"].sum()
    return {
        "trips": len(frame), "passenger_fare": passenger_fare, "driver_payout": driver_payout,
        "contribution": contribution, "margin": ratio(contribution, passenger_fare),
        "hours": hours, "hour_coverage": len(valid_hours) / len(frame),
        "profit_per_hour": ratio(valid_hours.passenger_fare.sum(min_count=1) - valid_hours.driver_payout.sum(min_count=1), hours),
        "passenger_fare_per_hour": ratio(valid_hours.passenger_fare.sum(min_count=1), hours),
        "driver_payout_per_hour": ratio(valid_hours.driver_payout.sum(min_count=1), hours),
        "loss_trips": int(frame.loss.sum()), "loss_rate": frame.loc[frame.contribution.notna(), "loss"].mean(),
        "gross_losses": -losses, "median_trip_profit": frame.contribution.median() if frame.contribution.notna().any() else np.nan,
    }


def grouped(trips: pd.DataFrame, column: str) -> pd.DataFrame:
    if trips.empty:
        return pd.DataFrame()
    values = trips.assign(
        _hour_profit=trips.contribution.where(trips.service_hours.notna()),
        _hour_revenue=trips.passenger_fare.where(trips.service_hours.notna()),
        _hour_cost=trips.driver_payout.where(trips.service_hours.notna()),
        _loss_amount=trips.contribution.where(trips.loss, 0),
    )
    groups = values.groupby(column, dropna=False, sort=True, observed=True)
    sums = groups[["passenger_fare", "driver_payout", "contribution", "service_hours", "_hour_profit", "_hour_revenue",
                   "_hour_cost", "_loss_amount", "StopTime", "StopTimeCost", "StopTimeDriverCost"]].sum(min_count=1)
    for column in ("passenger_fare", "driver_payout", "_hour_revenue", "_hour_cost"):
        sums[column] = groups[column].agg(money_sum)
    counts = groups.size()
    hours = sums.service_hours.replace(0, np.nan)
    return pd.DataFrame({
        "trips": counts, "passenger_fare": sums.passenger_fare, "driver_payout": sums.driver_payout,
        "contribution": sums.passenger_fare - sums.driver_payout, "margin": (sums.passenger_fare - sums.driver_payout) / sums.passenger_fare.replace(0, np.nan),
        "hours": sums.service_hours, "hour_coverage": groups.service_hours.count() / counts,
        "profit_per_hour": (sums._hour_revenue - sums._hour_cost) / hours, "passenger_fare_per_hour": sums._hour_revenue / hours,
        "driver_payout_per_hour": sums._hour_cost / hours,
        "loss_trips": groups.loss.sum(), "loss_rate": groups.loss.sum() / groups.contribution.count().replace(0, np.nan),
        "gross_losses": -sums._loss_amount, "median_trip_profit": groups.contribution.median(),
        "stop_minutes": sums.StopTime, "recorded_stop_charge": sums.StopTimeCost, "recorded_stop_driver_payout": sums.StopTimeDriverCost,
    }).reset_index()


def daily_totals(trips: pd.DataFrame) -> pd.DataFrame:
    """Numeric counterpart of daily_totals.sql; floor only AFTER daily summation."""
    daily = grouped(trips, "date").sort_values("date", ascending=False, na_position="last")
    result = pd.DataFrame({"TripDate": daily.date})
    for source, target in (("passenger_fare", "PassengerFare"), ("driver_payout", "DriverPayout")):
        result[target] = daily[source].map(lambda v: int((Decimal(str(v)) / 10).to_integral_value(rounding="ROUND_FLOOR")) if pd.notna(v) else np.nan)
    result["MarginPercent"] = daily.margin.map(lambda v: float((Decimal(str(v)) * 100).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)) if pd.notna(v) else np.nan)
    return result.reset_index(drop=True)


@dataclass
class Analysis:
    trips: pd.DataFrame
    destinations: pd.DataFrame
    destination_agg: pd.DataFrame
    diagnostics: dict

    @classmethod
    def from_frames(cls, trips_raw: pd.DataFrame, destinations_raw: pd.DataFrame):
        trips, a = prepare_trips(trips_raw)
        destinations, dest_agg, b = prepare_destinations(destinations_raw, trips)
        return cls(trips, destinations, dest_agg, a | b)

    def filter(self, start=None, end=None, organizations=None, intercity="All", cities=None):
        frame = self.trips
        if start is not None:
            frame = frame[frame.date >= start]
        if end is not None:
            frame = frame[frame.date <= end]
        if organizations:
            frame = frame[frame.OrganizationId.isin(organizations)]
        if cities:
            frame = frame[frame.OriginCityId.isin(cities)]
        if intercity == "City":
            frame = frame[frame.IsIntercity == 0]
        if intercity == "Intercity":
            frame = frame[frame.IsIntercity == 1]
        return Analysis(frame, self.destinations[self.destinations.TripId.isin(frame.Id)], self.destination_agg[self.destination_agg.TripId.isin(frame.Id)], self.diagnostics)
