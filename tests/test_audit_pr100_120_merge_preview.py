"""Offline-only regressions for read-only PR100-120 merge-tree audit."""
from __future__ import annotations

from copy import deepcopy
import unittest

from scripts.audit_pr100_120_merge_preview import (
    EXPECTED_MAIN, MERGED, PINNED, PR_NUMBERS, PAIRS,
    audit_inventory, build_report, interpret_preview,
)


def inventory():
    pulls = []
    for n in PR_NUMBERS:
        pinned = PINNED.get(n)
        pulls.append({
            "number": n,
            "state": "closed" if n in MERGED else "open",
            "draft": False if n in MERGED else True,
            "merged_at": "2026-11-20T10:00:00Z" if n in MERGED else None,
            "head": {
                "sha": pinned["sha"] if pinned else f"{n:040x}",
                "ref": pinned["branch"] if pinned else f"review/pr{n}",
            },
            "base": {"ref": "main" if n in MERGED else f"test/base{n}"},
        })
    return pulls, {"commit": {"sha": EXPECTED_MAIN}, "protected": False}


def clean_preview(left, right):
    return {"status": "CLEAN_PREVIEW_ONLY", "tree": "a" * 40,
            "conflicts": [], "details": None}


def conflicting_preview(left, right):
    if (left == PINNED[113]["sha"] and right == PINNED[120]["sha"]):
        return {"status": "MERGE_CONFLICTS", "tree": "a" * 40,
                "conflicts": ["api/v1/endpoints/portfolio.py", "apps/dsa-web/src/App.tsx"],
                "details": None}
    return clean_preview(left, right)


class TestPr100To120Audit(unittest.TestCase):
    def test_full_21_pull_snapshot_and_unprotected_main(self):
        prs, main = inventory()
        result = audit_inventory(prs, main)
        self.assertEqual(len(result["inventory"]), 21)
        self.assertEqual(result["open_draft_pr_count"], 18)
        self.assertEqual(result["merged_prs"], [105, 110, 115])
        self.assertFalse(result["main_branch_protected"])
        self.assertTrue(result["main_unprotected_security_blocker"])

    def test_shifting_main_and_pinned_head_block_previews(self):
        prs, main = inventory()
        main["commit"]["sha"] = "b" * 40
        with self.assertRaisesRegex(ValueError, "main_moved_since_pinned_audit"):
            audit_inventory(prs, main)
        prs, main = inventory()
        prs[13]["head"]["sha"] = "b" * 40  # PR113
        with self.assertRaisesRegex(ValueError, "pinned_pr_113_changed_since_audit"):
            audit_inventory(prs, main)

    def test_open_pr_must_remain_draft_and_merged_pr_status_not_reinterpreted(self):
        prs, main = inventory()
        prs[20]["draft"] = False
        with self.assertRaisesRegex(ValueError, "draft_pr_status_changed"):
            audit_inventory(prs, main)
        prs, main = inventory()
        prs[10]["merged_at"] = None
        with self.assertRaisesRegex(ValueError, "expected_merged_pr_changed"):
            audit_inventory(prs, main)

    def test_no_missing_or_repeated_pr_metadata_allowed(self):
        prs, main = inventory()
        with self.assertRaisesRegex(ValueError, "pr100_120_metadata_incomplete"):
            audit_inventory(prs[:-1], main)
        with self.assertRaisesRegex(ValueError, "duplicate_pr_metadata"):
            audit_inventory(prs + [deepcopy(prs[0])], main)

    def test_conflict_preview_extracts_paths_without_worktree_mutation(self):
        s = (
            "1" * 40 + "\n"
            "api/v1/endpoints/portfolio.py\n"
            "apps/dsa-web/src/App.tsx\n\n"
            "Auto-merging api/v1/endpoints/portfolio.py\n"
            "CONFLICT (content): Merge conflict in api/v1/endpoints/portfolio.py\n"
        )
        result = interpret_preview(1, s)
        self.assertEqual(result["status"], "MERGE_CONFLICTS")
        self.assertEqual(result["conflicts"], [
            "api/v1/endpoints/portfolio.py",
            "apps/dsa-web/src/App.tsx",
        ])

    def test_clean_preview_does_not_claim_composite_tests_passed(self):
        result = interpret_preview(0, "2" * 40 + "\n")
        self.assertEqual(result["status"], "CLEAN_PREVIEW_ONLY")
        self.assertEqual(result["conflicts"], [])
        pulls, main = inventory()
        report = build_report(pulls, main, preview=clean_preview)
        self.assertEqual(report["status"], "PAIRWISE_CLEAN_PREVIEW_NOT_INTEGRATED")
        self.assertTrue(report["core_pairwise_clean_for_ephemeral_test"])
        self.assertFalse(report["three_way_merge_verified"])
        self.assertFalse(report["combined_backend_tests_executed"])
        self.assertFalse(report["combined_frontend_tests_executed"])
        self.assertFalse(report["safe_to_merge_main"])

    def test_real_conflicts_block_without_mutating_any_remote(self):
        prs, main = inventory()
        result = build_report(prs, main, preview=conflicting_preview)
        self.assertEqual(result["status"], "BLOCKED_MERGE_CONFLICTS")
        self.assertEqual(result["conflicting_pairs"], ["pr113_vs_pr120"])
        self.assertFalse(result["core_pairwise_clean_for_ephemeral_test"])
        self.assertFalse(result["safe_to_merge_main"])
        self.assertEqual(result["orders"], result["paper_fills"])
        self.assertFalse(result["trading_enabled"])

    def test_errors_never_appear_as_clean(self):
        self.assertEqual(interpret_preview(128, "fatal: bad object")["status"],
                         "PREVIEW_TOOL_ERROR")
        self.assertEqual(interpret_preview(1, "f" * 40 + "\n")["status"],
                         "PREVIEW_TOOL_ERROR")
        prs, main = inventory()
        result = build_report(
            prs, main,
            preview=lambda _a, _b: {
                "status": "PREVIEW_TOOL_ERROR",
                "tree": None, "conflicts": [], "details": "missing commit",
            },
        )
        self.assertEqual(result["status"], "BLOCKED_PREVIEW_ERRORS")
        self.assertFalse(result["core_pairwise_clean_for_ephemeral_test"])
        self.assertEqual(len(result["preview_error_pairs"]), len(PAIRS))


if __name__ == "__main__":
    unittest.main()
