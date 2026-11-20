"""Manually triggered, read-only Solana meme watchlist. No trading capabilities.

Run: python -m scripts.scan_solana_meme --live
"""

from __future__ import annotations

import argparse
import json
import time
from dataclasses import asdict

from data_provider.solana_meme import MarketDataError, SolanaMemeFeed
from src.services.solana_meme_radar import evaluate


def _select_quotes(quotes: list, limit: int) -> dict:
    if not 1 <= limit <= 8:
        raise ValueError("limit must be between 1 and 8")
    ranked = sorted(
        quotes,
        key=lambda quote: (quote.liquidity_usd or 0, quote.volume_h24_usd or 0),
        reverse=True,
    )
    selected: dict = {}
    if limit >= 2:
        for source in ("geckoterminal", "dexscreener"):
            for quote in ranked:
                if (quote.source == source and quote.mint not in selected
                        and (quote.liquidity_usd or 0) >= 10_000):
                    selected[quote.mint] = quote
                    break
    for quote in ranked:
        if len(selected) >= limit:
            break
        if quote.mint not in selected:
            selected[quote.mint] = quote
    return selected


def scan(*, live: bool = False, limit: int = 8) -> dict:
    if not live:
        return {"enabled": False, "trading_enabled": False, "candidates": [], "errors": [], "message": "Use --live to explicitly enable read-only API calls"}
    feed = SolanaMemeFeed()
    now_ms = int(time.time() * 1000)
    candidates = []
    errors = []
    quotes = []
    for name, fetch in (("geckoterminal", feed.new_pools), ("dexscreener", lambda t: feed.latest_profiles(t, limit=limit))):
        try:
            quotes.extend(fetch(now_ms))
        except (MarketDataError, ValueError) as error:
            errors.append({"provider": name, "message": str(error)})
    # Give each independent discovery source one eligible slot when possible.
    # Otherwise a single high-liquidity feed could occupy the entire budget,
    # making the "new pool" and "momentum" discovery paths indistinguishable.
    selected = _select_quotes(quotes, limit)
    for quote in selected.values():
        try:
            security = feed.security(quote.mint)
        except (MarketDataError, ValueError) as error:
            errors.append({"provider": "goplus", "mint": quote.mint, "message": str(error)})
            security = None
        for strategy in ("new_coin_hunter", "momentum_watcher"):
            candidates.append(asdict(evaluate(quote, strategy, now_ms, security)))
    return {"enabled": True, "trading_enabled": False, "candidates": candidates, "errors": errors,
            "disclaimer": "Heuristic monitoring only; no buy/sell signals or transactions"}


def main() -> None:
    parser = argparse.ArgumentParser(description="Read-only Solana meme monitoring")
    parser.add_argument("--live", action="store_true", help="Opt into real API requests; never trade")
    parser.add_argument("--limit", type=int, default=8, help="Number of unique mints (1–8)")
    args = parser.parse_args()
    if not 1 <= args.limit <= 8:
        parser.error("--limit must be between 1 and 8")
    print(json.dumps(scan(live=args.live, limit=args.limit), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
