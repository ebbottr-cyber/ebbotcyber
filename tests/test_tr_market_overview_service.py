"""Offline-only safety tests: no Yahoo calls, no network or credentials."""
import math
import unittest
from datetime import date, datetime, timedelta

from src.services.tr_market_overview_service import (
    INSTRUMENTS,
    _history_close_rows,
    build_overview,
    quote_from_rows,
)


class FakeFrame:
    def __init__(self, entries):
        self.entries = entries
        self.empty = not bool(entries)

    def iterrows(self):
        return iter(self.entries)


class FakeTicker:
    def __init__(self, symbol, history_map):
        self.symbol = symbol
        self.history_map = history_map

    def history(self, **params):
        assert params == {
            "period": "10d", "interval": "1d", "auto_adjust": False, "timeout": 8,
        }
        if self.symbol not in self.history_map:
            raise RuntimeError("Provider unavailable")
        return FakeFrame(self.history_map[self.symbol])


class MarketOverviewTests(unittest.TestCase):
    def setUp(self):
        self.today = date(2026, 11, 18)
        self.days = [self.today - timedelta(days=2), self.today - timedelta(days=1)]

    def test_fixed_turkey_symbol_mapping(self):
        self.assertEqual(
            [row[2] for row in INSTRUMENTS],
            ["XU100.IS", "XU030.IS", "TRY=X", "EURTRY=X"],
        )

    def test_valid_daily_close_and_real_change(self):
        rows = list(zip(self.days, (100.0, 105.0)))
        item = quote_from_rows("usdtry", "USD/TRY", "TRY=X", "TRY", rows, self.today)
        self.assertEqual(item["status"], "ready")
        self.assertEqual(item["price"], 105.0)
        self.assertEqual(item["change_pct"], 5.0)
        self.assertEqual(item["as_of"], "2026-11-17")
        self.assertIn("gecikmeli", item["source"])

    def test_old_or_future_data_is_not_shown_as_current(self):
        item = quote_from_rows(
            "bist100", "BIST 100", "XU100.IS", "TRY",
            [(self.today - timedelta(days=10), 1234.0)], self.today,
        )
        self.assertEqual(item["status"], "stale")
        self.assertIsNone(item["price"])
        self.assertIsNone(item["change_pct"])
        future = quote_from_rows(
            "bist100", "BIST 100", "XU100.IS", "TRY",
            [(self.today + timedelta(days=1), 1234.0)], self.today,
        )
        self.assertEqual(future["status"], "unavailable")

    def test_bad_numeric_provider_values_are_rejected(self):
        frame = FakeFrame([
            (datetime(2026, 11, 16), {"Close": math.nan}),
            (datetime(2026, 11, 17), {"Close": 0}),
            (datetime(2026, 11, 18), {"Close": 98.25}),
        ])
        self.assertEqual(_history_close_rows(frame), [(self.today, 98.25)])
        item = quote_from_rows(
            "eurtry", "EUR/TRY", "EURTRY=X", "TRY",
            _history_close_rows(frame), self.today,
        )
        self.assertIsNone(item["change_pct"])

    def test_provider_failure_is_isolated_and_gold_is_not_fabricated(self):
        mapping = {
            "XU100.IS": [
                (datetime(2026, 11, 16), {"Close": 10900}),
                (datetime(2026, 11, 17), {"Close": 11010}),
            ],
        }
        calls = []

        def factory(symbol):
            calls.append(symbol)
            return FakeTicker(symbol, mapping)

        result = build_overview(factory, today=self.today)
        self.assertEqual(result["cadence"], "delayed_daily")
        self.assertEqual(calls, [r[2] for r in INSTRUMENTS])
        self.assertEqual(len(result["items"]), 5)
        self.assertEqual(result["items"][0]["price"], 11010)
        self.assertTrue(all(item["price"] is None for item in result["items"][1:]))
        self.assertEqual(result["items"][-1]["symbol"], None)
        self.assertIn("henüz", result["items"][-1]["note"])

    def test_no_provider_yields_only_unavailable_prices(self):
        # Direct quote calculation cannot turn an empty series into a fake value.
        item = quote_from_rows("bist30", "BIST 30", "XU030.IS", "TRY", [], self.today)
        self.assertEqual(item["status"], "unavailable")
        self.assertIsNone(item["price"])


if __name__ == "__main__":
    unittest.main()
