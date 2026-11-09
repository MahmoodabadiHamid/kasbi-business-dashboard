"""Tests for the financial failure modes that could mislead decisions."""
import unittest

import pandas as pd

from finance.metrics import Analysis, dimension_labels, grouped, summarize


class FinancialDefinitions(unittest.TestCase):
    def test_free_test_organization_and_its_destinations_are_excluded(self):
        from finance.metrics import EXCLUDED_ORGANIZATION_NAME
        trips = pd.DataFrame([
            dict(Id=1, OrganizationId=10, OrganizationName="  " + EXCLUDED_ORGANIZATION_NAME + "  ", DriverId=1, StartDateTime="2026-10-01", EndDateTime="2026-10-02", TripCost=10000, TripDriverCost=9000),
            dict(Id=2, OrganizationId=20, OrganizationName="Customer", DriverId=2, StartDateTime="2026-10-01", EndDateTime="2026-10-02", TripCost=100, TripDriverCost=50),
            dict(Id=3, OrganizationId=None, OrganizationName=None, DriverId=3, StartDateTime="2026-10-01", EndDateTime="2026-10-02", TripCost=100, TripDriverCost=50),
        ])
        destinations = pd.DataFrame([
            dict(Id=1, TripId=1, DestinationCost=10000, DestinationCostWithoutStopTime=10000, StopTimeDestinationCost=0),
            dict(Id=2, TripId=2, DestinationCost=100, DestinationCostWithoutStopTime=100, StopTimeDestinationCost=0),
        ])
        analysis = Analysis.from_frames(trips, destinations)
        self.assertEqual(analysis.trips.Id.tolist(), [2,3])
        self.assertEqual(analysis.destinations.TripId.tolist(), [2])
        self.assertAlmostEqual(summarize(analysis.trips)["passenger_fare"], 184.4)
        self.assertEqual(summarize(analysis.trips)["driver_payout"], 100)
        self.assertEqual(analysis.diagnostics["excluded_organization_rows"], 1)
        self.assertEqual(len(trips), 3)

    def setUp(self):
        self.trips = pd.DataFrame([
            dict(Id=1,OrganizationId=10,DriverId=7,StartDateTime="2026-09-01 09:00",EndDateTime="2026-09-01 11:00",TripCost=100,TripDriverCost=80,StopTimeCost=30,StopTimeDriverCost=35),
            dict(Id=2,OrganizationId=10,DriverId=8,StartDateTime="2026-09-01 09:00",EndDateTime="2026-09-01 13:00",TripCost=300,TripDriverCost=330,StopTimeCost=20,StopTimeDriverCost=25),
            dict(Id="workbook text",OrganizationId=None,DriverId=None,StartDateTime=None,EndDateTime=None,TripCost=None,TripDriverCost=None),
        ])
        self.dest = pd.DataFrame([
            dict(Id=21,TripId=1,DestinationCost=100,DestinationCostWithoutStopTime=80,StopTimeDestinationCost=20,SnapPrice=40,MlPrice=45,FreeStopTimeByMinutes=10),
            dict(Id=22,TripId=1,DestinationCost=30,DestinationCostWithoutStopTime=20,StopTimeDestinationCost=10,SnapPrice=20,MlPrice=24,FreeStopTimeByMinutes=0),
            dict(Id=23,TripId=2,DestinationCost=320,DestinationCostWithoutStopTime=300,StopTimeDestinationCost=20,SnapPrice=0,MlPrice=0,FreeStopTimeByMinutes=0),
        ])

    def test_retained_revenue_excludes_customer_stops_but_cost_includes_driver_stops_excluded(self):
        a = Analysis.from_frames(self.trips, self.dest)
        m = summarize(a.trips)
        self.assertAlmostEqual(m["passenger_fare"],368.8)
        self.assertEqual(m["driver_payout"],410)
        self.assertAlmostEqual(m["contribution"],368.8-410)
        self.assertEqual(m["loss_trips"],1)
        self.assertAlmostEqual(m["gross_losses"],330-276.6)
        self.assertAlmostEqual(m["margin"],(368.8-410)/(368.8))
        self.assertEqual(a.diagnostics["non_numeric_trip_ids"],1)

    def test_exact_coefficient_is_applied_once_without_changing_source(self):
        trips = self.trips.iloc[:1].copy()
        trips.loc[0, ["TripCost", "TripDriverCost", "StopTimeCost", "StopTimeDriverCost"]] = [1080, 800, 100, 50]
        original = trips.copy(deep=True)
        a = Analysis.from_frames(trips, self.dest)
        row = a.trips.iloc[0]
        self.assertAlmostEqual(row.passenger_fare, 995.76)
        self.assertAlmostEqual(row.fare_deduction, 84.24)
        self.assertEqual(row.driver_payout, 800)
        self.assertAlmostEqual(row.contribution, 195.76)
        self.assertEqual(row.source_trip_charge, 1080)
        pd.testing.assert_frame_equal(trips, original)

    def test_reconciliation_and_complete_competitor_coverage(self):
        a = Analysis.from_frames(self.trips, self.dest)
        d = a.destination_agg.set_index("TripId")
        self.assertFalse(bool(d.loc[1,"source_charge_matches"]))
        self.assertEqual(d.loc[1,"route_charge"],100)
        self.assertEqual(d.loc[1,"destination_charge"],130)
        self.assertFalse(bool(d.loc[2,"source_charge_matches"]))
        self.assertEqual(d.loc[1,"snap_total"],60)
        self.assertTrue(bool(d.loc[1,"snap_comparable"]))
        self.assertFalse(bool(d.loc[2,"snap_comparable"]))

    def test_ratio_of_sums_not_mean_of_trip_margins(self):
        a = Analysis.from_frames(self.trips, self.dest)
        result = grouped(a.trips,"OrganizationId").iloc[0]
        self.assertAlmostEqual(result["contribution"],368.8-410)
        self.assertAlmostEqual(result["margin"],(368.8-410)/(368.8))
        self.assertAlmostEqual(result["profit_per_hour"],(368.8-410)/6)
        self.assertAlmostEqual(result["passenger_fare_per_hour"],368.8/6)
        self.assertAlmostEqual(result["driver_payout_per_hour"],410/6)

    def test_missing_destinations_do_not_remove_trip_revenue(self):
        a = Analysis.from_frames(self.trips,self.dest.iloc[:2])
        self.assertEqual(len(a.trips),3)
        self.assertEqual(len(a.destination_agg),1)
        self.assertAlmostEqual(summarize(a.trips)["passenger_fare"],368.8)

    def test_additional_driver_stop_cost_does_not_change_baseline(self):
        trips = self.trips.iloc[:1].copy()
        trips.loc[0,"StopTimeDriverCost"] = 60
        a = Analysis.from_frames(trips, self.dest)
        m = summarize(a.trips)
        self.assertAlmostEqual(m["contribution"],92.2-80)
        self.assertEqual(m["loss_trips"],0)
        self.assertAlmostEqual(m["gross_losses"],0)

    def test_customer_stop_charge_cannot_create_or_cancel_retained_revenue(self):
        trips = self.trips.iloc[:2].copy()
        trips.loc[0,["TripCost","TripDriverCost","StopTimeCost","StopTimeDriverCost"]] = [0,0,30,20]
        trips.loc[1,["TripCost","StopTimeCost"]] = [300,-300]
        a = Analysis.from_frames(trips, self.dest)
        self.assertEqual(a.trips.Id.tolist(),[1,2])
        self.assertAlmostEqual(summarize(a.trips)["contribution"],276.6-330)
        self.assertEqual(a.diagnostics["not_completed_or_not_financial"],0)

    def test_null_components_sum_independently_without_row_exclusions(self):
        trips = self.trips.iloc[:2].copy()
        trips.loc[0,"TripCost"] = None
        trips.loc[1,"TripDriverCost"] = None
        a = Analysis.from_frames(trips, self.dest)
        self.assertEqual(len(a.trips),2)
        m = summarize(a.trips)
        self.assertAlmostEqual(m["passenger_fare"],276.6)
        self.assertEqual(m["driver_payout"],80)
        self.assertAlmostEqual(m["contribution"],196.6)
        self.assertAlmostEqual(grouped(a.trips,"date").iloc[0].contribution,196.6)

    def test_missing_stop_fields_do_not_affect_baseline(self):
        trips = self.trips.iloc[:2].drop(columns=["StopTimeCost","StopTimeDriverCost"])
        a = Analysis.from_frames(trips,self.dest)
        self.assertAlmostEqual(summarize(a.trips)["passenger_fare"],368.8)
        self.assertEqual(summarize(a.trips)["driver_payout"],410)

    def test_all_rows_are_retained_including_duplicates_negative_zero_and_missing_end(self):
        trips = self.trips.iloc[:2].copy()
        trips.loc[0,"EndDateTime"] = None
        trips.loc[0,"TripCost"] = -100
        trips.loc[1,"TripCost"] = 0
        trips.loc[1,"TripDriverCost"] = -20
        trips = pd.concat([trips,trips.iloc[:1]],ignore_index=True)
        a = Analysis.from_frames(trips,self.dest)
        self.assertEqual(len(a.trips),3)
        self.assertAlmostEqual(summarize(a.trips)["passenger_fare"],-184.4)
        self.assertEqual(summarize(a.trips)["driver_payout"],140)

    def test_daily_baseline_casts_before_multiply_and_floors_after_sum(self):
        from finance.metrics import daily_totals
        trips = self.trips.iloc[:2].copy()
        trips["TripCost"] = [10.005,10.005]
        trips["TripDriverCost"] = [5.005,5.005]
        a = Analysis.from_frames(trips,self.dest)
        daily = daily_totals(a.trips).iloc[0]
        self.assertEqual(daily.PassengerFare,1)
        self.assertEqual(daily.DriverPayout,1)
        self.assertAlmostEqual(summarize(a.trips)["passenger_fare"],18.45844)
        self.assertAlmostEqual(daily.MarginPercent,45.72)
        trips["TripCost"] = 0
        a = Analysis.from_frames(trips,self.dest)
        self.assertTrue(pd.isna(daily_totals(a.trips).iloc[0].MarginPercent))

    def test_offsetting_destination_errors_do_not_fake_reconciliation(self):
        corrupted = self.dest.copy()
        corrupted.loc[0,"DestinationCost"] += 5
        corrupted.loc[1,"DestinationCost"] -= 5
        a = Analysis.from_frames(self.trips,corrupted)
        self.assertFalse(bool(a.destination_agg.set_index("TripId").loc[1,"source_charge_matches"]))

    def test_city_filter_keeps_trip_and_destination_scope_together(self):
        trips = self.trips.copy()
        trips["OriginCityId"] = [1,2,None]
        a = Analysis.from_frames(trips,self.dest).filter(organizations=[10],cities=[2])
        self.assertEqual(a.trips.Id.tolist(),[2])
        self.assertEqual(a.destinations.TripId.tolist(),[2])
        self.assertEqual(a.destination_agg.TripId.tolist(),[2])
        self.assertAlmostEqual(summarize(a.trips)["passenger_fare"],276.6)

    def test_readable_labels_keep_duplicate_names_and_missing_names_distinct(self):
        trips = pd.DataFrame({"OrganizationId":[1,2,3,4,None],"OrganizationName":[" Shared ","Shared"," ",None,None]})
        labels = dimension_labels(trips,"OrganizationId","OrganizationName","Organization")
        self.assertEqual(labels,{1:"Shared (1)",2:"Shared (2)",3:"Organization 3",4:"Organization 4"})

    def test_missing_destination_amounts_and_partial_benchmarks_stay_unknown(self):
        destinations = self.dest.copy()
        destinations.loc[destinations.TripId == 1, ["DestinationCostWithoutStopTime", "SnapPrice", "MlPrice"]] = None
        destinations.loc[destinations.TripId == 2, "SnapPrice"] = -10
        analysis = Analysis.from_frames(self.trips, destinations)
        agg = analysis.destination_agg.set_index("TripId")
        self.assertTrue(pd.isna(agg.loc[1, "route_charge"]))
        self.assertTrue(pd.isna(agg.loc[1, "snap_total"]))
        self.assertTrue(pd.isna(agg.loc[1, "ml_total"]))
        self.assertEqual(agg.loc[1, "snap_rows"], 0)
        self.assertEqual(agg.loc[1, "ml_rows"], 0)
        self.assertFalse(bool(agg.loc[1, "source_charge_matches"]))
        self.assertFalse(bool(agg.loc[1, "snap_comparable"]))
        self.assertFalse(bool(agg.loc[2, "snap_comparable"]))
        self.assertAlmostEqual(summarize(analysis.trips)["passenger_fare"], 368.8)

    def test_grouped_totals_match_financial_definitions_for_null_categories_and_hours(self):
        trips = Analysis.from_frames(self.trips.iloc[:2], self.dest).trips
        trips = pd.concat([trips, trips.assign(Id=trips.Id + 10)], ignore_index=True)
        trips.loc[[0, 2], "service_hours"] = None
        trips.loc[[2, 3], "StopTime"] = None
        for categories in (["A", "A", None, None], pd.Categorical(["A", "A", None, None], categories=["A", "unused"])):
            with self.subTest(categorical=isinstance(categories, pd.Categorical)):
                trips["segment"] = categories
                expected = []
                for label, frame in trips.groupby("segment", dropna=False, sort=True, observed=True):
                    expected.append({"segment": label, **summarize(frame),
                                     "stop_minutes": frame.StopTime.sum(min_count=1),
                                     "recorded_stop_charge": frame.StopTimeCost.sum(min_count=1),
                                     "recorded_stop_driver_payout": frame.StopTimeDriverCost.sum(min_count=1)})
                actual = grouped(trips, "segment")
                actual["segment"] = actual.segment.astype(object)
                pd.testing.assert_frame_equal(actual, pd.DataFrame(expected), check_dtype=False, check_like=True)

    def test_aggregate_coverage_drops_all_duplicate_destination_ids_and_orphans(self):
        destinations = pd.concat([self.dest, self.dest.iloc[:1], self.dest.iloc[:1].assign(Id=999, TripId=999)], ignore_index=True)
        analysis = Analysis.from_frames(self.trips, destinations)
        agg = analysis.destination_agg.set_index("TripId")
        self.assertEqual(analysis.destinations.Id.tolist(), [22, 23])
        self.assertEqual(agg.loc[1, "destinations"], 1)
        self.assertEqual(agg.loc[1, "destination_charge"], 30)
        self.assertFalse(bool(agg.loc[1, "source_charge_matches"]))
        self.assertEqual(analysis.diagnostics["duplicate_destination_rows"], 1)


if __name__ == "__main__":
    unittest.main()
