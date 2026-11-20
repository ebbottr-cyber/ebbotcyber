"""Deterministic accounting and time-order guardrail tests for Solana paper replay."""
from decimal import Decimal

import pytest

from src.services.solana_paper_replay import PaperSettings, replay


def tick(t, p, status="watch", reasons=()):
    return {"timestamp_ms": t, "price_usd": p, "status": status, "reasons": list(reasons)}


def test_no_same_tick_fill_and_unfilled_final_signal():
    x = replay([tick(1, ".1", "blocked", ["security_unknown"]), tick(2, ".2")], strategy="momentum_watcher")
    assert x["entries"] == 0
    assert x["closed_trades"] == []
    assert x["open_position"] is None
    assert x["initial_cash_usd"] == x["estimated_equity_usd"]


def test_buy_executes_next_tick_only_and_final_position_unrealized():
    x = replay([tick(1, ".10"), tick(2, ".11")], strategy="new_coin_hunter")
    assert x["entries"] == 1
    assert x["closed_trades"] == []
    assert x["realized_pnl_usd"] == "0.00"
    assert x["open_position"]["entry_fill_ms"] == 2
    assert x["open_position"]["unrealized_pnl_usd"].startswith("-")


def test_risk_change_between_signal_and_fill_cancels_buy():
    x = replay([tick(1, ".10"), tick(2, ".11", "blocked", ["transfer_hook"]), tick(3, ".12", "blocked", ["transfer_hook"])], strategy="momentum_watcher")
    assert x["entries"] == 0
    assert x["canceled_buy_signals"] == 1


def test_take_profit_fills_next_quote_not_trigger_quote():
    x = replay([tick(1, ".10"), tick(2, ".10"), tick(3, ".14"), tick(4, ".105")], strategy="momentum_watcher")
    trade = x["closed_trades"][0]
    assert trade["entry_signal_ms"] == 1
    assert trade["entry_fill_ms"] == 2
    assert trade["exit_signal_ms"] == 3
    assert trade["exit_fill_ms"] == 4
    assert trade["reason"] == "take_profit"
    assert Decimal(trade["pnl_usd"]) < Decimal("5.00")


def test_stop_loss_gap_can_exceed_stop_threshold():
    x = replay([tick(1, ".10"), tick(2, ".10"), tick(3, ".08"), tick(4, ".05")], strategy="new_coin_hunter")
    trade = x["closed_trades"][0]
    assert trade["reason"] == "stop_loss"
    assert trade["exit_fill_ms"] == 4
    assert Decimal(trade["pnl_usd"]) < Decimal("-8")


def test_blocked_risk_forces_exit_on_next_quote():
    x = replay([tick(1, ".10"), tick(2, ".10"), tick(3, ".11", "blocked", ["security_unknown"]), tick(4, ".12")], strategy="new_coin_hunter")
    assert x["closed_trades"][0]["reason"] == "risk_blocked"
    assert x["closed_trades"][0]["exit_fill_ms"] == 4


def test_pending_exit_without_next_tick_remains_unrealized():
    x = replay([tick(1, ".10"), tick(2, ".10"), tick(3, ".20")], strategy="momentum_watcher")
    assert x["closed_trades"] == []
    assert x["open_position"]["pending_exit_without_fill"] == "take_profit"


def test_fees_and_slippage_cannot_improve_same_path_pnl():
    path = [tick(1, ".10"), tick(2, ".10"), tick(3, ".20"), tick(4, ".11")]
    costly = replay(path, strategy="momentum_watcher")
    free = replay(path, strategy="momentum_watcher", settings=PaperSettings(fee_bps=Decimal(0), slippage_bps=Decimal(0)))
    assert Decimal(costly["realized_pnl_usd"]) < Decimal(free["realized_pnl_usd"])
    assert costly["total_paid_fees_usd"] != "0.00"


@pytest.mark.parametrize("path", [
    [tick(1, ".10")],
    [tick(1, ".10"), tick(1, ".11")],
    [tick(2, ".10"), tick(1, ".11")],
    [tick(1, "nan"), tick(2, ".10")],
    [tick(1, "-1"), tick(2, ".10")],
    [tick(1, ".1", "watch", ["mintable"]), tick(2, ".11")],
    [tick(1, ".1", "blocked", []), tick(2, ".11")],
])
def test_malformed_or_futuristic_input_fails_closed(path):
    with pytest.raises(ValueError):
        replay(path, strategy="momentum_watcher")


def test_invalid_config_rejected():
    with pytest.raises(ValueError):
        replay([tick(1, ".1"), tick(2, ".1")], strategy="momentum_watcher", settings=PaperSettings(allocation_fraction=Decimal("1")))


def test_time_limit_triggers_at_observation_then_fills_next():
    cfg = PaperSettings(maximum_hold_snapshots=1, stop_loss_fraction=Decimal(".9"), take_profit_fraction=Decimal("4"))
    x = replay([tick(1, ".1"), tick(2, ".1"), tick(3, ".1"), tick(4, ".1")], strategy="new_coin_hunter", settings=cfg)
    assert x["closed_trades"][0]["reason"] == "time_limit"
    assert x["closed_trades"][0]["exit_fill_ms"] == 4
