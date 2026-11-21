"""GET-only, fail-closed advisory audit of main branch protection and independent PR review."""
from __future__ import annotations
import argparse
import fnmatch
import json
import os
import re
import sys
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

REQUIRED = "EBBot required gate / all offline acceptance checks"


def matches_main(conditions: dict) -> bool:
    refs = conditions.get("ref_name") or {}
    def matches(p: str) -> bool:
        return p in ("~DEFAULT_BRANCH", "~ALL") or fnmatch.fnmatchcase("refs/heads/main", p)
    return any(matches(p) for p in refs.get("include") or []) and not any(
        matches(p) for p in refs.get("exclude") or []
    )


def inspect(branch: dict, pr: dict, reviews: list[dict],
            rulesets: list[dict], sha: str) -> dict:
    blockers: list[str] = []
    if branch.get("protected") is not True:
        blockers.append("MAIN_NOT_PROTECTED")
    if pr.get("state") != "open" or pr.get("draft") is not False:
        blockers.append("PR_NOT_READY")
    if (pr.get("base") or {}).get("ref") != "main":
        blockers.append("BASE_NOT_MAIN")
    head = (pr.get("head") or {}).get("sha")
    if head != sha:
        blockers.append("PR_HEAD_DRIFT")
    active = [
        rs for rs in rulesets
        if rs.get("target") == "branch" and rs.get("enforcement") == "active"
        and matches_main(rs.get("conditions") or {})
    ]
    if not active:
        blockers.append("ACTIVE_MAIN_RULESET_MISSING")
    approval = stale = status = force = deletion = False
    for rs in active:
        if any(actor.get("bypass_mode") == "always"
               for actor in rs.get("bypass_actors") or []):
            blockers.append("UNRESTRICTED_BYPASS")
        for rule in rs.get("rules") or []:
            params = rule.get("parameters") or {}
            kind = rule.get("type")
            if kind == "pull_request" and params.get("required_approving_review_count", 0) >= 1:
                approval = True
                stale |= bool(params.get("dismiss_stale_reviews_on_push")
                              or params.get("require_last_push_approval"))
            elif kind == "required_status_checks":
                checks = [item.get("context") for item in
                          params.get("required_status_checks") or [] if isinstance(item, dict)]
                status |= REQUIRED in checks and bool(params.get("strict_required_status_checks_policy"))
            elif kind == "non_fast_forward":
                force = True
            elif kind == "deletion":
                deletion = True
    for ok, code in (
        (approval, "PULL_REQUEST_APPROVAL_RULE_MISSING"),
        (stale, "STALE_APPROVAL_GUARD_MISSING"),
        (status, "STRICT_REQUIRED_CHECK_MISSING"),
        (force, "FORCE_PUSH_PROTECTION_MISSING"),
        (deletion, "DELETE_PROTECTION_MISSING"),
    ):
        if not ok:
            blockers.append(code)
    owner = ((pr.get("user") or {}).get("login") or "").casefold()
    decisions: dict[str, dict] = {}
    for rev in reviews:
        user = ((rev.get("user") or {}).get("login") or "").casefold()
        if user and rev.get("state") in ("APPROVED", "CHANGES_REQUESTED", "DISMISSED"):
            decisions[user] = rev
    valid_approvals = [
        u for u, rev in decisions.items()
        if u != owner and rev.get("state") == "APPROVED" and rev.get("commit_id") == sha
    ]
    if not valid_approvals:
        blockers.append("INDEPENDENT_CURRENT_SHA_APPROVAL_MISSING")
    return {
        "schema_version": 1,
        "mode": "advisory_get_only",
        "status": "BLOCKED" if blockers else "GOVERNANCE_PRECHECK_PASSED",
        "blockers": sorted(set(blockers)),
        "pr_number": pr.get("number"),
        "expected_sha": sha,
        "observed_sha": head,
        "main_protected": bool(branch.get("protected")),
        "active_main_rulesets": len(active),
        "independent_current_sha_approvals": len(valid_approvals),
        "required_check": REQUIRED,
        "main_merged": False,
        "release_authorized": False,
        "trading_authorized": False,
    }


def github_get(repo: str, resource: str, token: str):
    host = os.environ.get("GITHUB_API_URL", "https://api.github.com").rstrip("/")
    request = Request(f"{host}/repos/{repo}/{resource}", method="GET", headers={
        "Accept": "application/vnd.github+json",
        "Authorization": f"Bearer {token}",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "EBBot-governance-preflight",
    })
    with urlopen(request, timeout=15) as response:
        return json.load(response)


def live(repo: str, number: int, sha: str, token: str) -> dict:
    branch = github_get(repo, "branches/main", token)
    pr = github_get(repo, f"pulls/{number}", token)
    reviews = github_get(repo, f"pulls/{number}/reviews?per_page=100", token)
    summaries = github_get(repo, "rulesets?includes_parents=true&per_page=100", token)
    # GitHub returns only summary metadata from list; fetch complete rules by ID.
    rulesets = [github_get(repo, f"rulesets/{rs['id']}", token) for rs in summaries]
    return inspect(branch, pr, reviews, rulesets, sha)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", required=True)
    parser.add_argument("--pr-number", required=True, type=int)
    parser.add_argument("--head-sha", required=True)
    parser.add_argument("--report", required=True, type=Path)
    args = parser.parse_args()
    report = {
        "mode": "advisory_get_only",
        "status": "BLOCKED",
        "blockers": ["GITHUB_READ_ERROR"],
        "main_merged": False,
        "release_authorized": False,
        "trading_authorized": False,
    }
    try:
        if (not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", args.repo)
            or not re.fullmatch(r"[a-f0-9]{40}", args.head_sha)
            or args.pr_number < 1):
            raise ValueError("invalid repo, pull request number or head SHA")
        token = os.environ.get("GITHUB_TOKEN", "")
        if not token:
            raise ValueError("missing read-only GitHub token")
        report = live(args.repo, args.pr_number, args.head_sha, token)
    except (ValueError, TypeError, KeyError, HTTPError, URLError, TimeoutError, OSError) as error:
        report["error_type"] = type(error).__name__
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, sort_keys=True))
    return 0 if report["status"] == "GOVERNANCE_PRECHECK_PASSED" else 1


if __name__ == "__main__":
    sys.exit(main())
