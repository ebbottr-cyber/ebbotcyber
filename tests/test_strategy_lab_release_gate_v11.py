"""Contract checks for the read-only release gate; no GitHub requests."""
import json

from scripts.check_strategy_lab_stack_v11 import STACK, assess_pr_stack, main


def _stack(*, draft=True):
    return [
        {
            "number": number, "state": "open", "merged": False,
            "draft": draft, "mergeable": True, "mergeable_state": "clean",
            "head": {"ref": head}, "base": {"ref": base},
        }
        for number, head, base in STACK
    ]


def test_correct_nonconflicting_draft_stack_passes_integration_only():
    result = assess_pr_stack(_stack())
    assert result["status"] == "PASS"
    assert result["blocked_prs"] == []
    assert all(item["status"] == "INTEGRATION_READY" for item in result["checks"])
    assert result["merge_performed"] is False
    assert result["trading_enabled"] is False


def test_dirty_pr_34_blocks_all_merges_even_if_other_tests_were_green():
    prs = _stack()
    item = next(p for p in prs if p["number"] == 34)
    item["mergeable"] = False
    item["mergeable_state"] = "dirty"
    outcome = assess_pr_stack(prs)
    assert outcome["status"] == "BLOCKED"
    assert outcome["blocked_prs"] == [34]
    assert "merge_conflict" in next(
        p for p in outcome["checks"] if p["pr"] == 34
    )["reasons"]


def test_rebased_wrong_branch_is_rejected():
    prs = _stack()
    prs[-1]["base"]["ref"] = "main"
    outcome = assess_pr_stack(prs)
    assert outcome["blocked_prs"] == [48]
    assert outcome["checks"][-1]["reasons"] == ["unexpected_base_branch"]


def test_missing_unknown_and_closed_prs_do_not_look_ready():
    prs = _stack()
    prs.pop()
    prs[0]["mergeable"] = None
    prs[1]["state"] = "closed"
    result = assess_pr_stack(prs)
    assert result["status"] == "BLOCKED"
    assert set(result["blocked_prs"]) == {30, 32, 48}
    assert "mergeability_unknown" in result["checks"][0]["reasons"]
    assert "pr_not_open_unmerged" in result["checks"][1]["reasons"]
    assert "pull_request_missing" in result["checks"][-1]["reasons"]


def test_release_mode_never_silently_approves_unreviewed_drafts():
    outcome = assess_pr_stack(_stack(), require_ready=True)
    assert outcome["status"] == "BLOCKED"
    assert len(outcome["blocked_prs"]) == len(STACK)
    assert all("draft_not_reviewed" in r["reasons"] for r in outcome["checks"])
    reviewed = assess_pr_stack(_stack(draft=False), require_ready=True)
    assert reviewed["status"] == "PASS"


def test_cli_accepts_only_explicit_offline_fixture_and_does_not_write(tmp_path, capsys):
    input_path = tmp_path / "pulls.json"
    input_path.write_text(json.dumps(_stack()), encoding="utf-8")
    assert main(["--fixture", str(input_path)]) == 0
    result = json.loads(capsys.readouterr().out)
    assert result["status"] == "PASS"
    assert len(list(tmp_path.iterdir())) == 1
    assert main(["--fixture", str(input_path), "--release"]) == 1
    assert json.loads(capsys.readouterr().out)["status"] == "BLOCKED"


def test_network_or_corrupt_fixture_failure_is_fully_blocked(tmp_path, capsys):
    missing = tmp_path / "missing.json"
    assert main(["--fixture", str(missing)]) == 1
    output = json.loads(capsys.readouterr().out)
    assert output["status"] == "BLOCKED"
    assert output["merge_performed"] is False
    assert output["trading_enabled"] is False
