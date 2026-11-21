"""Offline regression tests for manual vendor export staging; no real market prices."""
from __future__ import annotations

from contextlib import redirect_stdout
from datetime import date
import hashlib
import io
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from scripts.audit_ebbot_market_data_coverage import AuditInputError
from scripts.stage_ebbot_equity_ohlcv import parser, run, stage_vendor_ohlcv


TODAY = date(2026, 11, 21)
HEADER = (
    "market,symbol,session,open,high,low,close,volume,source,currency,"
    "provider,provider_symbol\n"
)


class LocalOhlcvStagingTests(unittest.TestCase):
    def setUp(self) -> None:
        self.folder = TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.root = Path(self.folder.name)
        self.index = self.write("index.json", "[]")
        self.stocks = self.write(
            "stocks.csv",
            "market,symbol,source,kind,source_as_of_date\n"
            "us,AAPL,exchange_list,stock,2026-11-20\n"
            "tr,THYAO.IS,company_list,stock,2026-11-20\n",
        )
        self.mapping = self.write(
            "mapping.csv",
            "market,symbol,provider,provider_symbol,source,source_as_of_date\n"
            "us,AAPL,demo_vendor,AAPL,manual_review,2026-11-20\n"
            "tr,THYAO.IS,tr_vendor,THYAO,manual_review,2026-11-20\n",
        )
        self.calendar = self.write(
            "sessions.csv",
            "market,session,source,source_as_of_date\n"
            "us,2026-11-19,calendar_review,2026-11-20\n"
            "us,2026-11-20,calendar_review,2026-11-20\n"
            "tr,2026-11-20,calendar_review,2026-11-20\n",
        )
        # Deliberately synthetic fixture numbers, NEVER a live pricing source.
        self.data = self.write(
            "vendor.csv", HEADER
            + "us,AAPL,2026-11-20,100,102,99,101,10,licensed_export,USD,demo_vendor,AAPL\n"
            + "us,AAPL,2026-11-19,100,103,99,102,20,licensed_export,USD,demo_vendor,AAPL\n",
        )
        self.manifest_path = self.root / "source-manifest.json"
        self.manifest = {
            "schema_version": 1, "market": "us",
            "provider": "demo_vendor", "source": "licensed_export",
            "currency": "USD", "source_as_of_date": "2026-11-20",
            "input_sha256": "", "license_review_reference": "TICKET-123",
        }
        self.save_manifest()
        self.out = self.root / "staged.csv"

    def write(self, name: str, data: str) -> Path:
        path = self.root / name
        path.write_text(data, encoding="utf-8")
        return path

    def save_manifest(self) -> None:
        self.manifest["input_sha256"] = hashlib.sha256(self.data.read_bytes()).hexdigest()
        self.manifest_path.write_text(json.dumps(self.manifest), encoding="utf-8")

    def call(self, **overrides):
        args = dict(
            index=self.index, stocks=[self.stocks],
            input_csv=self.data, manifest_file=self.manifest_path,
            mapping_file=self.mapping, calendar_file=self.calendar,
            output_csv=self.out, as_of=TODAY,
        )
        args.update(overrides)
        return stage_vendor_ohlcv(**args)

    def test_success_is_not_license_approval_and_is_stable_sorted_csv(self):
        result = self.call()
        self.assertEqual(result["status"], "STAGED_REVIEW_ONLY_NOT_LICENSE_VERIFIED")
        self.assertEqual(result["staged_bar_count"], 2)
        self.assertEqual(result["staged_symbol_count"], 1)
        self.assertEqual(result["market"], "us")
        self.assertFalse(result["license_verified"])
        self.assertFalse(result["provider_mapping_independently_verified"])
        self.assertEqual(result["network_requests"], 0)
        self.assertEqual(result["orders"], 0)
        self.assertFalse(result["paper_trading_enabled"])
        self.assertFalse(result["live_trading_enabled"])
        rows = self.out.read_text(encoding="utf-8").splitlines()
        self.assertEqual(rows[0], HEADER.strip())
        self.assertIn("2026-11-19", rows[1])
        self.assertIn("2026-11-20", rows[2])
        self.assertEqual(
            result["staged_sha256"],
            hashlib.sha256(self.out.read_bytes()).hexdigest(),
        )

    def test_no_license_reference_is_rejected(self):
        self.manifest["license_review_reference"] = ""
        self.save_manifest()
        with self.assertRaisesRegex(AuditInputError, "provenance"):
            self.call()
        self.assertFalse(self.out.exists())

    def test_checksum_mismatch_rejected(self):
        self.data.write_text(HEADER + "us,AAPL,2026-11-20,100,102,99,101,100,licensed_export,USD,demo_vendor,AAPL\n", encoding="utf-8")
        with self.assertRaisesRegex(AuditInputError, "checksum_mismatch"):
            self.call()
        self.assertFalse(self.out.exists())

    def test_provider_name_mismatch_rejected(self):
        text = self.data.read_text(encoding="utf-8").replace("demo_vendor", "other_vendor")
        self.data.write_text(text, encoding="utf-8")
        self.save_manifest()
        with self.assertRaisesRegex(AuditInputError, "provenance_mismatch"):
            self.call()

    def test_provider_symbol_mismatch_rejected(self):
        text = self.data.read_text(encoding="utf-8").replace(",demo_vendor,AAPL", ",demo_vendor,AAAX")
        self.data.write_text(text, encoding="utf-8")
        self.save_manifest()
        with self.assertRaisesRegex(AuditInputError, "ticker_identity_mismatch"):
            self.call()

    def test_cross_market_vendor_shard_blocked(self):
        text = self.data.read_text(encoding="utf-8").replace(
            "us,AAPL,2026-11-20", "tr,THYAO.IS,2026-11-20", 1
        )
        self.data.write_text(text, encoding="utf-8")
        self.save_manifest()
        with self.assertRaisesRegex(AuditInputError, "cross_market_provider_export"):
            self.call()

    def test_unknown_exchange_calendar_day_blocked(self):
        text = self.data.read_text(encoding="utf-8").replace("2026-11-19", "2026-11-18")
        self.data.write_text(text, encoding="utf-8")
        self.save_manifest()
        with self.assertRaisesRegex(AuditInputError, "session_not_in_supplied_calendar"):
            self.call()

    def test_future_bar_beyond_source_timestamp_blocked(self):
        self.calendar.write_text(
            self.calendar.read_text(encoding="utf-8")
            + "us,2026-11-21,calendar_review,2026-11-21\n", encoding="utf-8"
        )
        text = self.data.read_text(encoding="utf-8").replace("2026-11-20", "2026-11-21")
        self.data.write_text(text, encoding="utf-8")
        self.save_manifest()
        with self.assertRaisesRegex(AuditInputError, "session_after_source_export"):
            self.call()

    def test_invalid_ohlcv_math_is_rejected(self):
        text = self.data.read_text(encoding="utf-8").replace(",100,102,99,101,", ",100,99,99,101,")
        self.data.write_text(text, encoding="utf-8")
        self.save_manifest()
        with self.assertRaisesRegex(AuditInputError, "inconsistent_ohlcv_candle"):
            self.call()

    def test_future_manifest_export_is_rejected(self):
        self.manifest["source_as_of_date"] = "2026-11-22"
        self.save_manifest()
        with self.assertRaisesRegex(AuditInputError, "future_provider_export"):
            self.call()

    def test_missing_mapping_and_calendar_block_instead_of_assuming(self):
        self.mapping.write_text(
            "market,symbol,provider,provider_symbol,source,source_as_of_date\n"
            "tr,THYAO.IS,tr_vendor,THYAO,manual_review,2026-11-20\n",
            encoding="utf-8",
        )
        with self.assertRaisesRegex(AuditInputError, "missing_explicit_provider_symbol_mapping"):
            self.call()
        self.mapping.write_text(
            "market,symbol,provider,provider_symbol,source,source_as_of_date\n"
            "us,AAPL,demo_vendor,AAPL,manual_review,2026-11-20\n",
            encoding="utf-8",
        )
        self.calendar.write_text(
            "market,session,source,source_as_of_date\ntr,2026-11-20,review,2026-11-20\n",
            encoding="utf-8",
        )
        with self.assertRaisesRegex(AuditInputError, "missing_declared_provider_market_sessions"):
            self.call()

    def test_output_is_exclusive_and_never_overwrites(self):
        self.out.write_text("existing private evidence", encoding="utf-8")
        with self.assertRaises(FileExistsError):
            self.call()
        self.assertEqual(self.out.read_text(encoding="utf-8"), "existing private evidence")

    def test_csv_duplicate_stock_session_is_rejected(self):
        text = self.data.read_text(encoding="utf-8")
        text += "us,AAPL,2026-11-20,100,102,99,101,10,licensed_export,USD,demo_vendor,AAPL\n"
        self.data.write_text(text, encoding="utf-8")
        self.save_manifest()
        with self.assertRaisesRegex(AuditInputError, "duplicate_ohlcv_session"):
            self.call()

    def test_invalid_currency_and_untrusted_market_code_rejected(self):
        self.manifest["currency"] = "USD,FORMULA"
        self.save_manifest()
        with self.assertRaisesRegex(AuditInputError, "invalid_provider_currency"):
            self.call()
        self.manifest["currency"] = "USD"
        self.manifest["market"] = "cn"
        self.save_manifest()
        with self.assertRaisesRegex(AuditInputError, "unsupported_provider_market"):
            self.call()

    def test_no_top_n_shard_limit(self):
        rows = []
        markets = []
        mappings = []
        for i in range(121):
            symbol = f"U{i}"
            markets.append(f"us,{symbol},exchange_list,stock,2026-11-20\n")
            mappings.append(f"us,{symbol},demo_vendor,{symbol},manual_review,2026-11-20\n")
            rows.append(f"us,{symbol},2026-11-20,100,102,99,101,10,licensed_export,USD,demo_vendor,{symbol}\n")
        self.stocks.write_text(
            "market,symbol,source,kind,source_as_of_date\n" + "".join(markets),
            encoding="utf-8",
        )
        self.mapping.write_text(
            "market,symbol,provider,provider_symbol,source,source_as_of_date\n" + "".join(mappings),
            encoding="utf-8",
        )
        self.data.write_text(HEADER + "".join(reversed(rows)), encoding="utf-8")
        self.save_manifest()
        report = self.call()
        self.assertEqual(report["staged_bar_count"], 121)
        self.assertEqual(report["staged_symbol_count"], 121)

    def test_cli_invalid_manifest_fails_without_paths_or_prices_in_error(self):
        self.manifest["schema_version"] = 3
        self.save_manifest()
        args = parser().parse_args([
            "--index", str(self.index), "--stocks", str(self.stocks),
            "--input-csv", str(self.data), "--manifest", str(self.manifest_path),
            "--mapping", str(self.mapping), "--calendar", str(self.calendar),
            "--output-csv", str(self.out), "--as-of", TODAY.isoformat(),
        ])
        stdout = io.StringIO()
        with redirect_stdout(stdout):
            status = run(args)
        self.assertEqual(status, 1)
        result = json.loads(stdout.getvalue())
        self.assertEqual(result["status"], "BLOCKED_INVALID_VENDOR_INPUT")
        self.assertFalse(self.out.exists())
        self.assertNotIn(str(self.root), stdout.getvalue())


if __name__ == "__main__":
    unittest.main()
