"""One-off, fail-closed EBBot main branch release protection audit.

Read-only GitHub API JSON is supplied by Actions. This script does not modify
repository settings, merge PRs, deploy, trade, write portfolio events, start
schedules or make provider requests. The GitHub installation cannot read the
protected-branch administration details (403), therefore NO combination of
public metadata from this script can authorize a release.
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

REPOSITORY = "ebbottr-cyber/ebbotcyber"
EXPECTED_MAIN_SHA = "68f9d1652f81a3edf70784526d18578c772fe922"
EXPECTED_PR130_SHA = "f5c6dbe9a201d7f3a7df94b600697f869514c70c"
HEX40 = re.compile(r"^[0-9a-f]{40}$")
MAX_BYTES = 500_000


def load_json(path: Path) -> Any:
    if not path.is_file() or path.is_symlink() or path.stat().st_size > MAX_BYTES:
        raise ValueError("missing_or_oversized_evidence")
    return json.loads(
        path.read_text(encoding="utf-8"),
        parse_constant=lambda _: (_ for _ in ()).throw(
            ValueError("nonfinite_json_evidence")
        ),
    )


def assess_main_release_protection(
    repository: Any, branch: Any, rulesets: Any, pr130: Any,
) -> dict[str, Any]:
    """Do NOT infer required reviews/checks from a boolean or a ruleset title."""
    if any(not isinstance(x, dict) for x in (repository, branch, pr130)):
        raise ValueError("invalid_repository_branch_or_pull_metadata")
    if not isinstance(rulesets, list) or len(rulesets) > 200:
        raise ValueError("invalid_ruleset_metadata")
    if (repository.get("full_name") != REPOSITORY
            or repository.get("default_branch") != "main"
            or repository.get("private") is not False
            or branch.get("name") != "main"):
        raise ValueError("repository_or_main_mismatch")
    if type(branch.get("protected")) is not bool:
        raise ValueError("unknown_main_protection_state")
    commit = branch.get("commit")
    sha = commit.get("sha") if isinstance(commit, dict) else None
    if not isinstance(sha, str) or not HEX40.fullmatch(sha):
        raise ValueError("invalid_main_commit_identity")
    head = pr130.get("head")
    base = pr130.get("base")
    if (pr130.get("number") != 130
            or not isinstance(head, dict) or not isinstance(base, dict)
            or head.get("repo", {}).get("full_name") != REPOSITORY
            or head.get("ref") != "audit/ebbot-main-pr122-solana-replay-full-20261120"
            or pr130.get("state") != "open"
            or pr130.get("draft") is not True
            or pr130.get("merged_at") is not None):
        raise ValueError("expected_pr130_draft_state_missing")
    pr_head = head.get("sha")
    if not isinstance(pr_head, str) or not HEX40.fullmatch(pr_head):
        raise ValueError("invalid_pr130_head")
    if base.get("ref") != "audit/ebbot-pr122-main-full-offline-20261120":
        raise ValueError("pr130_base_changed")

    active_ids = []
    for rule in rulesets:
        if not isinstance(rule, dict):
            raise ValueError("invalid_ruleset_item")
        enforcement = rule.get("enforcement")
        rule_id = rule.get("id")
        if enforcement not in {"active", "evaluate", "disabled"}:
            raise ValueError("unknown_ruleset_enforcement")
        if type(rule_id) is not int or rule_id <= 0:
            raise ValueError("invalid_ruleset_identifier")
        if enforcement == "active":
            active_ids.append(rule_id)

    blockers = []
    if sha != EXPECTED_MAIN_SHA:
        blockers.append("main_commit_moved_since_review")
    if pr_head != EXPECTED_PR130_SHA:
        blockers.append("pr130_head_moved_since_review")
    if branch["protected"] is False:
        blockers.append("main_reports_unprotected")
    if not active_ids:
        blockers.append("no_active_repository_rulesets_reported")
    # REST branch.protected and top-level ruleset summaries cannot prove whether
    # code owners, reviews, passing checks, bypass actors and deletion/force-push
    # policies actually cover this branch. Admin verification is indispensable.
    blockers.append("required_reviews_checks_and_bypass_policy_not_verified")
    blockers.append("market_data_license_and_full_release_authorization_not_verified")

    result = {
        "status": (
            "BLOCKED_PINNED_SOURCE_MOVED"
            if sha != EXPECTED_MAIN_SHA or pr_head != EXPECTED_PR130_SHA
            else "BLOCKED_MAIN_UNPROTECTED"
            if branch["protected"] is False
            else "BLOCKED_ADMIN_POLICY_VERIFICATION_REQUIRED"
        ),
        "repository": REPOSITORY,
        "main_sha_observed": sha,
        "main_sha_expected": EXPECTED_MAIN_SHA,
        "pr130_sha_observed": pr_head,
        "pr130_sha_expected": EXPECTED_PR130_SHA,
        "main_protected_public_metadata": branch["protected"],
        "repository_rulesets_reported": len(rulesets),
        "active_rulesets_reported": len(active_ids),
        "active_ruleset_ids": sorted(set(active_ids)),
        "applies_to_main_proven": False,
        "requires_review_and_checks_proven": False,
        "force_pushes_blocked_proven": False,
        "deletions_blocked_proven": False,
        "admin_bypass_limited_proven": False,
        "github_admin_controls_verified": False,
        "release_blockers": blockers,
        "requires_human_admin_configuration": True,
        "approved_to_merge_main": False,
        "production_deployment_approved": False,
        "market_data_execution_rights_verified": False,
        "trading_enabled": False,
        "paper_trading_enabled": False,
        "live_trading_enabled": False,
        "scheduler_enabled": False,
        "orders": 0,
        "paper_fills": 0,
        "journal_writes": 0,
    }
    json.dumps(result, allow_nan=False)
    return result


def main() -> int:
    p = argparse.ArgumentParser(description="Read-only GitHub main release-policy audit")
    p.add_argument("--repository", type=Path, required=True)
    p.add_argument("--branch", type=Path, required=True)
    p.add_argument("--rulesets", type=Path, required=True)
    p.add_argument("--pr130", type=Path, required=True)
    p.add_argument("--out", type=Path, required=True)
    args = p.parse_args()
    try:
        result = assess_main_release_protection(
            load_json(args.repository), load_json(args.branch),
            load_json(args.rulesets), load_json(args.pr130),
        )
        args.out.write_text(
            json.dumps(result, indent=2, sort_keys=True, allow_nan=False) + "\n",
            encoding="utf-8",
        )
        print(json.dumps({
            "status": result["status"],
            "main_protected": result["main_protected_public_metadata"],
            "active_rulesets": result["active_rulesets_reported"],
            "release_blockers": result["release_blockers"],
            "approved_to_merge_main": False,
            "orders": 0,
        }, sort_keys=True))
        return 0  # Successfully reported a BLOCKED review; not release success.
    except (OSError, ValueError, TypeError, KeyError) as exc:
        args.out.write_text(json.dumps({
            "status": "BLOCKED_INVALID_SECURITY_EVIDENCE",
            "reason": str(exc)[:150],
            "approved_to_merge_main": False,
            "production_deployment_approved": False,
            "orders": 0,
        }, allow_nan=False) + "\n", encoding="utf-8")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
