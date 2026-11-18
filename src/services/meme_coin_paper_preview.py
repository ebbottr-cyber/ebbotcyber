"""Deterministic, synthetic-only meme coin paper *preview*.

No network, wallet, storage, order placement, real-market data or automation.
This is NOT an executable paper broker or a source of performance metrics.
"""
from __future__ import annotations

from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from typing import Any

STRATEGIES = frozenset({"new_launch", "momentum"})
MAX_SINGLE_ORDER_USD = Decimal("25")
MAX_EQUITY_EXPOSURE = Decimal("0.02")
MAX_DAILY_LOSS_FRACTION = Decimal("0.03")
ASSUMED_STOP_LOSS_FRACTION = Decimal("0.10")
MIN_POOL_LIQUIDITY_USD = Decimal("50000")
MAX_POOL_SHARE = Decimal("0.0003")
MAX_SNAPSHOT_AGE_SECONDS = Decimal("60")
ASSUMED_FEE_BPS = Decimal("30")
ASSUMED_SLIPPAGE_BPS = Decimal("100")
_BPS = Decimal("10000")
_CENTS = Decimal("0.01")


def _positive_decimal(value: Any) -> Decimal:
    if isinstance(value, bool) or value is None:
        raise ValueError("invalid numeric input")
    try:
        number = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        raise ValueError("invalid numeric input") from None
    if not number.is_finite() or number <= 0 or number > Decimal("1e12"):
        raise ValueError("out-of-range numeric input")
    return number


def _nonnegative_decimal(value: Any) -> Decimal:
    if value == 0 and not isinstance(value, bool):
        return Decimal("0")
    return _positive_decimal(value)


def _blocked(strategy: str, reason: str) -> dict[str, Any]:
    return {
        "strategy": strategy,
        "status": "blocked",
        "reason": reason,
        "net_pnl_usd": None,
        "trade_executed": False,
        "paper_trading_enabled": False,
        "live_trading_enabled": False,
    }


def preview_synthetic_round_trip(
    *,
    strategy: str,
    synthetic_entry_price_usd: Any,
    synthetic_exit_price_usd: Any,
    requested_notional_usd: Any,
    synthetic_equity_usd: Any,
    synthetic_pool_liquidity_usd: Any,
    snapshot_age_seconds: Any,
    synthetic_daily_realized_loss_usd: Any = 0,
) -> dict[str, Any]:
    """Model round-trip fees and slippage on caller-provided SYNTHETIC numbers.

    This function never accepts token identifiers, authorities, API keys, wallets
    or a candidate from discovery. It cannot certify an asset as safe, and it
    MUST NOT be connected to live candidate orders or dashboard PnL.
    """
    if strategy not in STRATEGIES:
        return _blocked(strategy, "unknown_strategy")
    try:
        entry = _positive_decimal(synthetic_entry_price_usd)
        exit_price = _positive_decimal(synthetic_exit_price_usd)
        notional = _positive_decimal(requested_notional_usd)
        equity = _positive_decimal(synthetic_equity_usd)
        liquidity = _positive_decimal(synthetic_pool_liquidity_usd)
        age = _nonnegative_decimal(snapshot_age_seconds)
        realized_loss = _nonnegative_decimal(synthetic_daily_realized_loss_usd)
    except ValueError:
        return _blocked(strategy, "invalid_synthetic_inputs")

    if age > MAX_SNAPSHOT_AGE_SECONDS:
        return _blocked(strategy, "stale_synthetic_snapshot")
    if liquidity < MIN_POOL_LIQUIDITY_USD:
        return _blocked(strategy, "low_synthetic_liquidity")
    if notional > MAX_SINGLE_ORDER_USD or notional > equity * MAX_EQUITY_EXPOSURE:
        return _blocked(strategy, "position_limit_exceeded")
    if notional > liquidity * MAX_POOL_SHARE:
        return _blocked(strategy, "pool_share_limit_exceeded")
    if (realized_loss + notional * ASSUMED_STOP_LOSS_FRACTION
            > equity * MAX_DAILY_LOSS_FRACTION):
        return _blocked(strategy, "daily_loss_budget_exceeded")

    fee_rate = ASSUMED_FEE_BPS / _BPS
    slip_rate = ASSUMED_SLIPPAGE_BPS / _BPS
    # Conservative: buy at the more expensive and sell at the cheaper quote.
    entry_execution_price = entry * (Decimal("1") + slip_rate)
    exit_execution_price = exit_price * (Decimal("1") - slip_rate)
    entry_fee = notional * fee_rate
    units = (notional - entry_fee) / entry_execution_price
    gross_exit = units * exit_execution_price
    exit_fee = gross_exit * fee_rate
    received = gross_exit - exit_fee
    pnl = (received - notional).quantize(_CENTS, rounding=ROUND_HALF_UP)

    return {
        "strategy": strategy,
        "status": "synthetic_preview_only",
        "reason": None,
        "net_pnl_usd": str(pnl),
        "assumed_entry_fee_bps": int(ASSUMED_FEE_BPS),
        "assumed_exit_fee_bps": int(ASSUMED_FEE_BPS),
        "assumed_slippage_bps_per_side": int(ASSUMED_SLIPPAGE_BPS),
        "trade_executed": False,
        "paper_trading_enabled": False,
        "live_trading_enabled": False,
        "realized_performance": False,
    }
