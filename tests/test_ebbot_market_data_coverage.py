"""Deterministic, offline tests for evidence-only market-data coverage auditing."""
from __future__ import annotations

from contextlib import redirect_stdout
from datetime import date
import io
import json
import hashlib
from unittest.mock import patch
from pathlib import Path
import tempfile
import unittest

from scripts.audit_ebbot_market_data_coverage import (
    AuditInputError, audit, parser, run, summary,
)


DAY = date(2026, 11, 21)


def index_row(market: str, symbol: str, kind: str = "stock", active: bool = True) -> list:
    return [symbol, "", "", "", "", "", market, kind, active]


class CoverageAuditTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.idx = self.root / "stocks.json"
        self.write_index([])

    def write_index(self, rows: list) -> None:
        self.idx.write_text(json.dumps(rows), encoding="utf-8")

    def stock_csv(self, text: str, name: str = "stocks.csv") -> Path:
        result = self.root / name
        result.write_text(text, encoding="utf-8")
        return result

    def bars_csv(self, records: list[tuple], name: str = "ohlcv.csv") -> Path:
        result = self.root / name
        body = "market,symbol,session,open,high,low,close,volume,source,currency\n"
        for record in records:
            body += ",".join(map(str, record)) + "\n"
        result.write_text(body, encoding="utf-8")
        return result

    def four_market_stock_file(self) -> Path:
        return self.stock_csv(
            "market,symbol,source,kind,source_as_of_date\n"
            "tr,THYAO.IS,kap_bist_company_directory,stock,2026-11-19\n"
            "us,AAPL,official_source,stock,2026-11-19\n"
            "de,SAP.DE,deutsche_boerse_xetra_t7,stock,2026-11-19\n"
            "hk,0700.HK,hk_exchange,stock,2026-11-19\n"
        )

    def test_reports_every_record_without_fixed_top_n(self):
        self.write_index([index_row("us", f"U{i}") for i in range(301)] + [
            index_row("cn", "600519.SS"), index_row("jp", "7203.T"),
            index_row("us", "^GSPC", "index"), index_row("us", "DEAD", active=False),
        ])
        report = audit(self.idx, as_of=DAY)
        self.assertEqual(report["total_candidate_instruments"], 301)
        self.assertEqual(report["markets"]["us"]["missing_ohlcv_count"], 301)
        self.assertEqual(len(report["markets"]["us"]["missing_symbols"]), 301)
        self.assertEqual(len(summary(report)["markets"]["us"]["missing_symbols"]), 10)
        self.assertEqual(report["inventory_diagnostics"]["out_of_scope_active_rows"], 2)
        self.assertEqual(report["inventory_diagnostics"]["benchmark_index_rows"], 1)
        self.assertEqual(report["inventory_diagnostics"]["inactive_index_rows"], 1)
        self.assertEqual(report["markets_without_inventory"], ["tr", "de", "hk"])
        self.assertFalse(report["full_exchange_listing_coverage_verified"])
        self.assertFalse(report["live_trading_enabled"])

    def test_real_repo_uppercase_market_tags_are_normalized(self):
        # The actual bundled stock index uses uppercase US/HK/CN/JP/BSE tags.
        self.write_index([
            index_row("US", "AAPL"), index_row("HK", "0700.HK"),
            index_row("CN", "600519.SS"), index_row("BSE", "430047.BJ"),
            index_row("US", "^GSPC", "index"),
        ])
        report = audit(self.idx, as_of=DAY)
        self.assertEqual(report["markets"]["us"]["candidate_instruments"], 1)
        self.assertEqual(report["markets"]["hk"]["candidate_instruments"], 1)
        self.assertEqual(report["inventory_diagnostics"]["out_of_scope_active_rows"], 2)
        self.assertEqual(report["inventory_diagnostics"]["benchmark_index_rows"], 1)
        self.assertEqual(report["total_candidate_instruments"], 2)

    def test_two_bars_are_only_review_evidence_not_license_or_broker_proof(self):
        stocks = self.four_market_stock_file()
        records = []
        for market, symbol, currency in (
            ("tr", "THYAO.IS", "TRY"),
            ("us", "AAPL", "USD"),
            ("de", "SAP.DE", "EUR"),
            ("hk", "0700.HK", "HKD"),
        ):
            for session in ("2026-11-19", "2026-11-20"):
                records.append((market, symbol, session, 10, 11, 9, 10, 123,
                                "provider_daily", currency))
        bars = self.bars_csv(records)
        report = audit(self.idx, [stocks], [bars], as_of=DAY, min_bars=2)
        self.assertEqual(report["status"], "REVIEW_ONLY_NEEDS_INDEPENDENT_VALIDATION")
        self.assertEqual(report["total_candidate_instruments"], 4)
        for market in ("tr", "us", "de", "hk"):
            self.assertEqual(report["markets"][market]["with_min_bars"], 1)
            self.assertEqual(report["markets"][market]["with_recent_bar"], 1)
            self.assertEqual(report["markets"][market]["missing_ohlcv_count"], 0)
        self.assertFalse(report["provider_symbol_mapping_verified"])
        self.assertFalse(report["market_data_license_verified"])
        self.assertFalse(report["exchange_session_gap_completeness_verified"])
        self.assertEqual(report["network_requests"], 0)
        self.assertEqual(report["orders"], 0)

    def test_index_only_is_not_a_dated_verified_market_list(self):
        self.write_index([index_row("us", "AAPL"), index_row("us", "SPY", "etf")])
        report = audit(self.idx, as_of=DAY)
        self.assertEqual(report["markets"]["us"]["stocks"], 1)
        self.assertEqual(report["markets"]["us"]["etfs"], 1)
        self.assertEqual(report["markets"]["us"]["undated_inventory_count"], 2)
        self.assertEqual(report["status"], "BLOCKED_INCOMPLETE_EVIDENCE")

    def test_stale_candles_and_insufficient_history_separately(self):
        stocks = self.stock_csv(
            "market,symbol,source,source_as_of_date\n"
            "us,AAPL,verified_list,2026-11-20\n"
        )
        bars = self.bars_csv([
            ("us", "AAPL", "2026-11-01", 10, 11, 9, 10, 5, "demo", "USD"),
        ])
        report = audit(self.idx, [stocks], [bars], as_of=DAY, min_bars=250)
        us = report["markets"]["us"]
        self.assertEqual(us["stale_symbols"], ["AAPL"])
        self.assertEqual(us["insufficient_symbols"], ["AAPL"])
        self.assertEqual(us["missing_ohlcv_count"], 0)

    def test_duplicate_or_wrong_symbol_cannot_silently_be_skipped(self):
        stocks = self.stock_csv("market,symbol,source\nus,AAPL,source\n")
        row = ("us", "AAPL", "2026-11-20", 10, 12, 9, 11, 200, "sample", "USD")
        with self.assertRaisesRegex(AuditInputError, "duplicate_ohlcv_session"):
            audit(self.idx, [stocks], [self.bars_csv([row, row])], as_of=DAY)
        wrong = ("us", "MSFT", "2026-11-20", 10, 12, 9, 11, 200, "sample", "USD")
        with self.assertRaisesRegex(AuditInputError, "ohlcv_symbol_not_in_inventory"):
            audit(self.idx, [stocks], [self.bars_csv([wrong])], as_of=DAY)

    def test_rejects_invalid_prices_and_candles_without_invented_values(self):
        stocks = self.stock_csv("market,symbol,source\nus,AAPL,source\n")
        for opening, high, low, close, volume in [
            ("nan", 12, 9, 11, 123),
            (10, 9, 9, 11, 123),
            (10, 12, 11, 11, 123),
            (10, 12, 9, -1, 123),
            (10, 12, 9, 11, -1),
            (10, "inf", 9, 11, 123),
        ]:
            with self.subTest(opening=opening, high=high, low=low, close=close, volume=volume):
                file = self.bars_csv([
                    ("us", "AAPL", "2026-11-20", opening, high, low,
                     close, volume, "provider", "USD")
                ])
                with self.assertRaises(AuditInputError):
                    audit(self.idx, [stocks], [file], as_of=DAY)

    def test_future_source_and_future_candle_rejected(self):
        future_stocks = self.stock_csv(
            "market,symbol,source,source_as_of_date\n"
            "us,AAPL,source,2026-11-22\n"
        )
        with self.assertRaisesRegex(AuditInputError, "future_inventory_source"):
            audit(self.idx, [future_stocks], as_of=DAY)
        stocks = self.stock_csv("market,symbol,source\nus,AAPL,source\n")
        bar = self.bars_csv([
            ("us", "AAPL", "2026-11-22", 10, 12, 9, 11, 12, "source", "USD")
        ])
        with self.assertRaisesRegex(AuditInputError, "future_ohlcv_session"):
            audit(self.idx, [stocks], [bar], as_of=DAY)

    def test_undated_and_stale_sources_never_count_as_fresh(self):
        stocks = self.stock_csv(
            "market,symbol,source,source_as_of_date\n"
            "us,AAPL,source,2026-11-01\n"
            "us,MSFT,source,\n"
        )
        report = audit(self.idx, [stocks], as_of=DAY, max_age_days=7)
        self.assertEqual(report["inventory_diagnostics"]["stale_inventory_rows"], 1)
        self.assertEqual(report["markets"]["us"]["undated_inventory_count"], 1)

    def test_checksum_pinned_xetra_is_loaded_only_for_bundled_index(self):
        xetra = self.stock_csv(
            "market,symbol,source,kind,source_as_of_date\n"
            "de,SAP.DE,deutsche_boerse_xetra_t7,stock,2026-11-19\n",
            name="xetra.csv",
        )
        digest = hashlib.sha256(xetra.read_bytes()).hexdigest()
        with patch("scripts.audit_ebbot_market_data_coverage.DEFAULT_INDEX", self.idx), \
             patch("scripts.audit_ebbot_market_data_coverage.DEFAULT_XETRA", xetra), \
             patch("scripts.audit_ebbot_market_data_coverage.XETRA_SHA256", digest):
            result = audit(self.idx, as_of=DAY)
        self.assertTrue(result["stored_xetra_manifest_loaded"])
        self.assertEqual(result["markets"]["de"]["candidate_instruments"], 1)
        self.assertEqual(result["stored_xetra_as_of"], "2026-11-19")

    def test_pinned_xetra_rejects_bom_and_crlf_mutations(self):
        xetra = self.stock_csv(
            "market,symbol,source,kind,source_as_of_date\n"
            "de,SAP.DE,deutsche_boerse_xetra_t7,stock,2026-11-19\n",
            name="xetra.csv",
        )
        raw = xetra.read_bytes()
        pinned_digest = hashlib.sha256(raw).hexdigest()
        mutations = (
            bytes.fromhex("efbbbf") + raw,
            raw.replace(bytes([10]), bytes([13, 10])),
        )
        with patch("scripts.audit_ebbot_market_data_coverage.DEFAULT_INDEX", self.idx):
            with patch("scripts.audit_ebbot_market_data_coverage.DEFAULT_XETRA", xetra):
                with patch("scripts.audit_ebbot_market_data_coverage.XETRA_SHA256", pinned_digest):
                    for contents in mutations:
                        with self.subTest(first_bytes=contents[:4]):
                            xetra.write_bytes(contents)
                            with self.assertRaisesRegex(
                                AuditInputError, "stored_xetra_snapshot_checksum_mismatch"
                            ):
                                audit(self.idx, as_of=DAY)

    def test_tampered_xetra_snapshot_blocks_all_instead_of_partial_ingest(self):
        xetra = self.stock_csv(
            "market,symbol,source,kind,source_as_of_date\n"
            "de,SAP.DE,deutsche_boerse_xetra_t7,stock,2026-11-19\n",
            name="xetra.csv",
        )
        with patch("scripts.audit_ebbot_market_data_coverage.DEFAULT_INDEX", self.idx), \
             patch("scripts.audit_ebbot_market_data_coverage.DEFAULT_XETRA", xetra), \
             patch("scripts.audit_ebbot_market_data_coverage.XETRA_SHA256", "0" * 64):
            with self.assertRaisesRegex(AuditInputError, "checksum_mismatch"):
                audit(self.idx, as_of=DAY)

    def test_inconsistent_currency_in_same_symbol_rejected(self):
        stocks = self.stock_csv("market,symbol,source\nus,AAPL,source\n")
        bars = self.bars_csv([
            ("us", "AAPL", "2026-11-19", 10, 12, 9, 11, 100, "source", "USD"),
            ("us", "AAPL", "2026-11-20", 10, 12, 9, 11, 100, "source", "EUR"),
        ])
        with self.assertRaisesRegex(AuditInputError, "conflicting_ohlcv_currencies"):
            audit(self.idx, [stocks], [bars], as_of=DAY)

    def test_unrecognized_manifest_active_flag_rejected(self):
        stocks = self.stock_csv("market,symbol,source,active\nus,AAPL,source,maybe\n")
        with self.assertRaisesRegex(AuditInputError, "invalid_manifest_active_flag"):
            audit(self.idx, [stocks], as_of=DAY)

    def test_source_collisions_in_kind_fail_closed(self):
        self.write_index([index_row("us", "AAPL", "stock")])
        stock = self.stock_csv("market,symbol,source,kind\nus,AAPL,source,etf\n")
        with self.assertRaisesRegex(AuditInputError, "conflicting_instrument_kind"):
            audit(self.idx, [stock], as_of=DAY)

    def test_strict_mode_blocks_even_complete_unverified_evidence(self):
        stock = self.four_market_stock_file()
        args = parser().parse_args([
            "--index", str(self.idx), "--stocks", str(stock),
            "--as-of", DAY.isoformat(), "--min-bars", "1", "--strict",
        ])
        output = io.StringIO()
        with redirect_stdout(output):
            code = run(args)
        self.assertEqual(code, 2)
        self.assertEqual(json.loads(output.getvalue())["status"], "BLOCKED_INCOMPLETE_EVIDENCE")

    def test_full_report_has_every_missing_symbol_without_overwriting(self):
        self.write_index([index_row("us", f"U{i}") for i in range(121)])
        target = self.root / "coverage.json"
        args = parser().parse_args([
            "--index", str(self.idx), "--as-of", DAY.isoformat(),
            "--report-json", str(target),
        ])
        with redirect_stdout(io.StringIO()):
            self.assertEqual(run(args), 0)
        report = json.loads(target.read_text(encoding="utf-8"))
        self.assertEqual(len(report["markets"]["us"]["missing_symbols"]), 121)
        with redirect_stdout(io.StringIO()) as output:
            self.assertEqual(run(args), 1)
        self.assertEqual(json.loads(output.getvalue())["status"], "BLOCKED_INVALID_INPUT")


if __name__ == "__main__":
    unittest.main()
