"""Bounded, one-off, read-only collection of *prospective* Solana observations.

Not historical OHLCV, not paper orders, not a strategy return calculator.
The selected token identities stay fixed after discovery; later rounds only
query fresh quotes for those same mints. No persistent process or scheduler.
"""

from __future__ import annotations

import argparse
import json
import time
from dataclasses import replace
from pathlib import Path
from typing import Any, Callable

from data_provider.solana_meme import (
    MarketDataError, MemeQuote, SolanaMemeFeed, _dex_quotes, _gecko_quotes, is_solana_address,
)
from scripts.scan_solana_meme import _select_quotes
from src.services.solana_meme_radar import evaluate

STRATEGIES = ("new_coin_hunter", "momentum_watcher")
PRICING_SOURCE = "dexscreener"
_GECKO_POOL_ENDPOINT = "https://api.geckoterminal.com/api/v2/networks/solana/pools/"
_MAX_OBSERVATIONS = 4


def _error(provider: str, error: Exception | None = None) -> dict[str, str]:
    """Do not leak upstream payloads, URLs or environment secrets into logs."""
    return {"provider": provider, "error_class": type(error).__name__ if error else "MissingData"}


def _eligible(quote: MemeQuote) -> bool:
    return (
        is_solana_address(quote.mint)
        and quote.price_usd is not None and quote.price_usd > 0
        and quote.liquidity_usd is not None and quote.liquidity_usd >= 10_000
    )


def _candidate(quote: MemeQuote, discovery: MemeQuote, now_ms: int,
               security: dict[str, Any] | None) -> dict[str, Any]:
    # The original GeckoTerminal source establishes the new-pool discovery
    # claim. A repeated quote may come from DEX Screener (a different pool)
    # or the verified original GeckoTerminal pool. Keep both identities.
    for_evaluation = replace(
        quote,
        source=discovery.source,
        pool_created_at_ms=discovery.pool_created_at_ms,
        observed_at_ms=now_ms,
    )
    analyses: dict[str, dict[str, Any]] = {}
    for strategy in STRATEGIES:
        result = evaluate(for_evaluation, strategy, now_ms, security)
        analyses[strategy] = {
            "status": result.status,
            "score": result.score,
            "reasons": list(result.reasons),
        }
    return {
        "timestamp_ms": now_ms,
        "status": "priced",
        "mint": discovery.mint,
        "discovery_source": discovery.source,
        "discovery_pool_id": discovery.pool_id,
        "discovery_pool_created_at_ms": discovery.pool_created_at_ms,
        "price_source": quote.source,
        "price_pair_id": quote.pool_id,
        "price_usd": str(quote.price_usd),
        "liquidity_usd": str(quote.liquidity_usd) if quote.liquidity_usd is not None else None,
        "volume_h24_usd": str(quote.volume_h24_usd) if quote.volume_h24_usd is not None else None,
        "buys_m5": quote.buys_m5,
        "sells_m5": quote.sells_m5,
        "change_m5_pct": quote.change_m5_pct,
        "risk_record_present": security is not None,
        "strategies": analyses,
    }


def collect(
    feed: SolanaMemeFeed,
    *,
    rounds: int = 3,
    interval_seconds: int = 60,
    limit: int = 2,
    clock: Callable[[], float] = time.time,
    sleeper: Callable[[float], None] = time.sleep,
) -> dict[str, Any]:
    """Gather <=4 spaced samples, no automatic retry, no background work."""
    if type(rounds) is not int or not 2 <= rounds <= _MAX_OBSERVATIONS:
        raise ValueError("rounds must be from 2 through 4")
    if type(interval_seconds) is not int or not 60 <= interval_seconds <= 120:
        raise ValueError("interval must be from 60 through 120 seconds")
    if type(limit) is not int or not 1 <= limit <= 2:
        raise ValueError("at most two mints per test")

    started_ms = int(clock() * 1000)
    discoveries: list[MemeQuote] = []
    errors: list[dict[str, str]] = []
    for provider, discover in (
        ("geckoterminal", lambda: feed.new_pools(started_ms)),
        ("dexscreener_profiles", lambda: feed.latest_profiles(started_ms, limit=limit)),
    ):
        try:
            discoveries.extend(discover())
        except (MarketDataError, ValueError) as exc:
            errors.append(_error(provider, exc))

    # Do not select an illiquid/unpriced candidate merely to fill the budget.
    selected = _select_quotes([q for q in discoveries if _eligible(q)], limit)
    fixed: dict[str, MemeQuote] = dict(selected)
    observed: list[dict[str, Any]] = []
    for index in range(rounds):
        if index:
            sleeper(interval_seconds)

        # One DEX HTTP call fetches quotes for the EXACT mints selected at T0.
        # We do not silently substitute other tokens discovered later.
        now_ms = int(clock() * 1000)
        prices: dict[str, MemeQuote] = {}
        if fixed:
            try:
                url = "https://api.dexscreener.com/tokens/v1/solana/" + ",".join(fixed)
                items = _dex_quotes(feed.transport(url), now_ms)
                for mint in fixed:
                    quoted = [q for q in items if q.mint == mint and _eligible(q)]
                    if quoted:
                        preferred = fixed[mint].pool_id
                        prices[mint] = max(
                            quoted,
                            key=lambda q: (
                                q.pool_id == preferred,
                                q.liquidity_usd or 0,
                            ),
                        )
            except (MarketDataError, ValueError) as exc:
                errors.append(_error("dexscreener_quotes", exc))

        # Some new GeckoTerminal pools are not yet indexed by DEX Screener.
        # A narrowly bounded fallback reads ONLY the original discovered pool
        # and checks BOTH pool ID and base mint. No cross-token substitution.
        for mint, original in fixed.items():
            if mint in prices or original.source != "geckoterminal":
                continue
            if not original.pool_id.startswith("solana_"):
                continue
            pool_address = original.pool_id[len("solana_"):]
            if not is_solana_address(pool_address):
                continue
            try:
                detail = feed.transport(_GECKO_POOL_ENDPOINT + pool_address + "?include=base_token")
                if not isinstance(detail, dict) or not isinstance(detail.get("data"), dict):
                    raise MarketDataError("Gecko pool payload invalid")
                normalized = _gecko_quotes({
                    "data": [detail["data"]],
                    "included": detail.get("included", []),
                }, now_ms)
                valid = [quote for quote in normalized
                         if quote.mint == mint and quote.pool_id == original.pool_id
                         and _eligible(quote)]
                if valid:
                    prices[mint] = valid[0]
            except (MarketDataError, ValueError) as exc:
                errors.append(_error("geckoterminal_pool", exc))

        # Record receipt time AFTER fetching all public price responses.
        received_ms = int(clock() * 1000)
        for mint, original in fixed.items():
            price = prices.get(mint)
            if price is None:
                observed.append({
                    "timestamp_ms": received_ms,
                    "mint": mint,
                    "status": "missing_price",
                    "price_source": None,
                    "strategies": {},
                })
                continue
            try:
                risk = feed.security(mint)
            except (MarketDataError, ValueError) as exc:
                errors.append(_error("goplus", exc))
                risk = None
            observed.append(_candidate(price, original, received_ms, risk))

    valid_counts = {mint: 0 for mint in fixed}
    for sample in observed:
        if sample.get("price_usd") is not None:
            valid_counts[sample["mint"]] += 1

    complete = bool(fixed) and all(count == rounds for count in valid_counts.values())
    # A green collection check requires both a complete price series and no
    # provider errors. Risk unknown still shows BLOCKED, never assumed safe.
    result = "passed" if complete and not errors else "degraded" if observed else "inconclusive"
    return {
        "schema_version": 1,
        "mode": "bounded_prospective_public_market_observations",
        "data_origin": "live_public_api_not_historical",
        "trading_enabled": False,
        "wallet_enabled": False,
        "background_schedule_enabled": False,
        "performance_calculated": False,
        "start_timestamp_ms": started_ms,
        "requested_rounds": rounds,
        "minimum_interval_seconds": interval_seconds,
        "tracked_mints": list(fixed),
        "observations": observed,
        "errors": errors,
        "summary": {
            "result": result,
            "rounds": rounds,
            "selected_tokens": len(fixed),
            "valid_price_observations": sum(valid_counts.values()),
            "missing_price_observations": len(observed) - sum(valid_counts.values()),
            "complete_token_series": sum(n == rounds for n in valid_counts.values()),
            "provider_error_classes": sorted({e["provider"] + ":" + e["error_class"] for e in errors}),
            "note": "No realized trades, market performance or verified OHLCV in these snapshots",
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Bounded, manual, read-only Solana observations")
    parser.add_argument("--live", action="store_true", help="Explicit one-time public API calls")
    parser.add_argument("--rounds", choices=[2, 3, 4], type=int, default=3)
    parser.add_argument("--interval", choices=[60, 90, 120], type=int, default=60)
    parser.add_argument("--limit", choices=[1, 2], type=int, default=2)
    parser.add_argument("--output", default="solana-public-observations.json")
    args = parser.parse_args()
    if not args.live:
        print(json.dumps({
            "status": "disabled", "trading_enabled": False,
            "message": "Explicit --live is required for public data collection",
        }, indent=2))
        return 0
    report = collect(SolanaMemeFeed(), rounds=args.rounds,
                     interval_seconds=args.interval, limit=args.limit)
    path = Path(args.output)
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    # Print aggregate diagnostics only, not identifiers or raw payloads.
    print(json.dumps({
        "data_origin": report["data_origin"],
        "trading_enabled": False,
        "performance_calculated": False,
        "summary": report["summary"],
    }, ensure_ascii=False, indent=2))
    return 0 if report["summary"]["result"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
