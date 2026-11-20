"""No-network provenance/security contracts for pinned main and draft PR122."""
from __future__ import annotations

from copy import deepcopy
import unittest

from scripts.audit_pr122_main_ephemeral import (
    MAIN_SHA, PR122_SHA, build_report, parse_merge_tree, validate_remote_snapshot,
)


def fixtures():
    main = {"commit": {"sha": MAIN_SHA}, "protected": False}
    pr = {
        "number": 122, "state": "open", "draft": True, "merged_at": None,
        "head": {
            "sha": PR122_SHA,
            "ref": "integration/ebbot-pr113-tr-data-safety-20261120",
        },
        "base": {"ref": "release-candidate/ebbot-main-pr109-offline-20261120"},
    }
    return main, pr


class MainPr122EphemeralTest(unittest.TestCase):
    def test_valid_state_never_grants_release_or_trading(self):
        main, pr = fixtures()
        report = build_report(
            main, pr, parse_merge_tree(0, "a" * 40 + "\n"),
        )
        self.assertEqual(report["status"], "CLEAN_EPHEMERAL_TREE_PREVIEW")
        self.assertTrue(report["eligible_for_ephemeral_combined_tests"])
        self.assertFalse(report["tests_proven_by_preview"])
        self.assertFalse(report["approved_to_merge_main"])
        self.assertFalse(report["production_deployment_approved"])
        self.assertTrue(report["main_unprotected_is_release_blocker"])
        self.assertFalse(report["live_trading_enabled"])
        self.assertFalse(report["paper_trading_enabled"])
        self.assertFalse(report["scheduler_enabled"])
        self.assertEqual(report["orders"], 0)
        self.assertEqual(report["paper_fills"], 0)
        self.assertEqual(report["journal_writes"], 0)
        self.assertEqual(report["market_data_requests"], 0)

    def test_main_moves_refuse_old_snapshot(self):
        main, pr = fixtures()
        main["commit"]["sha"] = "f" * 40
        with self.assertRaisesRegex(ValueError, "main_moved"):
            validate_remote_snapshot(main, pr)

    def test_branch_protection_change_demands_fresh_review(self):
        main, pr = fixtures()
        main["protected"] = True
        with self.assertRaisesRegex(ValueError, "reaudit"):
            validate_remote_snapshot(main, pr)

    def test_pr122_moved_or_closed_is_not_reviewed(self):
        for edit in [
            {"state": "closed"},
            {"draft": False},
            {"merged_at": "2026-11-20T20:30:00Z"},
            {"number": 121},
        ]:
            main, pr = fixtures()
            pr.update(edit)
            with self.subTest(edit=edit):
                with self.assertRaisesRegex(ValueError, "pr122_changed"):
                    validate_remote_snapshot(main, pr)

    def test_new_head_ref_or_sha_refuses_stale_snapshot(self):
        main, pr = fixtures()
        pr["head"]["sha"] = "b" * 40
        with self.assertRaisesRegex(ValueError, "pr122_changed"):
            validate_remote_snapshot(main, pr)
        main, pr = fixtures()
        pr["head"]["ref"] = "main"
        with self.assertRaisesRegex(ValueError, "pr122_changed"):
            validate_remote_snapshot(main, pr)

    def test_git_conflicts_fail_closed_even_with_tree_hash(self):
        main, pr = fixtures()
        result = build_report(
            main, pr,
            parse_merge_tree(1, "f" * 40 + "\nsrc/foo.py\n\nCONFLICT\n"),
        )
        self.assertEqual(result["status"], "BLOCKED_GIT_CONFLICTS")
        self.assertFalse(result["eligible_for_ephemeral_combined_tests"])
        self.assertFalse(result["approved_to_merge_main"])

    def test_git_errors_and_malformed_output_do_not_pass(self):
        self.assertEqual(parse_merge_tree(128, "fatal: bad tree")["status"],
                         "BLOCKED_GIT_MERGE_PREVIEW_ERROR")
        self.assertEqual(parse_merge_tree(0, "a" * 40 + "\nCONFLICT\n")["status"],
                         "BLOCKED_GIT_MERGE_PREVIEW_ERROR")
        self.assertEqual(parse_merge_tree(1, "")["status"],
                         "BLOCKED_GIT_MERGE_PREVIEW_ERROR")


if __name__ == "__main__":
    unittest.main()
