"""Check that all history is loaded unless bounds are explicitly supplied."""
import unittest
from pathlib import Path
from unittest.mock import patch

import pandas as pd

from finance.load import read_database


class DatabaseScope(unittest.TestCase):
    def test_every_sql_script_excludes_the_free_test_organization(self):
        from finance.metrics import EXCLUDED_ORGANIZATION_NAME
        for source in (Path(__file__).resolve().parents[1] / "sql").glob("*.sql"):
            with self.subTest(source=source.name):
                query = source.read_text(encoding="utf-8")
                self.assertIn("N'" + EXCLUDED_ORGANIZATION_NAME + "'", query)
                self.assertIn("NOT EXISTS", query)
                self.assertIn("excluded_org.Id = t.OrganizationId", query)

    def test_default_and_optional_date_bounds(self):
        for start, end in ((None,None), ("2026-01-01","2026-02-01"), ("2026-01-01",None), (None,"2026-02-01")):
            with self.subTest(start=start,end=end), \
                    patch("finance.load.connection_string",return_value="test connection"), \
                    patch("pyodbc.connect"), \
                    patch("finance.load.pd.read_sql_query",side_effect=[pd.DataFrame(),pd.DataFrame()]) as read:
                read_database(start,end)
                self.assertEqual(read.call_count,2)
                trip_query = read.call_args_list[0].args[0]
                self.assertIn("CAST(t.TripCost AS DECIMAL(18,2)) * 0.922 AS PassengerFare", trip_query)
                self.assertIn("CAST(t.TripCost AS DECIMAL(18,2)) * 0.078 AS FareDeduction", trip_query)
                self.assertIn("CAST(t.TripDriverCost AS DECIMAL(18,2)) AS DriverPayout", trip_query)
                for call in read.call_args_list:
                    self.assertEqual(call.kwargs["params"],[start,start,end,end])
                    self.assertEqual(call.args[0].count("?"),4)
                    self.assertIn("IS NULL",call.args[0])

    def test_invalid_window_does_not_connect(self):
        with patch("pyodbc.connect") as connect:
            with self.assertRaises(ValueError):
                read_database("2026-02-01","2026-01-01")
            connect.assert_not_called()
