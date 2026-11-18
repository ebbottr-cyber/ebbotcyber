"""Offline discovery tests: independent strategies, no wallet/order endpoints."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.v1.endpoints.meme_coin import router
from src.services import meme_coin_discovery as discovery

NOW = datetime(2026, 11, 18, 12, 0, tzinfo=timezone.utc)
TOKEN = "So11111111111111111111111111111111111111112"
POOL = "11111111111111111111111111111111"


def snapshot(*, age=20, reserve=60000, volume=10000, change=9, buys=20, sells=12):
    return {
        "data": [{
            "id": "solana_" + POOL,
            "type": "pool",
            "attributes": {
                "address": POOL,
                "name": "MEME / SOL",
                "pool_created_at": (NOW - timedelta(minutes=age)).isoformat(),
                "reserve_in_usd": str(reserve),
                "volume_usd": {"m5": str(volume)},
                "price_change_percentage": {"m5": str(change)},
                "transactions": {"m5": {"buys": buys, "sells": sells}},
            },
            "relationships": {"base_token": {"data": {"id": "solana_" + TOKEN}}},
        }],
        "included": [{
            "id": "solana_" + TOKEN,
            "type": "token",
            "attributes": {"address": TOKEN, "symbol": "MEME"},
        }],
    }


def test_both_strategies_rank_same_pool_independently_but_not_tradeable():
    a = discovery.rank_candidates("new_launch", snapshot(), now=NOW)
    b = discovery.rank_candidates("momentum", snapshot(), now=NOW)
    assert len(a) == len(b) == 1
    assert a[0]["strategy"] == "new_launch"
    assert b[0]["strategy"] == "momentum"
    assert a[0]["risk_status"] == b[0]["risk_status"] == "unverified"
    assert not a[0]["tradable"] and not b[0]["tradable"]


def test_new_launch_time_limit_and_momentum_volume_filters_are_different():
    assert discovery.rank_candidates("new_launch", snapshot(age=900), now=NOW) == []
    assert discovery.rank_candidates("momentum", snapshot(age=900), now=NOW)
    assert discovery.rank_candidates("momentum", snapshot(volume=300), now=NOW) == []
    assert discovery.rank_candidates("new_launch", snapshot(reserve=5000), now=NOW) == []


def test_missing_fields_nonfinite_values_and_fake_addresses_fail_closed():
    bad = snapshot()
    bad["data"][0]["attributes"]["reserve_in_usd"] = "NaN"
    assert discovery.rank_candidates("new_launch", bad, now=NOW) == []
    bad = snapshot()
    bad["included"][0]["attributes"]["address"] = "https://evil.test/"
    assert discovery.rank_candidates("momentum", bad, now=NOW) == []
    bad = snapshot(sells=0)
    assert discovery.rank_candidates("new_launch", bad, now=NOW) == []


def test_scan_disabled_does_not_contact_provider():
    with patch.dict("os.environ", {"MEME_COIN_DISCOVERY_ENABLED": "false"}):
        with patch.object(discovery, "fetch_json") as fetch:
            result = discovery.scan_strategy("new_launch")
        fetch.assert_not_called()
    assert result["status"] == "disabled"
    assert result["candidates"] == []


def test_scan_provider_error_is_not_misrepresented_as_empty_success():
    discovery._CACHE.clear()
    with patch.dict("os.environ", {"MEME_COIN_DISCOVERY_ENABLED": "true"}):
        with patch.object(discovery, "fetch_json", side_effect=RuntimeError("no network")):
            result = discovery.scan_strategy("momentum")
    assert result["status"] == "unavailable"
    assert result["candidates"] == []
    assert result["observed_at"] is None


def test_scan_uses_cache_independently_per_strategy():
    discovery._CACHE.clear()
    # Current-time snapshot for a valid candidate, using an observed time
    # that is independent from hard-coded NOW in other deterministic tests.
    fresh = snapshot()
    fresh["data"][0]["attributes"]["pool_created_at"] = (
        datetime.now(timezone.utc) - timedelta(minutes=20)
    ).isoformat()
    with patch.dict("os.environ", {"MEME_COIN_DISCOVERY_ENABLED": "true"}):
        with patch.object(discovery, "fetch_json", return_value=fresh) as fetch:
            first = discovery.scan_strategy("new_launch")
            second = discovery.scan_strategy("new_launch")
            third = discovery.scan_strategy("momentum")
    assert first["status"] == second["status"] == third["status"] == "ok"
    assert first["candidates"] and third["candidates"]
    assert fetch.call_count == 2
    assert first["candidates"][0]["tradable"] is False


def test_api_validates_strategy_and_does_not_expose_trade_mutation():
    app = FastAPI()
    app.include_router(router, prefix="/api/v1/meme-coins")
    client = TestClient(app)
    with patch.dict("os.environ", {"MEME_COIN_DISCOVERY_ENABLED": "false"}):
        response = client.get("/api/v1/meme-coins/candidates?strategy=new_launch")
    assert response.status_code == 200
    assert response.json()["status"] == "disabled"
    assert client.get("/api/v1/meme-coins/candidates?strategy=none").status_code == 422
    assert client.post("/api/v1/meme-coins/candidates", json={}).status_code == 405
