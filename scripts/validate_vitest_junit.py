"""Fail-closed validation of the complete Vitest JUnit output.

This is not a test runner. It checks the saved report after Vitest exits 0, so
disabling/skipping existing React tests cannot make required CI silently green.
The minimum test count rejects obvious removals, but does not prove that
individual test identities were preserved if a test was replaced or renamed.
Uses only the Python standard library and does not access services or wallets.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path
from xml.etree import ElementTree


def _local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def validate_junit(path: Path, *, min_tests: int = 1409) -> int:
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
    return count


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Require complete, unskipped Vitest JUnit")
    parser.add_argument("--file", required=True, type=Path, dest="path")
    parser.add_argument("--min-tests", type=int, default=1409)
    options = parser.parse_args(argv)
    try:
        cases = validate_junit(options.path, min_tests=options.min_tests)
    except (OSError, ElementTree.ParseError, ValueError) as exc:
        print(f"EBBot required React gate FAILED: {exc}", file=sys.stderr)
        return 1
    print(f"EBBot required React gate PASSED: {cases} cases, 0 skipped, 0 failed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
