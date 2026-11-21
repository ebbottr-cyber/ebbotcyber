"""Read-only KAP code <-> declared BIST instrument/ISIN crosswalk audit.

Operator-supplied CSV and URL claims prove neither original source authenticity
nor listing, license, trading eligibility, broker entitlement or provider mapping.
No network, prices, SQL, broker calls, or automatic symbol generation.
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

from scripts.audit_ebbot_kap_market_inventory import (
    CODE, EQUITY_MARKETS, ISIN, KAPInputError, MARKETS, inspect as inspect_kap,
    parse_day,
)

MAX_BYTES = 16 * 1024 * 1024
BIST_CODE = re.compile(r"[A-Z0-9]{2,12}\Z")
SHA = re.compile(r"[a-f0-9]{64}\Z")
REQUIRED_COLUMNS = {
    "kap_kodu", "bist_islem_kodu", "pazar", "isin", "kaynak_tarihi",
}


def official_bist_url(value: str) -> bool:
    parts = urlsplit(value)
    return (
        parts.scheme == "https"
        and parts.netloc in {"borsaistanbul.com", "www.borsaistanbul.com"}
        and parts.path in {
            "/veriler/pay-piyasasi-verileri",
            "/veriler/pay-piyasasi-verileri/bulten-verileri",
        }
        and not parts.fragment
        and not parts.username
        and not parts.password
    )


def read_pinned_csv(path: Path, digest: str) -> csv.DictReader:
    if (not SHA.fullmatch(digest) or path.is_symlink() or not path.is_file()
            or path.stat().st_size > MAX_BYTES):
        raise KAPInputError("invalid_or_unsafe_bist_source")
    raw = path.read_bytes()
    if len(raw) > MAX_BYTES or hashlib.sha256(raw).hexdigest() != digest:
        raise KAPInputError("bist_source_sha256_mismatch")
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeError as error:
        raise KAPInputError("bist_source_not_utf8") from error
    reader = csv.DictReader(io.StringIO(text))
    if (not reader.fieldnames or len(set(reader.fieldnames)) != len(reader.fieldnames)
            or set(reader.fieldnames) != REQUIRED_COLUMNS):
        raise KAPInputError("invalid_bist_crosswalk_columns")
    return reader


def audit(
    kap_csv: Path, kap_sha: str, kap_day: date,
    bist_csv: Path | None, bist_sha: str | None, bist_day: date | None,
    *, kap_url: str = "https://www.kap.org.tr/tr/Pazarlar",
    bist_url: str = "https://www.borsaistanbul.com/veriler/pay-piyasasi-verileri",
    as_of: date | None = None, max_age_days: int = 7,
) -> dict:
    now = as_of or datetime.now(timezone.utc).date()
    kap = inspect_kap(kap_csv, kap_sha, kap_url, kap_day,
                      as_of=now, max_age_days=max_age_days)
    if bool(bist_csv) != bool(bist_sha) or bool(bist_csv) != bool(bist_day):
        raise KAPInputError("incomplete_bist_evidence_bundle")
    all_kap: dict[str, str] = {}
    for category, data in kap["markets"].items():
        for code in data["kap_codes"]:
            all_kap[code] = category
    candidates = {
        code for code, market in all_kap.items() if market in EQUITY_MARKETS
    }
    # KAP's pinned JSON only reports the number of ISINs. Recheck the raw
    # snapshot bytes before reading individual ISINs for cross-evidence.
    kap_raw = kap_csv.read_bytes()
    if hashlib.sha256(kap_raw).hexdigest() != kap_sha:
        raise KAPInputError("kap_changed_during_audit")
    kap_reader = csv.DictReader(io.StringIO(kap_raw.decode("utf-8-sig")))
    kap_isins = {
        row["kap_kodu"].strip(): (row.get("isin") or "").strip()
        for row in kap_reader
    }
    declarations: dict[str, dict] = {}
    per_company: Counter[str] = Counter()
    mapped_kap: set[str] = set()
    declared_isins: dict[str, str] = {}
    dates: set[str] = set()
    pending_isin = 0
    if bist_csv is not None:
        if not official_bist_url(bist_url) or bist_day is None or bist_day > now:
            raise KAPInputError("untrusted_or_future_bist_source")
        for line, row in enumerate(read_pinned_csv(bist_csv, bist_sha or ""), 2):
            if None in row or any(v is None for v in row.values()):
                raise KAPInputError(f"malformed_bist_row_{line}")
            if not any(v.strip() for v in row.values()):
                continue
            kap_code = row["kap_kodu"].strip()
            symbol = row["bist_islem_kodu"].strip()
            isin = row["isin"].strip()
            date_val = parse_day(row["kaynak_tarihi"].strip())
            market = MARKETS.get(row["pazar"].strip())
            if not CODE.fullmatch(kap_code) or kap_code not in all_kap:
                raise KAPInputError(f"unknown_kap_reference_{line}")
            if all_kap[kap_code] not in EQUITY_MARKETS:
                raise KAPInputError(f"non_equity_kap_reference_{line}")
            if market != all_kap[kap_code]:
                raise KAPInputError(f"kap_bist_market_mismatch_{line}")
            if not BIST_CODE.fullmatch(symbol) or symbol in declarations:
                raise KAPInputError(f"invalid_or_reused_bist_instrument_code_{line}")
            if isin and not ISIN.fullmatch(isin):
                raise KAPInputError(f"invalid_bist_isin_{line}")
            if kap_isins.get(kap_code) and isin and kap_isins[kap_code] != isin:
                raise KAPInputError(f"kap_bist_isin_mismatch_{line}")
            if isin and isin in declared_isins:
                raise KAPInputError(f"duplicate_bist_isin_{line}")
            if date_val != bist_day:
                raise KAPInputError(f"mixed_bist_source_dates_{line}")
            if date_val > now:
                raise KAPInputError("future_bist_source")
            declarations[symbol] = {
                "kap_kodu": kap_code,
                "pazar": market,
                "isin": isin or None,
                "source_as_of_date": date_val.isoformat(),
                "mapping_origin_independently_verified": False,
                "provider_symbol_verified": False,
                "broker_symbol_verified": False,
            }
            mapped_kap.add(kap_code)
            per_company[kap_code] += 1
            pending_isin += not bool(isin)
            if isin:
                declared_isins[isin] = symbol
            dates.add(date_val.isoformat())
        if not declarations:
            raise KAPInputError("empty_bist_crosswalk")
    missing = sorted(candidates - mapped_kap)
    multiples = sorted(code for code, count in per_company.items() if count > 1)
    declared_stale = bist_day is not None and (now - bist_day).days > max_age_days
    # Always block independent-identity approval. A matching CSV is a
    # self-declared crosswalk until separately checked against original BIST data.
    return {
        "schema_version": 1,
        "status": (
            "BLOCKED_STALE_CROSSWALK" if kap["status"] == "BLOCKED_STALE_KAP_SNAPSHOT"
            or declared_stale else "BLOCKED_UNVERIFIED_BIST_CROSSWALK"
        ),
        "as_of": now.isoformat(),
        "kap_source_as_of": kap_day.isoformat(),
        "bist_source_as_of": bist_day.isoformat() if bist_day else None,
        "kap_source_sha256": kap_sha,
        "bist_source_sha256": bist_sha,
        "kap_source_origin_verified": False,
        "bist_source_origin_verified": False,
        "source_integrity_checks_passed": True,
        "kap_equity_market_candidate_codes": len(candidates),
        "declared_bist_instrument_codes": len(declarations),
        "kap_codes_with_declared_instruments": len(mapped_kap),
        "kap_codes_without_declared_instruments": len(missing),
        "kap_codes_without_declared_instruments_full": missing,
        "companies_with_multiple_declared_instruments": multiples,
        "instruments_without_isin": pending_isin,
        "declared_crosswalk_full": declarations,
        "all_eight_kap_segments_present": kap["all_eight_pay_market_segments_present"],
        "official_bist_list_independently_verified": False,
        "isin_independently_verified": False,
        "provider_mapping_verified": False,
        "broker_mapping_verified": False,
        "licensed_ohlcv_verified": False,
        "real_time_quotes_verified": False,
        "paper_trading_enabled": False,
        "live_trading_enabled": False,
        "network_requests": 0,
        "orders": 0,
    }


def main() -> int:
    p = argparse.ArgumentParser(description="EBBot offline KAP/BIST identity preflight (NO trades)")
    p.add_argument("--kap-csv", required=True, type=Path)
    p.add_argument("--kap-sha256", required=True)
    p.add_argument("--kap-date", required=True)
    p.add_argument("--bist-csv", type=Path)
    p.add_argument("--bist-sha256")
    p.add_argument("--bist-date")
    p.add_argument("--as-of")
    p.add_argument("--report-json", type=Path)
    p.add_argument("--strict", action="store_true")
    args = p.parse_args()
    try:
        report = audit(
            args.kap_csv, args.kap_sha256, parse_day(args.kap_date),
            args.bist_csv, args.bist_sha256,
            parse_day(args.bist_date) if args.bist_date else None,
            as_of=parse_day(args.as_of) if args.as_of else None,
        )
        if args.report_json:
            output = args.report_json
            if output.is_symlink() or not output.parent.is_dir() or output.parent.is_symlink():
                raise KAPInputError("unsafe_output_location")
            with output.open("x", encoding="utf-8") as stream:
                json.dump(report, stream, ensure_ascii=False, sort_keys=True)
                stream.write("\n")
        compact = {
            k: v for k, v in report.items()
            if k not in {"declared_crosswalk_full", "kap_codes_without_declared_instruments_full"}
        }
        compact["missing_kap_sample"] = report["kap_codes_without_declared_instruments_full"][:10]
        compact["declared_instrument_sample"] = list(report["declared_crosswalk_full"])[:10]
        print(json.dumps(compact, ensure_ascii=False, sort_keys=True))
        return 2 if args.strict else 0
    except (KAPInputError, ValueError, OSError, csv.Error, UnicodeError) as error:
        print(json.dumps({"status": "BLOCKED_INVALID_CROSSWALK_EVIDENCE",
                          "error": str(error), "orders": 0}, ensure_ascii=False))
        return 1


if __name__ == "__main__":
    sys.exit(main())
