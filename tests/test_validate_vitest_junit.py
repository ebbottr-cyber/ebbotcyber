"""Deterministic checks for the fail-closed React JUnit CI contract."""
from pathlib import Path
from xml.etree import ElementTree

import pytest

from scripts.validate_vitest_junit import junit_identity_sha256, main, validate_junit


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


def test_current_1409_baseline_rejects_1408_junit_cases(tmp_path: Path) -> None:
    cases = "".join(f'<testcase name="test_{i}"/>' for i in range(1408))
    xml = f"<testsuite>{cases}</testsuite>"
    with pytest.raises(ValueError, match="expected at least 1409"):
        validate_junit(_write(tmp_path, xml))


def test_identity_digest_accepts_reordered_cases(tmp_path: Path) -> None:
    xml = (
        '<testsuite>'
        '<testcase classname="a.test.tsx" name="first"/>'
        '<testcase classname="b.test.tsx" name="second"/>'
        '</testsuite>'
    )
    cases = list(ElementTree.fromstring(xml))
    digest = junit_identity_sha256(cases)
    reordered = (
        '<testsuite>'
        '<testcase classname="b.test.tsx" name="second"/>'
        '<testcase classname="a.test.tsx" name="first"/>'
        '</testsuite>'
    )
    assert validate_junit(
        _write(tmp_path, reordered), min_tests=2, expected_identity_sha256=digest
    ) == 2


def test_identity_digest_rejects_replacement_at_same_case_count(tmp_path: Path) -> None:
    baseline = (
        '<testsuite>'
        '<testcase classname="a.test.tsx" name="first"/>'
        '<testcase classname="b.test.tsx" name="second"/>'
        '</testsuite>'
    )
    digest = junit_identity_sha256(list(ElementTree.fromstring(baseline)))
    replaced = (
        '<testsuite>'
        '<testcase classname="a.test.tsx" name="first"/>'
        '<testcase classname="b.test.tsx" name="replacement"/>'
        '</testsuite>'
    )
    with pytest.raises(ValueError, match="testcase identities changed"):
        validate_junit(
            _write(tmp_path, replaced), min_tests=2, expected_identity_sha256=digest
        )


def test_identity_digest_preserves_duplicate_testcase_occurrences(tmp_path: Path) -> None:
    duplicated = (
        '<testsuite>'
        '<testcase classname="a" name="same"/>'
        '<testcase classname="a" name="same"/>'
        '</testsuite>'
    )
    digest = junit_identity_sha256(list(ElementTree.fromstring(duplicated)))
    with pytest.raises(ValueError, match="testcase identities changed"):
        validate_junit(
            _write(tmp_path, '<testsuite><testcase classname="a" name="same"/></testsuite>'),
            min_tests=1, expected_identity_sha256=digest,
        )


def test_identity_digest_rejects_missing_classname(tmp_path: Path) -> None:
    xml = '<testsuite><testcase name="one"/></testsuite>'
    with pytest.raises(ValueError, match="requires classname and name"):
        validate_junit(
            _write(tmp_path, xml), min_tests=1,
            expected_identity_sha256="a" * 64,
        )


def test_cli_enforces_reviewed_identity_baseline_file(tmp_path: Path) -> None:
    xml = '<testsuite><testcase classname="a" name="one"/></testsuite>'
    file = _write(tmp_path, xml)
    baseline = tmp_path / "baseline.sha256"
    baseline.write_text(
        junit_identity_sha256(list(ElementTree.fromstring(xml))), encoding="utf-8"
    )
    assert main(["--file", str(file), "--min-tests", "1",
                 "--baseline-sha256-file", str(baseline)]) == 0
    baseline.write_text("0" * 64, encoding="utf-8")
    assert main(["--file", str(file), "--min-tests", "1",
                 "--baseline-sha256-file", str(baseline)]) == 1
    baseline.write_text("not-a-sha256", encoding="utf-8")
    assert main(["--file", str(file), "--min-tests", "1",
                 "--baseline-sha256-file", str(baseline)]) == 1
