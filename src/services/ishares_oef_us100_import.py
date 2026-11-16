# -*- coding: utf-8 -*-
"""Convert an operator-downloaded iShares OEF holdings CSV into a US100 roster.

Only a locally supplied CSV file is read; no web scraping, DB writes, account
connection or order placement. Do NOT commit/repost downloaded holdings:
BlackRock's CSV includes restrictions on copying and redistribution.

We choose exactly the 100 highest-market-value distinct eligible NYSE/NASDAQ
equity ticker rows from a DATED OEF file. OEF holds >100 positions including
non-equity assets; the selected 100 are a *watch universe*, NOT a guarantee
of exact S&P100 membership or eligibility at any specific broker.
"""
from __future__ import annotations

import argparse
import csv
from datetime import date, datetime, timedelta
import io
import json
import math
from pathlib import Path
import re

from src.services.five_market_sample_validation import build_custom_probes

SOURCE_URL = "https://www.ishares.com/us/products/239723/x/latest-holdings.csv"
_MAX_INPUT_BYTES = 2_000_000
_MAX_AGE_DAYS = 45
_REQUIRED = {
    "Ticker", "Name", "Sector", "Asset Class", "Market Value",
    "Location", "Exchange", "Currency",
}
_EXCHANGES = frozenset({"NASDAQ", "NYSE"})
_SOURCE_TICKER = re.compile(r"[A-Z]{1,5}(?:\.[A-Z])?\Z")


def _parse_date(line: list[str]) -> date:
    if len(line) != 2 or line[0].strip() != "Fund Holdings as of":
        raise ValueError("Expected issuer's 'Fund Holdings as of' header")
    try:
        return datetime.strptime(line[1], "%b %d, %Y").date()
    except ValueError as exc:
        raise ValueError("Invalid issuer holdings date") from exc


def _canonical_ticker(value: str) -> str:
    code = value.strip().upper()
    # BlackRock writes a space for Berkshire's NYSE class-B ticker.
    if code == "BRK B":
        code = "BRK.B"
    if not _SOURCE_TICKER.fullmatch(code):
        raise ValueError(f"Unsupported issuer equity ticker: {value!r}")
    return code


def convert_ishares_oef_csv(path: Path, *, as_of: date) -> dict:
    """Parse one known issuer CSV; retain only a dated 100-stock watchlist."""
    if not path.is_file() or not 0 < path.stat().st_size <= _MAX_INPUT_BYTES:
        raise ValueError("OEF CSV missing, empty or >2 MB")
    try:
        rows = list(csv.reader(io.StringIO(path.read_text(encoding="utf-8-sig"))))
    except (OSError, UnicodeError, csv.Error) as exc:
        raise ValueError("Cannot decode OEF CSV") from exc
    if not rows or not rows[0] or rows[0][0].strip() != "iShares S&P 100 ETF":
        raise ValueError("Not the official iShares S&P 100 ETF holdings format")
    if len(rows) < 10:
        raise ValueError("OEF CSV is incomplete")
    issued = _parse_date(rows[1])
    if issued > as_of or as_of - issued > timedelta(days=_MAX_AGE_DAYS):
        raise ValueError("OEF holdings snapshot is future-dated or >45 days old")
    header_i = next(
        (i for i, row in enumerate(rows) if "Ticker" in row and "Asset Class" in row),
        None,
    )
    if header_i is None:
        raise ValueError("OEF equity header is missing")
    header = rows[header_i]
    if len(set(header)) != len(header) or not _REQUIRED.issubset(header):
        raise ValueError("OEF holdings headers are missing or duplicated")
    positions = []
    seen: set[str] = set()
    for values in rows[header_i + 1:]:
        if len(values) != len(header):
            continue  # skip copyright/footer disclaimer lines, not equities
        row = dict(zip(header, values))
        if row["Asset Class"] != "Equity":
            continue
        if (
            row["Exchange"].strip().upper() not in _EXCHANGES
            or row["Location"].strip() != "United States"
            or row["Currency"].strip() != "USD"
        ):
            continue
        code = _canonical_ticker(row["Ticker"])
        if code in seen:
            raise ValueError(f"Repeated equity holding: {code}")
        seen.add(code)
        try:
            value = float(row["Market Value"].replace(",", ""))
        except ValueError as exc:
            raise ValueError("Invalid issuer equity market value") from exc
        if not math.isfinite(value) or value <= 0:
            raise ValueError("Non-positive equity market value")
        positions.append((value, code))
    if len(positions) < 100:
        raise ValueError(f"OEF file has only {len(positions)} eligible US equities, needs 100")
    positions.sort(key=lambda x: (-x[0], x[1]))
    symbols = tuple(code for _, code in positions[:100])
    if len(build_custom_probes(symbols)) != 100:
        raise ValueError("US100 operational routing validation failed")
    return {
        "market": "us",
        "as_of": issued.isoformat(),
        "source_name": "iShares OEF issuer holdings, top 100 US NYSE/NASDAQ equities by market value (operator-downloaded)",
        "source_url": SOURCE_URL,
        "symbols": list(symbols),
        "selection_method": "top_100_eligible_equity_market_value",
        "eligible_equities_in_source": len(positions),
        "note": (
            "US stock candidate watchlist from licensed issuer file; not an "
            "exact S&P100 member certification, live Yahoo check, or brokerage permission."
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Prepare US100 from a locally downloaded iShares OEF CSV (no web requests)"
    )
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--as-of", type=date.fromisoformat, default=date.today())
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        result = convert_ishares_oef_csv(args.input, as_of=args.as_of)
    except ValueError as exc:
        parser.error(str(exc))
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(
        f"US100 candidate list created locally: {len(result['symbols'])} "
        f"equities as of {result['as_of']}, from {result['eligible_equities_in_source']} eligible rows. "
        "No quotes/trades performed; do not re-distribute the licensed holdings list."
    )


if __name__ == "__main__":
    main()
