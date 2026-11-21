"""BIST equity identity reconciliation from *operator-supplied* reference CSVs.

A KAP member directory is not a stock-exchange tradeable securities roster.
An operator-labelled exchange list is not independently authenticated here.
An ISIN check digit only validates syntax, not listing status or data rights.

This is offline, read-only, fail-closed evidence processing. It does not request
market data, install providers, approve license rights, or execute any trades.
"""
from __future__ import annotations

import argparse
from datetime import date, datetime, timezone
import json
from pathlib import Path
import re
import sys
from typing import Any

from scripts.audit_ebbot_market_data_coverage import (
    AuditInputError, canonical, ohlcv_evidence, parse_day, rows_from_csv,
)
from scripts.audit_ebbot_equity_session_gaps import _mapping

BIST_SYMBOL = re.compile(r"^[A-Z0-9]{3,8}\.IS$")
ISIN_PATTERN = re.compile(r"^[A-Z]{2}[A-Z0-9]{9}[0-9]$")
STATUS = frozenset({"active", "halted", "delisted"})
MAX_SOURCE_AGE_DAYS = 7


def isin_check_digit_valid(code: str) -> bool:
    """Check ISO 6166 / Luhn without mistaking validation for identification."""
    if not isinstance(code, str) or not ISIN_PATTERN.fullmatch(code):
        return False
    digits = "".join(str(ord(ch) - 55) if "A" <= ch <= "Z" else ch for ch in code)
    result = 0
    for i, char in enumerate(reversed(digits)):
        n = int(char)
        if i % 2:
            n *= 2
        result += n // 10 + n % 10
    return result % 10 == 0


def bist_symbol(market: Any, symbol: Any) -> str:
    key = canonical(market, symbol)
    if key[0] != "tr" or not BIST_SYMBOL.fullmatch(key[1]):
        raise AuditInputError("invalid_bist_equity_symbol")
    return key[1]


def source_day(row: dict[str, str], *, now: date) -> date:
    dated = row.get("source_as_of_date", "").strip()
    timestamp = row.get("observed_at_utc", "").strip()
    if not dated and not timestamp:
        raise AuditInputError("undated_bist_reference_row")
    if dated:
        stamped = parse_day(dated)
    else:
        # Previous PR #58 KAP exports use observed_at_utc, not source_as_of_date.
        try:
            dt = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
        except ValueError as exc:
            raise AuditInputError("invalid_kap_observation_timestamp") from exc
        if dt.tzinfo is None or dt.utcoffset() is None:
            raise AuditInputError("kap_timestamp_missing_timezone")
        stamped = dt.astimezone(timezone.utc).date()
    if dated and timestamp:
        try:
            dt = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
        except ValueError as exc:
            raise AuditInputError("invalid_kap_observation_timestamp") from exc
        if dt.tzinfo is None or dt.utcoffset() is None:
            raise AuditInputError("kap_timestamp_missing_timezone")
        if dt.astimezone(timezone.utc).date() != stamped:
            raise AuditInputError("conflicting_kap_reference_dates")
    if stamped > now:
        raise AuditInputError("future_bist_reference")
    return stamped


def _kap_rows(path: Path, now: date, max_age: int) -> tuple[dict[str, date], int]:
    records: dict[str, date] = {}
    stale = 0
    for row in rows_from_csv(path, {"market", "symbol", "source"}):
        symbol = bist_symbol(row["market"], row["symbol"])
        if not row["source"].strip():
            raise AuditInputError("missing_kap_source")
        if row.get("kind", "stock") != "stock":
            raise AuditInputError("kap_non_equity_in_stock_directory")
        when = source_day(row, now=now)
        stale += (now - when).days > max_age
        if symbol in records:
            raise AuditInputError("duplicate_kap_equity_code")
        records[symbol] = when
    if not records:
        raise AuditInputError("empty_kap_company_directory")
    return records, stale


def _exchange_rows(path: Path, now: date, max_age: int) -> tuple[dict[str, dict[str, str]], int]:
    required = {"market", "symbol", "isin", "mic", "listing_status", "source", "source_as_of_date"}
    records: dict[str, dict[str, str]] = {}
    isins: set[str] = set()
    stale = 0
    for row in rows_from_csv(path, required):
        symbol = bist_symbol(row["market"], row["symbol"])
        when = source_day(row, now=now)
        stale += (now - when).days > max_age
        isin = row["isin"]
        if not isin_check_digit_valid(isin):
            raise AuditInputError("invalid_bist_reference_isin")
        if row["mic"] != "XIST":
            raise AuditInputError("wrong_bist_exchange_mic")
        status = row["listing_status"]
        if status not in STATUS:
            raise AuditInputError("invalid_bist_listing_status")
        if not row["source"].strip():
            raise AuditInputError("missing_bist_exchange_reference_source")
        if symbol in records:
            raise AuditInputError("duplicate_exchange_symbol")
        if isin in isins:
            raise AuditInputError("duplicate_exchange_isin")
        isins.add(isin)
        records[symbol] = {"isin": isin, "status": status, "date": when.isoformat()}
    if not records:
        raise AuditInputError("empty_bist_exchange_reference")
    return records, stale


def _blocked(reason: str, today: date) -> dict[str, Any]:
    return {
        "status": "BLOCKED_MISSING_BIST_SOURCE_FILES",
        "reason": reason,
        "as_of_utc_date": today.isoformat(),
        "kap_candidate_count": None,
        "exchange_active_count": None,
        "matched_active_kap_exchange_count": None,
        "counts_unknown_not_zero": True,
        "independent_listing_authentication_verified": False,
        "isin_to_security_identity_verified": False,
        "price_provider_license_verified": False,
        "provider_symbol_mapping_independently_verified": False,
        "live_ohlcv_loaded": False,
        "paper_trading_enabled": False,
        "live_trading_enabled": False,
        "network_requests": 0,
        "orders": 0,
    }


def reconcile_bist(
    *,
    kap: Path | None = None,
    exchange: Path | None = None,
    provider_mapping: Path | None = None,
    bars: Path | None = None,
    as_of: date | None = None,
    max_source_age_days: int = MAX_SOURCE_AGE_DAYS,
) -> dict[str, Any]:
    """Compare operator-supplied, dated company and exchange security snapshots.

    Details contain candidate symbols but NO raw private OHLCV prices.
    Missing reference files result in unknown counts, not invented zeroes.
    """
    today = as_of or datetime.now(timezone.utc).date()
    if not 0 <= max_source_age_days <= 365:
        raise AuditInputError("invalid_bist_source_age_limit")
    if kap is None or exchange is None:
        return _blocked("kap_and_bist_reference_files_required", today)
    kap_rows, old_kap = _kap_rows(Path(kap), today, max_source_age_days)
    exchange_rows, old_exchange = _exchange_rows(Path(exchange), today, max_source_age_days)
    union_symbols = set(kap_rows) | set(exchange_rows)
    universe = {("tr", symbol): {"kind": "stock"} for symbol in union_symbols}
    mapping, map_diag = _mapping(
        [Path(provider_mapping)] if provider_mapping is not None else [],
        universe, as_of=today, max_age_days=max_source_age_days,
    )
    bar_evidence = ohlcv_evidence([Path(bars)] if bars is not None else [], universe, today)
    active = {s for s, row in exchange_rows.items() if row["status"] == "active"}
    nonactive = {s for s, row in exchange_rows.items() if row["status"] != "active"}
    kap_symbols = set(kap_rows)
    listed = set(exchange_rows)
    kap_only = sorted(kap_symbols - listed)
    exchange_only = sorted(listed - kap_symbols)
    common_active = sorted(kap_symbols & active)
    active_unmapped = sorted(s for s in active if ("tr", s) not in mapping)
    active_without_input_price = sorted(s for s in active if ("tr", s) not in bar_evidence)
    provider_map_missing = provider_mapping is None
    price_input_missing = bars is None
    old_mapping = map_diag.get("stale_provider_mapping_rows", 0)
    status = (
        "BLOCKED_STALE_OR_INCOMPLETE_BIST_REFERENCES"
        if old_kap or old_exchange or old_mapping or kap_only or exchange_only
        or active_unmapped or provider_map_missing or price_input_missing
        else "REVIEW_ONLY_NEEDS_INDEPENDENT_BIST_CONFIRMATION"
    )
    return {
        "status": status,
        "as_of_utc_date": today.isoformat(),
        "kap_candidate_count": len(kap_symbols),
        "exchange_reference_count": len(listed),
        "exchange_active_count": len(active),
        "exchange_halted_or_delisted_count": len(nonactive),
        "matched_kap_exchange_count": len(kap_symbols & listed),
        "matched_active_kap_exchange_count": len(common_active),
        "kap_not_in_exchange_count": len(kap_only),
        "exchange_not_in_kap_count": len(exchange_only),
        "active_without_declared_provider_mapping_count": len(active_unmapped),
        "active_with_ohlcv_in_supplied_file_count": (
            len(active) - len(active_without_input_price) if bars is not None else None
        ),
        "active_without_ohlcv_in_supplied_file_count": (
            len(active_without_input_price) if bars is not None else None
        ),
        "stale_kap_reference_rows": old_kap,
        "stale_exchange_reference_rows": old_exchange,
        "stale_provider_mapping_rows": old_mapping,
        "provider_mapping_file_supplied": not provider_map_missing,
        "ohlcv_file_supplied": not price_input_missing,
        "candidate_symbol_details": {
            "kap_only": kap_only,
            "exchange_only": exchange_only,
            "halted_or_delisted": sorted(nonactive),
            "active_without_provider_mapping": active_unmapped,
            "active_without_input_ohlcv": (
                active_without_input_price if bars is not None else None
            ),
        },
        "counts_are_input_reconciliation_only": True,
        "independent_listing_authentication_verified": False,
        "isin_to_security_identity_verified": False,
        "price_provider_license_verified": False,
        "provider_symbol_mapping_independently_verified": False,
        "live_ohlcv_loaded": False,
        "paper_trading_enabled": False,
        "live_trading_enabled": False,
        "network_requests": 0,
        "orders": 0,
    }


def compact(report: dict[str, Any]) -> dict[str, Any]:
    """Keep stdout bounded; an explicit private JSON keeps every candidate code."""
    reduced = dict(report)
    details = report.get("candidate_symbol_details")
    if isinstance(details, dict):
        reduced["candidate_symbol_details"] = {
            name: (values[:10] if isinstance(values, list) else None)
            for name, values in details.items()
        }
        reduced["stdout_candidate_lists_are_samples_only"] = True
    return reduced


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Offline BIST KAP-vs-XIST and provider-symbol audit")
    p.add_argument("--kap", type=Path, help="Local dated KAP company directory CSV")
    p.add_argument("--exchange", type=Path, help="Local dated operator-reviewed BIST XIST security CSV")
    p.add_argument("--mapping", type=Path, help="Optional provider-to-stock symbol map CSV")
    p.add_argument("--bars", type=Path, help="Optional actual OHLCV CSV, NEVER generated by this script")
    p.add_argument("--max-source-age-days", type=int, default=MAX_SOURCE_AGE_DAYS)
    p.add_argument("--as-of", type=str, help="UTC date for reproducible offline audit")
    p.add_argument("--report-json", type=Path, help="New local complete candidate-reconciliation report")
    return p


def run(args: argparse.Namespace) -> int:
    try:
        report = reconcile_bist(
            kap=args.kap, exchange=args.exchange, provider_mapping=args.mapping,
            bars=args.bars, as_of=parse_day(args.as_of) if args.as_of else None,
            max_source_age_days=args.max_source_age_days,
        )
        if args.report_json:
            path = args.report_json
            if not path.is_absolute() or path.is_symlink() or not path.parent.is_dir() or path.parent.is_symlink():
                raise AuditInputError("unsafe_bist_audit_output")
            with path.open("x", encoding="utf-8") as handle:
                json.dump(report, handle, sort_keys=True, ensure_ascii=False, allow_nan=False)
                handle.write("\n")
        print(json.dumps(compact(report), sort_keys=True, ensure_ascii=True, allow_nan=False))
        # 0: report generated; not evidence of licensed price rights or approval.
        return 0
    except (AuditInputError, OSError, UnicodeError, ValueError, TypeError) as exc:
        reason = str(exc) if isinstance(exc, AuditInputError) else "bist_reference_io_failure"
        print(json.dumps({
            "status": "BLOCKED_INVALID_BIST_REFERENCE",
            "reason": reason,
            "network_requests": 0,
            "orders": 0,
            "paper_trading_enabled": False,
            "live_trading_enabled": False,
        }, sort_keys=True))
        return 1


if __name__ == "__main__":
    sys.exit(run(parser().parse_args()))
