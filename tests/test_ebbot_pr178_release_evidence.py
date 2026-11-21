"""Offline tests for exact-SHA GitHub CI gate: fail closed on skipped jobs or bad refs."""
import copy
import unittest

from scripts.audit_ebbot_pr178_release_evidence import (
    MANUAL_BLOCKERS, PINNED_MAIN, PINNED_MERGE, RUNS, evaluate,
)


def fixture():
    workflows = {}
    for label, (run_id, name, job_names) in RUNS.items():
        workflows[label] = {
            "run": {
                "id": run_id, "name": name, "head_sha": PINNED_MERGE,
                "status": "completed", "conclusion": "success",
            },
            "jobs": {
                "total_count": len(job_names),
                "jobs": [
                    {"name": job, "status": "completed", "conclusion": "success"}
                    for job in sorted(job_names)
                ],
            },
        }
    return {
        "main": {"commit": {"sha": PINNED_MAIN}, "protected": False},
        "pull_request": {
            "number": 178, "draft": True, "merged": False,
            "head": {"sha": PINNED_MERGE}, "base": {"ref": "main"},
        },
        "commit": {
            "sha": PINNED_MERGE,
            "parents": [
                {"sha": "643c7105fb1856721c1d5cd8c559d75ba4af3054"},
                {"sha": PINNED_MAIN},
            ],
        },
        "workflows": workflows,
    }


class GitHubReleaseEvidenceTest(unittest.TestCase):
    def test_even_all_green_software_is_not_approved_for_release(self):
        result = evaluate(fixture())
        self.assertEqual(result["ci_status"], "ALL_EVIDENCE_VALIDATED")
        self.assertFalse(result["release_ready"])
        self.assertEqual(result["status"], "BLOCKED")
        self.assertIn("main_branch_unprotected", result["technical_or_provenance_blockers"])
        self.assertIn("actual_windows_signing_and_smartscreen_not_verified", MANUAL_BLOCKERS)

    def test_pending_and_skipped_jobs_cannot_be_missed(self):
        for kind in ("skipped", "cancelled", "failure", None):
            with self.subTest(kind=kind):
                data = fixture()
                data["workflows"]["windows"]["jobs"]["jobs"][0]["conclusion"] = kind
                report = evaluate(data)
                self.assertEqual(report["ci_workflows"]["windows"]["status"], "PENDING_OR_FAILED")
                self.assertFalse(report["release_ready"])

    def test_full_run_status_must_be_completed_success(self):
        for status, result in (("in_progress", None), ("completed", "failure")):
            data = fixture()
            data["workflows"]["backend"]["run"].update(status=status, conclusion=result)
            self.assertEqual(evaluate(data)["ci_workflows"]["backend"]["status"], "PENDING_OR_FAILED")

    def test_prevent_wrong_sha_run_and_moved_main(self):
        data = fixture()
        data["workflows"]["react"]["run"]["head_sha"] = PINNED_MAIN
        data["main"]["commit"]["sha"] = PINNED_MERGE
        report = evaluate(data)
        self.assertIn("main_commit_drift", report["technical_or_provenance_blockers"])
        self.assertEqual(report["ci_workflows"]["react"]["status"], "PENDING_OR_FAILED")

    def test_missing_job_or_incomplete_pagination_is_red(self):
        data = fixture()
        data["workflows"]["windows"]["jobs"]["jobs"].pop()
        self.assertEqual(evaluate(data)["ci_workflows"]["windows"]["status"], "PENDING_OR_FAILED")

    def test_no_false_green_on_draft_removed_or_parent_mutated(self):
        data = fixture()
        data["pull_request"]["draft"] = False
        data["commit"]["parents"].reverse()
        report = evaluate(data)
        self.assertIn("pr178_no_longer_safe_draft", report["technical_or_provenance_blockers"])
        self.assertIn("true_two_parent_merge_provenance_missing", report["technical_or_provenance_blockers"])

    def test_even_protected_main_requires_signing_device_review(self):
        data = fixture()
        data["main"]["protected"] = True
        result = evaluate(data)
        self.assertEqual(result["ci_status"], "ALL_EVIDENCE_VALIDATED")
        self.assertFalse(result["release_ready"])
        self.assertGreaterEqual(len(result["manual_release_blockers"]), 5)

    def test_untrusted_missing_workflows_never_pass(self):
        result = evaluate({"workflows": {}})
        self.assertEqual(result["ci_status"], "INCOMPLETE_OR_UNTRUSTED")
        self.assertFalse(result["release_ready"])


if __name__ == "__main__":
    unittest.main()
