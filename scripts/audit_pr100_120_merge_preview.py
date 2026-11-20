"""EBBot PR #100-#120 fail-closed, read-only merge-tree evidence gate.

This is NOT an implementation or a merge. Uses git merge-tree in the
ephemeral Actions checkout only. Never merges a GitHub PR, updates a
branch/ref, enables trading or claims untested combinations release-ready.
Heads are pinned to the 2026-11-20 snapshot; later changes invalidate audit.
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
from pathlib import Path
from typing import Any, Callable

EXPECTED_MAIN = "683bc0c272bdc8f8dd9f20fa6af15fb0b19a0be0"
PR_NUMBERS = tuple(range(100, 121))
MERGED = frozenset({105, 110, 115})
PINNED = {
    113: {
        "sha": "73e044c8c5d41a57e762b0b765569f446139cd58",
        "branch": "release-candidate/ebbot-main-pr109-offline-20261120",
    },
    117: {
        "sha": "229138e50c20f5760a89698b6f20ed66915fc89f",
        "branch": "test/ebbot-windows-electron-offline-package-20261120",
    },
    118: {
        "sha": "dbc258f885ef0437680b58514a845ed7d7004ae0",
        "branch": "feat/solana-reviewed-quality-candidate-20261120",
    },
    120: {
        "sha": "ed14387552e9fe0d35a18cc1a4945bf182702215",
        "branch": "audit/tr-fx-next-day-readonly-gate-20261120",
    },
}
PAIRS = (
    ("current_main_vs_pr113", "main", "113"),
    ("current_main_vs_pr120", "main", "120"),
    ("pr113_vs_pr120", "113", "120"),
    ("pr113_vs_pr117", "113", "117"),
    ("current_main_vs_pr118", "main", "118"),
)
HEX_SHA = re.compile(r"^[0-9a-f]{40}$")


def _raw_pr_field(pr: dict[str, Any], group: str, field: str) -> Any:
    obj = pr.get(group)
    return obj.get(field) if isinstance(obj, dict) else None


def audit_inventory(pulls: Any, main: Any) -> dict[str, Any]:
    if not isinstance(pulls, list) or not isinstance(main, dict):
        raise ValueError("pr_or_main_metadata_not_a_collection")
    selected: dict[int, dict[str, Any]] = {}
    for item in pulls:
        if not isinstance(item, dict):
            continue
        number = item.get("number")
        if type(number) is int and number in PR_NUMBERS:
            if number in selected:
                raise ValueError("duplicate_pr_metadata")
            selected[number] = item
    if set(selected) != set(PR_NUMBERS):
        raise ValueError("pr100_120_metadata_incomplete")
    main_sha = _raw_pr_field(main, "commit", "sha")
    if main_sha != EXPECTED_MAIN:
        raise ValueError("main_moved_since_pinned_audit")
    protected = main.get("protected")
    if type(protected) is not bool:
        raise ValueError("main_protection_state_unknown")

    inventory = []
    for number in PR_NUMBERS:
        item = selected[number]
        merged_at = item.get("merged_at")
        is_merged = bool(merged_at)
        state = item.get("state")
        draft = item.get("draft")
        if number in MERGED:
            if not is_merged or state != "closed":
                raise ValueError("expected_merged_pr_changed")
        elif state != "open" or draft is not True or is_merged:
            raise ValueError("draft_pr_status_changed")
        head = _raw_pr_field(item, "head", "sha")
        head_ref = _raw_pr_field(item, "head", "ref")
        base_ref = _raw_pr_field(item, "base", "ref")
        if (not isinstance(head, str) or not HEX_SHA.fullmatch(head)
                or not isinstance(base_ref, str) or not base_ref):
            raise ValueError("invalid_pr_ref_metadata")
        if number in PINNED:
            pin = PINNED[number]
            if head != pin["sha"] or head_ref != pin["branch"]:
                raise ValueError(f"pinned_pr_{number}_changed_since_audit")
        inventory.append({
            "pr": number,
            "state": "merged" if is_merged else "draft_open",
            "base": base_ref,
            "head_ref": head_ref,
            "head_sha": head,
            "targets_main": base_ref == "main",
        })
    return {
        "main_sha": main_sha,
        "main_branch_protected": protected,
        "main_unprotected_security_blocker": not protected,
        "merged_prs": sorted(MERGED),
        "open_draft_pr_count": len(PR_NUMBERS) - len(MERGED),
        "inventory": inventory,
    }


def interpret_preview(return_code: int, output: str) -> dict[str, Any]:
    """Interpret git merge-tree --write-tree --name-only conservatively."""
    if not isinstance(output, str):
        raise ValueError("invalid_git_merge_output")
    lines = output.splitlines()
    tree = lines[0].strip() if lines else None
    if tree is None or not HEX_SHA.fullmatch(tree):
        return {"status": "PREVIEW_TOOL_ERROR", "tree": None,
                "conflicts": [], "details": output[:500]}
    if return_code == 0:
        return {"status": "CLEAN_PREVIEW_ONLY", "tree": tree,
                "conflicts": [], "details": None}
    if return_code == 1:
        conflicted = []
        for line in lines[1:]:
            if not line.strip():
                break
            conflicted.append(line.strip())
        conflicted = sorted(set(conflicted))
        if conflicted:
            return {"status": "MERGE_CONFLICTS", "tree": tree,
                    "conflicts": conflicted, "details": None}
    return {"status": "PREVIEW_TOOL_ERROR", "tree": tree,
            "conflicts": [], "details": output[:500]}


def git_preview(left: str, right: str) -> dict[str, Any]:
    if not HEX_SHA.fullmatch(left) or not HEX_SHA.fullmatch(right):
        raise ValueError("invalid_commit_sha")
    try:
        run = subprocess.run(
            ["git", "merge-tree", "--write-tree", "--name-only", left, right],
            capture_output=True, text=True, check=False, timeout=120,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {"status": "PREVIEW_TOOL_ERROR", "tree": None,
                "conflicts": [], "details": type(exc).__name__}
    return interpret_preview(run.returncode, run.stdout or run.stderr)


def build_report(
    pulls: Any, main: Any,
    preview: Callable[[str, str], dict[str, Any]] = git_preview,
) -> dict[str, Any]:
    inv = audit_inventory(pulls, main)
    revisions = {"main": inv["main_sha"]}
    revisions.update({str(n): obj["sha"] for n, obj in PINNED.items()})
    outcomes = []
    for label, left, right in PAIRS:
        finding = preview(revisions[left], revisions[right])
        if finding.get("status") not in {
            "CLEAN_PREVIEW_ONLY", "MERGE_CONFLICTS", "PREVIEW_TOOL_ERROR",
        }:
            raise ValueError("unexpected_preview_status")
        outcomes.append({
            "pair": label, "left": revisions[left], "right": revisions[right],
            **finding,
        })
    conflicts = [x for x in outcomes if x["status"] == "MERGE_CONFLICTS"]
    errors = [x for x in outcomes if x["status"] == "PREVIEW_TOOL_ERROR"]
    core = {"current_main_vs_pr113", "current_main_vs_pr120", "pr113_vs_pr120"}
    clean_core = all(
        x["status"] == "CLEAN_PREVIEW_ONLY"
        for x in outcomes if x["pair"] in core
    )
    report = {
        "status": ("BLOCKED_PREVIEW_ERRORS" if errors else
                   "BLOCKED_MERGE_CONFLICTS" if conflicts else
                   "PAIRWISE_CLEAN_PREVIEW_NOT_INTEGRATED"),
        "main_sha": inv["main_sha"],
        "main_branch_protected": inv["main_branch_protected"],
        "main_unprotected_security_blocker": inv["main_unprotected_security_blocker"],
        "pr_range": [100, 120],
        "pr_count": len(PR_NUMBERS),
        "merged_prs": inv["merged_prs"],
        "open_draft_pr_count": inv["open_draft_pr_count"],
        "pr_inventory": inv["inventory"],
        "previews": outcomes,
        "conflicting_pairs": [x["pair"] for x in conflicts],
        "preview_error_pairs": [x["pair"] for x in errors],
        "core_pairwise_clean_for_ephemeral_test": clean_core and not errors,
        "three_way_merge_verified": False,
        "combined_backend_tests_executed": False,
        "combined_frontend_tests_executed": False,
        "safe_to_merge_main": False,
        "trading_enabled": False,
        "orders": 0,
        "paper_fills": 0,
        "scheduler_enabled": False,
        "network_market_data_requested": False,
    }
    json.dumps(report, allow_nan=False)
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description="PR100-120 offline read-only merge conflict preview")
    parser.add_argument("--prs", type=Path, required=True)
    parser.add_argument("--main", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    try:
        pulls = json.loads(args.prs.read_text(encoding="utf-8"))
        branch = json.loads(args.main.read_text(encoding="utf-8"))
        result = build_report(pulls, branch)
        args.out.write_text(json.dumps(result, indent=2, allow_nan=False) + "\n",
                            encoding="utf-8")
        print(json.dumps({
            "status": result["status"],
            "drafts": result["open_draft_pr_count"],
            "merged": result["merged_prs"],
            "conflicting_pairs": result["conflicting_pairs"],
            "preview_error_pairs": result["preview_error_pairs"],
            "main_protected": result["main_branch_protected"],
            "core_pairwise_clean_for_ephemeral_test":
                result["core_pairwise_clean_for_ephemeral_test"],
            "orders": 0,
        }, sort_keys=True))
        return 0
    except (OSError, ValueError, TypeError, KeyError) as exc:
        args.out.write_text(json.dumps({
            "status": "BLOCKED_METADATA_OR_IO",
            "reason": str(exc)[:150],
            "safe_to_merge_main": False,
            "orders": 0,
        }) + "\n", encoding="utf-8")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
