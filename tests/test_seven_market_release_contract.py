# -*- coding: utf-8 -*-
"""Final offline release contract for the TWO historical admin report APIs.

This never imports an Actions artifact, downloads prices, calls an LLM, trades,
publishes a report or opens production SQLite. Fixtures have synthetic scores
and explicitly partial BIST coverage. They are not real market observations.
"""
from copy import deepcopy
from datetime import date
import hashlib
import json

from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest

from api.v1.endpoints import data as data_endpoint
from src.services import six_market_smoke_report_reader as six_reader
from tests.test_bist100_technical_report_reader import _report as bist_fixture
from tests.test_six_market_smoke_report_reader import _example as six_fixture


def _save(monkeypatch, tmp_path, *, bist=None, six=None):
    """Create ONLY test-owned, immutable report sources under pytest tmp_path."""
    bist_source = tmp_path / "approved-bist-historical.json"
    six_source = tmp_path / "approved-six-samples-historical.json"
    bist_bytes = json.dumps(bist_fixture() if bist is None else bist).encode("utf-8")
    six_bytes = json.dumps(six_fixture() if six is None else six).encode("utf-8")
    bist_source.write_bytes(bist_bytes)
    six_source.write_bytes(six_bytes)
    monkeypatch.setenv("BIST100_TECHNICAL_REPORT_PATH", str(bist_source))
    monkeypatch.setenv("SIX_MARKET_SMOKE_REPORT_PATH", str(six_source))
    monkeypatch.setenv("SIX_MARKET_SMOKE_REPORT_SHA256", hashlib.sha256(six_bytes).hexdigest())
    return bist_source, six_source


@pytest.fixture
def app_client(monkeypatch):
    """Auth is mocked as an isolated admin boundary, never a live login."""
    monkeypatch.setattr(data_endpoint, "is_auth_enabled", lambda: True)
    monkeypatch.setattr(data_endpoint, "verify_session", lambda cookie: cookie == "approved-admin")
    # Independent exchange-calendar behavior has its own real-provider and
    # mocked deterministic regression tests; pin six historical dates here.
    monkeypatch.setattr(six_reader, "_last_completed", lambda market, as_of: date(2026, 11, 13))
    app = FastAPI()
    app.include_router(data_endpoint.router, prefix="/api/v1/data")
    with TestClient(app) as client:
        yield client


def _get(client, endpoint: str):
    return client.get(
        "/api/v1/data/" + endpoint,
        cookies={data_endpoint.COOKIE_NAME: "approved-admin"},
    )


def test_both_saved_admin_reports_are_independent_and_read_only(
    monkeypatch, tmp_path, app_client
):
    bist_source, six_source = _save(monkeypatch, tmp_path)
    before = {
        str(path): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in (bist_source, six_source)
    }
    bist = _get(app_client, "bist100/technical-ranking")
    six = _get(app_client, "six-market/smoke-report")
    assert bist.status_code == six.status_code == 200
    assert bist.json()["checked"] == 2  # synthetic partial fixture, NOT 100/100
    assert bist.json()["analyzed"] == 1
    assert six.json()["checked_markets"] == 6  # six single-equity examples
    assert six.json()["analyzed_markets"] == 6
    assert all(row["status"] == "analyzed" for row in six.json()["results"])
    for response in (bist, six):
        assert response.headers["cache-control"] == "no-store, private"
    assert six.headers["x-content-type-options"] == "nosniff"
    assert before == {
        str(path): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in (bist_source, six_source)
    }
    assert set(tmp_path.iterdir()) == {bist_source, six_source}


def test_missing_six_report_does_not_hide_valid_bist_report(
    monkeypatch, tmp_path, app_client
):
    _save(monkeypatch, tmp_path)
    monkeypatch.delenv("SIX_MARKET_SMOKE_REPORT_SHA256")
    assert _get(app_client, "six-market/smoke-report").status_code == 404
    assert _get(app_client, "bist100/technical-ranking").status_code == 200


def test_missing_bist_report_does_not_fake_six_market_failure(
    monkeypatch, tmp_path, app_client
):
    _save(monkeypatch, tmp_path)
    monkeypatch.delenv("BIST100_TECHNICAL_REPORT_PATH")
    assert _get(app_client, "bist100/technical-ranking").status_code == 404
    assert _get(app_client, "six-market/smoke-report").status_code == 200


@pytest.mark.parametrize("endpoint", [
    "bist100/technical-ranking", "six-market/smoke-report",
])
def test_both_read_endpoints_fail_closed_without_admin_session(
    monkeypatch, tmp_path, app_client, endpoint
):
    _save(monkeypatch, tmp_path)
    assert app_client.get("/api/v1/data/" + endpoint).status_code == 401
    denied = app_client.get(
        "/api/v1/data/" + endpoint,
        cookies={data_endpoint.COOKIE_NAME: "wrong-session"},
    )
    assert denied.status_code == 401
    monkeypatch.setattr(data_endpoint, "is_auth_enabled", lambda: False)
    assert _get(app_client, endpoint).status_code == 404


@pytest.mark.parametrize("endpoint", [
    "bist100/technical-ranking", "six-market/smoke-report",
])
def test_caller_supplied_file_path_or_scan_request_cannot_redirect_read(
    monkeypatch, tmp_path, app_client, endpoint
):
    _save(monkeypatch, tmp_path)
    result = app_client.get(
        "/api/v1/data/" + endpoint + "?path=/etc/passwd&run_probe=true",
        cookies={data_endpoint.COOKIE_NAME: "approved-admin"},
    )
    assert result.status_code == 200
    assert "passwd" not in result.text
    assert len(list(tmp_path.iterdir())) == 2


def test_repinning_a_forged_six_market_stale_session_remains_422_bist_stays_readable(
    monkeypatch, tmp_path, app_client
):
    forged = deepcopy(six_fixture())
    forged["results"][2]["expected_last_session"] = "2026-11-12"
    forged["results"][2]["last_bar_date"] = "2026-11-12"
    _save(monkeypatch, tmp_path, six=forged)
    # Even if an operator mistakenly pins the forged JSON, the exchange
    # calendar validator must reject its internally matching stale session.
    result = _get(app_client, "six-market/smoke-report")
    assert result.status_code == 422
    assert _get(app_client, "bist100/technical-ranking").status_code == 200


def test_invalid_bist_session_leaves_six_market_example_api_independent(
    monkeypatch, tmp_path, app_client
):
    forged = deepcopy(bist_fixture())
    forged["last_completed_session"] = "2026-11-12"
    forged["ranking"][0]["last_bar_date"] = "2026-11-12"
    forged["results"][0]["last_bar_date"] = "2026-11-12"
    _save(monkeypatch, tmp_path, bist=forged)
    assert _get(app_client, "bist100/technical-ranking").status_code == 422
    assert _get(app_client, "six-market/smoke-report").status_code == 200


def test_mismatched_fingerprint_never_returns_partial_six_market_success(
    monkeypatch, tmp_path, app_client
):
    _save(monkeypatch, tmp_path)
    monkeypatch.setenv("SIX_MARKET_SMOKE_REPORT_SHA256", "0" * 64)
    assert _get(app_client, "six-market/smoke-report").status_code == 422
    assert _get(app_client, "bist100/technical-ranking").status_code == 200
