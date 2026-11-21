#!/usr/bin/env python3
"""Read-only, offline 3-way conflict audit between EBBot main and draft stack.

Never merges refs, mutates branches, starts the desktop/backend, or enables
trading, updates, installation, signing, scheduling, or publication.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import subprocess

SHA_RE = re.compile(r"[a-f0-9]{40,64}")


def git(repo: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True, check=False)


def git_required(repo: Path, *args: str) -> str:
    p = git(repo, *args)
    if p.returncode != 0:
        raise RuntimeError("Git read-only audit command failed: " + args[0])
    return p.stdout.strip()


def changed_files(repo: Path, ancestor: str, head: str) -> set[str]:
    output = git_required(repo, "diff", "--name-only", "--no-renames", "-z", ancestor, head)
    return {name for name in output.split("\x00") if name}


def audit(repo: Path, base: str, candidate: str) -> dict:
    # Allow only refs, not user-provided command flags or filesystem paths.
    for value in (base, candidate):
        if not re.fullmatch(r"[A-Za-z0-9._/-]+", value) or value.startswith("-") or ".." in value:
            raise ValueError("Unsafe Git revision")
    base_sha = git_required(repo, "rev-parse", "--verify", base + "^{commit}")
    candidate_sha = git_required(repo, "rev-parse", "--verify", candidate + "^{commit}")
    common = git_required(repo, "merge-base", base_sha, candidate_sha)
    base_changes = changed_files(repo, common, base_sha)
    candidate_changes = changed_files(repo, common, candidate_sha)
    overlap = sorted(base_changes & candidate_changes)
    lower_main = {name.casefold() for name in base_changes}
    lower_candidate = {name.casefold() for name in candidate_changes}
    case_insensitive_overlap = sorted(lower_main & lower_candidate)
    merge = git(repo, "merge-tree", "--write-tree", "--messages", base_sha, candidate_sha)
    tree_line = merge.stdout.splitlines()[0] if merge.stdout else ""
    tree_sha = tree_line if SHA_RE.fullmatch(tree_line) else None
    if merge.returncode == 0 and tree_sha:
        status = "CLEAN_DRY_RUN"
    elif merge.returncode == 1:
        status = "REVIEW_REQUIRED_CONFLICTS"
    else:
        status = "REVIEW_REQUIRED_AUDIT_ERROR"
    lines = [line.strip() for line in merge.stdout.splitlines() if "CONFLICT" in line]
    return {
        "schema_version": 1,
        "mode": "git_merge_tree_no_ref_updates",
        "status": status,
        "release_status": "BLOCKED",
        "base_sha": base_sha,
        "candidate_sha": candidate_sha,
        "merge_base_sha": common,
        "merge_tree_sha": tree_sha,
        "merge_tree_exit_code": merge.returncode,
        "base_changed_files": len(base_changes),
        "candidate_changed_files": len(candidate_changes),
        "exact_overlap_files": overlap[:100],
        "exact_overlap_count": len(overlap),
        "case_insensitive_overlap_count": len(case_insensitive_overlap),
        "conflict_messages": lines[:70],
        "conflict_message_count": len(lines),
        "branch_or_refs_modified": False,
        "merges_performed": False,
        "automatic_update_enabled": False,
        "release_published": False,
        "orders_or_scheduled_jobs_run": False,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, default=Path("."))
    parser.add_argument("--base-ref", required=True)
    parser.add_argument("--candidate-ref", required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args(argv)
    report = audit(args.repo, args.base_ref, args.candidate_ref)
    with args.report.open("x", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, sort_keys=True, indent=2)
        f.write("\n")
    print(f"EBBot integration dry run: {report['status']}; " +
          f"overlap={report['exact_overlap_count']}; conflicts={report['conflict_message_count']}; RELEASE BLOCKED")
    return 0 if report["status"] == "CLEAN_DRY_RUN" else 1


if __name__ == "__main__":
    raise SystemExit(main())
