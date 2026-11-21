"""V11 read-only, fail-closed GitHub PR dependency audit.

No merges, review-state changes, scheduling, broker access or repository writes.
This audit verifies branch relationships and GitHub's current mergeability;
it does NOT replace full CI, a review, visual smoke or live-paper proof.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

# All feature PRs stay drafts until their individual checks and manual review.
# Head branch, base branch: exact names prevent 'looks green' on wrong bases.
STACK = (
    (30, "feat/random-timing-benchmark-v1", "main"),
    (32, "feat/rotation-random-benchmark-bridge-v1", "feat/random-timing-benchmark-v1"),
    (34, "feat/strategy-success-lab-v1", "feat/rotation-random-benchmark-bridge-v1"),
    (37, "fix/turkish-ui-type-coverage-v1", "feat/strategy-success-lab-v1"),
    (42, "feat/provider-consistency-v7", "fix/turkish-ui-type-coverage-v1"),
    (44, "feat/strategy-lab-walk-forward-v8", "feat/provider-consistency-v7"),
    (46, "feat/strategy-lab-prospective-paper-v9", "feat/strategy-lab-walk-forward-v8"),
    (48, "feat/strategy-lab-paper-ops-v10", "feat/strategy-lab-prospective-paper-v9"),
)


def assess_pr_stack(prs: list[dict], *, require_ready: bool = False) -> dict:
    """Build explicit per-PR blockers; missing/unknown states never silently pass."""
    provided = {p.get("number"): p for p in prs if isinstance(p, dict)}
    checks: list[dict] = []
    for number, head, base in STACK:
        p = provided.get(number)
        reasons: list[str] = []
        if p is None:
            checks.append({"pr": number, "status": "BLOCKED",
                           "reasons": ["pull_request_missing"]})
            continue
        if p.get("state") != "open" or p.get("merged") is not False:
            reasons.append("pr_not_open_unmerged")
        if p.get("head", {}).get("ref") != head:
            reasons.append("unexpected_head_branch")
        if p.get("base", {}).get("ref") != base:
            reasons.append("unexpected_base_branch")
        if p.get("mergeable") is False or p.get("mergeable_state") == "dirty":
            reasons.append("merge_conflict")
        elif p.get("mergeable") is None:
            reasons.append("mergeability_unknown")
        if require_ready:
            if p.get("draft") is not False:
                reasons.append("draft_not_reviewed")
            if p.get("mergeable_state") != "clean":
                reasons.append("not_clean_for_release")
        checks.append({
            "pr": number,
            "status": "BLOCKED" if reasons else "INTEGRATION_READY",
            "reasons": reasons,
            "draft": p.get("draft"),
            "mergeable_state": p.get("mergeable_state"),
        })
    blocked = [item["pr"] for item in checks if item["status"] == "BLOCKED"]
    return {
        "status": "BLOCKED" if blocked else "PASS",
        "mode": "release" if require_ready else "integration",
        "blocked_prs": blocked,
        "checks": checks,
        "merge_performed": False,
        "trading_enabled": False,
    }


def _fetch_pr(owner: str, repo: str, number: int, token: str) -> dict:
    url = f"https://api.github.com/repos/{owner}/{repo}/pulls/{number}"
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "EBBot-V11-ReadOnly-Release-Audit",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = Request(url, headers=headers, method="GET")
    with urlopen(req, timeout=15) as response:
        return json.load(response)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Read-only audit for EBBot's stacked Strategy Lab PRs")
    ap.add_argument("--repository", default="ebbottr-cyber/ebbotcyber")
    ap.add_argument("--release", action="store_true",
                    help="Also require every dependency PR to be ready for review and clean")
    ap.add_argument("--fixture", help="Offline JSON list of PR REST responses (for testing)")
    args = ap.parse_args(argv)
    if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", args.repository):
        ap.error("invalid repository name")
    try:
        if args.fixture:
            with open(args.fixture, encoding="utf-8") as file:
                prs = json.load(file)
        else:
            owner, repo = args.repository.split("/")
            token = os.environ.get("GITHUB_TOKEN", "")
            prs = [_fetch_pr(owner, repo, n, token) for n, _, _ in STACK]
        if not isinstance(prs, list):
            raise ValueError("PR response must be a list")
        result = assess_pr_stack(prs, require_ready=args.release)
    except (OSError, ValueError, KeyError, URLError, HTTPError) as exc:
        result = {
            "status": "BLOCKED",
            "error_type": type(exc).__name__,
            "message": "PR status could not be verified. Do not merge.",
            "merge_performed": False,
            "trading_enabled": False,
        }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["status"] == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
