"""Windows-compatible end-to-end OFFLINE market-data evidence pipeline.

Synthetic test data only. Tests invoke the *actual* entrypoints with subprocesses,
then validate output with the same local readers consumed by Data Center.
No exchange/broker network, subscription, license, application database, live
market data, order, paper fill, or packaged installer is involved.

Using synthetic session dates does not claim these are genuine BIST open days.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
import unittest

from scripts.audit_ebbot_bist_reference_identity import isin_check_digit_valid
from src.services.bist_identity_report_reader import read_bist_identity_summary
from src.services.equity_data_coverage_reader import read_equity_coverage_report

ROOT = Path(__file__).resolve().parents[1]
CSV_HEADER = (
    "market,symbol,session,open,high,low,close,volume,source,currency,"
    "provider,provider_symbol\n"
)


def synthetic_isin(number: int) -> str:
    base = f"TR{number:09d}"
    return next(base + str(digit) for digit in range(10)
                if isin_check_digit_valid(base + str(digit)))


class WindowsEquityOfflineFlowTests(unittest.TestCase):
    def setUp(self) -> None:
        directory = TemporaryDirectory(prefix="ebbot-offline-")
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name)
        self.today = datetime.now(timezone.utc).date()
        # Synthetic dates. This is NOT a holiday, IPO or session calendar claim.
        self.bar_day = self.today - timedelta(days=1)
        self.day = self.today.isoformat()
        self.bar = self.bar_day.isoformat()

        self.index = self.save("stock-index.json", json.dumps([
            ["AAPL", "", "", "", "", "", "US", "stock", True],
            ["SAP.DE", "", "", "", "", "", "DE", "stock", True],
            ["0700.HK", "", "", "", "", "", "HK", "stock", True],
        ]))
        self.kap = self.save(
            "kap-actual-shape-synthetic.csv",
            "market,symbol,source,kind,observed_at_utc\n"
            + "".join(
                f"tr,{sym},synthetic_kap_fixture,stock,{self.day}T08:00:00Z\n"
                for sym in ("THYAO.IS", "AKBNK.IS", "EXTRA.IS")
            ),
        )
        self.exchange = self.save(
            "xist-synthetic.csv",
            "market,symbol,isin,mic,listing_status,source,source_as_of_date\n"
            + f"tr,THYAO.IS,{synthetic_isin(1)},XIST,active,synthetic_bist_fixture,{self.day}\n"
            + f"tr,AKBNK.IS,{synthetic_isin(2)},XIST,halted,synthetic_bist_fixture,{self.day}\n"
            + f"tr,NEWCO.IS,{synthetic_isin(3)},XIST,active,synthetic_bist_fixture,{self.day}\n",
        )
        self.mapping = self.save(
            "provider-mapping.csv",
            "market,symbol,provider,provider_symbol,source,source_as_of_date\n"
            + f"tr,THYAO.IS,fixture_vendor,THYAO,synthetic_mapping,{self.day}\n",
        )
        self.calendar = self.save(
            "synthetic-calendar.csv",
            "market,session,source,source_as_of_date\n"
            + f"tr,{self.bar},synthetic_declared_session,{self.day}\n",
        )
        self.csv = self.save(
            "vendor-export.csv",
            CSV_HEADER
            + f"tr,THYAO.IS,{self.bar},10,11,9,10.5,1000,fixture_export,TRY,fixture_vendor,THYAO\n",
        )
        self.manifest = self.root / "vendor-manifest.json"
        self.write_manifest()
        self.staged = self.root / "validated-staged.csv"
        self.coverage = self.root / "four-market-review.json"
        self.bist = self.root / "bist-identity-review.json"

    def save(self, name: str, value: str) -> Path:
        path = self.root / name
        path.write_text(value, encoding="utf-8")
        return path

    def write_manifest(self) -> None:
        self.manifest.write_text(json.dumps({
            "schema_version": 1,
            "market": "tr",
            "provider": "fixture_vendor",
            "source": "fixture_export",
            "currency": "TRY",
            "source_as_of_date": self.day,
            "input_sha256": hashlib.sha256(self.csv.read_bytes()).hexdigest(),
            "license_review_reference": "SYNTHETIC-NOT-A-LICENSE",
        }), encoding="utf-8")

    def cli(self, module: str, *arguments: object, expected: int = 0) -> dict:
        env = os.environ.copy()
        env.update({
            "SCHEDULE_ENABLED": "false",
            "RUNTIME_SCHEDULER_SUPPRESS_START": "true",
            "MEME_RADAR_LIVE_ENABLED": "false",
            "MEME_COIN_DISCOVERY_ENABLED": "false",
        })
        process = subprocess.run(
            [sys.executable, "-m", module, *map(str, arguments)],
            cwd=ROOT,
            env=env,
            encoding="utf-8",
            errors="replace",
            capture_output=True,
            check=False,
            timeout=45,
        )
        self.assertEqual(process.returncode, expected,
                         f"{module}: {process.stdout[-700:]} {process.stderr[-700:]}")
        self.assertNotIn("Traceback", process.stderr)
        return json.loads(process.stdout.strip())

    def stage(self):
        return self.cli(
            "scripts.stage_ebbot_equity_ohlcv",
            "--index", self.index,
            "--stocks", self.kap,
            "--input-csv", self.csv,
            "--manifest", self.manifest,
            "--mapping", self.mapping,
            "--calendar", self.calendar,
            "--output-csv", self.staged,
            "--as-of", self.day,
        )

    def test_windows_cli_chain_from_vendor_to_two_data_center_reports(self):
        input_hash = hashlib.sha256(self.csv.read_bytes()).hexdigest()
        result = self.stage()
        self.assertEqual(result["status"], "STAGED_REVIEW_ONLY_NOT_LICENSE_VERIFIED")
        self.assertFalse(result["license_verified"])
        self.assertEqual(result["staged_bar_count"], 1)
        self.assertEqual(result["staged_symbol_count"], 1)
        self.assertEqual(result["orders"], 0)
        self.assertTrue(self.staged.is_file())

        coverage_cli = self.cli(
            "scripts.audit_ebbot_market_data_coverage",
            "--index", self.index,
            "--stocks", self.kap,
            "--bars", self.staged,
            "--as-of", self.day,
            "--min-bars", 2,
            "--report-json", self.coverage,
        )
        self.assertEqual(coverage_cli["status"], "BLOCKED_INCOMPLETE_EVIDENCE")
        coverage = read_equity_coverage_report(str(self.coverage), today=self.today)
        self.assertEqual(coverage["status"], "unverified")
        self.assertEqual(coverage["markets"]["tr"]["candidate_instruments"], 3)
        self.assertEqual(coverage["markets"]["tr"]["with_any_ohlcv"], 1)
        self.assertEqual(coverage["markets"]["tr"]["insufficient_history_count"], 1)
        self.assertEqual(coverage["markets"]["tr"]["missing_ohlcv_count"], 2)
        self.assertEqual(coverage["total_candidate_instruments"], 6)
        self.assertFalse(coverage["licensed_ohlcv_verified"])
        self.assertNotIn("THYAO.IS", json.dumps(coverage))

        bist_cli = self.cli(
            "scripts.audit_ebbot_bist_reference_identity",
            "--kap", self.kap,
            "--exchange", self.exchange,
            "--mapping", self.mapping,
            "--bars", self.staged,
            "--as-of", self.day,
            "--report-json", self.bist,
        )
        self.assertEqual(bist_cli["status"], "BLOCKED_STALE_OR_INCOMPLETE_BIST_REFERENCES")
        summary = read_bist_identity_summary(str(self.bist), today=self.today)
        self.assertEqual(summary["status"], "unverified")
        self.assertEqual(summary["counts"]["kap_candidate_count"], 3)
        self.assertEqual(summary["counts"]["exchange_active_count"], 2)
        self.assertEqual(summary["counts"]["matched_active_kap_exchange_count"], 1)
        self.assertEqual(summary["counts"]["exchange_halted_or_delisted_count"], 1)
        self.assertEqual(summary["counts"]["active_with_ohlcv_in_supplied_file_count"], 1)
        self.assertEqual(summary["counts"]["active_without_ohlcv_in_supplied_file_count"], 1)
        self.assertEqual(summary["counts"]["active_without_declared_provider_mapping_count"], 1)
        self.assertFalse(summary["licensed_prices_verified"])
        self.assertFalse(summary["live_trading_enabled"])
        self.assertNotIn("THYAO.IS", json.dumps(summary))
        self.assertNotIn(synthetic_isin(1), json.dumps(summary))
        self.assertNotIn(str(self.root), json.dumps(summary))

        sessions = self.cli(
            "scripts.audit_ebbot_equity_session_gaps",
            "--index", self.index,
            "--stocks", self.kap,
            "--bars", self.staged,
            "--calendar", self.calendar,
            "--mapping", self.mapping,
            "--as-of", self.day,
        )
        self.assertEqual(sessions["status"], "BLOCKED_REQUIRES_INDEPENDENT_MARKET_DATA_VALIDATION")
        self.assertEqual(sessions["markets"]["tr"]["symbols_with_any_ohlcv"], 1)
        self.assertEqual(sessions["markets"]["tr"]["potential_missing_symbol_session_slots"], 2)
        self.assertEqual(sessions["bar_identity_diagnostics"]["bar_rows_matching_declared_map"], 1)
        self.assertEqual(sessions["markets_without_calendar"], ["us", "de", "hk"])
        self.assertFalse(sessions["live_trading_enabled"])

        rights = self.cli(
            "scripts.audit_ebbot_equity_provider_readiness", "--as-of", self.day,
        )
        self.assertEqual(rights["status"], "BLOCKED_NOT_APPROVED_FOR_DATA_INGESTION_OR_TRADING")
        self.assertEqual(rights["markets_with_review_record"], 0)
        self.assertFalse(rights["may_auto_import_quotes"])
        self.assertEqual(hashlib.sha256(self.csv.read_bytes()).hexdigest(), input_hash)

    def test_manifest_hash_tampering_blocks_staging_without_creating_output(self):
        self.csv.write_text(
            self.csv.read_text(encoding="utf-8").replace("1000,fixture_export", "2000,fixture_export"),
            encoding="utf-8",
        )
        error = self.cli(
            "scripts.stage_ebbot_equity_ohlcv",
            "--index", self.index, "--stocks", self.kap,
            "--input-csv", self.csv, "--manifest", self.manifest,
            "--mapping", self.mapping, "--calendar", self.calendar,
            "--output-csv", self.staged, "--as-of", self.day,
            expected=1,
        )
        self.assertEqual(error["reason"], "provider_export_checksum_mismatch")
        self.assertFalse(self.staged.exists())

    def test_invalid_isin_blocks_bist_without_publishing_report(self):
        self.exchange.write_text(
            self.exchange.read_text(encoding="utf-8").replace(
                synthetic_isin(1), "TRNOTANISIN"
            ),
            encoding="utf-8",
        )
        result = self.cli(
            "scripts.audit_ebbot_bist_reference_identity",
            "--kap", self.kap, "--exchange", self.exchange,
            "--as-of", self.day, "--report-json", self.bist,
            expected=1,
        )
        self.assertEqual(result["status"], "BLOCKED_INVALID_BIST_REFERENCE")
        self.assertFalse(self.bist.exists())

    def test_missing_exchange_reference_returns_unknown_not_zero(self):
        report = self.cli(
            "scripts.audit_ebbot_bist_reference_identity",
            "--kap", self.kap, "--as-of", self.day,
            "--report-json", self.bist,
        )
        self.assertEqual(report["status"], "BLOCKED_MISSING_BIST_SOURCE_FILES")
        self.assertIsNone(report["exchange_active_count"])
        self.assertIsNone(read_bist_identity_summary(str(self.bist), today=self.today)["counts"])

    def test_staging_output_file_will_not_be_overwritten(self):
        self.staged.write_text("EXISTING OPERATOR DATA MUST STAY", encoding="utf-8")
        error = self.cli(
            "scripts.stage_ebbot_equity_ohlcv",
            "--index", self.index, "--stocks", self.kap,
            "--input-csv", self.csv, "--manifest", self.manifest,
            "--mapping", self.mapping, "--calendar", self.calendar,
            "--output-csv", self.staged, "--as-of", self.day,
            expected=1,
        )
        self.assertEqual(error["status"], "BLOCKED_INVALID_VENDOR_INPUT")
        self.assertEqual(self.staged.read_text(encoding="utf-8"),
                         "EXISTING OPERATOR DATA MUST STAY")

    def test_mismatched_provider_ticker_blocks_staging(self):
        self.csv.write_text(
            self.csv.read_text(encoding="utf-8").replace(
                ",fixture_vendor,THYAO", ",fixture_vendor,WRONG"
            ),
            encoding="utf-8",
        )
        self.write_manifest()
        error = self.cli(
            "scripts.stage_ebbot_equity_ohlcv",
            "--index", self.index, "--stocks", self.kap,
            "--input-csv", self.csv, "--manifest", self.manifest,
            "--mapping", self.mapping, "--calendar", self.calendar,
            "--output-csv", self.staged, "--as-of", self.day,
            expected=1,
        )
        self.assertEqual(error["reason"], "provider_ticker_identity_mismatch")
        self.assertFalse(self.staged.exists())


if __name__ == "__main__":
    unittest.main()
