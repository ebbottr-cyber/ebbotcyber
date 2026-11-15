# -*- coding: utf-8 -*-
"""Source-dated BIST100 constituents, not a live market-data feed.

This module intentionally does not download quotes, assume permanent index
membership, or add XU100.IS as a 101st stock.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
import json
from pathlib import Path
from typing import Any, Mapping

from src.services.bist_symbols import BIST100_INDEX_SYMBOL, normalize_bist_equity_symbol

_SNAPSHOT_PATH = Path(__file__).resolve().parents[1] / "data" / "bist100_constituents_2026q4.json"


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
    if len(additions) != 27 or len(exclusions) != 27 or len(substitutes) != 3:
        raise ValueError("BIST100 2026-Q4 official change counts mismatch")

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


def load_bist100_universe(for_date: date | None = None) -> Bist100Universe:
    """Load the snapshot for a trading date; refuse past/future stale membership.

    A valid ticker syntax does not prove a symbol has live Yahoo data.
    Callers must separately report quote coverage and unavailable tickers.
    """
    with _SNAPSHOT_PATH.open(encoding="utf-8") as handle:
        payload = json.load(handle)
    universe = validate_bist100_snapshot(payload)
    universe.require_effective_date(for_date if for_date is not None else date.today())
    return universe


def is_bist100_member(value: str | None, for_date: date | None = None) -> bool:
    """Check dated index membership (unlike generic .IS symbol validity)."""
    canonical = normalize_bist_equity_symbol(value)
    return canonical in load_bist100_universe(for_date).symbols if canonical else False
