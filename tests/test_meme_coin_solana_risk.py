"""Offline tests for read-only Solana mint authority and hypothetical cost checks."""
from __future__ import annotations

import json
import math
from unittest.mock import patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.v1.endpoints.meme_coin import router
from src.services import meme_coin_solana_risk as risk

MINT = "So11111111111111111111111111111111111111112"
ALT_MINT = "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v"
PROGRAM = "TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA"


def snapshot(mint_authority=None, freeze_authority=None, owner=PROGRAM, **changes):
    info = {
        "mintAuthority": mint_authority,
        "freezeAuthority": freeze_authority,
        "decimals": 9,
        "supply": "1000000000",
        "isInitialized": True,
    }
    info.update(changes)
    return {
        "context": {"slot": 1234},
        "value": {"owner": owner, "data": {
            "program": "spl-token",
            "parsed": {"type": "mint", "info": info},
        }},
    }


def test_address_validation_rejects_invalid_or_short_keys():
    assert risk.validate_mint(MINT) == MINT
    for bad in ("", "0" * 44, "O" * 44, "a" * 44, "1" * 31, "any.eth", "https://x.y"):
        with pytest.raises(ValueError):
            risk.validate_mint(bad)


def test_authorities_revoked_only_grant_review_status_not_safety():
    # Wrapped SOL is explicitly excluded even when permissions are revoked.
    state = risk.parse_mint_snapshot(MINT, snapshot())
    assert state["status"] == "screened"
    assert state["verdict"] == "blocked"
    assert "excluded_quote_asset" in state["blocking_reasons"]
    assert state["mint_authority_revoked"] is True
    assert state["freeze_authority_revoked"] is True
    assert state["full_safety_verified"] is False
    assert state["tradable"] is False
    assert "sellability" in state["remaining_unverified"]


def test_active_mint_or_freeze_rights_block_research():
    state = risk.parse_mint_snapshot(MINT, snapshot(mint_authority=ALT_MINT, freeze_authority=ALT_MINT))
    assert "mint_authority_active" in state["blocking_reasons"]
    assert "freeze_authority_active" in state["blocking_reasons"]
    assert state["mint_authority_revoked"] is False
    assert state["freeze_authority_revoked"] is False
    assert state["tradable"] is False


def test_token_2022_unknown_owner_and_unparsed_data_fail_closed():
    state = risk.parse_mint_snapshot(MINT, snapshot(owner="TokenzQdBNbLqP5VEhdkAS6EPFLC1PHnBqCXEpPxuEb"))
    assert state["status"] == "unsupported"
    assert state["verdict"] == "blocked"
    assert state["tradable"] is False
    state = risk.parse_mint_snapshot(MINT, {"context": {"slot": 42}, "value": {"owner": PROGRAM, "data": []}})
    assert state["status"] == "unavailable"
    assert state["verdict"] == "unknown"


def test_invalid_or_partial_rpc_data_does_not_imply_revoked_authorities():
    for bad in [
        snapshot(isInitialized="true"),
        snapshot(supply="NaN"),
        snapshot(decimals=True),
        {"context": {"slot": 0}, "value": snapshot()["value"]},
        {"context": {"slot": 12}, "value": None},
    ]:
        result = risk.parse_mint_snapshot(MINT, bad)
        assert result["verdict"] != "review_only"
        assert result["tradable"] is False


def test_disabled_mint_audit_never_queries_network():
    with patch.dict("os.environ", {"MEME_COIN_SOLANA_MINT_AUDIT_ENABLED": "false"}):
        with patch.object(risk, "fetch_mint_account") as fetch:
            result = risk.review_mint(MINT)
    assert result["status"] == "disabled"
    assert result["mint_authority_revoked"] is None
    fetch.assert_not_called()


def test_cached_mint_audit_does_not_leak_mutable_results():
    risk._CACHE.clear()
    with patch.dict("os.environ", {"MEME_COIN_SOLANA_MINT_AUDIT_ENABLED": "true"}):
        with patch.object(risk, "fetch_mint_account", return_value=snapshot()) as fetch:
            first = risk.review_mint(MINT)
            first["blocking_reasons"].clear()
            second = risk.review_mint(MINT)
            assert second["blocking_reasons"] == ["excluded_quote_asset"]
            assert fetch.call_count == 1
    assert second["tradable"] is False


def test_rpc_network_error_fails_closed():
    risk._CACHE.clear()
    with patch.dict("os.environ", {"MEME_COIN_SOLANA_MINT_AUDIT_ENABLED": "true"}):
        with patch.object(risk, "fetch_mint_account", side_effect=RuntimeError("rate limited")):
            result = risk.review_mint(MINT)
    assert result["status"] == "unavailable"
    assert result["mint_authority_revoked"] is None
    assert result["tradable"] is False


def test_hypothetical_cost_model_has_independent_fee_and_impact():
    result = risk.estimate_cpmm_impact(liquidity_usd=100000, order_usd=25, fee_bps=30)
    assert result["model"] == "hypothetical_cpmm_50_50"
    assert math.isclose(result["modeled_fee_usd"], 0.075)
    assert 0 < result["modeled_price_impact_pct"] < 0.1
    assert result["modeled_total_cost_pct"] > result["modeled_price_impact_pct"]
    assert result["modeled_min_output_value_usd"] < result["modeled_output_value_usd"]
    assert result["paper_review_status"] == "research_only"
    assert result["real_quote_available"] is False and result["tradable"] is False


def test_large_order_is_flagged_but_does_not_execute():
    result = risk.estimate_cpmm_impact(liquidity_usd=10000, order_usd=1000)
    assert "excess_model_impact" in result["flags"]
    assert "large_order_vs_liquidity" in result["flags"]
    assert result["paper_review_status"] == "blocked"
    assert result["tradable"] is False


@pytest.mark.parametrize("kwargs", [
    {"liquidity_usd": float("nan"), "order_usd": 25},
    {"liquidity_usd": 9999, "order_usd": 25},
    {"liquidity_usd": 100000, "order_usd": -1},
    {"liquidity_usd": 100000, "order_usd": 25, "fee_bps": 500},
    {"liquidity_usd": 100000, "order_usd": 25, "adverse_slippage_bps": 4000},
])
def test_invalid_model_inputs_rejected(kwargs):
    with pytest.raises(ValueError):
        risk.estimate_cpmm_impact(**kwargs)


def test_api_offline_contracts_and_no_trade_routes():
    app = FastAPI()
    app.include_router(router, prefix="/api/v1/meme-coins")
    client = TestClient(app)
    with patch.dict("os.environ", {"MEME_COIN_SOLANA_MINT_AUDIT_ENABLED": "false"}):
        response = client.get(f"/api/v1/meme-coins/solana/mint-review?mint={MINT}")
    assert response.status_code == 200
    assert response.json()["status"] == "disabled"
    assert response.json()["tradable"] is False
    assert client.get("/api/v1/meme-coins/solana/mint-review?mint=bad").status_code == 422

    estimate = client.get("/api/v1/meme-coins/solana/impact", params={
        "liquidity_usd": 100000, "order_usd": 25,
    })
    assert estimate.status_code == 200, estimate.text
    assert estimate.json()["real_quote_available"] is False
    assert client.get("/api/v1/meme-coins/solana/impact", params={"liquidity_usd": 0}).status_code == 422
    assert client.post("/api/v1/meme-coins/solana/impact", json={}).status_code == 405
    assert not any("order" in getattr(route, "path", "") or "wallet" in getattr(route, "path", "")
                   for route in app.routes)
