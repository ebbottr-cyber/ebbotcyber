# -*- coding: utf-8 -*-
"""Fail-closed, read-only, admin-configured four-market batch progress JSON.

This verifies structural consistency and sanitizes display fields. It cannot
cryptographically attest upstream Yahoo data or original market membership.
No scanning, SQLite access, broker I/O, or HTTP-controlled filesystem paths.
"""
from __future__ import annotations

from datetime import date
import json
import math
import os
from pathlib import Path
import re
from typing import Any

from src.services.five_market_report_reader import _PATTERNS, _STATUSES

_MARKETS = ("tr", "us", "de", "hk")
_ACTIONS = {
    "inspect_invalid_batches",
    "run_next_missing_batch",
    "review_or_retry_failed_batches",
    "all_samples_passed",
}
_MAX_BYTES = 2_000_000
_SHA = re.compile(r"[0-9a-f]{64}\Z")


class FourMarketProgressUnavailable(Exception):
    """Operator has not configured a valid absolute progress file."""


class FourMarketProgressInvalid(Exception):
    """Progress JSON violates the 400-symbol batch report contract."""


def _require(ok: Any, message: str = "Inconsistent four-market progress") -> None:
    if not ok:
        raise FourMarketProgressInvalid(message)


def _number(value: Any, lo: int, hi: int) -> bool:
    return type(value) is int and lo <= value <= hi


def _date(value: Any) -> date:
    _require(isinstance(value, str) and bool(re.fullmatch(r"\d{4}-\d{2}-\d{2}", value)),
             "Invalid progress date")
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise FourMarketProgressInvalid("Invalid progress date") from exc


def _indices(value: Any, total: int) -> list[int]:
    _require(isinstance(value, list) and len(value) <= total, "Invalid batch index list")
    previous = -1
    clean: list[int] = []
    for num in value:
        _require(_number(num, 0, total - 1) and num > previous,
                 "Duplicate, unsorted or out-of-range batch index")
        clean.append(num)
        previous = num
    return clean


def validate_four_market_batch_progress(raw: Any) -> dict:
    """Recalculate counters from the verified batch partition; sanitize output."""
    _require(isinstance(raw, dict) and raw.get("scope") == "etre_four_market_batch_progress")
    as_of = _date(raw.get("as_of"))
    source_as_of = _date(raw.get("source_as_of"))
    _require(source_as_of <= as_of)
    digest = raw.get("manifest_sha256")
    _require(isinstance(digest, str) and bool(_SHA.fullmatch(digest)))
    _require(raw.get("market_scope") == list(_MARKETS)
             and raw.get("target_symbols_per_market") == 100
             and raw.get("target_symbols_total") == 400)
    size = raw.get("batch_size")
    _require(_number(size, 1, 25))
    total = math.ceil(400 / size)
    _require(raw.get("batches_total") == total)
    for key in ("checked_symbols", "analyzed_symbols", "failed_symbols", "pending_symbols"):
        _require(_number(raw.get(key), 0, 400))
    _require(raw.get("network_requests") == 0
             and type(raw.get("checked_all")) is bool
             and type(raw.get("all_analyzed")) is bool)

    verified = _indices(raw.get("verified_batch_indices"), total)
    clean = _indices(raw.get("clean_batch_indices"), total)
    failed = _indices(raw.get("failed_batch_indices"), total)
    missing = _indices(raw.get("missing_batch_indices"), total)
    _require(set(verified) == set(clean) | set(failed)
             and not set(clean) & set(failed), "Invalid clean/failed partition")

    invalid_rows = raw.get("invalid_batches")
    _require(isinstance(invalid_rows, list) and len(invalid_rows) <= total)
    invalid: list[dict] = []
    invalid_ids: set[int] = set()
    for item in invalid_rows:
        _require(isinstance(item, dict))
        index = item.get("batch_index")
        _require(_number(index, 0, total - 1) and index not in invalid_ids)
        expected_name = f"batch-{index + 1:03d}-of-{total:03d}.json"
        reason = item.get("reason")
        _require(item.get("filename") == expected_name
                 and isinstance(reason, str) and 0 < len(reason) <= 180)
        invalid_ids.add(index)
        invalid.append({"batch_index": index, "filename": expected_name, "reason": reason})
    _require(set(verified) | set(missing) | invalid_ids == set(range(total))
             and not (set(verified) & set(missing))
             and not (set(verified) & invalid_ids)
             and not (set(missing) & invalid_ids), "Incomplete/overlapping batch partition")
    next_missing = missing[0] if missing else None
    _require(raw.get("next_missing_batch_index") == next_missing)

    expected_market_checked = dict.fromkeys(_MARKETS, 0)
    for index in verified:
        start = index * size
        end = min(400, start + size)
        for m, market in enumerate(_MARKETS):
            left, right = m * 100, (m + 1) * 100
            expected_market_checked[market] += max(0, min(end, right) - max(start, left))

    market_rows = raw.get("by_market")
    _require(isinstance(market_rows, dict) and set(market_rows) == set(_MARKETS))
    by_market: dict[str, dict] = {}
    for market in _MARKETS:
        item = market_rows[market]
        _require(isinstance(item, dict) and item.get("target_symbols") == 100)
        for key in ("checked_symbols", "analyzed_symbols", "failed_symbols", "pending_symbols"):
            _require(_number(item.get(key), 0, 100))
        checked = expected_market_checked[market]
        passed = item["analyzed_symbols"]
        failed_stocks = item["failed_symbols"]
        _require(item["checked_symbols"] == checked and passed + failed_stocks == checked
                 and item["pending_symbols"] == 100 - checked)
        by_market[market] = {
            "target_symbols": 100,
            "checked_symbols": checked,
            "analyzed_symbols": passed,
            "failed_symbols": failed_stocks,
            "pending_symbols": 100 - checked,
        }
    checked = sum(v["checked_symbols"] for v in by_market.values())
    analyzed = sum(v["analyzed_symbols"] for v in by_market.values())
    _require(raw["checked_symbols"] == checked and raw["analyzed_symbols"] == analyzed
             and raw["failed_symbols"] == checked - analyzed
             and raw["pending_symbols"] == 400 - checked)
    _require(raw["checked_all"] is (checked == 400)
             and raw["all_analyzed"] is (analyzed == checked == 400))

    failed_rows = raw.get("failed_rows")
    _require(isinstance(failed_rows, list) and len(failed_rows) == checked - analyzed)
    failures: list[dict] = []
    seen: set[str] = set()
    counts = dict.fromkeys(_MARKETS, 0)
    batches_with_failures: set[int] = set()
    for item in failed_rows:
        _require(isinstance(item, dict))
        idx, market, code, status = (
            item.get("batch_index"), item.get("market"), item.get("code"), item.get("status")
        )
        _require(_number(idx, 0, total - 1) and idx in failed
                 and isinstance(market, str) and market in _MARKETS
                 and isinstance(code, str) and bool(_PATTERNS[market].fullmatch(code))
                 and code not in seen
                 and isinstance(status, str) and status in _STATUSES
                 and status != "analyzed")
        first, last = idx * size, min(400, (idx + 1) * size)
        ordinal = _MARKETS.index(market)
        _require(last > ordinal * 100 and first < (ordinal + 1) * 100)
        seen.add(code)
        counts[market] += 1
        batches_with_failures.add(idx)
        failures.append({"batch_index": idx, "market": market, "code": code, "status": status})
    _require(all(counts[market] == by_market[market]["failed_symbols"] for market in _MARKETS)
             and batches_with_failures == set(failed))

    action = ("inspect_invalid_batches" if invalid else
              "run_next_missing_batch" if missing else
              "review_or_retry_failed_batches" if failed else "all_samples_passed")
    _require(raw.get("next_action") == action and action in _ACTIONS)

    return {
        "scope": "etre_four_market_batch_progress",
        "as_of": as_of.isoformat(),
        "source_as_of": source_as_of.isoformat(),
        "manifest_sha256": digest,
        "market_scope": list(_MARKETS),
        "target_symbols_per_market": 100,
        "target_symbols_total": 400,
        "checked_symbols": checked,
        "analyzed_symbols": analyzed,
        "failed_symbols": checked - analyzed,
        "pending_symbols": 400 - checked,
        "checked_all": checked == 400,
        "all_analyzed": analyzed == checked == 400,
        "batch_size": size,
        "batches_total": total,
        "verified_batch_indices": verified,
        "clean_batch_indices": clean,
        "failed_batch_indices": failed,
        "missing_batch_indices": missing,
        "invalid_batches": invalid,
        "next_missing_batch_index": next_missing,
        "failed_rows": failures,
        "by_market": by_market,
        "next_action": action,
        "network_requests": 0,
    }


def load_configured_four_market_batch_progress() -> dict:
    """Load only the absolute operator-configured JSON status file."""
    chosen = os.getenv("ETRE_FOUR_MARKET_PROGRESS_PATH", "").strip()
    if not chosen:
        raise FourMarketProgressUnavailable("No progress report configured")
    path = Path(chosen)
    if not path.is_absolute() or path.is_symlink():
        raise FourMarketProgressUnavailable("Progress path must be an absolute regular file")
    try:
        if not path.is_file() or not 0 < path.stat().st_size <= _MAX_BYTES:
            raise FourMarketProgressUnavailable("Progress report missing or too large")
        with path.open("rb") as handle:
            content = handle.read(_MAX_BYTES + 1)
        if len(content) > _MAX_BYTES:
            raise FourMarketProgressUnavailable("Progress file is too large")
        return validate_four_market_batch_progress(json.loads(content.decode("utf-8")))
    except FourMarketProgressInvalid:
        raise
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise FourMarketProgressInvalid("Configured progress JSON is unreadable") from exc
