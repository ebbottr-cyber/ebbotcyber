"""Create a PR-review *candidate* from verified Solana observation JSON files.

This OFFLINE converter cannot check GitHub workflow identity by itself. The
manual GitHub Actions entrypoint checks source run identity and downloads
artifacts before invoking it. A human must review the candidate and source
audit before merging into the frontend's public JSON. No market calls, orders,
wallets, automatic publishing, or performance estimates are performed.
"""
from __future__ import annotations

import argparse
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Sequence

from scripts.validate_solana_history import (
    ObservationValidationError,
    validate_document,
    validate_history,
)

_RUN_ID = re.compile(r"[0-9]{6,20}\Z")
_MAX_BYTES = 2_000_000
_MAX_CAPTURES = 6
_PUBLIC_REPORT_NAME = "solana-quality-reviewed.json"


def _check(condition: bool, message: str) -> None:
    if not condition:
        raise ObservationValidationError(message)


def _run_id(value: str) -> str:
    _check(bool(_RUN_ID.fullmatch(value)), "Invalid GitHub Actions run ID")
    return value


def _utc_timestamp(value: str) -> str:
    _check(isinstance(value, str) and bool(
        re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z", value)
    ), "UTC audit timestamp must be YYYY-MM-DDTHH:MM:SSZ")
    try:
        stamp = datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ")
    except ValueError as exc:
        raise ObservationValidationError("Invalid UTC audit timestamp") from exc
    _check(stamp.year >= 2020, "Audit timestamp is implausibly old")
    return value


def prepare_candidate(
    capture_paths: Sequence[tuple[str, Path]],
    *,
    audit_run_id: str,
    audited_at_utc: str,
) -> dict[str, Any]:
    """Recompute every count from raw rows, never from untrusted summaries.

    The resulting JSON is a REVIEW CANDIDATE, not proof of GitHub provenance.
    Before using this file in the UI, a reviewer must verify the successful
    audit workflow and that every run ID belongs to the approved producer.
    """
    audit_run_id = _run_id(audit_run_id)
    _utc_timestamp(audited_at_utc)
    _check(1 <= len(capture_paths) <= _MAX_CAPTURES, "Require 1 to 6 captures")
    _check(
        len({_run_id(run_id) for run_id, _ in capture_paths}) == len(capture_paths),
        "Duplicate observation run ID",
    )
    _check(
        all(run_id != audit_run_id for run_id, _ in capture_paths),
        "Source run cannot equal audit run",
    )

    docs: list[Any] = []
    captures = []
    for run_id, path in capture_paths:
        _check(path.is_file() and path.stat().st_size <= _MAX_BYTES,
               "Missing or oversized observation JSON artifact")
        try:
            doc = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, ValueError) as exc:
            raise ObservationValidationError("Invalid observation artifact JSON") from exc
        checked = validate_document(doc)
        _check(checked["result"] in ("passed", "degraded"),
               "Inconclusive capture cannot become a UI report")
        _check(checked["priced_rows"] + checked["missing_rows"] > 0,
               "Empty observation capture is inconclusive")
        docs.append(doc)
        captures.append({
            "run_id": run_id,
            "priced_rows": checked["priced_rows"],
            "missing_rows": checked["missing_rows"],
            "result": checked["result"],
        })

    combined = validate_history(docs)
    priced = sum(item["priced_rows"] for item in captures)
    missing = sum(item["missing_rows"] for item in captures)
    blocked = sum(validate_document(doc)["blocked_assessments"] for doc in docs)
    watch = sum(validate_document(doc)["watch_assessments_not_trade_signals"] for doc in docs)

    _check(
        combined["input_capture_count"] == len(captures)
        and combined["total_priced_rows"] == priced
        and combined["total_missing_rows"] == missing
        and blocked + watch == 2 * priced,
        "Combined quality totals disagree with validated observations",
    )
    _check(
        combined["safety"] == {
            "trading_enabled": False,
            "wallet_enabled": False,
            "external_requests": 0,
            "performance_calculated": False,
        }
        and combined["ready_for_verified_paper_performance"] is False,
        "History has unsupported safety or performance status",
    )
    _check(priced <= 48 and missing <= 48 and blocked <= 96 and watch <= 96,
           "Too many observations for the reviewed UI schema")
    return {
        "schema_version": 1,
        "mode": "reviewed_github_actions_archive_quality",
        "audited_at_utc": audited_at_utc,
        "audit_run_id": audit_run_id,
        "quality_result": combined["quality_result"],
        "capture_count": len(captures),
        "total_priced_rows": priced,
        "total_missing_rows": missing,
        "blocked_assessments": blocked,
        "watch_assessments": watch,
        "trading_enabled": False,
        "wallet_enabled": False,
        "performance_calculated": False,
        "ready_for_verified_paper_performance": False,
        "captures": captures,
    }


def verify_source_conclusions(
    candidate: dict[str, Any], conclusions: dict[str, str]
) -> None:
    """Match trusted GH run conclusions to the independently recomputed quality.

    A producer run intentionally fails on degraded data. Do not discard that
    evidence, but never treat a failed run as a successful capture. A failed
    run is still subject to explicit human audit before a UI PR is approved.
    """
    captures = candidate["captures"]
    _check(
        set(conclusions) == {item["run_id"] for item in captures},
        "Source conclusion IDs must match every reviewed capture",
    )
    for item in captures:
        conclusion = conclusions[item["run_id"]]
        _check(
            conclusion in ("success", "failure"),
            "Only completed successful or degraded-source runs are accepted",
        )
        _check(
            (conclusion == "success" and item["result"] == "passed")
            or (conclusion == "failure" and item["result"] == "degraded"),
            "Producer conclusion disagrees with validated capture quality",
        )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Generate REVIEW-ONLY Solana quality report candidate from local JSON"
    )
    parser.add_argument(
        "--capture", action="append", required=True, metavar="RUN_ID=OBSERVATIONS_JSON",
        help="Approved observation Actions run ID and local JSON (repeat 1-6 times)",
    )
    parser.add_argument(
        "--source-conclusion", action="append", required=True,
        metavar="RUN_ID=success|failure",
        help="Source GH run conclusion obtained from approved workflow, one per capture",
    )
    parser.add_argument("--audit-run-id", required=True, help="Independent quality audit run ID")
    parser.add_argument(
        "--audited-at-utc", default=None, help="Audit time YYYY-MM-DDTHH:MM:SSZ (UTC)",
    )
    parser.add_argument(
        "--output", type=Path, default=Path("solana-reviewed-quality-candidate.json"),
    )
    args = parser.parse_args()
    _check(args.output.name != _PUBLIC_REPORT_NAME,
           "Refuse direct writing to the published web quality report")
    try:
        captures = []
        for entry in args.capture:
            run_id, separator, filename = entry.partition("=")
            _check(bool(separator and filename), "Use RUN_ID=OBSERVATIONS_JSON")
            captures.append((run_id, Path(filename)))
        timestamp = args.audited_at_utc or datetime.now(timezone.utc).strftime(
            "%Y-%m-%dT%H:%M:%SZ"
        )
        candidate = prepare_candidate(
            captures, audit_run_id=args.audit_run_id, audited_at_utc=timestamp
        )
        conclusions: dict[str, str] = {}
        for entry in args.source_conclusion:
            run_id, separator, conclusion = entry.partition("=")
            _check(bool(separator) and run_id not in conclusions,
                   "Malformed or duplicated source conclusion")
            conclusions[_run_id(run_id)] = conclusion
        verify_source_conclusions(candidate, conclusions)
        # Write only after all validations pass. This is NOT the public UI file.
        args.output.write_text(
            json.dumps(candidate, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )
    except (OSError, ValueError, UnicodeError) as exc:
        print(json.dumps({
            "result": "rejected",
            "reason": type(exc).__name__,
            "trading_enabled": False,
            "performance_calculated": False,
            "candidate_published": False,
        }))
        return 1
    print(json.dumps({
        "result": "candidate_requires_review",
        "audit_run_id": candidate["audit_run_id"],
        "capture_count": candidate["capture_count"],
        "total_priced_rows": candidate["total_priced_rows"],
        "total_missing_rows": candidate["total_missing_rows"],
        "quality_result": candidate["quality_result"],
        "candidate_published": False,
        "trading_enabled": False,
    }))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
