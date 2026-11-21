"""Offline mark-to-market paper PnL and drawdown fail-closed contracts."""
from __future__ import annotations

from copy import deepcopy

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.v1.endpoints.meme_coin import router
from src.services.meme_coin_paper_mtm import replay_marked_guarded, readiness

MINT = "11111111111111111111111111111111"
SECOND = "So11111111111111111111111111111111111111112"


def event(identifier, *, strategy="new_launch", side="buy",
          amount="100", output="100", at=1000200, mint=MINT,
          outcome="success", fee="0.00"):
    return {
        "id": identifier, "strategy": strategy, "mint": mint,
        "side": side, "source": "offline_fixture",
        "quote_observed_at_ms": at - 200,
        "attempted_at_ms": at,
        "amount_in": amount, "expected_out": output,
        "network_fee_usd": fee, "priority_fee_usd": "0.00",
        "modeled_adverse_slippage_bps": 0,
        "outcome": outcome,
    }


def step(identifier, *, strategy="new_launch", side="buy",
         amount="100", output="100", at=1000200, mint=MINT,
         prices=None, emergency=False, risk_liq="60000", outcome="success", fee="0.00"):
    e = event(identifier, strategy=strategy, side=side, amount=amount,
              output=output, at=at, mint=mint, outcome=outcome, fee=fee)
    if prices is None:
        prices = {MINT: "1"}
    record = {
        "event": e,
        "risk_fact": {
            "source": "offline_assumption",
            "liquidity_usd": risk_liq, "observed_at_ms": at - 100,
        },
        "marks": {
            address: {
                "source": "offline_assumption", "bid_price_usd": price,
                "observed_at_ms": at - 100,
            }
            for address, price in prices.items()
        },
    }
    if emergency:
        record["emergency_stop"] = True
    return record


def test_unrealized_loss_trips_daily_buy_circuit_without_fabricating_real_trades():
    first = step("buy")
    later = step("second", at=1001200, prices={MINT: "0.4"}, amount="25")
    data = replay_marked_guarded([first, later])
    a = data["ledgers"]["new_launch"]
    assert a["successful_buys"] == 1
    assert a["marked_equity_usd"] == "940.00"
    assert a["unrealized_pnl_usd"] == "-60.00"
    assert a["realized_pnl_usd"] == "0.00"
    assert a["daily_mark_drawdown_circuit_open"] is True
    assert a["audit"][-1]["reason"] == "daily_strategy_mark_drawdown_limit"
    assert data["all_marks_are_unverified_offline_assumptions"] is True
    assert data["mark_is_executable_quote"] is False
    assert data["automatic_paper_trading_enabled"] is False
    assert data["live_trading_enabled"] is False


def test_global_mark_drawdown_blocks_both_strategy_buy_scenarios():
    first = step("a1")
    second = step("b1", strategy="momentum", at=1001200)
    third = step("a2", amount="25", at=1002200, prices={MINT: "0.4"})
    fourth = step("b2", strategy="momentum", amount="25", at=1003200, prices={MINT: "0.4"})
    data = replay_marked_guarded([first, second, third, fourth])
    assert data["global_mark_drawdown_circuit_open"] is True
    assert data["global_latest_equity_usd"] == "1880.00"
    for strategy in ("new_launch", "momentum"):
        ledger = data["ledgers"][strategy]
        assert ledger["successful_buys"] == 1
        assert ledger["audit"][-1]["reason"] == "global_mark_drawdown_limit"


def test_missing_marks_block_new_buys_without_fabricating_equity():
    first = step("a1")
    missing = step("a2", amount="25", at=1001200, prices={})
    data = replay_marked_guarded([first, missing])
    a = data["ledgers"]["new_launch"]
    assert a["audit"][-1]["reason"] == "unverified_portfolio_marks"
    assert a["marked_equity_usd"] is None
    assert a["unrealized_pnl_usd"] is None
    assert data["global_latest_equity_usd"] is None
    assert data["last_mark_problems"] == ["missing_mark:" + MINT]


def test_stale_marks_or_future_marks_block_new_buys():
    stale = step("a1", at=1000200)
    stale["marks"][MINT]["observed_at_ms"] = 960000
    outcome = replay_marked_guarded([stale])["ledgers"]["new_launch"]
    assert outcome["audit"][-1]["reason"] == "missing_stale_or_future_buy_mark"
    future = step("b1")
    future["marks"][MINT]["observed_at_ms"] += 1000
    outcome = replay_marked_guarded([future])["ledgers"]["new_launch"]
    assert outcome["audit"][-1]["reason"] == "missing_stale_or_future_buy_mark"


def test_soft_halt_does_not_force_sell_execution_and_allows_qualified_sell_scenario():
    buy = step("buy")
    down = step("down", amount="25", at=1001200, prices={MINT: "0.4"})
    sell = step("sell", side="sell", amount="100", output="40",
                at=1002200, prices={MINT: "0.4"})
    data = replay_marked_guarded([buy, down, sell])
    ledger = data["ledgers"]["new_launch"]
    assert ledger["successful_sells"] == 1
    assert ledger["cash_usd"] == "940.00"
    assert ledger["positions"] == {}
    assert ledger["realized_pnl_usd"] == "-60.00"
    assert ledger["audit"][-1]["status"] == "filled_scenario"


def test_hard_stop_flag_persists_for_all_subsequent_steps_in_replay():
    first = step("a")
    stop = step("stop", at=1001200, emergency=True, amount="25")
    later = step("later", at=1002200, amount="25")
    data = replay_marked_guarded([first, stop, later])
    a = data["ledgers"]["new_launch"]
    assert a["successful_buys"] == 1
    assert [row["reason"] for row in a["audit"]][-2:] == ["emergency_stop", "emergency_stop"]
    assert data["emergency_stop_persisted_in_steps"] is True
    assert data["emergency_stop_enabled"] is True


def test_operator_hard_stop_blocks_even_first_buy():
    result = replay_marked_guarded([step("a")], emergency_stop=True)
    assert result["ledgers"]["new_launch"]["cash_usd"] == "1000.00"
    assert result["ledgers"]["new_launch"]["audit"][0]["reason"] == "emergency_stop"


def test_missing_mark_in_other_strategy_blocks_new_buy():
    a = step("a")
    b = step("b", strategy="momentum", at=1001200, mint=SECOND, prices={MINT: "1", SECOND: "1"})
    c = step("c", at=1002200, prices={MINT: "1"})
    data = replay_marked_guarded([a, b, c])
    assert data["ledgers"]["new_launch"]["audit"][-1]["reason"] == "unverified_portfolio_marks"


def test_zero_mark_price_is_allowed_as_worst_case_loss_scenario():
    first = step("a")
    second = step("b", at=1001200, amount="25", prices={MINT: "0"})
    report = replay_marked_guarded([first, second])
    assert report["global_latest_equity_usd"] == "1900.00"
    assert report["global_mark_drawdown_circuit_open"] is True


def test_failed_transactions_model_fees_and_latch_failure_circuit():
    steps = [
        step("a", outcome="onchain_failure", fee="0.02"),
        step("b", at=1001200, outcome="timeout"),
        step("c", at=1002200, outcome="rejected_by_network"),
        step("d", at=1003200, amount="25"),
    ]
    report = replay_marked_guarded(steps)
    ledger = report["ledgers"]["new_launch"]
    assert ledger["failed_transactions"] == 1
    assert ledger["consecutive_failure_circuit_open"] is True
    assert ledger["audit"][-1]["reason"] == "consecutive_network_failures"
    assert ledger["cash_usd"] == "999.98"


def test_outdated_risk_fact_low_liquidity_and_order_exposure_fail_closed():
    x = step("a")
    x["risk_fact"]["observed_at_ms"] -= 31000
    assert replay_marked_guarded([x])["ledgers"]["new_launch"]["audit"][-1]["reason"] == "stale_liquidity_observation"
    x = step("a", risk_liq="9999")
    assert replay_marked_guarded([x])["ledgers"]["new_launch"]["audit"][-1]["reason"] == "insufficient_reported_liquidity"
    x = step("a", risk_liq="10000", amount="100")
    assert replay_marked_guarded([x])["ledgers"]["new_launch"]["audit"][-1]["reason"] == "order_too_large_vs_reported_liquidity"


@pytest.mark.parametrize("mutation", [
    lambda s: s["marks"][MINT].update({"source": "oracle_verified"}),
    lambda s: s["marks"][MINT].update({"bid_price_usd": "NaN"}),
    lambda s: s["marks"][MINT].update({"bid_price_usd": -1}),
    lambda s: s["marks"][MINT].update({"observed_at_ms": True}),
    lambda s: s["marks"][MINT].update({"unexpected": "secret"}),
    lambda s: s.update({"wallet_private_key": "sensitive"}),
    lambda s: s.update({"emergency_stop": "false"}),
    lambda s: s["risk_fact"].update({"source": "unverified_live"}),
])
def test_invalid_untrusted_mark_contracts_abort_before_any_scenario(mutation):
    x = step("a")
    mutation(x)
    with pytest.raises((ValueError, TypeError)):
        replay_marked_guarded([x])


def test_replay_determinism_and_no_mutation_of_input():
    steps = [step("a"), step("b", at=1001200, prices={MINT: "0.9"}, amount="25")]
    original = deepcopy(steps)
    assert replay_marked_guarded(steps) == replay_marked_guarded(steps)
    assert steps == original


def test_static_api_status_never_claims_recovery_is_online_or_live():
    app = FastAPI()
    app.include_router(router, prefix="/api/v1/meme-coins")
    client = TestClient(app)
    response = client.get("/api/v1/meme-coins/paper/mtm-readiness")
    assert response.status_code == 200
    body = response.json()
    assert body == readiness()
    assert body["database_online"] is False
    assert body["paper_scheduler_running"] is False
    assert body["live_trading_enabled"] is False
    assert [s["strategy"] for s in body["strategies"]] == ["new_launch", "momentum"]
    assert client.post("/api/v1/meme-coins/paper/mtm-readiness", json={}).status_code == 405
