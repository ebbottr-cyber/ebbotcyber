"""Read-only Solana DEX pool discovery for two independent research strategies.

GeckoTerminal's public API provides delayed/cacheable snapshots, not transaction-
level streaming, on-chain authority verification, or a trading execution venue.
Never interpret these candidates as buy decisions or verified-safe tokens.
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
from typing import Any, Literal
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

logger = logging.getLogger(__name__)
Strategy = Literal["new_launch", "momentum"]

_GECKO_HOST = "https://api.geckoterminal.com/api/v2"
_PATHS = {
    "new_launch": "/networks/solana/new_pools?include=base_token",
    "momentum": "/networks/solana/trending_pools?include=base_token&duration=5m",
}
_BASE58 = re.compile(r"^[1-9A-HJ-NP-Za-km-z]{32,44}$")
_TIMEOUT_SECONDS = 7
_CACHE_SECONDS = 60
_MAX_RESPONSE_BYTES = 2_000_000
_CACHE_LOCK = threading.RLock()
_CACHE: dict[str, tuple[float, dict[str, Any]]] = {}


def discovery_enabled() -> bool:
    return os.getenv("MEME_COIN_DISCOVERY_ENABLED", "false").strip().lower() in (
        "1", "true", "yes", "on"
    )


def _number(value: Any) -> float | None:
    try:
        if value is None or isinstance(value, bool):
            return None
        number = float(value)
    except (ValueError, TypeError, OverflowError):
        return None
    return number if math.isfinite(number) else None


def _window(data: Any, window: str, field: str | None = None) -> Any:
    if not isinstance(data, dict):
        return None
    value = data.get(window)
    if field is not None:
        return value.get(field) if isinstance(value, dict) else None
    return value


def _timestamp(raw: Any) -> datetime | None:
    if not isinstance(raw, str):
        return None
    try:
        value = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        return value.astimezone(timezone.utc) if value.tzinfo is not None else None
    except ValueError:
        return None


def fetch_json(strategy: Strategy) -> dict[str, Any]:
    """Request one fixed provider endpoint; no client-controlled URLs."""
    if strategy not in _PATHS:
        raise ValueError("unknown strategy")
    req = Request(
        _GECKO_HOST + _PATHS[strategy],
        headers={"Accept": "application/json", "User-Agent": "EBBot-MemeCoin-Research/0.2"},
    )
    try:
        with urlopen(req, timeout=_TIMEOUT_SECONDS) as response:
            data = response.read(_MAX_RESPONSE_BYTES + 1)
    except (HTTPError, URLError, TimeoutError, OSError) as exc:
        raise RuntimeError("provider_unavailable") from exc
    if len(data) > _MAX_RESPONSE_BYTES:
        raise RuntimeError("provider_payload_too_large")
    try:
        result = json.loads(data)
    except (ValueError, UnicodeDecodeError) as exc:
        raise RuntimeError("invalid_provider_response") from exc
    if not isinstance(result, dict) or not isinstance(result.get("data"), list):
        raise RuntimeError("invalid_provider_schema")
    return result


def rank_candidates(
    strategy: Strategy,
    payload: dict[str, Any],
    *,
    now: datetime | None = None,
) -> list[dict[str, Any]]:
    """Pure, deterministic filter of documented GeckoTerminal pool snapshots.

    Unverified token authorities, holder ownership, and sellability mean every
    returned candidate remains WATCH_ONLY, never trade-eligible.
    """
    if strategy not in _PATHS:
        raise ValueError("unknown strategy")
    if not isinstance(payload, dict) or not isinstance(payload.get("data"), list):
        raise ValueError("invalid pool snapshot")
    observed = now or datetime.now(timezone.utc)
    if observed.utcoffset() != timezone.utc.utcoffset(observed):
        observed = observed.astimezone(timezone.utc)

    included = {
        item.get("id"): item.get("attributes", {})
        for item in payload.get("included", [])
        if isinstance(item, dict) and item.get("type") == "token"
        and isinstance(item.get("id"), str)
        and isinstance(item.get("attributes"), dict)
    } if isinstance(payload.get("included"), list) else {}

    out: list[dict[str, Any]] = []
    seen: set[str] = set()
    for pool in payload["data"][:100]:
        if not isinstance(pool, dict) or pool.get("type") != "pool":
            continue
        attr = pool.get("attributes")
        rel = pool.get("relationships")
        if not isinstance(attr, dict) or not isinstance(rel, dict):
            continue
        base = rel.get("base_token")
        base_data = base.get("data") if isinstance(base, dict) else None
        base_id = base_data.get("id") if isinstance(base_data, dict) else None
        token = included.get(base_id, {})
        mint = token.get("address")
        address = attr.get("address")
        if (
            not isinstance(mint, str) or not _BASE58.fullmatch(mint)
            or not isinstance(address, str) or not _BASE58.fullmatch(address)
        ):
            continue
        symbol = token.get("symbol")
        if not isinstance(symbol, str) or not (1 <= len(symbol.strip()) <= 24):
            continue
        symbol = symbol.strip()
        if symbol.upper() in {"SOL", "WSOL", "USDC", "USDT"}:
            continue
        created = _timestamp(attr.get("pool_created_at"))
        liquidity = _number(attr.get("reserve_in_usd"))
        volume = _number(_window(attr.get("volume_usd"), "m5"))
        movement = _number(_window(attr.get("price_change_percentage"), "m5"))
        trades = attr.get("transactions")
        buys = _number(_window(trades, "m5", "buys"))
        sells = _number(_window(trades, "m5", "sells"))
        if any(value is None for value in (created, liquidity, volume, movement, buys, sells)):
            continue
        assert created is not None and liquidity is not None and volume is not None
        assert movement is not None and buys is not None and sells is not None
        age_minutes = (observed - created).total_seconds() / 60
        if age_minutes < 0 or buys < 0 or sells < 0 or liquidity <= 0:
            continue
        if strategy == "new_launch":
            if not (age_minutes <= 360 and liquidity >= 10_000 and volume >= 500
                    and buys >= 3 and sells >= 1):
                continue
            score = min(100.0, round(
                40 + min(volume / 200, 25) + min(buys / 2, 15)
                + min(liquidity / 5000, 10) + max(0, (120 - age_minutes) / 12), 1
            ))
        else:
            if not (liquidity >= 50_000 and volume >= 3_000 and 3 <= movement <= 80
                    and buys >= 5 and sells >= 2 and age_minutes >= 5):
                continue
            score = min(100.0, round(
                35 + min(movement * 1.2, 30) + min(volume / 1000, 20)
                + min(buys / 5, 10) + min(liquidity / 50_000, 5), 1
            ))
        # De-duplicate by mint to avoid a popular token filling the whole list.
        if mint in seen:
            continue
        seen.add(mint)
        out.append({
            "strategy": strategy,
            "symbol": symbol,
            "token_address": mint,
            "pool_address": address,
            "liquidity_usd": round(liquidity, 2),
            "volume_5m_usd": round(volume, 2),
            "change_5m_pct": round(movement, 2),
            "age_minutes": round(age_minutes, 1),
            "buys_5m": int(buys),
            "sells_5m": int(sells),
            "research_score": score,
            "risk_status": "unverified",
            "tradable": False,
            "source": "geckoterminal",
        })
    return sorted(out, key=lambda item: item["research_score"], reverse=True)[:10]


def scan_strategy(strategy: Strategy) -> dict[str, Any]:
    """Perform an explicit, rate-limited, fail-closed read-only scan."""
    if strategy not in _PATHS:
        raise ValueError("unknown strategy")
    if not discovery_enabled():
        return {
            "strategy": strategy,
            "status": "disabled",
            "source": "geckoterminal",
            "observed_at": None,
            "candidates": [],
            "error": None,
        }

    # One process-level cache and single-flight fetch; avoids aggressive polling
    # of the free public provider, including a short cooldown after failures.
    with _CACHE_LOCK:
        previous = _CACHE.get(strategy)
        if previous and time.monotonic() - previous[0] < _CACHE_SECONDS:
            return json.loads(json.dumps(previous[1]))
        observed_at = datetime.now(timezone.utc).isoformat()
        try:
            payload = fetch_json(strategy)
            candidates = rank_candidates(strategy, payload)
            result = {
                "strategy": strategy,
                "status": "ok",
                "source": "geckoterminal",
                "observed_at": observed_at,
                "candidates": candidates,
                "error": None,
            }
        except (RuntimeError, ValueError) as exc:
            logger.warning("Meme coin %s discovery failed: %s", strategy, exc)
            result = {
                "strategy": strategy,
                "status": "unavailable",
                "source": "geckoterminal",
                "observed_at": None,
                "candidates": [],
                "error": "provider_unavailable",
            }
        _CACHE[strategy] = (time.monotonic(), result)
        return json.loads(json.dumps(result))
