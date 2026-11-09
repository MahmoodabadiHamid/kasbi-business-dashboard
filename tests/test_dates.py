"""Check Shamsi year boundaries, validation and source timestamp preservation."""
from datetime import date
import unittest

import pandas as pd

from finance.dates import parse_shamsi, shamsi_date, shamsi_frame


class ShamsiDates(unittest.TestCase):
    def test_nowruz_and_leap_day_round_trips(self):
        for gregorian, shamsi in (
            (date(2025, 3, 20), "1403.12.30"),
            (date(2025, 3, 21), "1404.01.01"),
            (date(2026, 4, 1), "1405.01.12"),
            (date(2026, 10, 20), "1405.07.28"),
        ):
            with self.subTest(shamsi=shamsi):
                self.assertEqual(shamsi_date(gregorian), shamsi)
                self.assertEqual(parse_shamsi(shamsi), gregorian)

    def test_input_digits_separators_and_invalid_dates(self):
        self.assertIsNone(parse_shamsi("  "))
        for value in ("۱۴۰۵/۰۷/۲۸", "١٤٠٥-٠٧-٢٨", "1405.7.28"):
            self.assertEqual(parse_shamsi(value), date(2026, 10, 20))
        for value in ("1404.12.30", "1405.07.31", "1405.13.01", "bad", "1405/07-28"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                parse_shamsi(value)

    def test_date_frame_keeps_local_time_and_source_values(self):
        source = pd.DataFrame({
            "date": [date(2026, 10, 20), None],
            "StartDateTime": [pd.Timestamp("2026-10-20 23:59:30"), pd.NaT],
            "passenger_fare": [10, 20],
        })
        original = source.copy(deep=True)
        converted = shamsi_frame(source)
        self.assertEqual(converted.date.tolist(), ["1405.07.28", ""])
        self.assertEqual(converted.StartDateTime.tolist(), ["1405.07.28 23:59:30", ""])
        pd.testing.assert_frame_equal(source, original)
        pd.testing.assert_series_equal(converted.passenger_fare, source.passenger_fare)
