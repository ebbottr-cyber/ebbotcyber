"""Bridge a manually recorded Jupiter V2 quote-only snapshot into OFFLINE replay.

The source is an operator-controlled JSON file. A capture hash detects
accidental changes; it is NOT a provider signature or proof of provenance.
No HTTP, wallet, mutation API or automatic execution is added.

The user must supply token decimals and modeled failure/fee conditions.
The quote API reports raw token amounts and does not prove feasible fills.
"""
from __future__ import annotations

import argparse
import json
from decimal import Decimal
from pathlib import Path
from typing import Any

from src.services.meme_coin_jupiter_quotes import (
    USDC_MINT, normalize_quote,
)
from src.services.meme_coin_paper_replay import decimal_number, replay

USDC_DECIMALS = 6
MAX_CAPTURE_RECORDS = 10000
_ALLOWED_RECORD = {
    "quote", "token_decimals", "attempted_at_ms",
    "network_fee_usd", "priority_fee_usd",
    "modeled_adverse_slippage_bps", "outcome",
}


def _canonical_decimal(raw: str, decimals: int) -> str:
    value = Decimal(raw) / (Decimal(10) ** decimals)
    rendered = format(value, "f")
    return rendered.rstrip("0").rstrip(".") if "." in rendered else rendered


def capture_to_event(record: dict[str, Any]) -> dict[str, Any]:
    """Sanity check capture hash, pairing, timestamp and supplied token decimals."""
    if not isinstance(record, dict) or set(record) != _ALLOWED_RECORD:
        raise ValueError("invalid_capture_record")
    quote = record["quote"]
    if not isinstance(quote, dict):
        raise ValueError("missing_quote")
    expected_capture_fields = {
        "capture_id", "source", "strategy", "mint", "side",
        "input_mint", "output_mint", "amount_in_raw", "amount_out_raw",
        "fee_bps", "router", "captured_at_ms", "captured_at",
        "transaction_returned", "execution_is_real", "token_safety_verified",
        "estimated_network_fee_available", "tradable",
    }
    if set(quote) != expected_capture_fields:
        raise ValueError("invalid_quote_capture_fields")
    if quote["strategy"] not in ("new_launch", "momentum") or quote["side"] not in ("buy", "sell"):
        raise ValueError("invalid_strategy_or_side")
    if (quote["transaction_returned"] is not False
            or quote["execution_is_real"] is not False
            or quote["token_safety_verified"] is not False
            or quote["tradable"] is not False
            or quote["estimated_network_fee_available"] is not False):
        raise ValueError("unsafe_capture_flags")
    mint = quote["mint"]
    side = quote["side"]
    input_mint = USDC_MINT if side == "buy" else mint
    output_mint = mint if side == "buy" else USDC_MINT
    if quote["input_mint"] != input_mint or quote["output_mint"] != output_mint:
        raise ValueError("mint_or_side_mismatch")

    request = {
        "source": "jupiter_swap_v2_order_quote_only",
        "strategy": quote["strategy"], "mint": mint,
        "side": side, "input_mint": input_mint,
        "output_mint": output_mint,
        "amount_in_raw": quote["amount_in_raw"],
    }
    provider = {
        "inAmount": quote["amount_in_raw"],
        "outAmount": quote["amount_out_raw"],
        "router": quote["router"], "feeBps": quote["fee_bps"],
        "transaction": None,
    }
    # Recompute canonical identity from fields; not cryptographic source trust.
    normalized = normalize_quote(request, provider, observed_at_ms=quote["captured_at_ms"])
    if normalized != quote:
        raise ValueError("capture_hash_or_payload_mismatch")

    decimals = record["token_decimals"]
    if type(decimals) is not int or not 0 <= decimals <= 9:
        raise ValueError("invalid_token_decimals")
    attempted = record["attempted_at_ms"]
    if type(attempted) is not int or not quote["captured_at_ms"] <= attempted <= quote["captured_at_ms"] + 3000:
        raise ValueError("capture_out_of_time_window")
    slippage = record["modeled_adverse_slippage_bps"]
    if type(slippage) is not int or not 0 <= slippage <= 1000:
        raise ValueError("invalid_slippage_assumption")
    if record["outcome"] not in ("success", "onchain_failure", "timeout", "rejected_by_network"):
        raise ValueError("invalid_outcome")
    network_fee = decimal_number(record["network_fee_usd"], "network_fee", allow_zero=True)
    priority_fee = decimal_number(record["priority_fee_usd"], "priority_fee", allow_zero=True)
    if network_fee > 5 or priority_fee > 5:
        raise ValueError("excess_fee_assumption")

    # V2 amounts already reflect expected route/platform fees. Never double
    # subtract fee_bps; only apply separately assumed network/priority fees.
    if side == "buy":
        amount_in = _canonical_decimal(quote["amount_in_raw"], USDC_DECIMALS)
        expected_out = _canonical_decimal(quote["amount_out_raw"], decimals)
    else:
        amount_in = _canonical_decimal(quote["amount_in_raw"], decimals)
        expected_out = _canonical_decimal(quote["amount_out_raw"], USDC_DECIMALS)
    if Decimal(amount_in) <= 0 or Decimal(expected_out) <= 0:
        raise ValueError("zero_unit_amount")
    return {
        "id": "q-" + quote["capture_id"][:32],
        "strategy": quote["strategy"],
        "mint": mint, "side": side,
        "source": "offline_fixture",  # replay() only executes deterministic fixtures.
        "quote_observed_at_ms": quote["captured_at_ms"],
        "attempted_at_ms": attempted,
        "amount_in": amount_in, "expected_out": expected_out,
        "network_fee_usd": str(network_fee),
        "priority_fee_usd": str(priority_fee),
        "modeled_adverse_slippage_bps": slippage,
        "outcome": record["outcome"],
    }


def replay_captured_quotes(
    records: list[dict[str, Any]], *, initial_cash_usd: str = "1000.00",
) -> dict[str, Any]:
    if not isinstance(records, list) or len(records) > MAX_CAPTURE_RECORDS:
        raise ValueError("invalid_capture_sequence")
    events = [capture_to_event(item) for item in records]
    result = replay(events, initial_cash_usd=initial_cash_usd)
    result["mode"] = "offline_recorded_quote_scenarios"
    result["recorded_quote_source"] = "jupiter_swap_v2_order_quote_only"
    result["capture_provenance_cryptographically_verified"] = False
    result["token_decimals_supplied_by_operator"] = True
    result["fees_and_failure_outcomes_are_scenario_assumptions"] = True
    result["this_is_actual_performance"] = False
    result["capture_ids"] = [item["quote"]["capture_id"] for item in records]
    return result


def main() -> int:
    parser = argparse.ArgumentParser(
        description="OFFLINE scenario replay from captured Jupiter V2 quote-only JSON."
    )
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--initial-cash", default="1000.00")
    args = parser.parse_args()
    if args.input.resolve() == args.output.resolve():
        parser.error("input and output must differ")
    if args.input.stat().st_size > 4_000_000:
        parser.error("input too large")
    loaded = json.loads(args.input.read_text(encoding="utf-8"))
    if not isinstance(loaded, dict) or set(loaded) != {"captures"}:
        parser.error("expected {captures: [...]} file")
    report = replay_captured_quotes(loaded["captures"], initial_cash_usd=args.initial_cash)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
