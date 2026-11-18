"""Pure offline checks: the paper preview cannot become trading."""
from __future__ import annotations

from unittest.mock import patch

import pytest

from src.services.meme_coin_paper_preview import preview_synthetic_round_trip
from src.services.meme_coin_strategy_service import get_meme_coin_overview


def case(**overrides):
    values = dict(
        strategy="new_launch",
        synthetic_entry_price_usd="1",
        synthetic_exit_price_usd="1",
        requested_notional_usd="20",
        synthetic_equity_usd="1000",
        synthetic_pool_liquidity_usd="100000",
        snapshot_age_seconds="10",
        synthetic_daily_realized_loss_usd="0",
    )
    values.update(overrides)
    return preview_synthetic_round_trip(**values)


def test_flat_synthetic_price_loses_to_fees_and_slippage():
    r = case()
    assert r["status"] == "synthetic_preview_only"
    assert float(r["net_pnl_usd"]) < 0
    assert r["assumed_entry_fee_bps"] == 30
    assert r["assumed_slippage_bps_per_side"] == 100
    assert r["trade_executed"] is r["paper_trading_enabled"] is False
    assert r["live_trading_enabled"] is r["realized_performance"] is False


def test_independent_strategies_remain_only_synthetic():
    a = case()
    b = case(strategy="momentum", synthetic_exit_price_usd="2")
    assert a["strategy"] == "new_launch"
    assert b["strategy"] == "momentum"
    assert b["status"] == "synthetic_preview_only"
    assert float(b["net_pnl_usd"]) > 0
    for s in get_meme_coin_overview()["strategies"]:
        assert s["paper_trading_enabled"] is False
        assert s["metrics"]["trades"] is None


@pytest.mark.parametrize("change,reason", [
    ({"strategy": "invalid"}, "unknown_strategy"),
    ({"requested_notional_usd": 25}, "position_limit_exceeded"),
    ({"requested_notional_usd": "21"}, "position_limit_exceeded"),
    ({"synthetic_equity_usd": "100"}, "position_limit_exceeded"),
    ({"synthetic_pool_liquidity_usd": "100"}, "low_synthetic_liquidity"),
    ({"synthetic_pool_liquidity_usd": "50000"}, "pool_share_limit_exceeded"),
    ({"snapshot_age_seconds": 61}, "stale_synthetic_snapshot"),
    ({"synthetic_daily_realized_loss_usd": "29"}, "daily_loss_budget_exceeded"),
    ({"synthetic_entry_price_usd": "NaN"}, "invalid_synthetic_inputs"),
    ({"synthetic_exit_price_usd": float("inf")}, "invalid_synthetic_inputs"),
    ({"requested_notional_usd": -2}, "invalid_synthetic_inputs"),
    ({"requested_notional_usd": True}, "invalid_synthetic_inputs"),
    ({"snapshot_age_seconds": -1}, "invalid_synthetic_inputs"),
    ({"synthetic_daily_realized_loss_usd": None}, "invalid_synthetic_inputs"),
])
def test_fail_closed(change, reason):
    r = case(**change)
    assert r["status"] == "blocked"
    assert r["reason"] == reason
    assert r["net_pnl_usd"] is None
    assert r["trade_executed"] is False


def test_preview_never_uses_provider_or_wallet(monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("network access is forbidden")
    with patch("urllib.request.urlopen", forbidden):
        r = case()
    assert r["status"] == "synthetic_preview_only"
    assert r["trade_executed"] is False
