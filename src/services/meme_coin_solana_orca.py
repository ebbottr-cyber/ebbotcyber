"""Research-only Orca Whirlpool vault identity and raw reserve inspection.

Supports ONLY the official Orca Whirlpool program and classic SPL Token
vaults. Whirlpool CLMM token-account balances are NOT executable swap depth;
positions, tick arrays, active liquidity and withdrawal controls need further
verification. Absolutely no trading or wallet methods.
"""
from __future__ import annotations

import base64
import binascii
import json
import logging
import os
import threading
import time
from datetime import datetime, timezone
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from src.services.meme_coin_solana_risk import validate_mint

logger = logging.getLogger(__name__)
RPC = "https://api.mainnet-beta.solana.com"
WHIRLPOOL_PROGRAM = "whirLbMiicVdio4qvUfM5KAg6Ct8VwpYzGff3uctyCc"
CLASSIC_SPL_TOKEN_PROGRAM = "TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA"
WHIRLPOOL_DISCRIMINATOR = bytes.fromhex("3f95d10ce1806309")
WHIRLPOOL_ACCOUNT_LENGTH = 653
SLOT_TOLERANCE = 150
CACHE_SECONDS = 90
_MAX_RPC_BYTES = 100_000
_ALPHABET = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"
_CACHE_LOCK = threading.RLock()
_CACHE: dict[tuple[str, str], tuple[float, dict[str, Any]]] = {}


def enabled() -> bool:
    return os.getenv("MEME_COIN_ORCA_VAULT_AUDIT_ENABLED", "false").strip().lower() in {
        "true", "yes", "on", "1"
    }


def base58_encode(raw: bytes) -> str:
    if len(raw) != 32:
        raise ValueError("invalid_key_bytes")
    n = int.from_bytes(raw, "big")
    chars = ""
    while n:
        n, remainder = divmod(n, 58)
        chars = _ALPHABET[remainder] + chars
    leading_zeros = len(raw) - len(raw.lstrip(b"\x00"))
    return "1" * leading_zeros + chars


def _base(mint: str, pool: str) -> dict[str, Any]:
    return {
        "mint": mint, "pool": pool, "network": "solana-mainnet",
        "protocol": "orca_whirlpool", "status": "disabled", "verdict": "unknown",
        "checked_at": None, "pool_slot": None, "vault_slot": None,
        "pool_program": None, "mint_a": None, "mint_b": None,
        "vault_a": None, "vault_b": None, "vault_a_raw_amount": None,
        "vault_b_raw_amount": None, "vault_a_decimals": None,
        "vault_b_decimals": None, "clmm_liquidity_raw": None,
        "vault_authority_matches_pool": False,
        "warnings": [],
        "vault_reserves_observed": False,
        "active_swap_depth_verified": False,
        "liquidity_lock_verified": False,
        "lp_withdrawal_authority_verified": False,
        "sellability_verified": False,
        "tradable": False,
    }


def _rpc(method: str, addresses: list[str], encoding: str) -> dict[str, Any]:
    if method == "getAccountInfo":
        if len(addresses) != 1 or encoding != "base64":
            raise ValueError("unsupported_rpc_shape")
        params: list[Any] = [addresses[0], {"encoding": "base64", "commitment": "confirmed"}]
    elif method == "getMultipleAccounts":
        if len(addresses) != 2 or encoding != "jsonParsed":
            raise ValueError("unsupported_rpc_shape")
        params = [addresses, {"encoding": "jsonParsed", "commitment": "confirmed"}]
    else:
        raise ValueError("unsupported_rpc_method")
    for address in addresses:
        validate_mint(address)
    request = Request(
        RPC, method="POST",
        data=json.dumps({
            "jsonrpc": "2.0", "id": 1, "method": method, "params": params,
        }).encode("utf-8"),
        headers={
            "Accept": "application/json", "Content-Type": "application/json",
            "User-Agent": "EBBot-Orca-Whirlpool-Research/0.1",
        },
    )
    try:
        with urlopen(request, timeout=7) as response:
            raw = response.read(_MAX_RPC_BYTES + 1)
    except (HTTPError, URLError, OSError, TimeoutError) as exc:
        raise RuntimeError("rpc_unavailable") from exc
    if len(raw) > _MAX_RPC_BYTES:
        raise RuntimeError("rpc_response_too_large")
    try:
        obj = json.loads(raw)
    except (UnicodeDecodeError, ValueError) as exc:
        raise RuntimeError("invalid_rpc_json") from exc
    if (
        not isinstance(obj, dict)
        or obj.get("jsonrpc") != "2.0"
        or obj.get("id") != 1
        or not isinstance(obj.get("result"), dict)
    ):
        raise RuntimeError("invalid_rpc_envelope")
    return obj["result"]


def _slot(result: dict[str, Any]) -> int:
    ctx = result.get("context")
    if not isinstance(ctx, dict) or type(ctx.get("slot")) is not int or ctx["slot"] <= 0:
        raise ValueError("invalid_rpc_slot")
    return ctx["slot"]


def _decode_pool(raw_account: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(raw_account, dict):
        raise ValueError("missing_pool_account")
    if raw_account.get("owner") != WHIRLPOOL_PROGRAM:
        raise ValueError("unsupported_program")
    if raw_account.get("executable") is not False:
        raise ValueError("unexpected_executable_pool")
    encoded = raw_account.get("data")
    if (
        not isinstance(encoded, list) or len(encoded) != 2
        or encoded[1] != "base64" or not isinstance(encoded[0], str)
    ):
        raise ValueError("invalid_pool_encoding")
    try:
        data = base64.b64decode(encoded[0], validate=True)
    except (binascii.Error, ValueError) as exc:
        raise ValueError("invalid_pool_base64") from exc
    if len(data) != WHIRLPOOL_ACCOUNT_LENGTH or data[:8] != WHIRLPOOL_DISCRIMINATOR:
        raise ValueError("invalid_whirlpool_layout")
    # Offsets from Orca's official whirlpool.rs Anchor account data layout:
    # discriminator(8), config(32), bump(1), tick spacing(2),
    # fee-tier seed(2), fee(2), protocol fee(2), liquidity(16),
    # sqrt_price(16), current tick(4), protocol fees(8 each).
    mint_a = base58_encode(data[101:133])
    vault_a = base58_encode(data[133:165])
    mint_b = base58_encode(data[181:213])
    vault_b = base58_encode(data[213:245])
    if mint_a == mint_b or vault_a == vault_b:
        raise ValueError("duplicated_pool_addresses")
    liquidity = int.from_bytes(data[49:65], "little")
    sqrt_price = int.from_bytes(data[65:81], "little")
    if sqrt_price == 0:
        raise ValueError("invalid_sqrt_price")
    return {
        "mint_a": mint_a, "mint_b": mint_b,
        "vault_a": vault_a, "vault_b": vault_b,
        "clmm_liquidity_raw": str(liquidity),
    }


def _parse_vault(account: Any, expected_mint: str, expected_owner: str) -> tuple[str, int]:
    if not isinstance(account, dict) or account.get("owner") != CLASSIC_SPL_TOKEN_PROGRAM:
        raise ValueError("unsupported_token_vault_program")
    data = account.get("data")
    parsed = data.get("parsed") if isinstance(data, dict) else None
    info = parsed.get("info") if isinstance(parsed, dict) else None
    if (
        not isinstance(data, dict) or data.get("program") != "spl-token"
        or not isinstance(parsed, dict) or parsed.get("type") != "account"
        or not isinstance(info, dict)
        or info.get("mint") != expected_mint
        or info.get("owner") != expected_owner
        or info.get("state") != "initialized"
    ):
        raise ValueError("vault_mint_authority_or_state_mismatch")
    # Delegates may transfer tokens outside a regular swap; fail closed.
    if info.get("delegate") is not None or info.get("closeAuthority") is not None:
        raise ValueError("vault_delegate_or_close_authority")
    token_amount = info.get("tokenAmount")
    if not isinstance(token_amount, dict):
        raise ValueError("missing_vault_token_amount")
    raw = token_amount.get("amount")
    decimals = token_amount.get("decimals")
    if (
        not isinstance(raw, str) or not raw.isascii()
        or not raw.isdecimal() or len(raw) > 40
        or type(decimals) is not int or not 0 <= decimals <= 18
    ):
        raise ValueError("invalid_vault_amount")
    return raw, decimals


def inspect_orca(
    mint: str, pool: str, pool_result: dict[str, Any],
    vault_result: dict[str, Any],
) -> dict[str, Any]:
    """Assess a bounded pair of RPC snapshots without approximating USD liquidity."""
    validate_mint(mint)
    validate_mint(pool)
    result = _base(mint, pool)
    pool_slot = _slot(pool_result)
    vault_slot = _slot(vault_result)
    if abs(pool_slot - vault_slot) > SLOT_TOLERANCE:
        raise ValueError("stale_vault_snapshot")
    raw_pool = pool_result.get("value")
    decoded = _decode_pool(raw_pool)
    if mint not in (decoded["mint_a"], decoded["mint_b"]):
        raise ValueError("selected_token_not_in_pool")
    vault_accounts = vault_result.get("value")
    if not isinstance(vault_accounts, list) or len(vault_accounts) != 2:
        raise ValueError("missing_vault_accounts")
    amount_a, decimals_a = _parse_vault(vault_accounts[0], decoded["mint_a"], pool)
    amount_b, decimals_b = _parse_vault(vault_accounts[1], decoded["mint_b"], pool)
    warnings: list[str] = []
    if int(amount_a) == 0 or int(amount_b) == 0:
        warnings.append("empty_pool_vault")
    if int(decoded["clmm_liquidity_raw"]) == 0:
        warnings.append("zero_current_clmm_liquidity")
    result.update({
        "status": "screened",
        "verdict": "blocked" if warnings else "review_only",
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "pool_slot": pool_slot, "vault_slot": vault_slot,
        "pool_program": WHIRLPOOL_PROGRAM,
        "mint_a": decoded["mint_a"], "mint_b": decoded["mint_b"],
        "vault_a": decoded["vault_a"], "vault_b": decoded["vault_b"],
        "vault_a_raw_amount": amount_a, "vault_b_raw_amount": amount_b,
        "vault_a_decimals": decimals_a, "vault_b_decimals": decimals_b,
        "clmm_liquidity_raw": decoded["clmm_liquidity_raw"],
        "vault_authority_matches_pool": True,
        "vault_reserves_observed": True,
        "warnings": warnings,
    })
    return result


def review_orca_vaults(mint: str, pool: str) -> dict[str, Any]:
    validate_mint(mint)
    validate_mint(pool)
    baseline = _base(mint, pool)
    if not enabled():
        return baseline
    with _CACHE_LOCK:
        key = (mint, pool)
        cached = _CACHE.get(key)
        if cached and time.monotonic() - cached[0] < CACHE_SECONDS:
            return json.loads(json.dumps(cached[1]))
        try:
            pool_result = _rpc("getAccountInfo", [pool], "base64")
            _slot(pool_result)
            if not isinstance(pool_result.get("value"), dict):
                raise ValueError("missing_pool_account")
            if pool_result["value"].get("owner") != WHIRLPOOL_PROGRAM:
                outcome = {
                    **baseline, "status": "unsupported",
                    "pool_program": pool_result["value"].get("owner")
                    if isinstance(pool_result["value"].get("owner"), str) else None,
                }
            else:
                decoded = _decode_pool(pool_result["value"])
                if mint not in (decoded["mint_a"], decoded["mint_b"]):
                    raise ValueError("selected_token_not_in_pool")
                vault_result = _rpc(
                    "getMultipleAccounts", [decoded["vault_a"], decoded["vault_b"]],
                    "jsonParsed",
                )
                outcome = inspect_orca(mint, pool, pool_result, vault_result)
        except (ValueError, RuntimeError, TypeError, OverflowError) as exc:
            logger.warning("Orca Whirlpool vault audit unavailable: %s", type(exc).__name__)
            outcome = {**baseline, "status": "unavailable"}
        if len(_CACHE) >= 256:
            _CACHE.clear()
        _CACHE[key] = (time.monotonic(), outcome)
        return json.loads(json.dumps(outcome))
