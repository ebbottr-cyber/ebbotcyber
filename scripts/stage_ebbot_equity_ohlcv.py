"""Manual-only local market-data staging with checksum and source identity gates.

Inputs are user-supplied CSV exports and an operator-provided source manifest.
No network, API keys, broker, scheduler, application DB, trading or auto-loading.
Staged output remains *untrusted evidence*, never a verified licensed feed.
"""
from __future__ import annotations

import argparse
import csv
from datetime import date, datetime, timezone
import hashlib
from io import StringIO
import json
from pathlib import Path
import re
import sys
from typing import Any, Iterable

from scripts.audit_ebbot_market_data_coverage import (
    AuditInputError, DEFAULT_INDEX, MARKETS, MAX_INPUT_BYTES, canonical,
    inventory, ohlcv_evidence, parse_day, read_safe, rows_from_csv,
)
from scripts.audit_ebbot_equity_session_gaps import _calendar, _mapping, _stock_files

REQUIRED_MANIFEST = frozenset({
    "schema_version", "market", "provider", "source", "currency",
    "source_as_of_date", "input_sha256", "license_review_reference",
})
IDENTIFIER = re.compile(r"^[A-Za-z0-9_.:-]{3,80}$")
CURRENCY_CODE = re.compile(r"^[A-Z]{3}$")
SHA = re.compile(r"^[a-f0-9]{64}$")
HEADERS = (
    "market", "symbol", "session", "open", "high", "low",
    "close", "volume", "source", "currency", "provider", "provider_symbol",
)
MAX_MANIFEST_BYTES = 16 * 1024


def manifest_from_file(path: Path, today: date, max_source_age_days: int) -> dict[str, Any]:
    if path.is_symlink() or not path.is_file() or path.stat().st_size > MAX_MANIFEST_BYTES:
        raise AuditInputError("missing_unsafe_or_oversized_provider_manifest")
    try:
        manifest = json.loads(read_safe(path))
    except json.JSONDecodeError as exc:
        raise AuditInputError("invalid_provider_manifest_json") from exc
    if not isinstance(manifest, dict) or set(manifest) != REQUIRED_MANIFEST:
        raise AuditInputError("incorrect_provider_manifest_schema")
    if type(manifest["schema_version"]) is not int or manifest["schema_version"] != 1:
        raise AuditInputError("unsupported_provider_manifest_version")
    if manifest["market"] not in MARKETS:
        raise AuditInputError("unsupported_provider_market")
    if any(
        not isinstance(manifest[field], str) or not IDENTIFIER.fullmatch(manifest[field])
        for field in ("provider", "source", "license_review_reference")
    ):
        raise AuditInputError("missing_or_unsafe_provider_provenance")
    if not isinstance(manifest["currency"], str) or not CURRENCY_CODE.fullmatch(manifest["currency"]):
        raise AuditInputError("invalid_provider_currency")
    if not isinstance(manifest["input_sha256"], str) or not SHA.fullmatch(manifest["input_sha256"]):
        raise AuditInputError("missing_or_invalid_input_checksum")
    when = parse_day(manifest["source_as_of_date"])
    if when > today:
        raise AuditInputError("future_provider_export_timestamp")
    if (today - when).days > max_source_age_days:
        raise AuditInputError("stale_provider_export_timestamp")
    return manifest


def stage_vendor_ohlcv(
    *,
    index: Path = DEFAULT_INDEX,
    stocks: Iterable[Path] = (),
    input_csv: Path,
    manifest_file: Path,
    mapping_file: Path,
    calendar_file: Path,
    output_csv: Path,
    as_of: date | None = None,
    max_source_age_days: int = 30,
) -> dict[str, Any]:
    """Validate everything before exclusive-create of a single local output file.

    Does not check actual contractual rights; the license reference is merely
    an operator-provided tracking code. Does not enable trading or ingest into
    any EBBot production database. Multiple input shards may be staged
    separately, then passed to existing --bars audits as separate CSVs.
    """
    if not 0 <= max_source_age_days <= 365:
        raise AuditInputError("invalid_source_age_limit")
    now = as_of or datetime.now(timezone.utc).date()
    manifest = manifest_from_file(Path(manifest_file), now, max_source_age_days)
    source = Path(input_csv)
    if source.is_symlink() or not source.is_file():
        raise AuditInputError("missing_or_unsafe_input_csv")
    if source.stat().st_size == 0 or source.stat().st_size > MAX_INPUT_BYTES:
        raise AuditInputError("empty_or_oversized_input_csv")
    if hashlib.sha256(source.read_bytes()).hexdigest() != manifest["input_sha256"]:
        raise AuditInputError("provider_export_checksum_mismatch")

    stocks, _ = _stock_files(Path(index), stocks)
    universe, _ = inventory(Path(index), stocks, now, max_source_age_days)
    mapping, mapping_diagnostics = _mapping(
        [Path(mapping_file)], universe, as_of=now, max_age_days=max_source_age_days,
    )
    if mapping_diagnostics.get("stale_provider_mapping_rows", 0):
        raise AuditInputError("stale_provider_symbol_mapping")
    calendars, diagnostics = _calendar(
        [Path(calendar_file)], as_of=now, max_age_days=max_source_age_days,
    )
    if diagnostics["calendar_row_diagnostics"]:
        raise AuditInputError("stale_operator_calendar")
    eligible = set(calendars[manifest["market"]])
    if not eligible:
        raise AuditInputError("missing_declared_provider_market_sessions")

    # The shared audit enforces stock inventory, OHLCV math and deduplicated
    # (market, ticker, session), zero/nonfinite values and chronological bounds.
    evidence = ohlcv_evidence([source], universe, now)
    if not evidence:
        raise AuditInputError("empty_verified_ohlcv_evidence")

    data = []
    for row in rows_from_csv(source, set(HEADERS)):
        key = canonical(row["market"], row["symbol"])
        if key[0] != manifest["market"]:
            raise AuditInputError("cross_market_provider_export")
        if row["currency"] != manifest["currency"]:
            raise AuditInputError("provider_currency_mismatch")
        if row["source"] != manifest["source"] or row["provider"] != manifest["provider"]:
            raise AuditInputError("provider_export_provenance_mismatch")
        expected = mapping.get(key)
        if expected is None:
            raise AuditInputError("missing_explicit_provider_symbol_mapping")
        if (
            expected["provider"] != row["provider"]
            or expected["provider_symbol"].upper() != row["provider_symbol"].upper()
        ):
            raise AuditInputError("provider_ticker_identity_mismatch")
        when = parse_day(row["session"])
        if when > parse_day(manifest["source_as_of_date"]):
            raise AuditInputError("ohlcv_session_after_source_export")
        if when not in eligible:
            raise AuditInputError("ohlcv_session_not_in_supplied_calendar")
        data.append({
            "market": key[0],
            "symbol": key[1],
            "session": when.isoformat(),
            "open": row["open"],
            "high": row["high"],
            "low": row["low"],
            "close": row["close"],
            "volume": row["volume"],
            "source": manifest["source"],
            "currency": manifest["currency"],
            "provider": manifest["provider"],
            "provider_symbol": expected["provider_symbol"],
        })
    data.sort(key=lambda row: (row["market"], row["symbol"], row["session"]))
    staging = StringIO(newline="")
    writer = csv.DictWriter(staging, fieldnames=HEADERS, lineterminator="\n")
    writer.writeheader()
    writer.writerows(data)
    output_bytes = staging.getvalue().encode("utf-8")
    if len(output_bytes) > MAX_INPUT_BYTES:
        raise AuditInputError("staged_csv_oversized_split_input_first")

    target = Path(output_csv)
    if not target.is_absolute() or target.is_symlink() or not target.parent.is_dir() or target.parent.is_symlink():
        raise AuditInputError("invalid_staged_output_location")
    with target.open("xb") as output:
        output.write(output_bytes)
    return {
        "status": "STAGED_REVIEW_ONLY_NOT_LICENSE_VERIFIED",
        "market": manifest["market"],
        "provider": manifest["provider"],
        "source_as_of_date": manifest["source_as_of_date"],
        "input_sha256_match": True,
        "staged_sha256": hashlib.sha256(output_bytes).hexdigest(),
        "staged_bar_count": len(data),
        "staged_symbol_count": len(evidence),
        "declared_calendar_sessions": len(eligible),
        "license_reference_present_not_verified": True,
        "license_verified": False,
        "provider_mapping_independently_verified": False,
        "market_calendar_independently_verified": False,
        "full_exchange_coverage_verified": False,
        "paper_trading_enabled": False,
        "live_trading_enabled": False,
        "network_requests": 0,
        "orders": 0,
    }


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Stage operator-provided OHLCV for audits only")
    p.add_argument("--index", type=Path, default=DEFAULT_INDEX)
    p.add_argument("--stocks", type=Path, action="append", default=[])
    p.add_argument("--input-csv", type=Path, required=True)
    p.add_argument("--manifest", type=Path, required=True)
    p.add_argument("--mapping", type=Path, required=True)
    p.add_argument("--calendar", type=Path, required=True)
    p.add_argument("--output-csv", type=Path, required=True)
    p.add_argument("--as-of", type=str, help="Replay/testing UTC date YYYY-MM-DD")
    p.add_argument("--max-source-age-days", type=int, default=30)
    return p


def run(args: argparse.Namespace) -> int:
    try:
        result = stage_vendor_ohlcv(
            index=args.index, stocks=args.stocks, input_csv=args.input_csv,
            manifest_file=args.manifest, mapping_file=args.mapping,
            calendar_file=args.calendar, output_csv=args.output_csv,
            as_of=parse_day(args.as_of) if args.as_of else None,
            max_source_age_days=args.max_source_age_days,
        )
        print(json.dumps(result, ensure_ascii=True, sort_keys=True))
        return 0
    except (AuditInputError, OSError, UnicodeError, ValueError, TypeError) as exc:
        # Do not echo file paths, provider secrets or raw CSV prices.
        reason = str(exc) if isinstance(exc, AuditInputError) else "file_or_encoding_failure"
        print(json.dumps({
            "status": "BLOCKED_INVALID_VENDOR_INPUT",
            "reason": reason,
            "network_requests": 0, "orders": 0,
            "paper_trading_enabled": False, "live_trading_enabled": False,
        }, sort_keys=True))
        return 1


if __name__ == "__main__":
    sys.exit(run(parser().parse_args()))
