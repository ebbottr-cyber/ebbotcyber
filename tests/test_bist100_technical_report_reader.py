# -*- coding: utf-8 -*-
"""Security/shape tests for the saved BIST100 technical-ranking viewer."""
from copy import deepcopy
import json

from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest

from api.v1.endpoints import data as data_endpoint
from src.services.bist100_technical_report_reader import (
    TechnicalReportInvalid,
    TechnicalReportUnavailable,
    load_configured_technical_report,
    validate_technical_report,
)


def _report():
    analyzed = {
        "symbol": "THYAO.IS", "status": "analyzed", "bars": 80,
        "last_bar_date": "2026-11-13", "score": 72,
        "close_try": 100.0, "ma5_try": 99.0, "ma20_try": 97.0,
        "rsi12": 60.0, "macd_histogram": 1.2345,
        "bias_ma5_pct": 1.01, "trend": "Yükseliş",
        "technical_signal": "Alım sinyali", "chase_risk": False,
        "eligible_for_watchlist": True,
    }
    return {
        "index": "BIST100", "as_of": "2026-11-15",
        "last_completed_session": "2026-11-13", "mode": "read_only_local_sqlite",
        "universe_total": 100, "checked": 2, "remaining": 98,
        "analyzed": 1, "watchlist_eligible": 1,
        "status_counts": {"analyzed": 1, "not_imported": 1},
        "ranking": [{**analyzed, "rank": 1}],
        "results": [analyzed, {"symbol": "AKFYE.IS", "status": "not_imported"}],
        "note": "Historical technical ranking only. No LLM, trades, or investment recommendation.",
    }


def test_saved_report_has_honest_partial_counts(monkeypatch, tmp_path):
    location = tmp_path / "technical.json"
    location.write_text(json.dumps(_report()), encoding="utf-8")
    monkeypatch.setenv("BIST100_TECHNICAL_REPORT_PATH", str(location))
    report = load_configured_technical_report()
    assert report["checked"] == 2
    assert report["analyzed"] == 1
    assert report["remaining"] == 98
    assert report["ranking"][0]["rank"] == 1


def test_unconfigured_relative_and_oversize_paths_are_unavailable(monkeypatch, tmp_path):
    monkeypatch.delenv("BIST100_TECHNICAL_REPORT_PATH", raising=False)
    with pytest.raises(TechnicalReportUnavailable):
        load_configured_technical_report()
    monkeypatch.setenv("BIST100_TECHNICAL_REPORT_PATH", "private/report.json")
    with pytest.raises(TechnicalReportUnavailable):
        load_configured_technical_report()
    big = tmp_path / "big.json"
    big.write_bytes(b"x" * 2_000_001)
    monkeypatch.setenv("BIST100_TECHNICAL_REPORT_PATH", str(big))
    with pytest.raises(TechnicalReportUnavailable):
        load_configured_technical_report()


@pytest.mark.parametrize("mutate", [
    lambda p: p.update(checked=100, remaining=0),
    lambda p: p.update(analyzed=2),
    lambda p: p.update(watchlist_eligible=2),
    lambda p: p.update(as_of="2027-01-01"),
    lambda p: p.update(last_completed_session="2026-11-16"),
    lambda p: p.update(mode="fake_live_analysis"),
    lambda p: p["results"][0].update(symbol="XU100.IS"),
    lambda p: p["results"][1].update(symbol="THYAO.IS"),
    lambda p: p["results"][0].update(bars=12),
    lambda p: p["results"][0].update(score=101),
    lambda p: p["results"][0].update(close_try=float("nan")),
    lambda p: p["results"][0].update(chase_risk=True),
    lambda p: p["results"][0].update(bias_ma5_pct=10.0),
    lambda p: p["ranking"][0].update(rank=10),
    lambda p: p["ranking"][0].update(score=99),
    lambda p: p["status_counts"].update(analyzed=2),
])
def test_inconsistent_or_forged_report_rejected(mutate):
    report = deepcopy(_report())
    mutate(report)
    with pytest.raises(TechnicalReportInvalid):
        validate_technical_report(report)


def test_rejects_spoofed_stale_session_even_when_rows_agree():
    """An internally consistent but outdated report must not pass as current."""
    report = deepcopy(_report())
    report["last_completed_session"] = "2026-11-12"
    report["results"][0]["last_bar_date"] = "2026-11-12"
    report["ranking"][0]["last_bar_date"] = "2026-11-12"
    # Before the calendar gate all report fields were self-consistent.
    with pytest.raises(TechnicalReportInvalid, match="XIST"):
        validate_technical_report(report)


def test_missing_exchange_calendar_never_claims_report_freshness(monkeypatch):
    from src.services import bist100_technical_report_reader as reader

    monkeypatch.setattr(reader, "_last_completed_session", lambda _as_of: None)
    with pytest.raises(TechnicalReportInvalid, match="XIST"):
        validate_technical_report(_report())


def test_verified_last_session_is_stable_across_weekend():
    report = deepcopy(_report())
    report["as_of"] = "2026-11-16"
    assert validate_technical_report(report)["last_completed_session"] == "2026-11-13"


def test_calendar_mismatch_returns_422_not_success(monkeypatch, tmp_path):
    report = deepcopy(_report())
    report["last_completed_session"] = "2026-11-12"
    report["results"][0]["last_bar_date"] = "2026-11-12"
    report["ranking"][0]["last_bar_date"] = "2026-11-12"
    path = tmp_path / "outdated-but-self-consistent.json"
    path.write_text(json.dumps(report), encoding="utf-8")
    monkeypatch.setenv("BIST100_TECHNICAL_REPORT_PATH", str(path))
    monkeypatch.setattr(data_endpoint, "is_auth_enabled", lambda: True)
    monkeypatch.setattr(data_endpoint, "verify_session", lambda _session: True)
    app = FastAPI()
    app.include_router(data_endpoint.router, prefix="/api/v1/data")
    with TestClient(app) as client:
        result = client.get(
            "/api/v1/data/bist100/technical-ranking",
            cookies={data_endpoint.COOKIE_NAME: "valid"},
        )
    assert result.status_code == 422
    assert "XIST" not in result.text


def test_endpoint_requires_admin_auth_and_cannot_choose_local_path(monkeypatch, tmp_path):
    location = tmp_path / "technical.json"
    location.write_text(json.dumps(_report()), encoding="utf-8")
    monkeypatch.setenv("BIST100_TECHNICAL_REPORT_PATH", str(location))
    app = FastAPI()
    app.include_router(data_endpoint.router, prefix="/api/v1/data")
    with TestClient(app) as client:
        monkeypatch.setattr(data_endpoint, "is_auth_enabled", lambda: False)
        assert client.get("/api/v1/data/bist100/technical-ranking").status_code == 404
        monkeypatch.setattr(data_endpoint, "is_auth_enabled", lambda: True)
        monkeypatch.setattr(data_endpoint, "verify_session", lambda s: s == "valid")
        assert client.get("/api/v1/data/bist100/technical-ranking").status_code == 401
        response = client.get(
            "/api/v1/data/bist100/technical-ranking?path=/etc/passwd",
            cookies={data_endpoint.COOKIE_NAME: "valid"},
        )
        assert response.status_code == 200
        assert response.json()["analyzed"] == 1
        assert response.headers["cache-control"] == "no-store, private"
        assert "passwd" not in response.text


def test_missing_or_invalid_saved_report_is_not_falsely_zero(monkeypatch, tmp_path):
    monkeypatch.setattr(data_endpoint, "is_auth_enabled", lambda: True)
    monkeypatch.setattr(data_endpoint, "verify_session", lambda s: True)
    app = FastAPI()
    app.include_router(data_endpoint.router, prefix="/api/v1/data")
    with TestClient(app) as client:
        monkeypatch.setenv("BIST100_TECHNICAL_REPORT_PATH", str(tmp_path / "missing.json"))
        result = client.get(
            "/api/v1/data/bist100/technical-ranking",
            cookies={data_endpoint.COOKIE_NAME: "valid"},
        )
        assert result.status_code == 404
        invalid = tmp_path / "invalid.json"
        invalid.write_text('{"index":"BIST100"}', encoding="utf-8")
        monkeypatch.setenv("BIST100_TECHNICAL_REPORT_PATH", str(invalid))
        result = client.get(
            "/api/v1/data/bist100/technical-ranking",
            cookies={data_endpoint.COOKIE_NAME: "valid"},
        )
        assert result.status_code == 422
