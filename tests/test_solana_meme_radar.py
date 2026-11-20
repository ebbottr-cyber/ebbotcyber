"""Completely offline deterministic contract and safety tests."""

from __future__ import annotations

from dataclasses import replace

import pytest

from data_provider.solana_meme import (
    MarketDataError,
    MemeQuote,
    SolanaMemeFeed,
    _dex_quotes,
    _gecko_quotes,
    get_json,
)
from scripts.scan_solana_meme import scan, _select_quotes
from src.services.solana_meme_radar import evaluate, security_reasons

MINT = "So11111111111111111111111111111111111111112"
NOW = 1_800_000_000_000
SAFE = {key: {"status": "0"} for key in ("mintable", "freezable", "closable", "non_transferable", "transfer_hook")}


def new_quote(**updates):
    quote = MemeQuote(MINT, "TEST", "geckoterminal", "solana_pool", 0.05, 25000, 100000, 35, 10, 5.0, NOW - 3600_000, NOW)
    return replace(quote, **updates)


def test_opt_in_default_no_network():
    assert scan() == {"enabled": False, "trading_enabled": False, "candidates": [], "errors": [],
                      "message": "Use --live to explicitly enable read-only API calls"}


def test_new_hunter_and_momentum_can_watch_with_complete_risk_data():
    for strategy in ("new_coin_hunter", "momentum_watcher"):
        result = evaluate(new_quote(), strategy, NOW, SAFE)
        assert result.status == "watch"
        assert result.score == 100


def test_no_go_plus_record_is_blocked():
    out = evaluate(new_quote(), "momentum_watcher", NOW, None)
    assert out.status == "blocked"
    assert "security_unknown" in out.reasons


def test_reject_incomplete_or_dangerous_risks():
    assert "mintable_unknown" in security_reasons({"freezable": "0"})
    assert "mintable" in security_reasons({**SAFE, "mintable": {"status": "1"}})
    assert "malicious_creator" in security_reasons({**SAFE, "creator": {"malicious_address": "1"}})


def test_source_classification_and_stale_quotes():
    dex = replace(new_quote(), source="dexscreener")
    assert "not_new_pool_feed" in evaluate(dex, "new_coin_hunter", NOW, SAFE).reasons
    old = replace(new_quote(), observed_at_ms=NOW-121_000)
    assert "stale_quote" in evaluate(old, "momentum_watcher", NOW, SAFE).reasons


def test_absent_metrics_fail_closed():
    poor = new_quote(liquidity_usd=None, volume_h24_usd=None, buys_m5=None, sells_m5=None, change_m5_pct=None)
    result = evaluate(poor, "momentum_watcher", NOW, SAFE)
    assert result.status == "blocked"
    assert "transaction_counts_unknown" in result.reasons


def test_dex_normalizes_and_skips_non_solana():
    pair = {"chainId": "solana", "pairAddress": "pair1", "baseToken": {"address": MINT, "symbol": "TEST"},
            "priceUsd": "0.1", "volume": {"h24": 100000}, "liquidity": {"usd": 32000},
            "txns": {"m5": {"buys": 21, "sells": 10}}, "priceChange": {"m5": 8.2},
            "pairCreatedAt": NOW-2000}
    quotes = _dex_quotes([pair, {**pair, "chainId": "ethereum"}], NOW)
    assert len(quotes) == 1
    assert quotes[0].buys_m5 == 21
    assert quotes[0].liquidity_usd == 32000


def test_gecko_normalizes_and_skips_invalid_ids():
    pool = {"id": "solana_pool123", "relationships": {"base_token": {"data": {"id": "solana_" + MINT}}},
            "attributes": {"name": "TEST/SOL", "base_token_price_usd": "0.015", "reserve_in_usd": "22000",
                           "volume_usd": {"h24": "50000"}, "price_change_percentage": {"m5": "3"},
                           "transactions": {"m5": {"buys": 23, "sells": 8}},
                           "pool_created_at": "2027-01-01T00:00:00Z"}}
    quotes = _gecko_quotes({"data": [pool, {**pool, "id": "eth_bad"}]}, NOW)
    assert len(quotes) == 1
    assert quotes[0].mint == MINT
    assert quotes[0].buys_m5 == 23
    assert quotes[0].pool_created_at_ms is not None


def test_profile_endpoint_does_not_claim_mint_event():
    calls = []
    def transport(url):
        calls.append(url)
        if "token-profiles" in url:
            return [{"chainId": "solana", "tokenAddress": MINT},
                    {"chainId": "solana", "tokenAddress": MINT},
                    {"chainId": "ethereum", "tokenAddress": "0x123"}]
        return [{"chainId": "solana", "pairAddress": "testpool", "baseToken": {"address": MINT}}]
    got = SolanaMemeFeed(transport).latest_profiles(NOW)
    assert len(got) == 1
    assert got[0].source == "dexscreener"
    assert len(calls) == 2


def test_goplus_lookup_unknown_is_not_safe():
    feed = SolanaMemeFeed(lambda url: {"code": 1, "result": {}})
    assert feed.security(MINT) is None


def test_provider_error_is_not_silently_treated_as_empty():
    feed = SolanaMemeFeed(lambda url: {"not": "a pool list"})
    with pytest.raises(MarketDataError):
        feed.new_pools(NOW)
    with pytest.raises(MarketDataError):
        feed.security(MINT)
    with pytest.raises(MarketDataError):
        get_json("https://example.org/api")


def test_payload_nan_and_invalid_address_rejected():
    pair = {"chainId": "solana", "pairAddress": "pool", "baseToken": {"address": MINT},
            "priceUsd": "NaN", "liquidity": {"usd": -1}}
    q = _dex_quotes([pair], NOW)[0]
    assert q.price_usd is None
    assert q.liquidity_usd is None
    with pytest.raises(ValueError):
        SolanaMemeFeed().security("/../../etc/passwd")


def test_limit_capped():
    with pytest.raises(ValueError):
        SolanaMemeFeed().latest_profiles(NOW, limit=31)



def test_gecko_symbol_comes_from_included_base_token_not_pool_name():
    pool = {
        "id": "solana_pool123",
        "attributes": {"name": "FAKE / SOL", "base_token_price_usd": "0.125"},
        "relationships": {"base_token": {"data": {"id": "solana_" + MINT}}},
    }
    doc = {
        "data": [pool],
        "included": [{
            "id": "solana_" + MINT,
            "type": "token",
            "attributes": {"symbol": "REAL"},
        }],
    }
    quote = _gecko_quotes(doc, NOW)[0]
    assert quote.symbol == "REAL"
    # If the included token is missing, unknown is safer than a pool pair label.
    assert _gecko_quotes({"data": [pool]}, NOW)[0].symbol == "?"


def test_gecko_feed_explicitly_requests_token_identity():
    calls = []
    feed = SolanaMemeFeed(lambda url: calls.append(url) or {"data": []})
    assert feed.new_pools(NOW) == []
    assert calls == [
        "https://api.geckoterminal.com/api/v2/networks/solana/new_pools?page=1&include=base_token"
    ]


def test_scan_selection_includes_both_viable_sources():
    gecko = new_quote(mint=MINT, source="geckoterminal", liquidity_usd=20_000)
    dex = new_quote(
        mint="So11111111111111111111111111111111111111113",
        source="dexscreener",
        liquidity_usd=12_000,
    )
    another_gecko = new_quote(
        mint="So11111111111111111111111111111111111111114",
        source="geckoterminal",
        liquidity_usd=100_000,
    )
    result = _select_quotes([gecko, another_gecko, dex], limit=2)
    assert set(result) == {another_gecko.mint, dex.mint}
    assert {quote.source for quote in result.values()} == {"geckoterminal", "dexscreener"}
    # With one slot, highest liquidity still wins; duplicate mint has one entry.
    assert list(_select_quotes([gecko, another_gecko, dex], limit=1)) == [another_gecko.mint]
    assert len(_select_quotes([gecko, gecko], limit=8)) == 1


def test_scan_selection_does_not_reserve_illiquid_source():
    gecko = new_quote(mint=MINT, source="geckoterminal", liquidity_usd=7_000)
    dex = new_quote(
        mint="So11111111111111111111111111111111111111113",
        source="dexscreener",
        liquidity_usd=60_000,
    )
    assert list(_select_quotes([gecko, dex], limit=1)) == [dex.mint]
    assert len(_select_quotes([gecko, dex], limit=2)) == 2

def test_goplus_transfer_hook_address_and_status_are_risky():
    active = {**SAFE, "transfer_hook": {
        "address": "HookProgram111111111111111111111111111111",
        "malicious_address": "0",
    }}
    assert "transfer_hook" in security_reasons(active)
    # A contradictory payload must not be treated as safe.
    assert "transfer_hook" in security_reasons({
        **SAFE, "transfer_hook": {"status": "0", "address": "HookProgram"},
    })
    assert "transfer_hook" in security_reasons({
        **SAFE, "transfer_hook": {"status": "1", "address": ""},
    })


def test_goplus_transfer_hook_explicit_absence_and_unknown():
    assert security_reasons({**SAFE, "transfer_hook": {"address": ""}}) == []
    unknown = security_reasons({**SAFE, "transfer_hook": {"other": "value"}})
    assert "transfer_hook_unknown" in unknown
    assert "transfer_hook_unknown" in security_reasons({
        **SAFE, "transfer_hook": None,
    })


def test_goplus_additional_authority_flags_are_not_ignored():
    for field in (
        "metadata_mutable",
        "transfer_fee_upgradable",
        "default_account_state_upgradable",
        "balance_mutable_authority",
        "transfer_hook_upgradable",
    ):
        assert field in security_reasons({**SAFE, field: {"status": "1"}})
        assert f"{field}_unknown" in security_reasons({**SAFE, field: {"unknown": 4}})
        assert field not in security_reasons({**SAFE, field: {"status": "0"}})


def test_goplus_frozen_default_state_is_blocked():
    assert "default_account_not_initialized" in security_reasons({
        **SAFE, "default_account_state": "2",
    })
    assert "default_account_not_initialized" not in security_reasons({
        **SAFE, "default_account_state": "1",
    })

