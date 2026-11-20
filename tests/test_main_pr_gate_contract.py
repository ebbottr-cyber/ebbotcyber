"""Permanent main-PR CI guard contracts: no bypass through green/skipped jobs.

Uses the Python standard library only so the policy job can run without
installing dependencies, reading secrets or fetching live provider data.
"""
from __future__ import annotations

from contextlib import redirect_stdout
from io import StringIO
import json
import os
from pathlib import Path
from unittest import TestCase
from unittest.mock import patch

from scripts.validate_main_pr_check_results import (
    REQUIRED_JOBS, main, validate_required_jobs,
)

ROOT = Path(__file__).resolve().parents[1]
CI = ROOT / ".github/workflows/pr1-verify.yml"


def successful_jobs():
    return {job: {"result": "success", "outputs": {}} for job in REQUIRED_JOBS}


class MainPrRequiredChecksTest(TestCase):
    def test_valid_four_real_job_results_are_only_review_evidence(self):
        report = validate_required_jobs(successful_jobs())
        self.assertTrue(report["all_required_jobs_success"])
        self.assertEqual(set(report["jobs"]), {"policy", "backend", "frontend", "frontend-build"})
        self.assertFalse(report["approved_to_merge_main"])
        self.assertFalse(report["production_deployment_approved"])
        self.assertFalse(report["live_trading_enabled"])
        self.assertFalse(report["paper_trading_enabled"])
        self.assertFalse(report["scheduler_enabled"])
        self.assertEqual(report["orders"], 0)
        self.assertEqual(report["paper_fills"], 0)
        self.assertEqual(report["journal_writes"], 0)

    def test_skipped_failed_cancelled_unknown_never_accepted(self):
        for name in REQUIRED_JOBS:
            for conclusion in ("skipped", "failure", "cancelled", None, "pending", True):
                jobs = successful_jobs()
                jobs[name]["result"] = conclusion
                with self.subTest(job=name, result=conclusion), self.assertRaises(ValueError):
                    validate_required_jobs(jobs)

    def test_missing_or_extra_dependencies_rejected(self):
        jobs = successful_jobs()
        del jobs["frontend"]
        with self.assertRaisesRegex(ValueError, "required_main_pr_job_set"):
            validate_required_jobs(jobs)
        jobs = successful_jobs()
        jobs["optional-check"] = {"result": "success"}
        with self.assertRaisesRegex(ValueError, "required_main_pr_job_set"):
            validate_required_jobs(jobs)

    def test_untrusted_none_or_wrong_job_object_rejected(self):
        for invalid in (None, [], "success", {"policy": "success"}):
            with self.subTest(value=invalid), self.assertRaises(ValueError):
                validate_required_jobs(invalid)
        jobs = successful_jobs()
        jobs["backend"] = True
        with self.assertRaisesRegex(ValueError, "invalid_job_result"):
            validate_required_jobs(jobs)

    def test_cli_refuses_absent_malformed_and_nonfinite_json(self):
        for value in ("", "{", '{"backend":NaN}', "x" * 16385):
            with self.subTest(value=value[:30]):
                with patch.dict(os.environ, {"EBBOT_REQUIRED_JOB_RESULTS_JSON": value}):
                    with redirect_stdout(StringIO()) as output:
                        exit_code = main()
                self.assertEqual(exit_code, 1)
                self.assertIn("BLOCKED_REQUIRED_MAIN_PR_JOB_FAILURE", output.getvalue())

    def test_cli_accepts_exact_success_jobs_but_never_approves_merging(self):
        with patch.dict(os.environ, {
            "EBBOT_REQUIRED_JOB_RESULTS_JSON": json.dumps(successful_jobs()),
        }):
            with redirect_stdout(StringIO()) as output:
                code = main()
        self.assertEqual(code, 0)
        result = json.loads(output.getvalue())
        self.assertFalse(result["approved_to_merge_main"])

    def test_ci_is_unfiltered_main_pull_request_and_branch_selftest_only(self):
        yaml = CI.read_text(encoding="utf-8")
        self.assertIn("\non:\n  pull_request:\n    branches: [main]\n", yaml)
        self.assertIn(
            "\n  push:\n    branches: [security/ebbot-main-pr-stable-required-checks-20261121]",
            yaml,
        )
        for forbidden in ("pull_request_target:", "workflow_dispatch:", "\n  schedule:",
                          "\n  workflow_run:", "\n  release:", "\n  deployment:"):
            self.assertNotIn(forbidden, yaml)
        self.assertNotIn("    paths:", yaml)
        self.assertNotIn("    paths-ignore:", yaml)

    def test_ci_has_read_only_token_and_never_publishes_or_trades(self):
        yaml = CI.read_text(encoding="utf-8")
        self.assertIn("\npermissions:\n  contents: read\n", yaml)
        self.assertNotIn("contents: write", yaml)
        self.assertNotIn("actions: write", yaml)
        self.assertNotIn("pull-requests: write", yaml)
        self.assertNotIn("id-token: write", yaml)
        self.assertNotIn("secrets.", yaml)
        self.assertNotIn("git push", yaml)
        self.assertNotIn("gh pr merge", yaml)
        self.assertEqual(yaml.count("persist-credentials: false"), 5)
        self.assertIn("  SCHEDULE_ENABLED: 'false'", yaml)
        self.assertIn("  MEME_COIN_TRADING_ENABLED: 'false'", yaml)
        self.assertIn("  MEME_RADAR_LIVE_ENABLED: 'false'", yaml)

    def test_one_stable_unskippable_aggregator_requires_four_real_jobs(self):
        yaml = CI.read_text(encoding="utf-8")
        for job in ("policy:", "backend:", "frontend:", "frontend-build:", "merge-gate:"):
            self.assertIn("\n  " + job + "\n", yaml)
        self.assertIn("name: EBBot PR / merge gate", yaml)
        self.assertIn("needs: [policy, backend, frontend, frontend-build]", yaml)
        self.assertIn("    if: ${{ always() }}", yaml)
        self.assertIn("EBBOT_REQUIRED_JOB_RESULTS_JSON: ${{ toJSON(needs) }}", yaml)
        self.assertIn("python -m scripts.validate_main_pr_check_results", yaml)

    def test_backend_and_react_test_build_jobs_do_not_skip_one_another(self):
        yaml = CI.read_text(encoding="utf-8")
        sections = yaml.split("\n  backend:\n")
        self.assertEqual(len(sections), 2)
        backend, right = sections[1].split("\n  frontend:\n", 1)
        frontend, right = right.split("\n  frontend-build:\n", 1)
        frontend_build, _ = right.split("\n  merge-gate:\n", 1)
        for job in (backend, frontend, frontend_build):
            self.assertNotIn("\n    if:", job)
            self.assertNotIn("\n    needs:", job)
        self.assertIn('python -m pytest -q -m "not network"', backend)
        self.assertIn("--disable-socket --allow-unix-socket", backend)
        self.assertIn("npm ci --no-audit --no-fund", frontend)
        self.assertIn("npm test -- --reporter=dot --reporter=junit", frontend)
        self.assertIn("--outputFile.junit=vitest-results.xml", frontend)
        self.assertIn("exit 1", frontend)
        self.assertIn("Upload complete React test evidence even when failed", frontend)
        self.assertIn("if: always()", frontend)
        self.assertIn("npm run lint", frontend_build)
        self.assertIn("npm run build", frontend_build)
        self.assertNotIn("npm run lint", frontend)
        self.assertNotIn("npm run build", frontend)


if __name__ == "__main__":
    import unittest
    unittest.main()
