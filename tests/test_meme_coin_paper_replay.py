"""Offline paper replay contracts: zero live trading, isolated ledgers, strict quotes."""
from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.v1.endpoints.meme_coin import router
from src.services import meme_coin_paper_replay as paper

MINT = "So11111111111111111111111111111111111111112"
MINT_OTHER = "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v"


def event(
    event_id="e1", *, strategy="new_launch", side="buy", mint=MINT,
    observed=1000, attempted=1200, amount="50", output="100",
    network_fee="0.01", priority_fee="0.00", slippage=100,
    outcome="success",
):
    return {
        "id": event_id, "strategy": strategy, "mint": mint,
        "side": side, "source": "offline_fixture",
        "quote_observed_at_ms": observed, "attempted_at_ms": attempted,
        "amount_in": amount, "expected_out": output,
        "network_fee_usd": network_fee, "priority_fee_usd": priority_fee,
        "modeled_adverse_slippage_bps": slippage, "outcome": outcome,
    }


def test_separate_strategy_ledgers_and_fee_adjusted_sell_pnl():
    events = [
        event(),
        event("e2", strategy="momentum", mint=MINT, amount="40", output="80",
              network_fee="0.02", slippage=0, observed=1300, attempted=1400),
        event("e3", side="sell", amount="99", output="60", observed=1600, attempted=1700),
    ]
    result = paper.replay(events)
    a = result["ledgers"]["new_launch"]
    b = result["ledgers"]["momentum"]
    assert result["mode"] == "offline_fixture_replay"
    assert result["data_is_live"] is False
    assert result["live_trading_enabled"] is False
    assert result["quote_adapter_connected"] is False
    assert a["cash_usd"] == "1009.38"
    assert a["realized_pnl_usd"] == "9.38"
    assert a["network_and_priority_fees_usd"] == "0.02"
    assert a["positions"] == {}
    assert a["successful_buys"] == a["successful_sells"] == 1
    assert b["cash_usd"] == "959.98"
    assert b["realized_pnl_usd"] == "0.00"
    assert b["positions"][MINT]["quantity"] == "80.000000000"
    assert all(not a["audit"][i]["execution_is_real"] for i in range(len(a["audit"])))


def test_quote_age_limit_blocks_fills_and_no_lookahead_allowed():
    bad = event(observed=1000, attempted=4501)
    ledger = paper.replay([bad])["ledgers"]["new_launch"]
    assert ledger["rejected_events"] == 1
    assert ledger["audit"][0]["reason"] == "stale_quote"
    assert ledger["cash_usd"] == "1000.00"
    assert ledger["positions"] == {}
    with pytest.raises(ValueError, match="future_quote"):
        paper.replay([event(observed=1201, attempted=1200)])


def test_slippage_cap_and_network_rejection_no_fill():
    cases = [
        event("slippage", slippage=1001),
        event("timeout", outcome="timeout", observed=1300, attempted=1400),
        event("reject", outcome="rejected_by_network", observed=1500, attempted=1600),
    ]
    ledger = paper.replay(cases)["ledgers"]["new_launch"]
    assert ledger["rejected_events"] == 3
    assert ledger["failed_transactions"] == 0
    assert ledger["cash_usd"] == "1000.00"
    assert ledger["positions"] == {}


def test_onchain_failure_charges_gas_but_does_not_create_tokens():
    ledger = paper.replay([event(outcome="onchain_failure", network_fee="0.02",
                                 priority_fee="0.03")])["ledgers"]["new_launch"]
    assert ledger["failed_transactions"] == 1
    assert ledger["cash_usd"] == "999.95"
    assert ledger["network_and_priority_fees_usd"] == "0.05"
    assert ledger["audit"][0]["status"] == "onchain_failed"
    assert ledger["positions"] == {}


def test_sell_without_holdings_never_creates_short_or_cash():
    ledger = paper.replay([event(side="sell", amount="2", output="100")])["ledgers"]["new_launch"]
    assert ledger["cash_usd"] == "1000.00"
    assert ledger["successful_sells"] == 0
    assert ledger["audit"][0]["reason"] == "insufficient_token_quantity"


def test_position_budget_and_order_budget_rejected_without_spending():
    ledger = paper.replay([event(amount="101")])["ledgers"]["new_launch"]
    assert ledger["rejected_events"] == 1
    assert ledger["cash_usd"] == "1000.00"

    cases = [
        event("a", amount="100", output="100", slippage=0),
        event("b", amount="99.98", output="100", observed=1300, attempted=1400, slippage=0),
        event("c", amount="1", output="2", observed=1500, attempted=1600),
    ]
    ledger = paper.replay(cases)["ledgers"]["new_launch"]
    assert ledger["rejected_events"] == 1
    assert ledger["audit"][-1]["reason"] == "max_token_exposure"


def test_three_open_positions_limit_per_strategy():
    events = [
        event("e1", mint=MINT, amount="10", output="10"),
        event("e2", mint=MINT_OTHER, amount="10", output="10", observed=1300, attempted=1400),
        event("e3", mint="11111111111111111111111111111111", amount="10", output="10", observed=1500, attempted=1600),
        event("e4", mint="TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA",
              amount="10", output="10", observed=1700, attempted=1800),
    ]
    ledger = paper.replay(events)["ledgers"]["new_launch"]
    assert len(ledger["positions"]) == 3
    assert ledger["audit"][-1]["reason"] == "too_many_open_positions"


@pytest.mark.parametrize("changes", [
    {"source": "live_jupiter"},
    {"strategy": "robinhood_chain"},
    {"side": "swap"},
    {"mint": "invalid"},
    {"amount_in": 50.0},
    {"expected_out": "NaN"},
    {"network_fee_usd": "-1"},
    {"priority_fee_usd": "Infinity"},
    {"modeled_adverse_slippage_bps": -1},
    {"modeled_adverse_slippage_bps": 1.5},
    {"outcome": "unknown"},
])
def test_invalid_quote_inputs_rejected_fully(changes):
    e = event()
    e.update(changes)
    with pytest.raises((ValueError, TypeError)):
        paper.replay([e])


def test_duplicate_identifiers_reverse_time_and_invalid_fixture_shape_fail():
    with pytest.raises(ValueError, match="duplicate"):
        paper.replay([event(), event()])
    with pytest.raises(ValueError, match="non_chronological"):
        paper.replay([event(), event("e2", observed=100, attempted=200)])
    with pytest.raises(ValueError, match="event_fields"):
        paper.replay([{**event(), "wallet_key": "MUST_NOT_ACCEPT"}])
    with pytest.raises(ValueError):
        paper.replay([event()] * (paper.MAX_EVENTS + 1))


def test_partial_sale_cost_basis_is_proportional_and_always_strategy_isolated():
    result = paper.replay([
        event(amount="100", output="100", slippage=0, network_fee="0.00"),
        event("s", side="sell", amount="40", output="50", observed=1300,
              attempted=1400, slippage=0, network_fee="0.00"),
    ])
    ledger = result["ledgers"]["new_launch"]
    assert ledger["cash_usd"] == "950.00"
    assert ledger["realized_pnl_usd"] == "10.00"
    assert ledger["positions"][MINT]["quantity"] == "60.000000000"
    assert ledger["positions"][MINT]["cost_basis_usd"] == "60.00"
    assert result["ledgers"]["momentum"]["cash_usd"] == "1000.00"


def test_rerun_is_deterministic_and_original_events_unchanged():
    events = [event()]
    original = deepcopy(events)
    assert paper.replay(events) == paper.replay(events)
    assert events == original


def test_rest_status_reports_no_live_quotes_and_no_performance_data():
    status = paper.status()
    assert status["status"] == "offline_replay_available"
    assert [s["strategy"] for s in status["strategy_ledgers"]] == ["new_launch", "momentum"]
    assert status["live_quotes_connected"] is False
    assert status["paper_automated"] is False
    assert all(s["realized_pnl_usd"] is None for s in status["strategy_ledgers"])


def test_read_only_status_route_has_no_orders_or_wallet_endpoint():
    app = FastAPI()
    app.include_router(router, prefix="/api/v1/meme-coins")
    client = TestClient(app)
    response = client.get("/api/v1/meme-coins/paper/status")
    assert response.status_code == 200
    assert response.json()["strategy_ledgers"][0]["state"] == "not_running"
    assert response.json()["live_trading_enabled"] is False
    assert client.post("/api/v1/meme-coins/paper/status", json={}).status_code == 405
    assert not any("wallet" in getattr(route, "path", "") or "order" in getattr(route, "path", "")
                   for route in app.routes)
