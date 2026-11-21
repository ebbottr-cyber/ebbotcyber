"""Read-only operator evidence gate for four equity market-data providers.

Public product pages are research leads; a URL, vendor name, license ticket or
operator's boolean assertion is *not* proof of contractual rights or coverage.
This gate deliberately NEVER green-lights price ingestion, trading or release.

No network, API account access, credentials, PDF contract upload, scheduling,
database writes, orders, or automatic source enablement.
"""
from __future__ import annotations

import argparse
from datetime import date, datetime, timezone
import json
from pathlib import Path
import re
import sys
from typing import Any

from scripts.audit_ebbot_market_data_coverage import AuditInputError, MARKETS, parse_day

ROOT = Path(__file__).resolve().parents[1]
CATALOG = ROOT / "data/market_sources/official_equity_data_options.json"
MAX_REVIEW_FILE_BYTES = 32 * 1024
TAG = re.compile(r"^[A-Za-z0-9_.:-]{3,80}$")
REQUIRED_RIGHTS = (
    "historical_daily_ohlcv",
    "non_display_internal_research",
    "local_caching_and_retention",
    "automated_algorithmic_analysis",
)
REQUIRED_CHECKS = (
    "contract_terms_reviewed_by_authorized_person",
    "sample_export_obtained_by_authorized_person",
    "exchange_ticker_mapping_reviewed",
    "exchange_session_calendar_reviewed",
)
FRESHNESS_DAYS = 30


def _read_json(path: Path, *, limit: int) -> Any:
    if path.is_symlink() or not path.is_file() or not 0 < path.stat().st_size <= limit:
        raise AuditInputError("missing_unsafe_or_oversized_source_review")
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise AuditInputError("unreadable_source_review_json") from exc


def _catalog(path: Path) -> dict[str, Any]:
    raw = _read_json(path, limit=MAX_REVIEW_FILE_BYTES)
    if not isinstance(raw, dict) or raw.get("schema_version") != 1:
        raise AuditInputError("invalid_source_catalog")
    sources = raw.get("markets")
    if not isinstance(sources, dict) or set(sources) != set(MARKETS):
        raise AuditInputError("source_catalog_missing_markets")
    for market, entries in sources.items():
        if not isinstance(entries, list) or not entries:
            raise AuditInputError("empty_source_research_options")
        for option in entries:
            if (
                not isinstance(option, dict)
                or set(option) != {"product", "official_product_url", "note"}
                or not all(isinstance(x, str) and x.strip() for x in option.values())
                or not option["official_product_url"].startswith("https://")
                or len(option["official_product_url"]) > 300
            ):
                raise AuditInputError("invalid_source_research_option")
    return sources


def _validated_record(record: Any, today: date) -> tuple[list[str], dict[str, Any]]:
    if not isinstance(record, dict) or set(record) != {
        "provider_reference", "product_reference", "assessment_ticket",
        "reviewed_utc_date", "access_expires_utc_date", "rights_claimed",
        "checks_claimed",
    }:
        raise AuditInputError("invalid_provider_review_schema")
    for field in ("provider_reference", "product_reference", "assessment_ticket"):
        if not isinstance(record[field], str) or not TAG.fullmatch(record[field]):
            raise AuditInputError("unsafe_or_missing_provider_review_reference")
    rights = record["rights_claimed"]
    checks = record["checks_claimed"]
    if not isinstance(rights, dict) or set(rights) != set(REQUIRED_RIGHTS):
        raise AuditInputError("invalid_declared_usage_rights")
    if not isinstance(checks, dict) or set(checks) != set(REQUIRED_CHECKS):
        raise AuditInputError("invalid_declared_operator_checks")
    if any(type(v) is not bool for v in list(rights.values()) + list(checks.values())):
        raise AuditInputError("non_boolean_provider_attestation")
    reviewed = parse_day(record["reviewed_utc_date"])
    expires = parse_day(record["access_expires_utc_date"])
    if reviewed > today:
        raise AuditInputError("future_provider_review")
    missing = [
        f"right_not_attested:{name}" for name in REQUIRED_RIGHTS if not rights[name]
    ] + [
        f"check_not_attested:{name}" for name in REQUIRED_CHECKS if not checks[name]
    ]
    if expires < today:
        missing.append("access_review_expired")
    if expires < reviewed:
        missing.append("access_expiry_before_review")
    if (today - reviewed).days > FRESHNESS_DAYS:
        missing.append("operator_review_older_than_30_days")
    return missing, {
        "reviewed_utc_date": reviewed.isoformat(),
        "access_expires_utc_date": expires.isoformat(),
        "nonsecret_ticket_present": True,
        "claims_are_not_independently_verified": True,
    }


def audit_provider_readiness(
    review_file: Path | None = None,
    *,
    as_of: date | None = None,
    catalog_path: Path = CATALOG,
) -> dict[str, Any]:
    today = as_of or datetime.now(timezone.utc).date()
    options = _catalog(Path(catalog_path))
    declarations = {}
    if review_file is not None:
        raw = _read_json(Path(review_file), limit=MAX_REVIEW_FILE_BYTES)
        if not isinstance(raw, dict) or set(raw) != {"schema_version", "markets"}:
            raise AuditInputError("invalid_provider_review_document")
        if type(raw["schema_version"]) is not int or raw["schema_version"] != 1:
            raise AuditInputError("unsupported_provider_review_version")
        declarations = raw["markets"]
        if not isinstance(declarations, dict) or not set(declarations).issubset(MARKETS):
            raise AuditInputError("unsupported_review_market")
    results: dict[str, Any] = {}
    for market in MARKETS:
        leads = [{
            "product": x["product"],
            "official_product_url": x["official_product_url"],
            "note": x["note"],
            "connection_configured": False,
            "license_verified": False,
            "ohlcv_ingested": False,
        } for x in options[market]]
        record = declarations.get(market)
        if record is None:
            results[market] = {
                "state": "MISSING_OPERATOR_EVIDENCE",
                "missing_requirements": ["no_operator_review_record"],
                "review": None,
                "official_product_research_options": leads,
            }
            continue
        missing, metadata = _validated_record(record, today)
        results[market] = {
            "state": (
                "OPERATOR_CLAIMS_SUBMITTED_NEEDS_INDEPENDENT_VERIFICATION"
                if not missing else "BLOCKED_INCOMPLETE_OR_EXPIRED_OPERATOR_EVIDENCE"
            ),
            "missing_requirements": missing,
            "review": metadata,
            "official_product_research_options": leads,
        }
    return {
        "status": "BLOCKED_NOT_APPROVED_FOR_DATA_INGESTION_OR_TRADING",
        "as_of_utc_date": today.isoformat(),
        "selected_markets": list(MARKETS),
        "markets": results,
        "markets_with_review_record": sum(market in declarations for market in MARKETS),
        "markets_with_complete_operator_claims": sum(
            not results[m]["missing_requirements"] for m in MARKETS
        ),
        "independent_contract_verification": False,
        "independent_exchange_coverage_verification": False,
        "provider_credentials_connected": False,
        "licensed_historical_prices_loaded": False,
        "may_auto_import_quotes": False,
        "may_use_in_analysis": False,
        "paper_trading_enabled": False,
        "live_trading_enabled": False,
        "network_requests": 0,
        "orders": 0,
    }


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Read-only four-market provider operator evidence review")
    p.add_argument("--review", type=Path, help="Optional LOCAL nonsecret operator-claims JSON file")
    p.add_argument("--as-of", type=str, help="Replay/testing UTC date (YYYY-MM-DD)")
    return p


def run(args: argparse.Namespace) -> int:
    try:
        report = audit_provider_readiness(
            args.review, as_of=parse_day(args.as_of) if args.as_of else None,
        )
        print(json.dumps(report, ensure_ascii=True, sort_keys=True))
        # 0 means the DIAGNOSTIC executed, never that a source was approved.
        return 0
    except (AuditInputError, ValueError, TypeError, OSError) as exc:
        reason = str(exc) if isinstance(exc, AuditInputError) else "invalid_review_input"
        print(json.dumps({
            "status": "BLOCKED_INVALID_REVIEW_INPUT",
            "reason": reason,
            "network_requests": 0,
            "orders": 0,
            "paper_trading_enabled": False,
            "live_trading_enabled": False,
        }, sort_keys=True))
        return 1


if __name__ == "__main__":
    sys.exit(run(parser().parse_args()))
