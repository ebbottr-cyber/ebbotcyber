# -*- coding: utf-8 -*-
"""Synthetic-only offline tests for a locally downloaded issuer OEF CSV parser.

Fixtures are not actual holdings and must never be committed as real rosters.
"""
import csv
from datetime import date
from pathlib import Path

import pytest

from data_provider.yfinance_fetcher import YfinanceFetcher
from src.services.four_market_universe_plan import _load_foreign_roster
from src.services.ishares_oef_us100_import import convert_ishares_oef_csv

AS_OF = date(2026, 11, 16)
HEADER = [
    "Ticker", "Name", "Sector", "Asset Class", "Market Value",
    "Weight (%)", "Location", "Exchange", "Currency",
]


def _rows():
    symbols = [
        "U" + chr(65 + n // 26) + chr(65 + n % 26) for n in range(100)
    ]
    output = [
        [symbol, "Synthetic test only", "Industrials", "Equity",
         str(1000000 - i), "0.5", "United States",
         "NASDAQ" if i % 2 else "NYSE", "USD"]
        for i, symbol in enumerate(symbols)
    ]
    output.append(["BRK B", "Berkshire test", "Financials", "Equity",
                   "2000000", "2.5", "United States", "NYSE", "USD"])
    output.append(["ESZ6", "Index future test", "Derivatives", "Futures",
                   "999999999", "0", "-", "Index And Options Market", "USD"])
    output.append(["USD", "Cash", "Cash", "Cash", "999999999",
                   "0", "United States", "-", "USD"])
    output.append(["XTSLA", "Cash fund", "Cash", "Money Market", "999999999",
                   "0", "United States", "-", "USD"])
    return output


def _csv(tmp_path: Path, rows=None, *, date_text="Nov 13, 2026", title="iShares S&P 100 ETF"):
    location = tmp_path / "OEF.csv"
    with location.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.writer(f)
        writer.writerow([title])
        writer.writerow(["Fund Holdings as of", date_text])
        writer.writerow(["Inception Date", "Oct 23, 2000"])
        writer.writerow(["Shares Outstanding", "12,345"])
        writer.writerow(["Stock", "-"])
        writer.writerow(["Bond", "-"])
        writer.writerow(["Cash", "-"])
        writer.writerow(["Other", "-"])
        writer.writerow(HEADER)
        writer.writerows(_rows() if rows is None else rows)
        writer.writerow(["The content is protected by applicable rights."])
    return location


def test_offline_issuer_csv_selects_100_us_equities_excluding_cash_futures(tmp_path):
    roster = convert_ishares_oef_csv(_csv(tmp_path), as_of=AS_OF)
    assert roster["market"] == "us"
    assert roster["as_of"] == "2026-11-13"
    assert roster["eligible_equities_in_source"] == 101
    assert len(roster["symbols"]) == len(set(roster["symbols"])) == 100
    assert roster["symbols"][0] == "BRK.B"
    assert "XTSLA" not in roster["symbols"]
    assert "ESZ6" not in roster["symbols"]
    assert "USD" not in roster["symbols"]
    assert "U" + chr(65 + 99 // 26) + chr(65 + 99 % 26) not in roster["symbols"]


def test_source_dated_output_passes_foreign_roster_contract(tmp_path):
    import json
    candidate = convert_ishares_oef_csv(_csv(tmp_path), as_of=AS_OF)
    path = tmp_path / "us.json"
    path.write_text(json.dumps(candidate), encoding="utf-8")
    parsed = _load_foreign_roster("us", path, as_of=AS_OF)
    assert parsed.market == "us"
    assert len(parsed.symbols) == 100
    assert parsed.symbols[0] == "BRK.B"
    assert YfinanceFetcher()._convert_stock_code("BRK.B") == "BRK-B"


@pytest.mark.parametrize("changed", [
    {"date_text": "Sep 01, 2026"},
    {"date_text": "Nov 30, 2026"},
    {"title": "Other ETF"},
])
def test_wrong_or_stale_issuer_header_refused(tmp_path, changed):
    with pytest.raises(ValueError):
        convert_ishares_oef_csv(_csv(tmp_path, **changed), as_of=AS_OF)


def test_fewer_than_100_equities_fails_closed(tmp_path):
    with pytest.raises(ValueError, match="eligible US equities"):
        convert_ishares_oef_csv(_csv(tmp_path, rows=_rows()[:99]), as_of=AS_OF)


def test_invalid_ticker_duplicate_and_bad_us_exchange_fail(tmp_path):
    repeated = _rows()
    repeated[1][0] = repeated[0][0]
    with pytest.raises(ValueError, match="Repeated equity"):
        convert_ishares_oef_csv(_csv(tmp_path, rows=repeated), as_of=AS_OF)

    wrong = _rows()
    wrong[0][0] = "7203.T"
    with pytest.raises(ValueError, match="Unsupported issuer equity ticker"):
        convert_ishares_oef_csv(_csv(tmp_path, rows=wrong), as_of=AS_OF)

    all_nasdaq_to_otc = _rows()
    for row in all_nasdaq_to_otc:
        if row[3] == "Equity":
            row[7] = "OTC"
    with pytest.raises(ValueError, match="eligible US equities"):
        convert_ishares_oef_csv(_csv(tmp_path, rows=all_nasdaq_to_otc), as_of=AS_OF)
