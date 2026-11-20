"""Synthetic observations only; never assert claims about live market performance."""
from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path

import pytest

from scripts.prepare_solana_reviewed_report import main, prepare_candidate, verify_source_conclusions
from scripts.validate_solana_history import ObservationValidationError

MINT_A = "So11111111111111111111111111111111111111112"
MINT_B = "So11111111111111111111111111111111111111113"
AUDIT_ID = "44791912581"
DATE = "2026-11-20T18:21:11Z"


def observation_fixture(started=1_800_000_000_000, *, missing=False):
    observations = []
    for round_number in range(3):
        for mint in (MINT_A, MINT_B):
            row = {
                "timestamp_ms": started + (round_number + 1) * 60_000,
                "mint": mint,
            }
            if missing and mint == MINT_B:
                row.update(status="missing_price", price_source=None, strategies={})
            else:
                row.update(
                    status="priced",
                    discovery_source="dexscreener",
                    discovery_pool_id="pool_a" if mint == MINT_A else "pool_b",
                    price_source="dexscreener",
                    price_pair_id="pool_a" if mint == MINT_A else "pool_b",
                    price_usd="0.1",
                    liquidity_usd="25000",
                    volume_h24_usd="100000",
                    buys_m5=30,
                    sells_m5=10,
                    change_m5_pct=5,
                    risk_record_present=False,
                    strategies={
                        strategy: {
                            "status": "blocked",
                            "score": 50,
                            "reasons": ["security_unknown"],
                        }
                        for strategy in ("new_coin_hunter", "momentum_watcher")
                    },
                )
            observations.append(row)
    return {
        "schema_version": 1,
        "mode": "bounded_prospective_public_market_observations",
        "data_origin": "live_public_api_not_historical",
        "trading_enabled": False,
        "wallet_enabled": False,
        "background_schedule_enabled": False,
        "performance_calculated": False,
        "start_timestamp_ms": started,
        "requested_rounds": 3,
        "minimum_interval_seconds": 60,
        "tracked_mints": [MINT_A, MINT_B],
        "observations": observations,
        "errors": [],
        "summary": {
            "result": "degraded" if missing else "passed",
            "rounds": 3,
            "selected_tokens": 2,
            "valid_price_observations": 3 if missing else 6,
            "missing_price_observations": 3 if missing else 0,
            "complete_token_series": 1 if missing else 2,
            "provider_error_classes": [],
        },
    }


def write_json(tmp_path: Path, name: str, value: dict) -> Path:
    path = tmp_path / name
    path.write_text(json.dumps(value), encoding="utf-8")
    return path


def candidate(tmp_path: Path, *, missing=False) -> dict:
    first = write_json(tmp_path, "a.json", observation_fixture())
    second = write_json(
        tmp_path, "b.json", observation_fixture(1_800_005_000_000, missing=missing)
    )
    return prepare_candidate(
        [("44779967482", first), ("44777830658", second)],
        audit_run_id=AUDIT_ID,
        audited_at_utc=DATE,
    )


def test_two_complete_captures_generate_counters_but_never_pnl(tmp_path):
    result = candidate(tmp_path)
    assert result["quality_result"] == "complete_captures"
    assert result["total_priced_rows"] == 12
    assert result["total_missing_rows"] == 0
    assert result["blocked_assessments"] == 24
    assert result["watch_assessments"] == 0
    assert result["trading_enabled"] is False
    assert result["wallet_enabled"] is False
    assert result["performance_calculated"] is False
    assert result["ready_for_verified_paper_performance"] is False
    assert set(result["captures"][0]) == {
        "run_id", "result", "priced_rows", "missing_rows"
    }


def test_complete_and_degraded_captures_generate_reviewable_counts(tmp_path):
    result = candidate(tmp_path, missing=True)
    assert result["quality_result"] == "degraded_capture_data"
    assert result["capture_count"] == 2
    assert [item["priced_rows"] for item in result["captures"]] == [6, 3]
    assert [item["missing_rows"] for item in result["captures"]] == [0, 3]
    assert [item["result"] for item in result["captures"]] == ["passed", "degraded"]
    assert result["total_priced_rows"] == 9
    assert result["total_missing_rows"] == 3
    assert result["blocked_assessments"] == 18
    assert result["watch_assessments"] == 0
    assert result["audit_run_id"] == AUDIT_ID
    assert not any("price_usd" in entry for entry in result["captures"])


@pytest.mark.parametrize("change", [
    lambda x: x.update(trading_enabled=True),
    lambda x: x.update(wallet_enabled=True),
    lambda x: x.update(performance_calculated=True),
    lambda x: x.update(data_origin="synthetic"),
    lambda x: x["summary"].update(valid_price_observations=99),
    lambda x: x["observations"][0].update(price_usd="NaN"),
    lambda x: x["observations"][0]["strategies"]["new_coin_hunter"].update(
        status="watch", reasons=[]
    ),
])
def test_fails_closed_on_unsafe_or_fabricated_source(tmp_path, change):
    unsafe = observation_fixture()
    change(unsafe)
    path = write_json(tmp_path, "invalid.json", unsafe)
    with pytest.raises(ObservationValidationError):
        prepare_candidate(
            [("44779967482", path)], audit_run_id=AUDIT_ID, audited_at_utc=DATE
        )


@pytest.mark.parametrize("runs", [
    ("44779967482", "44779967482"),
    ("44779967482", "not-a-run"),
    ("44779967482", AUDIT_ID),
])
def test_rejects_duplicate_invalid_or_audit_source_id(tmp_path, runs):
    first = write_json(tmp_path, "first.json", observation_fixture())
    second = write_json(
        tmp_path, "second.json", observation_fixture(1_800_005_000_000)
    )
    with pytest.raises(ObservationValidationError):
        prepare_candidate(
            [(runs[0], first), (runs[1], second)],
            audit_run_id=AUDIT_ID,
            audited_at_utc=DATE,
        )


def test_reused_capture_data_under_different_run_ids_is_rejected(tmp_path):
    same = observation_fixture()
    first = write_json(tmp_path, "first.json", same)
    second = write_json(tmp_path, "second.json", deepcopy(same))
    with pytest.raises(ObservationValidationError, match="Repeated capture"):
        prepare_candidate(
            [("44779967482", first), ("44777830658", second)],
            audit_run_id=AUDIT_ID,
            audited_at_utc=DATE,
        )


def test_missing_or_oversized_input_never_produces_a_candidate(tmp_path):
    with pytest.raises(ObservationValidationError, match="Missing or oversized"):
        prepare_candidate(
            [("44779967482", tmp_path / "missing.json")],
            audit_run_id=AUDIT_ID,
            audited_at_utc=DATE,
        )
    large = tmp_path / "too-big.json"
    large.write_bytes(b"x" * 2_000_001)
    with pytest.raises(ObservationValidationError, match="Missing or oversized"):
        prepare_candidate(
            [("44779967482", large)], audit_run_id=AUDIT_ID, audited_at_utc=DATE
        )


@pytest.mark.parametrize("timestamp", [
    "2026-11-20", "2026-11-20T12:00:00+03:00", "no-date",
])
def test_requires_utc_timestamp(tmp_path, timestamp):
    path = write_json(tmp_path, "source.json", observation_fixture())
    with pytest.raises(ObservationValidationError):
        prepare_candidate(
            [("44779967482", path)],
            audit_run_id=AUDIT_ID,
            audited_at_utc=timestamp,
        )


def test_source_conclusions_are_cross_checked_and_failed_run_stays_degraded(tmp_path):
    result = candidate(tmp_path, missing=True)
    valid = {"44779967482": "success", "44777830658": "failure"}
    verify_source_conclusions(result, valid)

    with pytest.raises(ObservationValidationError, match="disagrees"):
        verify_source_conclusions(result, {
            "44779967482": "success", "44777830658": "success",
        })
    with pytest.raises(ObservationValidationError, match="disagrees"):
        verify_source_conclusions(result, {
            "44779967482": "failure", "44777830658": "failure",
        })
    with pytest.raises(ObservationValidationError, match="conclusion IDs"):
        verify_source_conclusions(result, {"44779967482": "success"})
    with pytest.raises(ObservationValidationError, match="Only completed"):
        verify_source_conclusions(result, {
            "44779967482": "success", "44777830658": "cancelled",
        })


def test_cli_rejects_mislabeled_failed_source_before_writing(monkeypatch, tmp_path):
    path = write_json(tmp_path, "degraded.json", observation_fixture(missing=True))
    out = tmp_path / "candidate.json"
    monkeypatch.setattr("sys.argv", [
        "prepare", "--capture", f"44777830658={path}",
        "--source-conclusion", "44777830658=success",
        "--audit-run-id", AUDIT_ID, "--audited-at-utc", DATE,
        "--output", str(out),
    ])
    assert main() == 1
    assert not out.exists()


def test_cli_never_writes_public_report_and_invalid_input_does_not_create_file(
    monkeypatch, tmp_path,
):
    path = write_json(tmp_path, "source.json", observation_fixture())
    candidate_path = tmp_path / "candidate.json"
    monkeypatch.setattr("sys.argv", [
        "prepare", "--capture", f"44779967482={path}",
        "--source-conclusion", "44779967482=success",
        "--audit-run-id", AUDIT_ID, "--audited-at-utc", DATE,
        "--output", str(candidate_path),
    ])
    assert main() == 0
    assert json.loads(candidate_path.read_text())["total_priced_rows"] == 6
    candidate_path.unlink()
    monkeypatch.setattr("sys.argv", [
        "prepare", "--capture", "44779967482=/nonexistent/file.json",
        "--source-conclusion", "44779967482=success",
        "--audit-run-id", AUDIT_ID, "--audited-at-utc", DATE,
        "--output", str(candidate_path),
    ])
    assert main() == 1
    assert not candidate_path.exists()
    monkeypatch.setattr("sys.argv", [
        "prepare", "--capture", f"44779967482={path}",
        "--source-conclusion", "44779967482=success",
        "--audit-run-id", AUDIT_ID, "--output",
        str(tmp_path / "solana-quality-reviewed.json"),
    ])
    with pytest.raises(ObservationValidationError, match="Refuse direct writing"):
        main()
