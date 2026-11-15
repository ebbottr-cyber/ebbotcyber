# -*- coding: utf-8 -*-
"""Stable offline acceptance: both market evidence endpoints share admin auth.

All fixtures are intentionally synthetic deterministic records. Actual
historical Yahoo BIST100 (100 symbols) and offshore 6 samples are separately
verified by short-lived PR #15 and PR #22 GitHub Actions. This long-lived test
never downloads price data, publishes user files, opens SQLite or trades.
"""
from datetime import date
import hashlib
import json

from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest

from api.v1.endpoints import data as endpoint
from src.services import six_market_smoke_report_reader as six_reader
from tests.test_bist100_technical_report_reader import _report as bist_report
from tests.test_six_market_smoke_report_reader import _example as six_report


BIST_PATH = "/api/v1/data/bist100/technical-ranking"
SIX_PATH = "/api/v1/data/six-market/smoke-report"


@pytest.fixture
def saved_reports(monkeypatch, tmp_path):
    """Use configured, SHA256-pinned files only in pytest's temporary directory."""
    bist_path = tmp_path / "approved-bist100-historical.json"
    bist_path.write_text(json.dumps(bist_report()), encoding="utf-8")
    monkeypatch.setenv("BIST100_TECHNICAL_REPORT_PATH", str(bist_path))

    six_path = tmp_path / "approved-six-samples-historical.json"
    raw = json.dumps(six_report()).encode("utf-8")
    six_path.write_bytes(raw)
    monkeypatch.setenv("SIX_MARKET_SMOKE_REPORT_PATH", str(six_path))
    monkeypatch.setenv("SIX_MARKET_SMOKE_REPORT_SHA256", hashlib.sha256(raw).hexdigest())
    monkeypatch.setattr(six_reader, "_last_completed", lambda _market, _as_of: date(2026, 11, 13))

    before = {item.name: item.read_bytes() for item in tmp_path.iterdir()}
    app = FastAPI()
    app.include_router(endpoint.router, prefix="/api/v1/data")
    with TestClient(app) as client:
        yield client, monkeypatch, tmp_path
    after = {item.name: item.read_bytes() for item in tmp_path.iterdir()}
    assert after == before, "Evidence GET must not change or generate files"


def test_both_historical_data_endpoints_require_same_admin_cookie(saved_reports):
    client, monkeypatch, _ = saved_reports
    monkeypatch.setattr(endpoint, "is_auth_enabled", lambda: False)
    for route in (BIST_PATH, SIX_PATH):
        assert client.get(route).status_code == 404

    monkeypatch.setattr(endpoint, "is_auth_enabled", lambda: True)
    monkeypatch.setattr(endpoint, "verify_session", lambda cookie: cookie == "approved-admin")
    for route in (BIST_PATH, SIX_PATH):
        assert client.get(route).status_code == 401
        assert client.get(route, cookies={endpoint.COOKIE_NAME: "wrong"}).status_code == 401


def test_one_authorized_admin_reads_distinct_scope_and_actual_saved_counts(saved_reports):
    client, monkeypatch, _ = saved_reports
    monkeypatch.setattr(endpoint, "is_auth_enabled", lambda: True)
    monkeypatch.setattr(endpoint, "verify_session", lambda cookie: cookie == "approved-admin")
    cookie = {endpoint.COOKIE_NAME: "approved-admin"}

    bist = client.get(BIST_PATH + "?path=/etc/passwd&symbols=all", cookies=cookie)
    six = client.get(SIX_PATH + "?path=/etc/passwd&run_probe=true", cookies=cookie)
    assert bist.status_code == 200
    assert six.status_code == 200
    assert bist.headers["cache-control"] == six.headers["cache-control"] == "no-store, private"

    tr = bist.json()
    foreign = six.json()
    assert tr["index"] == "BIST100"
    assert tr["universe_total"] == 100
    assert tr["checked"] == 2 and tr["analyzed"] == 1
    assert foreign["scope"] == "six_market_yahoo_fallback_one_symbol_each"
    assert foreign["checked_markets"] == foreign["analyzed_markets"] == 6
    assert {item["market"] for item in foreign["results"]} == {
        "cn", "hk", "us", "jp", "kr", "tw",
    }
    assert all(item["bars"] == 80 for item in foreign["results"])
    assert "passwd" not in bist.text and "passwd" not in six.text


def test_missing_bist_report_never_erases_approved_six_market_evidence(saved_reports):
    client, monkeypatch, _ = saved_reports
    monkeypatch.setattr(endpoint, "is_auth_enabled", lambda: True)
    monkeypatch.setattr(endpoint, "verify_session", lambda _cookie: True)
    monkeypatch.delenv("BIST100_TECHNICAL_REPORT_PATH")
    cookie = {endpoint.COOKIE_NAME: "approved"}
    assert client.get(BIST_PATH, cookies=cookie).status_code == 404
    six = client.get(SIX_PATH, cookies=cookie)
    assert six.status_code == 200
    assert six.json()["analyzed_markets"] == 6


def test_bad_offshore_fingerprint_does_not_poison_bist_historical_report(saved_reports):
    client, monkeypatch, _ = saved_reports
    monkeypatch.setattr(endpoint, "is_auth_enabled", lambda: True)
    monkeypatch.setattr(endpoint, "verify_session", lambda _cookie: True)
    monkeypatch.setenv("SIX_MARKET_SMOKE_REPORT_SHA256", "a" * 64)
    cookie = {endpoint.COOKIE_NAME: "approved"}
    assert client.get(SIX_PATH, cookies=cookie).status_code == 422
    bist = client.get(BIST_PATH, cookies=cookie)
    assert bist.status_code == 200
    assert bist.json()["analyzed"] == 1
