"""Synthetic-only promotion comparisons; no new or live market observations."""
from __future__ import annotations

import json
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path

import pytest

from scripts.check_solana_quality_promotion import (
    PromotionRejected,
    check_promotion,
    main,
    validate_report,
)

BASE_FILE = (
    Path(__file__).resolve().parents[1]
    / "apps/dsa-web/public/solana-quality-reviewed.json"
)
NOW = datetime(2026, 11, 20, 20, 0, 0, tzinfo=timezone.utc)


def published():
    """Frozen synthetic baseline, independent of mutable public report data.

    Run IDs are invented fixture identifiers, never real market observations.
    """
    return {
        "schema_version": 1,
        "mode": "reviewed_github_actions_archive_quality",
        "audited_at_utc": "2026-11-20T18:00:00Z",
        "audit_run_id": "90000099",
        "quality_result": "degraded_capture_data",
        "capture_count": 2,
        "total_priced_rows": 9,
        "total_missing_rows": 3,
        "blocked_assessments": 18,
        "watch_assessments": 0,
        "trading_enabled": False,
        "wallet_enabled": False,
        "performance_calculated": False,
        "ready_for_verified_paper_performance": False,
        "captures": [
            {"run_id": "90000001", "priced_rows": 6, "missing_rows": 0, "result": "passed"},
            {"run_id": "90000002", "priced_rows": 3, "missing_rows": 3, "result": "degraded"},
        ],
    }


def current_published():
    """Production JSON is checked separately without hardcoded totals or dates."""
    return json.loads(BASE_FILE.read_text(encoding="utf-8"))


def synthetic_next():
    """Invented IDs and counts only; never verified new GitHub observations."""
    value = deepcopy(published())
    value["audit_run_id"] = "90000199"
    value["audited_at_utc"] = "2026-11-20T19:00:00Z"
    value["captures"][0]["run_id"] = "90000101"
    value["captures"][1]["run_id"] = "90000102"
    return value


def test_synthetic_published_snapshot_matches_strict_gate():
    r = validate_report(published())
    assert r["total_priced_rows"] == 9
    assert r["total_missing_rows"] == 3
    assert r["blocked_assessments"] == 18
    assert r["watch_assessments"] == 0
    assert r["trading_enabled"] is False


def test_actual_published_file_valid_regardless_of_fresh_counts():
    """A legitimate next report must not break unrelated fixture tests."""
    report = validate_report(current_published())
    assert report["capture_count"] == len(report["captures"])
    assert report["total_priced_rows"] == sum(c["priced_rows"] for c in report["captures"])
    assert report["total_missing_rows"] == sum(c["missing_rows"] for c in report["captures"])
    assert report["blocked_assessments"] + report["watch_assessments"] == 2 * report["total_priced_rows"]
    assert report["trading_enabled"] is False
    assert report["wallet_enabled"] is False
    assert report["performance_calculated"] is False
    assert report["ready_for_verified_paper_performance"] is False


def test_new_capture_batch_is_eligible_for_review_but_not_approved():
    result = check_promotion(published(), synthetic_next(), now=NOW)
    assert result["quality_result"] == "degraded_capture_data"
    assert result["ready_for_verified_paper_performance"] is False


@pytest.mark.parametrize("mutation", [
    lambda x: x.update(audit_run_id="90000099"),
    lambda x: x.update(audit_run_id="90000000"),
    lambda x: x.update(audited_at_utc="2026-11-20T18:00:00Z"),
    lambda x: x.update(audited_at_utc="2026-11-19T19:00:00Z"),
    lambda x: x["captures"][0].update(run_id="90000001"),
    lambda x: x["captures"][0].update(run_id="90000000"),
    lambda x: x["captures"][0].update(run_id="90000102"),
    lambda x: x["captures"][0].update(run_id="90000199"),
    lambda x: x.update(total_priced_rows=99),
    lambda x: x.update(total_missing_rows=0),
    lambda x: x.update(blocked_assessments=0),
    lambda x: x.update(watch_assessments=2),
    lambda x: x.update(trading_enabled=True),
    lambda x: x.update(wallet_enabled=True),
    lambda x: x.update(performance_calculated=True),
    lambda x: x.update(ready_for_verified_paper_performance=True),
    lambda x: x.update(quality_result="complete_captures"),
    lambda x: x["captures"][1].update(result="passed"),
    lambda x: x["captures"][1].update(missing_rows=0),
    lambda x: x.update(mode="live_unreviewed_market_data"),
    lambda x: x.update(schema_version=True),
    lambda x: x.update(capture_count=True),
    lambda x: x.update(total_priced_rows=True),
    lambda x: x.update(malicious_new_field="trade-now"),
])
def test_replays_unsafe_flags_and_inconsistent_counts_fail_closed(mutation):
    r = synthetic_next()
    mutation(r)
    with pytest.raises(PromotionRejected):
        check_promotion(published(), r, now=NOW)


@pytest.mark.parametrize("bad_utc", [
    "2026-11-20T19:00:00+00:00",
    "2026-11-20T19:00:00+03:00",
    "2026-11-20", "2026-02-30T19:00:00Z", "not-time",
])
def test_bad_audit_timestamps_are_rejected(bad_utc):
    r = synthetic_next()
    r["audited_at_utc"] = bad_utc
    with pytest.raises(PromotionRejected):
        check_promotion(published(), r, now=NOW)


def test_future_audit_cannot_be_used_to_claim_freshness():
    r = synthetic_next()
    r["audited_at_utc"] = "2026-11-21T00:00:00Z"
    with pytest.raises(PromotionRejected, match="Future-dated"):
        check_promotion(published(), r, now=NOW)


def test_wholly_new_batch_can_still_be_degraded():
    r = synthetic_next()
    r["captures"][1]["result"] = "degraded"
    assert check_promotion(published(), r, now=NOW)["total_missing_rows"] == 3


def test_single_full_batch_does_not_imply_paper_trading_readiness():
    r = synthetic_next()
    r["captures"][1]["missing_rows"] = 0
    r["captures"][1]["priced_rows"] = 6
    r["captures"][1]["result"] = "passed"
    r["quality_result"] = "complete_captures"
    r["total_priced_rows"] = 12
    r["total_missing_rows"] = 0
    r["blocked_assessments"] = 24
    assert check_promotion(published(), r, now=NOW)["performance_calculated"] is False


def test_cli_unchanged_current_snapshot_can_only_be_inspected(monkeypatch, capsys):
    monkeypatch.setattr("sys.argv", [
        "checker", "--candidate", str(BASE_FILE),
    ])
    assert main() == 0
    output = json.loads(capsys.readouterr().out)
    assert output["status"] == "existing_report_valid"
    assert output["published"] is False
    assert output["approval_granted"] is False


def test_cli_rejects_replayed_source_without_overwriting(monkeypatch, capsys, tmp_path):
    candidate = tmp_path / "candidate.json"
    candidate.write_bytes(BASE_FILE.read_bytes())
    original = candidate.read_bytes()
    monkeypatch.setattr("sys.argv", [
        "checker", "--candidate", str(candidate),
        "--baseline", str(BASE_FILE),
    ])
    assert main() == 1
    output = json.loads(capsys.readouterr().out)
    assert output["status"] == "rejected"
    assert output["published"] is False
    assert candidate.read_bytes() == original


def test_missing_malformed_or_oversized_file_rejected(monkeypatch, tmp_path):
    bad = tmp_path / "bad.json"
    for payload in ("{not-json}", "x" * 12_001):
        bad.write_text(payload, encoding="utf-8")
        monkeypatch.setattr("sys.argv", ["checker", "--candidate", str(bad)])
        assert main() == 1
    monkeypatch.setattr("sys.argv", [
        "checker", "--candidate", str(tmp_path / "not-present.json"),
    ])
    assert main() == 1
