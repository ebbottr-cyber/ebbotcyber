"""Fail-closed read-only operator coverage report reader tests."""
from __future__ import annotations

from datetime import date
import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from src.services.equity_data_coverage_reader import read_equity_coverage_report


DAY = date(2026, 11, 21)


def fixture() -> dict:
    names = ("tr", "us", "de", "hk")
    rows = {}
    for market in names:
        rows[market] = {
            "candidate_instruments": 2, "stocks": 2, "etfs": 0,
            "with_any_ohlcv": 1, "with_min_bars": 1, "with_recent_bar": 1,
            "undated_inventory_count": 0, "missing_ohlcv_count": 1,
            "insufficient_history_count": 0, "stale_ohlcv_count": 0,
            "missing_symbols": ["secret_should_never_be_returned"],
        }
    return {
        "status": "BLOCKED_INCOMPLETE_EVIDENCE",
        "selected_markets": list(names),
        "as_of_utc_date": DAY.isoformat(),
        "markets": rows,
        "total_candidate_instruments": 8,
        "orders": 0,
    }


class ReaderTests(unittest.TestCase):
    def setUp(self):
        self.tmp = TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / "report.json"

    def save(self, data: dict) -> str:
        self.path.write_text(json.dumps(data), encoding="utf-8")
        return str(self.path)

    def test_unconfigured_path_never_invents_counts(self):
        with patch.dict(os.environ, {"EBBOT_EQUITY_COVERAGE_REPORT_PATH": ""}):
            response = read_equity_coverage_report(today=DAY)
        self.assertEqual(response["status"], "unavailable")
        self.assertIsNone(response["total_candidate_instruments"])
        self.assertEqual(response["markets"], {})

    def test_safe_valid_aggregate_does_not_expose_symbols_or_prices(self):
        data = fixture()
        text = self.save(data)
        report = read_equity_coverage_report(text, today=DAY)
        self.assertEqual(report["status"], "unverified")
        self.assertEqual(report["total_candidate_instruments"], 8)
        self.assertEqual(report["markets"]["us"]["missing_ohlcv_count"], 1)
        self.assertNotIn("secret_should_never_be_returned", json.dumps(report))
        self.assertNotIn("missing_symbols", json.dumps(report))
        self.assertFalse(report["licensed_ohlcv_verified"])
        self.assertFalse(report["paper_trading_enabled"])
        self.assertFalse(report["live_trading_enabled"])

    def test_older_than_seven_days_explicitly_stale(self):
        data = fixture()
        data["as_of_utc_date"] = "2026-11-01"
        report = read_equity_coverage_report(self.save(data), today=DAY)
        self.assertEqual(report["status"], "stale")

    def test_future_report_blocked(self):
        data = fixture()
        data["as_of_utc_date"] = "2026-11-22"
        report = read_equity_coverage_report(self.save(data), today=DAY)
        self.assertEqual(report["status"], "unavailable")

    def test_bad_total_not_served(self):
        data = fixture()
        data["total_candidate_instruments"] = 999
        report = read_equity_coverage_report(self.save(data), today=DAY)
        self.assertEqual(report["status"], "unavailable")

    def test_bool_counts_not_accepted_as_integers(self):
        data = fixture()
        data["markets"]["de"]["candidate_instruments"] = True
        report = read_equity_coverage_report(self.save(data), today=DAY)
        self.assertEqual(report["status"], "unavailable")

    def test_inconsistent_market_counts_not_served(self):
        data = fixture()
        data["markets"]["hk"]["with_any_ohlcv"] = 2
        report = read_equity_coverage_report(self.save(data), today=DAY)
        self.assertEqual(report["status"], "unavailable")

    def test_symlink_not_served(self):
        src = self.save(fixture())
        link = Path(self.tmp.name) / "symbolic.json"
        try:
            link.symlink_to(src)
        except (OSError, NotImplementedError):
            self.skipTest("Filesystem does not support symlinks")
        self.assertEqual(read_equity_coverage_report(str(link), today=DAY)["status"], "unavailable")

    def test_relative_or_missing_path_not_served(self):
        self.assertEqual(read_equity_coverage_report("relative.json", today=DAY)["status"], "unavailable")
        self.assertEqual(
            read_equity_coverage_report(str(self.path), today=DAY)["status"],
            "unavailable",
        )

    def test_not_a_valid_audit_document(self):
        data = fixture()
        data["status"] = "FULLY_VERIFIED"
        self.assertEqual(read_equity_coverage_report(self.save(data), today=DAY)["status"], "unavailable")

    def test_market_list_must_be_exactly_four(self):
        data = fixture()
        data["selected_markets"] = ["us", "hk"]
        self.assertEqual(read_equity_coverage_report(self.save(data), today=DAY)["status"], "unavailable")

    def test_schema_with_missing_market_is_rejected(self):
        data = fixture()
        del data["markets"]["tr"]
        self.assertEqual(read_equity_coverage_report(self.save(data), today=DAY)["status"], "unavailable")


if __name__ == "__main__":
    unittest.main()
