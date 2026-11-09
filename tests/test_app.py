"""Exercise the default start date and clearing filters through the page."""
from io import BytesIO
import json
import re
from pathlib import Path
import unittest
from unittest.mock import patch

import pandas as pd
import streamlit as st
from streamlit.testing.v1 import AppTest

from finance.load import DEST_REQUIRED
from finance.metrics import Analysis


def money_value(app, label="Customer passenger_fare"):
    card = next(element.value for element in app.markdown if f'aria-label="{label}"' in element.value)
    return re.search(r'class="money-metric-amount">([^<]*)', card).group(1)


def show_view(app, label):
    app.session_state["finance_view"] = label
    return app.run()


class DashboardFilters(unittest.TestCase):
    def test_baseline_keeps_duplicate_ids_negative_amounts_and_unknown_dates(self):
        raw = pd.DataFrame([
            dict(Id=1, OrganizationId=10, DriverId=1, StartDateTime="2026-10-01 09:00", EndDateTime="2026-10-01 11:00", TripCost=100, TripDriverCost=40),
            dict(Id=1, OrganizationId=10, DriverId=1, StartDateTime=None, EndDateTime=None, TripCost=-10, TripDriverCost=-5),
        ])
        st.cache_data.clear()
        self.addCleanup(st.cache_data.clear)
        with patch("finance.load.read_database", return_value=(raw, pd.DataFrame(columns=sorted(DEST_REQUIRED)))):
            app = AppTest.from_file(str(Path(__file__).resolve().parents[1] / "app.py"), default_timeout=20).run()
            self.assertFalse(app.exception)
            app.button[0].click().run()
            self.assertFalse(app.exception)
            self.assertEqual(money_value(app), "8")
            self.assertEqual(len(app.dataframe[0].value), 2)
            self.assertIn("Unknown start date", app.dataframe[0].value.TripDate.tolist())

    def test_ml_pricing_marker_is_present_on_every_date_chart(self):
        raw = pd.DataFrame([
            dict(Id=index, OrganizationId=10, DriverId=1, StartDateTime=f"2026-10-{day} 09:00", EndDateTime=f"2026-10-{day} 11:00", TripCost=100, StopTimeCost=0, TripDriverCost=90, StopTimeDriverCost=0, IsIntercity=0, StopTime=0)
            for index, day in enumerate((16, 18), start=1)
        ])
        st.cache_data.clear()
        self.addCleanup(st.cache_data.clear)
        with patch("finance.load.read_database", return_value=(raw, pd.DataFrame(columns=sorted(DEST_REQUIRED)))):
            app = AppTest.from_file(str(Path(__file__).resolve().parents[1] / "app.py"), default_timeout=20).run()
        self.assertFalse(app.exception)
        charts = [json.loads(chart.proto.spec) for chart in app.tabs[0].get("plotly_chart")]
        for chart in charts[:3]:
            marker = next(trace for trace in chart["data"] if trace.get("name") == "ML pricing")
            self.assertIn("17 October 2026", marker["hovertemplate"])
            self.assertFalse(chart["layout"].get("annotations"))
        self.assertEqual(charts[1]["layout"]["yaxis"]["range"], [.9, 1])
        self.assertEqual(charts[1]["layout"]["shapes"][0]["x0"], .5)
        self.assertEqual(charts[2]["layout"]["xaxis"]["type"], "date")
        self.assertIn("1405.07.24", charts[2]["data"][0]["hovertext"][0])

    def test_default_start_date_and_all_history_after_clearing(self):
        raw = pd.DataFrame([
            dict(Id=1,OrganizationId=10,DriverId=1,StartDateTime="2020-01-01 09:00",EndDateTime="2020-01-01 11:00",TripCost=100,StopTimeCost=10,TripDriverCost=80,StopTimeDriverCost=5,IsIntercity=0,StopTime=10),
            dict(Id=2,OrganizationId=20,DriverId=2,StartDateTime="2026-10-01 09:00",EndDateTime="2026-10-01 11:00",TripCost=200,StopTimeCost=20,TripDriverCost=250,StopTimeDriverCost=25,IsIntercity=1,StopTime=20),
        ])
        raw["OrganizationName"] = ["Alpha Pharma", "Beta Pharma"]
        raw["OriginCityId"] = [1,2]
        raw["OriginCityName"] = ["Tehran", "Shiraz"]
        st.cache_data.clear()
        self.addCleanup(st.cache_data.clear)
        with patch("finance.load.read_database",return_value=(raw,pd.DataFrame(columns=sorted(DEST_REQUIRED)))) as read:
            app = AppTest.from_file(str(Path(__file__).resolve().parents[1] / "app.py"),default_timeout=20).run()
            self.assertFalse(app.exception)
            read.assert_called_once_with()
            self.assertEqual(app.text_input(key="trip_start_shamsi").value,"1405.01.12")
            self.assertEqual(app.text_input(key="trip_end_shamsi").value,"")
            self.assertEqual(app.selectbox[0].value,"All")
            self.assertEqual(app.multiselect[0].value,[])
            self.assertEqual(app.multiselect[0].options,["Alpha Pharma","Beta Pharma"])
            self.assertEqual(app.multiselect[1].options,["Shiraz","Tehran"])
            self.assertEqual(money_value(app),"18")
            self.assertEqual(next(metric for metric in app.metric if metric.label == "Contribution margin").value,"-35.6%")
            chart_titles = [json.loads(chart.proto.spec)["layout"]["title"]["text"] for chart in app.tabs[0].get("plotly_chart")]
            self.assertEqual(chart_titles[:3], [
                "Cumulative daily economic trend", "Daily economic trend · passenger fare = 100%",
                "Contribution per service hour",
            ])
            self.assertEqual(len(app.dataframe), 1)
            show_view(app, "Where profit leaks")
            self.assertFalse(app.exception)
            self.assertEqual(app.dataframe[0].value["OrganizationName"].tolist(),["Beta Pharma"])
            self.assertEqual(app.dataframe[0].value["OriginCityName"].tolist(),["Shiraz"])
            self.assertEqual(app.dataframe[0].value["passenger_fare"].tolist(),["18"])
            self.assertEqual(app.dataframe[0].value["service_hours"].tolist(),[2.0])
            self.assertEqual(app.dataframe[0].value["date"].tolist(),["1405.07.09"])
            show_view(app, "Executive")

            app.text_input(key="trip_start_shamsi").set_value("1405.07.09")
            app.text_input(key="trip_end_shamsi").set_value("1405.07.09").run()
            self.assertFalse(app.exception)
            self.assertEqual(money_value(app),"18")
            app.selectbox[0].select("City").run()
            self.assertFalse(app.exception)
            self.assertTrue(app.warning)

            app.button[0].click().run()
            self.assertFalse(app.exception)
            self.assertEqual(app.text_input(key="trip_start_shamsi").value,"")
            self.assertEqual(app.text_input(key="trip_end_shamsi").value,"")
            self.assertEqual(app.selectbox[0].value,"All")
            self.assertEqual(money_value(app),"28")

            app.multiselect[0].set_value([10]).run()
            self.assertFalse(app.exception)
            self.assertEqual(money_value(app),"9")
            app.button[0].click().run()
            self.assertEqual(app.multiselect[0].value,[])
            self.assertEqual(money_value(app),"28")

            app.text_input(key="trip_start_shamsi").set_value("1405.07.09").run()
            self.assertFalse(app.exception)
            self.assertEqual(money_value(app),"18")
            app.button[0].click().run()
            self.assertFalse(app.exception)
            self.assertEqual(money_value(app),"28")

            app.multiselect[1].set_value([1]).run()
            self.assertFalse(app.exception)
            self.assertEqual(money_value(app),"9")
            app.button[0].click().run()
            self.assertFalse(app.exception)
            self.assertEqual(app.multiselect[1].value,[])
            self.assertEqual(money_value(app),"28")

            # End-only filters and invalid/reversed dates retain safe filtering behavior.
            app.text_input(key="trip_end_shamsi").set_value("1398.10.11").run()
            self.assertFalse(app.exception)
            self.assertEqual(money_value(app),"9")
            app.text_input(key="trip_start_shamsi").set_value("1405.07.09").run()
            self.assertTrue(app.error)
            self.assertFalse(app.metric)
            read.assert_called_once_with()
            app.button[0].click().run()
            app.text_input(key="trip_start_shamsi").set_value("1405.07.31").run()
            self.assertTrue(app.error)
            self.assertFalse(app.exception)
            self.assertFalse(app.metric)

    def test_compact_metrics_tables_and_precise_shamsi_csv(self):
        raw = pd.DataFrame([
            dict(Id=1,OrganizationId=10,DriverId=1,StartDateTime="2026-10-01 09:00",EndDateTime="2026-10-01 11:00",TripCost=40_000_000_000,StopTimeCost=0,TripDriverCost=36_820_000_000,StopTimeDriverCost=0,IsIntercity=0,StopTime=10),
        ])
        destinations = pd.DataFrame([
            dict(Id=1,TripId=1,DestinationCost=40_000_000_000,DestinationCostWithoutStopTime=40_000_000_000,StopTimeDestinationCost=0,SnapPrice=35_000_000_000),
        ])
        st.cache_data.clear()
        self.addCleanup(st.cache_data.clear)
        with patch("finance.load.read_database",return_value=(raw,destinations)), patch("streamlit.download_button") as download:
            app = AppTest.from_file(str(Path(__file__).resolve().parents[1] / "app.py"),default_timeout=20).run()
            self.assertFalse(app.exception)
            self.assertEqual(money_value(app),"3.69 B")
            self.assertEqual(money_value(app,"Contribution"),"6 M")
            download.assert_not_called()
            show_view(app, "Where profit leaks")
            self.assertEqual(app.dataframe[0].value["contribution"].tolist(),["6 M"])
            download.assert_not_called()
            show_view(app, "Data trust")
            self.assertFalse(app.exception)
            self.assertTrue(callable(download.call_args.args[1]))
            exported = pd.read_csv(BytesIO(download.call_args.args[1]()))
            self.assertEqual(exported.passenger_fare_toman.tolist(),[3_688_000_000])
            self.assertEqual(exported.contribution_toman.tolist(),[6_000_000])
            self.assertEqual(exported.fare_deduction_toman.tolist(),[312_000_000])
            self.assertEqual(exported.StartDateTime_shamsi.tolist(),["1405.07.09 09:00:00"])
            self.assertEqual(exported.EndDateTime_shamsi.tolist(),["1405.07.09 11:00:00"])
            self.assertEqual(exported.service_hours.tolist(),[2])

    def test_prepared_history_reused_until_refresh_and_only_active_tab_runs(self):
        raw = pd.DataFrame([
            dict(Id=1, OrganizationId=10, DriverId=1, StartDateTime="2026-10-01 09:00", EndDateTime="2026-10-01 11:00", TripCost=200, StopTimeCost=20, TripDriverCost=100, StopTimeDriverCost=10, IsIntercity=0, StopTime=20),
            dict(Id=2, OrganizationId=20, DriverId=2, StartDateTime="2026-10-02 09:00", EndDateTime="2026-10-02 11:00", TripCost=300, StopTimeCost=30, TripDriverCost=200, StopTimeDriverCost=20, IsIntercity=1, StopTime=20),
        ])
        destinations = pd.DataFrame([
            dict(Id=1, TripId=1, DestinationCost=220, DestinationCostWithoutStopTime=200, StopTimeDestinationCost=20, SnapPrice=190, MlPrice=210),
            dict(Id=2, TripId=2, DestinationCost=330, DestinationCostWithoutStopTime=300, StopTimeDestinationCost=30, SnapPrice=290, MlPrice=310),
        ])
        updated = raw.copy()
        updated.loc[0, "TripCost"] = 400
        st.cache_data.clear()
        self.addCleanup(st.cache_data.clear)
        with patch("finance.load.read_database", side_effect=[(raw, destinations), (updated, destinations)]) as read, \
                patch("finance.metrics.Analysis.from_frames", wraps=Analysis.from_frames) as prepare, \
                patch("streamlit.download_button") as download:
            app = AppTest.from_file(str(Path(__file__).resolve().parents[1] / "app.py"), default_timeout=20).run()
            self.assertFalse(app.exception)
            self.assertEqual(money_value(app), "46")
            self.assertFalse(app.tabs[1].get("plotly_chart"))
            self.assertFalse(app.tabs[3].get("slider"))
            download.assert_not_called()
            show_view(app, "Pricing & benchmarks")
            self.assertFalse(app.exception)
            self.assertEqual(money_value(app, "Sum of trip-level price shortfalls"), "0")
            show_view(app, "Executive")
            app.selectbox(key="service_geography").select("City").run()
            self.assertFalse(app.exception)
            self.assertEqual(money_value(app), "18")
            for label in ("Where profit leaks", "Customers & segments", "Pricing & benchmarks", "Data trust", "20 decisions"):
                show_view(app, label)
                self.assertFalse(app.exception, label)
                self.assertFalse(app.tabs[0].get("plotly_chart"))
            self.assertEqual(prepare.call_count, 1)
            self.assertEqual(read.call_count, 1)
            show_view(app, "Executive")
            app.button[1].click().run()
            self.assertFalse(app.exception)
            self.assertEqual(read.call_count, 2)
            self.assertEqual(prepare.call_count, 2)
            self.assertEqual(money_value(app), "37")
            self.assertEqual(app.selectbox(key="service_geography").value, "City")
