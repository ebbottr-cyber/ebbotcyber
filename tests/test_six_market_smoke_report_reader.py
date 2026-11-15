# -*- coding: utf-8 -*-
"""Offline tests: saved six-market smoke needs admin, fingerprint and true sessions."""
from copy import deepcopy
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo
import hashlib
import json

from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest

from api.v1.endpoints import data as endpoint
from src.services import six_market_smoke_report_reader as reader
from src.services.six_market_live_smoke import PROBES


def _example():
    return {
        "scope": "six_market_yahoo_fallback_one_symbol_each",
        "source": "Yahoo Finance", "as_of": "2026-11-15",
        "checked_markets": 6, "analyzed_markets": 6,
        "results": [{
            "market": p.market, "code": p.code, "yahoo_symbol": p.yahoo,
            "currency_expected": p.currency, "currency_observed": p.currency,
            "status": "analyzed", "bars": 80, "technical_score": 71,
            "last_bar_date": "2026-11-13",
            "expected_last_session": "2026-11-13",
        } for p in PROBES],
    }


@pytest.fixture(autouse=True)
def offline_calendar(monkeypatch):
    monkeypatch.setattr(reader, "_last_completed", lambda market, as_of: date(2026, 11, 13))


def _pin(monkeypatch, tmp_path, payload=None):
    raw = json.dumps(_example() if payload is None else payload).encode("utf-8")
    path = tmp_path / "six-market.json"
    path.write_bytes(raw)
    monkeypatch.setenv("SIX_MARKET_SMOKE_REPORT_PATH", str(path))
    monkeypatch.setenv("SIX_MARKET_SMOKE_REPORT_SHA256", hashlib.sha256(raw).hexdigest())
    return path


def test_valid_historical_report_has_only_one_example_per_market(monkeypatch, tmp_path):
    _pin(monkeypatch, tmp_path)
    report = reader.load_configured_six_market_smoke_report()
    assert report["analyzed_markets"] == 6
    assert len(report["results"]) == 6
    assert set(row["market"] for row in report["results"]) == {"cn", "hk", "us", "jp", "kr", "tw"}


def test_missing_config_and_wrong_path_never_create_files(monkeypatch, tmp_path):
    monkeypatch.delenv("SIX_MARKET_SMOKE_REPORT_PATH", raising=False)
    monkeypatch.delenv("SIX_MARKET_SMOKE_REPORT_SHA256", raising=False)
    with pytest.raises(reader.SixMarketSmokeUnavailable):
        reader.load_configured_six_market_smoke_report()
    monkeypatch.setenv("SIX_MARKET_SMOKE_REPORT_PATH", str(tmp_path / "missing.json"))
    monkeypatch.setenv("SIX_MARKET_SMOKE_REPORT_SHA256", "0" * 64)
    with pytest.raises(reader.SixMarketSmokeUnavailable):
        reader.load_configured_six_market_smoke_report()
    assert list(tmp_path.iterdir()) == []


def test_exact_sha256_is_required_and_modified_bytes_fail(monkeypatch, tmp_path):
    path = _pin(monkeypatch, tmp_path)
    path.write_bytes(path.read_bytes() + b"\n")
    with pytest.raises(reader.SixMarketSmokeInvalid, match="SHA-256"):
        reader.load_configured_six_market_smoke_report()
    monkeypatch.setenv("SIX_MARKET_SMOKE_REPORT_SHA256", "BAD-FINGERPRINT")
    with pytest.raises(reader.SixMarketSmokeUnavailable, match="fingerprint"):
        reader.load_configured_six_market_smoke_report()


@pytest.mark.parametrize("mutator", [
    lambda p: p.update(scope="all_markets_complete"),
    lambda p: p.update(checked_markets=100),
    lambda p: p.update(analyzed_markets=5),
    lambda p: p["results"].pop(),
    lambda p: p["results"][1].update(market="cn"),
    lambda p: p["results"][1].update(yahoo_symbol="AAPL"),
    lambda p: p["results"][0].update(currency_observed="HKD"),
    lambda p: p["results"][0].update(bars=59),
    lambda p: p["results"][0].update(technical_score=120),
    lambda p: p["results"][0].update(last_bar_date="2026-11-12"),
    lambda p: p["results"][0].update(expected_last_session="2026-11-12",
                                    last_bar_date="2026-11-12"),
    lambda p: p.update(as_of="2026-11-13"),
    lambda p: p["results"][0].update(status="analyzed", expected_last_session=None),
])
def test_forged_success_or_wrong_one_sample_scope_rejected(mutator):
    value = deepcopy(_example())
    mutator(value)
    with pytest.raises(reader.SixMarketSmokeInvalid):
        reader.validate_six_market_smoke_report(value)


def test_future_dated_report_is_rejected_before_calendar_lookup(monkeypatch):
    future = datetime.now(ZoneInfo("Europe/Istanbul")).date() + timedelta(days=1)
    value = _example()
    value["as_of"] = future.isoformat()
    calls = []

    def should_not_probe(_market, _as_of):
        calls.append((_market, _as_of))
        return date(2026, 11, 13)

    monkeypatch.setattr(reader, "_last_completed", should_not_probe)
    with pytest.raises(reader.SixMarketSmokeInvalid, match="Future as-of"):
        reader.validate_six_market_smoke_report(value)
    assert calls == []


def test_failed_example_with_future_last_bar_cannot_be_presented_as_historical():
    value = _example()
    item = value["results"][0]
    item["status"] = "stale_price"
    item["technical_score"] = None
    item["expected_last_session"] = None
    item["last_bar_date"] = "2026-11-16"
    value["analyzed_markets"] = 5
    with pytest.raises(reader.SixMarketSmokeInvalid, match="Future or same-day"):
        reader.validate_six_market_smoke_report(value)


def test_failed_example_with_same_day_bar_is_not_previous_completed_session():
    value = _example()
    value["results"][2].update(
        status="fetch_error",
        expected_last_session=None,
        last_bar_date="2026-11-15",
        technical_score=None,
    )
    value["analyzed_markets"] = 5
    with pytest.raises(reader.SixMarketSmokeInvalid, match="Future or same-day"):
        reader.validate_six_market_smoke_report(value)


def test_independent_calendar_missing_is_not_success(monkeypatch):
    monkeypatch.setattr(reader, "_last_completed", lambda market, as_of: None)
    with pytest.raises(reader.SixMarketSmokeInvalid, match="calendar"):
        reader.validate_six_market_smoke_report(_example())


def test_partially_failed_report_is_honest_and_remains_six_markets():
    report = _example()
    report["results"][2].update(status="fetch_error")
    report["results"][2].pop("technical_score")
    report["analyzed_markets"] = 5
    validated = reader.validate_six_market_smoke_report(report)
    assert validated["checked_markets"] == 6
    assert validated["analyzed_markets"] == 5
    assert validated["results"][2]["status"] == "fetch_error"


def test_calendar_unavailable_is_unverified_not_analyzed():
    value = _example()
    value["results"][0].update(
        status="calendar_unavailable", expected_last_session=None,
    )
    value["results"][0].pop("technical_score")
    value["analyzed_markets"] = 5
    assert reader.validate_six_market_smoke_report(value)["analyzed_markets"] == 5


def test_symlinked_report_and_ancestor_are_blocked(monkeypatch, tmp_path):
    source = _pin(monkeypatch, tmp_path)
    alias = tmp_path / "shortcut.json"
    alias.symlink_to(source)
    monkeypatch.setenv("SIX_MARKET_SMOKE_REPORT_PATH", str(alias))
    with pytest.raises(reader.SixMarketSmokeUnavailable, match="Symlinks"):
        reader.load_configured_six_market_smoke_report()
    root = tmp_path / "approved"
    root.mkdir()
    actual = root / "example.json"
    actual.write_bytes(source.read_bytes())
    alias_parent = tmp_path / "shortcut"
    alias_parent.symlink_to(root, target_is_directory=True)
    monkeypatch.setenv("SIX_MARKET_SMOKE_REPORT_PATH", str(alias_parent / "example.json"))
    with pytest.raises(reader.SixMarketSmokeUnavailable, match="Symlinks"):
        reader.load_configured_six_market_smoke_report()


def test_endpoint_auth_denies_disabled_and_missing_cookie(monkeypatch, tmp_path):
    _pin(monkeypatch, tmp_path)
    app = FastAPI()
    app.include_router(endpoint.router, prefix="/api/v1/data")
    with TestClient(app) as client:
        monkeypatch.setattr(endpoint, "is_auth_enabled", lambda: False)
        assert client.get("/api/v1/data/six-market/smoke-report").status_code == 404
        monkeypatch.setattr(endpoint, "is_auth_enabled", lambda: True)
        monkeypatch.setattr(endpoint, "verify_session", lambda value: value == "valid")
        assert client.get("/api/v1/data/six-market/smoke-report").status_code == 401
        response = client.get("/api/v1/data/six-market/smoke-report?path=/etc/passwd",
                              cookies={endpoint.COOKIE_NAME: "valid"})
    assert response.status_code == 200
    assert response.json()["analyzed_markets"] == 6
    assert response.headers["cache-control"] == "no-store, private"
    assert response.headers["x-content-type-options"] == "nosniff"
    assert "passwd" not in response.text


def test_endpoint_missing_and_invalid_reports_fail_closed(monkeypatch, tmp_path):
    monkeypatch.setattr(endpoint, "is_auth_enabled", lambda: True)
    monkeypatch.setattr(endpoint, "verify_session", lambda value: True)
    app = FastAPI()
    app.include_router(endpoint.router, prefix="/api/v1/data")
    with TestClient(app) as client:
        monkeypatch.delenv("SIX_MARKET_SMOKE_REPORT_PATH", raising=False)
        monkeypatch.delenv("SIX_MARKET_SMOKE_REPORT_SHA256", raising=False)
        missing = client.get("/api/v1/data/six-market/smoke-report",
                             cookies={endpoint.COOKIE_NAME: "valid"})
        assert missing.status_code == 404

        value = _example()
        value["results"][0]["currency_observed"] = "USD"
        _pin(monkeypatch, tmp_path, value)
        invalid = client.get("/api/v1/data/six-market/smoke-report",
                             cookies={endpoint.COOKIE_NAME: "valid"})
    assert invalid.status_code == 422
    assert "USD" not in invalid.text
