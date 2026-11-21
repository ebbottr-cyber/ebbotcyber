"""Fail-closed validation of the complete Vitest JUnit output.

This is not a test runner. It checks the saved report after Vitest exits 0, so
disabling/skipping existing React tests cannot make required CI silently green.
Uses only the Python standard library and does not access services or wallets.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path
from xml.etree import ElementTree


def _local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def junit_identity_sha256(cases: list[ElementTree.Element]) -> str:
    """Stable digest of all testcase class/name pairs, including duplicate names.

    Sorting means Vitest execution order changes do not change the digest;
    a removed/replaced testcase changes it even when total count stays equal.
    """
    identities = []
    for case in cases:
        classname = case.get("classname")
        name = case.get("name")
        if not classname or not name:
            raise ValueError("JUnit testcase identity requires classname and name")
        identities.append((classname, name))
    payload = json.dumps(sorted(identities), ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def validate_junit(
    path: Path, *, min_tests: int = 1409, expected_identity_sha256: str | None = None
) -> int:
    """Return test count; reject missing, skipped or failed JUnit test cases."""
    if min_tests < 1:
        raise ValueError("min_tests must be a positive integer")
    tree = ElementTree.parse(path)
    cases = [node for node in tree.getroot().iter()
             if _local_name(node.tag) == "testcase"]
    count = len(cases)
    if count < min_tests:
        raise ValueError(f"Only {count} JUnit cases; expected at least {min_tests}")
    failures = 0
    skipped = 0
    for case in cases:
        for child in case:
            status = _local_name(child.tag)
            if status == "skipped":
                skipped += 1
            elif status in ("failure", "error"):
                failures += 1
    if skipped or failures:
        raise ValueError(
            f"Vitest JUnit: {count} cases, {skipped} skipped, {failures} failures/errors"
        )
    if expected_identity_sha256 is not None:
        expected = expected_identity_sha256.strip().lower()
        if not re.fullmatch(r"[0-9a-f]{64}", expected):
            raise ValueError("Expected React testcase SHA-256 must be 64 hex characters")
        actual = junit_identity_sha256(cases)
        if actual != expected:
            raise ValueError(
                "Vitest JUnit testcase identities changed: "
                f"expected SHA-256 {expected}, got {actual}; review baseline changes"
            )
    return count


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Require complete, unskipped Vitest JUnit")
    parser.add_argument("--file", required=True, type=Path, dest="path")
    parser.add_argument("--min-tests", type=int, default=1409)
    parser.add_argument(
        "--baseline-sha256-file", type=Path,
        help="Reviewed SHA-256 baseline of sorted JUnit testcase classname/name pairs",
    )
    options = parser.parse_args(argv)
    try:
        expected = None
        if options.baseline_sha256_file is not None:
            expected = options.baseline_sha256_file.read_text(encoding="utf-8").strip()
        cases = validate_junit(
            options.path, min_tests=options.min_tests,
            expected_identity_sha256=expected,
        )
    except (OSError, ElementTree.ParseError, ValueError) as exc:
        print(f"EBBot required React gate FAILED: {exc}", file=sys.stderr)
        return 1
    print(f"EBBot required React gate PASSED: {cases} cases, 0 skipped, 0 failed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
