#!/usr/bin/env python3
"""Fail-closed, read-only PR #178 CI provenance and release-blocker evidence.

This parser NEVER approves release; all external data comes from GitHub API
response JSON retrieved by a read-only workflow. It cannot push, sign, deploy,
install, update the main branch or start paper/live trading.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

PINNED_MAIN = "885d4ff9a3c01d467853febb5f28303ff93638f2"
PINNED_MERGE = "9ac204944df962f1043296561f7907d42eea080c"
RUNS = {
    "react": (
        44887061797,
        "EBBot Windows React two-sided conflict candidate full regression (NO trades)",
        {
            "Thirty-five original and repaired UI suites",
            "Entire React Vitest regression (never hide failures)",
            "Independent ESLint and production TypeScript build",
        },
    ),
    "windows": (
        44887061763,
        "EBBot Windows Electron OFFLINE packaging verification (no release)",
        {
            "Desktop unit tests + fail-closed release audit",
            "Actual PyInstaller backend + NSIS Electron (NO publish or installer execution)",
        },
    ),
    "backend": (
        44887061769,
        "EBBot combined draft full offline backend regression (NO release or trades)",
        {
            "All offline-marked backend tests against real merged draft",
            "Fail closed if backend regression fails; release always BLOCKED",
        },
    ),
}
MANUAL_BLOCKERS = (
    "main_branch_protection_required",
    "independent_codesigning_certificate_ownership_required",
    "actual_windows_signing_and_smartscreen_not_verified",
    "real_device_installer_upgrade_uninstall_not_verified",
    "user_sqlite_backup_and_migration_not_verified",
    "third_party_licenses_and_distribution_review_pending",
    "two_existing_skipped_react_tests_require_separate_review",
    "no_release_authorization",
)


def evaluate(inputs: dict) -> dict:
    """Do not accept a green result from a different commit, job or PR."""
    blockers: list[str] = []
    main = inputs.get("main", {})
    pr = inputs.get("pull_request", {})
    commit = inputs.get("commit", {})
    reports = inputs.get("workflows", {})

    main_sha = (main.get("commit") or {}).get("sha")
    branch_protected = main.get("protected") is True
    if main_sha != PINNED_MAIN:
        blockers.append("main_commit_drift")
    if not branch_protected:
        blockers.append("main_branch_unprotected")

    head = (pr.get("head") or {}).get("sha")
    base = (pr.get("base") or {}).get("ref")
    if pr.get("number") != 178 or head != PINNED_MERGE or base != "main":
        blockers.append("pr178_head_or_base_drift")
    if pr.get("draft") is not True or pr.get("merged") is not False:
        blockers.append("pr178_no_longer_safe_draft")

    parents = [item.get("sha") for item in commit.get("parents", [])]
    if parents != [
        "643c7105fb1856721c1d5cd8c559d75ba4af3054",
        PINNED_MAIN,
    ]:
        blockers.append("true_two_parent_merge_provenance_missing")
    if commit.get("sha") != PINNED_MERGE:
        blockers.append("merge_commit_sha_mismatch")

    outcomes = {}
    for label, (expected_id, expected_name, required_names) in RUNS.items():
        item = reports.get(label) or {}
        run = item.get("run") or {}
        jobs_data = item.get("jobs") or {}
        jobs = jobs_data.get("jobs") or []
        received_names = [job.get("name") for job in jobs]
        failures = []
        if run.get("id") != expected_id:
            failures.append("run_id_mismatch")
        if run.get("head_sha") != PINNED_MERGE:
            failures.append("wrong_commit")
        if run.get("name") != expected_name:
            failures.append("wrong_workflow")
        if run.get("status") != "completed" or run.get("conclusion") != "success":
            failures.append("run_not_successful")
        if jobs_data.get("total_count") != len(jobs):
            failures.append("incomplete_job_page")
        if len(received_names) != len(set(received_names)):
            failures.append("duplicate_job_names")
        if set(received_names) != required_names:
            failures.append("unexpected_or_missing_jobs")
        for job in jobs:
            if job.get("status") != "completed" or job.get("conclusion") != "success":
                failures.append("job_not_successful:" + str(job.get("name", "unknown")))
        if failures:
            blockers.extend(label + ":" + problem for problem in failures)
        outcomes[label] = {
            "run_id": expected_id,
            "status": "PASS" if not failures else "PENDING_OR_FAILED",
            "details": failures,
            "job_count": len(jobs),
            "source_commit": run.get("head_sha"),
        }

    return {
        "schema_version": 1,
        "status": "BLOCKED",
        "ci_status": "ALL_EVIDENCE_VALIDATED" if not blockers or blockers == ["main_branch_unprotected"] else "INCOMPLETE_OR_UNTRUSTED",
        "release_ready": False,
        "pr178_head": head,
        "main_head": main_sha,
        "main_branch_protected": branch_protected,
        "ci_workflows": outcomes,
        "technical_or_provenance_blockers": blockers,
        "manual_release_blockers": list(MANUAL_BLOCKERS),
        "react_skipped_test_count_from_last_full_result": 2,
        "note": "Read-only GitHub metadata. Even all-green tests do not authorize release, merge or live/paper trading.",
        "remote_refs_modified": False,
        "installer_or_orders_executed": False,
    }


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--evidence", type=Path, required=True)
    p.add_argument("--report", type=Path, required=True)
    args = p.parse_args()
    report = {
        "schema_version": 1,
        "status": "BLOCKED",
        "ci_status": "INCOMPLETE_OR_UNTRUSTED",
        "release_ready": False,
        "technical_or_provenance_blockers": ["audit_error"],
    }
    try:
        inputs = json.loads(args.evidence.read_text(encoding="utf-8"))
        report = evaluate(inputs)
    except (OSError, ValueError, TypeError, AttributeError) as exc:
        report["error"] = type(exc).__name__ + ": " + str(exc)[:300]
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, sort_keys=True))
    # This is an explicit RELEASE gate, not a CI readiness pass: always blocked.
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
