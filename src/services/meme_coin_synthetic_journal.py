"""Offline synthetic round-trip journal. NO trades, wallets, I/O or persistence.

Pure, deterministic replay; two separate strategy journals and a shared daily
risk budget. All values are caller-supplied hypothetical values, NOT market data.
Do not expose via API or combine with real portfolio/PnL systems.
"""
from __future__ import annotations

from datetime import date
from decimal import Decimal, ROUND_HALF_UP
import re
from typing import Any

from src.services.meme_coin_paper_preview import (
    ASSUMED_STOP_LOSS_FRACTION,
    MAX_DAILY_LOSS_FRACTION,
    STRATEGIES,
    _positive_decimal,
    preview_synthetic_round_trip,
)

_CENT = Decimal("0.01")
_STRATEGY_DAY_LOSS_LIMIT = Decimal("0.02")  # part of shared 3% cap
_MAX_EVENTS = 200
_ID_PATTERN = re.compile(r"^[A-Za-z0-9_-]{1,64}$")
_FIELDS = frozenset({
    "event_id", "trading_day", "strategy",
    "synthetic_entry_price_usd", "synthetic_exit_price_usd",
    "requested_notional_usd", "synthetic_pool_liquidity_usd",
    "snapshot_age_seconds",
})


def _usd(number: Decimal) -> str:
    return str(number.quantize(_CENT, rounding=ROUND_HALF_UP))


def _blocked(reason: str) -> dict[str, Any]:
    # No partial results escape if a malformed event or conflicting ID arrives.
    return {
        "mode": "synthetic_replay_only", "status": "blocked", "reason": reason,
        "strategies": {}, "audit": [], "summary": None,
        "trade_executed": False, "paper_trading_enabled": False,
        "live_trading_enabled": False,
    }


def replay_synthetic_journal(
    *,
    starting_equity_usd: Any,
    events: Any,
    manual_kill_switch: bool = False,
) -> dict[str, Any]:
    """Replay ordered, strictly shaped SYNTHETIC closed-round-trip scenarios.

    The journal exists only in the returned value. It has no durable storage.
    A duplicate event ID with identical data is ignored; a changed payload
    with the same ID fails the *entire replay* closed. Records never claim
    orders were sent or fills happened.
    """
    if not isinstance(manual_kill_switch, bool):
        return _blocked("invalid_kill_switch")
    if not isinstance(events, (list, tuple)) or len(events) > _MAX_EVENTS:
        return _blocked("invalid_event_batch")
    try:
        start_equity = _positive_decimal(starting_equity_usd)
    except ValueError:
        return _blocked("invalid_synthetic_equity")

    # Prevalidate the whole batch before any journal calculation.
    normalized: list[dict[str, Any]] = []
    signatures: dict[str, tuple[tuple[str, str], ...]] = {}
    prior_day: date | None = None
    for event in events:
        if not isinstance(event, dict) or set(event) != _FIELDS:
            return _blocked("invalid_synthetic_event_shape")
        event_id = event["event_id"]
        strategy = event["strategy"]
        day_raw = event["trading_day"]
        if not isinstance(event_id, str) or _ID_PATTERN.fullmatch(event_id) is None:
            return _blocked("invalid_synthetic_event_id")
        if not isinstance(strategy, str) or strategy not in STRATEGIES:
            return _blocked("unknown_strategy")
        if not isinstance(day_raw, str):
            return _blocked("invalid_trading_day")
        try:
            event_day = date.fromisoformat(day_raw)
        except ValueError:
            return _blocked("invalid_trading_day")
        if event_day.isoformat() != day_raw:
            return _blocked("invalid_trading_day")
        if prior_day is not None and event_day < prior_day:
            return _blocked("events_out_of_order")
        prior_day = event_day

        signature = tuple((key, repr(event[key])) for key in sorted(_FIELDS))
        if event_id in signatures and signatures[event_id] != signature:
            return _blocked("conflicting_event_id")
        duplicate = event_id in signatures
        signatures[event_id] = signature
        normalized.append({"event": event, "day": day_raw, "duplicate": duplicate})

    journals: dict[str, dict[str, Any]] = {
        name: {"records": [], "synthetic_net_pnl": Decimal("0"),
               "daily_gross_losses": {}, "synthetic_wins": 0,
               "synthetic_losses": 0}
        for name in sorted(STRATEGIES)
    }
    account_daily_gross_losses: dict[str, Decimal] = {}
    account_net_pnl = Decimal("0")
    audit: list[dict[str, Any]] = []

    for item in normalized:
        event = item["event"]
        day = item["day"]
        strategy = event["strategy"]
        event_id = event["event_id"]
        journal = journals[strategy]
        decision = {"event_id": event_id, "trading_day": day, "strategy": strategy}
        if item["duplicate"]:
            audit.append({**decision, "result": "duplicate_ignored", "reason": None})
            continue

        reason: str | None = None
        equity_now = start_equity + account_net_pnl
        global_loss = account_daily_gross_losses.get(day, Decimal("0"))
        strategy_loss = journal["daily_gross_losses"].get(day, Decimal("0"))
        if manual_kill_switch:
            reason = "manual_kill_switch"
        elif equity_now <= 0:
            reason = "synthetic_equity_exhausted"
        else:
            try:
                notional = _positive_decimal(event["requested_notional_usd"])
            except ValueError:
                reason = "invalid_synthetic_inputs"
            else:
                possible_stop = notional * ASSUMED_STOP_LOSS_FRACTION
                if global_loss + possible_stop > start_equity * MAX_DAILY_LOSS_FRACTION:
                    reason = "global_daily_risk_budget"
                elif strategy_loss + possible_stop > start_equity * _STRATEGY_DAY_LOSS_LIMIT:
                    reason = "strategy_daily_risk_budget"

        if reason is not None:
            audit.append({**decision, "result": "rejected", "reason": reason})
            continue

        preview = preview_synthetic_round_trip(
            strategy=strategy,
            synthetic_entry_price_usd=event["synthetic_entry_price_usd"],
            synthetic_exit_price_usd=event["synthetic_exit_price_usd"],
            requested_notional_usd=event["requested_notional_usd"],
            synthetic_equity_usd=str(equity_now),
            synthetic_pool_liquidity_usd=event["synthetic_pool_liquidity_usd"],
            snapshot_age_seconds=event["snapshot_age_seconds"],
            synthetic_daily_realized_loss_usd=str(global_loss),
        )
        if preview["status"] != "synthetic_preview_only":
            audit.append({**decision, "result": "rejected", "reason": preview["reason"]})
            continue

        pnl = Decimal(preview["net_pnl_usd"])
        account_net_pnl += pnl
        journal["synthetic_net_pnl"] += pnl
        if pnl < 0:
            negative_pnl = -pnl
            account_daily_gross_losses[day] = global_loss + negative_pnl
            journal["daily_gross_losses"][day] = strategy_loss + negative_pnl
            journal["synthetic_losses"] += 1
        elif pnl > 0:
            journal["synthetic_wins"] += 1

        # These are hypothetical CLOSED round trips, not fills or orders.
        journal["records"].append({
            **decision, "synthetic_net_pnl_usd": _usd(pnl),
            "assumed_fee_bps_per_side": preview["assumed_entry_fee_bps"],
            "assumed_slippage_bps_per_side": preview["assumed_slippage_bps_per_side"],
            "realized_performance": False, "trade_executed": False,
        })
        audit.append({**decision, "result": "synthetic_recorded", "reason": None})

    summaries = {
        name: {
            "synthetic_round_trips": len(state["records"]),
            "synthetic_wins": state["synthetic_wins"],
            "synthetic_losses": state["synthetic_losses"],
            "synthetic_net_pnl_usd": _usd(state["synthetic_net_pnl"]),
            "daily_gross_synthetic_losses_usd": {
                day: _usd(loss) for day, loss in sorted(state["daily_gross_losses"].items())
            },
            "records": state["records"],
        }
        for name, state in journals.items()
    }
    return {
        "mode": "synthetic_replay_only", "status": "synthetic_preview_only",
        "reason": None,
        "manual_kill_switch": manual_kill_switch,
        "strategies": summaries,
        "audit": audit,
        "summary": {
            "starting_synthetic_equity_usd": _usd(start_equity),
            "ending_synthetic_equity_usd": _usd(start_equity + account_net_pnl),
            "synthetic_net_pnl_usd": _usd(account_net_pnl),
            "synthetic_round_trips": sum(len(j["records"]) for j in journals.values()),
            "daily_gross_synthetic_losses_usd": {
                day: _usd(loss) for day, loss in sorted(account_daily_gross_losses.items())
            },
        },
        "trade_executed": False,
        "paper_trading_enabled": False,
        "live_trading_enabled": False,
        "realized_performance": False,
    }
