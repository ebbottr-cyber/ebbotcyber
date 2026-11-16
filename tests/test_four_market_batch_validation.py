# -*- coding: utf-8 -*-
"""Offline-only test fixtures for sourced, resumable ETRE 4x100 Yahoo batches.

All 400 codes in these tests are invented *test identities*, not actual
listings. No network, broker connection, SQL writes or live order execution.
"""
from __future__ import annotations

from datetime import date
import json
from pathlib import Path
from types import SimpleNamespace

import pandas as pd
import pytest

from src.services.five_market_sample_validation import build_custom_probes
from src.services.four_market_batch_validation import (
    MAX_BATCH_SIZE, combine_batches, load_source_dated_manifest, run_batch,
)
from src.services.five_market_report_reader import validate_five_market_sample_report
from src.services.four_market_batch_progress import inspect_batch_progress


AS_OF = date(2026, 11, 16)
LAST = "2026-11-13"


def _synthetic_codes() -> list[str]:
    # Shape-valid fake tickers only; never report these as an actual universe.
    return (
        [f"T{chr(65 + i // 26)}{chr(65 + i % 26)}A.IS" for i in range(100)]
        + [f"U{chr(65 + i // 26)}{chr(65 + i % 26)}" for i in range(100)]
        + [f"D{i:04d}.DE" for i in range(100)]
        + [f"HK{i + 1:05d}" for i in range(100)]
    )


def _manifest_payload() -> dict:
    symbols = _synthetic_codes()
    return {
        "scope": "etre_four_market_source_dated_universe_plan",
        "as_of": AS_OF.isoformat(),
        "market_scope": ["tr", "us", "de", "hk"],
        "target_symbols_per_market": 100,
        "target_symbols_total": 400,
        "prepared_symbols": 400,
        "remaining_symbols": 0,
        "complete": True,
        "symbols": symbols,
        "markets": {
            market: {
                "status": "roster_provided",
                "count": 100,
                "source_date": AS_OF.isoformat(),
                "source_name": "Synthetic test fixture only",
                "source_url": "https://example.com/test-only",
            }
            for market in ("tr", "us", "de", "hk")
        },
    }


def _file(tmp_path: Path, raw: dict | None = None) -> Path:
    path = tmp_path / "manifest.json"
    path.write_text(json.dumps(_manifest_payload() if raw is None else raw), encoding="utf-8")
    return path


def _frame():
    dates = pd.bdate_range(end=LAST, periods=80)
    return pd.DataFrame({
        "Date": dates,
        "Open": [95.0 + i / 5 for i in range(80)],
        "High": [99.0 + i / 5 for i in range(80)],
        "Low": [92.0 + i / 5 for i in range(80)],
        "Close": [97.0 + i / 5 for i in range(80)],
        "Volume": [1000 + i for i in range(80)],
    })


def _helpers(*, failed: str | None = None):
    fake = _frame()
    specs = build_custom_probes(tuple(_synthetic_codes()))
    currencies = {spec.yahoo: spec.currency for spec in specs}
    calls: list[str] = []
    delays: list[float] = []

    def history(symbol, *_):
        calls.append(symbol)
        if symbol == failed:
            raise ConnectionError("synthetic provider outage")
        return fake

    return {
        "fetch_history": history,
        "fetch_currency": currencies.get,
        "sessions_for_market": lambda market, *_: pd.DatetimeIndex([LAST]),
        "analyzer": lambda *_: SimpleNamespace(signal_score=78),
        "pause": delays.append,
    }, calls, delays


def test_exact_source_dated_complete_manifest_accepted(tmp_path):
    manifest = load_source_dated_manifest(_file(tmp_path), as_of=AS_OF)
    assert len(manifest["symbols"]) == 400
    assert len(manifest["manifest_sha256"]) == 64
    assert manifest["symbols"][0].endswith(".IS")
    assert manifest["symbols"][100].startswith("U")
    assert manifest["symbols"][200].endswith(".DE")
    assert manifest["symbols"][300].startswith("HK")


@pytest.mark.parametrize("tamper", [
    lambda p: p.update(complete=False),
    lambda p: p.update(prepared_symbols=399),
    lambda p: p.update(market_scope=["tr", "us", "de", "jp"]),
    lambda p: p["symbols"].__setitem__(300, "7203.T"),
    lambda p: p["symbols"].__setitem__(300, p["symbols"][299]),
    lambda p: p.update(symbols=p["symbols"][:399]),
    lambda p: p.update(as_of="2026-01-01"),
    lambda p: p["markets"]["de"].update(source_date="2026-01-01"),
    lambda p: p["markets"]["hk"].update(status="source_roster_missing"),
])
def test_incomplete_stale_wrong_market_manifest_refused_before_network(tmp_path, tamper):
    raw = _manifest_payload()
    tamper(raw)
    with pytest.raises(ValueError):
        load_source_dated_manifest(_file(tmp_path, raw), as_of=AS_OF)


def test_single_batch_with_real_report_schema_and_throttle(tmp_path):
    manifest = load_source_dated_manifest(_file(tmp_path), as_of=AS_OF)
    args, calls, delays = _helpers()
    out = tmp_path / "batches"
    report = run_batch(manifest, as_of=AS_OF, batch_index=0,
                       batch_size=10, output_dir=out, delay_seconds=0.01, **args)
    assert report["checked_symbols"] == report["analyzed_symbols"] == 10
    assert report["remaining_to_target"] == 390
    assert report["by_market"]["tr"]["checked_symbols"] == 10
    assert report["by_market"]["de"]["sample_status"] == "not_requested"
    assert len(calls) == 10
    assert delays == [0.01] * 9
    path = out / "batch-001-of-040.json"
    assert path.is_file()
    assert validate_five_market_sample_report(json.loads(path.read_text()))["checked_symbols"] == 10

    # Resume checks the saved report, then skips every Yahoo request.
    resumed = run_batch(manifest, as_of=AS_OF, batch_index=0,
                        batch_size=10, output_dir=out, resume=True,
                        delay_seconds=0.01, **args)
    assert resumed["resumed_without_yahoo_requests"] is True
    assert len(calls) == 10
    with pytest.raises(FileExistsError):
        run_batch(manifest, as_of=AS_OF, batch_index=0,
                  batch_size=10, output_dir=out, **args)


def test_partial_merge_never_implies_400_checked_and_matches_viewer_schema(tmp_path):
    manifest = load_source_dated_manifest(_file(tmp_path), as_of=AS_OF)
    args, _, _ = _helpers()
    out = tmp_path / "batches"
    run_batch(manifest, as_of=AS_OF, batch_index=0,
              batch_size=25, output_dir=out, delay_seconds=0, **args)
    report = combine_batches(manifest, as_of=AS_OF, output_dir=out, batch_size=25)
    assert report["checked_symbols"] == report["analyzed_symbols"] == 25
    assert report["pending_symbols"] == 375
    assert report["checked_all"] is False
    assert report["all_analyzed"] is False
    assert report["completed_batches"] == 1
    assert report["batches_total"] == 16
    assert len(report["missing_batch_indices"]) == 15
    assert report["by_market"]["tr"]["sample_status"] == "samples_passed"
    assert report["by_market"]["us"]["sample_status"] == "not_requested"
    assert validate_five_market_sample_report(report)["checked_symbols"] == 25


def test_400_offline_resumed_batches_produce_one_honest_combined_report(tmp_path):
    manifest = load_source_dated_manifest(_file(tmp_path), as_of=AS_OF)
    args, calls, _ = _helpers()
    out = tmp_path / "batches"
    for n in range(16):
        report = run_batch(manifest, as_of=AS_OF, batch_index=n,
                           batch_size=25, output_dir=out, delay_seconds=0, **args)
        assert report["checked_symbols"] == 25
    merged = combine_batches(manifest, as_of=AS_OF, output_dir=out, batch_size=25)
    assert len(calls) == 400
    assert merged["checked_symbols"] == merged["analyzed_symbols"] == 400
    assert merged["checked_all"] is True
    assert merged["all_analyzed"] is True
    assert merged["pending_symbols"] == 0
    assert merged["missing_batch_indices"] == []
    assert all(v["checked_symbols"] == v["analyzed_symbols"] == 100
               for v in merged["by_market"].values())
    assert validate_five_market_sample_report(merged)["checked_symbols"] == 400


def test_saved_failed_batch_stays_failed_not_hidden(tmp_path):
    manifest = load_source_dated_manifest(_file(tmp_path), as_of=AS_OF)
    first = manifest["symbols"][0]
    args, calls, _ = _helpers(failed=first)
    out = tmp_path / "batches"
    report = run_batch(manifest, as_of=AS_OF, batch_index=0, batch_size=10,
                       output_dir=out, delay_seconds=0, **args)
    assert report["checked_symbols"] == 10
    assert report["analyzed_symbols"] == 9
    assert report["results"][0]["status"] == "fetch_error"
    summary = combine_batches(manifest, as_of=AS_OF, output_dir=out, batch_size=10)
    assert summary["checked_symbols"] == 10
    assert summary["analyzed_symbols"] == 9
    assert summary["by_market"]["tr"]["sample_status"] == "partial"
    assert summary["all_analyzed"] is False


def test_wrong_manifest_hash_and_tampered_success_disallow_resume(tmp_path):
    manifest = load_source_dated_manifest(_file(tmp_path), as_of=AS_OF)
    args, calls, _ = _helpers()
    out = tmp_path / "batches"
    run_batch(manifest, as_of=AS_OF, batch_index=0, batch_size=10,
              output_dir=out, delay_seconds=0, **args)
    path = out / "batch-001-of-040.json"
    raw = json.loads(path.read_text())
    raw["analyzed_symbols"] = 100
    path.write_text(json.dumps(raw))
    with pytest.raises(ValueError):
        run_batch(manifest, as_of=AS_OF, batch_index=0, batch_size=10,
                  output_dir=out, resume=True, delay_seconds=0, **args)
    assert len(calls) == 10
    with pytest.raises(ValueError):
        combine_batches(manifest, as_of=AS_OF, output_dir=out, batch_size=10)


def test_invalid_batch_boundaries_and_empty_report_fail_closed(tmp_path):
    manifest = load_source_dated_manifest(_file(tmp_path), as_of=AS_OF)
    kwargs, _, _ = _helpers()
    for size in (0, MAX_BATCH_SIZE + 1):
        with pytest.raises(ValueError):
            run_batch(manifest, as_of=AS_OF, batch_index=0,
                      batch_size=size, output_dir=tmp_path, **kwargs)
    with pytest.raises(ValueError):
        run_batch(manifest, as_of=AS_OF, batch_index=40,
                  batch_size=10, output_dir=tmp_path, **kwargs)
    result = combine_batches(manifest, as_of=AS_OF,
                             output_dir=tmp_path / "not-yet-generated")
    assert result["checked_symbols"] == 0
    assert result["checked_all"] is False
    assert result["pending_symbols"] == 400


def test_batch_date_mismatch_is_not_resumed(tmp_path):
    manifest = load_source_dated_manifest(_file(tmp_path), as_of=AS_OF)
    kwargs, _, _ = _helpers()
    directory = tmp_path / "batches"
    run_batch(manifest, as_of=AS_OF, batch_index=0,
              batch_size=10, output_dir=directory, delay_seconds=0, **kwargs)
    with pytest.raises(ValueError, match="analysis date"):
        run_batch(manifest, as_of=date(2026, 11, 17), batch_index=0, resume=True,
                  batch_size=10, output_dir=directory, delay_seconds=0, **kwargs)


def test_source_provenance_change_invalidates_old_resume(tmp_path):
    original = load_source_dated_manifest(_file(tmp_path), as_of=AS_OF)
    args, calls, _ = _helpers()
    out = tmp_path / "batches"
    run_batch(original, as_of=AS_OF, batch_index=0, batch_size=10,
              output_dir=out, delay_seconds=0, **args)
    changed = _manifest_payload()
    changed["markets"]["us"]["source_url"] = "https://another-official-source.example/us100"
    other = load_source_dated_manifest(_file(tmp_path, changed), as_of=AS_OF)
    assert other["manifest_sha256"] != original["manifest_sha256"]
    with pytest.raises(ValueError, match="does not belong"):
        run_batch(other, as_of=AS_OF, batch_index=0, batch_size=10,
                  output_dir=out, resume=True, delay_seconds=0, **args)
    assert len(calls) == 10


def test_retry_failed_only_rechecks_unsuccessful_stock_and_preserves_audit(tmp_path):
    manifest = load_source_dated_manifest(_file(tmp_path), as_of=AS_OF)
    first = manifest["symbols"][0]
    args_fail, original_calls, _ = _helpers(failed=first)
    directory = tmp_path / "batches"
    original = run_batch(manifest, as_of=AS_OF, batch_index=0, batch_size=10,
                         output_dir=directory, delay_seconds=0, **args_fail)
    assert original["analyzed_symbols"] == 9
    untouched = original["results"][1:]
    old_path = directory / "batch-001-of-040.json"

    args_ok, new_calls, _ = _helpers()
    retry = run_batch(manifest, as_of=AS_OF, batch_index=0, batch_size=10,
                      output_dir=directory, retry_failed=True,
                      delay_seconds=0, **args_ok)
    assert new_calls == [build_custom_probes((first,))[0].yahoo]
    assert len(original_calls) == 10
    assert retry["retried_symbols"] == 1
    assert retry["retry_attempts"] == 1
    assert retry["checked_symbols"] == retry["analyzed_symbols"] == 10
    assert retry["results"][1:] == untouched

    backup = directory / "batch-001-of-040.before-retry-01.json"
    assert backup.is_file()
    before = json.loads(backup.read_text())
    after = json.loads(old_path.read_text())
    assert before["results"][0]["status"] == "fetch_error"
    assert after["results"][0]["status"] == "analyzed"
    assert after["_retry_attempts"] == 1
    assert after["_batch"] == before["_batch"]
    assert combine_batches(manifest, as_of=AS_OF, output_dir=directory,
                           batch_size=10)["analyzed_symbols"] == 10

    # Already green: an explicit retry invokes no network calls and makes no backup.
    empty_calls: list[str] = []
    args_none, _, _ = _helpers()
    args_none["fetch_history"] = lambda symbol, *_: empty_calls.append(symbol)
    done = run_batch(manifest, as_of=AS_OF, batch_index=0, batch_size=10,
                     output_dir=directory, retry_failed=True, delay_seconds=0, **args_none)
    assert done["retried_symbols"] == 0
    assert empty_calls == []
    assert not (directory / "batch-001-of-040.before-retry-02.json").exists()


def test_retry_of_failed_provider_remains_failed_and_retains_original_evidence(tmp_path):
    manifest = load_source_dated_manifest(_file(tmp_path), as_of=AS_OF)
    first = manifest["symbols"][0]
    fail_args, calls, _ = _helpers(failed=first)
    directory = tmp_path / "batches"
    run_batch(manifest, as_of=AS_OF, batch_index=0, batch_size=10,
              output_dir=directory, delay_seconds=0, **fail_args)
    retry = run_batch(manifest, as_of=AS_OF, batch_index=0, batch_size=10,
                      output_dir=directory, retry_failed=True,
                      delay_seconds=0, **fail_args)
    assert retry["analyzed_symbols"] == 9
    assert retry["results"][0]["status"] == "fetch_error"
    assert retry["retry_attempts"] == 1
    assert len(calls) == 11
    assert (directory / "batch-001-of-040.before-retry-01.json").exists()


def test_retry_requires_existing_valid_batch_and_not_resume_simultaneously(tmp_path):
    manifest = load_source_dated_manifest(_file(tmp_path), as_of=AS_OF)
    args, calls, _ = _helpers()
    directory = tmp_path / "batches"
    with pytest.raises(FileNotFoundError, match="original batch"):
        run_batch(manifest, as_of=AS_OF, batch_index=0, batch_size=10,
                  output_dir=directory, retry_failed=True, delay_seconds=0, **args)
    with pytest.raises(ValueError, match="not both"):
        run_batch(manifest, as_of=AS_OF, batch_index=0, batch_size=10,
                  output_dir=directory, resume=True, retry_failed=True,
                  delay_seconds=0, **args)
    assert calls == []

    failed = manifest["symbols"][0]
    failed_args, _, _ = _helpers(failed=failed)
    run_batch(manifest, as_of=AS_OF, batch_index=0, batch_size=10,
              output_dir=directory, delay_seconds=0, **failed_args)
    path = directory / "batch-001-of-040.json"
    raw = json.loads(path.read_text())
    raw["checked_symbols"] = 50
    path.write_text(json.dumps(raw))
    with pytest.raises(ValueError, match="integrity"):
        run_batch(manifest, as_of=AS_OF, batch_index=0, batch_size=10,
                  output_dir=directory, retry_failed=True, delay_seconds=0, **args)
    assert calls == []
    assert not list(directory.glob("*.before-retry-*.json"))


def test_retry_limit_prevents_endless_provider_requests(tmp_path):
    manifest = load_source_dated_manifest(_file(tmp_path), as_of=AS_OF)
    failed = manifest["symbols"][0]
    args, calls, _ = _helpers(failed=failed)
    directory = tmp_path / "batches"
    run_batch(manifest, as_of=AS_OF, batch_index=0, batch_size=10,
              output_dir=directory, delay_seconds=0, **args)
    for i in range(5):
        retry = run_batch(manifest, as_of=AS_OF, batch_index=0, batch_size=10,
                          output_dir=directory, retry_failed=True,
                          delay_seconds=0, **args)
        assert retry["retry_attempts"] == i + 1
        assert retry["analyzed_symbols"] == 9
    assert len(calls) == 15
    with pytest.raises(ValueError, match="Retry limit"):
        run_batch(manifest, as_of=AS_OF, batch_index=0, batch_size=10,
                  output_dir=directory, retry_failed=True,
                  delay_seconds=0, **args)
    assert len(calls) == 15
    assert len(list(directory.glob("batch-001-of-040.before-retry-*.json"))) == 5


def test_progress_empty_run_has_400_pending_and_no_yahoo_calls(tmp_path):
    manifest = load_source_dated_manifest(_file(tmp_path), as_of=AS_OF)
    report = inspect_batch_progress(
        manifest, as_of=AS_OF, output_dir=tmp_path / "not-created",
        batch_size=10,
    )
    assert report["scope"] == "etre_four_market_batch_progress"
    assert report["checked_symbols"] == report["analyzed_symbols"] == 0
    assert report["pending_symbols"] == 400
    assert report["network_requests"] == 0
    assert report["checked_all"] is False
    assert report["all_analyzed"] is False
    assert report["next_missing_batch_index"] == 0
    assert report["missing_batch_indices"] == list(range(40))
    assert report["invalid_batches"] == []
    assert report["failed_rows"] == []
    assert report["next_action"] == "run_next_missing_batch"
    assert all(v["pending_symbols"] == 100
               for v in report["by_market"].values())


def test_progress_counts_failed_stocks_separately_from_missing_batches(tmp_path):
    manifest = load_source_dated_manifest(_file(tmp_path), as_of=AS_OF)
    directory = tmp_path / "batches"
    success, calls_ok, _ = _helpers()
    run_batch(manifest, as_of=AS_OF, batch_index=0, batch_size=10,
              output_dir=directory, delay_seconds=0, **success)
    fail_code = manifest["symbols"][10]
    failure, calls_failed, _ = _helpers(failed=fail_code)
    run_batch(manifest, as_of=AS_OF, batch_index=1, batch_size=10,
              output_dir=directory, delay_seconds=0, **failure)

    report = inspect_batch_progress(
        manifest, as_of=AS_OF, output_dir=directory, batch_size=10,
    )
    assert report["checked_symbols"] == 20
    assert report["analyzed_symbols"] == 19
    assert report["failed_symbols"] == 1
    assert report["pending_symbols"] == 380
    assert report["verified_batch_indices"] == [0, 1]
    assert report["clean_batch_indices"] == [0]
    assert report["failed_batch_indices"] == [1]
    assert report["missing_batch_indices"] == list(range(2, 40))
    assert report["next_missing_batch_index"] == 2
    assert report["failed_rows"] == [{
        "batch_index": 1, "market": "tr",
        "code": fail_code, "status": "fetch_error",
    }]
    assert report["by_market"]["tr"] == {
        "target_symbols": 100,
        "checked_symbols": 20,
        "analyzed_symbols": 19,
        "failed_symbols": 1,
        "pending_symbols": 80,
    }
    assert report["by_market"]["us"]["checked_symbols"] == 0
    assert report["next_action"] == "run_next_missing_batch"
    assert report["network_requests"] == 0
    assert len(calls_ok) + len(calls_failed) == 20


def test_progress_does_not_count_tampered_batch_or_claim_success(tmp_path):
    manifest = load_source_dated_manifest(_file(tmp_path), as_of=AS_OF)
    directory = tmp_path / "batches"
    args, calls, _ = _helpers()
    run_batch(manifest, as_of=AS_OF, batch_index=0, batch_size=10,
              output_dir=directory, delay_seconds=0, **args)
    path = directory / "batch-001-of-040.json"
    raw = json.loads(path.read_text())
    raw["analyzed_symbols"] = 100
    path.write_text(json.dumps(raw), encoding="utf-8")

    report = inspect_batch_progress(
        manifest, as_of=AS_OF, output_dir=directory, batch_size=10,
    )
    assert report["checked_symbols"] == 0
    assert report["analyzed_symbols"] == 0
    assert report["pending_symbols"] == 400
    assert report["verified_batch_indices"] == []
    assert report["invalid_batches"][0]["batch_index"] == 0
    assert report["invalid_batches"][0]["filename"] == path.name
    assert report["next_action"] == "inspect_invalid_batches"
    assert report["missing_batch_indices"] == list(range(1, 40))
    assert len(calls) == 10


def test_progress_after_selective_recovery_removes_failure_without_new_full_batch(tmp_path):
    manifest = load_source_dated_manifest(_file(tmp_path), as_of=AS_OF)
    directory = tmp_path / "batches"
    failed = manifest["symbols"][0]
    bad, first_calls, _ = _helpers(failed=failed)
    run_batch(manifest, as_of=AS_OF, batch_index=0, batch_size=10,
              output_dir=directory, delay_seconds=0, **bad)
    before = inspect_batch_progress(
        manifest, as_of=AS_OF, output_dir=directory, batch_size=10,
    )
    assert before["failed_batch_indices"] == [0]
    assert before["failed_symbols"] == 1
    good, retry_calls, _ = _helpers()
    run_batch(manifest, as_of=AS_OF, batch_index=0, batch_size=10,
              output_dir=directory, retry_failed=True,
              delay_seconds=0, **good)
    after = inspect_batch_progress(
        manifest, as_of=AS_OF, output_dir=directory, batch_size=10,
    )
    assert after["clean_batch_indices"] == [0]
    assert after["failed_batch_indices"] == []
    assert after["failed_symbols"] == 0
    assert after["analyzed_symbols"] == 10
    assert after["pending_symbols"] == 390
    assert len(first_calls) == 10
    assert len(retry_calls) == 1


def test_progress_rejects_invalid_requested_batch_size(tmp_path):
    manifest = load_source_dated_manifest(_file(tmp_path), as_of=AS_OF)
    for size in (0, 26):
        with pytest.raises(ValueError, match="batch_size"):
            inspect_batch_progress(
                manifest, as_of=AS_OF, output_dir=tmp_path, batch_size=size,
            )
