"""Executive contribution dashboard for dedicated-driver B2B transport."""
from __future__ import annotations

from datetime import date
from html import escape
import re

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from finance.load import read_database
from finance.charts import (
    PASSENGER_FARE_SHARE_EXCLUDED_DATES, cumulative_economic_trend, daily_economic_trend,
    add_ml_pricing_marker, format_money_chart, passenger_fare_share_daily_totals,
)
from finance.currency import CURRENCY_UNIT, MONEY_COLUMNS, compact_amount, to_toman, toman_frame
from finance.dates import parse_shamsi, shamsi_axis, shamsi_date, shamsi_frame
from finance.metrics import Analysis, FARE_RETAINED_RATE, daily_totals, dimension_labels, grouped, ratio, summarize
from finance.theme import COST, DASHBOARD_CSS, GRID, LOSS, MUTED, PLOT_LAYOUT, PROFIT, REVENUE


DEFAULT_START_DATE = date(2026, 4, 1)


def money(value, unit=CURRENCY_UNIT):
    if pd.isna(value):
        return "—"
    return f"{compact_amount(to_toman(float(value)))} {unit}"


def money_metric(label, value, target=st, role="profit"):
    if pd.notna(value) and value < 0 and role == "profit":
        role = "cost"
    amount = "—" if pd.isna(value) else compact_amount(to_toman(float(value)))
    target.markdown(
        f'<div class="money-metric metric--{role}" role="group" aria-label="{escape(label, quote=True)}">'
        f'<div class="money-metric-label">{escape(label)}</div>'
        '<div class="money-metric-value">'
        f'<span class="money-metric-amount">{escape(amount)}</span>'
        f'<span class="money-metric-unit">{CURRENCY_UNIT}</span>'
        '</div></div>',
        unsafe_allow_html=True,
    )


def semantic_metric(label, value, role, target=st, **kwargs):
    key = "kpi-" + role + "-" + re.sub(r"[^a-z0-9]+", "-", label.lower()).strip("-")
    with target.container(key=key):
        st.metric(label, value, **kwargs)


def pct(value):
    return "—" if pd.isna(value) else f"{value:.1%}"


def count(value):
    return "—" if pd.isna(value) else f"{value:,.0f}"


def display_frame(frame: pd.DataFrame) -> pd.DataFrame:
    display = shamsi_frame(toman_frame(frame))
    for column in MONEY_COLUMNS & set(display.columns):
        display[column] = display[column].map(lambda value: "" if pd.isna(value) else compact_amount(value))
    return display


def style(fig, percent=False):
    fig.update_layout(**PLOT_LAYOUT)
    fig.update_xaxes(showgrid=False, tickfont=dict(color=MUTED), title_font=dict(color=MUTED, size=12), automargin=True)
    fig.update_yaxes(gridcolor=GRID, zerolinecolor="#BAC4CD", tickfont=dict(color=MUTED), title_font=dict(color=MUTED, size=12), tickformat=".0%" if percent else ",.0f")
    return format_money_chart(fig)


def bar(frame, x, y, title, color=REVENUE, horizontal=False, percent=False):
    fig = go.Figure()
    monetary = y in MONEY_COLUMNS and not percent
    values = to_toman(frame[y]) if monetary else frame[y]
    suffix = f" {CURRENCY_UNIT}" if monetary else ""
    if y in {"contribution", "profit_per_hour", "margin", "median_trip_profit"}:
        color = [LOSS if value < 0 else PROFIT for value in frame[y]]
    elif y in {"driver_payout", "driver_payout_per_hour", "recorded_stop_driver_payout", "gross_losses"}:
        color = COST
    elif x == "margin_band":
        color = [LOSS if str(label) == "Loss" else PROFIT for label in frame[x]]
    labels = pd.to_datetime(frame[x]) if x == "date" else frame[x].astype(str)
    if horizontal:
        fig.add_bar(y=labels, x=values, orientation="h", marker_color=color, hovertemplate="%{y}: %{x:,.1f}" + suffix + "<extra></extra>")
        fig.update_layout(yaxis=dict(autorange="reversed"))
    else:
        fig.add_bar(x=labels, y=values, marker_color=color, hovertemplate="%{x}: %{y:,.1f}" + suffix + "<extra></extra>")
    if x == "date":
        shamsi_axis(fig, frame[x])
    if monetary:
        fig.update_layout(**{"xaxis_title" if horizontal else "yaxis_title": CURRENCY_UNIT})
    fig.update_layout(title=dict(text=title, font_size=15), showlegend=False)
    fig = style(fig, percent)
    return add_ml_pricing_marker(fig, frame[x]) if x == "date" else fig


@st.cache_data(show_spinner=False, ttl=300, refresh_mode="background")
def database_analysis(calculation_policy):
    """Cache validated, reconciled history, not just the raw SQL result."""
    trips_raw, destinations_raw = read_database()
    analysis = Analysis.from_frames(trips_raw, destinations_raw)
    return analysis, pd.Timestamp.now(tz="Asia/Tehran")


def refresh_database():
    database_analysis.clear()


def trip_review_csv(trips):
    """Generate a precise export only when the download is requested."""
    review = toman_frame(trips[["Id","OrganizationId","OrganizationName","OriginCityId","OriginCityName","DriverId","StartDateTime","EndDateTime","TripCost","TripDriverCost","source_trip_charge","fare_deduction","passenger_fare","driver_payout","contribution","service_hours","StopTime","StopTimeCost","StopTimeDriverCost"]])
    review = shamsi_frame(review).rename(columns={"StartDateTime": "StartDateTime_shamsi", "EndDateTime": "EndDateTime_shamsi"})
    review = review.rename(columns={column: f"{column}_toman" for column in MONEY_COLUMNS & set(review.columns)})
    return review.to_csv(index=False).encode("utf-8-sig")


def clear_filters():
    st.session_state["trip_start_shamsi"] = ""
    st.session_state["trip_end_shamsi"] = ""
    st.session_state["service_geography"] = "All"
    st.session_state["organizations"] = []
    st.session_state["origin_cities"] = []


st.set_page_config(page_title="Kasbi | Finance decisions", page_icon="◆", layout="wide")
st.markdown(DASHBOARD_CSS, unsafe_allow_html=True)

st.markdown('<div class="hero"><h1>Kasbi · Finance decisions</h1><p>Dedicated driver economics · executive contribution view</p><div class="semantic-legend" aria-label="Financial color key"><span><i aria-hidden="true"></i>Passenger fare</span><span class="cost"><i aria-hidden="true"></i>Cost / loss</span><span class="profit"><i aria-hidden="true"></i>Contribution / profit</span></div></div>', unsafe_allow_html=True)

with st.sidebar:
    st.header("Filters")
    st.caption(f"Default: trips from {shamsi_date(DEFAULT_START_DATE)} (Shamsi), with no end-date limit. Clear all filters to show all database history.")
    st.button("Clear all filters", on_click=clear_filters, width="stretch")
    st.button("Refresh data", on_click=refresh_database, width="stretch", help="Load the latest database snapshot now. Filters stay selected.")
    try:
        with st.spinner("Loading database history..."):
            full, loaded_at = database_analysis("passenger-fare-payout-exclude-free-test-v6")
    except Exception as exc:
        st.error(f"Could not load database data: {exc}")
        st.stop()
    if full.trips.empty:
        st.error("No source trip rows were found.")
        st.stop()
    organization_labels = dimension_labels(full.trips, "OrganizationId", "OrganizationName", "Organization")
    city_labels = dimension_labels(full.trips, "OriginCityId", "OriginCityName", "City")
    start, end = full.trips.date.dropna().min(), full.trips.date.dropna().max()
    st.session_state.setdefault("trip_start_shamsi", shamsi_date(DEFAULT_START_DATE))
    start_text = st.text_input("Start date (Shamsi)", key="trip_start_shamsi", placeholder="YYYY.MM.DD", help="Enter a Shamsi date, e.g. 1405.01.12. Leave blank for no start limit.")
    end_text = st.text_input("End date (Shamsi)", key="trip_end_shamsi", placeholder="YYYY.MM.DD · optional", help="The end date is inclusive. Leave blank for no end limit. Persian digits are supported.")
    try:
        start_date, end_date = parse_shamsi(start_text), parse_shamsi(end_text)
        if start_date is not None and end_date is not None and start_date > end_date:
            raise ValueError("End date must be on or after start date.")
    except ValueError as exc:
        st.error(str(exc))
        st.stop()
    city = st.selectbox("Service geography", ["All", "City", "Intercity"], key="service_geography")
    org_ids = sorted(organization_labels, key=lambda value: organization_labels[value])
    chosen_orgs = st.multiselect("Organizations", options=org_ids, format_func=organization_labels.get, placeholder="All organizations", key="organizations")
    city_ids = sorted(city_labels, key=lambda value: city_labels[value])
    chosen_cities = st.multiselect("Origin cities", options=city_ids, format_func=city_labels.get, placeholder="All origin cities", key="origin_cities")
    unit = CURRENCY_UNIT
    st.caption("Dates use the Shamsi calendar. Amounts are in toman (1 toman = 10 IRR); B = billion, M = million. CSV amounts retain full numeric precision.")
    st.caption("Business scope excludes سرویس تست رایگان.")
    st.caption(f"Database history: {shamsi_date(start)} to {shamsi_date(end)}. All source rows are retained; see Data trust for missing values and duplicate-ID diagnostics.")
    st.caption(f"Data loaded: {shamsi_date(loaded_at, include_time=True)} (Tehran). Cached for 5 minutes; refreshes in the background while a recent snapshot is available.")

data = full.filter(start_date, end_date, chosen_orgs, city, chosen_cities)
data.trips = data.trips.assign(
    OrganizationName=data.trips.OrganizationId.map(organization_labels).fillna("Unknown organization"),
    OriginCityName=data.trips.OriginCityId.map(city_labels).fillna("Unknown city"),
)
trips, agg = data.trips, data.destination_agg
if trips.empty:
    st.warning("No trips match the current filters.")
    st.stop()
main = summarize(trips)
recorded_stop_charge = trips.StopTimeCost.sum(min_count=1)
recorded_stop_driver_payout = trips.StopTimeDriverCost.sum(min_count=1)
coverage = ratio(len(agg), len(trips))
reconciled = agg[agg.source_charge_matches] if not agg.empty else agg
snap = agg[agg.snap_comparable] if not agg.empty else agg

if start_date is not None and end_date is not None:
    period = f"{shamsi_date(start_date)} to {shamsi_date(end_date)}"
elif start_date is not None:
    period = f"{shamsi_date(start_date)} onward"
elif end_date is not None:
    period = f"Through {shamsi_date(end_date)}"
else:
    period = f"All dates ({shamsi_date(start)} to {shamsi_date(end)})"
period += " (Shamsi)"

tabs = st.tabs(["Executive", "Where profit leaks", "Customers & segments", "Pricing & benchmarks", "Data trust", "20 decisions"], key="finance_view", on_change="rerun")

if tabs[0].open:
    with tabs[0]:
        st.subheader("Business performance")
        st.caption("Passenger fare = CAST(TripCost AS DECIMAL(18,2)) × 0.922; driver payout = CAST(TripDriverCost AS DECIMAL(18,2)). Neither stop field is added. All source rows within your selected filters are included, regardless of status, completion or amount sign.")
        a,b,c,d = st.columns(4)
        money_metric("Customer passenger_fare", main["passenger_fare"], a, role="passenger_fare")
        money_metric("Driver payout", main["driver_payout"], b, role="cost")
        money_metric("Contribution", main["contribution"], c)
        semantic_metric("Contribution margin", pct(main["margin"]), "cost" if main["margin"] < 0 else "profit", d)
        a,b,c,d = st.columns(4)
        money_metric("Profit / service hour", main["profit_per_hour"], a)
        semantic_metric("Loss-making trips", pct(main["loss_rate"]), "cost", b, delta=f"{count(main['loss_trips'])} trips", delta_color="off", delta_arrow="off")
        money_metric("Money lost on loss trips", main["gross_losses"], c, role="cost")
        money_metric("Median trip profit", main["median_trip_profit"], d)
        a,b,c = st.columns(3)
        a.metric("Elapsed service hours", count(main["hours"]))
        money_metric("Passenger fare / service hour", main["passenger_fare_per_hour"], b, role="passenger_fare")
        money_metric("Driver payout / service hour", main["driver_payout_per_hour"], c, role="cost")
        st.caption(f"Hours are elapsed StartDateTime → EndDateTime, not measured driver availability. Hourly numerators and denominators use the same valid-hour subset ({pct(main['hour_coverage'])} of filtered trips).")
        baseline = daily_totals(trips)
        baseline_display = baseline.copy()
        baseline_display["TripDate"] = baseline_display.TripDate.map(lambda v: shamsi_date(v) if pd.notna(v) else "Unknown start date")
        for column in ("PassengerFare", "DriverPayout"):
            baseline_display[column] = baseline_display[column].map(lambda v: "" if pd.isna(v) else f"{v:,.0f}")
        st.dataframe(baseline_display, hide_index=True, width="stretch")
        st.caption("Daily baseline · PassengerFare and DriverPayout are floor(daily sum in IRR ÷ 10), in toman. MarginPercent uses unrounded IRR totals. Clear all filters to match the unfiltered SQL query.")
        daily = grouped(trips, "date")
        left,right = st.columns(2)
        with left:
            st.plotly_chart(style(cumulative_economic_trend(daily)), width="stretch")
            st.caption("Running totals restart for the selected filters. The gap between cumulative passenger_fare and driver payout is green for profit and red for loss.")
        with right:
            share_daily = passenger_fare_share_daily_totals(daily)
            if share_daily.empty:
                st.info("No days remain in this chart after the date exclusions.")
            else:
                st.plotly_chart(style(daily_economic_trend(daily), percent=True), width="stretch")
            st.caption("The percentage axis zooms to the observed bands, keeping passenger_fare at 100%. Neon green shows profit; neon red shows loss, measured down from 100% in both cases. On loss days, costs consume all passenger_fare. Loss shading is capped at 100%; hover shows full cost, margin and shortfall. Hover the gray dashed line for the net average margin, including both profits and losses.")
            st.caption("The percentage chart requires positive daily passenger fare and known nonnegative daily payout; other days remain in baseline totals and the daily table. No dates are excluded by policy.")
            loss_days = share_daily[share_daily.driver_payout > share_daily.passenger_fare]
            if not loss_days.empty:
                st.caption(f"{count(len(loss_days))} of {count(len(share_daily))} days spent more than they earned · Total shortfall on those days: {money((loss_days.driver_payout - loss_days.passenger_fare).sum())}.")
        st.plotly_chart(bar(daily, "date", "profit_per_hour", "Contribution per service hour", PROFIT), width="stretch")
        st.subheader("What requires management attention")
        if main["gross_losses"] > 0:
            st.write(f"**Loss exposure:** {money(main['gross_losses'], unit)} across {count(main['loss_trips'])} trips. Review the loss table below and differentiate commercial pricing from operational duration.")
        st.write("**Stop fields:** recorded diagnostics only. Neither StopTimeCost nor StopTimeDriverCost is added to baseline passenger fare or driver payout.")
        st.write(f"**Capacity lens:** {money(main['profit_per_hour'], unit)} contribution per elapsed service hour; this excludes between-trip availability and repositioning.")

if tabs[1].open:
    with tabs[1]:
        st.subheader("Locate the economic leakage")
        profits = trips.contribution
        q1,q2,q3,q4 = st.columns(4)
        money_metric("P25 trip profit", profits.quantile(.25), q1)
        money_metric("Median trip profit", profits.median(), q2)
        money_metric("P75 trip profit", profits.quantile(.75), q3)
        money_metric("P90 trip profit", profits.quantile(.90), q4)
        l,r = st.columns(2)
        with l:
            edges = [-float('inf'),0,.10,.20,.30,.40,float('inf')]
            labels = ["Loss", "0–10%", "10–20%", "20–30%", "30–40%", "40%+"]
            buckets = trips.assign(margin_band=pd.cut(trips.margin, bins=edges, labels=labels, right=False)).groupby("margin_band", observed=False).agg(trips=("Id","size"), contribution=("contribution","sum")).reset_index()
            st.plotly_chart(bar(buckets,"margin_band","trips","Trip margin distribution",REVENUE),width="stretch")
        with r:
            duration = trips.assign(hours_band=pd.cut(trips.service_hours, bins=[0,2,4,6,8,12,float('inf')],labels=["<2h","2–4h","4–6h","6–8h","8–12h","12h+"],right=False))
            duration = grouped(duration,"hours_band")
            if not duration.empty:
                st.plotly_chart(bar(duration,"hours_band","profit_per_hour","Profit / service hour by duration",PROFIT),width="stretch")
        stop_bins = [-.1,0,30,60,120,240,float('inf')]
        stop_labels = ["0 min","1–30m","31–60m","61–120m","121–240m","240m+"]
        with_stop = trips.assign(stop_band=pd.cut(trips.StopTime.fillna(0),bins=stop_bins,labels=stop_labels,right=True))
        stop_groups = grouped(with_stop,"stop_band")
        l,r = st.columns(2)
        with l:
            if not stop_groups.empty:
                st.plotly_chart(bar(stop_groups,"stop_band","margin","Contribution margin by stop duration",REVENUE,percent=True),width="stretch")
        with r:
            fig = go.Figure()
            fig.add_bar(x=["Stop component"], y=[to_toman(recorded_stop_charge)], name="Customer stop charge",marker_color=REVENUE,hovertemplate="%{y:,.0f} Toman<extra>%{fullData.name}</extra>")
            fig.add_bar(x=["Stop component"], y=[to_toman(recorded_stop_driver_payout)], name="Recorded driver stop cost",marker_color=COST,hovertemplate="%{y:,.0f} Toman<extra>%{fullData.name}</extra>")
            fig.update_layout(title="Stop economics",barmode="group",yaxis_title=CURRENCY_UNIT)
            st.plotly_chart(style(fig),width="stretch")
        st.caption("Both stop fields are diagnostics only; neither is added to passenger fare or driver payout.")
        money_metric("Recorded stop driver amount · diagnostic only", recorded_stop_driver_payout, role="cost")
        st.metric("Free stop minutes · matched destinations only",count(agg.free_stop_minutes.sum(min_count=1)) if not agg.empty else "—")
        st.caption("No monetary cost is assigned to free stop minutes: the marginal cost and contract policy are not established, and destination coverage is incomplete.")
        st.subheader("Trip review · lowest contribution first")
        detail = trips.assign(service_hours=trips.service_hours.round(2), margin_pct=(trips.margin*100).round(1))
        cols = ["Id","date","OrganizationName","OriginCityName","DriverId","IsIntercity","service_hours","StopTime","passenger_fare","driver_payout","contribution","margin_pct"]
        st.dataframe(display_frame(detail.sort_values("contribution")[cols].head(100)), hide_index=True, width="stretch")

if tabs[2].open:
    with tabs[2]:
        st.subheader("Customer portfolio")
        org = grouped(trips,"OrganizationId")
        if not org.empty:
            org["OrganizationName"] = org.OrganizationId.map(organization_labels).fillna("Unknown organization")
            l,r = st.columns(2)
            with l:
                top = org.sort_values("passenger_fare",ascending=False).head(12).sort_values("contribution",ascending=False)
                st.plotly_chart(bar(top,"OrganizationName","contribution","Contribution by largest passenger_fare customers",PROFIT,horizontal=True),width="stretch")
            with r:
                top = org.sort_values("hours",ascending=False).head(12).sort_values("profit_per_hour",ascending=False)
                st.plotly_chart(bar(top,"OrganizationName","profit_per_hour","Profit/hour · highest capacity users",REVENUE,horizontal=True),width="stretch")
            st.dataframe(display_frame(org.sort_values("contribution",ascending=False)[["OrganizationName","trips","passenger_fare","driver_payout","contribution","margin","hours","profit_per_hour","loss_trips","stop_minutes","recorded_stop_charge","recorded_stop_driver_payout"]]),hide_index=True,width="stretch")
        st.subheader("Geography and service mix")
        geog = trips.assign(geography=trips.IsIntercity.map({0:"City",1:"Intercity"}).fillna("Unknown"))
        for label,col in [("Geography","geography"),("Service type code","ServiceType"),("Trip type code","TripType"),("Contract type code","ContractType"),("Origin city","OriginCityId")]:
            with st.expander(label,expanded=(label=="Geography")):
                group = grouped(geog,col)
                if not group.empty:
                    display_column = col
                    if col == "OriginCityId":
                        group["OriginCityName"] = group.OriginCityId.map(city_labels).fillna("Unknown city")
                        display_column = "OriginCityName"
                    st.dataframe(display_frame(group[[display_column,"trips","passenger_fare","contribution","margin","hours","profit_per_hour","loss_rate"]].sort_values("passenger_fare",ascending=False)),hide_index=True,width="stretch")
        st.caption("Organization and origin city names come from database lookups. Service and contract codes remain raw until authoritative labels are supplied.")

if tabs[3].open:
    with tabs[3]:
        st.subheader("Pricing and benchmarks")
        target = st.slider("Target direct contribution margin", min_value=0, max_value=50, value=25, step=5)/100
        pricing = trips[trips.passenger_fare.notna() & trips.driver_payout.notna()]
        fare_required = pricing.driver_payout / (1-target)
        price_required = fare_required / FARE_RETAINED_RATE
        shortfall = np.maximum(0,price_required-pricing.TripCost)
        c1,c2,c3 = st.columns(3)
        c1.metric(f"Trips below {target:.0%} margin", pct((pricing.passenger_fare < fare_required).mean()))
        money_metric("Sum of trip-level price shortfalls", shortfall.sum(), c2, role="cost")
        c3.metric("Direct break-even trips",count((pricing.passenger_fare < pricing.driver_payout).sum()))
        st.caption("Required base TripCost = TripDriverCost ÷ ((1 − 0.078) × (1 − target margin)), compared with recorded TripCost. Shortfalls are base trip-charge amounts, holding driver payout fixed. This scenario uses rows with known fare and payout and excludes additional adjustments, other costs, tax, demand response and the current Snapp Plus price ceiling. The supplied SnapPrice is not validated as snapp_plus_final; do not infer compliance with the 1.1× ceiling.")
        st.markdown(f'<div class="warn">Destination coverage is {len(agg):,}/{len(trips):,} trips ({pct(coverage)}). Any route-versus-Snapp result is a <b>selected subset</b>, not the business average.</div>',unsafe_allow_html=True)
        x,y,z = st.columns(3)
        x.metric("Destination/source charge matches",count(len(reconciled)))
        y.metric("Complete Snapp benchmark trips",count(len(snap)))
        z.metric("ML benchmark trips",count(int(agg.ml_comparable.sum()) if not agg.empty else 0))
        legs = data.destinations.copy()
        if not legs.empty:
            legs = legs[legs.SnapPrice.gt(0) & legs.DestinationCostWithoutStopTime.gt(0) &
                        np.isclose(legs.DestinationCost, legs.DestinationCostWithoutStopTime + legs.StopTimeDestinationCost, atol=1, rtol=0)].copy()
        if not legs.empty:
            leg_premium = ratio(legs.DestinationCostWithoutStopTime.sum(), legs.SnapPrice.sum())-1
            st.metric("Route/Snapp premium · comparable legs only",pct(leg_premium),f"{len(legs):,} of {len(data.destinations):,} matched destination legs",delta_color="off")
            st.caption("A separate leg-level diagnostic: sums only priced destination legs with positive route charge and positive Snapp reference. It does not estimate the premium for entire trips or the business.")
            fig = go.Figure()
            fig.add_scattergl(x=to_toman(legs.SnapPrice),y=to_toman(legs.DestinationCostWithoutStopTime),mode="markers",marker=dict(color=REVENUE,size=7,opacity=.55),hovertemplate="Snap %{x:,.0f} Toman<br>Route %{y:,.0f} Toman<extra></extra>")
            ceiling = to_toman(max(legs.DestinationCostWithoutStopTime.max(),legs.SnapPrice.max()))
            fig.add_scatter(x=[0,ceiling],y=[0,ceiling],mode="lines",line=dict(color=MUTED,dash="dash"),name="Equal")
            fig.update_layout(title="Comparable destination legs · selected subset",xaxis_title="Snapp price (Toman)",yaxis_title="Route-only customer charge (Toman)")
            st.plotly_chart(style(fig),width="stretch")
        if not snap.empty:
            premium = ratio(snap.route_charge.sum(),snap.snap_total.sum())-1
            st.metric("Route price premium / Snapp · matched subset",pct(premium))
            st.caption("Compare route-only destination passenger_fare with destination SnapPrice; require a positive SnapPrice at every matched destination. Confirm price snapshots and service equivalence before contract decisions.")
        else:
            st.info("There are no trips with complete destination and positive Snapp prices in this selection.")
        if not agg.empty:
            st.subheader("Source charge comparison")
            st.dataframe(display_frame(agg[["TripId","destinations","passenger_fare","source_trip_charge","destination_charge","route_charge","destination_stop_charge","snap_total","component_ok","source_charge_matches","snap_comparable"]].sort_values("TripId",ascending=False).head(100)),hide_index=True,width="stretch")

if tabs[4].open:
    with tabs[4]:
        st.subheader("Measurement coverage & reconciliation")
        diag = full.diagnostics
        qa = pd.DataFrame([
            ["Source trip rows",diag["raw_trip_rows"]],["Non-numeric trip IDs / source contamination",diag["non_numeric_trip_ids"]],
            ["Duplicate trip rows, retained",diag["duplicate_trip_rows"]],["Source rows excluded by financial rules",diag["not_completed_or_not_financial"]],
            ["Source rows in complete snapshot",diag["eligible_trips"]],["Nonpositive elapsed time",diag["nonpositive_duration"]],
            ["Elapsed time over 72 hours",diag["very_long_duration_over_72h"]],["Source destination rows",diag["raw_destination_rows"]],
            ["Matched destination rows",diag["matched_destination_rows"]],["Destination-covered trips in complete source",diag.get("destination_covered_trips",0)],
            ["Source charge matches in complete source",diag.get("reconciled_trips",0)]],columns=["Check (entire loaded source)","Count"])
        st.dataframe(qa,hide_index=True,width="stretch")
        a,b,c = st.columns(3)
        a.metric("Filtered trip coverage by destinations",pct(coverage))
        b.metric("Source charge matches / covered",pct(ratio(len(reconciled),len(agg))))
        c.metric("Snapp comparable / filtered",pct(ratio(len(snap),len(trips))))
        if not agg.empty:
            failures = agg[~agg.source_charge_matches]
            st.write(f"**{len(failures):,} covered trips do not match** to the destination components and source TripCost within one stored monetary unit. This comparison does not use retained passenger_fare. This is a raw source comparison, not a validated reconciliation rule or destination fare allocation.")
            st.dataframe(display_frame(failures[["TripId","passenger_fare","source_trip_charge","destination_charge","route_charge","destination_stop_charge","component_ok"]].head(100)),hide_index=True,width="stretch")
        st.markdown("**Controls before an executive meeting**")
        st.markdown("- Baseline: PassengerFare = CAST(TripCost AS DECIMAL(18,2)) × 0.922; DriverPayout = CAST(TripDriverCost AS DECIMAL(18,2)).\n- Both stop fields are diagnostics only. No status, completion, positive-fare, payout-sign or duplicate-ID exclusions are applied. NULL amounts are summed independently.\n- Source trip and destination charge comparisons are diagnostic; the baseline defines no destination financial allocation.\n- Select the same filters and date window when comparing with the DBA daily query.")
        st.download_button("Download filtered trip review (CSV · Toman)",lambda trips=trips: trip_review_csv(trips),file_name="kasbi_trip_finance_review_toman.csv",mime="text/csv",on_click="ignore")

if tabs[5].open:
    with tabs[5]:
        st.subheader("The 20 financial decisions")
        st.caption("Measured = calculable from trip data; provisional = interpretation or coverage needs validation; unavailable = new source data is required. All measured outcomes inherit the source quality checks.")
        questions = [
            (1,"Are we making money after direct driver payout?","Measured","Executive: passenger_fare, driver payout, contribution, margin"),
            (2,"What is the profit distribution per trip?","Measured","Where profit leaks: quantiles and margin bands"),
            (3,"What share of trips loses money, and how much?","Measured","Executive: loss rate and gross losses"),
            (4,"Why does each trip lose money?","Provisional","Where profit leaks: low-profit trip review; cause attribution needs operations logs"),
            (5,"How much contribution per service hour?","Provisional","Executive: elapsed service hours proxy, not full driver availability"),
            (6,"What is effective driver payout per service hour?","Provisional","TripDriverCost divided by valid elapsed hours; stop amounts are excluded"),
            (7,"Do stop charges cover driver stop cost?","Measured","Where profit leaks: recorded stop charges versus payouts; customer stop charges are excluded from baseline contribution"),
            (8,"What does free stop time cost us?","Unavailable","Free minutes on covered destinations; contract terms and marginal cost needed"),
            (9,"Is the route component profitable?","Unavailable","Route passenger_fare on reconciled destinations; no verified route driver-cost split"),
            (10,"How does route price compare with Snapp?","Provisional","Pricing: complete benchmark destinations only; service equivalence unverified"),
            (11,"Is ML pricing economically safe?","Provisional","Pricing: model-price coverage shown; historic quote/version and cost mapping needed"),
            (12,"Which customers generate contribution?","Measured","Customers: passenger_fare, contribution, margin, loss trips"),
            (13,"Which customers consume capacity inefficiently?","Provisional","Customers: contribution per elapsed service hour proxy"),
            (14,"How do city and intercity economics differ?","Measured","Customers & segments: separate aggregates"),
            (15,"Which cities, contracts and service types work?","Provisional","Customers & segments: named origin cities; service/contract labels and sample size need validation"),
            (16,"How does duration affect profitability?","Provisional","Where profit leaks: duration bands and contribution/hour proxy"),
            (17,"How does stop duration affect profitability?","Measured","Where profit leaks: stop bands and total trip margin"),
            (18,"What customer price meets a target direct margin?","Provisional","Pricing: direct driver-cost floor; excludes other costs and demand"),
            (19,"Are we profitable after all costs?","Unavailable","Need vehicle, fuel, insurance, operations, taxes, overhead and cost allocation"),
            (20,"Is contribution converting to cash?","Unavailable","Need invoices, settlements, due dates, receipts, credits and payment terms"),
        ]
        for number, question, status, evidence in questions:
            with st.expander(f"{number:02d}  {question}   ·   {status}"):
                st.write(evidence)
        st.markdown("### Next data contracts")
        st.dataframe(pd.DataFrame([
            ["Full costs","Cost event; trip, driver/vehicle or organization link; amount; period; cost type","Gross margin, operating profit, customer margin"],
            ["Billing & cash","Trip–invoice bridge; invoice amount/date; due date; receipts; credit notes","Collection rate, aged receivables, DSO, cash conversion"],
            ["Capacity & operations","Assignment, arrival, departure, release and reposition timestamps","Actual available hours, idle time and causal loss review"],
            ["Pricing history","Quoted route/stop price, ML version, approved discounts, Snapp snapshot","Price waterfall, policy compliance and model safety"],
            ["Master data","Service, contract and status code lookups; customer hierarchy","Meaningful segmentation and program-level economics"],
        ],columns=["Source","Minimum fields","Decisions unlocked"]),hide_index=True,width="stretch")

st.markdown(f'<div class="callout"><b>Definition:</b> passenger fare = CAST(TripCost AS DECIMAL(18,2)) × 0.922; driver payout = CAST(TripDriverCost AS DECIMAL(18,2)); contribution = passenger fare − driver payout. Neither stop field is added. <b>Period:</b> {period}. <b>Scope:</b> {count(main["trips"])} source rows.</div>', unsafe_allow_html=True)
