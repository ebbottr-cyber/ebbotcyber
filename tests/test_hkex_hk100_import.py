# -*- coding: utf-8 -*-
"""Offline synthetic HKEX Equity workbook tests: no real licensed stock data."""
import csv
from datetime import date
from html import escape
import json
from pathlib import Path
from zipfile import ZipFile

import pytest

from src.services.hkex_hk100_import import convert_hkex_equities
from src.services.four_market_universe_plan import _load_foreign_roster

AS_OF = date(2026, 11, 16)
HEADER = ["Stock Code", "Stock Name", "Category", "Currency"]


def _rows():
    rows = [[str(i), f"Synthetic company {i}", "Equity", "HKD"]
            for i in range(1, 106)]
    rows += [
        ["2800", "ETF", "ETP", "HKD"],
        ["4800", "Warrant", "Warrant", "HKD"],
        ["7800", "SPAC Equity", "Equity", "HKD"],
        ["80001", "Dual RMB Equity", "Equity", "CNY"],
        ["8000", "GEM Equity", "Equity", "HKD"],
    ]
    return rows


def _csv(tmp_path: Path, rows=None):
    path = tmp_path / "ListOfSecurities.csv"
    with path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.writer(stream)
        writer.writerow(["HKEX Official List of Securities"])
        writer.writerow(HEADER)
        writer.writerows(_rows() if rows is None else rows)
    return path


def _xlsx(tmp_path: Path, rows=None):
    path = tmp_path / "ListOfSecurities.xlsx"
    records = [["HKEX Official List of Securities"], HEADER] + (
        _rows() if rows is None else rows
    )
    with ZipFile(path, "w") as archive:
        cells = []
        for row_idx, values in enumerate(records, 1):
            parts = []
            for col_idx, value in enumerate(values):
                col = chr(ord("A") + col_idx)
                parts.append(
                    f'<c r="{col}{row_idx}" t="inlineStr">'
                    f'<is><t>{escape(value)}</t></is></c>'
                )
            cells.append(f'<row r="{row_idx}">{"".join(parts)}</row>')
        body = "".join(cells)
        xml = (
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
            f'<sheetData>{body}</sheetData></worksheet>'
        )
        archive.writestr("xl/worksheets/sheet1.xml", xml)
    return path


@pytest.mark.parametrize("kind", ["csv", "xlsx"])
def test_hkex_official_equity_category_selects_100_without_etps_or_spac(tmp_path, kind):
    path = _csv(tmp_path) if kind == "csv" else _xlsx(tmp_path)
    result = convert_hkex_equities(path, as_of=AS_OF)
    assert result["market"] == "hk"
    assert result["as_of"] == "2026-11-16"
    assert result["eligible_equities_in_source"] == 105
    assert len(result["symbols"]) == len(set(result["symbols"])) == 100
    assert result["symbols"][0] == "HK00001"
    assert result["symbols"][-1] == "HK00100"
    assert "HK02800" not in result["symbols"]
    assert "HK07800" not in result["symbols"]


def test_hkex_file_is_compatible_with_four_market_report_builder(tmp_path):
    out = convert_hkex_equities(_xlsx(tmp_path), as_of=AS_OF)
    file = tmp_path / "hk.json"
    file.write_text(json.dumps(out), encoding="utf-8")
    roster = _load_foreign_roster("hk", file, as_of=AS_OF)
    assert roster.market == "hk"
    assert len(roster.symbols) == 100


def test_missing_equity_category_never_guess_instrument_type(tmp_path):
    rows = [[str(i), "Company", "ETF", "HKD"] for i in range(1, 101)]
    with pytest.raises(ValueError, match="Only 0"):
        convert_hkex_equities(_csv(tmp_path, rows=rows), as_of=AS_OF)


def test_bad_source_headers_rejected_even_when_100_numeric_codes(tmp_path):
    target = tmp_path / "ListOfSecurities.csv"
    with target.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.writer(stream)
        writer.writerow(["Stock Code", "Stock Name"])
        writer.writerows([[i, "Example"] for i in range(1, 101)])
    with pytest.raises(ValueError, match="Category"):
        convert_hkex_equities(target, as_of=AS_OF)


def test_hkex_rejects_japan_codes_and_no_non_equity_fallback(tmp_path):
    rows = _rows()
    rows[0][0] = "7203.T"
    result = convert_hkex_equities(_csv(tmp_path, rows=rows), as_of=AS_OF)
    assert "7203.T" not in result["symbols"]
    assert result["symbols"][0] == "HK00002"


def test_oversized_or_invalid_xlsx_rejected(tmp_path):
    large = tmp_path / "ListOfSecurities.xlsx"
    large.write_bytes(b"X" * 8_000_001)
    with pytest.raises(ValueError, match="8 MB"):
        convert_hkex_equities(large, as_of=AS_OF)
    large.write_text("not an XLSX", encoding="utf-8")
    with pytest.raises(ValueError, match="decode"):
        convert_hkex_equities(large, as_of=AS_OF)
