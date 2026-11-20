"""Fail-closed aggregator for EBBot's required main PR checks.

Called only by the branch's read-only pull_request CI workflow. Successful
checks do not grant release, branch protection, trading, licensing or deployment.
The caller passes the direct JSON-encoded GitHub Actions needs context, not a
comment or a previously green workflow run.
"""
from __future__ import annotations

import json
import os
import sys
from typing import Any

REQUIRED_JOBS = frozenset(("policy", "backend", "frontend", "frontend-build"))
MAX_JSON_BYTES = 16_384


def validate_required_jobs(evidence: Any) -> dict[str, Any]:
    """Never treat skipped, missing, failed, cancelled or unknown jobs as green."""
    if not isinstance(evidence, dict) or set(evidence) != REQUIRED_JOBS:
        raise ValueError("required_main_pr_job_set_missing_or_changed")
    result = {}
    for job in sorted(REQUIRED_JOBS):
        details = evidence[job]
        if not isinstance(details, dict):
            raise ValueError(f"{job}:invalid_job_result")
        status = details.get("result")
        if status not in {"success", "failure", "cancelled", "skipped"}:
            raise ValueError(f"{job}:unrecognised_job_conclusion")
        if status != "success":
            raise ValueError(f"{job}:not_success:{status}")
        result[job] = status
    return {
        "status": "ALL_REQUIRED_PR_JOBS_PASSED_NOT_RELEASE_APPROVAL",
        "jobs": result,
        "all_required_jobs_success": True,
        "approved_to_merge_main": False,
        "production_deployment_approved": False,
        "market_data_license_verified": False,
        "live_trading_enabled": False,
        "paper_trading_enabled": False,
        "scheduler_enabled": False,
        "orders": 0,
        "paper_fills": 0,
        "journal_writes": 0,
    }


def main() -> int:
    raw = os.getenv("EBBOT_REQUIRED_JOB_RESULTS_JSON", "")
    try:
        if not raw or len(raw.encode("utf-8")) > MAX_JSON_BYTES:
            raise ValueError("missing_or_oversized_github_needs_json")
        record = json.loads(
            raw, parse_constant=lambda _: (_ for _ in ()).throw(
                ValueError("nonfinite_github_needs_json")
            ),
        )
        outcome = validate_required_jobs(record)
        print(json.dumps(outcome, sort_keys=True, allow_nan=False))
        return 0
    except (TypeError, ValueError, UnicodeError) as exc:
        print(json.dumps({
            "status": "BLOCKED_REQUIRED_MAIN_PR_JOB_FAILURE",
            "reason": str(exc)[:160],
            "approved_to_merge_main": False,
            "production_deployment_approved": False,
            "orders": 0,
        }, sort_keys=True))
        return 1


if __name__ == "__main__":
    sys.exit(main())
