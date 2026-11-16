# -*- coding: utf-8 -*-
"""Read-only 4x100 Yahoo batch progress; NEVER makes a data-provider request.

Only counts batches whose complete source, date, scope, stock list and
per-row evidence pass the existing batch-report validator. Corrupt reports
are listed for operator inspection, not silently treated as completed.
"""
from __future__ import annotations

from datetime import date
import math
from pathlib import Path
from typing import Any

from src.services.five_market_sample_validation import FOCUS_MARKETS
from src.services.four_market_batch_validation import (
    MAX_BATCH_SIZE,
    _batch_name,
    _read_bounded_json,
    _verify_batch,
)


def inspect_batch_progress(
    manifest: dict,
    *,
    as_of: date,
    output_dir: Path,
    batch_size: int = 10,
) -> dict[str, Any]:
    """Safely list verified, missing, corrupt and failed batches; no writes."""
    if not 1 <= batch_size <= MAX_BATCH_SIZE:
        raise ValueError("batch_size must be 1..25")
    if len(manifest["symbols"]) != 400:
        raise ValueError("Expected a complete source-dated 400-stock manifest")

    total = math.ceil(400 / batch_size)
    by_market = {
        market: {
            "target_symbols": 100,
            "checked_symbols": 0,
            "analyzed_symbols": 0,
            "failed_symbols": 0,
            "pending_symbols": 100,
        }
        for market in FOCUS_MARKETS
    }
    present: list[int] = []
    clean: list[int] = []
    with_failures: list[int] = []
    missing: list[int] = []
    invalid: list[dict[str, Any]] = []
    failures: list[dict[str, str | int]] = []

    for index in range(total):
        path = output_dir / _batch_name(index, total)
        if not path.exists():
            missing.append(index)
            continue
        try:
            checked = _verify_batch(
                _read_bounded_json(path),
                manifest,
                index=index,
                size=batch_size,
                as_of=as_of,
            )
        except (ValueError, OSError, TypeError, KeyError) as exc:
            # The file may be damaged or belong to a different dated universe.
            # Never include its rows/counters in the successful totals.
            invalid.append({
                "batch_index": index,
                "filename": path.name,
                "reason": str(exc)[:180],
            })
            continue

        present.append(index)
        failed_in_batch = False
        for row in checked["results"]:
            counts = by_market[row["market"]]
            counts["checked_symbols"] += 1
            if row["status"] == "analyzed":
                counts["analyzed_symbols"] += 1
            else:
                failed_in_batch = True
                counts["failed_symbols"] += 1
                failures.append({
                    "batch_index": index,
                    "market": row["market"],
                    "code": row["code"],
                    "status": row["status"],
                })
        (with_failures if failed_in_batch else clean).append(index)

    checked_total = sum(v["checked_symbols"] for v in by_market.values())
    analyzed_total = sum(v["analyzed_symbols"] for v in by_market.values())
    for market in FOCUS_MARKETS:
        by_market[market]["pending_symbols"] = (
            100 - by_market[market]["checked_symbols"]
        )

    if invalid:
        action = "inspect_invalid_batches"
    elif missing:
        action = "run_next_missing_batch"
    elif with_failures:
        action = "review_or_retry_failed_batches"
    else:
        action = "all_samples_passed"

    return {
        "scope": "etre_four_market_batch_progress",
        "as_of": as_of.isoformat(),
        "source_as_of": manifest["source_as_of"],
        "manifest_sha256": manifest["manifest_sha256"],
        "market_scope": list(FOCUS_MARKETS),
        "target_symbols_per_market": 100,
        "target_symbols_total": 400,
        "checked_symbols": checked_total,
        "analyzed_symbols": analyzed_total,
        "failed_symbols": checked_total - analyzed_total,
        "pending_symbols": 400 - checked_total,
        "checked_all": checked_total == 400,
        "all_analyzed": checked_total == 400 and analyzed_total == 400,
        "batch_size": batch_size,
        "batches_total": total,
        "verified_batch_indices": present,
        "clean_batch_indices": clean,
        "failed_batch_indices": with_failures,
        "missing_batch_indices": missing,
        "invalid_batches": invalid,
        "next_missing_batch_index": missing[0] if missing else None,
        "failed_rows": failures,
        "by_market": by_market,
        "next_action": action,
        "network_requests": 0,
        "note": (
            "Only verified historical Yahoo batch reports were counted. "
            "Missing or invalid batches are pending. A successful sample "
            "is not a current quote, full exchange coverage or a brokerage order."
        ),
    }
