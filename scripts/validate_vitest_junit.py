"""Fail-closed validation of the complete Vitest JUnit output.

This is not a test runner. It checks the saved report after Vitest exits 0, so
disabling/skipping existing React tests cannot make required CI silently green.
The minimum test count rejects obvious removals, but does not prove that
individual test identities were preserved if a test was replaced or renamed.
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


def validate_junit(
    path: Path, *, min_tests: int = 1409, expected_testset_sha256: str | None = None
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
    if expected_testset_sha256 is not None:
        expected = expected_testset_sha256.strip().lower()
        if not re.fullmatch(r"[0-9a-f]{64}", expected):
            raise ValueError("Invalid expected React test identity SHA-256")
        if any(not case.get("classname") or not case.get("name") for case in cases):
            raise ValueError("JUnit has a testcase without classname or name")
        identities = sorted((case.get("classname"), case.get("name")) for case in cases)
        canonical = json.dumps(identities, ensure_ascii=False, separators=(",", ":"))
        actual = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
        if actual != expected:
            raise ValueError(
                f"React test identities changed: expected SHA-256 {expected}, got {actual}; "
                "review the full JUnit report before updating the baseline"
            )
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
    return count


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Require complete, unskipped Vitest JUnit")
    parser.add_argument("--file", required=True, type=Path, dest="path")
    parser.add_argument("--min-tests", type=int, default=1409)
    parser.add_argument("--expected-testset-sha256-file", type=Path)
    options = parser.parse_args(argv)
    try:
        expected_hash = (
            options.expected_testset_sha256_file.read_text(encoding="utf-8").strip()
            if options.expected_testset_sha256_file is not None else None
        )
        cases = validate_junit(
            options.path, min_tests=options.min_tests, expected_testset_sha256=expected_hash
        )
    except (OSError, ElementTree.ParseError, ValueError) as exc:
        print(f"EBBot required React gate FAILED: {exc}", file=sys.stderr)
        return 1
    print(f"EBBot required React gate PASSED: {cases} cases, 0 skipped, 0 failed")
    if options.expected_testset_sha256_file is not None:
        print("EBBot React test identity baseline PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
