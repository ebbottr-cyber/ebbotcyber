"""Opt-in, walletless Jupiter Swap V2 quote-only preview.

GET /swap/v2/order with inputMint, outputMint and amount only. NEVER send
taker, payer, referral account, transaction instructions or execution calls.
Do not interpret route quotes as verified fill, token safety or paper PnL.

Output raw amounts remain raw token base units. No token decimal inference.
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
import threading
import time
from datetime import datetime, timezone
from typing import Any, Literal
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from src.services.meme_coin_solana_risk import validate_mint

logger = logging.getLogger(__name__)
JUPITER_ORDER_ENDPOINT = "https://api.jup.ag/swap/v2/order"
USDC_MINT = "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v"
WSOL_MINT = "So11111111111111111111111111111111111111112"
_STRATEGIES = ("new_launch", "momentum")
_SIDES = ("buy", "sell")
_MIN_INTERVAL_SECONDS = 2.5  # Below documented 0.5 req/s keyless limit
_MAX_PAYLOAD = 150_000
_LOCK = threading.RLock()
_LAST_REQUEST_MONOTONIC: float | None = None


def enabled() -> bool:
    return os.getenv("MEME_COIN_JUPITER_QUOTES_ENABLED", "false").strip().lower() in {
        "true", "1", "yes", "on",
    }


def _raw_amount(value: Any) -> str:
    if type(value) is not int or not 1 <= value <= 10**15:
        raise ValueError("invalid_raw_amount")
    return str(value)


def _provider_amount(value: Any, name: str, *, allow_zero: bool = False) -> str:
    if not isinstance(value, str) or not value or len(value) > 32 or not value.isascii() or not value.isdecimal():
        raise ValueError("invalid_provider_" + name)
    number = int(value)
    if number < 0 or (not allow_zero and number == 0) or number > 10**20:
        raise ValueError("invalid_provider_" + name)
    return str(number)


def _base(
    strategy: Literal["new_launch", "momentum"],
    mint: str,
    side: Literal["buy", "sell"],
    amount_raw: int,
) -> dict[str, Any]:
    buy = side == "buy"
    return {
        "strategy": strategy, "mint": mint, "side": side,
        "source": "jupiter_swap_v2_order_quote_only",
        "input_mint": USDC_MINT if buy else mint,
        "output_mint": mint if buy else USDC_MINT,
        "amount_in_raw": _raw_amount(amount_raw),
        "status": "disabled",
        "quote": None, "error": None,
        "live_quote_preview": False,
        "wallet_connected": False,
        "transaction_requested": False,
        "transaction_submitted": False,
        "tradable": False,
    }


def fetch_order_quote(input_mint: str, output_mint: str, amount_raw: str) -> dict[str, Any]:
    """Call ONLY Jupiter's walletless GET quote route on a fixed host."""
    validate_mint(input_mint)
    validate_mint(output_mint)
    _provider_amount(amount_raw, "amount_in")
    if input_mint == output_mint:
        raise ValueError("same_input_and_output")
    # These are the only query parameters; no taker -> no transaction.
    url = JUPITER_ORDER_ENDPOINT + "?" + urlencode({
        "inputMint": input_mint, "outputMint": output_mint,
        "amount": amount_raw,
    })
    headers = {
        "Accept": "application/json",
        "User-Agent": "EBBot-MemeCoin-ReadOnly-Quote/0.1",
    }
    key = os.getenv("JUPITER_API_KEY", "").strip()
    if key:
        if any(ch in key for ch in ("\r", "\n")):
            raise ValueError("invalid_api_key")
        headers["x-api-key"] = key
    req = Request(url, headers=headers, method="GET")
    try:
        with urlopen(req, timeout=7) as response:
            raw = response.read(_MAX_PAYLOAD + 1)
    except (HTTPError, URLError, OSError, TimeoutError) as exc:
        raise RuntimeError("quote_provider_unavailable") from exc
    if len(raw) > _MAX_PAYLOAD:
        raise RuntimeError("quote_payload_too_large")
    try:
        result = json.loads(raw)
    except (ValueError, UnicodeDecodeError) as exc:
        raise RuntimeError("invalid_quote_json") from exc
    if not isinstance(result, dict):
        raise RuntimeError("invalid_quote_response")
    return result


def normalize_quote(
    request: dict[str, Any], response: dict[str, Any], *, observed_at_ms: int,
) -> dict[str, Any]:
    """Pure strict validation; discard transaction and all opaque route data."""
    if request.get("source") != "jupiter_swap_v2_order_quote_only":
        raise ValueError("unsupported_request_source")
    if request.get("input_mint") == request.get("output_mint"):
        raise ValueError("same_input_output")
    if not isinstance(response, dict) or response.get("error") or response.get("errorCode") or response.get("errorMessage"):
        raise ValueError("provider_quote_error")
    if "transaction" in response and response["transaction"] is not None:
        raise ValueError("transaction_in_quote_only_response")
    for key, field in (("inputMint", "input_mint"), ("outputMint", "output_mint")):
        if key in response and response[key] != request[field]:
            raise ValueError("quote_mint_mismatch")
    amount_in = _provider_amount(response.get("inAmount"), "in_amount")
    amount_out = _provider_amount(response.get("outAmount"), "out_amount")
    if amount_in != request.get("amount_in_raw"):
        raise ValueError("quote_input_mismatch")
    fee_bps = response.get("feeBps")
    if type(fee_bps) is not int or not 0 <= fee_bps <= 500:
        raise ValueError("invalid_provider_fee")
    router = response.get("router")
    if not isinstance(router, str) or not 1 <= len(router) <= 32 or not router.isascii() or not router.replace("-", "").replace("_", "").isalnum():
        raise ValueError("invalid_provider_router")
    if type(observed_at_ms) is not int or observed_at_ms <= 0:
        raise ValueError("invalid_observed_at")
    digest = hashlib.sha256(json.dumps({
        "strategy": request["strategy"], "mint": request["mint"],
        "side": request["side"], "in": amount_in, "out": amount_out,
        "router": router, "fee": fee_bps, "t": observed_at_ms,
    }, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    return {
        "capture_id": digest,
        "source": "jupiter_swap_v2_order_quote_only",
        "strategy": request["strategy"], "mint": request["mint"],
        "side": request["side"],
        "input_mint": request["input_mint"],
        "output_mint": request["output_mint"],
        "amount_in_raw": amount_in,
        "amount_out_raw": amount_out,
        "fee_bps": fee_bps,
        "router": router,
        "captured_at_ms": observed_at_ms,
        "captured_at": datetime.fromtimestamp(observed_at_ms / 1000, timezone.utc).isoformat(),
        "transaction_returned": False,
        "execution_is_real": False,
        "token_safety_verified": False,
        "estimated_network_fee_available": False,
        "tradable": False,
    }


def quote_preview(
    strategy: Literal["new_launch", "momentum"],
    mint: str,
    side: Literal["buy", "sell"],
    amount_raw: int,
) -> dict[str, Any]:
    """One manual quote attempt; no automatic loop, no wallet, no real fill."""
    if strategy not in _STRATEGIES or side not in _SIDES:
        raise ValueError("invalid_strategy_or_side")
    validate_mint(mint)
    if mint in {USDC_MINT, WSOL_MINT}:
        raise ValueError("excluded_quote_asset")
    result = _base(strategy, mint, side, amount_raw)
    if not enabled():
        return result

    global _LAST_REQUEST_MONOTONIC
    with _LOCK:
        now = time.monotonic()
        if _LAST_REQUEST_MONOTONIC is not None and now - _LAST_REQUEST_MONOTONIC < _MIN_INTERVAL_SECONDS:
            return {**result, "status": "rate_limited", "error": "retry_after_cooldown"}
        _LAST_REQUEST_MONOTONIC = now
        try:
            provider = fetch_order_quote(result["input_mint"], result["output_mint"], result["amount_in_raw"])
            captured_at_ms = time.time_ns() // 1_000_000
            normalized = normalize_quote(result, provider, observed_at_ms=captured_at_ms)
            return {**result, "status": "ok", "quote": normalized, "live_quote_preview": True}
        except (RuntimeError, ValueError, TypeError, OverflowError) as exc:
            logger.warning("Jupiter walletless quote preview failed: %s", type(exc).__name__)
            return {**result, "status": "unavailable", "error": "quote_unavailable"}
