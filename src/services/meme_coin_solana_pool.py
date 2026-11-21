"""Optional read-only Solana liquidity cross-check.

Compares GeckoTerminal / DexScreener pool snapshots and confirms the pool
account exists on Solana. Neither aggregator proves reserves, a liquidity
lock, LP-token control, swap sellability, or pool authenticity.

Fixed allowlisted endpoints, base58-validated paths, bounded payloads,
fail-closed responses and NO execution or wallet access.
"""
from __future__ import annotations

import json
import logging
import math
import os
import threading
import time
from datetime import datetime, timezone
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from src.services.meme_coin_solana_risk import validate_mint

logger = logging.getLogger(__name__)

_GT_ROOT = "https://api.geckoterminal.com/api/v2/networks/solana/pools/"
_DS_ROOT = "https://api.dexscreener.com/latest/dex/pairs/solana/"
_SOLANA_RPC = "https://api.mainnet-beta.solana.com"
_ALLOWED_JSON_ROOTS = (_GT_ROOT, _DS_ROOT)
_TTL = 90
_CACHE: dict[tuple[str, str], tuple[float, dict[str, Any]]] = {}
_LOCK = threading.RLock()
_LIMIT = 350_000
_MAX_DIFFERENCE_PCT = 35.0
_MIN_LIQUIDITY_USD = 10_000.0


def enabled() -> bool:
    return os.getenv("MEME_COIN_SOLANA_LIQUIDITY_REVIEW_ENABLED", "false").lower().strip() in (
        "1", "true", "yes", "on"
    )


def _base(mint: str, pool: str) -> dict[str, Any]:
    return {
        "mint": mint, "pool": pool, "network": "solana",
        "status": "disabled", "verdict": "unknown", "checked_at": None,
        "geckoterminal_usd": None, "dexscreener_usd": None,
        "difference_pct": None, "dex_id": None,
        "onchain_account_found": None, "onchain_owner_program": None,
        "onchain_slot": None, "flags": [],
        "onchain_reserves_verified": False,
        "liquidity_lock_verified": False,
        "lp_owner_verified": False,
        "pool_authenticity_verified": False,
        "sellability_verified": False, "tradable": False,
    }


def _finite_liquidity(raw: Any) -> float:
    if type(raw) not in (str, float, int):
        raise ValueError("invalid_liquidity")
    try:
        value = float(raw)
    except (ValueError, OverflowError) as exc:
        raise ValueError("invalid_liquidity") from exc
    if not math.isfinite(value) or value <= 0 or value > 1e11:
        raise ValueError("invalid_liquidity")
    return value


def _read_http_json(url: str) -> dict[str, Any]:
    if not any(url.startswith(prefix) for prefix in _ALLOWED_JSON_ROOTS):
        raise ValueError("unapproved_provider_url")
    request = Request(url, headers={
        "Accept": "application/json", "User-Agent": "EBBot-MemeCoin-Liquidity-Research/0.1",
    })
    try:
        with urlopen(request, timeout=7) as response:
            raw = response.read(_LIMIT + 1)
    except (HTTPError, URLError, OSError, TimeoutError) as exc:
        raise RuntimeError("provider_unavailable") from exc
    if len(raw) > _LIMIT:
        raise RuntimeError("provider_payload_too_large")
    try:
        result = json.loads(raw)
    except (ValueError, UnicodeDecodeError) as exc:
        raise RuntimeError("invalid_provider_json") from exc
    if not isinstance(result, dict):
        raise ValueError("invalid_provider_body")
    return result


def fetch_gecko(pool: str) -> dict[str, Any]:
    validate_mint(pool)
    return _read_http_json(_GT_ROOT + pool + "?include=base_token")


def fetch_dexscreener(pool: str) -> dict[str, Any]:
    validate_mint(pool)
    return _read_http_json(_DS_ROOT + pool)


def fetch_pool_account(pool: str) -> dict[str, Any]:
    validate_mint(pool)
    request = Request(
        _SOLANA_RPC, method="POST",
        data=json.dumps({
            "jsonrpc": "2.0", "id": 1, "method": "getAccountInfo",
            "params": [pool, {"encoding": "base64", "commitment": "confirmed"}],
        }).encode("utf-8"),
        headers={"Accept": "application/json", "Content-Type": "application/json",
                 "User-Agent": "EBBot-MemeCoin-Pool-Research/0.1"},
    )
    try:
        with urlopen(request, timeout=7) as response:
            raw = response.read(80_000 + 1)
    except (HTTPError, URLError, OSError, TimeoutError) as exc:
        raise RuntimeError("rpc_unavailable") from exc
    if len(raw) > 80_000:
        raise RuntimeError("rpc_payload_too_large")
    try:
        body = json.loads(raw)
    except (ValueError, UnicodeDecodeError) as exc:
        raise RuntimeError("invalid_rpc_json") from exc
    if (not isinstance(body, dict) or body.get("jsonrpc") != "2.0"
            or body.get("id") != 1 or not isinstance(body.get("result"), dict)):
        raise ValueError("invalid_rpc_body")
    return body["result"]


def assess_pool(
    mint: str, pool: str, gecko: dict[str, Any],
    dex: dict[str, Any], chain_account: dict[str, Any],
) -> dict[str, Any]:
    """Pure snapshot validation, including chain and token/pool identity."""
    validate_mint(mint)
    validate_mint(pool)
    state = _base(mint, pool)
    record = gecko.get("data") if isinstance(gecko, dict) else None
    if not isinstance(record, dict) or record.get("type") != "pool":
        raise ValueError("invalid_gecko_pool")
    attr = record.get("attributes")
    rel = record.get("relationships")
    included = gecko.get("included")
    if not isinstance(attr, dict) or not isinstance(rel, dict) or not isinstance(included, list):
        raise ValueError("invalid_gecko_structure")
    if attr.get("address") != pool or not isinstance(attr.get("reserve_in_usd"), (str, int, float)):
        raise ValueError("gecko_pool_mismatch")
    base = rel.get("base_token")
    base_data = base.get("data") if isinstance(base, dict) else None
    base_id = base_data.get("id") if isinstance(base_data, dict) else None
    if not isinstance(base_id, str):
        raise ValueError("missing_base_token")
    token_found = any(
        isinstance(t, dict) and t.get("type") == "token"
        and t.get("id") == base_id and isinstance(t.get("attributes"), dict)
        and t["attributes"].get("address") == mint
        for t in included
    )
    if not token_found:
        raise ValueError("gecko_mint_mismatch")

    pairs = dex.get("pairs") if isinstance(dex, dict) else None
    if not isinstance(pairs, list):
        raise ValueError("invalid_dexscreener_body")
    matches = [
        p for p in pairs if isinstance(p, dict) and p.get("chainId") == "solana"
        and p.get("pairAddress") == pool
        and isinstance(p.get("baseToken"), dict)
        and p["baseToken"].get("address") == mint
    ]
    if len(matches) != 1:
        raise ValueError("dexscreener_pool_or_token_mismatch")
    pair = matches[0]
    dex_id = pair.get("dexId")
    if not isinstance(dex_id, str) or not (1 <= len(dex_id) <= 50):
        raise ValueError("unknown_dex")
    liquidity = pair.get("liquidity")
    if not isinstance(liquidity, dict):
        raise ValueError("invalid_dex_liquidity")
    gt_liq = _finite_liquidity(attr.get("reserve_in_usd"))
    ds_liq = _finite_liquidity(liquidity.get("usd"))

    context = chain_account.get("context") if isinstance(chain_account, dict) else None
    slot = context.get("slot") if isinstance(context, dict) else None
    account = chain_account.get("value") if isinstance(chain_account, dict) else None
    if type(slot) is not int or slot <= 0:
        raise ValueError("invalid_pool_context")
    if account is not None and not isinstance(account, dict):
        raise ValueError("invalid_pool_account")
    owner = account.get("owner") if isinstance(account, dict) else None
    if owner is not None:
        validate_mint(owner)
    if isinstance(account, dict):
        if (type(account.get("executable")) is not bool
                or type(account.get("lamports")) is not int
                or type(account.get("space")) is not int):
            raise ValueError("malformed_pool_account")

    diff_pct = 100 * abs(gt_liq - ds_liq) / max(gt_liq, ds_liq)
    flags: list[str] = []
    if diff_pct > _MAX_DIFFERENCE_PCT:
        flags.append("liquidity_source_divergence")
    if min(gt_liq, ds_liq) < _MIN_LIQUIDITY_USD:
        flags.append("low_reported_liquidity")
    if not isinstance(account, dict):
        flags.append("onchain_pool_account_missing")
    elif account["executable"] or account["lamports"] <= 0 or account["space"] <= 0:
        flags.append("unexpected_pool_account_state")

    state.update({
        "status": "screened",
        "verdict": "blocked" if flags else "review_only",
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "geckoterminal_usd": round(gt_liq, 2),
        "dexscreener_usd": round(ds_liq, 2),
        "difference_pct": round(diff_pct, 3),
        "dex_id": dex_id,
        "onchain_account_found": isinstance(account, dict),
        "onchain_owner_program": owner,
        "onchain_slot": slot,
        "flags": flags,
    })
    return state


def review_pool(mint: str, pool: str) -> dict[str, Any]:
    validate_mint(mint)
    validate_mint(pool)
    state = _base(mint, pool)
    if not enabled():
        return state
    key = (mint, pool)
    with _LOCK:
        prev = _CACHE.get(key)
        if prev and time.monotonic() - prev[0] < _TTL:
            return json.loads(json.dumps(prev[1]))
        try:
            state = assess_pool(
                mint, pool,
                fetch_gecko(pool),
                fetch_dexscreener(pool),
                fetch_pool_account(pool),
            )
        except (ValueError, RuntimeError, TypeError, OverflowError) as exc:
            logger.warning("Solana pool cross-check unavailable: %s", type(exc).__name__)
            state = {**state, "status": "unavailable", "verdict": "unknown"}
        if len(_CACHE) >= 256:
            _CACHE.clear()
        _CACHE[key] = (time.monotonic(), state)
        return json.loads(json.dumps(state))
