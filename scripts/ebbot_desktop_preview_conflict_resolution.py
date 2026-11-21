#!/usr/bin/env python3
"""Build a synthetic conflict-resolution *preview* in the CI runner only.

No git merge, commit, checkout, reset, ref updates, remote writes, installation,
app/server startup, real database access or release. Strict SHA pins prevent
silent use after main or the PR stack changes.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile

EXPECTED_MAIN = "85f35395922b10e47686315c3af1576f286e93b1"
EXPECTED_STACK = "0c0feb2d9eaca9ab9d3067d12e453a103fb8df35"
REVIEW_ONLY_REPLACEMENTS = (
    ".github/workflows/ebbot-electron-windows-offline-package.yml",
    "apps/dsa-desktop/main.js",
    "scripts/audit_ebbot_desktop_package.py",
    "tests/test_ebbot_desktop_package_audit.py",
)


def run(repo: Path, *args: str, index: str | None = None) -> str:
    env = os.environ.copy()
    if index:
        env["GIT_INDEX_FILE"] = index
    p = subprocess.run(["git", "-C", str(repo), *args],
                       env=env, capture_output=True, text=True, check=False)
    if p.returncode != 0:
        raise RuntimeError("Read-only Git tree preview command failed: " + args[0])
    return p.stdout.strip()


def preview(repo: Path, report: dict) -> dict:
    if (report.get("schema_version") != 1 or
            report.get("status") != "REVIEW_REQUIRED_CONFLICTS" or
            report.get("release_status") != "BLOCKED" or
            report.get("base_sha") != EXPECTED_MAIN or
            report.get("candidate_sha") != EXPECTED_STACK):
        raise ValueError("Unreviewed main or draft PR SHA; preview must fail closed")
    tree = report.get("merge_tree_sha")
    if not isinstance(tree, str) or not re.fullmatch(r"[a-f0-9]{40,64}", tree):
        raise ValueError("Missing computed merge-tree object")
    conflicts = []
    for message in report.get("conflict_messages", []):
        match = re.search(r"Merge conflict in (.+)$", message)
        if not match:
            raise ValueError("Unknown conflict format; manual review required")
        conflicts.append(match.group(1))
    if tuple(sorted(conflicts)) != tuple(sorted(REVIEW_ONLY_REPLACEMENTS)):
        raise ValueError("Conflict list changed; cannot auto-select preview source")
    if report.get("conflict_message_count") != len(REVIEW_ONLY_REPLACEMENTS):
        raise ValueError("Unexpected number of conflicts")

    # This uses a *temporary index* containing the merge-tree's tree object;
    # it replaces only the four KNOWN, REVIEW-REQUIRED conflicted blobs with
    # their exact PR #139 version. No working tree or Git refs are mutated.
    with tempfile.TemporaryDirectory(prefix="ebbot-integration-index-") as work:
        index = str(Path(work) / "synthetic-index")
        run(repo, "read-tree", tree, index=index)
        for filename in REVIEW_ONLY_REPLACEMENTS:
            info = run(repo, "ls-tree", EXPECTED_STACK, "--", filename)
            if len(info.splitlines()) != 1 or "\t" not in info:
                raise ValueError("Expected candidate Git blob absent")
            header, listed = info.split("\t", 1)
            mode, kind, blob = header.split()
            if listed != filename or kind != "blob" or mode != "100644":
                raise ValueError("Unexpected conflict resolution object type")
            run(repo, "update-index", "--add", "--cacheinfo",
                f"{mode},{blob},{filename}", index=index)
        resolved_tree = run(repo, "write-tree", index=index)
    if not re.fullmatch(r"[a-f0-9]{40,64}", resolved_tree):
        raise RuntimeError("Could not write temporary synthetic tree")

    return {
        "schema_version": 1,
        "status": "SYNTHETIC_PREVIEW_REVIEW_REQUIRED",
        "release_status": "BLOCKED",
        "base_sha": EXPECTED_MAIN,
        "candidate_sha": EXPECTED_STACK,
        "synthetic_tree_sha": resolved_tree,
        "conflicts_replaced_with_PR139_for_tests_only": list(REVIEW_ONLY_REPLACEMENTS),
        "human_approval_to_merge": False,
        "branch_or_refs_modified": False,
        "merges_performed": False,
        "signing_verified": False,
        "installed_or_published": False,
        "auto_update_enabled": False,
        "trade_or_scheduler_executed": False,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, default=Path("."))
    parser.add_argument("--audit-json", type=Path, required=True)
    parser.add_argument("--report-json", type=Path, required=True)
    args = parser.parse_args(argv)
    initial = json.loads(args.audit_json.read_text(encoding="utf-8"))
    # Verify refs were not changed between the audit and preview.
    if (run(args.repo, "rev-parse", "origin/ebbot-audit-main") != EXPECTED_MAIN or
            run(args.repo, "rev-parse", "origin/ebbot-audit-pr139") != EXPECTED_STACK):
        raise ValueError("Git refs drifted since audit; manual review required")
    result = preview(args.repo, initial)
    with args.report_json.open("x", encoding="utf-8") as output:
        json.dump(result, output, indent=2, ensure_ascii=False, sort_keys=True)
        output.write("\n")
    print("Synthetic 4-file conflict resolution tree prepared for CI tests; still REVIEW REQUIRED and RELEASE BLOCKED.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
