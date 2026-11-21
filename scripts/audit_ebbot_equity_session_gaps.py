"""Fail-closed offline four-market session/identity evidence diagnostics.

An operator supplies a real session calendar and (optionally) provider mappings.
A declared session is NOT proof that an individual security traded that day:
IPO date, delisting, suspension and corporate actions require separate review.
Neither provider rights nor ticker mappings are verified by CSV strings.
There are no network calls, trading operations or persistent state changes.
"""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import date, datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import sys
from typing import Any, Iterable

from scripts.audit_ebbot_market_data_coverage import (
    AuditInputError,
    DEFAULT_INDEX,
    DEFAULT_XETRA,
    MARKETS,
    XETRA_SHA256,
    canonical,
    inventory,
    ohlcv_evidence,
    parse_day,
    read_safe,
    rows_from_csv,
)

PROVIDER_SYMBOL = re.compile(r"^[A-Za-z0-9_.:^/-]{1,64}$")
PROVIDER_NAME = re.compile(r"^[A-Za-z0-9_.-]{1,64}$")
MAX_LOOKBACK_SESSIONS = 60


def _stock_files(index_path: Path, extras: Iterable[Path]) -> tuple[list[Path], bool]:
    paths = [Path(path) for path in extras]
    imported = False
    if index_path.resolve() == DEFAULT_INDEX.resolve() and DEFAULT_XETRA.is_file():
        raw = read_safe(DEFAULT_XETRA)
        if hashlib.sha256(raw.encode("utf-8")).hexdigest() != XETRA_SHA256:
            raise AuditInputError("xetra_candidate_checksum_mismatch")
        if not any(p.resolve() == DEFAULT_XETRA.resolve() for p in paths):
            paths.append(DEFAULT_XETRA)
        imported = True
    return paths, imported


def _calendar(
    paths: Iterable[Path], *, as_of: date, max_age_days: int
) -> tuple[dict[str, list[date]], dict[str, Any]]:
    sessions: dict[str, dict[date, str]] = {m: {} for m in MARKETS}
    sources = {m: set() for m in MARKETS}
    diag = Counter()
    for path in paths:
        for row in rows_from_csv(
            Path(path), {"market", "session", "source", "source_as_of_date"}
        ):
            market = row["market"]
            if market not in MARKETS:
                raise AuditInputError("invalid_calendar_market")
            session = parse_day(row["session"])
            observed = parse_day(row["source_as_of_date"])
            if not row["source"].strip():
                raise AuditInputError("missing_calendar_source")
            if session > as_of or observed > as_of:
                raise AuditInputError("future_calendar_evidence")
            if session > observed:
                raise AuditInputError("calendar_source_predates_session")
            if session in sessions[market]:
                raise AuditInputError("duplicate_calendar_session")
            sessions[market][session] = row["source"]
            sources[market].add(row["source"])
            if (as_of - observed).days > max_age_days:
                diag[f"{market}_stale_calendar_rows"] += 1
    return (
        {market: sorted(items) for market, items in sessions.items()},
        {
            "calendar_row_diagnostics": dict(diag),
            "declared_sources_by_market": {
                market: sorted(sources[market]) for market in MARKETS
            },
        },
    )


def _mapping(
    paths: Iterable[Path],
    universe: dict[tuple[str, str], dict[str, Any]],
    *,
    as_of: date,
    max_age_days: int,
) -> tuple[dict[tuple[str, str], dict[str, str]], dict[str, int]]:
    mappings: dict[tuple[str, str], dict[str, str]] = {}
    provider_tickers: dict[tuple[str, str, str], tuple[str, str]] = {}
    diag = Counter()
    for path in paths:
        for row in rows_from_csv(
            Path(path),
            {"market", "symbol", "provider", "provider_symbol",
             "source", "source_as_of_date"},
        ):
            key = canonical(row["market"], row["symbol"])
            if key not in universe:
                raise AuditInputError("mapping_symbol_missing_from_inventory")
            provider = row["provider"]
            ticker = row["provider_symbol"]
            if not PROVIDER_NAME.fullmatch(provider) or not PROVIDER_SYMBOL.fullmatch(ticker):
                raise AuditInputError("invalid_provider_identity")
            if not row["source"].strip():
                raise AuditInputError("missing_mapping_provenance")
            when = parse_day(row["source_as_of_date"])
            if when > as_of:
                raise AuditInputError("future_provider_mapping")
            if (as_of - when).days > max_age_days:
                diag["stale_provider_mapping_rows"] += 1
            if key in mappings:
                raise AuditInputError("duplicate_or_ambiguous_provider_mapping")
            collision_key = (key[0], provider, ticker.upper())
            if collision_key in provider_tickers:
                raise AuditInputError("provider_symbol_collides_across_equities")
            provider_tickers[collision_key] = key
            mappings[key] = {
                "provider": provider,
                "provider_symbol": ticker,
                "source_as_of_date": when.isoformat(),
            }
    return mappings, dict(diag)


def _verify_bar_identity(
    bar_files: Iterable[Path],
    mappings: dict[tuple[str, str], dict[str, str]],
) -> dict[str, int]:
    matched = 0
    unresolved = 0
    # Optional provider metadata is checked only when an explicit map is present.
    # No populated CSV grants real API access or independently proves an ISIN.
    for path in bar_files:
        for row in rows_from_csv(Path(path), {"market", "symbol", "session", "source"}):
            key = canonical(row["market"], row["symbol"])
            mapping = mappings.get(key)
            if mapping is None:
                unresolved += 1
                continue
            name = row.get("provider", "")
            ticker = row.get("provider_symbol", "")
            if not name or not ticker:
                unresolved += 1
                continue
            if name != mapping["provider"] or ticker.upper() != mapping["provider_symbol"].upper():
                raise AuditInputError("bar_provider_symbol_mapping_mismatch")
            matched += 1
    return {"bar_rows_matching_declared_map": matched,
            "bar_rows_without_identity_evidence": unresolved}


def session_gap_audit(
    *,
    index_path: Path = DEFAULT_INDEX,
    stocks: Iterable[Path] = (),
    bars: Iterable[Path] = (),
    calendars: Iterable[Path] = (),
    mappings: Iterable[Path] = (),
    as_of: date | None = None,
    max_age_days: int = 7,
    lookback_sessions: int = 20,
) -> dict[str, Any]:
    if not 1 <= lookback_sessions <= MAX_LOOKBACK_SESSIONS or not 0 <= max_age_days <= 365:
        raise AuditInputError("invalid_session_audit_threshold")
    now = as_of or datetime.now(timezone.utc).date()
    stock_files, xetra_loaded = _stock_files(Path(index_path), stocks)
    universe, inventory_diag = inventory(Path(index_path), stock_files, now, max_age_days)
    bar_files = [Path(p) for p in bars]
    evidence = ohlcv_evidence(bar_files, universe, now)
    sessions, calendar_diag = _calendar(calendars, as_of=now, max_age_days=max_age_days)
    identity, mapping_diag = _mapping(mappings, universe, as_of=now, max_age_days=max_age_days)
    bars_identity = _verify_bar_identity(bar_files, identity)
    result: dict[str, Any] = {}
    full_gaps: dict[str, dict[str, list[str]]] = {}
    for market in MARKETS:
        keys = sorted(k for k in universe if k[0] == market)
        dates = sessions[market][-lookback_sessions:]
        dates_set = set(dates)
        first = dates[0] if dates else None
        last = dates[-1] if dates else None
        mismatched_days = 0
        if first and last:
            for key in keys:
                for day in evidence.get(key, {}).get("sessions", ()):
                    if first <= day <= last and day not in dates_set:
                        mismatched_days += 1
        # A non-session bar inside the calendar's covered period is ambiguous
        # (bad bar OR omitted official session). Never silently label it valid.
        if mismatched_days:
            raise AuditInputError("ohlcv_date_not_in_declared_calendar")
        per_symbol: dict[str, list[str]] = {}
        slots = 0
        with_bars = 0
        for key in keys:
            observed = evidence.get(key, {}).get("sessions", set())
            with_bars += bool(observed)
            if dates:
                missing = [day.isoformat() for day in dates if day not in observed]
                if missing:
                    per_symbol[key[1]] = missing
                    slots += len(missing)
        full_gaps[market] = per_symbol
        map_count = sum(key in identity for key in keys)
        result[market] = {
            "candidate_symbols": len(keys),
            "symbols_with_any_ohlcv": with_bars,
            "symbols_without_ohlcv": len(keys) - with_bars,
            "declared_recent_market_sessions": len(dates),
            "declared_session_first": first.isoformat() if first else None,
            "declared_session_last": last.isoformat() if last else None,
            "declared_provider_mappings": map_count,
            "provider_mapping_missing_count": len(keys) - map_count,
            "symbols_with_potential_session_gaps": len(per_symbol) if dates else None,
            "potential_missing_symbol_session_slots": slots if dates else None,
            "sample_potential_gaps": [
                {"symbol": symbol, "sessions": missed}
                for symbol, missed in list(per_symbol.items())[:10]
            ],
        }
    return {
        "status": "BLOCKED_REQUIRES_INDEPENDENT_MARKET_DATA_VALIDATION",
        "as_of_utc_date": now.isoformat(),
        "markets": result,
        "selected_markets": list(MARKETS),
        "lookback_sessions": lookback_sessions,
        "markets_without_calendar": [
            market for market in MARKETS if not sessions[market]
        ],
        "calendar_diagnostics": calendar_diag,
        "mapping_diagnostics": mapping_diag,
        "inventory_diagnostics": inventory_diag,
        "bar_identity_diagnostics": bars_identity,
        "stored_xetra_candidates_loaded": xetra_loaded,
        "full_symbol_gap_details": full_gaps,
        "market_calendar_completeness_verified": False,
        "security_listing_and_trading_status_verified": False,
        "provider_symbol_mapping_independently_verified": False,
        "licensed_ohlcv_verified": False,
        "paper_trading_enabled": False,
        "live_trading_enabled": False,
        "network_requests": 0,
        "orders": 0,
    }


def compact(report: dict[str, Any]) -> dict[str, Any]:
    result = dict(report)
    result.pop("full_symbol_gap_details", None)
    result["stdout_gap_lists_are_samples_only"] = True
    return result


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="EBBot offline calendar and provider-symbol gap diagnostics")
    p.add_argument("--index", type=Path, default=DEFAULT_INDEX)
    p.add_argument("--stocks", type=Path, action="append", default=[])
    p.add_argument("--bars", type=Path, action="append", default=[])
    p.add_argument("--calendar", type=Path, action="append", default=[])
    p.add_argument("--mapping", type=Path, action="append", default=[])
    p.add_argument("--as-of", type=str)
    p.add_argument("--lookback-sessions", type=int, default=20)
    p.add_argument("--max-age-days", type=int, default=7)
    p.add_argument("--report-json", type=Path,
                   help="Write all per-symbol potential session gaps to a NEW local file")
    return p


def run(args: argparse.Namespace) -> int:
    try:
        result = session_gap_audit(
            index_path=args.index, stocks=args.stocks, bars=args.bars,
            calendars=args.calendar, mappings=args.mapping,
            as_of=parse_day(args.as_of) if args.as_of else None,
            max_age_days=args.max_age_days,
            lookback_sessions=args.lookback_sessions,
        )
        if args.report_json:
            output = args.report_json
            if output.is_symlink() or not output.parent.is_dir() or output.parent.is_symlink():
                raise AuditInputError("unsafe_output_location")
            with output.open("x", encoding="utf-8") as stream:
                json.dump(result, stream, ensure_ascii=False, sort_keys=True, allow_nan=False)
                stream.write("\n")
        print(json.dumps(compact(result), sort_keys=True, ensure_ascii=True, allow_nan=False))
        # 0 = diagnostic executed. No source is verified by running this CLI.
        return 0
    except (AuditInputError, OSError, UnicodeError, ValueError, TypeError) as exc:
        print(json.dumps({"status": "BLOCKED_INVALID_SESSION_DATA",
                          "reason": str(exc), "network_requests": 0,
                          "orders": 0, "paper_trading_enabled": False,
                          "live_trading_enabled": False}, sort_keys=True))
        return 1


if __name__ == "__main__":
    sys.exit(run(parser().parse_args()))
