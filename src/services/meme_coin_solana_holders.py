"""Opt-in, read-only Solana token-account concentration signals.

IMPORTANT: getTokenLargestAccounts lists TOKEN ACCOUNTS, not beneficial
owners/wallets. DEX vaults, custodians and related accounts cannot be separated
without further provenance checks. Results are never trading approvals.
"""
from __future__ import annotations

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
_RPC_URL = "https://api.mainnet-beta.solana.com"
_MAX_RPC_BYTES = 65536
_CACHE_TTL_SECONDS = 90
_MAX_SLOT_GAP = 150
_LOCK = threading.RLock()
_CACHE: dict[str, tuple[float, dict[str, Any]]] = {}


def holder_audit_enabled() -> bool:
    return os.getenv("MEME_COIN_SOLANA_HOLDER_AUDIT_ENABLED", "false").strip().lower() in {
        "true", "1", "yes", "on",
    }


def _baseline(mint: str) -> dict[str, Any]:
    return {
        "mint": mint,
        "network": "solana-mainnet",
        "status": "disabled",
        "verdict": "unknown",
        "checked_at": None,
        "supply_slot": None,
        "accounts_slot": None,
        "supply_base_units": None,
        "observed_accounts": 0,
        "top_account_pct": None,
        "top_ten_accounts_pct": None,
        "observed_top_twenty_pct": None,
        "warning_flags": [],
        "interpretation": "token_accounts_not_wallets",
        "owner_identity_verified": False,
        "pool_vaults_classified": False,
        "full_safety_verified": False,
        "tradable": False,
    }


def _raw_amount(value: Any) -> int:
    if not isinstance(value, str) or not value.isascii() or not value.isdecimal() or len(value) > 40:
        raise ValueError("invalid_raw_amount")
    return int(value)


def _fetch_rpc(method: str, mint: str) -> dict[str, Any]:
    """Allow only two explicit read methods on a fixed official RPC endpoint."""
    validate_mint(mint)
    if method not in {"getTokenSupply", "getTokenLargestAccounts"}:
        raise ValueError("unsupported_method")
    payload = {
        "jsonrpc": "2.0", "id": 1, "method": method,
        "params": [mint, {"commitment": "confirmed"}],
    }
    request = Request(
        _RPC_URL, method="POST", data=json.dumps(payload).encode("utf-8"),
        headers={"Accept": "application/json", "Content-Type": "application/json",
                 "User-Agent": "EBBot-ReadOnly-Concentration-Research/0.1"},
    )
    try:
        with urlopen(request, timeout=7) as response:
            data = response.read(_MAX_RPC_BYTES + 1)
    except (HTTPError, URLError, TimeoutError, OSError) as exc:
        raise RuntimeError("rpc_unavailable") from exc
    if len(data) > _MAX_RPC_BYTES:
        raise RuntimeError("rpc_response_too_large")
    try:
        obj = json.loads(data)
    except (ValueError, UnicodeDecodeError) as exc:
        raise RuntimeError("invalid_rpc_json") from exc
    if (not isinstance(obj, dict) or obj.get("jsonrpc") != "2.0"
            or obj.get("id") != 1 or not isinstance(obj.get("result"), dict)):
        raise RuntimeError("invalid_rpc_envelope")
    return obj["result"]


def _get_slot_and_value(result: Any) -> tuple[int, Any]:
    if not isinstance(result, dict):
        raise ValueError("invalid_rpc_result")
    ctx = result.get("context")
    if not isinstance(ctx, dict) or type(ctx.get("slot")) is not int or ctx["slot"] <= 0:
        raise ValueError("invalid_context")
    return ctx["slot"], result.get("value")


def assess_concentration(
    mint: str, supply_response: dict[str, Any], largest_response: dict[str, Any]
) -> dict[str, Any]:
    """Pure assessment of two context-scoped snapshots; conservative on error."""
    validate_mint(mint)
    result = _baseline(mint)
    supply_slot, supply_obj = _get_slot_and_value(supply_response)
    largest_slot, accounts = _get_slot_and_value(largest_response)
    if abs(supply_slot - largest_slot) > _MAX_SLOT_GAP:
        raise ValueError("inconsistent_slots")
    if not isinstance(supply_obj, dict) or not isinstance(accounts, list):
        raise ValueError("missing_supply_or_accounts")
    supply = _raw_amount(supply_obj.get("amount"))
    decimals = supply_obj.get("decimals")
    if type(decimals) is not int or not 0 <= decimals <= 18:
        raise ValueError("invalid_decimals")
    if supply <= 0 or not 1 <= len(accounts) <= 20:
        raise ValueError("empty_supply_or_accounts")

    seen: set[str] = set()
    balances: list[int] = []
    for entry in accounts:
        if not isinstance(entry, dict):
            raise ValueError("invalid_token_account")
        address = validate_mint(entry.get("address"))
        if address in seen:
            raise ValueError("duplicate_token_account")
        seen.add(address)
        amount = _raw_amount(entry.get("amount"))
        balances.append(amount)

    if balances != sorted(balances, reverse=True):
        raise ValueError("unexpected_account_order")
    if sum(balances) > supply:
        raise ValueError("account_amounts_exceed_supply")

    top_one = 100 * balances[0] / supply
    top_ten = 100 * sum(balances[:10]) / supply
    top_twenty = 100 * sum(balances) / supply
    warnings: list[str] = []
    if top_one >= 20:
        warnings.append("top_token_account_at_least_20pct")
    if top_ten >= 70:
        warnings.append("top_ten_token_accounts_at_least_70pct")
    # No assertion about number of wallets, LP locks, or independent owners.
    result.update({
        "status": "screened",
        "verdict": "concentration_signal" if warnings else "review_only",
        "supply_slot": supply_slot,
        "accounts_slot": largest_slot,
        "supply_base_units": str(supply),
        "observed_accounts": len(balances),
        "top_account_pct": round(top_one, 4),
        "top_ten_accounts_pct": round(top_ten, 4),
        "observed_top_twenty_pct": round(top_twenty, 4),
        "warning_flags": warnings,
        "checked_at": datetime.now(timezone.utc).isoformat(),
    })
    return result


def review_concentration(mint: str) -> dict[str, Any]:
    validate_mint(mint)
    baseline = _baseline(mint)
    if not holder_audit_enabled():
        return baseline
    with _LOCK:
        prior = _CACHE.get(mint)
        if prior and time.monotonic() - prior[0] < _CACHE_TTL_SECONDS:
            return json.loads(json.dumps(prior[1]))
        try:
            supply = _fetch_rpc("getTokenSupply", mint)
            accounts = _fetch_rpc("getTokenLargestAccounts", mint)
            result = assess_concentration(mint, supply, accounts)
        except (RuntimeError, ValueError, TypeError, OverflowError) as exc:
            logger.warning("Solana token-account concentration probe failed: %s", type(exc).__name__)
            result = {**baseline, "status": "unavailable", "verdict": "unknown"}
        if len(_CACHE) >= 512:
            _CACHE.clear()
        _CACHE[mint] = (time.monotonic(), result)
        return json.loads(json.dumps(result))
