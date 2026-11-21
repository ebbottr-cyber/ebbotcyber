#!/usr/bin/env python3
"""Read-only inventory for EBBot three-stack conflicts; never auto-picks ours/theirs.

The intent is to prevent old React regression repair from silently dropping
new Turkish locale, portfolio FX/TRY outage, or desktop health-security tests.
No Git ref updates, network providers, release, installation or trading.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import subprocess

SAFE_REF = re.compile(r"^[A-Za-z0-9._/-]+$")
SHA = re.compile(r"^[a-f0-9]{40}$")
TEST_NAME = re.compile(r"\b(?:it|test)(?:\.(?:skip|only))?\(\s*['\x22\x60]([^'\x22\x60]+)['\x22\x60]")
CONFLICT_TEST_PATHS = (
    "apps/dsa-web/src/components/alerts/__tests__/AlertRuleForm.test.tsx",
    "apps/dsa-web/src/components/alerts/__tests__/AlertRuleList.test.tsx",
    "apps/dsa-web/src/components/common/__tests__/Input.test.tsx",
    "apps/dsa-web/src/components/layout/__tests__/RouteBoundary.test.tsx",
    "apps/dsa-web/src/components/layout/__tests__/Shell.test.tsx",
    "apps/dsa-web/src/components/layout/__tests__/SidebarNav.test.tsx",
    "apps/dsa-web/src/components/settings/__tests__/LLMChannelEditor.test.tsx",
    "apps/dsa-web/src/components/settings/__tests__/NotificationTestPanel.test.tsx",
    "apps/dsa-web/src/components/tasks/__tests__/TaskPanel.test.tsx",
    "apps/dsa-web/src/components/theme/__tests__/ThemeToggle.test.tsx",
    "apps/dsa-web/src/pages/__tests__/AlertsPage.test.tsx",
    "apps/dsa-web/src/pages/__tests__/BacktestPage.test.tsx",
    "apps/dsa-web/src/pages/__tests__/DataCenterPage.test.tsx",
    "apps/dsa-web/src/pages/__tests__/HomePage.test.tsx",
    "apps/dsa-web/src/pages/__tests__/LoginPage.test.tsx",
    "apps/dsa-web/src/pages/__tests__/PortfolioPage.test.tsx",
)
PROTECTED_NON_TEST_PATHS = (
    ".github/workflows/ebbot-electron-windows-offline-package.yml",
    "scripts/probe_ebbot_packaged_health.py",
)


def testcase_names(source: str) -> set[str]:
    return {match.group(1) for match in TEST_NAME.finditer(source)}


def difference(left: str, right: str) -> dict:
    left_names, right_names = testcase_names(left), testcase_names(right)
    return {
        "react_title_count": len(left_names),
        "windows_title_count": len(right_names),
        "shared_title_count": len(left_names & right_names),
        "react_only_test_titles": sorted(left_names - right_names),
        "windows_only_test_titles": sorted(right_names - left_names),
        "different_source": left != right,
        "requires_human_semantic_review": left != right,
        "react_skip_literals": len(re.findall(r"\b(?:it|test)\.skip\s*\(", left)),
        "windows_skip_literals": len(re.findall(r"\b(?:it|test)\.skip\s*\(", right)),
        "parameterized_cases_not_fully_counted": (
            "it.each(" in left or "it.each(" in right
        ),
    }


def git(repo: Path, *args: str) -> str:
    proc = subprocess.run(
        ["git", "-C", str(repo), *args],
        capture_output=True, text=True, check=False,
    )
    if proc.returncode:
        raise RuntimeError("Git operation failed: " + args[0])
    return proc.stdout.strip()


def fixed_commit(repo: Path, ref: str, expected: str) -> str:
    if not SAFE_REF.fullmatch(ref) or ref.startswith("-") or ".." in ref:
        raise ValueError("Unsafe Git ref")
    if not SHA.fullmatch(expected):
        raise ValueError("Expected an exact commit SHA")
    commit = git(repo, "rev-parse", "--verify", ref + "^{commit}")
    if commit != expected:
        raise RuntimeError("Git ref moved since comparison; repin and rerun")
    return commit


def inventory(repo: Path, main: str, react: str, windows: str) -> dict:
    report: dict = {
        "schema_version": 1,
        "main_sha": main,
        "react_sha": react,
        "windows_sha": windows,
        "release_status": "BLOCKED",
        "main_updated": False,
        "trade_or_install_executed": False,
        "status": "REVIEW_REQUIRED",
        "conflict_test_paths": {},
        "non_test_conflicts": {},
    }
    for path in CONFLICT_TEST_PATHS:
        a = git(repo, "show", react + ":" + path)
        b = git(repo, "show", windows + ":" + path)
        report["conflict_test_paths"][path] = difference(a, b)
    for path in PROTECTED_NON_TEST_PATHS:
        candidates: dict[str, dict] = {}
        for label, sha in (("main", main), ("windows", windows)):
            code = git(repo, "show", sha + ":" + path)
            candidates[label] = {
                "lines": len(code.splitlines()),
                "sha": git(repo, "rev-parse", sha + ":" + path),
                "has_publish_never": "--publish never" in code,
                "has_loopback": "127.0.0.1" in code,
                "has_health_probe": "health" in code.lower(),
            }
        report["non_test_conflicts"][path] = {
            "candidates": candidates,
            "needs_human_merge": candidates["main"]["sha"] != candidates["windows"]["sha"],
        }
    report["react_only_title_total"] = sum(
        len(x["react_only_test_titles"]) for x in report["conflict_test_paths"].values()
    )
    report["windows_only_title_total"] = sum(
        len(x["windows_only_test_titles"]) for x in report["conflict_test_paths"].values()
    )
    report["same_test_titles_conflicts"] = sum(
        not x["react_only_test_titles"] and not x["windows_only_test_titles"]
        for x in report["conflict_test_paths"].values()
    )
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", type=Path, default=Path("."))
    for name in ("main", "react", "windows"):
        parser.add_argument("--" + name + "-ref", required=True)
        parser.add_argument("--" + name + "-sha", required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    report: dict = {"status": "REVIEW_REQUIRED_AUDIT_ERROR", "release_status": "BLOCKED"}
    try:
        resolved = {
            key: fixed_commit(args.repo, getattr(args, key + "_ref"), getattr(args, key + "_sha"))
            for key in ("main", "react", "windows")
        }
        report = inventory(args.repo, **resolved)
    except (OSError, RuntimeError, ValueError) as exc:
        report["error"] = str(exc)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(
        json.dumps(report, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(report, ensure_ascii=False, sort_keys=True))
    return 0 if report.get("status") == "REVIEW_REQUIRED" else 1


if __name__ == "__main__":
    raise SystemExit(main())
