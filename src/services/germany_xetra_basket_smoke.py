# -*- coding: utf-8 -*-
"""Read-only Yahoo/Xetra historical validation across three German equities.

These samples cover distinct German companies but do not verify all Xetra
listings, delayed vs real-time quotes, Midas tradability or any trade execution.
No database writes, LLM calls, brokerage accounts or order APIs are used.
"""
from __future__ import annotations

import argparse
from datetime import date, datetime
import json
from pathlib import Path
from zoneinfo import ZoneInfo

from src.services.six_market_live_smoke import MarketProbe, probe_six_markets


GERMANY_BASKET_PROBES: tuple[MarketProbe, ...] = (
    MarketProbe("de", "SAP.DE", "SAP.DE", "EUR"),
    MarketProbe("de", "SIE.DE", "SIE.DE", "EUR"),
    MarketProbe("de", "BMW.DE", "BMW.DE", "EUR"),
)


def probe_germany_xetra_basket(*, as_of: date, **kwargs) -> dict:
    """Check all three independently; never mask a failed member by averaging."""
    return probe_six_markets(
        as_of=as_of,
        probes=GERMANY_BASKET_PROBES,
        scope="germany_xetra_yahoo_three_equities",
        **kwargs,
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Read-only three-equity Xetra Yahoo history/EUR/technical smoke"
    )
    parser.add_argument(
        "--as-of", type=date.fromisoformat,
        default=datetime.now(ZoneInfo("Europe/Berlin")).date(),
    )
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    report = probe_germany_xetra_basket(as_of=args.as_of)
    report["note"] = (
        "Three independent German equity samples only; not an all-Xetra or live "
        "market coverage claim, nor Midas trading permission or trade execution."
    )
    output = json.dumps(report, indent=2, ensure_ascii=False) + "\n"
    if args.output:
        args.output.write_text(output, encoding="utf-8")
    print(output, end="")
    expected = len(GERMANY_BASKET_PROBES)
    if report["checked_markets"] != expected or report["analyzed_markets"] != expected:
        raise SystemExit(
            f"Germany Xetra basket incomplete: {report['analyzed_markets']}/{expected}; "
            "inspect the per-symbol JSON statuses"
        )


if __name__ == "__main__":
    main()
