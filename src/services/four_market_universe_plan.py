# -*- coding: utf-8 -*-
"""Build a *source-dated* ETRE four-market/400-ticker planning list.

Türkiye uses the already source-crosschecked BIST100 quarterly snapshot.
Other exchanges require operator-supplied, dated JSON rosters of 100 ACTUAL
listed equities apiece. This tool does not invent stocks, download tickers,
confirm website contents, fetch quotes, open SQLite or place trade orders.

The 'source_url' is provenance claimed by the operator, NOT online attestation.
Each Yahoo stock and brokerage permission still need separate verification.
"""
from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import date, timedelta
import json
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from src.services.bist100_universe import load_bist100_universe
from src.services.five_market_sample_validation import (
    FOCUS_MARKETS,
    build_custom_probes,
)

_MAX_ROSTER_BYTES = 100_000
_FRESHNESS_DAYS = 45


@dataclass(frozen=True)
class MarketRoster:
    market: str
    as_of: date
    symbols: tuple[str, ...]
    source_url: str
    source_name: str


def _source_url(value: Any) -> bool:
    if not isinstance(value, str) or len(value) > 500:
        return False
    parsed = urlparse(value)
    return (
        parsed.scheme == "https" and parsed.hostname is not None
        and parsed.username is None and parsed.password is None
        and parsed.hostname not in {"localhost", "127.0.0.1"}
        and not parsed.hostname.endswith(".local")
    )


def _load_foreign_roster(market: str, path: Path, *, as_of: date) -> MarketRoster:
    if market not in ("us", "de", "hk"):
        raise ValueError("Only US, DE and HK need external roster files")
    if not path.is_file() or path.stat().st_size > _MAX_ROSTER_BYTES:
        raise ValueError(f"{market}: roster missing or exceeds 100 KB")
    try:
        raw = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"{market}: unreadable roster JSON") from exc
    if not isinstance(raw, dict) or raw.get("market") != market:
        raise ValueError(f"{market}: roster market identity mismatch")
    try:
        dated = date.fromisoformat(raw["as_of"])
    except (KeyError, ValueError, TypeError) as exc:
        raise ValueError(f"{market}: invalid roster as_of date") from exc
    if not dated <= as_of or as_of - dated > timedelta(days=_FRESHNESS_DAYS):
        raise ValueError(f"{market}: roster older than 45 days or future dated")
    source_name = raw.get("source_name")
    if not isinstance(source_name, str) or not source_name.strip() or len(source_name) > 120:
        raise ValueError(f"{market}: descriptive source name required")
    source_url = raw.get("source_url")
    if not _source_url(source_url):
        raise ValueError(f"{market}: public HTTPS source_url required")
    values = raw.get("symbols")
    if not isinstance(values, list) or len(values) != 100 or not all(
        isinstance(code, str) and code.strip() == code and code == code.upper()
        for code in values
    ):
        raise ValueError(f"{market}: expected 100 canonical symbols")
    if len(set(values)) != 100:
        raise ValueError(f"{market}: duplicate symbols")

    # Reuse the operational routing contract to reject JP/CN/KR/TW, equities
    # masquerading as indexes, wrong suffixes, or a nonexistent Yahoo mapping.
    probes = build_custom_probes(tuple(values))
    if any(item.market != market for item in probes):
        raise ValueError(f"{market}: roster contains out-of-market symbols")
    return MarketRoster(market, dated, tuple(values), source_url, source_name)


def create_universe_plan(
    *,
    as_of: date,
    source_paths: dict[str, Path] | None = None,
) -> dict[str, Any]:
    if not isinstance(as_of, date):
        raise ValueError("as_of must be a date")
    selected = source_paths or {}
    if set(selected) - {"us", "de", "hk"}:
        raise ValueError("Unexpected market in source_paths")
    tr = load_bist100_universe(as_of)
    rosters: dict[str, MarketRoster] = {
        "tr": MarketRoster(
            "tr", tr.as_of, tr.symbols,
            tr.source_urls[0], "BIST100 2026-Q4 cross-checked source snapshot",
        )
    }
    errors: dict[str, str] = {}
    # Never hide a roster failure behind a fictitious 100/100 number.
    for market in ("us", "de", "hk"):
        if market not in selected:
            errors[market] = "source_roster_missing"
            continue
        try:
            rosters[market] = _load_foreign_roster(
                market, selected[market], as_of=as_of,
            )
        except (ValueError, OSError) as exc:
            errors[market] = str(exc)

    total = sum(len(r.symbols) for r in rosters.values())
    complete = set(rosters) == set(FOCUS_MARKETS) and total == 400
    result: dict[str, Any] = {
        "scope": "etre_four_market_source_dated_universe_plan",
        "as_of": as_of.isoformat(),
        "market_scope": list(FOCUS_MARKETS),
        "target_symbols_per_market": 100,
        "target_symbols_total": 400,
        "prepared_symbols": total,
        "remaining_symbols": 400 - total,
        "complete": complete,
        "markets": {
            market: {
                "count": len(rosters[market].symbols) if market in rosters else 0,
                "target": 100,
                "source_date": rosters[market].as_of.isoformat() if market in rosters else None,
                "source_name": rosters[market].source_name if market in rosters else None,
                "source_url": rosters[market].source_url if market in rosters else None,
                "status": "roster_provided" if market in rosters else errors[market],
            }
            for market in FOCUS_MARKETS
        },
        "note": (
            "BIST100 uses an existing source-crosschecked 2026-Q4 roster; "
            "foreign rosters are operator-supplied and MUST be checked against "
            "their cited source. This plan does not verify all Yahoo histories, "
            "listing status at run time, broker permissions, or real orders."
        ),
    }
    if complete:
        ordered = tuple(
            symbol for market in FOCUS_MARKETS for symbol in rosters[market].symbols
        )
        if len(set(ordered)) != 400:
            raise ValueError("Cross-market duplicate detected")
        probes = build_custom_probes(ordered)
        if len(probes) != 400:
            raise ValueError("Operational 400-symbol parser mismatch")
        result["symbols"] = list(ordered)
    else:
        # Do not provide export of a partial universe mislabeled as full.
        result["missing_markets"] = [
            market for market in FOCUS_MARKETS if market not in rosters
        ]
    return result


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Prepare a source-dated four-market 400-stock ticker universe (no data fetch)"
    )
    parser.add_argument("--as-of", type=date.fromisoformat, default=date.today())
    parser.add_argument("--us-roster", type=Path)
    parser.add_argument("--de-roster", type=Path)
    parser.add_argument("--hk-roster", type=Path)
    parser.add_argument("--report", type=Path)
    parser.add_argument(
        "--export-400", type=Path,
        help="Only exports when all four dated 100-stock rosters pass validation",
    )
    parser.add_argument(
        "--export-tr100", type=Path,
        help="Export the already verified BIST100 snapshot independently",
    )
    args = parser.parse_args()
    sources = {
        market: path for market, path in (
            ("us", args.us_roster), ("de", args.de_roster),
            ("hk", args.hk_roster),
        ) if path is not None
    }
    try:
        plan = create_universe_plan(as_of=args.as_of, source_paths=sources)
    except ValueError as exc:
        parser.error(str(exc))

    if args.export_tr100:
        tr = load_bist100_universe(args.as_of)
        args.export_tr100.write_text("\n".join(tr.symbols) + "\n", encoding="utf-8")
    if args.export_400:
        if not plan["complete"]:
            parser.error(
                "400-stock export blocked: verified 100-stock US/DE/HK rosters are "
                "not all provided. See per-market report; do not invent symbols."
            )
        args.export_400.write_text(
            "\n".join(plan["symbols"]) + "\n", encoding="utf-8",
        )
    output = json.dumps(plan, ensure_ascii=False, indent=2) + "\n"
    if args.report:
        args.report.write_text(output, encoding="utf-8")
    print(output, end="")


if __name__ == "__main__":
    main()
