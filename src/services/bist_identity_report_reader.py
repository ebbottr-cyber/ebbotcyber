"""Private, read-only BIST KAP/XIST reconciliation summary for EBBot Data Center.

Reads only an operator-selected local JSON report. Returns bounded numeric
aggregates, NEVER symbols, ISINs, OHLCV prices, paths or original source rows.
This is not proof of a current exchange listing or a market-data license.
"""
from __future__ import annotations

from datetime import date, datetime, timezone
import json
import os
from pathlib import Path
import re
from typing import Any

ENV_REPORT = "EBBOT_BIST_IDENTITY_REPORT_PATH"
MAX_REPORT_BYTES = 4 * 1024 * 1024
MAX_RECORDS = 100_000
DAY_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
REPORT_STATUSES = frozenset({
    "BLOCKED_STALE_OR_INCOMPLETE_BIST_REFERENCES",
    "REVIEW_ONLY_NEEDS_INDEPENDENT_BIST_CONFIRMATION",
})
NO_TRADE_FLAGS = (
    "independent_listing_authentication_verified",
    "isin_to_security_identity_verified",
    "price_provider_license_verified",
    "provider_symbol_mapping_independently_verified",
    "live_ohlcv_loaded",
    "paper_trading_enabled",
    "live_trading_enabled",
)
COUNT_FIELDS = (
    "kap_candidate_count",
    "exchange_reference_count",
    "exchange_active_count",
    "exchange_halted_or_delisted_count",
    "matched_kap_exchange_count",
    "matched_active_kap_exchange_count",
    "kap_not_in_exchange_count",
    "exchange_not_in_kap_count",
    "active_without_declared_provider_mapping_count",
    "stale_kap_reference_rows",
    "stale_exchange_reference_rows",
    "stale_provider_mapping_rows",
)
PRICE_FIELDS = (
    "active_with_ohlcv_in_supplied_file_count",
    "active_without_ohlcv_in_supplied_file_count",
)


class InvalidBistReport(ValueError):
    pass


def unavailable_bist_identity_report(reason: str = "operator_report_not_configured") -> dict[str, Any]:
    if reason not in {
        "operator_report_not_configured",
        "administrator_auth_required",
        "invalid_or_unsafe_bist_report",
        "bist_reference_files_missing",
    }:
        raise ValueError("unapproved_unavailable_reason")
    return {
        "status": "unavailable",
        "reason": reason,
        "as_of_utc_date": None,
        "counts": None,
        "prices_file_supplied": False,
        "provider_mapping_file_supplied": False,
        "source_kind": "operator_local_bist_identity_report",
        "independent_listing_verified": False,
        "licensed_prices_verified": False,
        "paper_trading_enabled": False,
        "live_trading_enabled": False,
    }


def _whole(raw: dict[str, Any], key: str) -> int:
    val = raw.get(key)
    if type(val) is not int or val < 0 or val > MAX_RECORDS:
        raise InvalidBistReport("invalid_aggregate_count")
    return val


def _flag(raw: dict[str, Any], key: str) -> bool:
    value = raw.get(key)
    if type(value) is not bool:
        raise InvalidBistReport("invalid_report_boolean")
    return value


def _assert_source_consistency(raw: dict[str, Any]) -> dict[str, int | None]:
    if raw.get("counts_are_input_reconciliation_only") is not True:
        raise InvalidBistReport("unrecognized_evidence_scope")
    if any(_flag(raw, name) for name in NO_TRADE_FLAGS):
        raise InvalidBistReport("unsafe_positive_verification_claim")
    if raw.get("network_requests") != 0 or raw.get("orders") != 0:
        raise InvalidBistReport("report_claimed_external_action")
    counts: dict[str, int | None] = {key: _whole(raw, key) for key in COUNT_FIELDS}
    kap = counts["kap_candidate_count"]
    exchange = counts["exchange_reference_count"]
    active = counts["exchange_active_count"]
    halted = counts["exchange_halted_or_delisted_count"]
    common = counts["matched_kap_exchange_count"]
    common_active = counts["matched_active_kap_exchange_count"]
    kap_only = counts["kap_not_in_exchange_count"]
    exchange_only = counts["exchange_not_in_kap_count"]
    unmapped = counts["active_without_declared_provider_mapping_count"]
    if (
        active + halted != exchange
        or common + kap_only != kap
        or common + exchange_only != exchange
        or common_active > common
        or common_active > active
        or unmapped > active
        or counts["stale_kap_reference_rows"] > kap
        or counts["stale_exchange_reference_rows"] > exchange
        or counts["stale_provider_mapping_rows"] > kap + exchange
    ):
        raise InvalidBistReport("contradictory_bist_aggregates")
    has_prices = _flag(raw, "ohlcv_file_supplied")
    has_mapping = _flag(raw, "provider_mapping_file_supplied")
    if not has_mapping and unmapped != active:
        raise InvalidBistReport("unmapped_count_without_source")
    if has_prices:
        counts.update({key: _whole(raw, key) for key in PRICE_FIELDS})
        if sum(counts[key] for key in PRICE_FIELDS) != active:
            raise InvalidBistReport("contradictory_price_counts")
    else:
        if any(raw.get(key) is not None for key in PRICE_FIELDS):
            raise InvalidBistReport("prices_without_supplied_file")
        counts.update({key: None for key in PRICE_FIELDS})
    details = raw.get("candidate_symbol_details")
    if not isinstance(details, dict):
        raise InvalidBistReport("missing_private_detail_consistency")
    expected_lengths: dict[str, int | None] = {
        "kap_only": kap_only,
        "exchange_only": exchange_only,
        "halted_or_delisted": halted,
        "active_without_provider_mapping": unmapped,
        "active_without_input_ohlcv": counts["active_without_ohlcv_in_supplied_file_count"],
    }
    for field, expected in expected_lengths.items():
        value = details.get(field)
        if expected is None:
            if value is not None:
                raise InvalidBistReport("unexpected_private_detail")
        elif not isinstance(value, list) or len(value) != expected:
            raise InvalidBistReport("private_detail_count_mismatch")
    return counts


def read_bist_identity_summary(
    path: str | None = None, *, today: date | None = None
) -> dict[str, Any]:
    configured = os.getenv(ENV_REPORT, "") if path is None else path
    if not configured:
        return unavailable_bist_identity_report()
    candidate = Path(configured)
    if not candidate.is_absolute() or candidate.is_symlink():
        return unavailable_bist_identity_report("invalid_or_unsafe_bist_report")
    try:
        if not candidate.is_file() or not 0 < candidate.stat().st_size <= MAX_REPORT_BYTES:
            raise InvalidBistReport("missing_or_oversized_report")
        raw = json.loads(candidate.read_text(encoding="utf-8-sig"))
        if not isinstance(raw, dict):
            raise InvalidBistReport("invalid_bist_report")
        if raw.get("status") == "BLOCKED_MISSING_BIST_SOURCE_FILES":
            return unavailable_bist_identity_report("bist_reference_files_missing")
        if raw.get("status") not in REPORT_STATUSES:
            raise InvalidBistReport("unrecognized_bist_report_status")
        stamp = raw.get("as_of_utc_date")
        if not isinstance(stamp, str) or not DAY_RE.fullmatch(stamp):
            raise InvalidBistReport("invalid_bist_report_date")
        when = date.fromisoformat(stamp)
        now = today or datetime.now(timezone.utc).date()
        if when > now:
            raise InvalidBistReport("future_bist_report_date")
        counts = _assert_source_consistency(raw)
        stale_rows = sum(counts[key] for key in (
            "stale_kap_reference_rows", "stale_exchange_reference_rows",
            "stale_provider_mapping_rows",
        ))
        stale = (now - when).days > 7 or stale_rows > 0
        return {
            "status": "stale" if stale else "unverified",
            "reason": (
                "outdated_bist_identity_evidence" if stale
                else "operator_bist_reference_comparison_only"
            ),
            "as_of_utc_date": stamp,
            "counts": counts,
            "prices_file_supplied": raw["ohlcv_file_supplied"],
            "provider_mapping_file_supplied": raw["provider_mapping_file_supplied"],
            "source_kind": "operator_local_bist_identity_report",
            "independent_listing_verified": False,
            "licensed_prices_verified": False,
            "paper_trading_enabled": False,
            "live_trading_enabled": False,
        }
    except (OSError, UnicodeError, ValueError, TypeError, json.JSONDecodeError):
        return unavailable_bist_identity_report("invalid_or_unsafe_bist_report")
