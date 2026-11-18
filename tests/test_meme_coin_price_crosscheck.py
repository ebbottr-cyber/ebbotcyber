"""Offline tests for manual Solana dual-source price comparison (no orders)."""
from __future__ import annotations

from copy import deepcopy
from unittest.mock import patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.v1.endpoints.meme_coin import router
from src.services import meme_coin_price_crosscheck as marks
from src.services.meme_coin_jupiter_quotes import normalize_quote, USDC_MINT

MINT = "11111111111111111111111111111111"
POOL = "So11111111111111111111111111111111111111112"
PROGRAM = "TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA"
NOW = 1_800_000_000_000


def fixtures(jup_usd_raw="20000000", dex_price="2.00", liquidity=60000, amount_raw=10_000_000):
    request = {
        "source": "jupiter_swap_v2_order_quote_only",
        "strategy": "new_launch", "mint": MINT, "side": "sell",
        "input_mint": MINT, "output_mint": USDC_MINT,
        "amount_in_raw": str(amount_raw),
    }
    provider = {
        "inAmount": str(amount_raw), "outAmount": jup_usd_raw,
        "router": "metis", "feeBps": 5, "transaction": None,
    }
    quote = normalize_quote(request, provider, observed_at_ms=NOW)
    response = {**request, "status": "ok", "quote": quote, "tradable": False}
    dex = {"pairs": [{
        "chainId": "solana", "pairAddress": POOL, "dexId": "orca",
        "baseToken": {"address": MINT}, "quoteToken": {"address": USDC_MINT},
        "priceUsd": dex_price, "liquidity": {"usd": liquidity},
    }]}
    mint = {"context": {"slot": 150000}, "value": {
        "owner": PROGRAM, "data": {"program": "spl-token", "parsed": {
            "type": "mint", "info": {
                "decimals": 6, "supply": "100000000000",
                "mintAuthority": None, "freezeAuthority": None, "isInitialized": True,
            },
        }},
    }}
    return response, dex, mint


def check(response=None, dex=None, mint=None, amount_raw=10_000_000, **kwargs):
    example = fixtures(amount_raw=amount_raw)
    return marks.assess_sources(
        "new_launch", MINT, POOL, amount_raw,
        response if response is not None else example[0],
        dex if dex is not None else example[1],
        mint if mint is not None else example[2],
        dex_retrieved_at_ms=NOW + 200,
        assessed_at_ms=NOW + 400,
        **kwargs,
    )


def test_matching_prices_research_only_not_a_safety_or_sellability_clearance():
    result = check()
    assert result["status"] == "screened"
    assert result["verdict"] == "comparison_only"
    assert result["jupiter_price_usd"] == "2.000000000000"
    assert result["dexscreener_price_usd"] == "2.00"
    assert result["price_divergence_pct"] == "0.0000"
    assert result["sample_quoted_usd"] == "20"
    assert result["token_decimals"] == 6
    assert result["mint_slot"] == 150000
    assert result["quote_capture_id"]
    for key in (
        "source_independence_verified", "dex_market_observation_timestamp_verified",
        "token_safety_verified", "sell_fill_verified",
        "mark_to_market_execution_verified", "automated_paper_marks_enabled",
        "live_trading_enabled", "tradable",
    ):
        assert result[key] is False


def test_large_spread_is_flagged_and_not_eligible_for_automatic_paper_marks():
    result = check(response=fixtures(jup_usd_raw="17000000")[0])
    assert result["status"] == "screened"
    assert result["verdict"] == "flagged"
    assert "price_sources_diverge_over_10pct" in result["warning_flags"]
    assert result["automated_paper_marks_enabled"] is False


def test_exact_ten_percent_divergence_is_allowed_but_no_safety_pass():
    result = check(response=fixtures(jup_usd_raw="18000000")[0])
    assert result["price_divergence_pct"] == "10.0000"
    assert result["verdict"] == "comparison_only"
    assert result["tradable"] is False


def test_low_liquidity_and_oversized_samples_flag_independently():
    low = check(dex=fixtures(liquidity=9999)[1])
    assert low["verdict"] == "flagged"
    assert "low_reported_pool_liquidity" in low["warning_flags"]
    oversized = check(dex=fixtures(liquidity=10000)[1])
    assert "quote_sample_exceeds_half_percent_of_reported_liquidity" not in oversized["warning_flags"]
    # 30 tokens * $2 = $60 > 0.5% of 10k (=50 USD)
    sample = check(response=fixtures(amount_raw=30_000_000, jup_usd_raw="60000000")[0],
                   dex=fixtures(liquidity=10000)[1], amount_raw=30_000_000)
    assert sample["verdict"] == "flagged"
    assert "quote_sample_exceeds_half_percent_of_reported_liquidity" in sample["warning_flags"]


def test_mint_with_active_authority_causes_warning_not_clearance():
    resp, dex, mint = fixtures()
    mint["value"]["data"]["parsed"]["info"]["freezeAuthority"] = PROGRAM
    state = check(mint=mint)
    assert state["verdict"] == "flagged"
    assert "mint_authority_or_initialization_warning" in state["warning_flags"]


@pytest.mark.parametrize("mutation", [
    "wrong_pair", "wrong_chain", "wrong_base_mint", "duplicate_pair",
    "missing_price", "bad_price", "missing_liquidity", "negative_liquidity",
    "capture_tamper", "jupiter_unavailable", "wrong_swap_side",
    "wrong_quote_mint", "wrong_quote_input", "bad_decimals",
    "missing_mint", "missing_quote", "missing_dex_pairs",
])
def test_broken_identity_or_untrusted_snapshot_fails_closed(mutation):
    resp, dex, mint = fixtures()
    if mutation == "wrong_pair":
        dex["pairs"][0]["pairAddress"] = MINT
    elif mutation == "wrong_chain":
        dex["pairs"][0]["chainId"] = "ethereum"
    elif mutation == "wrong_base_mint":
        dex["pairs"][0]["baseToken"]["address"] = POOL
    elif mutation == "duplicate_pair":
        dex["pairs"].append(deepcopy(dex["pairs"][0]))
    elif mutation == "missing_price":
        dex["pairs"][0].pop("priceUsd")
    elif mutation == "bad_price":
        dex["pairs"][0]["priceUsd"] = "NaN"
    elif mutation == "missing_liquidity":
        dex["pairs"][0]["liquidity"] = None
    elif mutation == "negative_liquidity":
        dex["pairs"][0]["liquidity"]["usd"] = -10
    elif mutation == "capture_tamper":
        resp["quote"]["amount_out_raw"] = "25000000"
    elif mutation == "jupiter_unavailable":
        resp["status"] = "unavailable"
    elif mutation == "wrong_swap_side":
        resp["quote"]["side"] = "buy"
    elif mutation == "wrong_quote_mint":
        resp["quote"]["mint"] = POOL
    elif mutation == "wrong_quote_input":
        resp["quote"]["amount_in_raw"] = "20000000"
    elif mutation == "bad_decimals":
        mint["value"]["data"]["parsed"]["info"]["decimals"] = True
    elif mutation == "missing_mint":
        mint["value"] = None
    elif mutation == "missing_quote":
        resp["quote"] = None
    elif mutation == "missing_dex_pairs":
        dex["pairs"] = None
    with pytest.raises((ValueError, TypeError)):
        check(response=resp, dex=dex, mint=mint)


@pytest.mark.parametrize("captured,dex_time,check_time", [
    (NOW, NOW + 3100, NOW + 3200),
    (NOW, NOW - 10, NOW + 100),
    (NOW + 200, NOW + 50, NOW + 400),
    (NOW, NOW + 100, NOW - 1),
])
def test_stale_or_out_of_order_receipt_times_fail_closed(captured, dex_time, check_time):
    resp, dex, mint = fixtures()
    if captured != NOW:
        request = {
            "source": "jupiter_swap_v2_order_quote_only", "strategy": "new_launch",
            "mint": MINT, "side": "sell", "input_mint": MINT,
            "output_mint": USDC_MINT, "amount_in_raw": "10000000",
        }
        resp["quote"] = normalize_quote(
            request, {"inAmount": "10000000", "outAmount": "20000000",
                      "feeBps": 5, "router": "metis", "transaction": None},
            observed_at_ms=captured,
        )
    with pytest.raises(ValueError, match="stale_or_inconsistent"):
        marks.assess_sources("new_launch", MINT, POOL, 10_000_000, resp, dex, mint,
                             dex_retrieved_at_ms=dex_time, assessed_at_ms=check_time)


def test_disabled_default_never_calls_any_provider():
    with patch.dict("os.environ", {"MEME_COIN_DUAL_SOURCE_MARKS_ENABLED": "false"}):
        with patch.object(marks, "quote_preview") as a, patch.object(marks, "fetch_dexscreener") as b, patch.object(marks, "fetch_mint_account") as c:
            result = marks.preview_crosscheck("new_launch", MINT, POOL, 1000000)
    assert result["status"] == "disabled"
    a.assert_not_called()
    b.assert_not_called()
    c.assert_not_called()


def test_jupiter_prerequisite_disabled_prevents_secondary_network_calls():
    with patch.dict("os.environ", {"MEME_COIN_DUAL_SOURCE_MARKS_ENABLED": "true"}):
        with patch.object(marks, "quote_preview", return_value={"status": "disabled"}):
            with patch.object(marks, "fetch_dexscreener") as b, patch.object(marks, "fetch_mint_account") as c:
                state = marks.preview_crosscheck("momentum", MINT, POOL, 1000000)
    assert state["status"] == "prerequisite_disabled"
    b.assert_not_called()
    c.assert_not_called()


def test_successful_opt_in_reads_exact_pair_mint_and_walletless_quote_only():
    marks._CACHE.clear()
    q, ds, mint = fixtures()
    with patch.dict("os.environ", {"MEME_COIN_DUAL_SOURCE_MARKS_ENABLED": "true"}):
        with patch.object(marks, "quote_preview", return_value=q) as quote, patch.object(marks, "fetch_dexscreener", return_value=ds) as dex, patch.object(marks, "fetch_mint_account", return_value=mint) as rpc:
            with patch.object(marks.time, "time_ns", return_value=NOW * 1000000 + 100000000):
                result = marks.preview_crosscheck("new_launch", MINT, POOL, 10_000_000)
    quote.assert_called_once_with("new_launch", MINT, "sell", 10_000_000)
    dex.assert_called_once_with(POOL)
    rpc.assert_called_once_with(MINT)
    assert result["status"] == "screened"
    assert result["verdict"] == "comparison_only"
    assert result["tradable"] is False


def test_provider_mismatch_never_fakes_price_comparison():
    marks._CACHE.clear()
    q, ds, mint = fixtures()
    ds["pairs"][0]["pairAddress"] = MINT
    with patch.dict("os.environ", {"MEME_COIN_DUAL_SOURCE_MARKS_ENABLED": "true"}):
        with patch.object(marks, "quote_preview", return_value=q), patch.object(marks, "fetch_dexscreener", return_value=ds), patch.object(marks, "fetch_mint_account", return_value=mint):
            result = marks.preview_crosscheck("new_launch", MINT, POOL, 10_000_000)
    assert result["status"] == "unavailable"
    assert result["jupiter_price_usd"] is None
    assert result["tradable"] is False


def test_api_contract_no_order_write_path_and_no_robinhood_query():
    app = FastAPI()
    app.include_router(router, prefix="/api/v1/meme-coins")
    client = TestClient(app)
    with patch.dict("os.environ", {"MEME_COIN_DUAL_SOURCE_MARKS_ENABLED": "false"}):
        response = client.get("/api/v1/meme-coins/solana/mark-crosscheck", params={
            "strategy": "new_launch", "mint": MINT,
            "pool": POOL, "amount_raw": 1000000,
        })
    assert response.status_code == 200
    assert response.json()["status"] == "disabled"
    assert response.json()["mark_to_market_execution_verified"] is False
    assert response.json()["live_trading_enabled"] is False
    assert client.post("/api/v1/meme-coins/solana/mark-crosscheck", json={}).status_code == 405
    assert client.get("/api/v1/meme-coins/solana/mark-crosscheck", params={
        "strategy": "robinhood_chain", "mint": MINT,
        "pool": POOL, "amount_raw": 1000000,
    }).status_code == 422
