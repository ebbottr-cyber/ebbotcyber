"""Opt-in grouping of largest SPL token accounts by their on-chain owner field.

Only maps the top 10 token-account addresses; a token-account owner may be a
custodian, DEX program, multisig or intermediary, NOT a beneficial investor.
No complete ownership analysis or risk clearance is possible from this data.
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

from src.services.meme_coin_solana_holders import _fetch_rpc, _get_slot_and_value, _raw_amount, assess_concentration
from src.services.meme_coin_solana_risk import validate_mint

logger = logging.getLogger(__name__)
_RPC = "https://api.mainnet-beta.solana.com"
_TOKEN_PROGRAM = "TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA"
_CACHE: dict[str, tuple[float, dict[str, Any]]] = {}
_LOCK = threading.RLock()
_TTL = 90
_SLOT_GAP = 150


def enabled() -> bool:
    return os.getenv("MEME_COIN_SOLANA_OWNER_GROUPS_ENABLED", "false").strip().lower() in {
        "1", "true", "yes", "on",
    }


def _base(mint: str) -> dict[str, Any]:
    return {
        "mint": mint, "network": "solana-mainnet", "status": "disabled",
        "verdict": "unknown", "checked_at": None,
        "observed_top_token_accounts": 0, "observed_owner_groups": 0,
        "largest_observed_owner_share_pct": None, "owner_groups": [],
        "flags": [],
        "interpretation": "observed_token_account_owner_not_beneficial_owner",
        "vault_classification_verified": False,
        "beneficial_ownership_verified": False,
        "full_safety_verified": False,
        "tradable": False,
    }


def fetch_grouped_accounts(addresses: list[str]) -> dict[str, Any]:
    if not isinstance(addresses, list) or not (1 <= len(addresses) <= 10):
        raise ValueError("invalid_addresses")
    if len(set(addresses)) != len(addresses):
        raise ValueError("duplicate_addresses")
    for address in addresses:
        validate_mint(address)
    body = {
        "jsonrpc": "2.0", "id": 1, "method": "getMultipleAccounts",
        "params": [addresses, {"encoding": "jsonParsed", "commitment": "confirmed"}],
    }
    request = Request(
        _RPC, method="POST", data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json", "Accept": "application/json",
                 "User-Agent": "EBBot-Owner-Group-Research/0.1"},
    )
    try:
        with urlopen(request, timeout=7) as response:
            raw = response.read(100_000 + 1)
    except (HTTPError, URLError, OSError, TimeoutError) as exc:
        raise RuntimeError("rpc_unavailable") from exc
    if len(raw) > 100_000:
        raise RuntimeError("rpc_payload_too_large")
    try:
        result = json.loads(raw)
    except (ValueError, UnicodeDecodeError) as exc:
        raise RuntimeError("invalid_rpc_json") from exc
    if (not isinstance(result, dict) or result.get("jsonrpc") != "2.0"
            or result.get("id") != 1 or not isinstance(result.get("result"), dict)):
        raise RuntimeError("invalid_rpc_result")
    return result["result"]


def assess_owner_groups(
    mint: str,
    supply_result: dict[str, Any],
    largest_result: dict[str, Any],
    grouped_result: dict[str, Any],
) -> dict[str, Any]:
    validate_mint(mint)
    state = _base(mint)
    # Full top-20 supply sanity checks are reused before grouping just 10.
    assess_concentration(mint, supply_result, largest_result)
    supply_slot, supply_value = _get_slot_and_value(supply_result)
    largest_slot, largest = _get_slot_and_value(largest_result)
    multiple_slot, accounts = _get_slot_and_value(grouped_result)
    if max(supply_slot, largest_slot, multiple_slot) - min(supply_slot, largest_slot, multiple_slot) > _SLOT_GAP:
        raise ValueError("inconsistent_rpc_slots")
    if not isinstance(supply_value, dict) or not isinstance(largest, list) or not isinstance(accounts, list):
        raise ValueError("invalid_rpc_data")
    supply = _raw_amount(supply_value.get("amount"))
    chosen = largest[:10]
    if len(chosen) != len(accounts) or not chosen:
        raise ValueError("account_count_mismatch")

    groups: dict[str, dict[str, Any]] = {}
    for largest_entry, account in zip(chosen, accounts):
        if not isinstance(largest_entry, dict) or not isinstance(account, dict):
            raise ValueError("missing_account")
        if account.get("owner") != _TOKEN_PROGRAM:
            raise ValueError("unsupported_account_program")
        data = account.get("data")
        parsed = data.get("parsed") if isinstance(data, dict) else None
        if not isinstance(data, dict) or data.get("program") != "spl-token":
            raise ValueError("unparsed_account")
        if not isinstance(parsed, dict) or parsed.get("type") != "account":
            raise ValueError("invalid_account_type")
        info = parsed.get("info")
        if not isinstance(info, dict) or info.get("mint") != mint:
            raise ValueError("mint_mismatch")
        owner = validate_mint(info.get("owner"))
        amount_obj = info.get("tokenAmount")
        if not isinstance(amount_obj, dict):
            raise ValueError("missing_token_amount")
        amount = _raw_amount(amount_obj.get("amount"))
        if amount != _raw_amount(largest_entry.get("amount")):
            raise ValueError("inconsistent_token_balances")
        previous = groups.setdefault(owner, {"address": owner, "sampled_token_accounts": 0, "amount": 0})
        previous["sampled_token_accounts"] += 1
        previous["amount"] += amount

    rows = sorted(groups.values(), key=lambda item: item["amount"], reverse=True)
    summaries = [
        {
            "owner_address": row["address"],
            "sampled_token_accounts": row["sampled_token_accounts"],
            "share_of_total_supply_pct": round(100 * row["amount"] / supply, 4),
        }
        for row in rows
    ]
    largest_pct = summaries[0]["share_of_total_supply_pct"]
    flags = ["sampled_owner_group_at_least_20pct"] if largest_pct >= 20 else []
    state.update({
        "status": "screened",
        "verdict": "concentration_signal" if flags else "review_only",
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "observed_top_token_accounts": len(chosen),
        "observed_owner_groups": len(summaries),
        "largest_observed_owner_share_pct": largest_pct,
        "owner_groups": summaries,
        "flags": flags,
    })
    return state


def review_owner_groups(mint: str) -> dict[str, Any]:
    validate_mint(mint)
    state = _base(mint)
    if not enabled():
        return state
    with _LOCK:
        prior = _CACHE.get(mint)
        if prior and time.monotonic() - prior[0] < _TTL:
            return json.loads(json.dumps(prior[1]))
        try:
            supply = _fetch_rpc("getTokenSupply", mint)
            largest = _fetch_rpc("getTokenLargestAccounts", mint)
            accounts = largest.get("value") if isinstance(largest, dict) else None
            if not isinstance(accounts, list) or not (1 <= len(accounts) <= 20):
                raise ValueError("missing_largest_accounts")
            chosen = accounts[:10]
            addresses = [
                validate_mint(item.get("address")) if isinstance(item, dict)
                else validate_mint(None)
                for item in chosen
            ]
            grouped = fetch_grouped_accounts(addresses)
            state = assess_owner_groups(mint, supply, largest, grouped)
        except (RuntimeError, ValueError, TypeError, OverflowError) as exc:
            logger.warning("Solana owner-group research unavailable: %s", type(exc).__name__)
            state = {**state, "status": "unavailable"}
        if len(_CACHE) >= 256:
            _CACHE.clear()
        _CACHE[mint] = (time.monotonic(), state)
        return json.loads(json.dumps(state))
