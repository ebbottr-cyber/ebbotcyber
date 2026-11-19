"""Opt-in Solana meme-market discovery. Read-only; no wallet or order APIs.

DEX Screener latest token profiles are *profile updates*, not mint events.
GeckoTerminal new pools are *pool events*, not mint events.
"""

from __future__ import annotations

import json
import math
import re
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Callable
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen


_MINT_RE = re.compile(r"^[1-9A-HJ-NP-Za-km-z]{32,44}$")
_NETWORK = "solana"
_MAX_RESPONSE_BYTES = 2_000_000


class MarketDataError(RuntimeError):
    """Provider is unreachable or returned an invalid payload."""


def is_solana_address(value: Any) -> bool:
    return isinstance(value, str) and bool(_MINT_RE.fullmatch(value))


def _finite_float(value: Any, default: float | None = None) -> float | None:
    try:
        number = float(value)
        return number if math.isfinite(number) else default
    except (ValueError, TypeError, OverflowError):
        return default


def _float(value: Any, default: float = 0.0) -> float:
    number = _finite_float(value)
    return number if number is not None else default


def _obj(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _time_from_iso(value: Any) -> int | None:
    if not isinstance(value, str):
        return None
    try:
        return int(datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp() * 1000)
    except (ValueError, OverflowError):
        return None


def get_json(url: str) -> Any:
    """Perform one bounded HTTPS GET. No automatic unbounded retries."""
    if not url.startswith(("https://api.dexscreener.com/", "https://api.geckoterminal.com/", "https://api.gopluslabs.io/")):
        raise MarketDataError("Unapproved market data host")
    try:
        request = Request(url, headers={"Accept": "application/json", "User-Agent": "EBBot-MemeRadar/0.1"})
        with urlopen(request, timeout=8) as response:
            if response.status != 200:
                raise MarketDataError(f"Provider HTTP {response.status}")
            data = response.read(_MAX_RESPONSE_BYTES + 1)
        if len(data) > _MAX_RESPONSE_BYTES:
            raise MarketDataError("Provider response too large")
        return json.loads(data)
    except (HTTPError, URLError, TimeoutError, OSError, json.JSONDecodeError) as error:
        raise MarketDataError(f"Provider request failed: {type(error).__name__}") from error


@dataclass(frozen=True)
class MemeQuote:
    mint: str
    symbol: str
    source: str
    pool_id: str
    price_usd: float | None
    liquidity_usd: float | None
    volume_h24_usd: float | None
    buys_m5: int | None
    sells_m5: int | None
    change_m5_pct: float | None
    pool_created_at_ms: int | None
    observed_at_ms: int


def _nonnegative(value: Any) -> float | None:
    number = _finite_float(value)
    return number if number is not None and number >= 0 else None


def _count(value: Any) -> int | None:
    number = _nonnegative(value)
    return int(number) if number is not None and number.is_integer() else None


def _dex_quotes(items: Any, now_ms: int) -> list[MemeQuote]:
    if not isinstance(items, list):
        raise MarketDataError("DEX Screener token quotes: invalid list")
    quotes = []
    for item in items:
        pair = _obj(item)
        if pair.get("chainId") != _NETWORK:
            continue
        token = _obj(pair.get("baseToken"))
        mint = token.get("address")
        if not is_solana_address(mint):
            continue
        tx5 = _obj(_obj(pair.get("txns")).get("m5"))
        pair_id = pair.get("pairAddress")
        if not isinstance(pair_id, str) or not pair_id:
            continue
        quotes.append(MemeQuote(
            mint=mint, symbol=str(token.get("symbol") or "?")[:24], source="dexscreener",
            pool_id=pair_id, price_usd=_nonnegative(pair.get("priceUsd")),
            liquidity_usd=_nonnegative(_obj(pair.get("liquidity")).get("usd")),
            volume_h24_usd=_nonnegative(_obj(pair.get("volume")).get("h24")),
            buys_m5=_count(tx5.get("buys")), sells_m5=_count(tx5.get("sells")),
            change_m5_pct=_finite_float(_obj(pair.get("priceChange")).get("m5")),
            pool_created_at_ms=_count(pair.get("pairCreatedAt")), observed_at_ms=now_ms,
        ))
    return quotes


def _mint_from_relationship(record: Any) -> str | None:
    # GeckoTerminal JSON:API token ID is formatted `solana_<mint>`.
    raw = _obj(_obj(record).get("data")).get("id")
    if not isinstance(raw, str) or not raw.startswith("solana_"):
        return None
    mint = raw[len("solana_"):]
    return mint if is_solana_address(mint) else None


def _gecko_quotes(document: Any, now_ms: int) -> list[MemeQuote]:
    data = _obj(document).get("data")
    if not isinstance(data, list):
        raise MarketDataError("GeckoTerminal pools: invalid data")
    quotes = []
    for raw in data:
        pool = _obj(raw)
        attrs = _obj(pool.get("attributes"))
        mint = _mint_from_relationship(_obj(pool.get("relationships")).get("base_token"))
        pool_id = pool.get("id")
        if not mint or not isinstance(pool_id, str) or not pool_id.startswith("solana_"):
            continue
        changes = _obj(attrs.get("price_change_percentage"))
        transactions = _obj(_obj(attrs.get("transactions")).get("m5"))
        quotes.append(MemeQuote(
            mint=mint, symbol=str(attrs.get("name") or "?")[:24], source="geckoterminal",
            pool_id=pool_id, price_usd=_nonnegative(attrs.get("base_token_price_usd")),
            liquidity_usd=_nonnegative(attrs.get("reserve_in_usd")),
            volume_h24_usd=_nonnegative(_obj(attrs.get("volume_usd")).get("h24")),
            buys_m5=_count(transactions.get("buys")), sells_m5=_count(transactions.get("sells")),
            change_m5_pct=_finite_float(changes.get("m5")),
            pool_created_at_ms=_time_from_iso(attrs.get("pool_created_at")), observed_at_ms=now_ms,
        ))
    return quotes


class SolanaMemeFeed:
    def __init__(self, transport: Callable[[str], Any] = get_json):
        self.transport = transport

    def new_pools(self, now_ms: int) -> list[MemeQuote]:
        """New *pools* (not token mints); geared to early discovery."""
        data = self.transport("https://api.geckoterminal.com/api/v2/networks/solana/new_pools?page=1")
        return _gecko_quotes(data, now_ms)

    def latest_profiles(self, now_ms: int, limit: int = 8) -> list[MemeQuote]:
        """Discover Solana profiles and request their pairs, max 8 by default."""
        if not 1 <= limit <= 30:
            raise ValueError("limit must be in [1, 30]")
        profiles = self.transport("https://api.dexscreener.com/token-profiles/latest/v1")
        if not isinstance(profiles, list):
            raise MarketDataError("DEX Screener token profiles: invalid list")
        mints: list[str] = []
        for profile in profiles:
            entry = _obj(profile)
            mint = entry.get("tokenAddress")
            if entry.get("chainId") == _NETWORK and is_solana_address(mint) and mint not in mints:
                mints.append(mint)
                if len(mints) >= limit:
                    break
        if not mints:
            return []
        url = "https://api.dexscreener.com/tokens/v1/solana/" + ",".join(quote(mint, safe="") for mint in mints)
        quotes = _dex_quotes(self.transport(url), now_ms)
        return [q for q in quotes if q.mint in mints]

    def security(self, mint: str) -> dict[str, Any] | None:
        """Return one GoPlus record. None means unknown, never 'safe'."""
        if not is_solana_address(mint):
            raise ValueError("Invalid Solana token mint")
        url = "https://api.gopluslabs.io/api/v1/solana/token_security?contract_addresses=" + quote(mint, safe="")
        payload = _obj(self.transport(url))
        if str(payload.get("code")) != "1":
            raise MarketDataError("GoPlus returned unsuccessful code")
        records = _obj(payload.get("result"))
        record = records.get(mint) or records.get(mint.lower())
        return record if isinstance(record, dict) and record else None
