"""Offline integration preflight: both remediation PRs remain review-only."""
import json

from scripts.check_integration_dependencies_v14 import assess_deps, main, DEPENDENCIES


def _prs():
    return [
        {"number": number, "state": "open", "merged": False,
         "draft": True, "mergeable": True, "mergeable_state": "clean",
         "head": {"ref": head}, "base": {"ref": base}}
        for number, head, base in DEPENDENCIES
    ]


def test_both_correct_draft_dependencies_are_reviewable():
    out = assess_deps(_prs())
    assert out["status"] == "PASS"
    assert [x["status"] for x in out["dependencies"]] == ["INTEGRATION_REVIEWABLE"] * 2
    assert out["merged"] is False and out["trading_enabled"] is False


def test_missing_pr_is_fail_closed():
    out = assess_deps(_prs()[:1])
    assert out["status"] == "BLOCKED"
    assert out["dependencies"][1]["reasons"] == ["missing_pull_request"]


def test_conflict_and_unknown_mergeability_fail_closed():
    for value in (None, False):
        prs = _prs()
        prs[0]["mergeable"] = value
        result = assess_deps(prs)
        assert result["status"] == "BLOCKED"
        assert "conflicted_or_unknown_mergeability" in result["dependencies"][0]["reasons"]


def test_incorrect_base_or_existing_merge_fails():
    prs = _prs()
    prs[1]["base"]["ref"] = "main"
    assert assess_deps(prs)["status"] == "BLOCKED"
    prs = _prs()
    prs[0]["merged"] = True
    assert assess_deps(prs)["status"] == "BLOCKED"


def test_offline_cli_does_not_mutate_files(tmp_path, capsys):
    fixture = tmp_path / "prs.json"
    fixture.write_text(json.dumps(_prs()), encoding="utf-8")
    assert main(["--fixture", str(fixture)]) == 0
    assert json.loads(capsys.readouterr().out)["status"] == "PASS"
    assert len(list(tmp_path.iterdir())) == 1


def test_bad_fixture_fails_closed(tmp_path, capsys):
    missing = tmp_path / "missing.json"
    assert main(["--fixture", str(missing)]) == 1
    assert json.loads(capsys.readouterr().out)["status"] == "BLOCKED"
