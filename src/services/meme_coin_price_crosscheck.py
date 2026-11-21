"""Opt-in walletless dual-source Solana token price CROSS-CHECK.

This is a *manual research preview* only. A Jupiter Swap V2 sell quote is
compared to DEX Screener's priceUsd for the EXACT selected pool / base mint.
The two sources may share underlying liquidity/market data, and DEX
Screener's price observation timestamp is not available in this endpoint.
Agreement does NOT verify liquidity, sell execution or market freshness.

All methods are read-only; no key, wallet, swap, order or paper scheduler.
"""
from __future__ import annotations

import json
import logging
import os
import threading
import time
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from typing import Any

from src.services.meme_coin_jupiter_quotes import (
    USDC_MINT, normalize_quote, quote_preview,
)
from src.services.meme_coin_solana_pool import fetch_dexscreener
from src.services.meme_coin_solana_risk import (
    fetch_mint_account, parse_mint_snapshot, validate_mint,
)

logger = logging.getLogger(__name__)
D = Decimal
MAX_SPREAD_PCT = D("10")
MIN_DEX_LIQUIDITY_USD = D("10000")
MAX_SAMPLE_OF_LIQUIDITY = D("0.005")
MAX_QUOTE_AGE_MS = 3000
MAX_CROSS_SOURCE_WINDOW_MS = 7000
_CACHE_TTL_SECONDS = 2
_CACHE: dict[tuple[str, str, str, int], tuple[float, dict[str, Any]]] = {}
_LOCK = threading.RLock()


def enabled() -> bool:
    return os.getenv("MEME_COIN_DUAL_SOURCE_MARKS_ENABLED", "false").strip().lower() in {
        "1", "true", "yes", "on",
    }


def _decimal(raw: Any, name: str, *, allow_zero: bool = False) -> Decimal:
    if type(raw) not in (str, int, float):
        raise ValueError("invalid_" + name)
    if isinstance(raw, float):
        # The aggregator sometimes supplies a float JSON value; format with
        # Python's shortest round-trippable representation.
        raw = str(raw)
    if isinstance(raw, int):
        raw = str(raw)
    if not isinstance(raw, str) or not raw.isascii() or not 1 <= len(raw) <= 48:
        raise ValueError("invalid_" + name)
    try:
        value = D(raw)
    except InvalidOperation as exc:
        raise ValueError("invalid_" + name) from exc
    if not value.is_finite() or value < 0 or (value == 0 and not allow_zero) or value > D("1000000000000"):
        raise ValueError("invalid_" + name)
    return value


def _baseline(strategy: str, mint: str, pool: str, amount_raw: int) -> dict[str, Any]:
    return {
        "strategy": strategy,
        "mint": mint, "pool": pool, "network": "solana-mainnet",
        "status": "disabled", "verdict": "unknown",
        "sample_sell_raw": str(amount_raw),
        "token_decimals": None, "mint_slot": None,
        "jupiter_price_usd": None, "dexscreener_price_usd": None,
        "dex_liquidity_usd": None,
        "price_divergence_pct": None,
        "sample_quoted_usd": None,
        "jupiter_captured_at_ms": None, "dex_retrieved_at_ms": None,
        "checked_at": None,
        "quote_capture_id": None, "dex_id": None,
        "warning_flags": [],
        "source_independence_verified": False,
        "dex_market_observation_timestamp_verified": False,
        "token_safety_verified": False,
        "sell_fill_verified": False,
        "mark_to_market_execution_verified": False,
        "automated_paper_marks_enabled": False,
        "live_trading_enabled": False,
        "tradable": False,
    }


def assess_sources(
    strategy: str, mint: str, pool: str, amount_raw: int,
    jupiter: dict[str, Any], dex: dict[str, Any],
    mint_account: dict[str, Any], *,
    dex_retrieved_at_ms: int,
    assessed_at_ms: int,
) -> dict[str, Any]:
    """Pure strict comparison, not an independently verified token oracle."""
    if strategy not in ("new_launch", "momentum"):
        raise ValueError("invalid_strategy")
    validate_mint(mint)
    validate_mint(pool)
    if type(amount_raw) is not int or not 1 <= amount_raw <= 10**15:
        raise ValueError("invalid_sample_raw")
    state = _baseline(strategy, mint, pool, amount_raw)

    snapshot = parse_mint_snapshot(mint, mint_account)
    if snapshot["status"] != "screened" or type(snapshot["decimals"]) is not int:
        raise ValueError("mint_decimals_unavailable")
    decimals = snapshot["decimals"]
    if not 0 <= decimals <= 18:
        raise ValueError("unsupported_token_decimals")
    state["token_decimals"] = decimals
    state["mint_slot"] = snapshot["slot"]

    if not isinstance(jupiter, dict) or jupiter.get("status") != "ok":
        raise ValueError("jupiter_quote_unavailable")
    capture = jupiter.get("quote")
    if not isinstance(capture, dict):
        raise ValueError("missing_jupiter_capture")
    if (jupiter.get("strategy") != strategy or jupiter.get("mint") != mint
            or jupiter.get("side") != "sell"
            or capture.get("source") != "jupiter_swap_v2_order_quote_only"
            or capture.get("input_mint") != mint
            or capture.get("output_mint") != USDC_MINT
            or capture.get("amount_in_raw") != str(amount_raw)
            or capture.get("strategy") != strategy
            or capture.get("mint") != mint
            or capture.get("side") != "sell"
            or capture.get("execution_is_real") is not False
            or capture.get("transaction_returned") is not False
            or capture.get("tradable") is not False):
        raise ValueError("quote_capture_identity_mismatch")
    req = {
        "source": "jupiter_swap_v2_order_quote_only",
        "strategy": strategy, "mint": mint, "side": "sell",
        "input_mint": mint, "output_mint": USDC_MINT,
        "amount_in_raw": str(amount_raw),
    }
    raw_quote = {
        "inAmount": capture.get("amount_in_raw"),
        "outAmount": capture.get("amount_out_raw"),
        "router": capture.get("router"), "feeBps": capture.get("fee_bps"),
        "transaction": None,
    }
    captured = capture.get("captured_at_ms")
    normalized = normalize_quote(req, raw_quote, observed_at_ms=captured)
    if normalized != capture:
        raise ValueError("modified_jupiter_capture")
    if (type(dex_retrieved_at_ms) is not int or type(assessed_at_ms) is not int
            or captured > dex_retrieved_at_ms
            or dex_retrieved_at_ms > assessed_at_ms
            or assessed_at_ms - captured > MAX_CROSS_SOURCE_WINDOW_MS
            or assessed_at_ms - captured > MAX_QUOTE_AGE_MS):
        raise ValueError("stale_or_inconsistent_capture_times")

    pairs = dex.get("pairs") if isinstance(dex, dict) else None
    if not isinstance(pairs, list):
        raise ValueError("missing_dex_pairs")
    matches = [
        pair for pair in pairs
        if isinstance(pair, dict)
        and pair.get("chainId") == "solana"
        and pair.get("pairAddress") == pool
        and isinstance(pair.get("baseToken"), dict)
        and pair["baseToken"].get("address") == mint
    ]
    if len(matches) != 1:
        raise ValueError("dex_pool_or_mint_mismatch")
    pair = matches[0]
    dex_id = pair.get("dexId")
    if not isinstance(dex_id, str) or not 1 <= len(dex_id) <= 48 or not dex_id.isascii():
        raise ValueError("invalid_dex_identity")
    liq = pair.get("liquidity")
    if not isinstance(liq, dict):
        raise ValueError("dex_liquidity_missing")
    liquidity_usd = _decimal(liq.get("usd"), "dex_liquidity")
    spot = _decimal(pair.get("priceUsd"), "dex_price")
    quoted_usd = _decimal(capture.get("amount_out_raw"), "quote_usdc_raw") / D(10**6)
    amount_in_tokens = D(amount_raw) / D(10**decimals)
    if amount_in_tokens <= 0 or quoted_usd < D("1"):
        raise ValueError("sample_too_small")
    jupiter_unit_usd = quoted_usd / amount_in_tokens
    pct = abs(jupiter_unit_usd - spot) / spot * D(100)

    flags: list[str] = []
    if liquidity_usd < MIN_DEX_LIQUIDITY_USD:
        flags.append("low_reported_pool_liquidity")
    if spot * amount_in_tokens > liquidity_usd * MAX_SAMPLE_OF_LIQUIDITY:
        flags.append("quote_sample_exceeds_half_percent_of_reported_liquidity")
    if pct > MAX_SPREAD_PCT:
        flags.append("price_sources_diverge_over_10pct")
    if snapshot["blocking_reasons"]:
        flags.append("mint_authority_or_initialization_warning")
    # Even a near-identical price is not independent verification.
    state.update({
        "status": "screened",
        "verdict": "flagged" if flags else "comparison_only",
        "jupiter_price_usd": str(jupiter_unit_usd.quantize(D("0.000000000001"))),
        "dexscreener_price_usd": str(spot),
        "dex_liquidity_usd": str(liquidity_usd),
        "price_divergence_pct": str(pct.quantize(D("0.0001"))),
        "sample_quoted_usd": str(quoted_usd),
        "jupiter_captured_at_ms": captured,
        "dex_retrieved_at_ms": dex_retrieved_at_ms,
        "checked_at": datetime.fromtimestamp(assessed_at_ms / 1000, timezone.utc).isoformat(),
        "quote_capture_id": normalized["capture_id"],
        "dex_id": dex_id,
        "warning_flags": flags,
    })
    return state


def preview_crosscheck(strategy: str, mint: str, pool: str, amount_raw: int) -> dict[str, Any]:
    """Manual observation only, fail closed on all missing/mismatched sources."""
    if strategy not in ("new_launch", "momentum"):
        raise ValueError("invalid_strategy")
    validate_mint(mint)
    validate_mint(pool)
    if type(amount_raw) is not int or not 1 <= amount_raw <= 10**15:
        raise ValueError("invalid_sample_raw")
    if mint in {USDC_MINT, "So11111111111111111111111111111111111111112"}:
        raise ValueError("excluded_quote_asset")
    baseline = _baseline(strategy, mint, pool, amount_raw)
    if not enabled():
        return baseline

    # A 2-second process-local cache avoids accidental repeated GETs, but
    # does not provide multi-worker rate limiting. V9 enforces Jupiter's own
    # conservative 2.5-second keyless cooldown independently.
    key = (strategy, mint, pool, amount_raw)
    with _LOCK:
        now = time.monotonic()
        old = _CACHE.get(key)
        if old and now - old[0] < _CACHE_TTL_SECONDS:
            return json.loads(json.dumps(old[1]))
        quote = quote_preview(strategy, mint, "sell", amount_raw)
        if quote["status"] == "rate_limited":
            result = {**baseline, "status": "rate_limited", "verdict": "unknown"}
        elif quote["status"] == "disabled":
            result = {**baseline, "status": "prerequisite_disabled", "verdict": "unknown"}
        elif quote["status"] != "ok":
            result = {**baseline, "status": "unavailable", "verdict": "unknown"}
        else:
            try:
                dex = fetch_dexscreener(pool)
                received_ms = time.time_ns() // 1_000_000
                account = fetch_mint_account(mint)
                result = assess_sources(
                    strategy, mint, pool, amount_raw,
                    quote, dex, account,
                    dex_retrieved_at_ms=received_ms,
                    assessed_at_ms=time.time_ns() // 1_000_000,
                )
            except (RuntimeError, ValueError, TypeError, OverflowError) as exc:
                logger.warning("Meme coin dual-source check unavailable: %s", type(exc).__name__)
                result = {**baseline, "status": "unavailable", "verdict": "unknown"}
        if len(_CACHE) >= 200:
            _CACHE.clear()
        _CACHE[key] = (time.monotonic(), result)
        return json.loads(json.dumps(result))
