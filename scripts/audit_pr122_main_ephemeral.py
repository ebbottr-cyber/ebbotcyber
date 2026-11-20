"""One-off read-only snapshot of Solana anti-replay main + PR122 merge feasibility.

This audit never merges upstream PRs, pushes a branch, starts the scheduler,
touches a ledger or routes data to trading. The release gate is always false
until an independently approved rollout with protected main.
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
from pathlib import Path
from typing import Any

MAIN_SHA = "68f9d1652f81a3edf70784526d18578c772fe922"
PR122_SHA = "f73ce5d7fcea9255822239420ed61d12521e3493"
REPO = "ebbottr-cyber/ebbotcyber"
VALID_SHA = re.compile(r"^[a-f0-9]{40}$")


def validate_remote_snapshot(main: Any, pull: Any) -> dict[str, Any]:
    """Refuse drift and preserve the unfixed branch-protection warning."""
    if not isinstance(main, dict) or not isinstance(pull, dict):
        raise ValueError("invalid_git_metadata")
    main_head = main.get("commit")
    main_head = main_head.get("sha") if isinstance(main_head, dict) else None
    if main_head != MAIN_SHA:
        raise ValueError("main_moved_stop_snapshot")
    if main.get("protected") is not False:
        # Snapshot deliberately expects unprotected main, a release blocker.
        raise ValueError("main_branch_protection_state_changed_reaudit")
    head = pull.get("head")
    base = pull.get("base")
    if not isinstance(head, dict) or not isinstance(base, dict):
        raise ValueError("invalid_pr_metadata")
    if (pull.get("number") != 122 or pull.get("state") != "open"
            or pull.get("draft") is not True or pull.get("merged_at") is not None
            or head.get("sha") != PR122_SHA
            or head.get("ref") != "integration/ebbot-pr113-tr-data-safety-20261120"
            or base.get("ref") != "release-candidate/ebbot-main-pr109-offline-20261120"):
        raise ValueError("pr122_changed_or_not_a_draft")
    return {
        "main_sha": MAIN_SHA,
        "pr122_sha": PR122_SHA,
        "main_branch_protected": False,
        "main_unprotected_is_release_blocker": True,
    }


def parse_merge_tree(return_code: int, output: str) -> dict[str, Any]:
    """Fail closed on conflict, malformed tool output, and nonzero git status."""
    if not isinstance(output, str):
        raise ValueError("invalid_git_output")
    first = output.splitlines()[0].strip() if output.splitlines() else ""
    valid_tree = bool(VALID_SHA.fullmatch(first))
    if return_code == 0 and valid_tree and len(output.splitlines()) == 1:
        return {"status": "CLEAN_EPHEMERAL_TREE_PREVIEW", "tree_sha": first}
    if return_code == 1 and valid_tree:
        return {"status": "BLOCKED_GIT_CONFLICTS", "tree_sha": first}
    return {"status": "BLOCKED_GIT_MERGE_PREVIEW_ERROR", "tree_sha": None}


def git_merge_preview(main_sha: str, pr_sha: str) -> dict[str, Any]:
    for sha in (main_sha, pr_sha):
        if not isinstance(sha, str) or not VALID_SHA.fullmatch(sha):
            raise ValueError("invalid_commit_hash")
        res = subprocess.run(
            ["git", "cat-file", "-e", sha + "^{commit}"],
            check=False, capture_output=True, timeout=20,
        )
        if res.returncode != 0:
            raise ValueError("missing_verified_commit_in_local_git")
    cmd = ["git", "merge-tree", "--write-tree", "--name-only", main_sha, pr_sha]
    try:
        res = subprocess.run(
            cmd, check=False, capture_output=True, text=True, timeout=120,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise ValueError("git_merge_preview_unavailable") from exc
    return parse_merge_tree(res.returncode, res.stdout)


def build_report(main: Any, pull: Any, preview: dict[str, Any]) -> dict[str, Any]:
    provenance = validate_remote_snapshot(main, pull)
    if preview.get("status") not in {
        "CLEAN_EPHEMERAL_TREE_PREVIEW",
        "BLOCKED_GIT_CONFLICTS",
        "BLOCKED_GIT_MERGE_PREVIEW_ERROR",
    }:
        raise ValueError("unknown_merge_preview")
    clean = preview["status"] == "CLEAN_EPHEMERAL_TREE_PREVIEW"
    result = {
        **provenance,
        "status": preview["status"],
        "preview_tree_sha": preview.get("tree_sha"),
        "eligible_for_ephemeral_combined_tests": clean,
        "tests_proven_by_preview": False,
        "backend_combined_tests_passed": False,
        "frontend_combined_tests_passed": False,
        "approved_to_merge_main": False,
        "production_deployment_approved": False,
        "live_trading_enabled": False,
        "paper_trading_enabled": False,
        "scheduler_enabled": False,
        "orders": 0,
        "paper_fills": 0,
        "journal_writes": 0,
        "market_data_requests": 0,
    }
    json.dumps(result, allow_nan=False)
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="Pinned main+PR122 ephemeral merge preflight")
    parser.add_argument("--main-json", type=Path, required=True)
    parser.add_argument("--pr-json", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        remote_main = json.loads(args.main_json.read_text(encoding="utf-8"))
        remote_pr = json.loads(args.pr_json.read_text(encoding="utf-8"))
        validate_remote_snapshot(remote_main, remote_pr)
        preview = git_merge_preview(MAIN_SHA, PR122_SHA)
        audit = build_report(remote_main, remote_pr, preview)
        args.output.write_text(json.dumps(audit, sort_keys=True, indent=2,
                                          allow_nan=False) + "\n", encoding="utf-8")
        print(json.dumps(audit, sort_keys=True, allow_nan=False))
        return 0  # A blocked preview is a factual finding, not permission to test.
    except (OSError, ValueError, TypeError, KeyError, subprocess.SubprocessError) as exc:
        args.output.write_text(json.dumps({
            "status": "BLOCKED_UNVERIFIED_STATE",
            "reason": str(exc)[:160],
            "eligible_for_ephemeral_combined_tests": False,
            "approved_to_merge_main": False,
            "orders": 0,
        }) + "\n", encoding="utf-8")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
