"""Stdlib-only tests for pinned GitHub artifact evidence without live network."""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime
import json
from io import StringIO
from contextlib import redirect_stdout
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from scripts.audit_tr_fx_archived_evidence import (
    PINNED_RUNS, _read_strict_json, build_report, validate_archive,
)
from src.services.tr_market_overview_service import SOURCE


def observation(hour: int) -> dict:
    day = "2026-11-20"
    return {
        "status": "READ_ONLY_OBSERVATION",
        "observed_at_istanbul": f"2026-11-20T{hour:02d}:00:00+03:00",
        "as_of_local_date": day,
        "research_only": True,
        "prices_executable": False,
        "paper_trading_enabled": False,
        "live_trading_enabled": False,
        "scheduler_enabled": False,
        "orders": 0,
        "paper_fills": 0,
        "journal_writes": 0,
        "market_daily": {
            "checks": [
                {
                    "key": key, "symbol": symbol, "source": SOURCE,
                    "price": 10000.0, "price_date": day,
                    "status": "observed_delayed_daily",
                    "indicative_only": True, "executable_quote": False,
                }
                for key, symbol in [
                    ("bist100", "XU100.IS"),
                    ("bist30", "XU030.IS"),
                    ("usdtry", "TRY=X"),
                    ("eurtry", "EURTRY=X"),
                ]
            ]
        },
        "official_tcmb": {
            "checks": [
                {
                    "currency": currency, "target_currency": "TRY",
                    "try_per_unit": 10.0, "bulletin_date": day,
                    "source": "TCMB daily ForexSelling",
                    "status": "observed_official_indicative",
                    "executable_quote": False,
                }
                for currency in ("USD", "EUR", "CNY")
            ]
        },
    }


def github_run(pinned: dict) -> dict:
    return {
        "id": pinned["run_id"],
        "head_sha": pinned["commit"],
        "head_branch": pinned["branch"],
        "repository": {"full_name": "ebbottr-cyber/ebbotcyber"},
        "status": "completed",
        "conclusion": "success",
        "event": "push",
        "created_at": "2026-11-20T18:00:00Z",
        "updated_at": "2026-11-20T21:00:00Z",
    }


def three_runs() -> list[tuple[dict, dict, dict]]:
    return [
        (pinned, github_run(pinned), observation(21 + i))
        for i, pinned in enumerate(PINNED_RUNS)
    ]


class GithubArchivedEvidenceTest(unittest.TestCase):
    def test_three_successful_runs_are_not_three_independent_market_days(self):
        r = build_report(three_runs())
        self.assertEqual(r["status"], "ARCHIVED_EVIDENCE_CHECKED")
        self.assertEqual(r["pinned_run_count"], 3)
        self.assertEqual(r["independently_observed_github_run_count"], 3)
        self.assertEqual(r["continuity"]["total_observations"], 3)
        self.assertEqual(r["continuity"]["distinct_observation_dates"], 1)
        self.assertEqual(r["continuity"]["status"], "INSUFFICIENT_DISTINCT_DATES")
        for key, value in r["continuity"]["provider_publication_evidence"].items():
            self.assertEqual(value["distinct_publication_dates"], 1, key)
        self.assertTrue(r["market_data_values_redacted_from_summary"])
        self.assertFalse(r["prices_executable"])
        self.assertFalse(r["long_term_reliability_proven"])
        self.assertFalse(r["licensed_second_bist_source_verified"])
        self.assertEqual(r["orders"], r["paper_fills"])
        self.assertEqual(r["paper_fills"], 0)
        json.dumps(r, allow_nan=False)

    def test_pinned_run_ids_cannot_be_repeated_or_reassigned(self):
        originals = three_runs()
        overwritten = deepcopy(originals)
        overwritten[2] = overwritten[0]
        with self.assertRaisesRegex(ValueError, "duplicate_or_unpinned_run"):
            build_report(overwritten)
        overwritten = deepcopy(originals)
        overwritten[1][0]["commit"] = "0" * 40
        with self.assertRaisesRegex(ValueError, "modified_pinned_run_contract"):
            build_report(overwritten)

    def test_successful_run_must_have_exact_sha_branch_and_repo(self):
        p, meta, snapshot = three_runs()[0]
        for change in (
            {"head_sha": "0" * 40},
            {"head_branch": "main"},
            {"repository": {"full_name": "someone-else/ebbotcyber"}},
            {"status": "in_progress"},
            {"conclusion": "failure"},
            {"event": "schedule"},
        ):
            malformed = dict(meta, **change)
            with self.subTest(change=change):
                with self.assertRaisesRegex(ValueError, "pinned_github_run_metadata_mismatch"):
                    validate_archive(p, malformed, snapshot)

    def test_observed_instant_must_fit_original_successful_run(self):
        p, meta, sample = three_runs()[0]
        for value in ("2026-11-19T22:00:00+03:00",
                      "2026-11-21T22:00:00+03:00"):
            modified = dict(sample, observed_at_istanbul=value)
            with self.assertRaisesRegex(ValueError, "snapshot_outside_pinned_run_interval"):
                validate_archive(p, meta, modified)
        modified = dict(sample, as_of_local_date="2026-11-21")
        with self.assertRaisesRegex(ValueError, "snapshot_istanbul_local_date_mismatch"):
            validate_archive(p, meta, modified)

    def test_duplicate_observed_instant_is_refused_as_fake_independence(self):
        evidence = three_runs()
        evidence[1][2]["observed_at_istanbul"] = evidence[0][2]["observed_at_istanbul"]
        with self.assertRaisesRegex(ValueError, "duplicate_observation_instant"):
            build_report(evidence)

    def test_corrupted_source_not_upgraded_to_success_by_three_github_runs(self):
        evidence = three_runs()
        evidence[2][2]["market_daily"]["checks"][0]["price"] = None
        report = build_report(evidence)
        bist = report["continuity"]["daily_evidence"][0]["sources"]["bist100"]
        self.assertEqual(bist["status"], "intermittent_within_day")
        self.assertEqual(bist["observation_count"], 3)
        self.assertEqual(bist["observed_count"], 2)
        self.assertFalse(report["continuity"]["daily_evidence"][0]["complete_indicative_source_coverage"])

    def test_nonfinite_json_and_symbolic_shortcuts_cannot_be_loaded(self):
        with TemporaryDirectory() as root:
            path = Path(root) / "fake.json"
            path.write_text('{"price":NaN}', encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "non_finite_json_not_allowed"):
                _read_strict_json(path)
            path.write_text("{}" * 1_000_000, encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "missing_oversized_or_unsafe_evidence_file"):
                _read_strict_json(path)
            path.unlink()
            with self.assertRaisesRegex(ValueError, "missing_oversized_or_unsafe_evidence_file"):
                _read_strict_json(path)


if __name__ == "__main__":
    unittest.main()
