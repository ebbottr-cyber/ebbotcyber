#!/usr/bin/env python3
"""Fail-closed, ref-preserving Git three-way preview for EBBot React integration.

This script only reads pinned branch commits, creates an unreachable local Git
merge-tree object, and optionally extracts that tree to a temporary directory.
It never merges/pushes a branch, releases a build, or places an order.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import subprocess

SHA = re.compile(r"^[0-9a-f]{40}$")


def git(repo: Path, *args: str) -> subprocess.CompletedProcess[bytes]:
    return subprocess.run(
        ["git", "-C", str(repo), *args], capture_output=True, check=False,
    )


def require_git(repo: Path, *args: str) -> bytes:
    result = git(repo, *args)
    if result.returncode:
        raise RuntimeError(f"Git {args[0]} failed (exit {result.returncode})")
    return result.stdout.strip()


def inspect(repo: Path, base: str, candidate: str, expected_base: str,
            expected_candidate: str, extract_dir: Path) -> dict:
    for value in (base, candidate):
        if not re.fullmatch(r"[A-Za-z0-9._/-]+", value) or ".." in value or value.startswith("-"):
            raise ValueError("Invalid revision")
    for sha in (expected_base, expected_candidate):
        if not SHA.fullmatch(sha):
            raise ValueError("Expected a pinned 40-character commit SHA")

    base_sha = require_git(repo, "rev-parse", "--verify", base + "^{commit}").decode()
    candidate_sha = require_git(repo, "rev-parse", "--verify", candidate + "^{commit}").decode()
    if base_sha != expected_base or candidate_sha != expected_candidate:
        raise RuntimeError(
            "Pinned commit moved; do not interpret stale merge-preview results as current"
        )
    ancestor = require_git(repo, "merge-base", base_sha, candidate_sha).decode()
    base_paths = set(require_git(repo, "diff", "--name-only", "-z", ancestor, base_sha)
                     .decode("utf-8").split("\0")) - {""}
    candidate_paths = set(require_git(repo, "diff", "--name-only", "-z", ancestor, candidate_sha)
                          .decode("utf-8").split("\0")) - {""}

    result = git(repo, "merge-tree", "--write-tree", "--messages", base_sha, candidate_sha)
    lines = result.stdout.decode("utf-8", errors="replace").splitlines()
    tree = lines[0].strip() if lines else ""
    clean = result.returncode == 0 and bool(SHA.fullmatch(tree))
    report = {
        "schema_version": 1,
        "main_sha": base_sha,
        "react_candidate_sha": candidate_sha,
        "merge_base_sha": ancestor,
        "status": "CLEAN_DRY_RUN" if clean else "REVIEW_REQUIRED",
        "release_status": "BLOCKED",
        "main_changed_files": len(base_paths),
        "react_candidate_changed_files": len(candidate_paths),
        "overlap_files": sorted(base_paths & candidate_paths),
        "conflict_messages": [x.strip() for x in lines if "CONFLICT" in x][:80],
        "merge_tree_exit_code": result.returncode,
        "merge_tree_sha": tree if SHA.fullmatch(tree) else None,
        "main_or_candidate_ref_updated": False,
        "release_or_trading_performed": False,
    }
    if not clean:
        return report

    if extract_dir.exists():
        raise RuntimeError("Preview directory already exists: refusing overwrite")
    extract_dir.mkdir(parents=True)
    archive = subprocess.Popen(
        ["git", "-C", str(repo), "archive", "--format=tar", tree],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE,
    )
    assert archive.stdout is not None
    unpack = subprocess.run(
        ["tar", "-xf", "-", "-C", str(extract_dir)],
        stdin=archive.stdout, capture_output=True, check=False,
    )
    archive.stdout.close()
    _stdout, archive_err = archive.communicate()
    if archive.returncode or unpack.returncode:
        raise RuntimeError(
            f"Temporary tree extraction failed: archive={archive.returncode}, "
            f"tar={unpack.returncode}; " +
            archive_err.decode("utf-8", errors="replace")[:200]
        )
    report["preview_extracted_to_temporary_directory"] = True
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", type=Path, default=Path("."))
    parser.add_argument("--base-ref", required=True)
    parser.add_argument("--candidate-ref", required=True)
    parser.add_argument("--expected-base", required=True)
    parser.add_argument("--expected-candidate", required=True)
    parser.add_argument("--extract-dir", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()

    report = {"status": "REVIEW_REQUIRED_AUDIT_ERROR", "release_status": "BLOCKED"}
    try:
        report = inspect(
            args.repo, args.base_ref, args.candidate_ref,
            args.expected_base, args.expected_candidate, args.extract_dir,
        )
    except (OSError, RuntimeError, ValueError) as error:
        report["error"] = str(error)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(
        json.dumps(report, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(report, ensure_ascii=False, sort_keys=True))
    return 0 if report["status"] == "CLEAN_DRY_RUN" else 1


if __name__ == "__main__":
    raise SystemExit(main())
