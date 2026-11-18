"""OFFLINE risk-gated Solana paper replay, without automatic paper/live orders.

Only deterministic operator-supplied fixtures are processed. Reported pool
liquidity and quote times are scenario assumptions, never safety approvals.
A hard emergency stop blocks all fills; loss/failure circuit breakers block
new BUY scenarios while allowing qualified SELL exit scenarios.
"""
from __future__ import annotations

import argparse
import json
import os
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any

from src.services.meme_coin_paper_replay import (
    STRATEGIES, MAX_EVENTS, PaperLedger, _audit, _execute, _validate_event,
    decimal_number, money, new_ledgers, quantity,
)

D = Decimal
MIN_LIQUIDITY_USD = D("10000")
MIN_DATA_FRESHNESS_MS = 30000
DAILY_STRATEGY_LOSS_USD = D("50")
GLOBAL_LOSS_USD = D("100")
CONSECUTIVE_FAILURE_LIMIT = 3
MAX_NOTIONAL_LIQUIDITY_SHARE = D("0.01")
_FACT_FIELDS = {"source", "liquidity_usd", "observed_at_ms"}


def _equity_at_cost(ledger: PaperLedger) -> Decimal:
    """Cash + unliquidated COST BASIS: excludes all unrealized PnL."""
    return ledger.cash_usd + sum((pos.cost_basis_usd for pos in ledger.positions.values()), D("0"))


def _validate_facts(
    events: list[dict[str, Any]], facts: dict[str, dict[str, Any]],
) -> dict[str, tuple[Decimal, int]]:
    if not isinstance(facts, dict):
        raise ValueError("missing_risk_facts")
    result: dict[str, tuple[Decimal, int]] = {}
    seen: set[str] = set()
    for event in events:
        _validate_event(event)
        event_id = event["id"]
        if event_id in seen:
            raise ValueError("duplicate_event_id")
        seen.add(event_id)
        fact = facts.get(event_id)
        if not isinstance(fact, dict) or set(fact) != _FACT_FIELDS:
            raise ValueError("missing_or_unexpected_risk_fact")
        if fact["source"] != "offline_assumption":
            raise ValueError("unverified_liquidity_source")
        value = decimal_number(fact["liquidity_usd"], "liquidity_usd")
        timestamp = fact["observed_at_ms"]
        if type(timestamp) is not int or timestamp <= 0:
            raise ValueError("invalid_risk_observation_timestamp")
        result[event_id] = (value, timestamp)
    if set(facts) != seen:
        raise ValueError("orphan_risk_facts")
    return result


def _reject(ledger: PaperLedger, event: dict, reason: str) -> None:
    ledger.rejected_events += 1
    _audit(ledger, event, "risk_blocked", reason)


def replay_guarded(
    events: list[dict[str, Any]], *,
    facts: dict[str, dict[str, Any]],
    initial_cash_usd: str = "1000.00",
    emergency_stop: bool = False,
) -> dict[str, Any]:
    if type(emergency_stop) is not bool:
        raise ValueError("invalid_emergency_stop")
    if not isinstance(events, list) or len(events) > MAX_EVENTS:
        raise ValueError("invalid_event_list")
    parsed_facts = _validate_facts(events, facts)
    times = [event["attempted_at_ms"] for event in events]
    if times != sorted(times):
        raise ValueError("non_chronological_events")

    ledgers = new_ledgers(initial_cash_usd)
    initial_global_equity = sum((ledger.initial_cash_usd for ledger in ledgers.values()), D(0))
    prior_days: dict[str, str] = {}
    daily_baseline: dict[str, Decimal] = {}
    daily_halts: dict[str, bool] = {key: False for key in STRATEGIES}
    failure_halts: dict[str, bool] = {key: False for key in STRATEGIES}
    consecutive_failures: dict[str, int] = {key: 0 for key in STRATEGIES}
    global_halt = False

    for event in events:
        strategy = event["strategy"]
        ledger = ledgers[strategy]
        event_day = datetime.fromtimestamp(
            event["attempted_at_ms"] / 1000, tz=timezone.utc,
        ).date().isoformat()
        if prior_days.get(strategy) != event_day:
            prior_days[strategy] = event_day
            daily_baseline[strategy] = _equity_at_cost(ledger)
            daily_halts[strategy] = False

        liquidity, observed_at = parsed_facts[event["id"]]
        age = event["attempted_at_ms"] - observed_at
        if emergency_stop:
            _reject(ledger, event, "emergency_stop")
            continue
        if age < 0:
            _reject(ledger, event, "future_risk_observation")
            continue
        if age > MIN_DATA_FRESHNESS_MS:
            _reject(ledger, event, "stale_liquidity_observation")
            continue
        if liquidity < MIN_LIQUIDITY_USD:
            _reject(ledger, event, "insufficient_reported_liquidity")
            continue

        # These are deterministic BOOK (cost-basis) guardrails. With no
        # unrealized price marks, this is NOT total portfolio drawdown risk.
        if initial_global_equity - sum((_equity_at_cost(x) for x in ledgers.values()), D(0)) >= GLOBAL_LOSS_USD:
            global_halt = True
        if daily_baseline[strategy] - _equity_at_cost(ledger) >= DAILY_STRATEGY_LOSS_USD:
            daily_halts[strategy] = True

        if event["side"] == "buy":
            if global_halt:
                _reject(ledger, event, "global_book_loss_limit")
                continue
            if daily_halts[strategy]:
                _reject(ledger, event, "daily_strategy_book_loss_limit")
                continue
            if failure_halts[strategy]:
                _reject(ledger, event, "consecutive_network_failures")
                continue
            amount = decimal_number(event["amount_in"], "amount_in")
            if amount > liquidity * MAX_NOTIONAL_LIQUIDITY_SHARE:
                _reject(ledger, event, "order_too_large_vs_reported_liquidity")
                continue

        before = len(ledger.audit)
        _execute(ledger, event)
        if len(ledger.audit) <= before:
            raise RuntimeError("missing_replay_audit")
        row = ledger.audit[-1]
        if row["status"] in ("onchain_failed", "rejected") and (
            row["status"] == "onchain_failed"
            or row["reason"].startswith("network_")
        ):
            consecutive_failures[strategy] += 1
            if consecutive_failures[strategy] >= CONSECUTIVE_FAILURE_LIMIT:
                failure_halts[strategy] = True
        elif row["status"] == "filled_scenario":
            consecutive_failures[strategy] = 0

        if daily_baseline[strategy] - _equity_at_cost(ledger) >= DAILY_STRATEGY_LOSS_USD:
            daily_halts[strategy] = True
        if initial_global_equity - sum((_equity_at_cost(x) for x in ledgers.values()), D(0)) >= GLOBAL_LOSS_USD:
            global_halt = True

    result: dict[str, Any] = {
        "mode": "offline_risk_guarded_replay",
        "events_processed": len(events),
        "data_is_live": False,
        "risk_facts_are_offline_assumptions": True,
        "unrealized_pnl_evaluated": False,
        "actual_trading_enabled": False,
        "automatic_paper_trading_enabled": False,
        "emergency_stop_enabled": emergency_stop,
        "global_book_loss_circuit_open": global_halt,
        "risk_limits": {
            "daily_strategy_book_loss_usd": money(DAILY_STRATEGY_LOSS_USD),
            "global_book_loss_usd": money(GLOBAL_LOSS_USD),
            "minimum_reported_liquidity_usd": money(MIN_LIQUIDITY_USD),
            "max_risk_data_age_ms": MIN_DATA_FRESHNESS_MS,
            "max_buy_vs_liquidity_fraction": "0.01",
            "max_consecutive_failed_attempts": CONSECUTIVE_FAILURE_LIMIT,
        },
        "ledgers": {},
    }
    for strategy, ledger in ledgers.items():
        result["ledgers"][strategy] = {
            "initial_cash_usd": money(ledger.initial_cash_usd),
            "cash_usd": money(ledger.cash_usd),
            "book_equity_usd": money(_equity_at_cost(ledger)),
            "realized_pnl_usd": money(ledger.realized_pnl_usd),
            "network_and_priority_fees_usd": money(ledger.fees_paid_usd),
            "successful_buys": ledger.successful_buys,
            "successful_sells": ledger.successful_sells,
            "failed_transactions": ledger.failed_transactions,
            "rejected_events": ledger.rejected_events,
            "daily_book_loss_circuit_open": daily_halts[strategy],
            "consecutive_failure_circuit_open": failure_halts[strategy],
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
    """Static API readiness; does not open archives or execute fixtures."""
    return {
        "status": "offline_safeguards_available",
        "archive_mode": "manual_local_sqlite_only",
        "journal_online": False,
        "paper_engine_running": False,
        "live_trading_enabled": False,
        "risk_facts_verified_from_market": False,
        "strategy_ledgers": [
            {"strategy": key, "mode": "offline_only", "live_orders_enabled": False}
            for key in STRATEGIES
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="OFFLINE risk guarded paper replay only.")
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--initial-cash", default="1000.00")
    parser.add_argument("--emergency-stop", action="store_true")
    args = parser.parse_args()
    if args.input.resolve() == args.output.resolve():
        parser.error("input/output must differ")
    if args.input.stat().st_size > 4_000_000:
        parser.error("input too large")
    document = json.loads(args.input.read_text(encoding="utf-8"))
    if not isinstance(document, dict) or set(document) != {"events", "risk_facts"}:
        parser.error("input must contain events and risk_facts only")
    env_stop = os.getenv("MEME_COIN_PAPER_EMERGENCY_STOP", "false").lower().strip() in {
        "1", "true", "yes", "on",
    }
    output = replay_guarded(
        document["events"], facts=document["risk_facts"],
        initial_cash_usd=args.initial_cash,
        emergency_stop=args.emergency_stop or env_stop,
    )
    args.output.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
