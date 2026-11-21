"""Offline cross-source pool liquidity/provenance tests (no trading)."""
from __future__ import annotations

from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient
from api.v1.endpoints.meme_coin import router
from src.services import meme_coin_solana_pool as pool_review

MINT = "So11111111111111111111111111111111111111112"
POOL = "11111111111111111111111111111111"
PROGRAM = "TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA"


def example(liq_gecko="60000", liq_dex=61000, mint=MINT, pool=POOL):
    gecko = {
        "data": {
            "type": "pool", "attributes": {"address": pool, "reserve_in_usd": liq_gecko},
            "relationships": {"base_token": {"data": {"id": f"solana_{mint}"}}},
        },
        "included": [{"id": f"solana_{mint}", "type": "token", "attributes": {"address": mint}}],
    }
    dex = {"pairs": [{
        "chainId": "solana", "pairAddress": pool, "dexId": "example",
        "baseToken": {"address": mint, "symbol": "MEME"},
        "quoteToken": {"address": PROGRAM, "symbol": "SOL"},
        "liquidity": {"usd": liq_dex},
    }]}
    chain = {"context": {"slot": 123450}, "value": {
        "owner": PROGRAM, "lamports": 100000, "space": 250, "executable": False,
    }}
    return gecko, dex, chain


def test_concordant_snapshot_is_research_only_not_a_verified_liquidity_lock():
    result = pool_review.assess_pool(MINT, POOL, *example())
    assert result["status"] == "screened"
    assert result["verdict"] == "review_only"
    assert result["difference_pct"] < 5
    assert result["onchain_account_found"] is True
    assert result["onchain_owner_program"] == PROGRAM
    assert result["onchain_reserves_verified"] is False
    assert result["liquidity_lock_verified"] is False
    assert result["lp_owner_verified"] is False
    assert result["pool_authenticity_verified"] is False
    assert result["sellability_verified"] is False
    assert result["tradable"] is False


def test_liquidity_divergence_or_low_reserve_flags_without_buys():
    divergent = pool_review.assess_pool(MINT, POOL, *example(liq_gecko="20000", liq_dex=90000))
    assert divergent["verdict"] == "blocked"
    assert "liquidity_source_divergence" in divergent["flags"]
    low = pool_review.assess_pool(MINT, POOL, *example(liq_gecko="7000", liq_dex=7300))
    assert low["verdict"] == "blocked"
    assert "low_reported_liquidity" in low["flags"]
    assert low["tradable"] is False


def test_missing_onchain_account_marks_blocked_and_identity_not_verified():
    gecko, dex, chain = example()
    chain["value"] = None
    result = pool_review.assess_pool(MINT, POOL, gecko, dex, chain)
    assert result["onchain_account_found"] is False
    assert result["verdict"] == "blocked"
    assert "onchain_pool_account_missing" in result["flags"]


def test_pool_identity_and_mint_mismatches_never_produce_clearance():
    import pytest
    for which in ("gecko_pool", "gecko_mint", "dex_chain", "dex_pool", "dex_mint", "invalid_number"):
        gt, ds, account = example()
        if which == "gecko_pool":
            gt["data"]["attributes"]["address"] = MINT
        elif which == "gecko_mint":
            gt["included"][0]["attributes"]["address"] = POOL
        elif which == "dex_chain":
            ds["pairs"][0]["chainId"] = "ethereum"
        elif which == "dex_pool":
            ds["pairs"][0]["pairAddress"] = MINT
        elif which == "dex_mint":
            ds["pairs"][0]["baseToken"]["address"] = POOL
        elif which == "invalid_number":
            gt["data"]["attributes"]["reserve_in_usd"] = "NaN"
        with pytest.raises(ValueError):
            pool_review.assess_pool(MINT, POOL, gt, ds, account)


def test_disabled_by_default_never_contacts_any_provider():
    pool_review._CACHE.clear()
    with patch.dict("os.environ", {"MEME_COIN_SOLANA_LIQUIDITY_REVIEW_ENABLED": "false"}):
        with patch.object(pool_review, "fetch_gecko") as a, patch.object(pool_review, "fetch_dexscreener") as b, patch.object(pool_review, "fetch_pool_account") as c:
            result = pool_review.review_pool(MINT, POOL)
    assert result["status"] == "disabled"
    assert not a.called and not b.called and not c.called


def test_enabled_caches_and_never_fabricates_success_on_failure():
    pool_review._CACHE.clear()
    gecko, dex, chain = example()
    with patch.dict("os.environ", {"MEME_COIN_SOLANA_LIQUIDITY_REVIEW_ENABLED": "true"}):
        with patch.object(pool_review, "fetch_gecko", return_value=gecko) as a, patch.object(pool_review, "fetch_dexscreener", return_value=dex), patch.object(pool_review, "fetch_pool_account", return_value=chain):
            first = pool_review.review_pool(MINT, POOL)
            first["flags"].append("changed")
            second = pool_review.review_pool(MINT, POOL)
    assert a.call_count == 1
    assert second["status"] == "screened"
    assert "changed" not in second["flags"]
    pool_review._CACHE.clear()
    with patch.dict("os.environ", {"MEME_COIN_SOLANA_LIQUIDITY_REVIEW_ENABLED": "true"}):
        with patch.object(pool_review, "fetch_gecko", side_effect=RuntimeError("rate-limited")):
            error = pool_review.review_pool(MINT, POOL)
    assert error["status"] == "unavailable"
    assert error["geckoterminal_usd"] is None
    assert error["tradable"] is False


def test_authenticated_read_only_contract_rejects_bad_addresses():
    app = FastAPI()
    app.include_router(router, prefix="/api/v1/meme-coins")
    client = TestClient(app)
    with patch.dict("os.environ", {"MEME_COIN_SOLANA_LIQUIDITY_REVIEW_ENABLED": "false"}):
        r = client.get("/api/v1/meme-coins/solana/pool-review", params={"mint": MINT, "pool": POOL})
    assert r.status_code == 200
    assert r.json()["onchain_reserves_verified"] is False
    assert r.json()["tradable"] is False
    assert client.get("/api/v1/meme-coins/solana/pool-review", params={"mint": "bad", "pool": POOL}).status_code == 422
    assert client.post("/api/v1/meme-coins/solana/pool-review", json={}).status_code == 405
