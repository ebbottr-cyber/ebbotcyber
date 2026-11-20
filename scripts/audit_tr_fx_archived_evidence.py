"""Verify three immutable, pinned GitHub run artifacts as multi-snapshot evidence.

Manual/review CI only. The workflow downloads its own completed run artifacts
from GitHub and separately fetches the original run metadata. This script
does NOT contact any provider, broker or GitHub API itself. No live/paper trades,
schedules, market-day inference, current-quote claims, or persistence.
These specific archived artifacts expire after 7 days; intentionally not a
permanent CI gate or a scheduled archive.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timedelta
import json
from pathlib import Path
from typing import Any

from scripts.audit_tr_fx_multiday_continuity import ISTANBUL, summarize_continuity

MAX_FILE_BYTES = 1_000_000
PINNED_RUNS = (
    {
        "run_id": 44798315574,
        "commit": "54e0f7408c2a65610a2c4bee30475ea30cc6942c",
        "branch": "audit/tr-fx-cross-source-staleness-20261120",
        "artifact": "ebbot-tr-fx-cross-source-audit",
        "file": "tr-fx-readonly-observation.json",
    },
    {
        "run_id": 44799531473,
        "commit": "37e4a946589c210c2a59af34744ec51dba2ac434",
        "branch": "audit/tr-fx-multiday-continuity-20261120",
        "artifact": "ebbot-tr-fx-real-multiday-evidence",
        "file": "tr-fx-real-one-day-observation.json",
    },
    {
        "run_id": 44806940721,
        "commit": "abdb1dfa983c2c8a04c7df4d6d32acb89b7cf02f",
        "branch": "audit/tr-fx-publication-progress-20261120",
        "artifact": "tr-fx-publication-day-evidence",
        "file": "tr-fx-publication-source.json",
    },
)


def _no_constants(_: str) -> None:
    raise ValueError("non_finite_json_not_allowed")


def _read_strict_json(path: Path) -> Any:
    if not path.is_file() or path.is_symlink() or path.stat().st_size > MAX_FILE_BYTES:
        raise ValueError("missing_oversized_or_unsafe_evidence_file")
    return json.loads(path.read_text(encoding="utf-8"), parse_constant=_no_constants)


def _utc_timestamp(value: Any) -> datetime:
    if not isinstance(value, str):
        raise ValueError("missing_run_timestamp")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError("malformed_run_timestamp") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError("run_timestamp_without_timezone")
    return parsed


def validate_archive(
    pinned: dict[str, Any],
    metadata: Any,
    snapshot: Any,
) -> dict[str, Any]:
    """Do not confuse a successful CI job with authentic independent price data."""
    if not isinstance(metadata, dict) or not isinstance(snapshot, dict):
        raise ValueError("invalid_run_metadata_or_observation")
    if (type(metadata.get("id")) is not int
            or metadata["id"] != pinned["run_id"]
            or metadata.get("head_sha") != pinned["commit"]
            or metadata.get("head_branch") != pinned["branch"]
            or metadata.get("repository", {}).get("full_name") != "ebbottr-cyber/ebbotcyber"
            or metadata.get("event") != "push"
            or metadata.get("status") != "completed"
            or metadata.get("conclusion") != "success"):
        raise ValueError("pinned_github_run_metadata_mismatch")

    started = _utc_timestamp(metadata.get("created_at"))
    updated = _utc_timestamp(metadata.get("updated_at"))
    seen = _utc_timestamp(snapshot.get("observed_at_istanbul"))
    if not (started <= seen <= updated + timedelta(minutes=5)):
        raise ValueError("snapshot_outside_pinned_run_interval")
    if updated < started:
        raise ValueError("run_ended_before_it_started")
    if snapshot.get("as_of_local_date") != seen.astimezone(ISTANBUL).date().isoformat():
        raise ValueError("snapshot_istanbul_local_date_mismatch")
    return {
        "run_id": pinned["run_id"],
        "commit": pinned["commit"],
        "branch": pinned["branch"],
        "artifact": pinned["artifact"],
        "observation_timestamp": seen.astimezone(ISTANBUL).isoformat(),
        "observed_local_date": snapshot["as_of_local_date"],
        "run_conclusion": "success",
        "prices_verified_as_executable": False,
    }


def build_report(evidence: list[tuple[dict[str, Any], Any, Any]]) -> dict[str, Any]:
    """Check run-identity, timestamps, then delegate source truth to the prior audit."""
    if len(evidence) != len(PINNED_RUNS):
        raise ValueError("archived_run_count_mismatch")
    seen_ids = set()
    snapshots = []
    provenance = []
    for pinned, metadata, snapshot in evidence:
        run_id = pinned.get("run_id")
        if run_id in seen_ids or run_id not in {x["run_id"] for x in PINNED_RUNS}:
            raise ValueError("duplicate_or_unpinned_run")
        seen_ids.add(run_id)
        if pinned != next(x for x in PINNED_RUNS if x["run_id"] == run_id):
            raise ValueError("modified_pinned_run_contract")
        provenance.append(validate_archive(pinned, metadata, snapshot))
        snapshots.append(snapshot)
    audit = summarize_continuity(snapshots)
    if audit["total_observations"] != len(PINNED_RUNS):
        raise ValueError("unexpected_observation_count")

    result = {
        "status": "ARCHIVED_EVIDENCE_CHECKED",
        "pinned_run_count": len(PINNED_RUNS),
        "independently_observed_github_run_count": len(seen_ids),
        "github_success_not_quote_authenticity": True,
        "run_provenance": provenance,
        "continuity": audit,
        "market_data_values_redacted_from_summary": True,
        "no_new_public_market_requests": True,
        "orders": 0,
        "paper_fills": 0,
        "journal_writes": 0,
        "scheduler_enabled": False,
        "paper_trading_enabled": False,
        "live_trading_enabled": False,
        "prices_executable": False,
        "licensed_second_bist_source_verified": False,
        "long_term_reliability_proven": False,
    }
    json.dumps(result, allow_nan=False)
    return result


def load_evidence(root: Path) -> list[tuple[dict[str, Any], Any, Any]]:
    return [
        (
            pinned,
            _read_strict_json(root / str(pinned["run_id"]) / "run-metadata.json"),
            _read_strict_json(root / str(pinned["run_id"]) / pinned["file"]),
        )
        for pinned in PINNED_RUNS
    ]


def main() -> int:
    parser = argparse.ArgumentParser(description="Pinned GitHub observation artifacts: offline review")
    parser.add_argument("--evidence-root", type=Path, required=True)
    args = parser.parse_args()
    try:
        report = build_report(load_evidence(args.evidence_root))
        print(json.dumps(report, sort_keys=True, ensure_ascii=True, allow_nan=False))
        return 0
    except (OSError, ValueError, UnicodeError, TypeError, KeyError) as exc:
        print(json.dumps({"status": "BLOCKED", "reason": str(exc)[:120],
                          "orders": 0, "live_trading_enabled": False}))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
