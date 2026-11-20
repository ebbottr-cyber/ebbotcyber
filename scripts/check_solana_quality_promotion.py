"""Offline fail-closed PR gate for reviewed Solana quality JSON promotion.

This checks schema, arithmetic, and replay/recency relative to main's published
snapshot. It cannot authenticate GitHub artifact provenance by itself: reviewers
must separately confirm the producer and independent audit run on GitHub.
No HTTP requests, trading, wallets, scan, scheduler, or file mutation.
"""
from __future__ import annotations

import argparse
import json
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

RUN_ID = re.compile(r"[1-9][0-9]{5,19}\Z")
DATE_UTC = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z\Z")
MAX_REPORT_BYTES = 12_000
EXPECTED_FIELDS = {
    "schema_version", "mode", "audited_at_utc", "audit_run_id",
    "quality_result", "capture_count", "total_priced_rows",
    "total_missing_rows", "blocked_assessments", "watch_assessments",
    "trading_enabled", "wallet_enabled", "performance_calculated",
    "ready_for_verified_paper_performance", "captures",
}
CAPTURE_FIELDS = {"run_id", "priced_rows", "missing_rows", "result"}


class PromotionRejected(ValueError):
    """Report is not an acceptable reviewed observation promotion."""


def require(test: bool, message: str) -> None:
    if not test:
        raise PromotionRejected(message)


def non_negative_integer(x: Any, upper: int) -> bool:
    return type(x) is int and 0 <= x <= upper


def id_value(value: Any) -> int:
    require(isinstance(value, str) and RUN_ID.fullmatch(value) is not None,
            "Invalid Actions run ID")
    return int(value)


def parse_utc(value: Any) -> datetime:
    require(isinstance(value, str) and DATE_UTC.fullmatch(value) is not None,
            "Audited time must be UTC ISO YYYY-MM-DDTHH:MM:SSZ")
    try:
        parsed = datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ")
    except ValueError as exc:
        raise PromotionRejected("Invalid UTC audit date") from exc
    require(parsed.year >= 2020, "Implausibly old audit date")
    return parsed.replace(tzinfo=timezone.utc)


def validate_report(value: Any) -> dict[str, Any]:
    """Validate the entire reviewed JSON shape before trusting any numbers."""
    require(type(value) is dict and set(value) == EXPECTED_FIELDS,
            "Unexpected or missing report fields")
    require(type(value["schema_version"]) is int and value["schema_version"] == 1,
            "Unexpected reviewed report schema version")
    require(value["mode"] == "reviewed_github_actions_archive_quality",
            "Unreviewed report mode")
    parse_utc(value["audited_at_utc"])
    audit_id = id_value(value["audit_run_id"])
    for flag in ("trading_enabled", "wallet_enabled", "performance_calculated",
                 "ready_for_verified_paper_performance"):
        require(value[flag] is False, f"Unsafe flag: {flag}")

    captures = value["captures"]
    require(type(captures) is list and 1 <= len(captures) <= 6,
            "Expected 1 to 6 capture summaries")
    require(non_negative_integer(value["capture_count"], 6)
            and value["capture_count"] == len(captures),
            "Capture count mismatch")

    ids: set[int] = set()
    priced = missing = 0
    all_passed = True
    for item in captures:
        require(type(item) is dict and set(item) == CAPTURE_FIELDS,
                "Unexpected capture fields")
        run_id = id_value(item["run_id"])
        require(run_id not in ids and run_id != audit_id and run_id < audit_id,
                "Duplicate or non-chronological source run")
        ids.add(run_id)
        valid = item["priced_rows"]
        absent = item["missing_rows"]
        require(non_negative_integer(valid, 8) and non_negative_integer(absent, 8)
                and 1 <= valid + absent <= 8, "Invalid capture price counters")
        require(item["result"] in ("passed", "degraded"), "Invalid capture quality")
        require(item["result"] != "passed" or absent == 0,
                "Missing prices cannot be marked as passed")
        priced += valid
        missing += absent
        all_passed = all_passed and item["result"] == "passed"
    require(non_negative_integer(value["total_priced_rows"], 48)
            and value["total_priced_rows"] == priced, "Priced count mismatch")
    require(non_negative_integer(value["total_missing_rows"], 48)
            and value["total_missing_rows"] == missing, "Missing count mismatch")
    blocked, watch = value["blocked_assessments"], value["watch_assessments"]
    require(non_negative_integer(blocked, 96) and non_negative_integer(watch, 96)
            and blocked + watch == 2 * priced,
            "Risk decisions do not match both strategies per priced row")
    quality = "complete_captures" if all_passed and missing == 0 else "degraded_capture_data"
    require(value["quality_result"] == quality, "Quality label contradicts captures")
    return value


def check_promotion(
    published: Any, candidate: Any, *, now: datetime | None = None,
) -> dict[str, Any]:
    """Require a strictly newer audit AND wholly new source batch.

    The script does not write either file and does not replace human review or
    actual GitHub workflow provenance verification.
    """
    previous = validate_report(published)
    current = validate_report(candidate)
    old_audit_id = id_value(previous["audit_run_id"])
    next_audit_id = id_value(current["audit_run_id"])
    require(next_audit_id > old_audit_id, "Audit run has not advanced")
    old_date = parse_utc(previous["audited_at_utc"])
    next_date = parse_utc(current["audited_at_utc"])
    require(next_date > old_date, "Audit timestamp is not newer")
    clock = now or datetime.now(timezone.utc)
    require(clock.tzinfo is not None and clock.utcoffset() is not None,
            "Comparison clock must be timezone-aware")
    require(next_date <= clock.astimezone(timezone.utc) + timedelta(minutes=5),
            "Future-dated audits must not be displayed as completed")

    old_ids = {id_value(item["run_id"]) for item in previous["captures"]}
    new_ids = {id_value(item["run_id"]) for item in current["captures"]}
    require(new_ids.isdisjoint(old_ids), "Prior capture run reused in new report")
    require(min(new_ids) > max(old_ids), "New report contains older/replayed observations")
    # No extra permissions result from a good quality label; numbers remain observations.
    return current


def read_small_json(path: Path) -> Any:
    try:
        require(path.is_file() and path.stat().st_size <= MAX_REPORT_BYTES,
                "Report is missing or too large")
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise PromotionRejected("Could not read JSON report") from exc


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Read-only PR gate against replayed Solana reviewed quality reports"
    )
    parser.add_argument("--candidate", required=True, type=Path)
    parser.add_argument(
        "--baseline", type=Path, default=None,
        help="Existing main-branch reviewed JSON for a proposed replacement",
    )
    args = parser.parse_args()
    try:
        candidate = read_small_json(args.candidate)
        if args.baseline is None:
            validate_report(candidate)
            kind = "existing_report_valid"
        else:
            check_promotion(read_small_json(args.baseline), candidate)
            kind = "new_capture_batch_requires_human_review"
    except (PromotionRejected, ValueError) as exc:
        print(json.dumps({"status": "rejected", "reason": str(exc),
                          "trading_enabled": False, "published": False}))
        return 1
    print(json.dumps({"status": kind, "trading_enabled": False,
                      "published": False, "approval_granted": False}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
