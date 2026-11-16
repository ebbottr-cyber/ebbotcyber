# -*- coding: utf-8 -*-
"""Operator-run, read-only, resumable Yahoo *historical* check for 4 x 100.

The source-dated manifest must be built by four_market_universe_plan and
reviewed by an operator. No symbol roster is fabricated, no brokerage/LLM/DB
credentials are used, and NO orders are placed. Each invocation fetches at
most 25 symbols, producing a durable JSON report even on per-symbol errors.
A 400-symbol result is only 'fully checked' after all batches are present;
'fully analyzed' additionally requires 400 independently passed results.
"""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import date, timedelta
import hashlib
import json
import math
import os
from pathlib import Path
import tempfile
import time
from typing import Any, Callable
from urllib.parse import urlparse

from src.services.five_market_sample_validation import (
    FOCUS_MARKETS,
    build_custom_probes,
    validate_five_market_samples,
)
from src.services.five_market_report_reader import (
    FiveMarketReportInvalid,
    validate_five_market_sample_report,
)
from src.services.six_market_live_smoke import _fetch_yahoo_history

MAX_BATCH_SIZE = 25
DEFAULT_BATCH_SIZE = 10
MAX_MANIFEST_BYTES = 100_000
MAX_BATCH_REPORT_BYTES = 300_000
MAX_RETRY_ATTEMPTS = 5
MAX_ROSTER_AGE_DAYS = 45
CUSTOM_SCOPE = "etre_four_market_custom_historical_symbols"


def _date(value: Any) -> date:
    if not isinstance(value, str):
        raise ValueError("Manifest date is not ISO text")
    try:
        result = date.fromisoformat(value)
    except ValueError as exc:
        raise ValueError("Invalid manifest ISO date") from exc
    if result.isoformat() != value:
        raise ValueError("Noncanonical manifest ISO date")
    return result


def load_source_dated_manifest(path: Path, *, as_of: date) -> dict:
    """Reject absent/old/not-full 400-source plans BEFORE any Yahoo call."""
    if not path.is_file() or not 0 < path.stat().st_size <= MAX_MANIFEST_BYTES:
        raise ValueError("Missing or oversized 400-source manifest (100 KB max)")
    try:
        raw = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError("Could not read source-dated manifest") from exc
    if not isinstance(raw, dict) or raw.get("scope") != "etre_four_market_source_dated_universe_plan":
        raise ValueError("Wrong four-market source-plan identity")
    if raw.get("complete") is not True or raw.get("market_scope") != list(FOCUS_MARKETS):
        raise ValueError("Source plan incomplete or includes excluded countries")
    recorded = _date(raw.get("as_of"))
    if recorded > as_of or as_of - recorded > timedelta(days=MAX_ROSTER_AGE_DAYS):
        raise ValueError("Source plan is future dated or over 45 days old")
    if (raw.get("target_symbols_per_market") != 100
            or raw.get("target_symbols_total") != 400
            or raw.get("prepared_symbols") != 400
            or raw.get("remaining_symbols") != 0):
        raise ValueError("Source plan does not certify four sets of 100")
    symbols = raw.get("symbols")
    if not isinstance(symbols, list) or len(symbols) != 400 or not all(
        isinstance(s, str) and s == s.strip() and s == s.upper() for s in symbols
    ):
        raise ValueError("Manifest must include 400 canonical stock codes")
    probes = build_custom_probes(tuple(symbols))
    markets = [spec.market for spec in probes]
    expected_markets = [market for market in FOCUS_MARKETS for _ in range(100)]
    if markets != expected_markets:
        raise ValueError("Manifest symbols must be grouped as TR100, US100, DE100, HK100")
    items = raw.get("markets")
    if not isinstance(items, dict) or set(items) != set(FOCUS_MARKETS):
        raise ValueError("Per-market source records missing")
    for market in FOCUS_MARKETS:
        info = items[market]
        if not isinstance(info, dict) or info.get("status") != "roster_provided" or info.get("count") != 100:
            raise ValueError(f"{market}: source roster has not been provided")
        source_date = _date(info.get("source_date"))
        if source_date > recorded or recorded - source_date > timedelta(days=MAX_ROSTER_AGE_DAYS):
            raise ValueError(f"{market}: dated source is expired or future")
        if not isinstance(info.get("source_name"), str) or not info["source_name"].strip():
            raise ValueError(f"{market}: missing source description")
        url = info.get("source_url")
        if not isinstance(url, str) or len(url) > 500:
            raise ValueError(f"{market}: missing HTTPS source provenance")
        parsed = urlparse(url)
        if (parsed.scheme != "https" or not parsed.hostname or
                parsed.username or parsed.password or
                parsed.hostname in {"localhost", "127.0.0.1"} or
                parsed.hostname.endswith(".local")):
            raise ValueError(f"{market}: invalid public HTTPS source provenance")

    canonical = json.dumps(
        {
            "as_of": recorded.isoformat(), "symbols": symbols,
            "market_sources": {
                market: {
                    "source_date": items[market]["source_date"],
                    "source_name": items[market]["source_name"],
                    "source_url": items[market]["source_url"],
                }
                for market in FOCUS_MARKETS
            },
        },
        separators=(",", ":"), sort_keys=True, ensure_ascii=True,
    ).encode("utf-8")
    return {
        "symbols": tuple(symbols),
        "source_as_of": recorded.isoformat(),
        "manifest_sha256": hashlib.sha256(canonical).hexdigest(),
    }


def _batch_name(index: int, total: int) -> str:
    return f"batch-{index + 1:03d}-of-{total:03d}.json"


def _read_bounded_json(path: Path) -> dict:
    if not path.is_file() or not 0 < path.stat().st_size <= MAX_BATCH_REPORT_BYTES:
        raise ValueError("Missing or oversized batch report")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError("Could not read batch JSON") from exc
    if not isinstance(data, dict):
        raise ValueError("Batch report is not a JSON object")
    return data


def _verify_batch(raw: dict, manifest: dict, *, index: int, size: int, as_of: date) -> dict:
    symbols = manifest["symbols"]
    total = math.ceil(len(symbols) / size)
    if not 0 <= index < total:
        raise ValueError("Batch index outside complete source plan")
    expected = list(symbols[index * size:(index + 1) * size])
    meta = raw.get("_batch")
    if not isinstance(meta, dict) or meta != {
        "manifest_sha256": manifest["manifest_sha256"],
        "source_as_of": manifest["source_as_of"],
        "batch_index": index,
        "batch_size": size,
        "batches_total": total,
    }:
        raise ValueError("Batch does not belong to this exact dated manifest / batch plan")
    attempts = raw.get("_retry_attempts", 0)
    if type(attempts) is not int or not 0 <= attempts <= MAX_RETRY_ATTEMPTS:
        raise ValueError("Invalid batch retry counter")
    try:
        sanitized = validate_five_market_sample_report(raw)
    except FiveMarketReportInvalid as exc:
        raise ValueError("Saved batch report failed four-market integrity checks") from exc
    if sanitized["as_of"] != as_of.isoformat() or sanitized["scope"] != CUSTOM_SCOPE:
        raise ValueError("Batch must match the selected analysis date and custom scope")
    if [row["code"] for row in sanitized["results"]] != expected:
        raise ValueError("Batch contains missing/reordered/out-of-range stock codes")
    return sanitized


def _atomic_json(path: Path, data: dict) -> None:
    """One JSON file is published at a time; no partially written success files."""
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_name: str | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", dir=path.parent, prefix=".etre-", suffix=".tmp",
            delete=False,
        ) as handle:
            temp_name = handle.name
            json.dump(data, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_name, path)
    finally:
        if temp_name is not None and os.path.exists(temp_name):
            os.unlink(temp_name)


def _validated_summary_from_rows(results: list[dict], *, as_of: date) -> dict:
    """Recompute every market total from stock rows after a selective retry."""
    analyzed = sum(row["status"] == "analyzed" for row in results)
    summary = {}
    for market in FOCUS_MARKETS:
        subset = [row for row in results if row["market"] == market]
        failed = Counter(row["status"] for row in subset if row["status"] != "analyzed")
        passed = sum(row["status"] == "analyzed" for row in subset)
        summary[market] = {
            "checked_symbols": len(subset),
            "analyzed_symbols": passed,
            "target_symbols": 100,
            "remaining_to_target": 100 - len(subset),
            "sample_status": (
                "not_requested" if not subset
                else "samples_passed" if len(subset) == passed
                else "partial" if passed else "samples_failed"
            ),
            "failure_status_counts": dict(sorted(failed.items())),
        }
    merged = {
        "scope": CUSTOM_SCOPE, "source": "Yahoo Finance",
        "as_of": as_of.isoformat(),
        "checked_symbols": len(results),
        "analyzed_symbols": analyzed,
        "markets_checked": sum(bool(summary[m]["checked_symbols"]) for m in FOCUS_MARKETS),
        "market_scope": list(FOCUS_MARKETS),
        "target_symbols_per_market": 100, "target_symbols_total": 400,
        "remaining_to_target": 400 - len(results),
        "results": results, "by_market": summary,
    }
    # Output is compatible with the existing read-only Data Center viewer and
    # authenticated report endpoint, but not trusted as issuer attestation.
    valid = validate_five_market_sample_report(merged)
    return valid


def run_batch(
    manifest: dict,
    *,
    as_of: date,
    batch_index: int,
    output_dir: Path,
    batch_size: int = DEFAULT_BATCH_SIZE,
    resume: bool = False,
    retry_failed: bool = False,
    delay_seconds: float = 2.0,
    fetch_history: Callable[..., Any] = _fetch_yahoo_history,
    pause: Callable[[float], None] = time.sleep,
    **probe_kwargs: Any,
) -> dict:
    if not 1 <= batch_size <= MAX_BATCH_SIZE:
        raise ValueError("batch_size must be 1..25")
    if resume and retry_failed:
        raise ValueError("Select --resume or --retry-failed, not both")
    if not math.isfinite(delay_seconds) or not 0 <= delay_seconds <= 30:
        raise ValueError("delay_seconds must be between 0 and 30")
    symbols = manifest["symbols"]
    total = math.ceil(len(symbols) / batch_size)
    if not 0 <= batch_index < total:
        raise ValueError("Invalid batch index")
    output = output_dir / _batch_name(batch_index, total)
    subset = tuple(symbols[batch_index * batch_size:(batch_index + 1) * batch_size])
    calls = 0

    def paced_history(symbol: str, start: date, current: date):
        nonlocal calls
        if calls and delay_seconds:
            pause(delay_seconds)
        calls += 1
        return fetch_history(symbol, start, current)

    if retry_failed:
        if not output.exists():
            raise FileNotFoundError("Cannot retry failures before the original batch exists")
        prior = _read_bounded_json(output)
        checked = _verify_batch(prior, manifest, index=batch_index,
                                size=batch_size, as_of=as_of)
        failed = tuple(row["code"] for row in checked["results"]
                       if row["status"] != "analyzed")
        attempts = prior.get("_retry_attempts", 0)
        if not failed:
            return {**checked, "retried_symbols": 0,
                    "retry_attempts": attempts}
        if attempts >= MAX_RETRY_ATTEMPTS:
            raise ValueError("Retry limit reached; review provider errors manually")
        retried = validate_five_market_samples(
            as_of=as_of,
            symbols=failed,
            fetch_history=paced_history,
            **probe_kwargs,
        )
        retried_by_code = {row["code"]: row for row in retried["results"]}
        updated_rows = [retried_by_code.get(row["code"], row)
                        for row in checked["results"]]
        updated = _validated_summary_from_rows(updated_rows, as_of=as_of)
        updated["_batch"] = prior["_batch"]
        updated["_retry_attempts"] = attempts + 1
        _verify_batch(updated, manifest, index=batch_index,
                      size=batch_size, as_of=as_of)
        backup = output.with_name(
            f"{output.stem}.before-retry-{attempts + 1:02d}.json"
        )
        if backup.exists():
            raise FileExistsError("Previous retry audit backup already exists")
        _atomic_json(backup, prior)
        _atomic_json(output, updated)
        return {**updated, "retried_symbols": len(failed),
                "retry_attempts": attempts + 1}

    if output.exists():
        if not resume:
            raise FileExistsError(
                f"{output} exists; use --resume to skip or --retry-failed to recheck errors"
            )
        existing = _verify_batch(_read_bounded_json(output), manifest,
                                 index=batch_index, size=batch_size, as_of=as_of)
        return {**existing, "resumed_without_yahoo_requests": True}

    report = validate_five_market_samples(
        as_of=as_of,
        symbols=subset,
        fetch_history=paced_history,
        **probe_kwargs,
    )
    report["_batch"] = {
        "manifest_sha256": manifest["manifest_sha256"],
        "source_as_of": manifest["source_as_of"],
        "batch_index": batch_index,
        "batch_size": batch_size,
        "batches_total": total,
    }
    _verify_batch(report, manifest, index=batch_index, size=batch_size, as_of=as_of)
    _atomic_json(output, report)
    return report


def combine_batches(
    manifest: dict, *,
    as_of: date,
    output_dir: Path,
    batch_size: int = DEFAULT_BATCH_SIZE,
) -> dict:
    """Merge only identical, verified completed batches; never invent results."""
    if not 1 <= batch_size <= MAX_BATCH_SIZE:
        raise ValueError("batch_size must be 1..25")
    symbols = manifest["symbols"]
    total = math.ceil(len(symbols) / batch_size)
    results: list[dict] = []
    present: list[int] = []
    for index in range(total):
        path = output_dir / _batch_name(index, total)
        if not path.exists():
            continue
        rows = _verify_batch(_read_bounded_json(path), manifest, index=index,
                             size=batch_size, as_of=as_of)
        results.extend(rows["results"])
        present.append(index)
    if not results:
        return {
            "manifest_sha256": manifest["manifest_sha256"],
            "source_as_of": manifest["source_as_of"],
            "as_of": as_of.isoformat(), "requested_symbols": 400,
            "checked_symbols": 0, "analyzed_symbols": 0, "pending_symbols": 400,
            "checked_all": False, "all_analyzed": False,
            "completed_batches": 0, "batches_total": total,
            "missing_batch_indices": list(range(total)),
            "note": "No valid Yahoo result yet; cannot present a sample report.",
        }
    valid = _validated_summary_from_rows(results, as_of=as_of)
    valid.update({
        "manifest_sha256": manifest["manifest_sha256"],
        "source_as_of": manifest["source_as_of"],
        "requested_symbols": 400,
        "pending_symbols": 400 - len(results),
        "checked_all": len(results) == 400,
        "all_analyzed": len(results) == 400 and analyzed == 400,
        "completed_batches": len(present),
        "batches_total": total,
        "missing_batch_indices": [n for n in range(total) if n not in present],
        "note": (
            "Completed samples are historical Yahoo data checks, NOT a live quote, "
            "broker approval, investment recommendation or trading instruction."
        ),
    })
    return valid


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Operator-run resumable four-market Yahoo history batches, read-only"
    )
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--as-of", type=date.fromisoformat, default=date.today())
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--batch-size", type=int, default=DEFAULT_BATCH_SIZE)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--batch-index", type=int,
                      help="0-based batch number; one invocation checks at most 25 equities")
    mode.add_argument("--combine", action="store_true",
                      help="Combine previously completed batches, without contacting Yahoo")
    recovery = parser.add_mutually_exclusive_group()
    recovery.add_argument("--resume", action="store_true",
                          help="Skip any existing validated batch unchanged")
    recovery.add_argument("--retry-failed", action="store_true",
                          help="Recheck only failed stocks in an existing batch, with audit backup")
    parser.add_argument("--delay-seconds", type=float, default=2.0)
    parser.add_argument("--report", type=Path,
                        help="Output merged report JSON (with --combine)")
    args = parser.parse_args()
    if args.combine and (args.resume or args.retry_failed):
        parser.error("--combine cannot be used with --resume or --retry-failed")
    try:
        manifest = load_source_dated_manifest(args.manifest, as_of=args.as_of)
        if args.combine:
            result = combine_batches(
                manifest, as_of=args.as_of, output_dir=args.output_dir,
                batch_size=args.batch_size,
            )
            if args.report and result["checked_symbols"] > 0:
                _atomic_json(args.report, result)
        else:
            result = run_batch(
                manifest, as_of=args.as_of, output_dir=args.output_dir,
                batch_index=args.batch_index, batch_size=args.batch_size,
                resume=args.resume, retry_failed=args.retry_failed,
                delay_seconds=args.delay_seconds,
            )
    except (ValueError, FileExistsError, OSError) as exc:
        parser.error(str(exc))
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if args.combine:
        if not result["checked_all"]:
            raise SystemExit("Some of the 400 equities have not been checked (see pending_symbols)")
        if not result["all_analyzed"]:
            raise SystemExit("400 have been checked, but some Yahoo/technical checks failed")
    elif result["analyzed_symbols"] != result["checked_symbols"]:
        raise SystemExit("Batch saved with failures; inspect per-equity statuses")


if __name__ == "__main__":
    main()
