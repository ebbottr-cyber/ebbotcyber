"""V13 OFFLINE full-position exit-quote preflight and feed outage gate.

No HTTP calls, no wallet, no orders or automatic runner. All connectivity
heartbeats and Jupiter V2 quote captures are explicitly SUPPLIED TEST DATA.
The gate conditionally blocks new hypothetical BUYs before the existing V11
MTM simulator evaluates them. It NEVER treats provider timestamps, LP safety
or real sell execution as verified.

Accepted test quotes remain scenario assumptions, NOT signed provider proof.
"""
from __future__ import annotations

import argparse
import json
from copy import deepcopy
from decimal import Decimal
from pathlib import Path
from typing import Any

from src.services.meme_coin_jupiter_quotes import USDC_MINT, normalize_quote
from src.services.meme_coin_paper_mtm import _prevalidate, replay_marked_guarded
from src.services.meme_coin_paper_replay import decimal_number
from src.services.meme_coin_solana_risk import validate_mint

D = Decimal
MAX_GATE_STEPS = 50  # full deterministic replay per step, O(n^2) on purpose
MAX_FEED_HEARTBEAT_AGE_MS = 5000
MAX_EXIT_CAPTURE_AGE_MS = 3000
MAX_CAPTURED_EXIT_NOTIONAL_USD = D("1000000")
ADVERSE_EXIT_HAIRCUT_BPS = 100
MODELED_EXIT_NETWORK_FEE_USD = D("0.01")
_FEED_FIELDS = {
    "source", "jupiter_online", "dexscreener_online",
    "solana_rpc_online", "observed_at_ms",
}
_EVIDENCE_FIELDS = {"provider_status", "token_decimals", "full_sell_quotes"}


class QuoteGateError(ValueError):
    """A conservative scenario reject with one closed-set reason."""

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


def _full_raw_amount(human: Decimal, decimals: int) -> str:
    if type(decimals) is not int or not 0 <= decimals <= 9:
        # V11 paper ledger rounds token quantities to nine places. Reject
        # higher on-chain decimals in this version to avoid false precision.
        raise QuoteGateError("invalid_exit_evidence")
    value = human * D(10**decimals)
    if value != value.to_integral_exact() or not 1 <= value <= 10**15:
        raise QuoteGateError("wrong_full_position_size")
    return str(int(value))


def _validate_full_quote(
    snapshot: Any, *, strategy: str, mint: str,
    raw_amount: str, attempted_at_ms: int,
) -> str:
    if not isinstance(snapshot, dict):
        raise QuoteGateError("missing_exit_snapshot")
    req = {
        "source": "jupiter_swap_v2_order_quote_only",
        "strategy": strategy, "mint": mint, "side": "sell",
        "input_mint": mint, "output_mint": USDC_MINT,
        "amount_in_raw": raw_amount,
    }
    provider = {
        "inAmount": snapshot.get("amount_in_raw"),
        "outAmount": snapshot.get("amount_out_raw"),
        "router": snapshot.get("router"),
        "feeBps": snapshot.get("fee_bps"),
        "transaction": None,
    }
    captured = snapshot.get("captured_at_ms")
    try:
        normalized = normalize_quote(req, provider, observed_at_ms=captured)
    except (TypeError, ValueError, OverflowError) as exc:
        raise QuoteGateError("invalid_exit_evidence") from exc
    if normalized != snapshot:
        raise QuoteGateError("invalid_exit_evidence")
    if captured > attempted_at_ms or attempted_at_ms - captured > MAX_EXIT_CAPTURE_AGE_MS:
        raise QuoteGateError("stale_exit_quote")
    # Output is quote-only USDC already after provider route/pool fees;
    # apply a *separate scenario-only* 1% adverse move + network USD cost.
    amount_usd = D(snapshot["amount_out_raw"]) / D(10**6)
    if amount_usd > MAX_CAPTURED_EXIT_NOTIONAL_USD:
        raise QuoteGateError("invalid_exit_evidence")
    after_model_costs = (
        amount_usd * (D(10000 - ADVERSE_EXIT_HAIRCUT_BPS) / D(10000))
        - MODELED_EXIT_NETWORK_FEE_USD
    )
    if after_model_costs < D("1"):
        raise QuoteGateError("insufficient_exit_proceeds")
    return format(after_model_costs.quantize(D("0.01")), "f")


def assess_entry_exit_coverage(
    *,
    strategy: str,
    positions: dict[str, dict[str, str]],
    pending_buy: dict[str, Any],
    evidence: Any,
    at_ms: int,
) -> dict[str, Any]:
    """Requiring full-exit SELL quote for every open + proposed paper position."""
    if strategy not in {"new_launch", "momentum"}:
        raise ValueError("unsupported_strategy")
    if not isinstance(positions, dict) or set(positions) != {"new_launch", "momentum"}:
        raise ValueError("invalid_position_inventory")
    if type(at_ms) is not int or at_ms <= 0:
        raise ValueError("invalid_time")
    result: dict[str, Any] = {
        "status": "blocked",
        "reason": "missing_exit_snapshot",
        "strategy": strategy,
        "evaluated_at_ms": at_ms,
        "assumed_full_exit_net_usd_by_position": {},
        "provider_market_observation_time_verified": False,
        "quote_provider_signature_verified": False,
        "independent_price_sources_verified": False,
        "all_quote_amounts_match_full_positions": False,
        "automatic_paper_execution_enabled": False,
        "live_trading_enabled": False,
    }
    try:
        if not isinstance(evidence, dict) or set(evidence) != _EVIDENCE_FIELDS:
            raise QuoteGateError("missing_exit_snapshot")
        health = evidence["provider_status"]
        if not isinstance(health, dict) or set(health) != _FEED_FIELDS or health["source"] != "offline_fixture":
            raise QuoteGateError("invalid_exit_evidence")
        age = at_ms - health["observed_at_ms"] if type(health["observed_at_ms"]) is int else -1
        if age < 0 or age > MAX_FEED_HEARTBEAT_AGE_MS:
            raise QuoteGateError("feed_stale")
        for name in ("jupiter_online", "dexscreener_online", "solana_rpc_online"):
            if health[name] is not True:
                raise QuoteGateError("feed_disconnected")
        decimals_by_mint = evidence["token_decimals"]
        quote_snapshots = evidence["full_sell_quotes"]
        if not isinstance(decimals_by_mint, dict) or not isinstance(quote_snapshots, dict):
            raise QuoteGateError("invalid_exit_evidence")

        holdings: dict[tuple[str, str], Decimal] = {}
        for name, mint_quantities in positions.items():
            if not isinstance(mint_quantities, dict) or len(mint_quantities) > 3:
                raise QuoteGateError("invalid_exit_evidence")
            for mint, raw_qty in mint_quantities.items():
                try:
                    validate_mint(mint)
                    quantity = decimal_number(raw_qty, "position_quantity")
                except (TypeError, ValueError) as exc:
                    raise QuoteGateError("invalid_exit_evidence") from exc
                holdings[(name, mint)] = quantity

        mint = pending_buy.get("mint") if isinstance(pending_buy, dict) else None
        if not isinstance(mint, str):
            raise QuoteGateError("invalid_exit_evidence")
        try:
            validate_mint(mint)
            expected = decimal_number(pending_buy["expected_out"], "expected_out")
            slip = pending_buy["modeled_adverse_slippage_bps"]
            if type(slip) is not int or not 0 <= slip <= 1000:
                raise ValueError("invalid_slippage")
        except (ValueError, TypeError, KeyError) as exc:
            raise QuoteGateError("invalid_exit_evidence") from exc
        projected_quantity = expected * D(10000 - slip) / D(10000)
        holdings[(strategy, mint)] = holdings.get((strategy, mint), D(0)) + projected_quantity

        if set(decimals_by_mint) != {mint for _, mint in holdings}:
            raise QuoteGateError("invalid_exit_evidence")
        expected_keys = {name + ":" + mint for name, mint in holdings}
        if set(quote_snapshots) != expected_keys:
            raise QuoteGateError("missing_exit_snapshot")
        values: dict[str, str] = {}
        for name, held_mint in sorted(holdings):
            raw_qty = _full_raw_amount(holdings[(name, held_mint)], decimals_by_mint[held_mint])
            key = name + ":" + held_mint
            values[key] = _validate_full_quote(
                quote_snapshots[key], strategy=name, mint=held_mint,
                raw_amount=raw_qty, attempted_at_ms=at_ms,
            )
        result.update({
            "status": "scenario_coverage_only",
            "reason": None,
            "assumed_full_exit_net_usd_by_position": values,
            "all_quote_amounts_match_full_positions": True,
        })
    except QuoteGateError as exc:
        result["reason"] = exc.reason
    return result


def replay_exit_gated(
    steps: list[dict[str, Any]],
    evidence_by_event_id: dict[str, dict[str, Any]],
    *, initial_cash_usd: str = "1000.00",
) -> dict[str, Any]:
    """Deterministic PRE-FLIGHT of fixture entries; does not place paper orders."""
    _prevalidate(steps)
    if not isinstance(steps, list) or len(steps) > MAX_GATE_STEPS:
        raise ValueError("invalid_exit_gate_sequence")
    if not isinstance(evidence_by_event_id, dict):
        raise ValueError("invalid_exit_evidence_collection")
    all_buys = {step["event"]["id"] for step in steps if step["event"]["side"] == "buy"}
    if set(evidence_by_event_id) - all_buys:
        raise ValueError("orphan_or_wrong_side_exit_evidence")
    gated: list[dict[str, Any]] = []
    audits: list[dict[str, Any]] = []
    for step in steps:
        current = deepcopy(step)
        event = current["event"]
        if event["side"] == "buy":
            # Derive current holdings from past accepted *offline* steps.
            prior = replay_marked_guarded(gated, initial_cash_usd=initial_cash_usd)
            inventory = {
                strategy: {
                    mint: holding["quantity"]
                    for mint, holding in prior["ledgers"][strategy]["positions"].items()
                }
                for strategy in ("new_launch", "momentum")
            }
            review = assess_entry_exit_coverage(
                strategy=event["strategy"], positions=inventory,
                pending_buy=event, evidence=evidence_by_event_id.get(event["id"]),
                at_ms=event["attempted_at_ms"],
            )
            audits.append({
                "event_id": event["id"],
                "strategy": event["strategy"],
                "status": review["status"],
                "reason": review["reason"],
                "quote_provenance_authenticated": False,
                "real_execution_confirmed": False,
            })
            if review["status"] != "scenario_coverage_only":
                current["exit_quote_gate"] = {
                    "status": "blocked", "reason": review["reason"],
                }
        gated.append(current)

    report = replay_marked_guarded(gated, initial_cash_usd=initial_cash_usd)
    return {
        "status": "offline_quote_coverage_replayed",
        "test_steps": len(gated),
        "gated_steps": gated,
        "gate_audit": audits,
        "replay_report": report,
        "market_quote_provenance_authenticated": False,
        "online_paper_scheduler_running": False,
        "live_trading_enabled": False,
    }


def readiness() -> dict[str, Any]:
    return {
        "status": "offline_exit_feed_safeguards_available",
        "full_exit_quotes_verified_live": False,
        "paper_safety_scheduler_running": False,
        "provider_market_timestamps_verified": False,
        "connectivity_from_live_providers": False,
        "live_trading_enabled": False,
        "strategies": [
            {"strategy": s, "state": "not_running"}
            for s in ("new_launch", "momentum")
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="OFFLINE full-exit quote coverage + feed outage gate; no orders.",
    )
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--initial-cash", default="1000.00")
    args = parser.parse_args()
    if args.input.resolve() == args.output.resolve():
        parser.error("input and output paths must differ")
    if args.input.stat().st_size > 2_000_000:
        parser.error("input too large")
    data = json.loads(args.input.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or set(data) != {"steps", "exit_evidence"}:
        parser.error("expected steps and exit_evidence")
    result = replay_exit_gated(
        data["steps"], data["exit_evidence"], initial_cash_usd=args.initial_cash,
    )
    args.output.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
