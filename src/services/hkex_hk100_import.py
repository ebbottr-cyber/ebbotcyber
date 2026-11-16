# -*- coding: utf-8 -*-
"""Locally import official HKEX ListOfSecurities.xlsx -> 100 HK equity candidates.

Parses the public workbook's Equity category without accepting unrelated
warrants, funds, debt, REITs, SPACs or RMB dual-counters. Takes the first
100 *by numeric stock code*, NOT a liquidity or market-cap ranking.

All reading is local, with a bounded stdlib ZIP/XML parser (no workbook macros,
external links or downloads). Workbook snapshot date is operator supplied:
this importer cannot independently attest the publisher's update timestamp.
No live Yahoo quotes, broker access, SQLite writes or trade orders.
"""
from __future__ import annotations

import argparse
import csv
from datetime import date
import io
import json
from pathlib import Path
import re
from xml.etree import ElementTree as ET
from zipfile import BadZipFile, ZipFile

from src.services.five_market_sample_validation import build_custom_probes

SOURCE_URL = "https://www.hkex.com.hk/eng/services/trading/securities/securitieslists/ListOfSecurities.xlsx"
_MAX_FILE_BYTES = 8_000_000
_MAX_EXPANDED_BYTES = 35_000_000
_CELL_NS = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
_CANDIDATE_HEADERS = ("Stock Code", "Category")


def _read_csv(path: Path) -> list[list[str]]:
    try:
        with path.open("r", encoding="utf-8-sig", newline="") as stream:
            return list(csv.reader(stream))
    except (UnicodeError, OSError, csv.Error) as exc:
        raise ValueError("Could not parse HKEX-exported CSV") from exc


def _read_xlsx(path: Path) -> list[list[str]]:
    try:
        with ZipFile(path) as book:
            members = {item.filename: item for item in book.infolist()}
            if any(item.file_size > _MAX_EXPANDED_BYTES for item in members.values()) or sum(
                item.file_size for item in members.values()
            ) > _MAX_EXPANDED_BYTES:
                raise ValueError("HKEX workbook expanded size exceeds limit")
            for required in ("xl/worksheets/sheet1.xml",):
                if required not in members:
                    raise ValueError("Unsupported HKEX workbook sheet layout")
            shared: list[str] = []
            if "xl/sharedStrings.xml" in members:
                root = ET.fromstring(book.read("xl/sharedStrings.xml"))
                shared = [
                    "".join(node.itertext())
                    for node in root.findall(f"{_CELL_NS}si")
                ]
                if len(shared) > 100_000:
                    raise ValueError("HKEX workbook has excessive shared strings")
            root = ET.fromstring(book.read("xl/worksheets/sheet1.xml"))
            rows: list[list[str]] = []
            for row in root.findall(f".//{_CELL_NS}sheetData/{_CELL_NS}row"):
                cells: dict[int, str] = {}
                for cell in row.findall(f"{_CELL_NS}c"):
                    address = cell.get("r", "")
                    match = re.match(r"([A-Z]{1,3})\d+$", address)
                    if not match:
                        continue
                    column = 0
                    for ch in match.group(1):
                        column = column * 26 + ord(ch) - ord("A") + 1
                    column -= 1
                    if column > 40:
                        continue
                    value = cell.find(f"{_CELL_NS}v")
                    inline = cell.find(f"{_CELL_NS}is")
                    if cell.get("t") == "s" and value is not None:
                        index = int(value.text or "-1")
                        if index < 0 or index >= len(shared):
                            raise ValueError("Invalid shared string cell")
                        cells[column] = shared[index]
                    elif cell.get("t") == "inlineStr" and inline is not None:
                        cells[column] = "".join(inline.itertext())
                    elif value is not None:
                        cells[column] = value.text or ""
                if cells:
                    rows.append([cells.get(i, "") for i in range(max(cells) + 1)])
                if len(rows) > 15000:
                    raise ValueError("Excessive HKEX workbook rows")
            return rows
    except (OSError, BadZipFile, ET.ParseError, IndexError, KeyError) as exc:
        raise ValueError("Could not decode HKEX official workbook") from exc


def _normalize_header(value: str) -> str:
    return re.sub(r"\s+", " ", value.strip()).casefold()


def convert_hkex_equities(path: Path, *, as_of: date) -> dict:
    if not path.is_file() or not 0 < path.stat().st_size <= _MAX_FILE_BYTES:
        raise ValueError("HKEX source file missing or exceeds 8 MB")
    if path.suffix.lower() == ".xlsx":
        rows = _read_xlsx(path)
    elif path.suffix.lower() == ".csv":
        rows = _read_csv(path)
    else:
        raise ValueError("Use HKEX ListOfSecurities.xlsx or its CSV export")
    found: tuple[int, dict[str, int]] | None = None
    for i, row in enumerate(rows[:40]):
        labels = {_normalize_header(v): idx for idx, v in enumerate(row)}
        if all(k.casefold() in labels for k in _CANDIDATE_HEADERS):
            found = (i, labels)
            break
    if found is None:
        raise ValueError("HKEX table must contain Stock Code and Category columns")
    header_i, headers = found
    code_column, category_column = headers["stock code"], headers["category"]
    currency_column = headers.get("currency")
    codes: set[int] = set()
    for row in rows[header_i + 1:]:
        raw_code = row[code_column].strip() if len(row) > code_column else ""
        category = row[category_column].strip() if len(row) > category_column else ""
        if category.casefold() != "equity":
            continue
        if not re.fullmatch(r"\d{1,5}", raw_code):
            continue
        numeric = int(raw_code)
        # Exclude HKEX SPAC shares (7800..7999), dual RMB (80000+),
        # out-of-scope GEM (8000..8999), and other non-main-board ranges.
        if not 1 <= numeric <= 9999 or 7800 <= numeric <= 8999:
            continue
        if currency_column is not None and len(row) > currency_column and (
            row[currency_column].strip().upper() not in {"HKD", ""}
        ):
            continue
        codes.add(numeric)
    if len(codes) < 100:
        raise ValueError(f"Only {len(codes)} eligible HKEX equity codes; 100 required")
    symbols = tuple(f"HK{n:05d}" for n in sorted(codes)[:100])
    if len(build_custom_probes(symbols)) != 100:
        raise ValueError("HKEX canonical symbol conversion failed")
    return {
        "market": "hk",
        "as_of": as_of.isoformat(),
        "source_name": (
            "HKEX official Equity list: first 100 eligible stock codes "
            "(operator-dated local workbook)"
        ),
        "source_url": SOURCE_URL,
        "symbols": list(symbols),
        "selection_method": "equity_category_first_100_by_stock_code",
        "eligible_equities_in_source": len(codes),
        "note": (
            "Local snapshot source date is asserted by operator, not inferred "
            "from Excel metadata; no Yahoo-history or broker-trading proof."
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="HKEX official workbook local read-only 100 Equity candidates")
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--as-of", type=date.fromisoformat, required=True,
                        help="Operator-confirmed date when official HKEX workbook was downloaded")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        result = convert_hkex_equities(args.input, as_of=args.as_of)
    except ValueError as exc:
        parser.error(str(exc))
    args.output.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print("HKEX 100-source candidate codes selected from an operator-supplied "
          "Equity workbook. No live quote or trading validation.")


if __name__ == "__main__":
    main()
