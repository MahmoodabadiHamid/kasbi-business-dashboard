"""Economic charts independent of the Streamlit page."""
from __future__ import annotations

import math
from datetime import date

import pandas as pd
import plotly.graph_objects as go

from finance.currency import CURRENCY_UNIT, compact_amount, to_toman
from finance.dates import shamsi_axis, shamsi_date
from finance.theme import COST, COST_FILL, LOSS, LOSS_FILL, MUTED, NEUTRAL_FILL, PROFIT, PROFIT_FILL, REVENUE


PASSENGER_FARE_SHARE_EXCLUDED_DATES = ()
ML_PRICING_START = pd.Timestamp("2026-10-17")


def add_ml_pricing_marker(fig: go.Figure, dates, *, compressed=False) -> go.Figure:
    """Mark the pricing change only when it falls within the plotted date window."""
    days = pd.DatetimeIndex(pd.to_datetime(dates)).normalize().dropna().unique().sort_values()
    if days.empty or not days.min() <= ML_PRICING_START <= days.max():
        return fig
    # Compressed charts place the change before the first day under ML pricing,
    # without adding an empty day when the change date has no observations.
    position = int(days.searchsorted(ML_PRICING_START)) - .5 if compressed else ML_PRICING_START
    fig.add_shape(
        type="line", x0=position, x1=position, xref="x", y0=0, y1=1, yref="paper",
        line=dict(color="#AE5CFF", width=2, dash="dot"),
    )
    # A hidden overlay axis makes the hover target span the plot independently
    # of money units, auto-ranging and the passenger_fare-share zoom.
    axis_number = 2
    while f"yaxis{axis_number}" in fig.layout:
        axis_number += 1
    fig.update_layout(**{f"yaxis{axis_number}": dict(
        overlaying="y", range=[0, 1], visible=False, fixedrange=True,
    )})
    fig.add_scatter(
        x=[position] * 101, y=[index / 100 for index in range(101)], yaxis=f"y{axis_number}",
        mode="markers", marker=dict(size=10, opacity=0), name="ML pricing",
        showlegend=False, meta=dict(event="ml_pricing"),
        hovertemplate=f"ML pricing<br>{shamsi_date(ML_PRICING_START)} · 17 October 2026<extra></extra>",
    )
    return fig


def passenger_fare_share_daily_totals(daily: pd.DataFrame) -> pd.DataFrame:
    """Prepare the included days shared by the passenger_fare-share plot and its summary."""
    totals = daily.assign(date=pd.to_datetime(daily.date).dt.normalize()).groupby("date")[["passenger_fare", "driver_payout"]].sum(min_count=1).sort_index()
    return totals[
        totals.passenger_fare.gt(0) & totals.driver_payout.ge(0)
        & ~totals.index.isin(pd.to_datetime(PASSENGER_FARE_SHARE_EXCLUDED_DATES))
    ].copy()


def format_money_chart(fig):
    """Use compact toman ticks and tooltips without changing numeric plot geometry."""
    monetary_axes = {
        key.replace("axis", ""): key for key in fig.layout
        if key.startswith(("xaxis", "yaxis")) and CURRENCY_UNIT in (fig.layout[key].title.text or "")
    }
    for reference, axis_key in monetary_axes.items():
        axis = reference[0]
        values = [float(value) for trace in fig.data
                  if trace.name != "ML pricing" and (getattr(trace, f"{axis}axis", None) or axis) == reference
                  for value in getattr(trace, axis, ())
                  if value is not None and pd.notna(value) and math.isfinite(float(value))]
        if not values:
            continue
        low, high = min(0, min(values)), max(0, max(values))
        if fig.layout[axis_key].range is not None:
            low, high = min(fig.layout[axis_key].range), max(fig.layout[axis_key].range)
        if low == high:
            ticks = [0]
        else:
            rough_step = (high - low) / 5
            power = 10 ** math.floor(math.log10(rough_step))
            step = next(multiplier * power for multiplier in (1, 2, 2.5, 5, 10)
                        if multiplier * power >= rough_step)
            ticks = [index * step for index in range(math.ceil(low / step), math.floor(high / step) + 1)]
        fig.update_layout(**{axis_key: dict(
            tickmode="array", tickvals=ticks, ticktext=[compact_amount(value) for value in ticks],
        )})
    if monetary_axes:
        for trace in fig.data:
            if trace.hoverinfo == "skip" or trace.name == "ML pricing":
                continue
            x_reference, y_reference = trace.xaxis or "x", trace.yaxis or "y"
            money_x, money_y = x_reference in monetary_axes, y_reference in monetary_axes
            if not (money_x or money_y):
                continue
            x_axis_key = f"xaxis{x_reference[1:]}"
            labels = []
            for x, y in zip(trace.x, trace.y):
                x_label = f"{compact_amount(x)} {CURRENCY_UNIT}" if money_x else (
                    shamsi_date(x) if fig.layout[x_axis_key].type == "date" else str(x)
                )
                y_label = f"{compact_amount(y)} {CURRENCY_UNIT}" if money_y else str(y)
                labels.append(f"{x_label}<br>{y_label}")
            trace.update(hovertext=labels, hovertemplate="%{hovertext}<extra>%{fullData.name}</extra>")
    return fig


def _add_economic_areas(fig, totals):
    """Shade the cost/passenger_fare gap, including interpolated sign crossings."""
    # Keep the area below both totals neutral; only their gap indicates profit/loss.
    fig.add_scatter(
        x=totals.index, y=totals.min(axis=1, skipna=False), name="Base area",
        mode="lines", line=dict(width=0), fill="tozeroy",
        fillcolor=NEUTRAL_FILL, showlegend=False, hoverinfo="skip",
    )

    points = []
    for date, passenger_fare, cost in totals.itertuples(name=None):
        if pd.isna(passenger_fare) or pd.isna(cost):
            points.append(None)
            continue
        gap = passenger_fare - cost
        if points and points[-1] is not None:
            previous_date, previous_revenue, previous_cost = points[-1]
            previous_gap = previous_revenue - previous_cost
            if previous_gap * gap < 0:
                fraction = -previous_gap / (gap - previous_gap)
                crossing_date = previous_date + (date - previous_date) * fraction
                crossing_value = previous_revenue + (passenger_fare - previous_revenue) * fraction
                points.append((crossing_date, crossing_value, crossing_value))
        points.append((date, passenger_fare, cost))

    def add_band(segment, sign):
        if not segment:
            return
        dates, revenues, costs = map(list, zip(*segment))
        fig.add_scatter(
            x=dates + dates[::-1], y=revenues + costs[::-1],
            name="Profit" if sign > 0 else "Loss", mode="lines",
            line=dict(width=0), fill="toself", showlegend=False, hoverinfo="skip",
            fillcolor=PROFIT_FILL if sign > 0 else LOSS_FILL,
        )

    segment, segment_sign = [], 0
    for left, right in zip(points, points[1:]):
        if left is None or right is None:
            add_band(segment, segment_sign)
            segment, segment_sign = [], 0
            continue
        # Inserted crossings ensure each interval has a single profit/loss sign.
        gap = (left[1] - left[2]) + (right[1] - right[2])
        sign = 1 if gap > 0 else (-1 if gap < 0 else 0)
        if sign != segment_sign:
            add_band(segment, segment_sign)
            segment = []
            segment_sign = sign
        if sign:
            if not segment:
                segment.append(left)
            segment.append(right)
    add_band(segment, segment_sign)


def cumulative_economic_trend(daily: pd.DataFrame) -> go.Figure:
    """Show cumulative economics with daily passenger fare bars on a separate scale."""
    amounts = ["passenger_fare", "driver_payout"]
    totals = daily.assign(date=pd.to_datetime(daily.date).dt.normalize()).groupby("date")[amounts].sum().sort_index()
    daily_revenue = to_toman(totals.passenger_fare)
    if not totals.empty:
        # No-trip days keep the prior running total instead of interpolating growth.
        totals = totals.reindex(pd.date_range(totals.index.min(), totals.index.max()), fill_value=0)
    cumulative = to_toman(totals.cumsum())
    fig = go.Figure()
    fig.add_bar(
        x=daily_revenue.index, y=daily_revenue, name="Daily passenger fare", yaxis="y2",
        marker=dict(color=REVENUE, opacity=.45, line_width=0),
        width=24 * 60 * 60 * 1000 * .75,
    )
    _add_economic_areas(fig, cumulative)

    # Draw the two economic lines above the shaded areas.
    for column, name, color in (
        ("passenger_fare", "Passenger fare", REVENUE),
        ("driver_payout", "Driver payout", COST),
    ):
        fig.add_scatter(
            x=cumulative.index, y=cumulative[column], name=name,
            mode="lines", line=dict(color=color, width=2),
            hovertemplate=f"Cumulative {name.lower()}: %{{y:,.0f}} {CURRENCY_UNIT}<extra></extra>",
        )
    fig.add_hline(y=0, line_color=MUTED, line_width=1)
    daily_max = float(daily_revenue.max()) if not daily_revenue.empty else 0
    fig.update_layout(
        title="Cumulative daily economic trend", yaxis_title=f"Cumulative · {CURRENCY_UNIT}",
        xaxis_title="Trip start date", barmode="overlay",
        yaxis2=dict(
            title=f"Daily passenger fare · {CURRENCY_UNIT}", overlaying="y", side="right",
            showgrid=False, zeroline=False, range=[0, daily_max * 4 if daily_max > 0 else 1],
        ),
    )
    fig.update_yaxes(rangemode="tozero")
    shamsi_axis(fig, cumulative.index)
    return add_ml_pricing_marker(format_money_chart(fig), cumulative.index)


def daily_economic_trend(daily: pd.DataFrame) -> go.Figure:
    """Split each observed day's passenger_fare into driver payout and contribution."""
    totals = passenger_fare_share_daily_totals(daily)
    costs = totals.driver_payout / totals.passenger_fare
    margins = 1 - costs
    actual_costs = costs.tolist()
    band_boundaries = (1 - margins.abs().clip(0, 1)).tolist()
    positions = list(range(len(totals)))
    dates = [shamsi_date(value) for value in totals.index]
    # Extend the filled regions to the edges, including for a single observed day.
    area_x, area_actual = [], []
    if positions:
        area_x.append(-.5)
        area_actual.append(actual_costs[0])
        for index, cost in enumerate(actual_costs):
            # Split at break-even and at a 100% loss before clipping band heights.
            crossings = []
            if index:
                previous_cost = actual_costs[index - 1]
                for threshold in (1, 2):
                    if (previous_cost - threshold) * (cost - threshold) < 0:
                        fraction = (threshold - previous_cost) / (cost - previous_cost)
                        crossings.append((fraction, threshold))
            for fraction, threshold in sorted(crossings):
                area_x.append(index - 1 + fraction)
                area_actual.append(threshold)
            area_x.append(index)
            area_actual.append(cost)
        area_x.append(len(totals) - .5)
        area_actual.append(actual_costs[-1])
    area_costs = [min(value, 1) for value in area_actual]
    fig = go.Figure()
    fig.add_scatter(
        x=area_x, y=area_costs, name="Driver payout", mode="lines",
        line=dict(color=COST, width=2), fill="tozeroy", fillcolor=COST_FILL,
        hoverinfo="skip",
    )
    fig.add_scatter(
        x=area_x, y=[1] * len(area_x), name="Contribution (profit)", mode="lines",
        line=dict(color=PROFIT, width=0), fill="tonexty", fillcolor=PROFIT_FILL,
        hoverinfo="skip",
    )
    has_losses = bool(costs.gt(1).any())
    daily_hover = []
    for day, cost, margin, revenue_amount, cost_amount in zip(dates, costs, margins, totals.passenger_fare, totals.driver_payout):
        shortfall = max(cost_amount - revenue_amount, 0)
        status = f"Loss day · costs exceed passenger_fare by {cost - 1:.1%}" if cost > 1 else (
            "Break even" if cost == 1 else "Positive contribution"
        )
        daily_hover.append([day, cost, margin, status, f"{compact_amount(to_toman(shortfall))} {CURRENCY_UNIT}", max(cost - 1, 0)])
    if has_losses:
        # The loss band overlays passenger_fare already consumed by costs; it is not
        # an additive cost component. A 30% loss occupies the upper 30%.
        loss_lower = [1 - min(max(value - 1, 0), 1) for value in area_actual]
        fig.add_scatter(
            x=area_x + area_x[::-1], y=loss_lower + [1] * len(area_x),
            name="Loss (overlay)", mode="lines", line=dict(color=LOSS, width=0),
            fill="toself", fillcolor=LOSS_FILL, hoverinfo="skip",
        )
    reference_y = 1
    if not totals.empty:
        # Net both profits and losses across the included days, weighted by passenger_fare.
        average_margin = (totals.passenger_fare.sum() - totals.driver_payout.sum()) / totals.passenger_fare.sum()
        # Both profit and loss bands are measured down from the 100% top edge.
        reference_y = 1 - min(abs(average_margin), 1)
        fig.add_scatter(
            x=area_x, y=[reference_y] * len(area_x), name="Average profit", mode="lines",
            line=dict(color=MUTED, dash="dash", width=1.5), showlegend=False,
            hovertemplate=f"Average profit: {average_margin:.1%}<br>Includes profits and losses<extra></extra>",
        )
    # Invisible hit targets provide daily hover details without visible point symbols.
    fig.add_scatter(
        x=positions, y=band_boundaries, name="Passenger fare split", mode="markers",
        line=dict(width=0), marker=dict(color=COST, size=12, opacity=0),
        showlegend=False, customdata=daily_hover,
        hovertemplate="%{customdata[0]}<br>%{customdata[3]}<br>Passenger fare: 100%<br>Driver payout: %{customdata[1]:.1%}<br>Contribution margin: %{customdata[2]:.1%}<br>Loss: %{customdata[5]:.1%}<br>Shortfall: %{customdata[4]}<extra></extra>",
    )
    ticks = positions if len(positions) <= 8 else [round(index * (len(positions) - 1) / 7) for index in range(8)]
    fig.update_layout(title="Daily economic trend · passenger fare = 100%", hovermode="closest")
    fig.update_xaxes(
        type="linear", range=[-.5, max(.5, len(totals) - .5)], tickmode="array",
        tickvals=ticks, ticktext=[dates[index] for index in ticks],
        title="Trip start date (Shamsi) · days with data only",
    )
    # Include every profit/loss boundary and the signed-average reference, with
    # five percentage points of padding and a minimum ten-point viewing window.
    lowest_boundary = min([reference_y, *band_boundaries]) if band_boundaries else 0
    lower = max(0, min(.9, math.floor((lowest_boundary - .05 + 1e-10) * 20) / 20))
    step = .05 if lower >= .5 else .1 if lower >= .2 else .2
    tick_count = round((1 - lower) / step)
    ticks_y = sorted({round(lower, 10), 1, *[
        round(1 - index * step, 10) for index in range(tick_count + 1)
        if 1 - index * step >= lower - 1e-10
    ]})
    fig.update_yaxes(
        title="Share of daily passenger fare · zoomed scale" if lower > 0 else "Share of daily passenger fare",
        range=[lower, 1], tickformat=".0%", tickmode="array", tickvals=ticks_y, fixedrange=True,
    )
    return add_ml_pricing_marker(fig, totals.index, compressed=True)
