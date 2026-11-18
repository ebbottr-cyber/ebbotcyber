"""Read-only four-market equity scope and strict manual Xetra CSV conversion.

Only TR, US, DE and HK are selectable in this reporting layer. A source
instrument is NOT evidence of broker access, usable Yahoo quotes or a trade.
"""
from __future__ import annotations

import csv
from datetime import date, datetime
from io import StringIO
from pathlib import Path
import re
from typing import Any, Iterable

from src.services.paper_universe_inventory import audit_universe, read_input

MARKETS = ("tr", "us", "de", "hk")
XETRA_SOURCE_URL = (
    "https://www.cashmarket.deutsche-boerse.com/resource/blob/1528/"
    "b52ea43a2edac92e8283d40645d1c076/data/t7-xetr-allTradableInstruments.csv"
)
_MNEMONIC = re.compile(r"^[A-Z0-9]{1,16}$")
_ISIN = re.compile(r"^[A-Z]{2}[A-Z0-9]{9}[0-9]$")
_REQUIRED = {
    "Product Status", "Instrument Status", "ISIN",
    "Mnemonic", "MIC Code", "Instrument Type",
}


def xetra_equities_to_manifest(raw: str, *, today: date | None = None) -> tuple[str, dict[str, Any]]:
    """Convert a dated XETR exchange CSV into candidate .DE shares (not quotes).

    Xetra's T7 reference format uses a market line, last-update line, and a
    semicolon-delimited header. CS means common stock; ETF/ETN/ETC and all
    non-Active records must NEVER be counted as shares.
    """
    if not isinstance(raw, str) or not raw or len(raw.encode("utf-8")) > 64 * 1024 * 1024:
        raise ValueError("invalid_or_oversized_xetra_csv")
    lines = raw.lstrip("\ufeff").splitlines()
    if len(lines) < 4 or lines[0].strip() != "Market: XETR":
        raise ValueError("wrong_xetra_market_or_format")
    date_match = re.fullmatch(r"Date Last Update:\s*(\d{2}\.\d{2}\.\d{4})", lines[1].strip())
    if not date_match:
        raise ValueError("missing_xetra_source_date")
    try:
        source_date = datetime.strptime(date_match.group(1), "%d.%m.%Y").date()
    except ValueError as exc:
        raise ValueError("invalid_xetra_source_date") from exc
    age = ((today or date.today()) - source_date).days
    if age < 0 or age > 7:
        raise ValueError("stale_or_future_xetra_source_date")

    reader = csv.DictReader(StringIO("\n".join(lines[2:])), delimiter=";")
    if not reader.fieldnames or not _REQUIRED.issubset(set(reader.fieldnames)):
        raise ValueError("invalid_xetra_columns")
    matches: dict[str, str] = {}
    total = excluded_inactive = excluded_non_equity = excluded_other_mic = excluded_invalid = duplicates = 0
    for row in reader:
        if None in row or any(value is None for value in row.values()):
            raise ValueError("malformed_xetra_row")
        if not any(value.strip() for value in row.values()):
            continue
        total += 1
        if row["MIC Code"].strip() != "XETR":
            excluded_other_mic += 1
            continue
        if row["Instrument Type"].strip() != "CS":
            excluded_non_equity += 1
            continue
        if row["Product Status"].strip() != "Active" or row["Instrument Status"].strip() != "Active":
            excluded_inactive += 1
            continue
        name = row["Mnemonic"].strip().upper()
        isin = row["ISIN"].strip().upper()
        if not _MNEMONIC.fullmatch(name) or not _ISIN.fullmatch(isin):
            excluded_invalid += 1
            continue
        if name in matches:
            if matches[name] != isin:
                raise ValueError("xetra_mnemonic_collision_requires_manual_mapping")
            duplicates += 1
            continue
        matches[name] = isin
    if not matches:
        raise ValueError("no_active_xetra_common_stocks")
    output = StringIO(newline="")
    writer = csv.writer(output, lineterminator="\n")
    writer.writerow(("market", "symbol", "source", "kind", "source_as_of_date", "isin", "price_symbol_verified"))
    for name, isin in sorted(matches.items()):
        writer.writerow(("de", name + ".DE", "deutsche_boerse_xetra_t7", "stock", source_date.isoformat(), isin, "false"))
    report = {
        "status": "XETRA_CANDIDATES_ONLY",
        "source_as_of_date": source_date.isoformat(),
        "source_age_days": age,
        "source_url": XETRA_SOURCE_URL,
        "total_rows": total,
        "included_common_stocks": len(matches),
        "excluded_non_equity": excluded_non_equity,
        "excluded_other_mic": excluded_other_mic,
        "excluded_inactive": excluded_inactive,
        "excluded_invalid_code_or_isin": excluded_invalid,
        "duplicates_deduplicated": duplicates,
        "yahoo_de_suffix_candidates_only": True,
        "price_symbols_verified": False,
        "broker_access_verified": False,
        "market_completeness_verified": False,
        "network_requests": 0,
        "orders": 0,
    }
    return output.getvalue(), report


def audit_four_market_equities(
    stock_index: Path, *, stock_manifests: Iterable[Path] = ()
) -> dict[str, Any]:
    """Scope existing offline candidate inventory without modifying it.

    The underlying worldwide index may contain China/Japan/Korea etc., but
    those markets are excluded from the four-market result and its totals.
    """
    raw = audit_universe(stock_index, stock_manifests=stock_manifests)
    counts = raw["stocks_by_market"]
    included = {market: counts.get(market, 0) for market in MARKETS}
    excluded = {market: count for market, count in counts.items() if market not in MARKETS}
    return {
        "status": "MISSING_MARKET_INVENTORIES" if any(not n for n in included.values()) else "CANDIDATES_ONLY",
        "selected_markets": list(MARKETS),
        "candidate_stocks_by_market": included,
        "selected_candidate_stock_count": sum(included.values()),
        "out_of_scope_stock_count_excluded": sum(excluded.values()),
        "out_of_scope_markets_excluded": sorted(excluded),
        "markets_without_candidates": [market for market, n in included.items() if not n],
        "index_records_excluded": raw["index_records_excluded_from_stocks"],
        "duplicates_deduplicated": raw["duplicates_deduplicated"],
        "fixed_top_n_cap": False,
        "full_exchange_coverage_verified": False,
        "source_freshness_verified": False,
        "price_symbols_verified": False,
        "broker_access_verified": False,
        "prices_loaded": False,
        "paper_trading_enabled": False,
        "live_trading_enabled": False,
        "network_requests": 0,
        "orders": 0,
        "journal_writes": 0,
    }
