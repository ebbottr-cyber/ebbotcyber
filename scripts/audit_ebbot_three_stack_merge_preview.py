#!/usr/bin/env python3
"""Read-only preview of pinned main + React + Windows/SQLite draft heads.

All Git operations are confined to an ephemeral CI checkout. git commit-tree
creates only an unreachable local object: it does not move branch refs.
No running backend, installers, schedules, deployments, publishing or trades.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re
import subprocess

SHA = re.compile(r"^[0-9a-f]{40}$")
SAFE_REF = re.compile(r"^[A-Za-z0-9._/-]+$")


def git(repo: Path, *args: str, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[bytes]:
    return subprocess.run(
        ["git", "-C", str(repo), *args],
        capture_output=True, check=False, env=env,
    )


def required(repo: Path, *args: str, env: dict[str, str] | None = None) -> str:
    result = git(repo, *args, env=env)
    if result.returncode:
        raise RuntimeError(f"Git {args[0]} failed, exit={result.returncode}")
    return result.stdout.decode("utf-8", errors="replace").strip()


def pinned(repo: Path, ref: str, expected: str) -> str:
    if not SAFE_REF.fullmatch(ref) or ref.startswith("-") or ".." in ref:
        raise ValueError("Unsafe Git revision")
    if not SHA.fullmatch(expected):
        raise ValueError("Invalid required pinned SHA")
    actual = required(repo, "rev-parse", "--verify", ref + "^{commit}")
    if actual != expected:
        raise RuntimeError(f"Ref moved: {ref}; fail closed instead of using stale evidence")
    return actual


def merge_tree(repo: Path, base: str, candidate: str) -> dict:
    proc = git(repo, "merge-tree", "--write-tree", "--messages", base, candidate)
    lines = proc.stdout.decode("utf-8", errors="replace").splitlines()
    tree = lines[0].strip() if lines else ""
    return {
        "status": "CLEAN_DRY_RUN" if proc.returncode == 0 and SHA.fullmatch(tree) else "REVIEW_REQUIRED",
        "exit_code": proc.returncode,
        "tree_sha": tree if SHA.fullmatch(tree) else None,
        "messages": [line.strip() for line in lines if "CONFLICT" in line][:100],
    }


def changed(repo: Path, ancestor: str, head: str) -> set[str]:
    return set(
        required(repo, "diff", "--name-only", "-z", ancestor, head).split("\x00")
    ) - {""}


def inspect(repo: Path, main_ref: str, react_ref: str, windows_ref: str,
            main_pin: str, react_pin: str, windows_pin: str) -> dict:
    main = pinned(repo, main_ref, main_pin)
    react = pinned(repo, react_ref, react_pin)
    windows = pinned(repo, windows_ref, windows_pin)

    main_react = merge_tree(repo, main, react)
    evidence = {
        "schema_version": 1,
        "mode": "pinned_three_stack_merge_tree_no_ref_updates",
        "release_status": "BLOCKED",
        "main_sha": main,
        "react_sha": react,
        "windows_sha": windows,
        "stage_1_main_plus_react": main_react,
        "stage_2_add_windows": {"status": "NOT_RUN"},
        "branch_refs_modified": False,
        "merge_or_release_performed": False,
        "real_or_paper_trading_performed": False,
        "overall_status": "REVIEW_REQUIRED",
    }
    if main_react["status"] != "CLEAN_DRY_RUN":
        return evidence
    virtual_tree = main_react["tree_sha"]
    assert virtual_tree is not None
    env = {
        **os.environ,
        "GIT_AUTHOR_NAME": "EBBot ephemeral integration audit",
        "GIT_AUTHOR_EMAIL": "audit@example.invalid",
        "GIT_COMMITTER_NAME": "EBBot ephemeral integration audit",
        "GIT_COMMITTER_EMAIL": "audit@example.invalid",
        "GIT_AUTHOR_DATE": "2000-01-01T00:00:00 +0000",
        "GIT_COMMITTER_DATE": "2000-01-01T00:00:00 +0000",
    }
    synthetic = required(
        repo, "commit-tree", virtual_tree, "-p", main,
        "-m", "ephemeral virtual main+React for merge-tree only (no refs)",
        env=env,
    )
    if not SHA.fullmatch(synthetic):
        raise RuntimeError("Ephemeral synthetic commit-tree did not return a commit SHA")
    ancestor = required(repo, "merge-base", synthetic, windows)
    synthetic_paths = changed(repo, ancestor, synthetic)
    windows_paths = changed(repo, ancestor, windows)
    stage2 = merge_tree(repo, synthetic, windows)
    evidence["stage_2_add_windows"] = {
        **stage2,
        "common_ancestor_sha": ancestor,
        "candidate_file_overlap": sorted(synthetic_paths & windows_paths)[:100],
        "candidate_file_overlap_count": len(synthetic_paths & windows_paths),
        "windows_changed_files": len(windows_paths),
        "virtual_main_react_changed_files": len(synthetic_paths),
    }
    evidence["overall_status"] = stage2["status"]
    return evidence


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", type=Path, default=Path("."))
    parser.add_argument("--main-ref", required=True)
    parser.add_argument("--react-ref", required=True)
    parser.add_argument("--windows-ref", required=True)
    parser.add_argument("--main-sha", required=True)
    parser.add_argument("--react-sha", required=True)
    parser.add_argument("--windows-sha", required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    report: dict = {
        "schema_version": 1,
        "overall_status": "REVIEW_REQUIRED_AUDIT_ERROR",
        "release_status": "BLOCKED",
    }
    try:
        report = inspect(
            args.repo, args.main_ref, args.react_ref, args.windows_ref,
            args.main_sha, args.react_sha, args.windows_sha,
        )
    except (OSError, RuntimeError, ValueError) as err:
        report["error"] = str(err)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(
        json.dumps(report, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(report, ensure_ascii=False, sort_keys=True))
    return 0 if report["overall_status"] == "CLEAN_DRY_RUN" else 1


if __name__ == "__main__":
    raise SystemExit(main())
