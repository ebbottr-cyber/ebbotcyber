"""Private BIST identity report reader: no fabricated counts or raw symbol leakage."""
from __future__ import annotations

from datetime import date
import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from src.services.bist_identity_report_reader import (
    read_bist_identity_summary, unavailable_bist_identity_report,
)

DAY = date(2026, 11, 21)


def fixture() -> dict:
    return {
        "status": "BLOCKED_STALE_OR_INCOMPLETE_BIST_REFERENCES",
        "as_of_utc_date": "2026-11-21",
        "kap_candidate_count": 3,
        "exchange_reference_count": 3,
        "exchange_active_count": 2,
        "exchange_halted_or_delisted_count": 1,
        "matched_kap_exchange_count": 2,
        "matched_active_kap_exchange_count": 1,
        "kap_not_in_exchange_count": 1,
        "exchange_not_in_kap_count": 1,
        "active_without_declared_provider_mapping_count": 1,
        "active_with_ohlcv_in_supplied_file_count": 1,
        "active_without_ohlcv_in_supplied_file_count": 1,
        "stale_kap_reference_rows": 0,
        "stale_exchange_reference_rows": 0,
        "stale_provider_mapping_rows": 0,
        "provider_mapping_file_supplied": True,
        "ohlcv_file_supplied": True,
        "candidate_symbol_details": {
            "kap_only": ["PRIVATE_KAP_IS"],
            "exchange_only": ["PRIVATE_BIST_IS"],
            "halted_or_delisted": ["PRIVATE_HALTED_IS"],
            "active_without_provider_mapping": ["PRIVATE_UNMAPPED_IS"],
            "active_without_input_ohlcv": ["PRIVATE_NO_OHLCV_IS"],
        },
        "counts_are_input_reconciliation_only": True,
        "independent_listing_authentication_verified": False,
        "isin_to_security_identity_verified": False,
        "price_provider_license_verified": False,
        "provider_symbol_mapping_independently_verified": False,
        "live_ohlcv_loaded": False,
        "paper_trading_enabled": False,
        "live_trading_enabled": False,
        "network_requests": 0,
        "orders": 0,
    }


class BistIdentityReaderTests(unittest.TestCase):
    def setUp(self):
        tmp = TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.path = self.root / "bist-reconciliation.json"

    def save(self, data: dict) -> str:
        self.path.write_text(json.dumps(data), encoding="utf-8")
        return str(self.path)

    def test_unconfigured_report_yields_unknown_not_zero(self):
        with patch.dict(os.environ, {"EBBOT_BIST_IDENTITY_REPORT_PATH": ""}):
            result = read_bist_identity_summary(today=DAY)
        self.assertEqual(result["status"], "unavailable")
        self.assertIsNone(result["counts"])
        self.assertFalse(result["licensed_prices_verified"])

    def test_valid_reconciliation_shows_only_aggregate_counts_not_symbols_or_isins(self):
        result = read_bist_identity_summary(self.save(fixture()), today=DAY)
        self.assertEqual(result["status"], "unverified")
        self.assertEqual(result["counts"]["exchange_active_count"], 2)
        self.assertEqual(result["counts"]["kap_not_in_exchange_count"], 1)
        self.assertEqual(result["counts"]["active_with_ohlcv_in_supplied_file_count"], 1)
        self.assertTrue(result["prices_file_supplied"])
        self.assertNotIn("PRIVATE_", json.dumps(result))
        self.assertNotIn("candidate_symbol_details", json.dumps(result))
        self.assertNotIn(str(self.root), json.dumps(result))
        self.assertFalse(result["independent_listing_verified"])
        self.assertFalse(result["licensed_prices_verified"])
        self.assertFalse(result["live_trading_enabled"])

    def test_missing_bist_sources_report_yields_unknown(self):
        data = fixture()
        data["status"] = "BLOCKED_MISSING_BIST_SOURCE_FILES"
        data["kap_candidate_count"] = None
        response = read_bist_identity_summary(self.save(data), today=DAY)
        self.assertEqual(response["status"], "unavailable")
        self.assertEqual(response["reason"], "bist_reference_files_missing")
        self.assertIsNone(response["counts"])

    def test_missing_price_file_yields_null_price_counts(self):
        data = fixture()
        data["ohlcv_file_supplied"] = False
        data["active_with_ohlcv_in_supplied_file_count"] = None
        data["active_without_ohlcv_in_supplied_file_count"] = None
        data["candidate_symbol_details"]["active_without_input_ohlcv"] = None
        response = read_bist_identity_summary(self.save(data), today=DAY)
        self.assertEqual(response["status"], "unverified")
        self.assertIsNone(response["counts"]["active_with_ohlcv_in_supplied_file_count"])
        self.assertIsNone(response["counts"]["active_without_ohlcv_in_supplied_file_count"])
        self.assertFalse(response["prices_file_supplied"])

    def test_old_report_is_marked_stale(self):
        data = fixture()
        data["as_of_utc_date"] = "2026-11-01"
        response = read_bist_identity_summary(self.save(data), today=DAY)
        self.assertEqual(response["status"], "stale")

    def test_stale_reference_rows_are_marked_stale(self):
        data = fixture()
        data["stale_kap_reference_rows"] = 1
        response = read_bist_identity_summary(self.save(data), today=DAY)
        self.assertEqual(response["status"], "stale")

    def test_future_report_is_rejected(self):
        data = fixture()
        data["as_of_utc_date"] = "2026-11-22"
        response = read_bist_identity_summary(self.save(data), today=DAY)
        self.assertEqual(response["status"], "unavailable")
        self.assertIsNone(response["counts"])

    def test_forged_verified_status_is_rejected(self):
        data = fixture()
        data["status"] = "FULLY_VERIFIED"
        response = read_bist_identity_summary(self.save(data), today=DAY)
        self.assertEqual(response["status"], "unavailable")

    def test_forged_license_true_is_rejected(self):
        data = fixture()
        data["price_provider_license_verified"] = True
        response = read_bist_identity_summary(self.save(data), today=DAY)
        self.assertEqual(response["status"], "unavailable")

    def test_bool_or_negative_counts_rejected(self):
        data = fixture()
        data["exchange_active_count"] = True
        self.assertEqual(read_bist_identity_summary(self.save(data), today=DAY)["status"], "unavailable")
        data["exchange_active_count"] = -1
        self.assertEqual(read_bist_identity_summary(self.save(data), today=DAY)["status"], "unavailable")

    def test_inconsistent_kap_exchange_count_is_rejected(self):
        data = fixture()
        data["matched_kap_exchange_count"] = 999
        self.assertEqual(read_bist_identity_summary(self.save(data), today=DAY)["status"], "unavailable")

    def test_inconsistent_price_counts_rejected(self):
        data = fixture()
        data["active_with_ohlcv_in_supplied_file_count"] = 2
        self.assertEqual(read_bist_identity_summary(self.save(data), today=DAY)["status"], "unavailable")

    def test_incomplete_private_detail_lists_rejected_without_exposure(self):
        data = fixture()
        data["candidate_symbol_details"]["kap_only"] = []
        self.assertEqual(read_bist_identity_summary(self.save(data), today=DAY)["status"], "unavailable")

    def test_missing_path_relative_and_symlink_rejected(self):
        self.assertEqual(read_bist_identity_summary(str(self.path), today=DAY)["status"], "unavailable")
        self.assertEqual(read_bist_identity_summary("relative.json", today=DAY)["status"], "unavailable")
        self.save(fixture())
        link = self.root / "link.json"
        try:
            link.symlink_to(self.path)
        except (OSError, NotImplementedError):
            self.skipTest("Symlink unavailable")
        self.assertEqual(read_bist_identity_summary(str(link), today=DAY)["status"], "unavailable")

    def test_no_mapping_file_requires_every_active_symbol_to_be_unmapped(self):
        data = fixture()
        data["provider_mapping_file_supplied"] = False
        self.assertEqual(read_bist_identity_summary(self.save(data), today=DAY)["status"], "unavailable")

    def test_backend_attested_network_action_is_rejected(self):
        data = fixture()
        data["orders"] = 1
        self.assertEqual(read_bist_identity_summary(self.save(data), today=DAY)["status"], "unavailable")

    def test_blank_report_path_and_unrecognized_reason_not_abusable(self):
        with self.assertRaisesRegex(ValueError, "unapproved_unavailable_reason"):
            unavailable_bist_identity_report("all_verified")
        with patch.dict(os.environ, {"EBBOT_BIST_IDENTITY_REPORT_PATH": ""}):
            self.assertIsNone(read_bist_identity_summary(today=DAY)["counts"])


if __name__ == "__main__":
    unittest.main()
