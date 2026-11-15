# -*- coding: utf-8 -*-
"""Offline contracts for the opt-in authenticated BIST100 report endpoint."""
from copy import deepcopy
from datetime import date
import json

from fastapi import FastAPI
from fastapi.testclient import TestClient
import pandas as pd
import pytest

from api.v1.endpoints import data as data_endpoint
from src.services import bist100_coverage as coverage
from src.services.bist100_report_reader import (
    CoverageReportInvalid,
    CoverageReportUnavailable,
    load_configured_coverage_report,
    validate_coverage_report,
)


def _report(monkeypatch):
    monkeypatch.setattr(
        coverage, "get_trading_dates", lambda *args: pd.DatetimeIndex(["2026-11-13"])
    )
    frame = pd.DataFrame({
        "date": pd.bdate_range(end="2026-11-13", periods=70),
        "open": [100.0] * 70, "high": [101.0] * 70,
        "low": [99.0] * 70, "close": [100.0] * 70,
        "volume": [1000] * 70,
    })
    return coverage.scan_bist100_history(
        as_of=date(2026, 11, 15),
        symbols=("THYAO.IS", "AKFYE.IS"),
        fetch_history=lambda *args: frame,
        fetch_currency=lambda *args: "TRY",
        delay_seconds=0,
    )


def test_valid_local_report_has_explicit_partial_counts(monkeypatch, tmp_path):
    report = _report(monkeypatch)
    file = tmp_path / "coverage.json"
    file.write_text(json.dumps(report), encoding="utf-8")
    monkeypatch.setenv("BIST100_COVERAGE_REPORT_PATH", str(file))
    parsed = load_configured_coverage_report()
    assert parsed["checked"] == 2
    assert parsed["remaining"] == 98
    assert parsed["ready"] == 2
    assert parsed["complete"] is False
    assert len(parsed["results"]) == 2


def test_missing_relative_and_large_paths_are_unavailable(monkeypatch, tmp_path):
    monkeypatch.delenv("BIST100_COVERAGE_REPORT_PATH", raising=False)
    with pytest.raises(CoverageReportUnavailable):
        load_configured_coverage_report()
    monkeypatch.setenv("BIST100_COVERAGE_REPORT_PATH", "data/coverage.json")
    with pytest.raises(CoverageReportUnavailable):
        load_configured_coverage_report()
    large = tmp_path / "large.json"
    large.write_bytes(b"x" * 2_000_001)
    monkeypatch.setenv("BIST100_COVERAGE_REPORT_PATH", str(large))
    with pytest.raises(CoverageReportUnavailable):
        load_configured_coverage_report()


@pytest.mark.parametrize("mutate", [
    lambda r: r.update(ready=100),
    lambda r: r.update(complete=True),
    lambda r: r["results"][1].update(symbol="THYAO.IS"),
    lambda r: r["results"][0].update(symbol="XU100.IS"),
    lambda r: r["results"][0].update(observed_currency="USD"),
    lambda r: r["results"][0].update(last_bar_date="2026-11-14"),
    lambda r: r["results"][0].update(rows=0),
    lambda r: r.update(as_of="2027-01-01"),
    lambda r: r.update(source="AkShare"),
])
def test_forged_or_mismatched_reports_rejected(monkeypatch, mutate):
    report = deepcopy(_report(monkeypatch))
    mutate(report)
    with pytest.raises(CoverageReportInvalid):
        validate_coverage_report(report)


def test_endpoint_is_disabled_without_auth_and_never_accepts_path_query(monkeypatch, tmp_path):
    report = _report(monkeypatch)
    file = tmp_path / "report.json"
    file.write_text(json.dumps(report), encoding="utf-8")
    monkeypatch.setenv("BIST100_COVERAGE_REPORT_PATH", str(file))
    app = FastAPI()
    app.include_router(data_endpoint.router, prefix="/api/v1/data")
    with TestClient(app) as client:
        monkeypatch.setattr(data_endpoint, "is_auth_enabled", lambda: False)
        assert client.get("/api/v1/data/bist100/coverage").status_code == 404

        monkeypatch.setattr(data_endpoint, "is_auth_enabled", lambda: True)
        monkeypatch.setattr(data_endpoint, "verify_session", lambda v: v == "valid-session")
        assert client.get("/api/v1/data/bist100/coverage").status_code == 401
        response = client.get(
            "/api/v1/data/bist100/coverage?path=/etc/passwd",
            cookies={data_endpoint.COOKIE_NAME: "valid-session"},
        )
        assert response.status_code == 200
        assert response.json()["checked"] == 2
        assert response.headers["cache-control"] == "no-store, private"
        assert "passwd" not in response.text


def test_endpoint_reports_missing_file_without_false_zero(monkeypatch):
    monkeypatch.setenv("BIST100_COVERAGE_REPORT_PATH", "/nonexistent/bist100.json")
    monkeypatch.setattr(data_endpoint, "is_auth_enabled", lambda: True)
    monkeypatch.setattr(data_endpoint, "verify_session", lambda v: True)
    app = FastAPI()
    app.include_router(data_endpoint.router, prefix="/api/v1/data")
    with TestClient(app) as client:
        response = client.get(
            "/api/v1/data/bist100/coverage",
            cookies={data_endpoint.COOKIE_NAME: "session"},
        )
        assert response.status_code == 404
        assert response.json()["detail"] == "BIST100 report not configured"
