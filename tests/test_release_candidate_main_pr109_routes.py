"""Release-candidate guardrails for the two independent Solana panels.

No wallet, order, provider or scheduled scan is used in these tests.
"""
from __future__ import annotations

import re
from pathlib import Path

from fastapi.routing import APIRoute
from fastapi.testclient import TestClient

from api.app import app


ROOT = Path(__file__).resolve().parents[1]


def test_two_meme_api_namespaces_have_distinct_documented_operations():
    paths = app.openapi()["paths"]
    assert "/api/v1/meme-coins/overview" in paths
    assert "get" in paths["/api/v1/meme-coins/overview"]
    assert "/api/v1/meme-radar/status" in paths
    assert "get" in paths["/api/v1/meme-radar/status"]
    assert "/api/v1/meme-radar/scan" in paths
    assert "post" in paths["/api/v1/meme-radar/scan"]
    # Avoid a silently shadowed route when both legacy and new routers register.
    pairs = [(method, route.path) for route in app.routes if isinstance(route, APIRoute)
             for method in route.methods]
    assert len(pairs) == len(set(pairs)), "Duplicate API method/path registration"


def test_radar_scan_is_disabled_by_default_even_when_both_panels_exist(monkeypatch):
    monkeypatch.delenv("MEME_RADAR_LIVE_ENABLED", raising=False)
    client = TestClient(app)
    status = client.get("/api/v1/meme-radar/status")
    assert status.status_code == 200
    assert status.json()["live_enabled"] is False
    assert status.json()["trading_enabled"] is False
    blocked = client.post("/api/v1/meme-radar/scan", json={"limit": 5})
    assert blocked.status_code == 403
    assert "disabled" in blocked.text.lower()


def test_release_candidate_environment_example_defaults_to_no_scans():
    sample = (ROOT / ".env.example").read_text(encoding="utf-8")
    # Unregistered opt-in keys are safe as commented examples, not active
    # WebUI settings. Absence is intentionally OFF in both services.
    for key in ("MEME_RADAR_LIVE_ENABLED", "MEME_COIN_DISCOVERY_ENABLED"):
        assert re.search(rf"^#\s*{key}=false\s*$", sample, flags=re.MULTILINE | re.IGNORECASE)
        assert not re.search(rf"^{key}\s*=", sample, flags=re.MULTILINE)
    assert re.search(r"^SCHEDULE_ENABLED=false\s*$", sample, flags=re.MULTILINE | re.IGNORECASE)
    assert "LLM_MODELFLARE_PROTOCOL" in sample
    assert "LLM_MODELFLARE_BASE_URL" in sample
    assert "LLM_MODELFLARE_MODELS" in sample


def test_separate_frontend_panel_routes_and_radar_api_paths():
    app_src = (ROOT / "apps/dsa-web/src/App.tsx").read_text(encoding="utf-8")
    radar_client = (ROOT / "apps/dsa-web/src/api/memeRadar.ts").read_text(encoding="utf-8")
    nav = (ROOT / "apps/dsa-web/src/components/layout/SidebarNav.tsx").read_text(encoding="utf-8")
    assert "path: '/meme-coins', element: <MemeCoinPage />" in app_src
    assert "path: '/meme-radar', element: <MemeCoinsPage />" in app_src
    assert "/api/v1/meme-radar/status" in radar_client
    assert "/api/v1/meme-radar/scan" in radar_client
    assert "/api/v1/meme-coins/scan" not in radar_client
    assert "to: '/meme-coins'" in nav
    assert "to: '/meme-radar'" in nav
