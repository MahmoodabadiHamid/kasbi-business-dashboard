"""Check presentation conversion preserves financial source data and other units."""
import unittest

import pandas as pd

from finance.currency import compact_amount, toman_frame


class TomanPresentation(unittest.TestCase):
    def test_compact_amounts_and_rounding_boundaries(self):
        for value, expected in (
            (4_000_000_000, "4 B"), (6_000_000, "6 M"),
            (1_234_567_890, "1.23 B"), (-6_250_000, "-6.25 M"),
            (999_999_999, "1 B"), (999_999, "999,999"),
            (0, "0"), (float("nan"), "—"),
        ):
            with self.subTest(value=value):
                self.assertEqual(compact_amount(value), expected)

    def test_amounts_convert_without_changing_source_or_other_units(self):
        source = pd.DataFrame({
            "Id": [10, 20, 30],
            "passenger_fare": [12345.0, 0, float("nan")],
            "contribution": [-125.0, 0, float("nan")],
            "StopTimeCost": [15, 0, 20],
            "SnapPrice": [250, 0, 300],
            "profit_per_hour": [-62.5, 0, float("nan")],
            "margin": [-0.1, 0, float("nan")],
            "service_hours": [2.0, 3.0, 4.0],
            "StopTime": [30, 0, 60],
        })
        original = source.copy(deep=True)
        converted = toman_frame(source)
        self.assertEqual(converted.passenger_fare.iloc[0], 1234.5)
        self.assertEqual(converted.contribution.iloc[0], -12.5)
        self.assertEqual(converted.StopTimeCost.iloc[0], 1.5)
        self.assertEqual(converted.SnapPrice.iloc[0], 25)
        self.assertEqual(converted.profit_per_hour.iloc[0], -6.25)
        self.assertEqual(converted.passenger_fare.iloc[1], 0)
        self.assertTrue(pd.isna(converted.passenger_fare.iloc[2]))
        for column in ("Id", "margin", "service_hours", "StopTime"):
            pd.testing.assert_series_equal(converted[column], source[column])
        pd.testing.assert_frame_equal(source, original)
