"""Deterministic watchlist scores; NEVER produces executable trade orders."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from data_provider.solana_meme import MemeQuote


@dataclass(frozen=True)
class WatchCandidate:
    strategy: str
    mint: str
    symbol: str
    pool_id: str
    source: str
    score: int
    status: str  # watch, blocked
    reasons: tuple[str, ...]


def _flag_status(value: Any) -> bool | None:
    if isinstance(value, dict):
        value = value.get("status")
    if value in ("1", 1, True):
        return True
    if value in ("0", 0, False):
        return False
    return None


def security_reasons(record: dict[str, Any] | None) -> list[str]:
    """Unknown security fields are never silently treated as clean."""
    if not record:
        return ["security_unknown"]
    risks = []
    for field in ("mintable", "freezable", "closable", "non_transferable", "transfer_hook"):
        state = _flag_status(record.get(field))
        if state is True:
            risks.append(field)
        if state is None:
            risks.append(f"{field}_unknown")
    default_state = record.get("default_account_state")
    if default_state is not None and str(default_state) != "1":
        risks.append("default_account_not_initialized")
    creator = record.get("creator")
    if isinstance(creator, dict) and _flag_status(creator.get("malicious_address")) is True:
        risks.append("malicious_creator")
    return risks


def evaluate(quote: MemeQuote, strategy: str, now_ms: int,
             security: dict[str, Any] | None) -> WatchCandidate:
    """Heuristics for paper-watchlists only (not financial recommendations)."""
    if strategy not in ("new_coin_hunter", "momentum_watcher"):
        raise ValueError("Unknown strategy")
    reasons: list[str] = []
    if quote.observed_at_ms > now_ms or now_ms - quote.observed_at_ms > 120_000:
        reasons.append("stale_quote")
    if quote.price_usd is None or quote.price_usd <= 0:
        reasons.append("price_unknown")
    if quote.liquidity_usd is None or quote.liquidity_usd < 10_000:
        reasons.append("liquidity_below_10000_or_unknown")
    if quote.volume_h24_usd is None or quote.volume_h24_usd < 2_000:
        reasons.append("volume_below_2000_or_unknown")
    if quote.buys_m5 is None or quote.sells_m5 is None:
        reasons.append("transaction_counts_unknown")
    elif quote.buys_m5 < 5 or quote.buys_m5 <= quote.sells_m5:
        reasons.append("weak_buy_activity")
    if strategy == "new_coin_hunter":
        if quote.pool_created_at_ms is None or not 0 <= now_ms - quote.pool_created_at_ms <= 4 * 3_600_000:
            reasons.append("pool_not_confirmed_recent")
        # DEX profile feed is not evidence of new mint or pool.
        if quote.source != "geckoterminal":
            reasons.append("not_new_pool_feed")
    else:
        if quote.change_m5_pct is None or not 2 <= quote.change_m5_pct <= 20:
            reasons.append("momentum_outside_2_to_20_pct")
        if quote.volume_h24_usd is None or quote.volume_h24_usd < 50_000:
            reasons.append("volume_below_50000_or_unknown")
        if quote.buys_m5 is None or quote.buys_m5 < 20:
            reasons.append("insufficient_five_minute_buys")
    reasons.extend(security_reasons(security))
    # A high score with a blocked status must NEVER be interpreted as trade approval.
    score = 0
    if quote.liquidity_usd is not None and quote.liquidity_usd >= 10_000:
        score += 25
    if quote.volume_h24_usd is not None and quote.volume_h24_usd >= (50_000 if strategy == "momentum_watcher" else 2_000):
        score += 25
    if quote.buys_m5 is not None and quote.sells_m5 is not None and quote.buys_m5 >= 5 and quote.buys_m5 > quote.sells_m5:
        score += 25
    if strategy == "new_coin_hunter" and quote.pool_created_at_ms is not None and 0 <= now_ms - quote.pool_created_at_ms <= 4 * 3_600_000:
        score += 25
    if strategy == "momentum_watcher" and quote.change_m5_pct is not None and 2 <= quote.change_m5_pct <= 20:
        score += 25
    return WatchCandidate(strategy, quote.mint, quote.symbol, quote.pool_id, quote.source,
                          score, "blocked" if reasons else "watch", tuple(reasons))
