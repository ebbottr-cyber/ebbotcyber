"""Pure no-network main-branch protection readiness regression tests."""
from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from scripts.audit_main_release_protection import (
    EXPECTED_MAIN_SHA, EXPECTED_PR130_SHA,
    assess_main_release_protection, load_json,
)


def fixture():
    return (
        {"full_name": "ebbottr-cyber/ebbotcyber", "default_branch": "main", "private": False},
        {"name": "main", "commit": {"sha": EXPECTED_MAIN_SHA}, "protected": False},
        [],
        {
            "number": 130, "state": "open", "draft": True, "merged_at": None,
            "head": {
                "sha": EXPECTED_PR130_SHA,
                "ref": "audit/ebbot-main-pr122-solana-replay-full-20261120",
                "repo": {"full_name": "ebbottr-cyber/ebbotcyber"},
            },
            "base": {"ref": "audit/ebbot-pr122-main-full-offline-20261120"},
        },
    )


class BranchSecurityTest(unittest.TestCase):
    def test_real_current_shape_is_release_blocked(self):
        x = assess_main_release_protection(*fixture())
        self.assertEqual(x["status"], "BLOCKED_MAIN_UNPROTECTED")
        self.assertFalse(x["main_protected_public_metadata"])
        self.assertEqual(x["active_rulesets_reported"], 0)
        self.assertIn("main_reports_unprotected", x["release_blockers"])
        self.assertIn("no_active_repository_rulesets_reported", x["release_blockers"])
        self.assertFalse(x["approved_to_merge_main"])
        self.assertFalse(x["production_deployment_approved"])
        self.assertEqual(x["orders"], 0)
        self.assertEqual(x["paper_fills"], 0)
        self.assertEqual(x["journal_writes"], 0)

    def test_fake_protected_flag_without_policy_proof_still_blocked(self):
        repo, branch, rules, pr = fixture()
        branch["protected"] = True
        x = assess_main_release_protection(repo, branch, rules, pr)
        self.assertEqual(x["status"], "BLOCKED_ADMIN_POLICY_VERIFICATION_REQUIRED")
        self.assertFalse(x["requires_review_and_checks_proven"])
        self.assertFalse(x["force_pushes_blocked_proven"])
        self.assertFalse(x["approved_to_merge_main"])

    def test_active_ruleset_title_is_not_proof_it_applies_to_main(self):
        repo, branch, rules, pr = fixture()
        branch["protected"] = True
        rules[:] = [{"id": 123, "name": "secure main (unverified)", "enforcement": "active"}]
        x = assess_main_release_protection(repo, branch, rules, pr)
        self.assertEqual(x["active_rulesets_reported"], 1)
        self.assertFalse(x["applies_to_main_proven"])
        self.assertFalse(x["admin_bypass_limited_proven"])
        self.assertFalse(x["approved_to_merge_main"])

    def test_evaluate_and_disabled_rules_not_confused_with_enforced(self):
        repo, branch, rules, pr = fixture()
        branch["protected"] = True
        rules.extend([
            {"id": 11, "enforcement": "evaluate"},
            {"id": 12, "enforcement": "disabled"},
        ])
        x = assess_main_release_protection(repo, branch, rules, pr)
        self.assertEqual(x["active_rulesets_reported"], 0)
        self.assertFalse(x["approved_to_merge_main"])

    def test_main_or_audited_pr_drift_blocked(self):
        repo, branch, rules, pr = fixture()
        branch["commit"]["sha"] = "1" * 40
        x = assess_main_release_protection(repo, branch, rules, pr)
        self.assertEqual(x["status"], "BLOCKED_PINNED_SOURCE_MOVED")
        self.assertIn("main_commit_moved_since_review", x["release_blockers"])
        repo, branch, rules, pr = fixture()
        pr["head"]["sha"] = "2" * 40
        x = assess_main_release_protection(repo, branch, rules, pr)
        self.assertEqual(x["status"], "BLOCKED_PINNED_SOURCE_MOVED")
        self.assertIn("pr130_head_moved_since_review", x["release_blockers"])

    def test_missing_or_unknown_security_metadata_rejected(self):
        tests = [
            (1, {"protected": "false"}),
            (2, [{"id": 3, "enforcement": "mystery"}]),
            (2, [{"id": True, "enforcement": "active"}]),
            (0, {"full_name": "other/repo"}),
            (3, {"draft": False}),
            (3, {"merged_at": "2026-11-20T20:00:00Z"}),
            (3, {"state": "closed"}),
        ]
        for index, changes in tests:
            values = list(deepcopy(fixture()))
            if index == 2:
                values[index] = changes
            else:
                values[index].update(changes)
            with self.subTest(index=index, changes=changes), self.assertRaises(ValueError):
                assess_main_release_protection(*values)

    def test_untrusted_source_repo_and_branch_are_rejected(self):
        repo, branch, rules, pr = fixture()
        pr["head"]["repo"]["full_name"] = "other/somewhere"
        with self.assertRaisesRegex(ValueError, "expected_pr130"):
            assess_main_release_protection(repo, branch, rules, pr)
        repo, branch, rules, pr = fixture()
        branch["name"] = "develop"
        with self.assertRaisesRegex(ValueError, "repository_or_main"):
            assess_main_release_protection(repo, branch, rules, pr)

    def test_nonfinite_or_unsafe_json_never_accepted(self):
        with TemporaryDirectory() as d:
            p = Path(d) / "bad.json"
            p.write_text('{"protected": NaN}', encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "nonfinite"):
                load_json(p)
            p.write_text("[]" * 250_001, encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "missing_or_oversized"):
                load_json(p)
            p.unlink()
            with self.assertRaisesRegex(ValueError, "missing_or_oversized"):
                load_json(p)


if __name__ == "__main__":
    unittest.main()
