"""Fail-closed contract for the new meme-coin panel."""
from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.v1.endpoints.meme_coin import router
from src.services.meme_coin_strategy_service import get_meme_coin_overview


def test_strategies_are_distinct_and_disconnected():
    first = get_meme_coin_overview()
    assert first["mode"] == "paper_planned"
    assert first["live_trading_enabled"] is False
    assert first["shared_risk_engine_connected"] is False
    assert [item["id"] for item in first["strategies"]] == ["new_launch", "momentum"]
    for strategy in first["strategies"]:
        assert strategy["status"] == "not_connected"
        assert strategy["engine_connected"] is False
        assert strategy["paper_trading_enabled"] is False
        assert strategy["live_trading_enabled"] is False
        assert strategy["metrics"]["trades"] is None
        assert strategy["metrics"]["net_pnl_usd"] is None

    # Returned status is not shared mutable state across requests.
    first["strategies"][0]["status"] = "connected"
    assert get_meme_coin_overview()["strategies"][0]["status"] == "not_connected"


def test_api_exposes_status_without_trading_mutations():
    app = FastAPI()
    app.include_router(router, prefix="/api/v1/meme-coins")
    client = TestClient(app)

    response = client.get("/api/v1/meme-coins/overview")
    assert response.status_code == 200
    payload = response.json()
    assert payload["mode"] == "paper_planned"
    assert len(payload["strategies"]) == 2
    assert payload["strategies"][0]["metrics"]["win_rate_pct"] is None
    assert client.post("/api/v1/meme-coins/overview", json={}).status_code == 405

    routes = [route.path for route in app.routes]
    assert not any("order" in path or "wallet" in path for path in routes)
