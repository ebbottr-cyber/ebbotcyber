# -*- coding: utf-8 -*-
"""Read-only German Xetra Yahoo smoke: one SAP.DE symbol, EUR, completed session.

No broker API, SQL writes, trade orders, AI model calls or personal account data.
The single ticker cannot establish entire exchange coverage or live tradeability.
"""
from __future__ import annotations

import argparse
from datetime import date, datetime
import json
from pathlib import Path
from zoneinfo import ZoneInfo

from src.services.six_market_live_smoke import MarketProbe, probe_six_markets


GERMANY_PROBES = (MarketProbe("de", "SAP.DE", "SAP.DE", "EUR"),)


def probe_germany_xetra(*, as_of: date, **kwargs) -> dict:
    return probe_six_markets(
        as_of=as_of,
        probes=GERMANY_PROBES,
        scope="germany_xetra_yahoo_one_symbol",
        **kwargs,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Read-only one-symbol Yahoo Xetra/EUR diagnostic")
    parser.add_argument(
        "--as-of", type=date.fromisoformat,
        default=datetime.now(ZoneInfo("Europe/Berlin")).date(),
    )
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    report = probe_germany_xetra(as_of=args.as_of)
    report["note"] = (
        "Xetra one-symbol read-only historical provider/technical probe only; "
        "not full market coverage, Midas account permissions, realtime prices or trades."
    )
    output = json.dumps(report, indent=2, ensure_ascii=False) + "\n"
    if args.output:
        args.output.write_text(output, encoding="utf-8")
    print(output, end="")
    if report["checked_markets"] != 1 or report["analyzed_markets"] != 1:
        raise SystemExit("Germany Xetra Yahoo smoke incomplete; inspect report and stderr")


if __name__ == "__main__":
    main()
