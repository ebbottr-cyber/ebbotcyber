"""Offline test data only; no token address, wallet, market or network I/O."""
from __future__ import annotations

from copy import deepcopy
from unittest.mock import patch

import pytest

from src.services.meme_coin_synthetic_journal import replay_synthetic_journal
from src.services.meme_coin_strategy_service import get_meme_coin_overview


def event(event_id="a1", strategy="new_launch", day="2026-11-18", **kwargs):
    values = dict(
        event_id=event_id, trading_day=day, strategy=strategy,
        synthetic_entry_price_usd="1", synthetic_exit_price_usd="1",
        requested_notional_usd="10", synthetic_pool_liquidity_usd="100000",
        snapshot_age_seconds="10",
    )
    values.update(kwargs)
    return values


def replay(events, **kwargs):
    return replay_synthetic_journal(
        starting_equity_usd="1000", events=events, **kwargs
    )


def test_two_independent_journals_and_account_reconciliation():
    first = event("new1", synthetic_exit_price_usd="1.5")
    second = event("mom1", strategy="momentum", synthetic_exit_price_usd="0.5")
    before = deepcopy([first, second])
    r = replay([first, second])
    assert [first, second] == before
    assert r["status"] == "synthetic_preview_only"
    assert r["trade_executed"] is r["paper_trading_enabled"] is False
    assert r["live_trading_enabled"] is r["realized_performance"] is False
    a = r["strategies"]["new_launch"]
    b = r["strategies"]["momentum"]
    assert len(a["records"]) == len(b["records"]) == 1
    assert a["records"][0]["strategy"] == "new_launch"
    assert b["records"][0]["strategy"] == "momentum"
    assert float(a["synthetic_net_pnl_usd"]) > 0
    assert float(b["synthetic_net_pnl_usd"]) < 0
    assert r["summary"]["synthetic_round_trips"] == 2
    combined = round(float(a["synthetic_net_pnl_usd"]) +
                     float(b["synthetic_net_pnl_usd"]), 2)
    assert float(r["summary"]["synthetic_net_pnl_usd"]) == pytest.approx(combined)
    assert r == replay([first, second])
    for strategy in get_meme_coin_overview()["strategies"]:
        assert strategy["paper_trading_enabled"] is False
        assert strategy["metrics"]["net_pnl_usd"] is None


def test_idempotent_duplicate_event_not_counted_twice():
    one = event("idempotent")
    r = replay([one, deepcopy(one)])
    assert r["summary"]["synthetic_round_trips"] == 1
    assert r["audit"][1]["result"] == "duplicate_ignored"


def test_conflicting_id_across_strategies_fails_entire_replay_closed():
    r = replay([event("same"), event("same", strategy="momentum")])
    assert r["status"] == "blocked"
    assert r["reason"] == "conflicting_event_id"
    assert r["strategies"] == {}
    assert r["audit"] == []


def test_strategy_daily_budget_only_blocks_same_strategy():
    events = [
        event("loss1", synthetic_exit_price_usd="0.01",
              requested_notional_usd="20"),
        event("loss2", synthetic_exit_price_usd="2",
              requested_notional_usd="10"),
        event("mom", strategy="momentum"),
    ]
    r = replay(events)
    assert r["audit"][1]["reason"] == "strategy_daily_risk_budget"
    assert r["audit"][2]["result"] == "synthetic_recorded"
    assert r["strategies"]["new_launch"]["synthetic_round_trips"] == 1
    assert r["strategies"]["momentum"]["synthetic_round_trips"] == 1


def test_shared_daily_loss_halts_both_strategies_but_new_day_restarts():
    events = [
        event("l1", synthetic_exit_price_usd="0.01",
              requested_notional_usd="20"),
        event("l2", strategy="momentum", synthetic_exit_price_usd="0.01",
              requested_notional_usd="19"),
        event("l3", synthetic_exit_price_usd="2"),
        event("l4", strategy="momentum", synthetic_exit_price_usd="2"),
        event("next", day="2026-11-19", synthetic_exit_price_usd="1.1"),
    ]
    r = replay(events)
    assert [a["reason"] for a in r["audit"][2:4]] == [
        "global_daily_risk_budget", "global_daily_risk_budget"
    ]
    assert r["audit"][4]["result"] == "synthetic_recorded"
    assert r["summary"]["synthetic_round_trips"] == 3
    assert float(r["summary"]["daily_gross_synthetic_losses_usd"]["2026-11-18"]) > 30


def test_manual_kill_switch_blocks_all_preview_records():
    r = replay([event("one"), event("two", strategy="momentum")],
               manual_kill_switch=True)
    assert r["summary"]["synthetic_round_trips"] == 0
    assert all(a["reason"] == "manual_kill_switch" for a in r["audit"])


@pytest.mark.parametrize("payload,reason", [
    ([{**event(), "token_address": "forbidden"}], "invalid_synthetic_event_shape"),
    ([event(day="2026-99-99")], "invalid_trading_day"),
    ([event(event_id="*")], "invalid_synthetic_event_id"),
    ([event(strategy="not-real")], "unknown_strategy"),
    ([event("later", day="2026-11-19"),
      event("earlier", day="2026-11-18")], "events_out_of_order"),
])
def test_invalid_scenarios_fail_closed(payload, reason):
    r = replay(payload)
    assert r["status"] == "blocked"
    assert r["reason"] == reason
    assert r["summary"] is None


def test_preview_failure_rejected_without_any_pnl():
    r = replay([event("bad", synthetic_entry_price_usd="NaN")])
    assert r["summary"]["synthetic_round_trips"] == 0
    assert r["audit"][0]["result"] == "rejected"
    assert r["audit"][0]["reason"] == "invalid_synthetic_inputs"


def test_no_io_or_provider_access():
    with patch("urllib.request.urlopen", side_effect=AssertionError("network forbidden")):
        result = replay([event("a"), event("b", strategy="momentum")])
    assert result["summary"]["synthetic_round_trips"] == 2
