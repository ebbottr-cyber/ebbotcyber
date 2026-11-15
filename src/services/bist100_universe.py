# -*- coding: utf-8 -*-
"""Source-dated BIST100 constituents, not a live market-data feed.

This module intentionally does not download quotes, assume permanent index
membership, or add XU100.IS as a 101st stock.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
import json
from pathlib import Path
from typing import Any, Mapping

from src.services.bist_symbols import BIST100_INDEX_SYMBOL, normalize_bist_equity_symbol

_SNAPSHOT_PATH = Path(__file__).resolve().parents[1] / "data" / "bist100_constituents_2026q4.json"
_SNAPSHOT_DIRECTORY = _SNAPSHOT_PATH.parent


def _quarter_start(target: date) -> date:
    """Start of the three-month XIST membership period, never a rolling window."""
    return date(target.year, ((target.month - 1) // 3) * 3 + 1, 1)


def _snapshot_filename(target: date) -> str:
    start = _quarter_start(target)
    return f"bist100_constituents_{start.year}q{(start.month - 1) // 3 + 1}.json"



@dataclass(frozen=True)
class Bist100Universe:
    effective_from: date
    effective_to: date
    as_of: date
    verified_on: date
    symbols: tuple[str, ...]
    additions: tuple[str, ...]
    exclusions: tuple[str, ...]
    substitutes: tuple[str, ...]
    source_urls: tuple[str, ...]

    def require_effective_date(self, target: date) -> None:
        if not (self.effective_from <= target <= self.effective_to):
            raise ValueError(
                "BIST100 constituent snapshot is not valid for "
                f"{target.isoformat()}; effective period is "
                f"{self.effective_from.isoformat()}..{self.effective_to.isoformat()}. "
                "Obtain a newer dated roster instead of silently reusing stale members."
            )


def _symbols(payload: Mapping[str, Any], key: str) -> tuple[str, ...]:
    values = payload.get(key)
    if not isinstance(values, list) or not all(isinstance(v, str) for v in values):
        raise ValueError(f"BIST100 {key} must be a list of ticker strings")
    symbols = tuple(values)
    if len(set(symbols)) != len(symbols):
        raise ValueError(f"BIST100 {key} contains duplicate tickers")
    if any(normalize_bist_equity_symbol(s) != s for s in symbols):
        raise ValueError(f"BIST100 {key} must contain canonical .IS equity codes only")
    return symbols


def validate_bist100_snapshot(payload: Mapping[str, Any]) -> Bist100Universe:
    """Fail closed on missing, contradictory or unproven 2026-Q4 membership."""
    if not isinstance(payload, Mapping):
        raise ValueError("BIST100 snapshot must be a JSON object")
    if payload.get("index") != "BIST100" or payload.get("benchmark") != BIST100_INDEX_SYMBOL:
        raise ValueError("BIST100 index/benchmark identity mismatch")
    if payload.get("currency") != "TRY" or payload.get("timezone") != "Europe/Istanbul":
        raise ValueError("BIST100 market metadata mismatch")

    try:
        start = date.fromisoformat(payload["effective_from"])
        end = date.fromisoformat(payload["effective_to"])
        as_of = date.fromisoformat(payload["as_of"])
        verified = date.fromisoformat(payload["verified_on"])
    except (TypeError, ValueError, KeyError) as exc:
        raise ValueError("BIST100 snapshot has invalid or missing ISO dates") from exc
    if start > end or not start <= as_of <= end or verified < as_of:
        raise ValueError("BIST100 snapshot dates are inconsistent")
    # Do not permit overlapping, gap-filling or artificially prolonged
    # rosters: every approved file covers exactly its named calendar quarter.
    if start != _quarter_start(start):
        raise ValueError("BIST100 snapshot dates must begin on a quarter boundary")
    next_start = date(start.year + (start.month == 10), (start.month % 12) + 3 if start.month != 10 else 1, 1)
    if end != next_start - timedelta(days=1):
        raise ValueError("BIST100 snapshot dates must cover exactly one quarter")

    sources = payload.get("sources")
    required_sources = ("official_periodic_changes", "full_roster", "independent_roster")
    if not isinstance(sources, dict) or any(
        not isinstance(sources.get(k), str) or not sources[k].startswith("https://")
        for k in required_sources
    ):
        raise ValueError("BIST100 source provenance is incomplete")

    symbols = _symbols(payload, "constituents")
    additions = _symbols(payload, "official_additions")
    exclusions = _symbols(payload, "official_exclusions")
    substitutes = _symbols(payload, "official_substitutes")
    members = set(symbols)
    if len(symbols) != 100 or symbols != tuple(sorted(symbols)):
        raise ValueError("BIST100 constituents must be exactly 100 unique sorted stocks")
    if not set(additions).issubset(members):
        raise ValueError("BIST100 official additions are missing from constituents")
    if (set(exclusions) | set(substitutes)) & members:
        raise ValueError("BIST100 removed or substitute stocks cannot be active members")
    if set(additions) & (set(exclusions) | set(substitutes)):
        raise ValueError("BIST100 change categories overlap")
    # The 27/27/3 counts belong ONLY to the verified 2026-Q4 official notice.
    # Future quarters must never be forced to reuse those old counts.
    if start == date(2026, 10, 1):
        if len(additions) != 27 or len(exclusions) != 27 or len(substitutes) != 3:
            raise ValueError("BIST100 2026-Q4 official change counts mismatch")
    elif len(additions) != len(exclusions):
        raise ValueError("BIST100 new quarter additions/exclusions counts disagree")

    return Bist100Universe(
        effective_from=start,
        effective_to=end,
        as_of=as_of,
        verified_on=verified,
        symbols=symbols,
        additions=additions,
        exclusions=exclusions,
        substitutes=substitutes,
        source_urls=tuple(sources[k] for k in required_sources),
    )


def _read_quarter_snapshot(target: date) -> Bist100Universe:
    """Read only the exact quarter's checked-in JSON; never search or fall back."""
    path = _SNAPSHOT_DIRECTORY / _snapshot_filename(target)
    if path.is_symlink() or not path.is_file():
        raise ValueError(
            f"BIST100 constituent snapshot is not valid for {target.isoformat()}: "
            f"reviewed {_snapshot_filename(target)} is missing; "
            "do not reuse an earlier quarter"
        )
    with path.open(encoding="utf-8") as handle:
        payload = json.load(handle)
    universe = validate_bist100_snapshot(payload)
    universe.require_effective_date(target)
    return universe


def load_bist100_universe(for_date: date | None = None) -> Bist100Universe:
    """Read exactly one source-reviewed BIST100 quarter, or fail closed.

    The existing historical 2026-Q4 candidate is retained without changing
    its official 27 additions / 27 exclusions / 3 substitutions. For new
    periods the candidate must be independently source-reviewed and checked
    into this repository; its additions and exclusions must exactly equal
    the difference from the previous quarter, not merely pass a 100-count.
    No network, runtime path override, automatic ticker reuse or DB access.
    """
    target = for_date if for_date is not None else date.today()
    universe = _read_quarter_snapshot(target)
    if universe.effective_from == date(2026, 10, 1):
        return universe

    predecessor_date = universe.effective_from - timedelta(days=1)
    previous = _read_quarter_snapshot(predecessor_date)
    if previous.effective_to != predecessor_date:
        raise ValueError("BIST100 predecessor roster must end immediately before new quarter")
    previous_members = set(previous.symbols)
    next_members = set(universe.symbols)
    if (next_members - previous_members != set(universe.additions)
            or previous_members - next_members != set(universe.exclusions)):
        raise ValueError(
            "BIST100 quarter additions/exclusions do not match actual prior roster changes"
        )
    if universe.source_urls[0] == previous.source_urls[0]:
        raise ValueError("BIST100 new quarter reuses previous official announcement")
    return universe


def is_bist100_member(value: str | None, for_date: date | None = None) -> bool:
    """Check dated index membership (unlike generic .IS symbol validity)."""
    canonical = normalize_bist_equity_symbol(value)
    return canonical in load_bist100_universe(for_date).symbols if canonical else False
