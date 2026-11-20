"""Offline contract tests for fixed-mint, time-spaced public observations."""
from __future__ import annotations

import json
from dataclasses import replace
from unittest.mock import patch

import pytest

from data_provider.solana_meme import MemeQuote
from scripts.collect_solana_observations import collect, main


MINT1 = "So11111111111111111111111111111111111111112"
MINT2 = "So11111111111111111111111111111111111111113"
SAFE = {k: {"status": "0"} for k in
        ("mintable", "freezable", "closable", "non_transferable", "transfer_hook")}


def initial(mint, source, liquidity=22000):
    return MemeQuote(
        mint=mint, symbol="EX", source=source, pool_id="solana_originalpool",
        price_usd=.1, liquidity_usd=liquidity, volume_h24_usd=99000,
        buys_m5=35, sells_m5=8, change_m5_pct=5.0,
        pool_created_at_ms=1_799_999_000_000, observed_at_ms=1_800_000_000_000,
    )


class FakeFeed:
    def __init__(self, *, missing_price=False, failed_security=False,
                 missing_gecko_dex_price=False, wrong_gecko_pool=False):
        self.urls = []
        self.missing_price = missing_price
        self.failed_security = failed_security
        self.missing_gecko_dex_price = missing_gecko_dex_price
        self.wrong_gecko_pool = wrong_gecko_pool
        self.security_calls = []

    def new_pools(self, now_ms):
        return [replace(initial(MINT1, "geckoterminal"), pool_id="solana_"+MINT1)]

    def latest_profiles(self, now_ms, limit):
        return [initial(MINT2, "dexscreener")]

    def transport(self, url):
        self.urls.append(url)
        if "/networks/solana/pools/" in url:
            return {
                "data": {
                    "id": "solana_"+(MINT2 if self.wrong_gecko_pool else MINT1),
                    "type": "pool",
                    "attributes": {
                        "base_token_price_usd": "0.15", "reserve_in_usd": "25000",
                        "volume_usd": {"h24": "100000"},
                        "transactions": {"m5": {"buys": 40, "sells": 10}},
                        "price_change_percentage": {"m5": "7"},
                    },
                    "relationships": {"base_token": {"data": {"id": "solana_"+MINT1}}},
                },
                "included": [],
            }
        data = []
        for mint in (MINT1, MINT2):
            if (mint == MINT2 and self.missing_price) or (mint == MINT1 and self.missing_gecko_dex_price):
                continue
            data.append({
                "chainId": "solana", "pairAddress": "pair_"+mint,
                "baseToken": {"address": mint, "symbol": "EX"},
                "priceUsd": ".1", "liquidity": {"usd": 25000},
                "volume": {"h24": 100000},
                "txns": {"m5": {"buys": 40, "sells": 10}},
                "priceChange": {"m5": 7.0},
            })
        return data

    def security(self, mint):
        self.security_calls.append(mint)
        if self.failed_security:
            return None
        return SAFE


def run(feed, rounds=3, interval_seconds=60, limit=2):
    clock_state = [1_800_000_000]
    sleeps = []

    def sleeper(seconds):
        sleeps.append(seconds)
        clock_state[0] += seconds

    out = collect(feed, rounds=rounds, interval_seconds=interval_seconds,
                  limit=limit, clock=lambda: clock_state[0], sleeper=sleeper)
    return out, sleeps


def test_same_two_mints_are_sampled_three_times():
    feed = FakeFeed()
    out, sleeps = run(feed)
    assert out["summary"]["result"] == "passed"
    assert out["data_origin"] == "live_public_api_not_historical"
    assert out["performance_calculated"] is False
    assert out["trading_enabled"] is False
    assert len(out["tracked_mints"]) == 2
    assert len(feed.urls) == 3
    assert len(feed.security_calls) == 6
    assert sleeps == [60, 60]
    assert len(out["observations"]) == 6
    assert len({o["timestamp_ms"] for o in out["observations"]}) == 3
    for mint in out["tracked_mints"]:
        dates = [o["timestamp_ms"] for o in out["observations"] if o["mint"] == mint]
        assert dates == sorted(dates) and len(set(dates)) == 3
    assert all(o["price_source"] == "dexscreener" for o in out["observations"])
    assert all(o["strategies"]["new_coin_hunter"]["status"] in ("watch", "blocked")
               for o in out["observations"])
    assert all("buy_order" not in json.dumps(o) for o in out["observations"])


def test_discovery_source_is_not_faked_as_price_source():
    out, _ = run(FakeFeed())
    gecko = next(o for o in out["observations"] if o["discovery_source"] == "geckoterminal")
    assert gecko["price_source"] == "dexscreener"
    assert gecko["discovery_pool_id"] == "solana_"+MINT1
    assert gecko["price_pair_id"].startswith("pair_")


def test_missing_quote_has_no_fabricated_price_or_strategy():
    out, _ = run(FakeFeed(missing_price=True))
    assert out["summary"]["result"] == "degraded"
    assert out["summary"]["missing_price_observations"] == 3
    missing = [o for o in out["observations"] if o["status"] == "missing_price"]
    assert len(missing) == 3 and all("price_usd" not in o for o in missing)


def test_missing_risk_never_becomes_safe():
    out, _ = run(FakeFeed(failed_security=True))
    assert out["summary"]["result"] == "passed"  # price series still complete
    assert all(not o["risk_record_present"] for o in out["observations"])
    assert all(o["strategies"]["momentum_watcher"]["status"] == "blocked"
               for o in out["observations"])


def test_one_token_mode_honors_limit():
    feed = FakeFeed()
    out, sleeps = run(feed, limit=1, rounds=2)
    assert len(out["tracked_mints"]) == 1
    assert len(out["observations"]) == 2
    assert sleeps == [60]
    assert all(MINT2 not in url for url in feed.urls)


@pytest.mark.parametrize("kwargs", [
    {"rounds": 1}, {"rounds": 5},
    {"interval_seconds": 59}, {"interval_seconds": 121},
    {"limit": 0}, {"limit": 3},
    {"rounds": True}, {"limit": True},
])
def test_budget_and_spacing_are_strict(kwargs):
    with pytest.raises(ValueError):
        run(FakeFeed(), **kwargs)


def test_cli_is_safe_by_default(monkeypatch, capsys):
    monkeypatch.setattr("sys.argv", ["collect_solana_observations"])
    with patch("scripts.collect_solana_observations.SolanaMemeFeed") as constructor:
        assert main() == 0
        constructor.assert_not_called()
    assert '"trading_enabled": false' in capsys.readouterr().out


def test_no_candidates_does_not_appear_green():
    class Empty(FakeFeed):
        def new_pools(self, now_ms):
            return []
        def latest_profiles(self, now_ms, limit):
            return []
    out, _ = run(Empty())
    assert out["summary"]["result"] == "inconclusive"
    assert out["observations"] == []


def test_missing_gecko_dex_quote_falls_back_to_same_gecko_pool():
    feed = FakeFeed(missing_gecko_dex_price=True)
    out, sleeps = run(feed)
    assert out["summary"]["result"] == "passed"
    assert out["summary"]["valid_price_observations"] == 6
    assert out["summary"]["missing_price_observations"] == 0
    gecko = [r for r in out["observations"] if r["mint"] == MINT1]
    assert len(gecko) == 3
    assert all(r["price_source"] == "geckoterminal" for r in gecko)
    assert all(r["price_pair_id"] == "solana_"+MINT1 for r in gecko)
    assert all(r["price_usd"] == "0.15" for r in gecko)
    assert len([u for u in feed.urls if "/networks/solana/pools/" in u]) == 3
    assert sleeps == [60, 60]


def test_gecko_pool_fallback_rejects_pool_identity_mismatch():
    feed = FakeFeed(missing_gecko_dex_price=True, wrong_gecko_pool=True)
    out, _ = run(feed)
    assert out["summary"]["result"] == "degraded"
    assert out["summary"]["valid_price_observations"] == 3
    missing = [r for r in out["observations"] if r.get("status") == "missing_price"]
    assert len(missing) == 3 and all(r["mint"] == MINT1 for r in missing)
