"""Deterministic checks for the fail-closed React JUnit CI contract."""
from pathlib import Path

import pytest

from scripts.validate_vitest_junit import main, validate_junit


def _write(tmp_path: Path, xml: str) -> Path:
    path = tmp_path / "vitest.xml"
    path.write_text(xml, encoding="utf-8")
    return path


def test_accepts_complete_successful_junit(tmp_path: Path) -> None:
    xml = '<testsuites><testsuite><testcase name="a"/><testcase name="b"/></testsuite></testsuites>'
    assert validate_junit(_write(tmp_path, xml), min_tests=2) == 2


@pytest.mark.parametrize(
    "xml",
    [
        '<testsuite><testcase name="a"><skipped/></testcase></testsuite>',
        '<testsuite><testcase name="a"><failure>oops</failure></testcase></testsuite>',
        '<testsuite><testcase name="a"><error>oops</error></testcase></testsuite>',
    ],
)
def test_rejects_skipped_failed_and_error_cases(tmp_path: Path, xml: str) -> None:
    with pytest.raises(ValueError):
        validate_junit(_write(tmp_path, xml), min_tests=1)


def test_rejects_silent_test_removal(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="at least 2"):
        validate_junit(_write(tmp_path, '<testsuite><testcase name="a"/></testsuite>'), min_tests=2)


def test_rejects_no_tests(tmp_path: Path) -> None:
    with pytest.raises(ValueError):
        validate_junit(_write(tmp_path, '<testsuites/>'), min_tests=1)


def test_accepts_namespaced_junit(tmp_path: Path) -> None:
    xml = '<testsuite xmlns="urn:x"><testcase name="a"/></testsuite>'
    assert validate_junit(_write(tmp_path, xml), min_tests=1) == 1


def test_cli_fails_closed_on_invalid_xml(tmp_path: Path) -> None:
    file = _write(tmp_path, "<broken")
    assert main(["--file", str(file), "--min-tests", "1"]) == 1


def test_cli_success(tmp_path: Path) -> None:
    file = _write(tmp_path, '<testsuite><testcase name="a"/></testsuite>')
    assert main(["--file", str(file), "--min-tests", "1"]) == 0
