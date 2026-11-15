# -*- coding: utf-8 -*-
"""Exact archived six-market Yahoo probe -> approved API proof.

Run ONLY with the original 2026-11-15 GitHub Actions artifact downloaded into
the temporary CI runner. This is historical 1-stock-per-exchange evidence, not
full equity coverage, a production import, a live quote, or a trade.

Intentionally located outside tests/: default offline CI has no artifact.
"""
from copy import deepcopy
from datetime import date
import hashlib
import json
import os
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest

from api.v1.endpoints import data as data_endpoint
from src.services.six_market_live_smoke import PROBES
from src.services.six_market_smoke_report_reader import (
    SixMarketSmokeInvalid,
    load_configured_six_market_smoke_report,
    validate_six_market_smoke_report,
    _last_completed,
)

EXPECTED_SHA256 = "e2a4f357add80d7dc11ec305aab7a2fa0707f583763db36258c89cddd84d6bd2"
EXPECTED_AS_OF = "2026-11-15"
EXPECTED_SESSION = date(2026, 11, 13)


@pytest.fixture(scope="module")
def saved_real_report():
    source = os.environ.get("SIX_MARKET_REAL_SOURCE")
    if not source:
        pytest.fail("SIX_MARKET_REAL_SOURCE required: original archived Yahoo artifact missing")
    path = Path(source)
    raw = path.read_bytes()
    digest = hashlib.sha256(raw).hexdigest()
    assert digest == EXPECTED_SHA256, "Do not substitute a synthetic or modified six-market source"
    return json.loads(raw.decode("utf-8"))


def test_original_source_contains_exactly_six_historically_analyzed_samples(saved_real_report):
    report = saved_real_report
    assert report["scope"] == "six_market_yahoo_fallback_one_symbol_each"
    assert report["source"] == "Yahoo Finance"
    assert report["as_of"] == EXPECTED_AS_OF
    assert report["checked_markets"] == report["analyzed_markets"] == 6
    assert len(report["results"]) == 6
    assert [(row["market"], row["code"], row["yahoo_symbol"], row["currency_expected"])
            for row in report["results"]] == [
        (spec.market, spec.code, spec.yahoo, spec.currency) for spec in PROBES
    ]
    assert all(row["status"] == "analyzed" and row["bars"] >= 60 for row in report["results"])
    assert all(row["expected_last_session"] == EXPECTED_SESSION.isoformat() and
               row["last_bar_date"] == EXPECTED_SESSION.isoformat() for row in report["results"])


def test_archived_report_passes_actual_independent_six_exchange_calendars(saved_real_report):
    as_of = date.fromisoformat(saved_real_report["as_of"])
    assert all(_last_completed(spec.market, as_of) == EXPECTED_SESSION for spec in PROBES), (
        "Historical calendar not independently verified for every market"
    )
    verified = validate_six_market_smoke_report(saved_real_report)
    assert verified["analyzed_markets"] == 6


def test_real_bytes_read_from_pinned_server_path_then_authenticated_api(
    saved_real_report, monkeypatch,
):
    path = Path(os.environ["SIX_MARKET_REAL_SOURCE"])
    monkeypatch.setenv("SIX_MARKET_SMOKE_REPORT_PATH", str(path))
    monkeypatch.setenv("SIX_MARKET_SMOKE_REPORT_SHA256", EXPECTED_SHA256)
    assert load_configured_six_market_smoke_report() == saved_real_report

    monkeypatch.setattr(data_endpoint, "is_auth_enabled", lambda: True)
    monkeypatch.setattr(data_endpoint, "verify_session", lambda session: session == "authorized")
    app = FastAPI()
    app.include_router(data_endpoint.router, prefix="/api/v1/data")
    with TestClient(app) as client:
        no_auth = client.get("/api/v1/data/six-market/smoke-report")
        assert no_auth.status_code == 401
        approved = client.get(
            "/api/v1/data/six-market/smoke-report?path=/tmp/other.json&run_probe=true",
            cookies={data_endpoint.COOKIE_NAME: "authorized"},
        )
        assert approved.status_code == 200
        assert approved.json() == saved_real_report
        assert approved.headers["cache-control"] == "no-store, private"
        assert approved.headers["x-content-type-options"] == "nosniff"
        assert "other.json" not in approved.text


def test_real_historical_source_cannot_pass_if_one_session_is_rewritten(saved_real_report):
    forged = deepcopy(saved_real_report)
    forged["results"][0]["expected_last_session"] = "2026-11-12"
    forged["results"][0]["last_bar_date"] = "2026-11-12"
    with pytest.raises(SixMarketSmokeInvalid, match="exchange calendar"):
        validate_six_market_smoke_report(forged)


def test_original_report_never_fabricates_full_market_analysis(saved_real_report):
    report = validate_six_market_smoke_report(saved_real_report)
    assert report["checked_markets"] == 6
    assert len(report["results"]) == 6
    assert "one_symbol_each" in report["scope"]
    assert all("bars" in row and row["status"] == "analyzed" for row in report["results"])
