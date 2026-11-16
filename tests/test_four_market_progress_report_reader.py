# -*- coding: utf-8 -*-
"""No-network tests for admin-only, operator-configured Yahoo batch progress."""
from copy import deepcopy
from datetime import date
import json

from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest

from api.v1.endpoints import data as endpoint
from src.services.four_market_progress_report_reader import (
    FourMarketProgressInvalid,
    FourMarketProgressUnavailable,
    load_configured_four_market_batch_progress,
    validate_four_market_batch_progress,
)
from src.services.four_market_batch_progress import inspect_batch_progress
from src.services.four_market_batch_validation import (
    load_source_dated_manifest,
    run_batch,
)
from tests.test_four_market_batch_validation import _file, _helpers

AS_OF = date(2026, 11, 16)
KEY = "ETRE_FOUR_MARKET_PROGRESS_PATH"


def _progress(tmp_path, *, failed=False):
    manifest = load_source_dated_manifest(_file(tmp_path), as_of=AS_OF)
    batches = tmp_path / "batches"
    kwargs, _, _ = _helpers(failed=manifest["symbols"][0] if failed else None)
    run_batch(
        manifest, as_of=AS_OF, batch_index=0, batch_size=10,
        output_dir=batches, delay_seconds=0, **kwargs,
    )
    return inspect_batch_progress(
        manifest, as_of=AS_OF, output_dir=batches, batch_size=10,
    )


def _app():
    app = FastAPI()
    app.include_router(endpoint.router, prefix="/api/v1/data")
    return TestClient(app)


def test_valid_operator_progress_matches_generated_batch_report(tmp_path, monkeypatch):
    raw = _progress(tmp_path, failed=True)
    path = tmp_path / "progress.json"
    raw["private_secret"] = "do-not-expose"
    path.write_text(json.dumps(raw), encoding="utf-8")
    monkeypatch.setenv(KEY, str(path))
    report = load_configured_four_market_batch_progress()
    assert report["checked_symbols"] == 10
    assert report["analyzed_symbols"] == 9
    assert report["failed_symbols"] == 1
    assert report["pending_symbols"] == 390
    assert report["failed_rows"][0]["market"] == "tr"
    assert report["verified_batch_indices"] == [0]
    assert report["missing_batch_indices"] == list(range(1, 40))
    assert report["by_market"]["tr"]["checked_symbols"] == 10
    assert "private_secret" not in report
    assert "note" not in report


@pytest.mark.parametrize("tamper", [
    lambda p: p.update(scope="old_five_market_batch_progress"),
    lambda p: p.update(checked_symbols=400),
    lambda p: p.update(analyzed_symbols=10),
    lambda p: p.update(pending_symbols=0),
    lambda p: p.update(network_requests=100),
    lambda p: p.update(target_symbols_total=500),
    lambda p: p.update(checked_all=True),
    lambda p: p.update(all_analyzed=True),
    lambda p: p.update(market_scope=["tr", "us", "de", "jp"]),
    lambda p: p.update(as_of="2026-11-31"),
    lambda p: p.update(manifest_sha256="fakehash"),
    lambda p: p.update(verified_batch_indices=[0, 0]),
    lambda p: p.update(clean_batch_indices=[0]),
    lambda p: p.update(missing_batch_indices=list(range(40))),
    lambda p: p.update(next_missing_batch_index=999),
    lambda p: p["by_market"]["de"].update(checked_symbols=10),
    lambda p: p["by_market"]["tr"].update(analyzed_symbols=10),
    lambda p: p["by_market"]["tr"].update(failed_symbols=0),
    lambda p: p.update(failed_rows=[]),
    lambda p: p["failed_rows"][0].update(code="7203.T"),
    lambda p: p["failed_rows"][0].update(status="analyzed"),
    lambda p: p["failed_rows"][0].update(batch_index=30),
    lambda p: p.update(next_action="all_samples_passed"),
    lambda p: p.update(invalid_batches=[{"batch_index": 0, "filename": "fake", "reason": "x"}]),
])
def test_tampered_progress_fails_closed(tmp_path, tamper):
    raw = deepcopy(_progress(tmp_path, failed=True))
    tamper(raw)
    with pytest.raises(FourMarketProgressInvalid):
        validate_four_market_batch_progress(raw)


def test_operator_path_missing_relative_symlink_and_oversized(tmp_path, monkeypatch):
    monkeypatch.delenv(KEY, raising=False)
    with pytest.raises(FourMarketProgressUnavailable):
        load_configured_four_market_batch_progress()
    monkeypatch.setenv(KEY, "reports/progress.json")
    with pytest.raises(FourMarketProgressUnavailable):
        load_configured_four_market_batch_progress()
    too_large = tmp_path / "huge.json"
    too_large.write_bytes(b"x" * 2_000_001)
    monkeypatch.setenv(KEY, str(too_large))
    with pytest.raises(FourMarketProgressUnavailable):
        load_configured_four_market_batch_progress()
    real = tmp_path / "real.json"
    real.write_text(json.dumps(_progress(tmp_path)), encoding="utf-8")
    symlink = tmp_path / "symlink.json"
    try:
        symlink.symlink_to(real)
    except (OSError, NotImplementedError):
        pytest.skip("Symlinks not available on this platform")
    monkeypatch.setenv(KEY, str(symlink))
    with pytest.raises(FourMarketProgressUnavailable):
        load_configured_four_market_batch_progress()


def test_api_requires_admin_and_ignores_query_path(tmp_path, monkeypatch):
    raw = _progress(tmp_path)
    path = tmp_path / "approved-progress.json"
    path.write_text(json.dumps(raw), encoding="utf-8")
    monkeypatch.setenv(KEY, str(path))

    with _app() as client:
        monkeypatch.setattr(endpoint, "is_auth_enabled", lambda: False)
        assert client.get("/api/v1/data/four-market/batch-progress").status_code == 404

        monkeypatch.setattr(endpoint, "is_auth_enabled", lambda: True)
        monkeypatch.setattr(endpoint, "verify_session", lambda value: value == "valid")
        assert client.get("/api/v1/data/four-market/batch-progress").status_code == 401
        client.cookies.set(endpoint.COOKIE_NAME, "bad")
        assert client.get("/api/v1/data/four-market/batch-progress").status_code == 401
        client.cookies.set(endpoint.COOKIE_NAME, "valid")
        response = client.get("/api/v1/data/four-market/batch-progress?path=/etc/passwd")
        assert response.status_code == 200
        assert response.json()["checked_symbols"] == 10
        assert "passwd" not in response.text
        assert response.headers["cache-control"] == "no-store, private"
        assert response.headers["x-content-type-options"] == "nosniff"
        assert response.json()["network_requests"] == 0


def test_api_missing_or_malformed_progress_statuses(tmp_path, monkeypatch):
    with _app() as client:
        monkeypatch.setattr(endpoint, "is_auth_enabled", lambda: True)
        monkeypatch.setattr(endpoint, "verify_session", lambda _: True)
        client.cookies.set(endpoint.COOKIE_NAME, "valid")
        monkeypatch.delenv(KEY, raising=False)
        response = client.get("/api/v1/data/four-market/batch-progress")
        assert response.status_code == 404
        assert response.json()["detail"] == "Four-market progress not configured"

        raw = _progress(tmp_path)
        raw["analyzed_symbols"] = 400
        invalid = tmp_path / "forged.json"
        invalid.write_text(json.dumps(raw), encoding="utf-8")
        monkeypatch.setenv(KEY, str(invalid))
        response = client.get("/api/v1/data/four-market/batch-progress")
        assert response.status_code == 422
        assert response.json()["detail"] == "Four-market progress failed validation"
