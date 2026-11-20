"""Deterministic OFFLINE Solana meme-coin paper replay.

No network calls, wallet access, exchange adapter, API mutation, background
scheduler or live-trading imports. Quote snapshots must be explicitly supplied
from a fixture/replay feed; the engine cannot fetch or fabricate prices.

Assumptions: buy quotes specify token output for input USD, sell quotes specify
USD output for input token units. Expected outputs must already include DEX
route/pool fees; separate network and priority fees are deducted in USD.
Applying assumed adverse slippage produces a scenario, NOT a real fill.
"""
from __future__ import annotations

import argparse
import json
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation, ROUND_HALF_EVEN
from pathlib import Path
from typing import Any, Literal

from src.services.meme_coin_solana_risk import validate_mint

STRATEGIES = ("new_launch", "momentum")
D = Decimal
MAX_EVENTS = 10000
QUOTE_MAX_AGE_MS = 3000
MAX_SLIPPAGE_BPS = 1000
US_DOLLARS = D("0.01")
TOKEN_UNITS = D("0.000000001")


def decimal_number(value: Any, label: str, *, allow_zero: bool = False) -> Decimal:
    """Accept only ASCII canonical decimal strings, never float / NaN / exponent."""
    if not isinstance(value, str) or not (1 <= len(value) <= 36):
        raise ValueError("invalid_" + label)
    if not value.isascii() or any(c not in "0123456789." for c in value):
        raise ValueError("invalid_" + label)
    if value.count(".") > 1 or not value.strip(".") or value.startswith(".") or value.endswith("."):
        raise ValueError("invalid_" + label)
    try:
        number = D(value)
    except InvalidOperation as exc:
        raise ValueError("invalid_" + label) from exc
    if not number.is_finite() or (number < 0 if allow_zero else number <= 0):
        raise ValueError("invalid_" + label)
    if number > D("1000000000000"):
        raise ValueError("out_of_range_" + label)
    return number


def money(value: Decimal) -> str:
    return str(value.quantize(US_DOLLARS, rounding=ROUND_HALF_EVEN))


def quantity(value: Decimal) -> str:
    return str(value.quantize(TOKEN_UNITS, rounding=ROUND_HALF_EVEN))


@dataclass
class Position:
    quantity: Decimal = D("0")
    cost_basis_usd: Decimal = D("0")


@dataclass
class PaperLedger:
    strategy: Literal["new_launch", "momentum"]
    initial_cash_usd: Decimal
    cash_usd: Decimal
    realized_pnl_usd: Decimal = D("0")
    fees_paid_usd: Decimal = D("0")
    successful_buys: int = 0
    successful_sells: int = 0
    closed_profitable_sells: int = 0
    failed_transactions: int = 0
    rejected_events: int = 0
    positions: dict[str, Position] = field(default_factory=dict)
    audit: list[dict[str, Any]] = field(default_factory=list)


def new_ledgers(initial_cash_usd: str = "1000.00") -> dict[str, PaperLedger]:
    initial = decimal_number(initial_cash_usd, "initial_cash")
    if initial < 100 or initial > 100000:
        raise ValueError("initial_cash_out_of_range")
    return {
        strategy: PaperLedger(strategy, initial, initial)
        for strategy in STRATEGIES
    }


def _int_field(event: dict, name: str, *, minimum: int = 0, maximum: int = 10**15) -> int:
    value = event.get(name)
    if type(value) is not int or not minimum <= value <= maximum:
        raise ValueError("invalid_" + name)
    return value


def _validate_event(event: Any) -> dict:
    if not isinstance(event, dict):
        raise ValueError("invalid_event")
    required = {
        "id", "strategy", "mint", "side", "source",
        "quote_observed_at_ms", "attempted_at_ms", "amount_in",
        "expected_out", "network_fee_usd", "priority_fee_usd",
        "modeled_adverse_slippage_bps", "outcome",
    }
    if set(event) != required:
        raise ValueError("event_fields_mismatch")
    event_id = event["id"]
    if not isinstance(event_id, str) or not (1 <= len(event_id) <= 80) or not event_id.isascii() or not all(c.isalnum() or c in "-_" for c in event_id):
        raise ValueError("invalid_event_id")
    if event["strategy"] not in STRATEGIES or event["side"] not in {"buy", "sell"}:
        raise ValueError("invalid_strategy_or_side")
    if event["source"] != "offline_fixture":
        raise ValueError("unverified_quote_source")
    if event["outcome"] not in {"success", "rejected_by_network", "timeout", "onchain_failure"}:
        raise ValueError("invalid_network_outcome")
    validate_mint(event["mint"])
    ts_quote = _int_field(event, "quote_observed_at_ms", minimum=1)
    ts_attempt = _int_field(event, "attempted_at_ms", minimum=1)
    if ts_quote > ts_attempt:
        raise ValueError("future_quote_lookahead")
    for key in ("amount_in", "expected_out"):
        decimal_number(event[key], key)
    for key in ("network_fee_usd", "priority_fee_usd"):
        decimal_number(event[key], key, allow_zero=True)
    slip = _int_field(event, "modeled_adverse_slippage_bps", maximum=10000)
    return event


def _audit(ledger: PaperLedger, event: dict, status: str, reason: str, *, qty: str = "0", net_usd: str = "0.00") -> None:
    ledger.audit.append({
        "event_id": event["id"],
        "strategy": ledger.strategy,
        "mint": event["mint"],
        "side": event["side"],
        "attempted_at_ms": event["attempted_at_ms"],
        "quote_observed_at_ms": event["quote_observed_at_ms"],
        "status": status, "reason": reason,
        "modeled_token_quantity": qty,
        "modeled_net_cash_flow_usd": net_usd,
        "execution_is_real": False,
    })


def _execute(ledger: PaperLedger, event: dict) -> None:
    amount_in = decimal_number(event["amount_in"], "amount_in")
    quoted_out = decimal_number(event["expected_out"], "expected_out")
    network = decimal_number(event["network_fee_usd"], "network_fee_usd", allow_zero=True)
    priority = decimal_number(event["priority_fee_usd"], "priority_fee_usd", allow_zero=True)
    fee = network + priority
    slip = event["modeled_adverse_slippage_bps"]
    mint = event["mint"]
    side = event["side"]
    position = ledger.positions.get(mint, Position())
    age = event["attempted_at_ms"] - event["quote_observed_at_ms"]

    def reject(reason: str) -> None:
        ledger.rejected_events += 1
        _audit(ledger, event, "rejected", reason)

    if age > QUOTE_MAX_AGE_MS:
        reject("stale_quote")
        return
    if slip > MAX_SLIPPAGE_BPS:
        reject("slippage_limit")
        return
    if event["outcome"] in {"timeout", "rejected_by_network"}:
        reject("network_" + event["outcome"] + "_no_confirmed_fill")
        return
    if fee > ledger.cash_usd:
        reject("insufficient_fee_balance")
        return
    if event["outcome"] == "onchain_failure":
        ledger.cash_usd -= fee
        ledger.fees_paid_usd += fee
        ledger.failed_transactions += 1
        _audit(ledger, event, "onchain_failed", "gas_charged_no_fill", net_usd=money(-fee))
        return

    # Replay is a conservative scenario, not a proof of route liquidity.
    multiplier = (D(10000) - D(slip)) / D(10000)
    estimated_out = quoted_out * multiplier
    if side == "buy":
        if amount_in > D("100") or amount_in + fee > ledger.cash_usd:
            reject("buy_limit_or_cash")
            return
        if len([x for x in ledger.positions.values() if x.quantity > 0]) >= 3 and position.quantity == 0:
            reject("too_many_open_positions")
            return
        # Conservative cost-basis budget across open buys, independent per strategy.
        if position.cost_basis_usd + amount_in + fee > D("200"):
            reject("max_token_exposure")
            return
        if estimated_out < TOKEN_UNITS:
            reject("token_quantity_too_small")
            return
        ledger.cash_usd -= amount_in + fee
        position.quantity += estimated_out
        position.cost_basis_usd += amount_in + fee
        ledger.positions[mint] = position
        ledger.successful_buys += 1
        ledger.fees_paid_usd += fee
        _audit(
            ledger, event, "filled_scenario", "modeled_quote_including_dex_fees",
            qty=quantity(estimated_out), net_usd=money(-(amount_in + fee)),
        )
    else:
        if amount_in > position.quantity or position.quantity == 0:
            reject("insufficient_token_quantity")
            return
        # On sells, expected_out USD already accounts for pool/route fees.
        cash_received = estimated_out - fee
        if cash_received < 0:
            reject("negative_proceeds_after_network_fees")
            return
        closed_fraction = amount_in / position.quantity
        cost_removed = position.cost_basis_usd * closed_fraction
        pnl = cash_received - cost_removed
        ledger.cash_usd += cash_received
        ledger.realized_pnl_usd += pnl
        ledger.fees_paid_usd += fee
        ledger.successful_sells += 1
        if pnl > 0:
            ledger.closed_profitable_sells += 1
        position.quantity -= amount_in
        position.cost_basis_usd -= cost_removed
        if position.quantity == 0:
            del ledger.positions[mint]
        else:
            ledger.positions[mint] = position
        _audit(
            ledger, event, "filled_scenario", "modeled_quote_including_dex_fees",
            qty=quantity(amount_in), net_usd=money(cash_received),
        )


def replay(events: list[dict[str, Any]], *, initial_cash_usd: str = "1000.00") -> dict[str, Any]:
    """Strict reproducible replay; no result is implied to be live performance."""
    if not isinstance(events, list) or len(events) > MAX_EVENTS:
        raise ValueError("invalid_event_sequence")
    ledgers = new_ledgers(initial_cash_usd)
    seen_ids: set[str] = set()
    prior_time = 0
    for event in events:
        _validate_event(event)
        if event["id"] in seen_ids:
            raise ValueError("duplicate_event_id")
        seen_ids.add(event["id"])
        if event["attempted_at_ms"] < prior_time:
            raise ValueError("non_chronological_events")
        prior_time = event["attempted_at_ms"]
        _execute(ledgers[event["strategy"]], event)

    output: dict[str, Any] = {
        "mode": "offline_fixture_replay",
        "data_is_live": False,
        "live_trading_enabled": False,
        "simulation_is_realized_return": False,
        "quote_adapter_connected": False,
        "events_processed": len(events),
        "ledgers": {},
    }
    for strategy, ledger in ledgers.items():
        output["ledgers"][strategy] = {
            "initial_cash_usd": money(ledger.initial_cash_usd),
            "cash_usd": money(ledger.cash_usd),
            "realized_pnl_usd": money(ledger.realized_pnl_usd),
            "network_and_priority_fees_usd": money(ledger.fees_paid_usd),
            "successful_buys": ledger.successful_buys,
            "successful_sells": ledger.successful_sells,
            "profitable_sells": ledger.closed_profitable_sells,
            "failed_transactions": ledger.failed_transactions,
            "rejected_events": ledger.rejected_events,
            "positions": {
                mint: {
                    "quantity": quantity(position.quantity),
                    "cost_basis_usd": money(position.cost_basis_usd),
                }
                for mint, position in sorted(ledger.positions.items())
            },
            "audit": ledger.audit,
        }
    return output


def status() -> dict[str, Any]:
    """Readiness only; no stateful paper engine is running in the API."""
    return {
        "status": "offline_replay_available",
        "data_source": "operator_supplied_offline_fixture",
        "live_quotes_connected": False,
        "paper_automated": False,
        "live_trading_enabled": False,
        "strategy_ledgers": [
            {"strategy": strategy, "state": "not_running", "realized_pnl_usd": None}
            for strategy in STRATEGIES
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run an offline, deterministic meme-coin quote replay (NO orders)."
    )
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--initial-cash", default="1000.00")
    args = parser.parse_args()
    # Input/output handled only as offline files, never inside the web API.
    if args.input.resolve() == args.output.resolve():
        parser.error("input and output paths must be different")
    if args.input.stat().st_size > 3_000_000:
        parser.error("replay file exceeds 3 MB")
    payload = json.loads(args.input.read_text(encoding="utf-8"))
    if not isinstance(payload, dict) or set(payload) != {"events"}:
        parser.error("expected one JSON object with an events array")
    result = replay(payload["events"], initial_cash_usd=args.initial_cash)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
