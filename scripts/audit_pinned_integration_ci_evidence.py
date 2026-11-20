"""Verify successful *actual* detached main+PR122 CI jobs, without release approval.

Only canonical GitHub API JSONs read by a one-off Actions workflow. Green from
another PR, skipped tests, incomplete runs, a stale commit, duplicate jobs and
a changed PR are not equivalent to this exact integration's evidence.
A successfully verified run is still NOT a release, deploy or trade approval.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from scripts.audit_main_release_protection import (
    EXPECTED_MAIN_SHA, EXPECTED_PR130_SHA, REPOSITORY, load_json,
)

RUN_ID = 44813551015
RUN_NAME = "EBBot anti-replay Solana main plus PR122 full offline verification (NO merge)"
HEAD_BRANCH = "audit/ebbot-main-pr122-solana-replay-full-20261120"
PR122_SHA = "f73ce5d7fcea9255822239420ed61d12521e3493"
REQUIRED_JOB_STEPS = {
    "Pin GitHub main and PR122, no-commit merge-tree, NO release": (
        "Strict offline metadata and git preview regression tests",
        "Refuse moving branches, then compute real Git merge-tree",
    ),
    "FULL React/PWA on actual ephemeral main plus PR122 joined code": (
        "Materialize detached LOCAL joined React tree (never push)",
        "Full React Vitest",
        "React ESLint",
        "Production TypeScript and Vite build",
        "Built asset PWA smoke tests",
    ),
    "FULL backend on actual ephemeral main plus PR122 joined code": (
        "Materialize detached LOCAL merged tree, verify exact two parents",
        "Offline critical joint portfolio, Solana and TR source guards",
        "Full backend regression on actual joined code, no network-marked tests",
    ),
}


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def _repository_name(value: Any) -> str | None:
    return value.get("full_name") if isinstance(value, dict) else None


def assess_integration_ci(
    workflow_run: Any,
    workflow_jobs: Any,
    pr130: Any,
    pr122: Any,
    branch_main: Any,
) -> dict[str, Any]:
    _require(all(isinstance(x, dict) for x in
                 (workflow_run, workflow_jobs, pr130, pr122, branch_main)),
             "invalid_github_evidence")
    _require(workflow_run.get("id") == RUN_ID
             and type(workflow_run.get("id")) is int
             and workflow_run.get("name") == RUN_NAME
             and workflow_run.get("head_sha") == EXPECTED_PR130_SHA
             and workflow_run.get("head_branch") == HEAD_BRANCH
             and _repository_name(workflow_run.get("repository")) == REPOSITORY
             and workflow_run.get("event") == "push"
             and workflow_run.get("status") == "completed"
             and workflow_run.get("conclusion") == "success"
             and type(workflow_run.get("run_attempt")) is int
             and workflow_run["run_attempt"] == 1,
             "wrong_or_incomplete_integration_workflow")
    _require(pr130.get("number") == 130
             and type(pr130.get("number")) is int
             and pr130.get("state") == "open"
             and pr130.get("draft") is True
             and pr130.get("merged_at") is None
             and isinstance(pr130.get("head"), dict)
             and pr130["head"].get("sha") == EXPECTED_PR130_SHA
             and pr130["head"].get("ref") == HEAD_BRANCH
             and _repository_name(pr130["head"].get("repo")) == REPOSITORY
             and isinstance(pr130.get("base"), dict)
             and pr130["base"].get("ref")
             == "audit/ebbot-pr122-main-full-offline-20261120",
             "pr130_changed_since_integration")
    _require(pr122.get("number") == 122
             and type(pr122.get("number")) is int
             and pr122.get("state") == "open"
             and pr122.get("draft") is True
             and pr122.get("merged_at") is None
             and isinstance(pr122.get("head"), dict)
             and pr122["head"].get("sha") == PR122_SHA
             and pr122["head"].get("ref") ==
             "integration/ebbot-pr113-tr-data-safety-20261120"
             and _repository_name(pr122["head"].get("repo")) == REPOSITORY,
             "pr122_moved_or_not_draft")
    sha_obj = branch_main.get("commit")
    _require(branch_main.get("name") == "main"
             and isinstance(sha_obj, dict)
             and sha_obj.get("sha") == EXPECTED_MAIN_SHA
             and branch_main.get("protected") is False,
             "main_commit_or_protection_changed")
    jobs = workflow_jobs.get("jobs")
    _require(type(jobs) is list and len(jobs) == len(REQUIRED_JOB_STEPS),
             "integration_job_count_mismatch")
    seen_names: set[str] = set()
    seen_ids: set[int] = set()
    evidence_jobs: list[dict[str, Any]] = []
    for job in jobs:
        _require(isinstance(job, dict), "invalid_integration_job")
        name, job_id = job.get("name"), job.get("id")
        _require(type(name) is str and name in REQUIRED_JOB_STEPS
                 and name not in seen_names
                 and type(job_id) is int and job_id > 0
                 and job_id not in seen_ids
                 and job.get("run_id") == RUN_ID
                 and type(job.get("run_id")) is int
                 and job.get("status") == "completed"
                 and job.get("conclusion") == "success",
                 "skipped_failed_duplicate_or_unrelated_job")
        if job.get("head_sha") is not None:
            _require(job["head_sha"] == EXPECTED_PR130_SHA,
                     "job_not_at_pinned_pr130_commit")
        steps = job.get("steps")
        _require(isinstance(steps, list) and len(steps) >= 2,
                 "missing_job_step_evidence")
        for required in REQUIRED_JOB_STEPS[name]:
            matching = [step for step in steps if
                        isinstance(step, dict) and step.get("name") == required]
            _require(len(matching) == 1
                     and matching[0].get("status") == "completed"
                     and matching[0].get("conclusion") == "success",
                     "required_integration_step_missing_or_not_successful")
        seen_names.add(name)
        seen_ids.add(job_id)
        evidence_jobs.append({
            "name": name,
            "job_id": job_id,
            "conclusion": "success",
            "required_steps_verified": len(REQUIRED_JOB_STEPS[name]),
        })
    _require(seen_names == set(REQUIRED_JOB_STEPS), "missing_required_jobs")

    result = {
        "status": "PINNED_INTEGRATION_TESTS_VERIFIED_RELEASE_STILL_BLOCKED",
        "run_id": RUN_ID,
        "run_head_sha": EXPECTED_PR130_SHA,
        "main_sha_under_test": EXPECTED_MAIN_SHA,
        "pr122_sha_under_test": PR122_SHA,
        "verified_job_count": len(evidence_jobs),
        "jobs": sorted(evidence_jobs, key=lambda item: item["name"]),
        "all_required_integration_jobs_verified": True,
        "main_branch_protected": False,
        "release_blockers": [
            "main_unprotected",
            "effective_required_reviews_and_checks_unverified",
            "market_data_license_not_verified",
            "long_term_multi_day_market_data_not_proven",
            "windows_installer_release_not_proven",
        ],
        "production_deployment_approved": False,
        "approved_to_merge_main": False,
        "paper_trading_enabled": False,
        "live_trading_enabled": False,
        "scheduler_enabled": False,
        "prices_executable": False,
        "orders": 0,
        "paper_fills": 0,
        "journal_writes": 0,
    }
    json.dumps(result, allow_nan=False)
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="Pinned EBBot 3-job CI evidence; never release")
    parser.add_argument("--run", type=Path, required=True)
    parser.add_argument("--jobs", type=Path, required=True)
    parser.add_argument("--pr130", type=Path, required=True)
    parser.add_argument("--pr122", type=Path, required=True)
    parser.add_argument("--main", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        result = assess_integration_ci(
            load_json(args.run), load_json(args.jobs), load_json(args.pr130),
            load_json(args.pr122), load_json(args.main),
        )
        args.output.write_text(json.dumps(result, indent=2, sort_keys=True,
                                          allow_nan=False) + "\n", encoding="utf-8")
        print(json.dumps({
            "status": result["status"],
            "run_id": result["run_id"],
            "verified_jobs": result["verified_job_count"],
            "release_approved": False,
            "orders": 0,
        }, sort_keys=True))
        return 0
    except (OSError, ValueError, KeyError, TypeError) as exc:
        failure = {
            "status": "BLOCKED_UNVERIFIED_INTEGRATION_CI",
            "reason": str(exc)[:160],
            "approved_to_merge_main": False,
            "production_deployment_approved": False,
            "orders": 0,
        }
        args.output.write_text(json.dumps(failure, allow_nan=False) + "\n",
                               encoding="utf-8")
        print(json.dumps(failure, sort_keys=True))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
