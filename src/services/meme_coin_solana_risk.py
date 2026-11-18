"""Solana meme coin preliminary mint checks and hypothetical AMM cost model.

This is research-only. A mint with revoked authorities is NOT certified safe:
holder distribution, liquidity ownership, token provenance, and sellability are
not checked. No wallet, order or transaction method exists here.
"""
from __future__ import annotations

import json
import logging
import math
import os
import re
import threading
import time
from datetime import datetime, timezone
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

logger = logging.getLogger(__name__)

_SOLANA_RPC = "https://api.mainnet-beta.solana.com"
_CLASSIC_TOKEN_PROGRAM = "TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA"
_BASE58 = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"
_MINT_RE = re.compile(r"^[1-9A-HJ-NP-Za-km-z]{32,44}$")
_NON_MEME_MINTS = frozenset({
    "So11111111111111111111111111111111111111112",  # wrapped SOL
    "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v",  # USDC
})
_UNVERIFIED_CHECKS = ["holder_concentration", "liquidity_ownership", "pool_provenance", "sellability"]
_CACHE_TTL_SECONDS = 90
_MAX_RPC_BYTES = 131072
_LOCK = threading.RLock()
_CACHE: dict[str, tuple[float, dict[str, Any]]] = {}


def mint_audit_enabled() -> bool:
    return os.getenv("MEME_COIN_SOLANA_MINT_AUDIT_ENABLED", "false").strip().lower() in (
        "1", "true", "yes", "on",
    )


def validate_mint(mint: str) -> str:
    if not isinstance(mint, str) or not _MINT_RE.fullmatch(mint):
        raise ValueError("invalid_mint_address")
    # Validate canonical Base58 and the decoded Solana public key length (32).
    value = 0
    for character in mint:
        value = value * 58 + _BASE58.index(character)
    length = (value.bit_length() + 7) // 8
    decoded_length = (len(mint) - len(mint.lstrip("1"))) + length
    if decoded_length != 32:
        raise ValueError("invalid_mint_address")
    return mint


def _base_result(mint: str) -> dict[str, Any]:
    return {
        "mint": mint,
        "network": "solana-mainnet",
        "status": "disabled",
        "verdict": "unknown",
        "slot": None,
        "checked_at": None,
        "token_program": None,
        "mint_authority_revoked": None,
        "freeze_authority_revoked": None,
        "decimals": None,
        "supply_base_units": None,
        "blocking_reasons": [],
        "remaining_unverified": list(_UNVERIFIED_CHECKS),
        "full_safety_verified": False,
        "tradable": False,
    }


def fetch_mint_account(mint: str) -> dict[str, Any]:
    """One fixed Solana mainnet RPC; only getAccountInfo is permitted."""
    validate_mint(mint)
    payload = {
        "jsonrpc": "2.0", "id": 1, "method": "getAccountInfo",
        "params": [mint, {"encoding": "jsonParsed", "commitment": "confirmed"}],
    }
    req = Request(
        _SOLANA_RPC,
        data=json.dumps(payload).encode("utf-8"),
        method="POST",
        headers={"Accept": "application/json", "Content-Type": "application/json",
                 "User-Agent": "EBBot-Solana-Mint-Research/0.1"},
    )
    try:
        with urlopen(req, timeout=7) as response:
            raw = response.read(_MAX_RPC_BYTES + 1)
    except (HTTPError, URLError, TimeoutError, OSError) as exc:
        raise RuntimeError("rpc_unavailable") from exc
    if len(raw) > _MAX_RPC_BYTES:
        raise RuntimeError("rpc_response_too_large")
    try:
        data = json.loads(raw)
    except (UnicodeDecodeError, ValueError) as exc:
        raise RuntimeError("invalid_rpc_response") from exc
    if (not isinstance(data, dict) or data.get("jsonrpc") != "2.0"
            or data.get("id") != 1 or not isinstance(data.get("result"), dict)):
        raise RuntimeError("invalid_rpc_response")
    result = data["result"]
    ctx = result.get("context")
    if not isinstance(ctx, dict) or type(ctx.get("slot")) is not int or ctx["slot"] <= 0:
        raise RuntimeError("invalid_rpc_context")
    return result


def parse_mint_snapshot(mint: str, rpc_result: dict[str, Any]) -> dict[str, Any]:
    """Fail-closed parsing; Token-2022 and unknown owners remain unsupported."""
    validate_mint(mint)
    state = _base_result(mint)
    slot = rpc_result.get("context", {}).get("slot") if isinstance(rpc_result.get("context"), dict) else None
    account = rpc_result.get("value")
    if type(slot) is not int or slot <= 0 or not isinstance(account, dict):
        return {**state, "status": "unavailable", "blocking_reasons": ["missing_mint_account"]}
    state["slot"] = slot
    owner = account.get("owner")
    data = account.get("data")
    state["token_program"] = owner if isinstance(owner, str) and len(owner) < 60 else None
    if owner != _CLASSIC_TOKEN_PROGRAM:
        return {**state, "status": "unsupported", "verdict": "blocked",
                "blocking_reasons": ["unsupported_token_program"]}
    if not isinstance(data, dict) or data.get("program") != "spl-token":
        return {**state, "status": "unavailable",
                "blocking_reasons": ["unparsed_token_account"]}
    parsed = data.get("parsed")
    if not isinstance(parsed, dict) or parsed.get("type") != "mint":
        return {**state, "status": "unavailable", "blocking_reasons": ["not_a_mint"]}
    info = parsed.get("info")
    if not isinstance(info, dict):
        return {**state, "status": "unavailable", "blocking_reasons": ["missing_mint_info"]}
    if any(field not in info for field in ("mintAuthority", "freezeAuthority", "supply", "decimals", "isInitialized")):
        return {**state, "status": "unavailable", "blocking_reasons": ["incomplete_mint_info"]}
    mint_authority = info["mintAuthority"]
    freeze_authority = info["freezeAuthority"]
    decimals = info["decimals"]
    supply = info["supply"]
    is_initialized = info["isInitialized"]
    if not (
        (mint_authority is None or (isinstance(mint_authority, str) and _MINT_RE.fullmatch(mint_authority)))
        and (freeze_authority is None or (isinstance(freeze_authority, str) and _MINT_RE.fullmatch(freeze_authority)))
        and type(decimals) is int and 0 <= decimals <= 18
        and isinstance(supply, str) and supply.isascii() and supply.isdecimal()
        and type(is_initialized) is bool
    ):
        return {**state, "status": "unavailable", "blocking_reasons": ["invalid_mint_info"]}
    blocking = []
    if not is_initialized:
        blocking.append("uninitialized_mint")
    if mint_authority is not None:
        blocking.append("mint_authority_active")
    if freeze_authority is not None:
        blocking.append("freeze_authority_active")
    if mint in _NON_MEME_MINTS:
        blocking.append("excluded_quote_asset")
    state.update({
        "status": "screened",
        "verdict": "blocked" if blocking else "review_only",
        "mint_authority_revoked": mint_authority is None,
        "freeze_authority_revoked": freeze_authority is None,
        "decimals": decimals,
        "supply_base_units": supply,
        "blocking_reasons": blocking,
    })
    return state


def review_mint(mint: str) -> dict[str, Any]:
    """Opt-in, read-only snapshot; cached failures never grant safety."""
    validate_mint(mint)
    state = _base_result(mint)
    if not mint_audit_enabled():
        return state
    with _LOCK:
        prior = _CACHE.get(mint)
        if prior and time.monotonic() - prior[0] < _CACHE_TTL_SECONDS:
            return json.loads(json.dumps(prior[1]))
        try:
            state = parse_mint_snapshot(mint, fetch_mint_account(mint))
            if state["status"] == "screened":
                state["checked_at"] = datetime.now(timezone.utc).isoformat()
        except (RuntimeError, ValueError, TypeError) as exc:
            logger.warning("Solana mint research unavailable: %s", type(exc).__name__)
            state = {**state, "status": "unavailable", "blocking_reasons": ["rpc_unavailable"]}
        if len(_CACHE) > 512:
            _CACHE.clear()
        _CACHE[mint] = (time.monotonic(), state)
        return json.loads(json.dumps(state))


def estimate_cpmm_impact(
    *,
    liquidity_usd: float,
    order_usd: float,
    fee_bps: int = 30,
    adverse_slippage_bps: int = 100,
) -> dict[str, Any]:
    """Hypothetical 50/50 x*y=k USD model, NOT a real DEX route quotation.

    Assumes half of reported USD pool liquidity acts as input-side reserve,
    fixed fee, no concentrated liquidity, no taxes, no competing trades.
    Slippage buffer is modelled separately from pool price impact.
    """
    if any(type(x) not in (float, int) or not math.isfinite(x) for x in (liquidity_usd, order_usd)):
        raise ValueError("invalid_amount")
    if not (10_000 <= liquidity_usd <= 1e10 and 1 <= order_usd <= 10_000):
        raise ValueError("amount_out_of_range")
    if type(fee_bps) is not int or not (0 <= fee_bps <= 200):
        raise ValueError("invalid_fee_bps")
    if type(adverse_slippage_bps) is not int or not (0 <= adverse_slippage_bps <= 3000):
        raise ValueError("invalid_slippage_bps")

    fee_usd = order_usd * fee_bps / 10_000
    net_input = order_usd - fee_usd
    assumed_quote_reserve = liquidity_usd / 2
    # Invariant on equal-USD-value reserves, converted to USD at the spot rate.
    modeled_output_usd = assumed_quote_reserve * net_input / (assumed_quote_reserve + net_input)
    impact_pct = 100 * (1 - modeled_output_usd / net_input)
    total_cost_pct = 100 * (1 - modeled_output_usd / order_usd)
    quote_floor = modeled_output_usd * (1 - adverse_slippage_bps / 10_000)
    relative_order_pct = 100 * order_usd / liquidity_usd
    flags = []
    if impact_pct > 3:
        flags.append("excess_model_impact")
    if relative_order_pct > 1:
        flags.append("large_order_vs_liquidity")
    return {
        "model": "hypothetical_cpmm_50_50",
        "liquidity_usd": round(liquidity_usd, 2),
        "order_usd": round(order_usd, 2),
        "fee_bps": fee_bps,
        "adverse_slippage_bps": adverse_slippage_bps,
        "modeled_fee_usd": round(fee_usd, 4),
        "modeled_output_value_usd": round(modeled_output_usd, 4),
        "modeled_min_output_value_usd": round(quote_floor, 4),
        "modeled_price_impact_pct": round(impact_pct, 4),
        "modeled_total_cost_pct": round(total_cost_pct, 4),
        "order_vs_liquidity_pct": round(relative_order_pct, 4),
        "flags": flags,
        "paper_review_status": "blocked" if flags else "research_only",
        "real_quote_available": False,
        "tradable": False,
    }
