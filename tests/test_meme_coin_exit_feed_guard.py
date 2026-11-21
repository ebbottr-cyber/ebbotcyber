"""Offline V13 full-position exit-quote and feed-disconnection risk contracts."""
from __future__ import annotations

from copy import deepcopy

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.v1.endpoints.meme_coin import router
from src.services.meme_coin_exit_feed_guard import (
    assess_entry_exit_coverage, replay_exit_gated, readiness,
)
from src.services.meme_coin_jupiter_quotes import normalize_quote, USDC_MINT
from src.services.meme_coin_paper_mtm import replay_marked_guarded

MINT = "11111111111111111111111111111111"
SECOND = "TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA"
T0 = 1000200


def event(identifier, *, strategy="new_launch", side="buy", amount="100",
          output="100", at=T0, mint=MINT, outcome="success"):
    return {
        "id": identifier, "strategy": strategy, "mint": mint,
        "side": side, "source": "offline_fixture",
        "quote_observed_at_ms": at - 200, "attempted_at_ms": at,
        "amount_in": amount, "expected_out": output,
        "network_fee_usd": "0.00", "priority_fee_usd": "0.00",
        "modeled_adverse_slippage_bps": 0, "outcome": outcome,
    }


def step(identifier, **kwargs):
    e = event(identifier, **kwargs)
    return {
        "event": e,
        "risk_fact": {
            "source": "offline_assumption",
            "liquidity_usd": "60000",
            "observed_at_ms": e["attempted_at_ms"] - 100,
        },
        "marks": {
            e["mint"]: {
                "source": "offline_assumption", "bid_price_usd": "1",
                "observed_at_ms": e["attempted_at_ms"] - 100,
            },
        },
    }


def quote(strategy, mint, full_raw, *, at=T0, dollars_raw=None):
    request = {
        "source": "jupiter_swap_v2_order_quote_only",
        "strategy": strategy, "mint": mint, "side": "sell",
        "input_mint": mint, "output_mint": USDC_MINT,
        "amount_in_raw": str(full_raw),
    }
    response = {
        "inAmount": str(full_raw),
        "outAmount": str(full_raw if dollars_raw is None else dollars_raw),
        "router": "metis", "feeBps": 2, "transaction": None,
    }
    return normalize_quote(request, response, observed_at_ms=at - 100)


def evidence(at=T0, *, q=None, up=True, health_time=None, decimals=None, quotes=None):
    if quotes is None:
        quotes = {"new_launch:" + MINT: q if q is not None else quote(
            "new_launch", MINT, 100_000_000, at=at,
        )}
    return {
        "provider_status": {
            "source": "offline_fixture",
            "jupiter_online": up,
            "dexscreener_online": up,
            "solana_rpc_online": up,
            "observed_at_ms": at - 100 if health_time is None else health_time,
        },
        "token_decimals": {MINT: 6} if decimals is None else decimals,
        "full_sell_quotes": quotes,
    }


def gate(first, snap=None):
    return replay_exit_gated([first], {
        first["event"]["id"]: evidence(first["event"]["attempted_at_ms"]) if snap is None else snap,
    })


def test_valid_full_position_quote_allows_only_an_offline_scenario():
    result = gate(step("buy"))
    assert result["status"] == "offline_quote_coverage_replayed"
    assert result["gate_audit"][0]["status"] == "scenario_coverage_only"
    assert result["gate_audit"][0]["quote_provenance_authenticated"] is False
    assert result["gate_audit"][0]["real_execution_confirmed"] is False
    assert "exit_quote_gate" not in result["gated_steps"][0]
    assert result["replay_report"]["ledgers"]["new_launch"]["successful_buys"] == 1
    assert result["market_quote_provenance_authenticated"] is False
    assert result["online_paper_scheduler_running"] is False
    assert result["live_trading_enabled"] is False


def test_missing_or_disconnected_exit_evidence_blocks_buy_and_logs_reason():
    candidate = step("buy")
    no_quote = replay_exit_gated([candidate], {})
    assert no_quote["gate_audit"][0]["reason"] == "missing_exit_snapshot"
    assert no_quote["replay_report"]["ledgers"]["new_launch"]["successful_buys"] == 0
    assert no_quote["replay_report"]["ledgers"]["new_launch"]["audit"][0]["reason"] == "exit_quote_missing_exit_snapshot"
    assert no_quote["replay_report"]["ledgers"]["new_launch"]["cash_usd"] == "1000.00"
    state = evidence(up=False)
    disconnected = gate(candidate, state)
    assert disconnected["gate_audit"][0]["reason"] == "feed_disconnected"
    assert disconnected["replay_report"]["ledgers"]["new_launch"]["audit"][0]["reason"] == "exit_quote_feed_disconnected"


def test_feed_outage_is_temporary_buy_suspension_not_a_forced_sell():
    a = step("a")
    b = step("b", at=T0+1000, output="25", amount="25")
    c = step("c", side="sell", at=T0+2000, amount="100", output="80")
    snapshots = {
        "a": evidence(),
        "b": evidence(T0+1000, up=False),
    }
    report = replay_exit_gated([a,b,c], snapshots)
    ledger = report["replay_report"]["ledgers"]["new_launch"]
    assert ledger["successful_buys"] == 1
    assert ledger["successful_sells"] == 1
    assert ledger["audit"][1]["reason"] == "exit_quote_feed_disconnected"
    assert ledger["positions"] == {}
    assert report["replay_report"]["live_trading_enabled"] is False


def test_stale_heartbeat_stale_quote_and_future_quote_fail_closed():
    x = step("x")
    old_health = gate(x, evidence(health_time=T0-5001))
    assert old_health["gate_audit"][0]["reason"] == "feed_stale"
    stale = evidence(q=quote("new_launch", MINT, 100_000_000, at=T0-4000))
    assert gate(x, stale)["gate_audit"][0]["reason"] == "stale_exit_quote"
    future = evidence(q=quote("new_launch", MINT, 100_000_000, at=T0+1000))
    assert gate(x, future)["gate_audit"][0]["reason"] == "stale_exit_quote"


def test_wrong_full_sell_amount_blocks_even_with_profitable_quote():
    x = step("x")
    badly_sized = evidence(q=quote("new_launch", MINT, 99_000_000))
    assert gate(x, badly_sized)["gate_audit"][0]["reason"] == "invalid_exit_evidence"
    # Valid quote for 99 tokens can never be substituted for 100 tokens.
    direct = assess_entry_exit_coverage(
        strategy="new_launch", positions={"new_launch":{}, "momentum":{}},
        pending_buy=x["event"], evidence=badly_sized, at_ms=T0,
    )
    assert direct["all_quote_amounts_match_full_positions"] is False
    assert direct["automatic_paper_execution_enabled"] is False


def test_forged_token_quantity_or_capture_hash_fail_closed():
    x = step("x")
    snap = evidence()
    snap["full_sell_quotes"]["new_launch:"+MINT]["capture_id"] = "0"*64
    assert gate(x, snap)["gate_audit"][0]["reason"] == "invalid_exit_evidence"
    snap = evidence(decimals={MINT: 9})
    assert gate(x, snap)["gate_audit"][0]["reason"] == "invalid_exit_evidence"
    snap = evidence(decimals={MINT: 10})
    assert gate(x, snap)["gate_audit"][0]["reason"] == "invalid_exit_evidence"


def test_tiny_after_costs_exit_rejected_without_false_cash_value():
    x = step("x")
    snap = evidence(q=quote("new_launch", MINT, 100_000_000, dollars_raw=500000))
    assert gate(x, snap)["gate_audit"][0]["reason"] == "insufficient_exit_proceeds"
    assert gate(x, snap)["replay_report"]["ledgers"]["new_launch"]["successful_buys"] == 0


def test_quote_coverage_requires_aggregated_full_position_after_second_buy():
    a = step("a")
    b = step("b", at=T0+1000, amount="25", output="25")
    second = evidence(at=T0+1000, q=quote("new_launch", MINT, 125_000_000, at=T0+1000))
    report = replay_exit_gated([a,b], {"a":evidence(), "b":second})
    aledger = report["replay_report"]["ledgers"]["new_launch"]
    assert aledger["successful_buys"] == 2
    assert aledger["positions"][MINT]["quantity"] == "125.000000000"
    assert [r["status"] for r in report["gate_audit"]] == ["scenario_coverage_only"]*2


def test_full_quote_per_strategy_is_required_even_if_same_token_held():
    a = step("a")
    b = step("b", strategy="momentum", at=T0+1000, amount="25", output="25")
    extra = evidence(
        at=T0+1000,
        quotes={
            "new_launch:"+MINT: quote("new_launch", MINT, 100_000_000, at=T0+1000),
            "momentum:"+MINT: quote("momentum", MINT, 25_000_000, at=T0+1000),
        },
    )
    report = replay_exit_gated([a,b], {"a":evidence(), "b":extra})
    assert report["replay_report"]["ledgers"]["new_launch"]["successful_buys"] == 1
    assert report["replay_report"]["ledgers"]["momentum"]["successful_buys"] == 1
    missing = deepcopy(extra)
    del missing["full_sell_quotes"]["new_launch:"+MINT]
    report = replay_exit_gated([a,b], {"a":evidence(), "b":missing})
    assert report["replay_report"]["ledgers"]["momentum"]["successful_buys"] == 0
    assert report["gate_audit"][-1]["reason"] == "missing_exit_snapshot"


def test_connection_restored_can_recheck_but_not_auto_trade():
    a = step("a")
    b = step("b", at=T0+1000, amount="25", output="25")
    c = step("c", at=T0+2000, amount="25", output="25")
    good = evidence(T0+2000, q=quote("new_launch", MINT, 125_000_000, at=T0+2000))
    report = replay_exit_gated(
        [a,b,c], {
            "a":evidence(),
            "b":evidence(T0+1000, up=False),
            "c":good,
        },
    )
    assert report["replay_report"]["ledgers"]["new_launch"]["successful_buys"] == 2
    assert report["replay_report"]["ledgers"]["new_launch"]["audit"][1]["reason"] == "exit_quote_feed_disconnected"
    assert report["gate_audit"][-1]["status"] == "scenario_coverage_only"


@pytest.mark.parametrize("bad", [
    {"provider_status": {}, "token_decimals": {}, "full_sell_quotes": {}},
    {"provider_status": "up", "token_decimals": {}, "full_sell_quotes": {}},
    {"provider_status": {"source":"live_verified"}, "token_decimals": {}, "full_sell_quotes": {}},
    {"random_private_key": "must_not_be_accepted"},
])
def test_invalid_evidence_fails_closed_without_any_api_execution(bad):
    x = step("x")
    data = gate(x, bad)
    assert data["replay_report"]["ledgers"]["new_launch"]["successful_buys"] == 0
    assert data["gate_audit"][0]["status"] == "blocked"


def test_extra_evidence_for_sell_is_rejected():
    a = step("a", side="sell")
    with pytest.raises(ValueError, match="orphan"):
        replay_exit_gated([a], {"a": evidence()})


def test_v11_direct_blocked_entry_quote_gate_is_replayable_and_cannot_be_cleared():
    x = step("x")
    x["exit_quote_gate"] = {"status":"blocked", "reason":"feed_disconnected"}
    report = replay_marked_guarded([x])
    assert report["ledgers"]["new_launch"]["audit"][0]["reason"] == "exit_quote_feed_disconnected"
    x["exit_quote_gate"] = {"status":"approved", "reason":"feed_disconnected"}
    with pytest.raises(ValueError, match="invalid_exit_quote_gate"):
        replay_marked_guarded([x])


def test_static_readiness_endpoint_has_no_online_price_provider_or_order_routes():
    app = FastAPI()
    app.include_router(router, prefix="/api/v1/meme-coins")
    c = TestClient(app)
    r = c.get("/api/v1/meme-coins/paper/exit-guard-readiness")
    assert r.status_code == 200
    assert r.json() == readiness()
    assert r.json()["full_exit_quotes_verified_live"] is False
    assert r.json()["paper_safety_scheduler_running"] is False
    assert r.json()["provider_market_timestamps_verified"] is False
    assert r.json()["connectivity_from_live_providers"] is False
    assert r.json()["live_trading_enabled"] is False
    assert c.post("/api/v1/meme-coins/paper/exit-guard-readiness", json={}).status_code == 405
