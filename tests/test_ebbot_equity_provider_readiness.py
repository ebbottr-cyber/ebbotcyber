"""Offline regressions: operator claim is never a market-data license."""
from __future__ import annotations

from contextlib import redirect_stdout
from datetime import date
import io
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from scripts.audit_ebbot_market_data_coverage import AuditInputError
from scripts.audit_ebbot_equity_provider_readiness import (
    CATALOG, MARKETS, REQUIRED_CHECKS, REQUIRED_RIGHTS,
    audit_provider_readiness, parser, run,
)

NOW = date(2026, 11, 21)


def review_record() -> dict:
    return {
        "provider_reference": "NONSECRET-DEMO",
        "product_reference": "EOD-PRODUCT-01",
        "assessment_ticket": "LOCAL-TICKET-123",
        "reviewed_utc_date": "2026-11-20",
        "access_expires_utc_date": "2027-01-31",
        "rights_claimed": {name: True for name in REQUIRED_RIGHTS},
        "checks_claimed": {name: True for name in REQUIRED_CHECKS},
    }


class ProviderReadinessTests(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.file = self.root / "operator-claims.json"

    def write(self, markets: dict, version: object = 1) -> Path:
        self.file.write_text(
            json.dumps({"schema_version": version, "markets": markets}),
            encoding="utf-8",
        )
        return self.file

    def test_official_research_catalog_covers_exactly_four_markets_without_access(self):
        report = audit_provider_readiness(as_of=NOW)
        self.assertEqual(report["selected_markets"], list(MARKETS))
        self.assertEqual(report["markets_with_review_record"], 0)
        self.assertEqual(report["markets_with_complete_operator_claims"], 0)
        for market in MARKETS:
            self.assertEqual(report["markets"][market]["state"], "MISSING_OPERATOR_EVIDENCE")
            self.assertEqual(report["markets"][market]["missing_requirements"], ["no_operator_review_record"])
            for option in report["markets"][market]["official_product_research_options"]:
                self.assertTrue(option["official_product_url"].startswith("https://"))
                self.assertFalse(option["connection_configured"])
                self.assertFalse(option["license_verified"])
                self.assertFalse(option["ohlcv_ingested"])
        self.assertTrue(CATALOG.is_file())
        self.assertFalse(report["may_auto_import_quotes"])
        self.assertFalse(report["may_use_in_analysis"])
        self.assertFalse(report["paper_trading_enabled"])
        self.assertFalse(report["live_trading_enabled"])
        self.assertEqual(report["network_requests"], 0)
        self.assertEqual(report["orders"], 0)

    def test_all_claims_true_never_means_contract_or_trade_verified(self):
        report = audit_provider_readiness(
            self.write({market: review_record() for market in MARKETS}),
            as_of=NOW,
        )
        self.assertEqual(report["markets_with_review_record"], 4)
        self.assertEqual(report["markets_with_complete_operator_claims"], 4)
        self.assertEqual(report["status"], "BLOCKED_NOT_APPROVED_FOR_DATA_INGESTION_OR_TRADING")
        self.assertEqual(
            report["markets"]["us"]["state"],
            "OPERATOR_CLAIMS_SUBMITTED_NEEDS_INDEPENDENT_VERIFICATION",
        )
        self.assertFalse(report["independent_contract_verification"])
        self.assertFalse(report["licensed_historical_prices_loaded"])
        self.assertFalse(report["provider_credentials_connected"])
        self.assertFalse(report["may_auto_import_quotes"])
        self.assertFalse(report["may_use_in_analysis"])
        self.assertFalse(report["live_trading_enabled"])
        self.assertNotIn("LOCAL-TICKET", json.dumps(report))
        self.assertNotIn("NONSECRET-DEMO", json.dumps(report))

    def test_partial_markets_stay_blocked_with_explicit_missing_market(self):
        report = audit_provider_readiness(self.write({"de": review_record()}), as_of=NOW)
        self.assertEqual(report["markets_with_review_record"], 1)
        self.assertEqual(report["markets_with_complete_operator_claims"], 1)
        self.assertEqual(report["markets"]["tr"]["state"], "MISSING_OPERATOR_EVIDENCE")
        self.assertEqual(report["markets"]["hk"]["state"], "MISSING_OPERATOR_EVIDENCE")

    def test_missing_critical_automated_research_right_detected(self):
        rec = review_record()
        rec["rights_claimed"]["automated_algorithmic_analysis"] = False
        report = audit_provider_readiness(self.write({"us": rec}), as_of=NOW)
        self.assertIn(
            "right_not_attested:automated_algorithmic_analysis",
            report["markets"]["us"]["missing_requirements"],
        )
        self.assertEqual(
            report["markets"]["us"]["state"],
            "BLOCKED_INCOMPLETE_OR_EXPIRED_OPERATOR_EVIDENCE",
        )

    def test_missing_manual_source_review_check_is_explicit(self):
        rec = review_record()
        rec["checks_claimed"]["sample_export_obtained_by_authorized_person"] = False
        report = audit_provider_readiness(self.write({"tr": rec}), as_of=NOW)
        self.assertIn(
            "check_not_attested:sample_export_obtained_by_authorized_person",
            report["markets"]["tr"]["missing_requirements"],
        )

    def test_expired_and_review_older_than_30_days_fail(self):
        rec = review_record()
        rec["reviewed_utc_date"] = "2026-09-20"
        rec["access_expires_utc_date"] = "2026-10-10"
        r = audit_provider_readiness(self.write({"hk": rec}), as_of=NOW)
        missing = r["markets"]["hk"]["missing_requirements"]
        self.assertIn("access_review_expired", missing)
        self.assertIn("operator_review_older_than_30_days", missing)

    def test_future_review_rejected_not_trusted(self):
        rec = review_record()
        rec["reviewed_utc_date"] = "2026-11-22"
        with self.assertRaisesRegex(AuditInputError, "future_provider_review"):
            audit_provider_readiness(self.write({"de": rec}), as_of=NOW)

    def test_expiry_before_review_rejected_as_incomplete(self):
        rec = review_record()
        rec["access_expires_utc_date"] = "2026-11-19"
        r = audit_provider_readiness(self.write({"de": rec}), as_of=NOW)
        self.assertIn("access_expiry_before_review", r["markets"]["de"]["missing_requirements"])

    def test_boolean_schema_version_is_rejected(self):
        with self.assertRaisesRegex(AuditInputError, "unsupported_provider_review_version"):
            audit_provider_readiness(self.write({}, version=True), as_of=NOW)

    def test_unknown_market_is_rejected(self):
        with self.assertRaisesRegex(AuditInputError, "unsupported_review_market"):
            audit_provider_readiness(self.write({"xx": review_record()}), as_of=NOW)

    def test_non_boolean_assertion_is_rejected(self):
        rec = review_record()
        rec["checks_claimed"]["exchange_ticker_mapping_reviewed"] = "yes"
        with self.assertRaisesRegex(AuditInputError, "non_boolean_provider_attestation"):
            audit_provider_readiness(self.write({"us": rec}), as_of=NOW)

    def test_missing_reference_and_invalid_extra_fields_rejected(self):
        rec = review_record()
        rec["assessment_ticket"] = ""
        with self.assertRaisesRegex(AuditInputError, "unsafe_or_missing"):
            audit_provider_readiness(self.write({"us": rec}), as_of=NOW)
        rec = review_record()
        rec["api_key"] = "accidental-should-never-be-accepted"
        with self.assertRaisesRegex(AuditInputError, "invalid_provider_review_schema"):
            audit_provider_readiness(self.write({"us": rec}), as_of=NOW)

    def test_absent_and_symlinked_files_rejected(self):
        with self.assertRaisesRegex(AuditInputError, "missing_unsafe"):
            audit_provider_readiness(self.root / "missing.json", as_of=NOW)
        target = self.write({})
        link = self.root / "linked.json"
        try:
            link.symlink_to(target)
        except (OSError, NotImplementedError):
            self.skipTest("No symlink support")
        with self.assertRaisesRegex(AuditInputError, "missing_unsafe"):
            audit_provider_readiness(link, as_of=NOW)

    def test_cli_invalid_is_fail_closed_and_does_not_dump_confidential_path(self):
        rec = review_record()
        rec["provider_reference"] = "unsafe path with spaces and secrets"
        self.write({"tr": rec})
        args = parser().parse_args(["--review", str(self.file), "--as-of", NOW.isoformat()])
        output = io.StringIO()
        with redirect_stdout(output):
            code = run(args)
        self.assertEqual(code, 1)
        data = json.loads(output.getvalue())
        self.assertEqual(data["status"], "BLOCKED_INVALID_REVIEW_INPUT")
        self.assertNotIn(str(self.root), output.getvalue())
        self.assertEqual(data["network_requests"], 0)
        self.assertEqual(data["orders"], 0)

    def test_no_review_cli_reports_blocked_not_zero_prices(self):
        args = parser().parse_args(["--as-of", NOW.isoformat()])
        output = io.StringIO()
        with redirect_stdout(output):
            code = run(args)
        self.assertEqual(code, 0)
        data = json.loads(output.getvalue())
        self.assertEqual(data["markets_with_review_record"], 0)
        self.assertEqual(data["status"], "BLOCKED_NOT_APPROVED_FOR_DATA_INGESTION_OR_TRADING")
        self.assertFalse(data["licensed_historical_prices_loaded"])


if __name__ == "__main__":
    unittest.main()
