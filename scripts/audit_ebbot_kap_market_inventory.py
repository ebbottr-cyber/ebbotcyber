"""Review-only BIST KAP market inventory staging; never infer broker/provider symbols.

The supplied CSV is an operator-normalized transcription of a dated official
source. A matching SHA-256 proves local byte integrity, NOT source authenticity.
No HTTP, market quotes, account changes or order APIs are used.
"""
from __future__ import annotations

import argparse
from collections import Counter
import csv
from datetime import date, datetime, timezone
import hashlib
import io
import json
from pathlib import Path
import re
import sys
from urllib.parse import urlsplit

MAX_BYTES = 16 * 1024 * 1024
CODE = re.compile(r"[A-Z0-9]{3,8}\Z")
HEX_SHA = re.compile(r"[a-f0-9]{64}\Z")
ISIN = re.compile(r"[A-Z]{2}[A-Z0-9]{9}[0-9]\Z")
MARKETS = {
    "YILDIZ PAZAR": "star",
    "ANA PAZAR": "main",
    "ALT PAZAR": "sub",
    "YAKIN İZLEME PAZARI": "watch",
    "PİYASA ÖNCESİ İŞLEM PLATFORMU": "pre_market",
    "YAPILANDIRILMIŞ ÜRÜNLER VE FON PAZARI": "structured_fund",
}
EQUITY_MARKETS = {"star", "main", "sub", "watch", "pre_market"}
COLUMNS = {"pazar", "kap_kodu", "unvan", "kaynak_tarihi"}


class KAPInputError(ValueError):
    """Ambiguous, inconsistent or untrusted inventory evidence."""


def parse_day(value: str) -> date:
    try:
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
            raise ValueError("expected ISO date")
        return date.fromisoformat(value)
    except (TypeError, ValueError) as error:
        raise KAPInputError("invalid_source_date") from error


def official_page(url: str) -> bool:
    p = urlsplit(url)
    return (p.scheme == "https" and p.netloc in {"kap.org.tr", "www.kap.org.tr"}
            and p.path == "/tr/Pazarlar" and not p.fragment
            and not p.username and not p.password)


def inspect(path: Path, expected_hash: str, page: str, snapshot_date: date,
            *, as_of: date | None = None, max_age_days: int = 7) -> dict:
    today = as_of or datetime.now(timezone.utc).date()
    if (not HEX_SHA.fullmatch(expected_hash) or not official_page(page)
            or snapshot_date > today or max_age_days < 0):
        raise KAPInputError("invalid_manifest_provenance")
    if path.is_symlink() or not path.is_file() or path.stat().st_size > MAX_BYTES:
        raise KAPInputError("missing_unsafe_or_oversized_source")
    source = path.read_bytes()
    if len(source) > MAX_BYTES or hashlib.sha256(source).hexdigest() != expected_hash:
        raise KAPInputError("source_sha256_mismatch")
    try:
        text = source.decode("utf-8-sig")
    except UnicodeError as error:
        raise KAPInputError("source_not_utf8") from error
    reader = csv.DictReader(io.StringIO(text))
    if (not reader.fieldnames or len(reader.fieldnames) != len(set(reader.fieldnames))
            or not COLUMNS.issubset(reader.fieldnames)
            or set(reader.fieldnames) - (COLUMNS | {"isin"})):
        raise KAPInputError("invalid_csv_columns")

    seen: set[str] = set()
    groups = Counter()
    codes: dict[str, list[str]] = {group: [] for group in MARKETS.values()}
    with_isin = 0
    for line, row in enumerate(reader, 2):
        if not any((value or "").strip() for value in row.values() if value is not None):
            continue
        if None in row or any(value is None for value in row.values()):
            raise KAPInputError(f"malformed_row_{line}")
        market = MARKETS.get(row["pazar"].strip())
        code = row["kap_kodu"].strip()
        name = row["unvan"].strip()
        if not market:
            raise KAPInputError(f"unknown_market_{line}")
        if not CODE.fullmatch(code) or code in seen:
            raise KAPInputError(f"invalid_or_duplicate_kap_code_{line}")
        if not name or len(name) > 250 or name[0] in "=+-@" or any(ord(ch) < 32 for ch in name):
            raise KAPInputError(f"invalid_company_title_{line}")
        if parse_day(row["kaynak_tarihi"].strip()) != snapshot_date:
            raise KAPInputError(f"mixed_source_dates_{line}")
        isin = row.get("isin", "").strip()
        if isin and not ISIN.fullmatch(isin):
            raise KAPInputError(f"invalid_isin_format_{line}")
        with_isin += bool(isin)
        seen.add(code)
        groups[market] += 1
        codes[market].append(code)
    if not seen:
        raise KAPInputError("empty_market_inventory")

    for group in codes:
        codes[group].sort()
    eligible = sorted(code for group in EQUITY_MARKETS for code in codes[group])
    return {
        "schema_version": 1,
        "status": ("BLOCKED_STALE_KAP_SNAPSHOT"
                   if (today - snapshot_date).days > max_age_days
                   else "REVIEW_ONLY_UNMAPPED_KAP_CODES"),
        "source_page_claim": page,
        "snapshot_date": snapshot_date.isoformat(),
        "as_of": today.isoformat(),
        "source_sha256": expected_hash,
        "source_origin_independently_verified": False,
        "source_integrity_verified": True,
        "source_rows": len(seen),
        "markets": {m: {"rows": groups[m], "kap_codes": codes[m]} for m in codes},
        "equity_market_candidate_count": len(eligible),
        "structured_fund_separate_count": groups["structured_fund"],
        "kap_codes_pending_provider_symbol_mapping": eligible,
        "rows_with_unverified_isin_format": with_isin,
        "verified_provider_symbols": 0,
        "approved_broker_symbols": 0,
        "verified_ohlcv_bars": 0,
        "tradeable_bist_universe_verified": False,
        "market_data_license_verified": False,
        "paper_trading_enabled": False,
        "live_trading_enabled": False,
        "network_requests": 0,
        "orders": 0,
    }


def main() -> int:
    p = argparse.ArgumentParser(description="Review-only KAP Pazarlar CSV staging")
    p.add_argument("--csv", required=True, type=Path)
    p.add_argument("--sha256", required=True)
    p.add_argument("--source-url", required=True)
    p.add_argument("--snapshot-date", required=True)
    p.add_argument("--as-of", default=None)
    p.add_argument("--report-json", type=Path)
    p.add_argument("--strict", action="store_true")
    args = p.parse_args()
    try:
        report = inspect(args.csv, args.sha256, args.source_url,
                         parse_day(args.snapshot_date),
                         as_of=parse_day(args.as_of) if args.as_of else None)
        if args.report_json:
            target = args.report_json
            if (target.is_symlink() or not target.parent.is_dir()
                    or target.parent.is_symlink()):
                raise KAPInputError("unsafe_report_output")
            with target.open("x", encoding="utf-8") as output:
                json.dump(report, output, ensure_ascii=False, sort_keys=True)
                output.write("\n")
        compact = {k: v for k, v in report.items()
                   if k not in {"markets", "kap_codes_pending_provider_symbol_mapping"}}
        compact["markets"] = {k: v["rows"] for k, v in report["markets"].items()}
        compact["sample_pending_kap_codes"] = report["kap_codes_pending_provider_symbol_mapping"][:10]
        print(json.dumps(compact, ensure_ascii=False, sort_keys=True))
        return 2 if args.strict else 0  # 0 means parsed, NEVER release approved
    except (KAPInputError, OSError, csv.Error) as error:
        print(json.dumps({"status": "BLOCKED_INVALID_KAP_EVIDENCE",
                          "reason": str(error), "orders": 0}, ensure_ascii=False))
        return 1


if __name__ == "__main__":
    sys.exit(main())
