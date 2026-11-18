"""OFFLINE mark-to-market Solana paper replay with no orders or network.

Marks are explicitly *synthetic/assumed* conservative sell-side USD prices,
NOT verified oracle prices or executable DEX quotes. Replay calculates marked
equity including open positions and latches new BUYs on drawdown. A hard
emergency stop blocks both sides. Recovery is handled in a separate local
SQLite checkpoint module. No scheduler, wallet, or HTTP write routes.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

from src.services.meme_coin_paper_replay import (
    STRATEGIES, MAX_EVENTS, PaperLedger, _audit, _execute, _validate_event,
    decimal_number, money, new_ledgers, quantity,
)
from src.services.meme_coin_paper_guard import (
    _validate_facts, MIN_LIQUIDITY_USD, MAX_NOTIONAL_LIQUIDITY_SHARE,
    DAILY_STRATEGY_LOSS_USD, GLOBAL_LOSS_USD,
    CONSECUTIVE_FAILURE_LIMIT, MIN_DATA_FRESHNESS_MS,
)
from src.services.meme_coin_solana_risk import validate_mint

D = Decimal
MAX_MARK_AGE_MS = 30000
_ALLOWED_STEP_FIELDS = {"event", "risk_fact", "marks"}
_MARK_FIELDS = {"source", "bid_price_usd", "observed_at_ms"}


def _reject(ledger: PaperLedger, event: dict[str, Any], reason: str) -> None:
    ledger.rejected_events += 1
    _audit(ledger, event, "risk_blocked", reason)


def _prevalidate(steps: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Validate the entire input before any simulated balance can change."""
    if not isinstance(steps, list) or len(steps) > MAX_EVENTS:
        raise ValueError("invalid_steps")
    all_events: list[dict[str, Any]] = []
    all_facts: dict[str, dict[str, Any]] = {}
    ids: set[str] = set()
    previous = 0
    for step in steps:
        if not isinstance(step, dict) or (set(step) not in (
            _ALLOWED_STEP_FIELDS, _ALLOWED_STEP_FIELDS | {"emergency_stop"},
        )):
            raise ValueError("invalid_step_contract")
        if "emergency_stop" in step and type(step["emergency_stop"]) is not bool:
            raise ValueError("invalid_step_emergency_stop")
        event = step["event"]
        _validate_event(event)
        identifier = event["id"]
        if identifier in ids:
            raise ValueError("duplicate_event_id")
        ids.add(identifier)
        ts = event["attempted_at_ms"]
        if ts < previous or ts > 10**13:
            raise ValueError("out_of_order_or_unsupported_timestamp")
        previous = ts
        all_events.append(event)
        all_facts[identifier] = step["risk_fact"]
        marks = step["marks"]
        if not isinstance(marks, dict) or len(marks) > 20:
            raise ValueError("invalid_marks")
        for address, mark in marks.items():
            validate_mint(address)
            if not isinstance(mark, dict) or set(mark) != _MARK_FIELDS:
                raise ValueError("invalid_mark_contract")
            if mark["source"] != "offline_assumption":
                raise ValueError("unverified_mark_source")
            decimal_number(mark["bid_price_usd"], "mark_price", allow_zero=True)
            if type(mark["observed_at_ms"]) is not int or not 1 <= mark["observed_at_ms"] <= 10**13:
                raise ValueError("invalid_mark_timestamp")
    _validate_facts(all_events, all_facts)
    return steps


def _mark_equities(
    ledgers: dict[str, PaperLedger], marks: dict[str, dict[str, Any]],
    attempted_ms: int,
) -> tuple[dict[str, Decimal | None], list[str]]:
    """A complete observation is required before inferring portfolio equity."""
    values: dict[str, Decimal | None] = {}
    problems: list[str] = []
    for strategy, ledger in ledgers.items():
        equity = ledger.cash_usd
        for mint, position in ledger.positions.items():
            mark = marks.get(mint)
            if mark is None:
                problems.append("missing_mark:" + mint)
                equity = None
                continue
            mark_age = attempted_ms - mark["observed_at_ms"]
            if mark_age < 0:
                problems.append("future_mark:" + mint)
                equity = None
                continue
            if mark_age > MAX_MARK_AGE_MS:
                problems.append("stale_mark:" + mint)
                equity = None
                continue
            if equity is not None:
                equity += position.quantity * decimal_number(
                    mark["bid_price_usd"], "mark_price", allow_zero=True,
                )
        values[strategy] = equity
    return values, sorted(set(problems))


def _global_equity(values: dict[str, Decimal | None]) -> Decimal | None:
    if any(value is None for value in values.values()):
        return None
    return sum((value for value in values.values() if value is not None), D(0))


def replay_marked_guarded(
    steps: list[dict[str, Any]], *,
    initial_cash_usd: str = "1000.00",
    emergency_stop: bool = False,
) -> dict[str, Any]:
    if type(emergency_stop) is not bool:
        raise ValueError("invalid_emergency_stop")
    _prevalidate(steps)
    ledgers = new_ledgers(initial_cash_usd)
    starting_capital = sum((x.initial_cash_usd for x in ledgers.values()), D(0))
    global_peak = starting_capital
    global_halt = False
    stop_latched = False
    current_day: dict[str, str] = {}
    daily_start: dict[str, Decimal | None] = {}
    daily_halt = {strategy: False for strategy in STRATEGIES}
    network_halt = {strategy: False for strategy in STRATEGIES}
    consecutive_failures = {strategy: 0 for strategy in STRATEGIES}
    latest_equities: dict[str, Decimal | None] = {
        strategy: ledger.cash_usd for strategy, ledger in ledgers.items()
    }
    latest_mark_problems: list[str] = []

    for step in steps:
        event = step["event"]
        stop_latched = stop_latched or step.get("emergency_stop", False)
        strategy = event["strategy"]
        ledger = ledgers[strategy]
        now = event["attempted_at_ms"]
        marks = step["marks"]
        try:
            day = datetime.fromtimestamp(now / 1000, tz=timezone.utc).date().isoformat()
        except (OverflowError, OSError, ValueError) as exc:
            raise ValueError("unsupported_timestamp") from exc

        before, problems = _mark_equities(ledgers, marks, now)
        portfolio_before = _global_equity(before)
        if portfolio_before is not None:
            global_peak = max(global_peak, portfolio_before)
            if global_peak - portfolio_before >= GLOBAL_LOSS_USD:
                global_halt = True

        if current_day.get(strategy) != day:
            current_day[strategy] = day
            daily_halt[strategy] = False
            # First accurate observation defines the day's baseline;
            # an overnight gap remains subject to sticky global drawdown.
            daily_start[strategy] = before[strategy]
        elif daily_start.get(strategy) is None and before[strategy] is not None:
            daily_start[strategy] = before[strategy]

        start = daily_start.get(strategy)
        if start is not None and before[strategy] is not None:
            if start - before[strategy] >= DAILY_STRATEGY_LOSS_USD:
                daily_halt[strategy] = True

        if emergency_stop or stop_latched:
            _reject(ledger, event, "emergency_stop")
            latest_equities, latest_mark_problems = before, problems
            continue

        fact = step["risk_fact"]
        liquidity = decimal_number(fact["liquidity_usd"], "liquidity_usd")
        observed = fact["observed_at_ms"]
        risk_age = now - observed
        if risk_age < 0:
            _reject(ledger, event, "future_risk_observation")
        elif risk_age > MIN_DATA_FRESHNESS_MS:
            _reject(ledger, event, "stale_liquidity_observation")
        elif liquidity < MIN_LIQUIDITY_USD:
            _reject(ledger, event, "insufficient_reported_liquidity")
        elif event["side"] == "buy" and portfolio_before is None:
            _reject(ledger, event, "unverified_portfolio_marks")
        elif event["side"] == "buy" and (
            event["mint"] not in marks
            or marks[event["mint"]]["observed_at_ms"] > now
            or now - marks[event["mint"]]["observed_at_ms"] > MAX_MARK_AGE_MS
        ):
            _reject(ledger, event, "missing_stale_or_future_buy_mark")
        elif event["side"] == "buy" and global_halt:
            _reject(ledger, event, "global_mark_drawdown_limit")
        elif event["side"] == "buy" and daily_halt[strategy]:
            _reject(ledger, event, "daily_strategy_mark_drawdown_limit")
        elif event["side"] == "buy" and network_halt[strategy]:
            _reject(ledger, event, "consecutive_network_failures")
        elif event["side"] == "buy" and (
            decimal_number(event["amount_in"], "amount_in")
            > liquidity * MAX_NOTIONAL_LIQUIDITY_SHARE
        ):
            _reject(ledger, event, "order_too_large_vs_reported_liquidity")
        else:
            _execute(ledger, event)
            row = ledger.audit[-1]
            if (
                row["status"] == "onchain_failed"
                or row["status"] == "rejected" and row["reason"].startswith("network_")
            ):
                consecutive_failures[strategy] += 1
                if consecutive_failures[strategy] >= CONSECUTIVE_FAILURE_LIMIT:
                    network_halt[strategy] = True
            elif row["status"] == "filled_scenario":
                consecutive_failures[strategy] = 0

        after, after_problems = _mark_equities(ledgers, marks, now)
        latest_equities, latest_mark_problems = after, after_problems
        portfolio_after = _global_equity(after)
        if portfolio_after is not None:
            global_peak = max(global_peak, portfolio_after)
            if global_peak - portfolio_after >= GLOBAL_LOSS_USD:
                global_halt = True
        start = daily_start.get(strategy)
        if start is not None and after[strategy] is not None:
            if start - after[strategy] >= DAILY_STRATEGY_LOSS_USD:
                daily_halt[strategy] = True

    last_global = _global_equity(latest_equities)
    result: dict[str, Any] = {
        "mode": "offline_mtm_guarded_replay",
        "events_processed": len(steps),
        "data_is_live": False,
        "all_marks_are_unverified_offline_assumptions": True,
        "mark_is_executable_quote": False,
        "automatic_paper_trading_enabled": False,
        "live_trading_enabled": False,
        "emergency_stop_enabled": emergency_stop or stop_latched,
        "emergency_stop_persisted_in_steps": stop_latched,
        "global_mark_drawdown_circuit_open": global_halt,
        "global_peak_equity_usd": money(global_peak),
        "global_latest_equity_usd": money(last_global) if last_global is not None else None,
        "last_mark_problems": latest_mark_problems,
        "limits": {
            "max_mark_age_ms": MAX_MARK_AGE_MS,
            "daily_strategy_mark_drawdown_usd": money(DAILY_STRATEGY_LOSS_USD),
            "global_mark_drawdown_usd": money(GLOBAL_LOSS_USD),
            "minimum_assumed_liquidity_usd": money(MIN_LIQUIDITY_USD),
        },
        "ledgers": {},
    }
    for strategy, ledger in ledgers.items():
        latest = latest_equities[strategy]
        result["ledgers"][strategy] = {
            "initial_cash_usd": money(ledger.initial_cash_usd),
            "cash_usd": money(ledger.cash_usd),
            "marked_equity_usd": money(latest) if latest is not None else None,
            "realized_pnl_usd": money(ledger.realized_pnl_usd),
            "unrealized_pnl_usd": (
                money(latest - ledger.cash_usd - sum((p.cost_basis_usd for p in ledger.positions.values()), D(0)))
                if latest is not None else None
            ),
            "daily_mark_drawdown_circuit_open": daily_halt[strategy],
            "consecutive_failure_circuit_open": network_halt[strategy],
            "successful_buys": ledger.successful_buys,
            "successful_sells": ledger.successful_sells,
            "failed_transactions": ledger.failed_transactions,
            "rejected_events": ledger.rejected_events,
            "positions": {
                mint: {
                    "quantity": quantity(pos.quantity),
                    "cost_basis_usd": money(pos.cost_basis_usd),
                }
                for mint, pos in sorted(ledger.positions.items())
            },
            "audit": ledger.audit,
        }
    return result


def readiness() -> dict[str, Any]:
    """Only static readiness is exposed by the authenticated read-only API."""
    return {
        "status": "offline_mtm_recovery_available",
        "mark_source": "unverified_offline_assumptions",
        "database_online": False,
        "paper_scheduler_running": False,
        "live_trading_enabled": False,
        "strategies": [
            {"strategy": strategy, "status": "not_running"}
            for strategy in STRATEGIES
        ],
    }
