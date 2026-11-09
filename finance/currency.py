"""Convert stored rial amounts to toman at presentation boundaries."""
from __future__ import annotations

import pandas as pd


CURRENCY_UNIT = "Toman"
RIALS_PER_TOMAN = 10
MONEY_COLUMNS = {
    "passenger_fare", "driver_payout", "contribution", "profit_per_hour", "passenger_fare_per_hour",
    "driver_payout_per_hour", "gross_losses", "median_trip_profit", "StopTimeCost",
    "StopTimeDriverCost", "recorded_stop_charge", "recorded_stop_driver_payout", "DestinationCost",
    "DestinationCostWithoutStopTime", "StopTimeDestinationCost", "SnapPrice", "MlPrice",
    "destination_charge", "route_charge", "destination_stop_charge", "snap_total",
    "ml_total", "TripCost", "TripDriverCost", "source_trip_charge", "fare_deduction",
}


def compact_amount(value) -> str:
    """Format an amount already in toman with uppercase billion/million suffixes."""
    if pd.isna(value):
        return "—"
    value = float(value)
    magnitude = abs(value)
    if magnitude >= 1e6:
        scale, suffix = (1e9, "B") if magnitude >= 1e9 else (1e6, "M")
        scaled = round(value / scale, 2)
        # Avoid displaying a rounded million amount as 1,000 M.
        if suffix == "M" and abs(scaled) >= 1000:
            scaled, suffix = round(value / 1e9, 2), "B"
        return f"{scaled:,.2f}".rstrip("0").rstrip(".") + f" {suffix}"
    return f"{value:,.0f}"


def to_toman(value):
    """Convert a scalar or Series without rounding."""
    return value / RIALS_PER_TOMAN


def toman_frame(frame: pd.DataFrame) -> pd.DataFrame:
    """Convert only monetary columns, preserving source data and non-money units."""
    display = frame.copy()
    for column in MONEY_COLUMNS & set(display.columns):
        display[column] = to_toman(display[column])
    return display
