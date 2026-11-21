"""Offline, fail-closed evidence audit for EBBot's four selected equity markets.

This is an inventory/dated OHLCV *evidence* audit, not a market-data provider,
exchange-membership certification, trading signal, or release approval.
No network, account, SQLite, scheduler, paper fill or order is touched.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from datetime import date, datetime, timezone
import csv
import io
import hashlib
import json
import math
from pathlib import Path
import re
import sys
from typing import Any, Iterable

MARKETS = ("tr", "us", "de", "hk")
SYMBOL = re.compile(r"^[A-Za-z0-9.^_-]{1,64}$")
CURRENCY = re.compile(r"^[A-Z]{3}$")
MAX_INPUT_BYTES = 64 * 1024 * 1024
DEFAULT_INDEX = Path(__file__).resolve().parents[1] / "apps/dsa-web/public/stocks.index.json"
DEFAULT_XETRA = Path(__file__).resolve().parents[1] / "data/market_snapshots/de/xetra-candidates.csv"
XETRA_SHA256 = "9e19abebcc9bbf956111fbf54c380978377407d7fcb43c1a8d064b370aaa9c6a"


class AuditInputError(ValueError):
    """Invalid or untrustworthy input: reject, never silently skip."""


def read_safe(path: Path) -> str:
    if path.is_symlink() or not path.is_file() or path.stat().st_size > MAX_INPUT_BYTES:
        raise AuditInputError("missing_unsafe_or_oversized_input")
    return path.read_text(encoding="utf-8-sig")


def rows_from_csv(path: Path, required: set[str]) -> Iterable[dict[str, str]]:
    reader = csv.DictReader(io.StringIO(read_safe(path)))
    if not reader.fieldnames or not required.issubset(reader.fieldnames):
        raise AuditInputError("missing_required_csv_columns")
    for index, row in enumerate(reader, 2):
        if None in row or any(v is None for v in row.values()):
            raise AuditInputError(f"malformed_csv_row_{index}")
        if any(str(v).strip() for v in row.values()):
            yield row


def canonical(market: Any, symbol: Any) -> tuple[str, str]:
    if not isinstance(market, str) or market not in MARKETS:
        raise AuditInputError("unsupported_market")
    if not isinstance(symbol, str) or not SYMBOL.fullmatch(symbol):
        raise AuditInputError("invalid_equity_symbol")
    return market, symbol.upper()


def parse_day(value: str) -> date:
    try:
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
            raise ValueError()
        return date.fromisoformat(value)
    except (ValueError, TypeError) as exc:
        raise AuditInputError("invalid_iso_session_date") from exc


def positive_number(value: str, *, allow_zero: bool = False) -> float:
    try:
        number = float(value)
    except (ValueError, TypeError) as exc:
        raise AuditInputError("invalid_ohlcv_number") from exc
    if not math.isfinite(number) or (number < 0 if allow_zero else number <= 0):
        raise AuditInputError("invalid_ohlcv_number")
    return number


def inventory(
    index_path: Path, stock_files: Iterable[Path], today: date, max_source_age: int
) -> tuple[dict[tuple[str, str], dict[str, Any]], dict[str, int]]:
    try:
        items = json.loads(read_safe(index_path))
    except json.JSONDecodeError as exc:
        raise AuditInputError("invalid_stock_index_json") from exc
    if not isinstance(items, list):
        raise AuditInputError("invalid_stock_index")
    candidates: dict[tuple[str, str], dict[str, Any]] = {}
    diagnostics = Counter()
    for item in items:
        if not isinstance(item, list) or len(item) < 9 or type(item[8]) is not bool:
            raise AuditInputError("malformed_stock_index_row")
        if not item[8]:
            diagnostics["inactive_index_rows"] += 1
            continue
        if item[7] == "index":
            diagnostics["benchmark_index_rows"] += 1
            continue
        if item[7] not in ("stock", "etf"):
            raise AuditInputError("unsupported_index_instrument_kind")
        # The bundled legacy stocks.index.json uses uppercase market tags
        # (US/HK/CN/JP/KR/BSE), unlike normalized CSV manifests (us/hk/etc.).
        # Convert the tag without altering the original index or its symbols.
        if not isinstance(item[6], str):
            raise AuditInputError("invalid_index_market_tag")
        indexed_market = item[6].strip().lower()
        if indexed_market not in MARKETS:
            diagnostics["out_of_scope_active_rows"] += 1
            continue
        key = canonical(indexed_market, item[0])
        if key in candidates:
            diagnostics["duplicate_index_rows"] += 1
        else:
            candidates[key] = {"kind": item[7], "dated_source": False, "source": "legacy_index"}
    for path in stock_files:
        for row in rows_from_csv(Path(path), {"market", "symbol", "source"}):
            key = canonical(row["market"], row["symbol"])
            kind = row.get("kind") or "stock"
            if kind not in ("stock", "etf"):
                raise AuditInputError("invalid_stock_manifest_kind")
            if not row["source"].strip():
                raise AuditInputError("missing_stock_manifest_source")
            if row.get("active", "").lower() == "false":
                diagnostics["inactive_manifest_rows"] += 1
                continue
            stamp = row.get("source_as_of_date", "").strip()
            dated = bool(stamp)
            if dated:
                source_day = parse_day(stamp)
                if source_day > today:
                    raise AuditInputError("future_inventory_source")
                if (today - source_day).days > max_source_age:
                    diagnostics["stale_inventory_rows"] += 1
            else:
                diagnostics["undated_manifest_rows"] += 1
            if key in candidates:
                if candidates[key]["kind"] != kind:
                    raise AuditInputError("conflicting_instrument_kind")
                diagnostics["duplicates_reconciled"] += 1
                if dated:
                    candidates[key].update(dated_source=True, source=row["source"])
            else:
                candidates[key] = {"kind": kind, "dated_source": dated, "source": row["source"]}
    return candidates, dict(diagnostics)


def ohlcv_evidence(
    bar_files: Iterable[Path], candidates: dict[tuple[str, str], dict[str, Any]], today: date
) -> dict[tuple[str, str], dict[str, Any]]:
    evidence: dict[tuple[str, str], dict[str, Any]] = {}
    for path in bar_files:
        required = {"market", "symbol", "session", "open", "high", "low",
                    "close", "volume", "source", "currency"}
        for row in rows_from_csv(Path(path), required):
            key = canonical(row["market"], row["symbol"])
            if key not in candidates:
                raise AuditInputError("ohlcv_symbol_not_in_inventory")
            stamp = parse_day(row["session"])
            if stamp > today:
                raise AuditInputError("future_ohlcv_session")
            if not row["source"].strip() or not CURRENCY.fullmatch(row["currency"]):
                raise AuditInputError("missing_or_invalid_ohlcv_provenance")
            op = positive_number(row["open"])
            hi = positive_number(row["high"])
            lo = positive_number(row["low"])
            cl = positive_number(row["close"])
            vol = positive_number(row["volume"], allow_zero=True)
            if lo > min(op, cl, hi) or hi < max(op, cl, lo):
                raise AuditInputError("inconsistent_ohlcv_candle")
            item = evidence.setdefault(key, {"sessions": set(), "last": None, "zero_volume": 0,
                                             "sources": set(), "currencies": set()})
            if stamp in item["sessions"]:
                raise AuditInputError("duplicate_ohlcv_session")
            item["sessions"].add(stamp)
            item["last"] = max(stamp, item["last"]) if item["last"] else stamp
            item["zero_volume"] += int(vol == 0)
            item["sources"].add(row["source"])
            item["currencies"].add(row["currency"])
    return evidence


def audit(
    index_path: Path, stock_files: Iterable[Path] = (), bar_files: Iterable[Path] = (),
    *, as_of: date | None = None, min_bars: int = 250, max_age_days: int = 7
) -> dict[str, Any]:
    if min_bars < 1 or max_age_days < 0:
        raise AuditInputError("invalid_threshold")
    today = as_of or datetime.now(timezone.utc).date()
    stock_files = list(stock_files)
    stored_xetra_loaded = False
    # Reuse the dated official-derived Xetra *candidate* manifest from PR #59,
    # but only when auditing the real bundled repository index (not fixtures).
    if index_path.resolve() == DEFAULT_INDEX.resolve() and DEFAULT_XETRA.is_file():
        snapshot = read_safe(DEFAULT_XETRA)
        if hashlib.sha256(snapshot.encode("utf-8")).hexdigest() != XETRA_SHA256:
            raise AuditInputError("stored_xetra_snapshot_checksum_mismatch")
        if not any(path.resolve() == DEFAULT_XETRA.resolve() for path in stock_files):
            stock_files.append(DEFAULT_XETRA)
        stored_xetra_loaded = True
    candidates, diagnostics = inventory(index_path, stock_files, today, max_age_days)
    bars = ohlcv_evidence(bar_files, candidates, today)
    result: dict[str, Any] = {}
    for market in MARKETS:
        keys = sorted(k for k in candidates if k[0] == market)
        missing = [s for m, s in keys if (m, s) not in bars]
        insufficient = [s for m, s in keys if (m, s) in bars
                        and len(bars[m, s]["sessions"]) < min_bars]
        stale = [s for m, s in keys if (m, s) in bars
                 and (today - bars[m, s]["last"]).days > max_age_days]
        undated = [s for m, s in keys if not candidates[m, s]["dated_source"]]
        recent_enough = sum((m, s) in bars and (today - bars[m, s]["last"]).days <= max_age_days
                            for m, s in keys)
        long_enough = sum((m, s) in bars and len(bars[m, s]["sessions"]) >= min_bars
                          for m, s in keys)
        result[market] = {
            "candidate_instruments": len(keys),
            "stocks": sum(candidates[k]["kind"] == "stock" for k in keys),
            "etfs": sum(candidates[k]["kind"] == "etf" for k in keys),
            "with_any_ohlcv": len(keys) - len(missing),
            "with_min_bars": long_enough,
            "with_recent_bar": recent_enough,
            "undated_inventory_count": len(undated),
            "missing_ohlcv_count": len(missing),
            "insufficient_history_count": len(insufficient),
            "stale_ohlcv_count": len(stale),
            "missing_symbols": missing,
            "insufficient_symbols": insufficient,
            "stale_symbols": stale,
            "undated_inventory_symbols": undated,
            "zero_volume_bar_count": sum(bars[k]["zero_volume"] for k in keys if k in bars),
        }
    missing_markets = [m for m in MARKETS if not result[m]["candidate_instruments"]]
    has_full_evidence = not missing_markets and all(
        not result[m]["missing_ohlcv_count"]
        and not result[m]["insufficient_history_count"]
        and not result[m]["stale_ohlcv_count"]
        and not result[m]["undated_inventory_count"]
        for m in MARKETS
    )
    return {
        "status": ("REVIEW_ONLY_NEEDS_INDEPENDENT_VALIDATION" if has_full_evidence
                   else "BLOCKED_INCOMPLETE_EVIDENCE"),
        "as_of_utc_date": today.isoformat(),
        "selected_markets": list(MARKETS),
        "stored_xetra_manifest_loaded": stored_xetra_loaded,
        "stored_xetra_as_of": "2026-11-19" if stored_xetra_loaded else None,
        "min_ohlcv_bars_per_symbol": min_bars,
        "max_age_calendar_days": max_age_days,
        "markets_without_inventory": missing_markets,
        "inventory_diagnostics": diagnostics,
        "markets": result,
        "total_candidate_instruments": sum(r["candidate_instruments"] for r in result.values()),
        "full_exchange_listing_coverage_verified": False,
        "exchange_session_gap_completeness_verified": False,
        "provider_symbol_mapping_verified": False,
        "market_data_license_verified": False,
        "turkish_broker_access_verified": False,
        "real_time_quotes_verified": False,
        "paper_trading_enabled": False,
        "live_trading_enabled": False,
        "network_requests": 0,
        "orders": 0,
    }


def summary(report: dict[str, Any]) -> dict[str, Any]:
    """Bound stdout size; --report-json retains every missing symbol, no Top-N filter."""
    compact = dict(report)
    compact["markets"] = {}
    for market, data in report["markets"].items():
        compact["markets"][market] = {
            k: (v[:10] if k.endswith("_symbols") else v)
            for k, v in data.items()
        }
    compact["stdout_symbol_lists_are_samples_only"] = True
    compact["full_counts_are_not_truncated"] = True
    return compact


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="EBBot four-market offline OHLCV evidence audit")
    p.add_argument("--index", type=Path, default=DEFAULT_INDEX)
    p.add_argument("--stocks", type=Path, action="append", default=[],
                   help="Repeat for dated BIST/Xetra or other source-labelled inventory CSV")
    p.add_argument("--bars", type=Path, action="append", default=[],
                   help="Repeat for real daily OHLCV CSV (never synthesized)")
    p.add_argument("--as-of", type=str, help="UTC audit date YYYY-MM-DD (test/replay only)")
    p.add_argument("--min-bars", type=int, default=250)
    p.add_argument("--max-age-days", type=int, default=7)
    p.add_argument("--report-json", type=Path, help="New file with ALL missing symbols")
    p.add_argument("--strict", action="store_true",
                   help="Fail closed unless independently verifiable production readiness")
    return p


def run(args: argparse.Namespace) -> int:
    try:
        report = audit(args.index, args.stocks, args.bars,
                       as_of=parse_day(args.as_of) if args.as_of else None,
                       min_bars=args.min_bars, max_age_days=args.max_age_days)
        if args.report_json:
            target = args.report_json
            if target.is_symlink() or not target.parent.is_dir() or target.parent.is_symlink():
                raise AuditInputError("unsafe_report_output")
            with target.open("x", encoding="utf-8") as handle:
                json.dump(report, handle, ensure_ascii=False, sort_keys=True, allow_nan=False)
                handle.write("\n")
        print(json.dumps(summary(report), ensure_ascii=True, sort_keys=True, allow_nan=False))
        # Even a complete CSV is not proof of exchange coverage/licensing/broker rights.
        return 2 if args.strict else 0
    except (AuditInputError, OSError, UnicodeError, json.JSONDecodeError) as exc:
        print(json.dumps({
            "status": "BLOCKED_INVALID_INPUT", "reason": str(exc),
            "network_requests": 0, "orders": 0,
            "paper_trading_enabled": False, "live_trading_enabled": False,
        }, ensure_ascii=True, sort_keys=True))
        return 1


if __name__ == "__main__":
    sys.exit(run(parser().parse_args()))
