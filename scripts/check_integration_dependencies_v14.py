"""Read-only verification of the separate V12/V13 remediation PR dependencies.

Complements the V11 eight-PR Strategy Lab audit. Does not merge, rebase,
enable scheduling, start paper observation or trade.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys

from scripts.check_strategy_lab_stack_v11 import _fetch_pr

DEPENDENCIES = (
    (51, "fix/archived-workflow-ci-contracts-v12", "main"),
    (52, "fix/turkish-report-backend-v13", "fix/archived-workflow-ci-contracts-v12"),
)


def assess_deps(prs: list[dict]) -> dict:
    indexed = {p.get("number"): p for p in prs if isinstance(p, dict)}
    results = []
    for number, head, base in DEPENDENCIES:
        pr = indexed.get(number)
        reasons = []
        if pr is None:
            reasons.append("missing_pull_request")
        else:
            if pr.get("state") != "open" or pr.get("merged") is not False:
                reasons.append("pr_not_open_unmerged")
            if pr.get("head", {}).get("ref") != head or pr.get("base", {}).get("ref") != base:
                reasons.append("unexpected_dependency_branch")
            if pr.get("mergeable") is not True or pr.get("mergeable_state") == "dirty":
                reasons.append("conflicted_or_unknown_mergeability")
        results.append({"pr": number, "status": "BLOCKED" if reasons else "INTEGRATION_REVIEWABLE", "reasons": reasons})
    return {
        "status": "BLOCKED" if any(x["reasons"] for x in results) else "PASS",
        "dependencies": results,
        "merged": False,
        "trading_enabled": False,
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Read-only V12/V13 pull request dependency check")
    ap.add_argument("--repository", default="ebbottr-cyber/ebbotcyber")
    ap.add_argument("--fixture", help="Optional offline PR JSON list")
    args = ap.parse_args(argv)
    if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", args.repository):
        ap.error("Invalid repository")
    try:
        if args.fixture:
            with open(args.fixture, encoding="utf-8") as file:
                prs = json.load(file)
        else:
            owner, name = args.repository.split("/")
            prs = [_fetch_pr(owner, name, n, os.environ.get("GITHUB_TOKEN", "")) for n, _, _ in DEPENDENCIES]
        if not isinstance(prs, list):
            raise ValueError("Expected JSON list")
        answer = assess_deps(prs)
    except Exception as exc:
        answer = {"status": "BLOCKED", "error_type": type(exc).__name__,
                  "message": "Cannot independently verify remediation PRs",
                  "merged": False, "trading_enabled": False}
    print(json.dumps(answer, indent=2, ensure_ascii=False))
    return 0 if answer["status"] == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
