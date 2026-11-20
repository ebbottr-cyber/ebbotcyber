"""Deterministic OFFLINE replay of hypothetical Solana positions.

No exchange adapter, wallet, network requests, scheduler or order API.
A signal seen at T may fill at T+1 only; no same-snapshot fills.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from typing import Any, Sequence


@dataclass(frozen=True)
class PaperSettings:
    initial_usd: Decimal = Decimal("1000")
    allocation_fraction: Decimal = Decimal("0.10")
    fee_bps: Decimal = Decimal("30")
    slippage_bps: Decimal = Decimal("75")
    stop_loss_fraction: Decimal = Decimal("0.08")
    take_profit_fraction: Decimal = Decimal("0.15")
    maximum_hold_snapshots: int = 8

    def validate(self) -> None:
        fields = (
            self.initial_usd, self.allocation_fraction, self.fee_bps,
            self.slippage_bps, self.stop_loss_fraction, self.take_profit_fraction,
        )
        if any(not isinstance(x, Decimal) or not x.is_finite() for x in fields):
            raise ValueError("Settings must contain finite Decimal values")
        if not 0 < self.initial_usd <= 1_000_000:
            raise ValueError("Invalid initial cash")
        if not 0 < self.allocation_fraction <= Decimal("0.25"):
            raise ValueError("Invalid allocation limit")
        if not 0 <= self.fee_bps <= 1_000 or not 0 <= self.slippage_bps <= 2_000:
            raise ValueError("Fee or slippage out of bounds")
        if not 0 < self.stop_loss_fraction < 1 or not 0 < self.take_profit_fraction <= 5:
            raise ValueError("Stop / take-profit out of bounds")
        if not type(self.maximum_hold_snapshots) is int or not 1 <= self.maximum_hold_snapshots <= 100:
            raise ValueError("Maximum hold snapshots out of bounds")


def _decimal(value: Any) -> Decimal:
    if isinstance(value, bool) or value is None:
        raise ValueError("Missing or invalid price")
    try:
        price = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise ValueError("Missing or invalid price") from exc
    if not price.is_finite() or price <= 0:
        raise ValueError("Nonpositive or nonfinite price")
    return price


def _usd(value: Decimal) -> str:
    return str(value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


def replay(
    snapshots: Sequence[dict[str, Any]],
    *,
    strategy: str,
    settings: PaperSettings | None = None,
) -> dict[str, Any]:
    """One-token replay; one synthetic position maximum per strategy.

    Caller supplies risk-reviewed signals (from the existing Meme Radar
    evaluate() function). Every observation is processed in time order:
      - a watch signal at T schedules a possible buy for T+1;
      - a risk/stop/take signal at T schedules a sell for T+1;
      - incomplete positions are only *marked* at the final quote.
    """
    if strategy not in ("new_coin_hunter", "momentum_watcher"):
        raise ValueError("Unsupported strategy")
    cfg = settings or PaperSettings()
    cfg.validate()
    if not 2 <= len(snapshots) <= 2000:
        raise ValueError("Replay requires 2 to 2000 observations")
    prepared: list[tuple[int, Decimal, str, tuple[str, ...]]] = []
    last_time = -1
    for sample in snapshots:
        if not isinstance(sample, dict):
            raise ValueError("Malformed observation")
        t = sample.get("timestamp_ms")
        if type(t) is not int or t <= last_time:
            raise ValueError("Observations must be strictly chronological")
        last_time = t
        price = _decimal(sample.get("price_usd"))
        status = sample.get("status")
        reasons = sample.get("reasons")
        if status not in ("watch", "blocked") or not isinstance(reasons, (list, tuple)) or not all(isinstance(r, str) and r for r in reasons):
            raise ValueError("Invalid risk-review status or reasons")
        if (status == "watch" and reasons) or (status == "blocked" and not reasons):
            raise ValueError("Watch status cannot bypass risk reasons")
        prepared.append((t, price, status, tuple(reasons)))

    fee = cfg.fee_bps / Decimal("10000")
    slip = cfg.slippage_bps / Decimal("10000")
    cash = cfg.initial_usd
    position: dict[str, Any] | None = None
    pending_buy: int | None = None
    pending_sell: tuple[str, int] | None = None
    closed_trades: list[dict[str, Any]] = []
    entry_count = 0
    canceled_buys = 0
    watch_signals = 0
    blocked_signals = 0
    total_fees = Decimal("0")

    for index, (t, quote, status, reasons) in enumerate(prepared):
        watch_signals += status == "watch"
        blocked_signals += status == "blocked"
        entry_on_this_tick = False
        exit_on_this_tick = False

        # A sell scheduled at the EARLIER quote fills at today's next
        # observed price, including gaps, fees and slippage.
        if pending_sell is not None and position is not None:
            reason, signal_time = pending_sell
            fill = quote * (Decimal("1") - slip)
            proceeds_before_fee = position["quantity"] * fill
            sell_fee = proceeds_before_fee * fee
            proceeds = proceeds_before_fee - sell_fee
            total_fees += sell_fee
            cash += proceeds
            closed_trades.append({
                "entry_signal_ms": position["signal_ms"],
                "entry_fill_ms": position["fill_ms"],
                "exit_signal_ms": signal_time,
                "exit_fill_ms": t,
                "entry_price_usd": str(position["fill_price"]),
                "exit_price_usd": str(fill),
                "reason": reason,
                "pnl_usd": _usd(proceeds - position["cost"]),
                "entry_cost_usd": _usd(position["cost"]),
                "exit_proceeds_usd": _usd(proceeds),
            })
            position = None
            pending_sell = None
            exit_on_this_tick = True

        # Fresh risk status must still be watch at hypothetical buy fill.
        if pending_buy is not None and position is None and not closed_trades:
            if status == "watch" and not reasons:
                fill = quote * (Decimal("1") + slip)
                budget = cash * cfg.allocation_fraction
                qty = budget / (fill * (Decimal("1") + fee))
                buy_fee = qty * fill * fee
                total_fees += buy_fee
                cash -= budget
                position = {
                    "signal_ms": pending_buy,
                    "fill_ms": t,
                    "fill_index": index,
                    "fill_price": fill,
                    "quantity": qty,
                    "cost": budget,
                }
                entry_count += 1
                entry_on_this_tick = True
            else:
                canceled_buys += 1
            pending_buy = None

        if exit_on_this_tick or entry_on_this_tick:
            continue

        # Trigger at this observation; only a later observation can fill.
        if position is not None and pending_sell is None:
            estimated_unit_exit = quote * (Decimal("1") - slip) * (Decimal("1") - fee)
            entry_unit_cost = position["fill_price"] * (Decimal("1") + fee)
            estimated_return = estimated_unit_exit / entry_unit_cost - 1
            reason = None
            if status != "watch" or reasons:
                reason = "risk_blocked"
            elif estimated_return <= -cfg.stop_loss_fraction:
                reason = "stop_loss"
            elif estimated_return >= cfg.take_profit_fraction:
                reason = "take_profit"
            elif index - position["fill_index"] >= cfg.maximum_hold_snapshots:
                reason = "time_limit"
            if reason is not None:
                pending_sell = (reason, t)
        elif position is None and pending_buy is None and not closed_trades and entry_count == 0:
            if status == "watch" and not reasons:
                pending_buy = t

    # Never invent a fill at the final quote: report mark only.
    if position is None:
        equity = cash
        unrealized = Decimal("0")
        marked_open = None
    else:
        last_quote = prepared[-1][1]
        estimated_exit = last_quote * (Decimal("1") - slip)
        marked_liquidation = position["quantity"] * estimated_exit * (Decimal("1") - fee)
        equity = cash + marked_liquidation
        unrealized = marked_liquidation - position["cost"]
        marked_open = {
            "entry_signal_ms": position["signal_ms"],
            "entry_fill_ms": position["fill_ms"],
            "entry_cost_usd": _usd(position["cost"]),
            "marked_liquidation_usd": _usd(marked_liquidation),
            "unrealized_pnl_usd": _usd(unrealized),
            "last_observation_ms": prepared[-1][0],
            "pending_exit_without_fill": pending_sell[0] if pending_sell else None,
        }

    realized = sum((Decimal(t["pnl_usd"]) for t in closed_trades), Decimal("0"))
    return {
        "mode": "offline_paper_replay_only",
        "data_origin": "synthetic_or_caller_provided_not_verified",
        "trading_enabled": False,
        "strategy": strategy,
        "snapshots": len(prepared),
        "signals_watch": watch_signals,
        "signals_blocked": blocked_signals,
        "canceled_buy_signals": canceled_buys,
        "entries": entry_count,
        "closed_trades": closed_trades,
        "open_position": marked_open,
        "initial_cash_usd": _usd(cfg.initial_usd),
        "available_cash_usd": _usd(cash),
        "estimated_equity_usd": _usd(equity),
        "realized_pnl_usd": _usd(realized),
        "unrealized_pnl_usd": _usd(unrealized),
        "total_paid_fees_usd": _usd(total_fees),
        "assumptions": {
            "allocation_fraction": str(cfg.allocation_fraction),
            "fee_bps_each_side": str(cfg.fee_bps),
            "slippage_bps_each_side": str(cfg.slippage_bps),
            "stop_loss_fraction": str(cfg.stop_loss_fraction),
            "take_profit_fraction": str(cfg.take_profit_fraction),
            "maximum_hold_snapshots": cfg.maximum_hold_snapshots,
            "maximum_positions": 1,
            "maximum_entries": 1,
            "fills": "next_observation_only",
        },
        "disclaimer": "Illustrative accounting test, NOT actual trades, broker fills or verified historical performance.",
    }
