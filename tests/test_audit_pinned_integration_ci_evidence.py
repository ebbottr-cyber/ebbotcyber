"""Offline-only provenance/regression tests: successful CI != permission to release."""
from __future__ import annotations

from copy import deepcopy
import unittest

from scripts.audit_pinned_integration_ci_evidence import (
    RUN_ID, RUN_NAME, HEAD_BRANCH, PR122_SHA, REQUIRED_JOB_STEPS,
    EXPECTED_MAIN_SHA, EXPECTED_PR130_SHA, REPOSITORY,
    assess_integration_ci,
)


def examples():
    run = {
        "id": RUN_ID, "name": RUN_NAME,
        "head_sha": EXPECTED_PR130_SHA, "head_branch": HEAD_BRANCH,
        "repository": {"full_name": REPOSITORY},
        "status": "completed", "conclusion": "success",
        "event": "push", "run_attempt": 1,
    }
    jobs = {"jobs": []}
    for n, (name, required) in enumerate(REQUIRED_JOB_STEPS.items(), 1):
        jobs["jobs"].append({
            "id": 136555000000 + n,
            "run_id": RUN_ID, "head_sha": EXPECTED_PR130_SHA,
            "name": name, "status": "completed", "conclusion": "success",
            "steps": [
                {"name": item, "status": "completed", "conclusion": "success"}
                for item in required
            ],
        })
    def pr(number, branch, sha, base):
        return {
            "number": number, "state": "open", "draft": True, "merged_at": None,
            "head": {"sha": sha, "ref": branch,
                     "repo": {"full_name": REPOSITORY}},
            "base": {"ref": base},
        }
    pr130 = pr(130, HEAD_BRANCH, EXPECTED_PR130_SHA,
               "audit/ebbot-pr122-main-full-offline-20261120")
    pr122 = pr(122, "integration/ebbot-pr113-tr-data-safety-20261120",
               PR122_SHA, "release-candidate/ebbot-main-pr109-offline-20261120")
    main = {"name": "main", "commit": {"sha": EXPECTED_MAIN_SHA}, "protected": False}
    return [run, jobs, pr130, pr122, main]


class PinnedIntegrationProvenanceTest(unittest.TestCase):
    def test_valid_run_confirms_jobs_but_never_release(self):
        report = assess_integration_ci(*examples())
        self.assertEqual(report["verified_job_count"], 3)
        self.assertTrue(report["all_required_integration_jobs_verified"])
        self.assertFalse(report["approved_to_merge_main"])
        self.assertFalse(report["production_deployment_approved"])
        self.assertFalse(report["scheduler_enabled"])
        self.assertFalse(report["prices_executable"])
        self.assertEqual(report["orders"], 0)
        self.assertEqual(report["paper_fills"], 0)
        self.assertEqual(report["journal_writes"], 0)
        self.assertIn("main_unprotected", report["release_blockers"])

    def test_skipped_failed_cancelled_job_is_not_a_pass(self):
        for conclusion in ("skipped", "failure", "cancelled", None):
            a = examples()
            a[1]["jobs"][1]["conclusion"] = conclusion
            with self.subTest(conclusion=conclusion):
                with self.assertRaisesRegex(ValueError, "skipped_failed"):
                    assess_integration_ci(*a)

    def test_incomplete_run_or_replay_attempt_does_not_pass(self):
        for field, value in [
            ("status", "in_progress"), ("conclusion", "cancelled"),
            ("head_sha", "f" * 40), ("head_branch", "main"),
            ("id", RUN_ID + 1), ("run_attempt", 2),
            ("event", "schedule"), ("name", "Other workflow"),
            ("repository", {"full_name": "other/repo"}),
        ]:
            a = examples()
            a[0][field] = value
            with self.subTest(field=field):
                with self.assertRaisesRegex(ValueError, "wrong_or_incomplete"):
                    assess_integration_ci(*a)

    def test_wrong_sha_pr130_or_pr122_disables_proof(self):
        for index, edit in [
            (2, lambda p: p["head"].update(sha="1" * 40)),
            (2, lambda p: p.update(draft=False)),
            (2, lambda p: p.update(merged_at="2026-11-20T21:00:00Z")),
            (3, lambda p: p["head"].update(sha="2" * 40)),
            (3, lambda p: p["head"].update(ref="main")),
            (3, lambda p: p.update(state="closed")),
        ]:
            a = examples()
            edit(a[index])
            with self.subTest(index=index, edit=str(edit)):
                with self.assertRaisesRegex(ValueError, "changed|moved"):
                    assess_integration_ci(*a)

    def test_main_change_or_protection_change_refuses_pinned_proof(self):
        a = examples()
        a[4]["commit"]["sha"] = "3" * 40
        with self.assertRaisesRegex(ValueError, "main_commit_or_protection_changed"):
            assess_integration_ci(*a)
        a = examples()
        a[4]["protected"] = True
        with self.assertRaisesRegex(ValueError, "main_commit_or_protection_changed"):
            assess_integration_ci(*a)

    def test_missing_duplicate_extra_or_renamed_job_rejected(self):
        for mutation in (
            lambda x: x.pop(),
            lambda x: x.append(deepcopy(x[0])),
            lambda x: x.__setitem__(1, deepcopy(x[0])),
            lambda x: x[0].update(name="renamed unverified check"),
        ):
            a = examples()
            mutation(a[1]["jobs"])
            with self.subTest(mutation=str(mutation)), self.assertRaises(ValueError):
                assess_integration_ci(*a)

    def test_wrong_source_run_job_id_or_hash_rejected(self):
        for key, value in [
            ("run_id", RUN_ID + 1),
            ("id", True),
            ("head_sha", "9" * 40),
            ("status", "queued"),
        ]:
            a = examples()
            a[1]["jobs"][0][key] = value
            with self.subTest(key=key), self.assertRaises(ValueError):
                assess_integration_ci(*a)

    def test_required_test_step_skipped_or_missing_rejected(self):
        for mode in ("failure", "skipped", "missing"):
            a = examples()
            step = a[1]["jobs"][2]["steps"][-1]
            if mode == "missing":
                a[1]["jobs"][2]["steps"].pop()
            else:
                step["conclusion"] = mode
            with self.subTest(mode=mode):
                with self.assertRaisesRegex(ValueError, "required_integration_step"):
                    assess_integration_ci(*a)

    def test_duplicate_test_step_name_rejected(self):
        a = examples()
        a[1]["jobs"][0]["steps"].append(deepcopy(a[1]["jobs"][0]["steps"][0]))
        with self.assertRaisesRegex(ValueError, "required_integration_step"):
            assess_integration_ci(*a)


if __name__ == "__main__":
    unittest.main()
