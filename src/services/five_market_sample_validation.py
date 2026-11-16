# -*- coding: utf-8 -*-
"""Read-only sample coverage check for ETRE's five investment-focus markets.

This is a bounded, opt-in Yahoo historical-data diagnostic, not an exchange-wide
stock screener, a buy/sell recommendation, or a broker trading integration.
Never touches SQLite, positions, LLM credentials or order APIs.
"""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import date, datetime
import json
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from src.services.six_market_live_smoke import MarketProbe, probe_six_markets


# One independently checked equity per selected market.
FOCUS_MARKETS = ("tr", "us", "de", "hk", "jp")
CORE_PROBES: tuple[MarketProbe, ...] = (
    MarketProbe("tr", "THYAO.IS", "THYAO.IS", "TRY"),
    MarketProbe("us", "AAPL", "AAPL", "USD"),
    MarketProbe("de", "SAP.DE", "SAP.DE", "EUR"),
    MarketProbe("hk", "HK00700", "0700.HK", "HKD"),
    MarketProbe("jp", "7203.T", "7203.T", "JPY"),
)
# Bounded expansion for coverage exploration; not an official exchange
# constituent list or a guarantee that these names trade at every broker.
EXTRA_PROBES: tuple[MarketProbe, ...] = (
    MarketProbe("tr", "ASELS.IS", "ASELS.IS", "TRY"),
    MarketProbe("us", "MSFT", "MSFT", "USD"),
    MarketProbe("de", "SIE.DE", "SIE.DE", "EUR"),
    MarketProbe("hk", "HK01810", "1810.HK", "HKD"),
    MarketProbe("jp", "6758.T", "6758.T", "JPY"),
)


def validate_five_market_samples(
    *,
    as_of: date,
    sample_set: str = "core",
    **kwargs: Any,
) -> dict[str, Any]:
    """Keep each stock and market's data quality distinct, including failures."""
    if sample_set not in {"core", "expanded"}:
        raise ValueError("sample_set must be core or expanded")
    probes = CORE_PROBES if sample_set == "core" else CORE_PROBES + EXTRA_PROBES
    if len({probe.code for probe in probes}) != len(probes):
        raise ValueError("duplicate sample symbols")

    result = probe_six_markets(
        as_of=as_of,
        probes=probes,
        scope=f"etre_five_market_{sample_set}_historical_samples",
        **kwargs,
    )

    result["checked_symbols"] = result.pop("checked_markets")
    result["analyzed_symbols"] = result.pop("analyzed_markets")
    by_market: dict[str, dict[str, Any]] = {}
    for market in FOCUS_MARKETS:
        subset = [item for item in result["results"] if item["market"] == market]
        statuses = Counter(str(item["status"]) for item in subset)
        successes = statuses.get("analyzed", 0)
        by_market[market] = {
            "checked_symbols": len(subset),
            "analyzed_symbols": successes,
            "sample_status": (
                "samples_passed" if len(subset) > 0 and successes == len(subset)
                else "partial" if successes > 0 else "samples_failed"
            ),
            "failure_status_counts": {
                key: count for key, count in sorted(statuses.items()) if key != "analyzed"
            },
        }
    result["markets_checked"] = len(FOCUS_MARKETS)
    result["by_market"] = by_market
    result["note"] = (
        "Yahoo daily price, currency, completed session and technical-score "
        "sample validation only. The listed symbols are examples, not full "
        "exchange coverage, live quotes, Midas account permissions or trades."
    )
    return result


def main() -> None:
    parser = argparse.ArgumentParser(
        description="ETRE five-market read-only historical sample validation"
    )
    parser.add_argument("--sample-set", choices=("core", "expanded"), default="core")
    parser.add_argument(
        "--as-of", type=date.fromisoformat,
        default=datetime.now(ZoneInfo("Europe/Istanbul")).date(),
    )
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    report = validate_five_market_samples(
        as_of=args.as_of,
        sample_set=args.sample_set,
    )
    payload = json.dumps(report, indent=2, ensure_ascii=False) + "\n"
    if args.output:
        args.output.write_text(payload, encoding="utf-8")
    print(payload, end="")
    expected = len(CORE_PROBES) if args.sample_set == "core" else len(CORE_PROBES + EXTRA_PROBES)
    if report["checked_symbols"] != expected or report["analyzed_symbols"] != expected:
        raise SystemExit(
            f"ETRE {args.sample_set} historical sample check incomplete: "
            f"{report['analyzed_symbols']}/{expected}; inspect JSON per-symbol statuses"
        )


if __name__ == "__main__":
    main()
