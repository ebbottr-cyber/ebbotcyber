"""Manual read-only market price-quality preflight for all imported assets.

One explicit --fetch runs four public Binance GET requests and produces aggregate
quality counts; nothing is persisted, no quotes are treated as trade fills.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import sys

from src.services.paper_universe_inventory import read_input
from src.services.paper_universe_sources import (
    BINANCE_SPOT_URL, BINANCE_SPOT_TICKERS_URL,
    USDM_MARKS_URL, COINM_MARKS_URL, fetch_source,
)
from src.services.paper_market_data_quality import (
    active_spot_assets, check_bist, check_futures, check_spot,
)


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="All-market price source audit; never places orders")
    p.add_argument("--fetch", action="store_true", help="Explicit opt-in to four public GET requests")
    p.add_argument("--stocks", type=Path, required=True, help="KAP company-code CSV")
    p.add_argument("--spot", type=Path, required=True, help="Binance Spot asset JSON")
    p.add_argument("--usdm", type=Path, required=True, help="Binance USD-M contract JSON")
    p.add_argument("--coinm", type=Path, required=True, help="Binance COIN-M contract JSON")
    p.add_argument("--bist-daily", type=Path,
                   help="Optional licensed, timestamped BIST daily close CSV")
    return p


def run(args: argparse.Namespace) -> int:
    if not args.fetch:
        print(json.dumps({"status": "DISABLED", "network_requests": 0,
                          "paper_trading_enabled": False, "live_trading_enabled": False}))
        return 0

    now = datetime.now(timezone.utc)
    kap = read_input(args.stocks)
    assets = active_spot_assets(read_input(args.spot))
    usdm = read_input(args.usdm)
    coinm = read_input(args.coinm)
    bist = check_bist(kap, read_input(args.bist_daily) if args.bist_daily else None,
                      today=now.date())
    # Only fixed, public, allowlisted market-data GET URLs; no query params.
    endpoints = (BINANCE_SPOT_URL, BINANCE_SPOT_TICKERS_URL,
                 USDM_MARKS_URL, COINM_MARKS_URL)
    responses = [fetch_source(url) for url in endpoints]
    at = datetime.now(timezone.utc)
    observed_ms = int(at.timestamp() * 1000)
    spot = check_spot(responses[0], responses[1], assets)
    futures_usdm = check_futures(usdm, responses[2],
                                 market="binance_usdm_futures", now_ms=observed_ms)
    futures_coinm = check_futures(coinm, responses[3],
                                  market="binance_coinm_futures", now_ms=observed_ms)
    output = {
        "status": "QUALITY_AUDIT_ONLY",
        "observed_at_utc": at.isoformat(),
        "bist": bist,
        "spot": spot,
        "usdm": futures_usdm,
        "coinm": futures_coinm,
        "full_market_price_coverage_proven": False,
        "prices_executable": False,
        "paper_trading_enabled": False,
        "live_trading_enabled": False,
        "leverage_enabled": False,
        "orders": 0,
        "paper_fills": 0,
        "journal_writes": 0,
        "network_requests": len(endpoints),
    }
    print(json.dumps(output, ensure_ascii=False, sort_keys=True, allow_nan=False))
    return 0


def main() -> int:
    args = parser().parse_args()
    try:
        return run(args)
    except (ValueError, OSError, UnicodeError, OverflowError) as exc:
        print(json.dumps({
            "status": "BLOCKED",
            "reason": str(exc) if isinstance(exc, ValueError) else "unavailable_or_invalid_market_data",
            "paper_trading_enabled": False,
            "live_trading_enabled": False,
            "orders": 0,
            "paper_fills": 0,
        }, ensure_ascii=False), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
