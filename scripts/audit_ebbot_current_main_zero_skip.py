#!/usr/bin/env python3
"""Read-only, pinned, true git merge-tree audit of current main and candidate.

Never checks out or merges into refs, never starts a trading or desktop runtime.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import subprocess

SHA = re.compile(r"^[a-f0-9]{40}$")
REF = re.compile(r"^[A-Za-z0-9._/-]+$")


def git(repo: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", "-C", str(repo), *args],
        capture_output=True, text=True, check=False,
    )


def required(repo: Path, *args: str) -> str:
    result = git(repo, *args)
    if result.returncode != 0:
        raise RuntimeError(f"Git {args[0]} failed, exit={result.returncode}")
    return result.stdout.strip()


def verify(repo: Path, ref: str, expected: str) -> str:
    if not REF.fullmatch(ref) or ref.startswith("-") or ".." in ref:
        raise ValueError("Unsafe revision")
    if not SHA.fullmatch(expected):
        raise ValueError("Invalid pinned commit")
    actual = required(repo, "rev-parse", "--verify", ref + "^{commit}")
    if actual != expected:
        raise RuntimeError("Pinned branch moved; refuse stale integration evidence")
    return actual


def paths(repo: Path, ancestor: str, commit: str) -> set[str]:
    diff = required(repo, "diff", "--name-only", "-z", ancestor, commit)
    return set(diff.split("\0")) - {""}


def inspect(repo: Path, main_ref: str, candidate_ref: str,
            main_sha: str, candidate_sha: str) -> dict:
    main = verify(repo, main_ref, main_sha)
    candidate = verify(repo, candidate_ref, candidate_sha)
    ancestor = required(repo, "merge-base", main, candidate)
    base_paths, candidate_paths = paths(repo, ancestor, main), paths(repo, ancestor, candidate)
    result = git(repo, "merge-tree", "--write-tree", "--messages", main, candidate)
    lines = result.stdout.splitlines()
    tree = lines[0].strip() if lines else ""
    is_clean = result.returncode == 0 and bool(SHA.fullmatch(tree))
    return {
        "schema_version": 1,
        "mode": "read_only_pinned_merge_tree",
        "status": "CLEAN_DRY_RUN" if is_clean else "REVIEW_REQUIRED",
        "main_sha": main,
        "candidate_sha": candidate,
        "merge_base_sha": ancestor,
        "main_changed_paths": len(base_paths),
        "candidate_changed_paths": len(candidate_paths),
        "overlap_paths": sorted(base_paths & candidate_paths),
        "overlap_count": len(base_paths & candidate_paths),
        "merge_exit_code": result.returncode,
        "tree_sha": tree if SHA.fullmatch(tree) else None,
        "conflict_messages": [s.strip() for s in lines if "CONFLICT" in s][:120],
        "refs_modified": False,
        "main_merged": False,
        "release_status": "BLOCKED",
        "trading_or_scheduler_started": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", type=Path, default=Path("."))
    parser.add_argument("--main-ref", required=True)
    parser.add_argument("--candidate-ref", required=True)
    parser.add_argument("--main-sha", required=True)
    parser.add_argument("--candidate-sha", required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    report: dict = {"status": "REVIEW_REQUIRED_ERROR", "release_status": "BLOCKED"}
    try:
        report = inspect(
            args.repo, args.main_ref, args.candidate_ref, args.main_sha, args.candidate_sha,
        )
    except (OSError, RuntimeError, ValueError) as exc:
        report["error"] = str(exc)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, sort_keys=True))
    return 0 if report["status"] == "CLEAN_DRY_RUN" else 1


if __name__ == "__main__":
    raise SystemExit(main())
