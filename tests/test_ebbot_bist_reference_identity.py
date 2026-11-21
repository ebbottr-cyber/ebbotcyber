"""Offline BIST issuer-vs-traded-security reconciliation regressions.

All input fixtures are synthetically assembled. No scraped exchange data,
confidential quotes, provider contracts, API keys or trading operations.
"""
from __future__ import annotations

from contextlib import redirect_stdout
from datetime import date
import io
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from scripts.audit_ebbot_market_data_coverage import AuditInputError
from scripts.audit_ebbot_bist_reference_identity import (
    compact, isin_check_digit_valid, parser, reconcile_bist, run,
)

NOW = date(2026, 11, 21)


def valid_isin(index: int) -> str:
    # Synthetic test-only ISIN with valid ISO 6166/Luhn check digit.
    base = f"TR{index:09d}"
    return next(base + str(k) for k in range(10) if isin_check_digit_valid(base + str(k)))


class BistIdentityTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.kap = self.root / "kap.csv"
        self.exchange = self.root / "exchange.csv"
        self.mapping = self.root / "provider.csv"
        self.bars = self.root / "bars.csv"
        self.out = self.root / "audit.json"
        self.write_kap([
            ("THYAO.IS", "2026-11-20T15:00:00+00:00"),
            ("AKBNK.IS", "2026-11-20T15:00:00+00:00"),
            ("EXTRA.IS", "2026-11-20T15:00:00+00:00"),
        ])
        self.write_exchange([
            ("THYAO.IS", valid_isin(1), "active", "2026-11-20"),
            ("AKBNK.IS", valid_isin(2), "halted", "2026-11-20"),
            ("NEWCO.IS", valid_isin(3), "active", "2026-11-20"),
        ])
        self.mapping.write_text(
            "market,symbol,provider,provider_symbol,source,source_as_of_date\n"
            "tr,THYAO.IS,demo_vendor,THYAO,operator_entry,2026-11-20\n",
            encoding="utf-8",
        )
        self.bars.write_text(
            "market,symbol,session,open,high,low,close,volume,source,currency\n"
            "tr,THYAO.IS,2026-11-20,10,11,9,10,100,fixture_not_real,TRY\n",
            encoding="utf-8",
        )

    def write_kap(self, records):
        self.kap.write_text(
            "market,symbol,source,kind,observed_at_utc\n"
            + "".join(
                f"tr,{symbol},kap_bist_company_directory,stock,{stamp}\n"
                for symbol, stamp in records
            ),
            encoding="utf-8",
        )

    def write_exchange(self, records):
        self.exchange.write_text(
            "market,symbol,isin,mic,listing_status,source,source_as_of_date\n"
            + "".join(
                f"tr,{symbol},{isin},XIST,{status},operator_bist_reference,{when}\n"
                for symbol, isin, status, when in records
            ),
            encoding="utf-8",
        )

    def audit(self, **kwargs):
        args = {"kap": self.kap, "exchange": self.exchange, "as_of": NOW}
        args.update(kwargs)
        return reconcile_bist(**args)

    def test_no_files_reports_unknown_not_zero(self):
        report = reconcile_bist(as_of=NOW)
        self.assertEqual(report["status"], "BLOCKED_MISSING_BIST_SOURCE_FILES")
        self.assertIsNone(report["kap_candidate_count"])
        self.assertIsNone(report["exchange_active_count"])
        self.assertTrue(report["counts_unknown_not_zero"])
        self.assertFalse(report["live_trading_enabled"])
        self.assertEqual(report["network_requests"], 0)
        self.assertEqual(report["orders"], 0)

    def test_kap_directory_not_equivalent_to_active_bist_listing(self):
        report = self.audit()
        self.assertEqual(report["kap_candidate_count"], 3)
        self.assertEqual(report["exchange_reference_count"], 3)
        self.assertEqual(report["exchange_active_count"], 2)
        self.assertEqual(report["exchange_halted_or_delisted_count"], 1)
        self.assertEqual(report["matched_kap_exchange_count"], 2)
        self.assertEqual(report["matched_active_kap_exchange_count"], 1)
        self.assertEqual(report["kap_not_in_exchange_count"], 1)
        self.assertEqual(report["exchange_not_in_kap_count"], 1)
        self.assertEqual(report["active_without_declared_provider_mapping_count"], 2)
        self.assertIsNone(report["active_with_ohlcv_in_supplied_file_count"])
        self.assertIsNone(report["candidate_symbol_details"]["active_without_input_ohlcv"])
        self.assertEqual(report["candidate_symbol_details"]["kap_only"], ["EXTRA.IS"])
        self.assertEqual(report["candidate_symbol_details"]["exchange_only"], ["NEWCO.IS"])
        self.assertEqual(report["candidate_symbol_details"]["halted_or_delisted"], ["AKBNK.IS"])

    def test_attached_mapping_and_ohlcv_evidence_report_only_supplied_rows(self):
        report = self.audit(provider_mapping=self.mapping, bars=self.bars)
        self.assertEqual(report["active_without_declared_provider_mapping_count"], 1)
        self.assertEqual(report["active_with_ohlcv_in_supplied_file_count"], 1)
        self.assertEqual(report["active_without_ohlcv_in_supplied_file_count"], 1)
        self.assertEqual(report["candidate_symbol_details"]["active_without_input_ohlcv"], ["NEWCO.IS"])
        self.assertFalse(report["isin_to_security_identity_verified"])
        self.assertFalse(report["price_provider_license_verified"])
        self.assertFalse(report["live_ohlcv_loaded"])
        self.assertFalse(report["paper_trading_enabled"])
        self.assertFalse(report["live_trading_enabled"])

    def test_perfect_claimed_rows_remain_review_only_and_not_exchange_verified(self):
        self.write_kap([("THYAO.IS", "2026-11-20T10:00:00Z")])
        self.write_exchange([("THYAO.IS", valid_isin(1), "active", "2026-11-20")])
        self.bars.write_text(
            "market,symbol,session,open,high,low,close,volume,source,currency,provider,provider_symbol\n"
            "tr,THYAO.IS,2026-11-20,10,11,9,10,100,fixture_not_real,TRY,demo_vendor,THYAO\n",
            encoding="utf-8",
        )
        report = self.audit(provider_mapping=self.mapping, bars=self.bars)
        self.assertEqual(report["status"], "REVIEW_ONLY_NEEDS_INDEPENDENT_BIST_CONFIRMATION")
        self.assertFalse(report["independent_listing_authentication_verified"])
        self.assertFalse(report["provider_symbol_mapping_independently_verified"])
        self.assertFalse(report["price_provider_license_verified"])

    def test_provider_mismatch_in_ohlcv_is_blocked(self):
        self.bars.write_text(
            "market,symbol,session,open,high,low,close,volume,source,currency,provider,provider_symbol\n"
            "tr,THYAO.IS,2026-11-20,10,11,9,10,100,fixture_not_real,TRY,demo_vendor,WRONG\n",
            encoding="utf-8",
        )
        with self.assertRaisesRegex(AuditInputError, "bar_provider_symbol_mapping_mismatch"):
            self.audit(provider_mapping=self.mapping, bars=self.bars)

    def test_unattributed_ohlcv_remains_blocked_even_when_symbol_has_a_map(self):
        self.write_kap([("THYAO.IS", "2026-11-20T10:00:00Z")])
        self.write_exchange([("THYAO.IS", valid_isin(1), "active", "2026-11-20")])
        report = self.audit(provider_mapping=self.mapping, bars=self.bars)
        self.assertEqual(report["ohlcv_bar_identity_diagnostics"]["bar_rows_without_identity_evidence"], 1)
        self.assertEqual(report["status"], "BLOCKED_STALE_OR_INCOMPLETE_BIST_REFERENCES")

    def test_isin_validity_is_only_a_check_digit(self):
        self.assertTrue(isin_check_digit_valid(valid_isin(1)))
        self.assertFalse(isin_check_digit_valid(valid_isin(1)[:-1] + "X"))
        self.assertFalse(isin_check_digit_valid("TR0000000010" if valid_isin(1) != "TR0000000010" else "TR0000000011"))

    def test_reject_invalid_or_repeated_isin(self):
        self.write_exchange([("THYAO.IS", "TR0000000000", "active", "2026-11-20")])
        if isin_check_digit_valid("TR0000000000"):
            self.write_exchange([("THYAO.IS", "TR000000000X", "active", "2026-11-20")])
        with self.assertRaisesRegex(AuditInputError, "invalid_bist_reference_isin"):
            self.audit()
        self.write_exchange([
            ("THYAO.IS", valid_isin(1), "active", "2026-11-20"),
            ("AKBNK.IS", valid_isin(1), "active", "2026-11-20"),
        ])
        with self.assertRaisesRegex(AuditInputError, "duplicate_exchange_isin"):
            self.audit()

    def test_reject_wrong_mic_even_with_correct_isin(self):
        text = self.exchange.read_text(encoding="utf-8").replace(",XIST,", ",XNAS,")
        self.exchange.write_text(text, encoding="utf-8")
        with self.assertRaisesRegex(AuditInputError, "wrong_bist_exchange_mic"):
            self.audit()

    def test_reject_listing_status_without_explicit_active_or_halted(self):
        self.exchange.write_text(
            self.exchange.read_text(encoding="utf-8").replace(",halted,", ",unknown,"),
            encoding="utf-8",
        )
        with self.assertRaisesRegex(AuditInputError, "invalid_bist_listing_status"):
            self.audit()

    def test_duplicate_kap_and_exchange_symbols_are_rejected(self):
        line = self.kap.read_text(encoding="utf-8").splitlines()[1]
        with self.kap.open("a", encoding="utf-8") as handle:
            handle.write(line + "\n")
        with self.assertRaisesRegex(AuditInputError, "duplicate_kap_equity_code"):
            self.audit()
        self.write_kap([("THYAO.IS", "2026-11-20T10:00:00Z")])
        line = self.exchange.read_text(encoding="utf-8").splitlines()[1]
        with self.exchange.open("a", encoding="utf-8") as handle:
            handle.write(line + "\n")
        with self.assertRaisesRegex(AuditInputError, "duplicate_exchange_symbol"):
            self.audit()

    def test_stale_files_detected_and_not_approved(self):
        self.write_kap([("THYAO.IS", "2026-11-01T10:00:00Z")])
        self.write_exchange([("THYAO.IS", valid_isin(1), "active", "2026-11-01")])
        report = self.audit()
        self.assertEqual(report["stale_kap_reference_rows"], 1)
        self.assertEqual(report["stale_exchange_reference_rows"], 1)
        self.assertEqual(report["status"], "BLOCKED_STALE_OR_INCOMPLETE_BIST_REFERENCES")

    def test_stale_mapping_is_never_success(self):
        self.mapping.write_text(
            self.mapping.read_text(encoding="utf-8").replace("2026-11-20", "2026-10-20"),
            encoding="utf-8",
        )
        report = self.audit(provider_mapping=self.mapping, bars=self.bars)
        self.assertEqual(report["stale_provider_mapping_rows"], 1)
        self.assertEqual(report["status"], "BLOCKED_STALE_OR_INCOMPLETE_BIST_REFERENCES")

    def test_future_snapshot_and_naive_observation_rejected(self):
        self.write_kap([("THYAO.IS", "2026-11-22T00:00:00Z")])
        with self.assertRaisesRegex(AuditInputError, "future_bist_reference"):
            self.audit()
        self.write_kap([("THYAO.IS", "2026-11-20T10:00:00")])
        with self.assertRaisesRegex(AuditInputError, "kap_timestamp_missing_timezone"):
            self.audit()

    def test_kap_old_observed_at_utc_is_compatible_with_collector(self):
        self.write_kap([("THYAO.IS", "2026-11-18T12:45:00+00:00")])
        result = self.audit()
        self.assertEqual(result["kap_candidate_count"], 1)
        self.assertEqual(result["stale_kap_reference_rows"], 0)

    def test_missing_source_date_rejected_without_freshness_guess(self):
        self.write_kap([("THYAO.IS", "")])
        with self.assertRaisesRegex(AuditInputError, "undated_bist_reference_row"):
            self.audit()

    def test_nontr_or_bad_equity_symbol_fails_closed(self):
        self.write_kap([("7203.T", "2026-11-20T10:00:00Z")])
        with self.assertRaisesRegex(AuditInputError, "invalid_bist_equity_symbol"):
            self.audit()

    def test_bad_ohlcv_is_rejected_before_counted(self):
        self.bars.write_text(
            self.bars.read_text(encoding="utf-8").replace(",10,11,9,10,", ",10,8,9,10,"),
            encoding="utf-8",
        )
        with self.assertRaisesRegex(AuditInputError, "inconsistent_ohlcv_candle"):
            self.audit(bars=self.bars)

    def test_zero_price_input_absent_does_not_mean_no_market_prices(self):
        report = self.audit(bars=None)
        self.assertFalse(report["ohlcv_file_supplied"])
        self.assertIsNone(report["active_with_ohlcv_in_supplied_file_count"])
        self.assertFalse(report["live_ohlcv_loaded"])

    def test_200_symbols_no_fixed_top100_cap_and_bounded_stdout(self):
        kap_records = []
        exchange_records = []
        for index in range(200):
            symbol = f"A{index:03d}.IS"
            kap_records.append((symbol, "2026-11-20T10:00:00Z"))
            exchange_records.append((symbol, valid_isin(index), "active", "2026-11-20"))
        self.write_kap(kap_records)
        self.write_exchange(exchange_records)
        report = self.audit()
        self.assertEqual(report["kap_candidate_count"], 200)
        self.assertEqual(report["exchange_active_count"], 200)
        self.assertEqual(report["active_without_declared_provider_mapping_count"], 200)
        self.assertEqual(len(report["candidate_symbol_details"]["active_without_provider_mapping"]), 200)
        short = compact(report)
        self.assertEqual(len(short["candidate_symbol_details"]["active_without_provider_mapping"]), 10)

    def test_cli_writes_new_private_full_report_never_overwrite(self):
        args = parser().parse_args([
            "--kap", str(self.kap), "--exchange", str(self.exchange),
            "--report-json", str(self.out), "--as-of", NOW.isoformat(),
        ])
        with redirect_stdout(io.StringIO()) as stdout:
            code = run(args)
        self.assertEqual(code, 0)
        self.assertIn("BLOCKED_STALE_OR_INCOMPLETE", stdout.getvalue())
        report = json.loads(self.out.read_text(encoding="utf-8"))
        self.assertEqual(report["kap_candidate_count"], 3)
        self.assertEqual(report["candidate_symbol_details"]["kap_only"], ["EXTRA.IS"])
        with redirect_stdout(io.StringIO()) as stdout:
            self.assertEqual(run(args), 1)
        self.assertIn("BLOCKED_INVALID_BIST_REFERENCE", stdout.getvalue())
        self.assertNotIn(str(self.root), stdout.getvalue())

    def test_cli_without_inputs_is_safe_unknown(self):
        args = parser().parse_args(["--as-of", NOW.isoformat()])
        with redirect_stdout(io.StringIO()) as stdout:
            self.assertEqual(run(args), 0)
        result = json.loads(stdout.getvalue())
        self.assertTrue(result["counts_unknown_not_zero"])
        self.assertIsNone(result["exchange_active_count"])
        self.assertFalse(result["live_trading_enabled"])


if __name__ == "__main__":
    unittest.main()
