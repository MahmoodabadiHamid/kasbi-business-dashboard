"""Repeatable synthetic timings; never connects to the production database."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from time import perf_counter
from unittest.mock import patch

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from finance.metrics import Analysis, grouped


def sample_frames(count):
    ids = np.arange(1, count + 1)
    starts = pd.Timestamp("2026-04-01") + pd.to_timedelta(ids % 210, unit="D")
    trips = pd.DataFrame(dict(
        Id=ids, OrganizationId=ids % 100, DriverId=ids % 500,
        StartDateTime=starts, EndDateTime=starts + pd.Timedelta(hours=2),
        TripCost=900_000, StopTimeCost=90_000, TripDriverCost=800_000,
        StopTimeDriverCost=90_000, StopTime=30, OriginCityId=ids % 8, IsIntercity=ids % 2,
    ))
    destinations = pd.DataFrame(dict(
        Id=np.arange(count * 3), TripId=np.repeat(ids, 3), DestinationCost=330_000,
        DestinationCostWithoutStopTime=300_000, StopTimeDestinationCost=30_000,
        SnapPrice=290_000, MlPrice=320_000,
    ))
    return trips, destinations


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--trips", type=int, default=20_000)
    parser.add_argument("--app", action="store_true", help="Also time initial and warm-filter Streamlit runs")
    args = parser.parse_args()
    raw, destinations = sample_frames(args.trips)
    started = perf_counter()
    analysis = Analysis.from_frames(raw, destinations)
    result = dict(trips=len(raw), destinations=len(destinations), prepare_seconds=perf_counter() - started)
    started = perf_counter()
    grouped(analysis.trips, "date")
    result["daily_group_seconds"] = perf_counter() - started
    if args.app:
        import streamlit as st
        from streamlit.testing.v1 import AppTest

        st.cache_data.clear()
        with patch("finance.load.read_database", return_value=(raw, destinations)) as read:
            app = AppTest.from_file(str(ROOT / "app.py"), default_timeout=120)
            started = perf_counter()
            app.run()
            result["initial_app_seconds"] = perf_counter() - started
            if app.exception:
                raise RuntimeError(app.exception[0].message)
            started = perf_counter()
            app.selectbox(key="service_geography").select("City").run()
            result["filter_seconds"] = perf_counter() - started
            result["database_reads"] = read.call_count
            if app.exception:
                raise RuntimeError(app.exception[0].message)
        st.cache_data.clear()
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
