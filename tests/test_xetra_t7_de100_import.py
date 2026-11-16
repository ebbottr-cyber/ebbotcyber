# -*- coding: utf-8 -*-
"""Synthetic T7 CSV only; never commit or claim source memberships as real."""
import csv
from datetime import date
import json
from pathlib import Path

import pytest

from src.services.xetra_t7_de100_import import convert_xetra_t7_csv
from src.services.four_market_universe_plan import _load_foreign_roster

AS_OF = date(2026, 11, 16)


def _records():
    rows = []
    for n in range(105):
        code = "A" + chr(65 + n // 26) + chr(65 + n % 26)
        rows.append([
            "Active", "Active", "Synthetic German equity", f"DE{n:010d}",
            code, "XETR", "EUR", "CS",
        ])
    rows.extend([
        ["Active", "Active", "ETF", "DE0000000001", "ETFA", "XETR", "EUR", "ETF"],
        ["Active", "Active", "US-listed issuer", "US0000000001", "USA", "XETR", "EUR", "CS"],
        ["Active", "Active", "Frankfurt", "DE0000000002", "FRA", "XFRA", "EUR", "CS"],
        ["Published", "Active", "Pending", "DE0000000003", "PUB", "XETR", "EUR", "CS"],
        ["Active", "Pending deletion", "Delisted", "DE0000000004", "DEL", "XETR", "EUR", "CS"],
        ["Active", "Active", "USD", "DE0000000005", "USD", "XETR", "USD", "CS"],
        ["Active", "Active", "Numeric mnemonic", "DE0000000006", "1U1", "XETR", "EUR", "CS"],
    ])
    return rows


def _csv(tmp_path: Path, *, market="Market: XETR",
         updated="Date Last Update: 14.11.2026", records=None):
    target = tmp_path / "t7-xetr-allTradableInstruments.csv"
    with target.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.writer(stream, delimiter=";")
        writer.writerow([market])
        writer.writerow([updated])
        writer.writerow([
            "Product Status", "Instrument Status", "Instrument", "ISIN",
            "Mnemonic", "MIC Code", "Settlement Currency", "Instrument Type",
        ])
        writer.writerows(_records() if records is None else records)
    return target


def test_xetra_100_candidates_are_active_german_isin_equities_only(tmp_path):
    data = convert_xetra_t7_csv(_csv(tmp_path), as_of=AS_OF)
    assert data["market"] == "de"
    assert data["as_of"] == "2026-11-14"
    assert data["eligible_equities_in_source"] == 105
    assert len(data["symbols"]) == len(set(data["symbols"])) == 100
    assert all(x.endswith(".DE") for x in data["symbols"])
    assert "ETFA.DE" not in data["symbols"]
    assert "USA.DE" not in data["symbols"]
    assert data["selection_method"] == "german_isin_active_equity_mnemonic_alphabetic"


def test_xetra_output_is_compatible_with_existing_four_market_roster(tmp_path):
    data = convert_xetra_t7_csv(_csv(tmp_path), as_of=AS_OF)
    file = tmp_path / "de.json"
    file.write_text(json.dumps(data), encoding="utf-8")
    validated = _load_foreign_roster("de", file, as_of=AS_OF)
    assert validated.market == "de"
    assert len(validated.symbols) == 100


@pytest.mark.parametrize("market,updated", [
    ("Market: XFRA", "Date Last Update: 14.11.2026"),
    ("Market: XETR", "Date Last Update: 01.01.2026"),
    ("Market: XETR", "Date Last Update: 31.12.2026"),
    ("Market: XETR", "Date Last Update: unknown"),
])
def test_xetra_wrong_market_or_stale_reference_is_rejected(tmp_path, market, updated):
    with pytest.raises(ValueError):
        convert_xetra_t7_csv(_csv(tmp_path, market=market, updated=updated), as_of=AS_OF)


def test_xetra_fewer_than_100_real_equity_rows_fails(tmp_path):
    with pytest.raises(ValueError, match="Only 99"):
        convert_xetra_t7_csv(_csv(tmp_path, records=_records()[:99]), as_of=AS_OF)


def test_xetra_mnemonic_collision_different_isin_is_rejected(tmp_path):
    records = _records()
    collision = records[0].copy()
    collision[3] = "DE1234567890"
    records.append(collision)
    with pytest.raises(ValueError, match="more than one ISIN"):
        convert_xetra_t7_csv(_csv(tmp_path, records=records), as_of=AS_OF)
