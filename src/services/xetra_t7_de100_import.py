# -*- coding: utf-8 -*-
"""Read-only, local Deutsche Boerse T7 XETR share CSV -> source-dated DE100.

The full T7 export (semicolon-delimited, Market/Date metadata on first two
lines) is an exchange reference, NOT an index constituent/priority list.
Choose the first 100 distinct eligible German-issued equities by canonical
Xetra mnemonic alphabetically. This is a deterministic candidate set, not
market-cap ranking, validated Yahoo histories or broker tradability.

No web fetching, broker keys, SQLite writes or order placement.
Do not redistribute proprietary raw exchange exports.
"""
from __future__ import annotations

import argparse
import csv
from datetime import date, datetime, timedelta
import json
from pathlib import Path
import re

from src.services.five_market_sample_validation import build_custom_probes

SOURCE_URL = (
    "https://www.cashmarket.deutsche-boerse.com/cash-en/trading/"
    "Tradable-Instruments-Xetra/Downloads/xetra-downloads"
)
MAX_FILE_BYTES = 5_000_000
MAX_SOURCE_AGE_DAYS = 45
_REQUIRED = {
    "Instrument Status", "Instrument", "ISIN", "Mnemonic",
    "MIC Code", "Settlement Currency", "Instrument Type",
}
_GERMAN_ISIN = re.compile(r"DE[A-Z0-9]{10}\Z")
_MNEMONIC = re.compile(r"[A-Z][A-Z0-9]{0,7}\Z")


def _metadata_date(line: str) -> date:
    match = re.fullmatch(
        r"Date Last Update\s*:\s*;?\s*(\d{2})\.(\d{2})\.(\d{4})",
        line.strip(),
        flags=re.IGNORECASE,
    )
    if not match:
        raise ValueError("Xetra T7 metadata must include a dd.mm.yyyy source date")
    day, month, year = map(int, match.groups())
    try:
        return date(year, month, day)
    except ValueError as exc:
        raise ValueError("Invalid Xetra reference data date") from exc


def convert_xetra_t7_csv(path: Path, *, as_of: date) -> dict:
    if not path.is_file() or not 0 < path.stat().st_size <= MAX_FILE_BYTES:
        raise ValueError("Xetra T7 CSV missing or exceeds 5 MB")
    try:
        with path.open("r", encoding="utf-8-sig", newline="") as stream:
            market_line = stream.readline().strip()
            date_line = stream.readline().strip()
            if not re.fullmatch(r"Market\s*:\s*;?\s*XETR", market_line, flags=re.IGNORECASE):
                raise ValueError("Not a production XETR market reference file")
            source_date = _metadata_date(date_line)
            if source_date > as_of or as_of - source_date > timedelta(days=MAX_SOURCE_AGE_DAYS):
                raise ValueError("Xetra reference data is stale or future dated")
            reader = csv.DictReader(stream, delimiter=";")
            if not reader.fieldnames or not _REQUIRED.issubset(
                {name.strip() for name in reader.fieldnames if name}
            ):
                raise ValueError("Missing required Xetra instrument reference columns")
            # Unknown fields are permitted, but required column names must be exact.
            if len(set(reader.fieldnames)) != len(reader.fieldnames):
                raise ValueError("Duplicate Xetra CSV headers")
            if not _REQUIRED.issubset(reader.fieldnames):
                raise ValueError("Unsupported Xetra header whitespace/format")
            eligible: dict[str, str] = {}
            count = 0
            for row in reader:
                if None in row:
                    raise ValueError("Malformed Xetra CSV row")
                if row["Instrument Type"].strip().upper() != "CS":
                    continue
                if row["Instrument Status"].strip().upper() != "ACTIVE":
                    continue
                if "Product Status" in row and row["Product Status"].strip().upper() != "ACTIVE":
                    continue
                if "Market Segment Status" in row and row["Market Segment Status"].strip().upper() != "ACTIVE":
                    continue
                if row["MIC Code"].strip().upper() != "XETR":
                    continue
                if row["Settlement Currency"].strip().upper() != "EUR":
                    continue
                isin = row["ISIN"].strip().upper()
                if not _GERMAN_ISIN.fullmatch(isin):
                    continue
                mnemonic = row["Mnemonic"].strip().upper()
                if not _MNEMONIC.fullmatch(mnemonic):
                    continue
                previous_isin = eligible.get(mnemonic)
                if previous_isin is not None and previous_isin != isin:
                    raise ValueError("Xetra mnemonic belongs to more than one ISIN")
                eligible[mnemonic] = isin
                count += 1
    except (OSError, UnicodeError, csv.Error) as exc:
        raise ValueError("Cannot decode local Xetra reference CSV") from exc
    if len(eligible) < 100:
        raise ValueError(f"Only {len(eligible)} active German-ISIN Xetra equity symbols")
    symbols = tuple(f"{code}.DE" for code in sorted(eligible)[:100])
    if len(build_custom_probes(symbols)) != 100:
        raise ValueError("Operational Xetra symbol conversion mismatch")
    return {
        "market": "de",
        "as_of": source_date.isoformat(),
        "source_name": (
            "Deutsche Boerse XETR T7 CSV: first 100 active DE-ISIN "
            "CS mnemonic candidates (operator download)"
        ),
        "source_url": SOURCE_URL,
        "symbols": list(symbols),
        "selection_method": "german_isin_active_equity_mnemonic_alphabetic",
        "eligible_equities_in_source": len(eligible),
        "note": (
            "Exchange-listed share candidates, NOT DAX100 composition, market-cap "
            "ranking, Yahoo availability or any broker's trading permission."
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Source-dated XETR T7 100 German-ISIN equities (read-only)"
    )
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--as-of", type=date.fromisoformat, default=date.today())
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        result = convert_xetra_t7_csv(args.input, as_of=args.as_of)
    except ValueError as exc:
        parser.error(str(exc))
    args.output.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Candidate DE100 source roster ready: {len(result['symbols'])} / "
          f"{result['eligible_equities_in_source']} eligible Xetra rows. "
          "No live Yahoo data or broker permissions verified.")


if __name__ == "__main__":
    main()
