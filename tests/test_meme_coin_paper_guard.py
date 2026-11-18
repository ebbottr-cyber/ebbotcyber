"""Offline modeled circuit breaker tests — no real trades or validated market facts."""
from __future__ import annotations

from copy import deepcopy

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.v1.endpoints.meme_coin import router
from src.services.meme_coin_paper_guard import replay_guarded, readiness

MINT = "11111111111111111111111111111111"
MINT2 = "So11111111111111111111111111111111111111112"


def event(event_id, *, strategy="new_launch", side="buy", amount="25",
          expected="25", observed=1000000, attempted=1000200, outcome="success",
          network_fee="0.00"):
    return {
        "id": event_id, "strategy": strategy, "mint": MINT,
        "side": side, "source": "offline_fixture",
        "quote_observed_at_ms": observed,
        "attempted_at_ms": attempted,
        "amount_in": amount, "expected_out": expected,
        "network_fee_usd": network_fee, "priority_fee_usd": "0.00",
        "modeled_adverse_slippage_bps": 0, "outcome": outcome,
    }


def facts(*events, liq="60000", observed_offset_ms=100):
    return {
        item["id"]: {
            "source": "offline_assumption",
            "liquidity_usd": liq,
            "observed_at_ms": item["attempted_at_ms"] - observed_offset_ms,
        }
        for item in events
    }


def test_independent_strategy_ledgers_and_cost_basis_do_not_mix():
    a = event("a")
    b = event("b", strategy="momentum", observed=1001000, attempted=1001200)
    result = replay_guarded([a, b], facts=facts(a, b))
    assert result["mode"] == "offline_risk_guarded_replay"
    assert result["data_is_live"] is False
    assert result["risk_facts_are_offline_assumptions"] is True
    assert result["automatic_paper_trading_enabled"] is False
    assert result["actual_trading_enabled"] is False
    assert result["global_book_loss_circuit_open"] is False
    assert result["ledgers"]["new_launch"]["cash_usd"] == "975.00"
    assert result["ledgers"]["momentum"]["cash_usd"] == "975.00"
    assert result["ledgers"]["new_launch"]["positions"][MINT]["quantity"] == "25.000000000"
    assert result["ledgers"]["momentum"]["positions"][MINT]["quantity"] == "25.000000000"


def test_missing_or_stale_liquidity_prevents_any_simulated_fill():
    a = event("a")
    with pytest.raises(ValueError, match="missing_or_unexpected_risk_fact"):
        replay_guarded([a], facts={})
    bad = facts(a, liq="9999")
    result = replay_guarded([a], facts=bad)["ledgers"]["new_launch"]
    assert result["cash_usd"] == "1000.00"
    assert result["audit"][0]["reason"] == "insufficient_reported_liquidity"
    assert result["positions"] == {}
    age = replay_guarded([a], facts=facts(a, observed_offset_ms=31000))["ledgers"]["new_launch"]
    assert age["audit"][0]["reason"] == "stale_liquidity_observation"
    assert age["cash_usd"] == "1000.00"


def test_future_risk_fact_and_unsafe_fact_source_are_not_approved():
    a = event("a")
    future = replay_guarded([a], facts=facts(a, observed_offset_ms=-1))["ledgers"]["new_launch"]
    assert future["audit"][0]["reason"] == "future_risk_observation"
    risky = facts(a)
    risky["a"]["source"] = "live_unverified"
    with pytest.raises(ValueError, match="unverified_liquidity_source"):
        replay_guarded([a], facts=risky)
    risky = facts(a)
    risky["a"]["api_key"] = "should never be stored"
    with pytest.raises(ValueError):
        replay_guarded([a], facts=risky)


def test_modeled_buy_more_than_one_percent_of_liquidity_is_rejected():
    a = event("a", amount="50")
    result = replay_guarded([a], facts=facts(a, liq="10000"))["ledgers"]["new_launch"]
    assert result["successful_buys"] == 1  # 50 / 10000 == 0.5%, permitted
    second = event("b", amount="100", observed=1000300, attempted=1000400)
    result2 = replay_guarded([second], facts=facts(second, liq="10000"))["ledgers"]["new_launch"]
    assert result2["audit"][0]["reason"] == "order_too_large_vs_reported_liquidity"


def test_daily_strategy_book_loss_blocks_new_buys_but_not_other_strategy():
    buy = event("buy", amount="100", expected="100")
    sell = event("sell", side="sell", amount="100", expected="40",
                 observed=1001000, attempted=1001200)
    later = event("later", observed=1002000, attempted=1002200)
    other = event("other", strategy="momentum", observed=1003000, attempted=1003200)
    results = replay_guarded([buy, sell, later, other], facts=facts(buy, sell, later, other))
    a = results["ledgers"]["new_launch"]
    b = results["ledgers"]["momentum"]
    assert a["realized_pnl_usd"] == "-60.00"
    assert a["daily_book_loss_circuit_open"] is True
    assert a["audit"][-1]["reason"] == "daily_strategy_book_loss_limit"
    assert a["successful_buys"] == 1
    assert b["successful_buys"] == 1
    assert b["cash_usd"] == "975.00"


def test_global_book_loss_latch_blocks_both_strategies():
    e = [
        event("a1", amount="100", expected="100"),
        event("a2", side="sell", amount="100", expected="40", observed=1001000, attempted=1001200),
        event("b1", strategy="momentum", amount="100", expected="100", observed=1002000, attempted=1002200),
        event("b2", strategy="momentum", side="sell", amount="100", expected="40",
              observed=1003000, attempted=1003200),
        event("a3", observed=1004000, attempted=1004200),
        event("b3", strategy="momentum", observed=1005000, attempted=1005200),
    ]
    result = replay_guarded(e, facts=facts(*e))
    assert result["global_book_loss_circuit_open"] is True
    assert result["ledgers"]["new_launch"]["audit"][-1]["reason"] == "global_book_loss_limit"
    assert result["ledgers"]["momentum"]["audit"][-1]["reason"] == "global_book_loss_limit"


def test_three_network_failures_latch_breaker_and_charge_only_known_gas():
    e = [
        event("f1", outcome="onchain_failure", network_fee="0.02"),
        event("f2", outcome="timeout", observed=1001000, attempted=1001200),
        event("f3", outcome="rejected_by_network", observed=1002000, attempted=1002200),
        event("new", observed=1003000, attempted=1003200),
    ]
    result = replay_guarded(e, facts=facts(*e))["ledgers"]["new_launch"]
    assert result["consecutive_failure_circuit_open"] is True
    assert result["cash_usd"] == "999.98"
    assert result["failed_transactions"] == 1
    assert result["audit"][-1]["reason"] == "consecutive_network_failures"


def test_hard_emergency_stop_rejects_all_actions_even_sells():
    a = event("a")
    b = event("b", side="sell", observed=1001000, attempted=1001200)
    result = replay_guarded([a, b], facts=facts(a, b), emergency_stop=True)
    ledger = result["ledgers"]["new_launch"]
    assert result["emergency_stop_enabled"] is True
    assert ledger["cash_usd"] == "1000.00"
    assert ledger["positions"] == {}
    assert [a["reason"] for a in ledger["audit"]] == ["emergency_stop", "emergency_stop"]


def test_buys_resume_next_utc_day_after_daily_limit_if_global_not_hit():
    day = 86400000
    a = event("a", amount="100", expected="100", observed=1000000, attempted=1000200)
    b = event("b", side="sell", amount="100", expected="40", observed=1001000, attempted=1001200)
    c = event("c", observed=day + 1000000, attempted=day + 1000200)
    result = replay_guarded([a, b, c], facts=facts(a, b, c))
    ledger = result["ledgers"]["new_launch"]
    assert ledger["successful_buys"] == 2
    assert ledger["daily_book_loss_circuit_open"] is False
    assert result["global_book_loss_circuit_open"] is False


def test_duplicate_ids_or_orphan_facts_cannot_partially_execute():
    a = event("a")
    with pytest.raises(ValueError, match="duplicate"):
        replay_guarded([a, deepcopy(a)], facts=facts(a))
    wrong = facts(a)
    wrong["orphan"] = {"source": "offline_assumption", "liquidity_usd": "60000",
                       "observed_at_ms": 1000}
    with pytest.raises(ValueError, match="orphan_risk_facts"):
        replay_guarded([a], facts=wrong)


def test_safety_readiness_api_does_not_start_or_store_any_strategy():
    app = FastAPI()
    app.include_router(router, prefix="/api/v1/meme-coins")
    client = TestClient(app)
    response = client.get("/api/v1/meme-coins/paper/risk-readiness")
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["status"] == "offline_safeguards_available"
    assert body["journal_online"] is False
    assert body["paper_engine_running"] is False
    assert body["live_trading_enabled"] is False
    assert body["risk_facts_verified_from_market"] is False
    assert [r["strategy"] for r in body["strategy_ledgers"]] == ["new_launch", "momentum"]
    assert client.post("/api/v1/meme-coins/paper/risk-readiness", json={}).status_code == 405
    assert readiness() == body
