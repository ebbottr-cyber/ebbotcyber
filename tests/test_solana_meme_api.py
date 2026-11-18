"""Meme API contract tests; strictly offline."""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.v1.endpoints import meme_coins


@pytest.fixture
def client(monkeypatch):
    monkeypatch.delenv("MEME_RADAR_LIVE_ENABLED", raising=False)
    meme_coins._last_scan = None
    meme_coins._last_scan_at = 0.0
    meme_coins._last_scan_limit = 0
    app = FastAPI()
    app.include_router(meme_coins.router)
    return TestClient(app)


def test_status_is_disabled_by_default(client):
    response = client.get("/status")
    assert response.status_code == 200
    assert response.json()["live_enabled"] is False
    assert response.json()["trading_enabled"] is False


def test_manual_scan_requires_server_opt_in(client):
    assert client.post("/scan", json={"limit": 5}).status_code == 403


def test_manual_scan_limit_validated(client, monkeypatch):
    monkeypatch.setenv("MEME_RADAR_LIVE_ENABLED", "true")
    assert client.post("/scan", json={"limit": 0}).status_code == 422
    assert client.post("/scan", json={"limit": 9}).status_code == 422


def test_scan_is_read_only_and_cached(client, monkeypatch):
    monkeypatch.setenv("MEME_RADAR_LIVE_ENABLED", "true")
    calls = []

    def fake_scan(*, live=False, limit=8):
        calls.append((live, limit))
        return {"enabled": True, "trading_enabled": False, "candidates": [], "errors": []}

    monkeypatch.setattr(meme_coins, "scan", fake_scan)
    first = client.post("/scan", json={"limit": 3})
    second = client.post("/scan", json={"limit": 3})
    assert first.status_code == second.status_code == 200
    assert first.json()["cached"] is False
    assert second.json()["cached"] is True
    assert calls == [(True, 3)]


def test_provider_failure_is_sanitized(client, monkeypatch):
    monkeypatch.setenv("MEME_RADAR_LIVE_ENABLED", "true")

    def failing_scan(*, live=False, limit=8):
        raise RuntimeError("private details")

    monkeypatch.setattr(meme_coins, "scan", failing_scan)
    response = client.post("/scan", json={"limit": 4})
    assert response.status_code == 502
    assert "private details" not in response.text


def test_get_status_never_starts_a_scan(client, monkeypatch):
    def should_not_scan(*, live=False, limit=8):
        raise AssertionError("GET status must not contact market data providers")

    monkeypatch.setattr(meme_coins, "scan", should_not_scan)
    response = client.get("/status")
    assert response.status_code == 200
    assert response.json()["live_enabled"] is False


def test_concurrent_scan_is_rejected_without_provider_calls(client, monkeypatch):
    monkeypatch.setenv("MEME_RADAR_LIVE_ENABLED", "true")
    called = []
    monkeypatch.setattr(meme_coins, "scan", lambda **kwargs: called.append(kwargs))
    assert meme_coins._LOCK.acquire(blocking=False)
    try:
        response = client.post("/scan", json={"limit": 5})
    finally:
        meme_coins._LOCK.release()
    assert response.status_code == 429
    assert called == []
