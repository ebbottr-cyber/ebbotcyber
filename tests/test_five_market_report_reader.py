# -*- coding: utf-8 -*-
"""Offline checks for an authenticated, pre-generated five-market JSON endpoint."""
from copy import deepcopy
from datetime import date
import json

from fastapi import FastAPI
from fastapi.testclient import TestClient
import pandas as pd
import pytest

from api.v1.endpoints import data as endpoint
from src.services.five_market_sample_validation import CORE_PROBES, validate_five_market_samples
from src.services.five_market_report_reader import (
    FiveMarketReportInvalid,
    FiveMarketReportUnavailable,
    load_configured_five_market_sample_report,
    validate_five_market_sample_report,
)


def _report() -> dict:
    markets = {p.code: p.market for p in CORE_PROBES}
    yahoo = {p.code: p.yahoo for p in CORE_PROBES}
    currencies = {p.yahoo: p.currency for p in CORE_PROBES}
    dates = pd.bdate_range(end="2026-11-13", periods=80)
    frame = pd.DataFrame({
        "Date": dates,
        "Open": [95.0 + i / 5 for i in range(80)],
        "High": [99.0 + i / 5 for i in range(80)],
        "Low": [92.0 + i / 5 for i in range(80)],
        "Close": [97.0 + i / 5 for i in range(80)],
        "Volume": [1000.0 + i for i in range(80)],
    })
    return validate_five_market_samples(
        as_of=date(2026, 11, 15),
        fetch_history=lambda *_: frame,
        fetch_currency=currencies.get,
        sessions_for_market=lambda *_: pd.DatetimeIndex(["2026-11-13"]),
        detect_market=markets.get,
        convert_ticker=yahoo.get,
        analyzer=lambda frame, code: type("Result", (), {"signal_score": 70})(),
    )


def test_saved_sample_report_matches_real_five_market_producer(tmp_path, monkeypatch):
    raw = _report()
    path = tmp_path / "five.json"
    path.write_text(json.dumps(raw), encoding="utf-8")
    monkeypatch.setenv("ETRE_FIVE_MARKET_REPORT_PATH", str(path))
    loaded = load_configured_five_market_sample_report()
    assert loaded["checked_symbols"] == 5
    assert loaded["analyzed_symbols"] == 5
    assert loaded["markets_checked"] == 5
    assert loaded["by_market"]["de"]["sample_status"] == "samples_passed"
    assert [x["code"] for x in loaded["results"]] == [p.code for p in CORE_PROBES]
    assert "note" not in loaded  # sanitize ancillary arbitrary text


@pytest.mark.parametrize("corrupt", [
    lambda r: r.update(analyzed_symbols=50),
    lambda r: r.update(markets_checked=3),
    lambda r: r.update(source="unverified"),
    lambda r: r.update(scope="germany_xetra_yahoo_three_equities"),
    lambda r: r.update(market_scope=["tr", "us", "de", "hk", "cn"]),
    lambda r: r["results"][2].update(market="cn"),
    lambda r: r["results"][2].update(code="1234.DE"),
    lambda r: r["results"][1].update(code="THYAO.IS"),
    lambda r: r["results"][2].update(currency_observed="USD"),
    lambda r: r["results"][2].update(last_bar_date="2026-11-12"),
    lambda r: r["results"][2].update(bars=0),
    lambda r: r["results"][2].update(technical_score=150),
    lambda r: r["results"][0].update(status=["analyzed"]),
    lambda r: r["results"][0].update(status="fetch_error"),
    lambda r: r["by_market"]["de"].update(sample_status="samples_failed"),
    lambda r: r["by_market"]["de"].update(checked_symbols=100),
    lambda r: r.update(scope=[]),
    lambda r: r.update(by_market={**r["by_market"], "cn": {}}),
])
def test_untrustworthy_saved_report_rejected(corrupt):
    bad = deepcopy(_report())
    corrupt(bad)
    with pytest.raises(FiveMarketReportInvalid):
        validate_five_market_sample_report(bad)


def test_missing_relative_and_oversized_reports_not_served(monkeypatch, tmp_path):
    monkeypatch.delenv("ETRE_FIVE_MARKET_REPORT_PATH", raising=False)
    with pytest.raises(FiveMarketReportUnavailable):
        load_configured_five_market_sample_report()
    monkeypatch.setenv("ETRE_FIVE_MARKET_REPORT_PATH", "reports/five.json")
    with pytest.raises(FiveMarketReportUnavailable):
        load_configured_five_market_sample_report()
    large = tmp_path / "big.json"
    large.write_bytes(b"x" * 2_000_001)
    monkeypatch.setenv("ETRE_FIVE_MARKET_REPORT_PATH", str(large))
    with pytest.raises(FiveMarketReportUnavailable):
        load_configured_five_market_sample_report()


def test_admin_endpoint_fail_closed_and_no_http_path_selection(monkeypatch, tmp_path):
    report = _report()
    file = tmp_path / "approved.json"
    file.write_text(json.dumps(report), encoding="utf-8")
    monkeypatch.setenv("ETRE_FIVE_MARKET_REPORT_PATH", str(file))
    app = FastAPI()
    app.include_router(endpoint.router, prefix="/api/v1/data")
    with TestClient(app) as client:
        monkeypatch.setattr(endpoint, "is_auth_enabled", lambda: False)
        assert client.get("/api/v1/data/five-market/samples").status_code == 404

        monkeypatch.setattr(endpoint, "is_auth_enabled", lambda: True)
        monkeypatch.setattr(endpoint, "verify_session", lambda value: value == "valid-session")
        assert client.get("/api/v1/data/five-market/samples").status_code == 401
        assert client.get(
            "/api/v1/data/five-market/samples",
            cookies={endpoint.COOKIE_NAME: "invalid"},
        ).status_code == 401

        res = client.get(
            "/api/v1/data/five-market/samples?path=/etc/passwd",
            cookies={endpoint.COOKIE_NAME: "valid-session"},
        )
        assert res.status_code == 200
        assert res.json()["analyzed_symbols"] == 5
        assert res.headers["cache-control"] == "no-store, private"
        assert res.headers["x-content-type-options"] == "nosniff"
        assert "passwd" not in res.text


def test_admin_endpoint_rejects_tampered_or_missing_report(monkeypatch, tmp_path):
    app = FastAPI()
    app.include_router(endpoint.router, prefix="/api/v1/data")
    monkeypatch.setattr(endpoint, "is_auth_enabled", lambda: True)
    monkeypatch.setattr(endpoint, "verify_session", lambda session: True)
    with TestClient(app) as client:
        monkeypatch.delenv("ETRE_FIVE_MARKET_REPORT_PATH", raising=False)
        response = client.get("/api/v1/data/five-market/samples", cookies={
            endpoint.COOKIE_NAME: "session",
        })
        assert response.status_code == 404
        assert response.json()["detail"] == "Five-market report not configured"

        bad = _report()
        bad["results"][0]["technical_score"] = 200
        path = tmp_path / "forged.json"
        path.write_text(json.dumps(bad), encoding="utf-8")
        monkeypatch.setenv("ETRE_FIVE_MARKET_REPORT_PATH", str(path))
        response = client.get("/api/v1/data/five-market/samples", cookies={
            endpoint.COOKIE_NAME: "session",
        })
        assert response.status_code == 422
        assert response.json()["detail"] == "Five-market report failed validation"
