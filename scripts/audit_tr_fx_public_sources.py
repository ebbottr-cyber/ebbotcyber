"""Manual, read-only Turkish indices/FX source availability check.

Only --fetch contacts the four fixed Yahoo daily history instruments and the
official TCMB today.xml bulletin via existing, guarded services. This does not
query a broker, discover new instruments, calculate order prices, or trade.
The JSON is observational: a successful CI run is NOT a passing data feed.
"""
from __future__ import annotations

import argparse
from datetime import date, datetime
import json
import math
from typing import Any
from zoneinfo import ZoneInfo

from src.services.tr_market_overview_service import (
    INSTRUMENTS, MAX_AGE_DAYS, SOURCE, build_overview,
)
from src.services.tcmb_try_display_service import (
    MAX_QUOTE_AGE_DAYS, get_tcmb_try_display_quotes,
)

EXPECTED_FX = ("USD", "EUR", "CNY")
ISTANBUL = ZoneInfo("Europe/Istanbul")


def _finite_positive(value: Any) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    try:
        result = float(value)
    except (OverflowError, TypeError, ValueError):
        return None
    return result if math.isfinite(result) and result > 0 else None


def _verified_day(raw: Any, today: date, maximum_age: int) -> str | None:
    if not isinstance(raw, str):
        return None
    try:
        parsed = date.fromisoformat(raw)
    except ValueError:
        return None
    return raw if 0 <= (today - parsed).days <= maximum_age else None


def summarize(
    overview: Any,
    bulletin: Any,
    *,
    today: date,
    observed_at: datetime,
) -> dict[str, Any]:
    """Fail closed on missing, stale, malformed, or unverified evidence."""
    items = overview.get("items") if isinstance(overview, dict) else None
    by_key: dict[str, dict] = {}
    if isinstance(items, list):
        for item in items:
            if not isinstance(item, dict):
                continue
            key = item.get("key")
            if isinstance(key, str):
                if key in by_key:
                    # Duplicate keys make this entire instrument untrustworthy.
                    by_key[key] = {}
                else:
                    by_key[key] = item

    checks: list[dict[str, Any]] = []
    for key, label, symbol, currency in INSTRUMENTS:
        item = by_key.get(key, {})
        price = _finite_positive(item.get("price"))
        as_of = _verified_day(item.get("as_of"), today, MAX_AGE_DAYS)
        verified = (
            item.get("key") == key
            and item.get("symbol") == symbol
            and item.get("currency") == currency
            and item.get("status") == "ready"
            and item.get("source") == SOURCE
            and as_of is not None and price is not None
        )
        checks.append({
            "key": key,
            "label": label,
            "symbol": symbol,
            "currency": currency,
            "status": "observed_delayed_daily" if verified else "unavailable_or_unverified",
            "source": SOURCE,
            "price": price if verified else None,
            "price_date": as_of if verified else None,
            "indicative_only": True,
            "executable_quote": False,
        })

    published: str | None = None
    quote_rows = []
    if isinstance(bulletin, dict):
        published = _verified_day(
            bulletin.get("as_of_date"), today, MAX_QUOTE_AGE_DAYS,
        ) if bulletin.get("source") == "TCMB" and bulletin.get("rate_kind") == "indicative_forex_selling" else None
        raw = bulletin.get("quotes")
        if published and isinstance(raw, list):
            quote_rows = raw

    counts: dict[str, int] = {}
    for row in quote_rows:
        if isinstance(row, dict):
            c = row.get("source_currency")
            if isinstance(c, str):
                counts[c] = counts.get(c, 0) + 1

    fx_checks = []
    for code in EXPECTED_FX:
        matches = [r for r in quote_rows if isinstance(r, dict) and r.get("source_currency") == code]
        r = matches[0] if len(matches) == 1 else {}
        rate = _finite_positive(r.get("try_per_unit"))
        valid = (
            published is not None
            and counts.get(code) == 1
            and r.get("source") == "TCMB"
            and r.get("source_currency") == code
            and r.get("target_currency") == "TRY"
            and type(r.get("source_unit")) is int
            and r.get("source_unit") == 1
            and r.get("as_of_date") == published
            and rate is not None
        )
        fx_checks.append({
            "currency": code,
            "target_currency": "TRY",
            "status": "observed_official_indicative" if valid else "unavailable_or_unverified",
            "source": "TCMB daily ForexSelling",
            "bulletin_date": published if valid else None,
            "try_per_unit": rate if valid else None,
            "executable_quote": False,
        })

    yahoo_ok = sum(r["status"] == "observed_delayed_daily" for r in checks)
    tcmb_ok = sum(r["status"] == "observed_official_indicative" for r in fx_checks)
    result = {
        "status": "READ_ONLY_OBSERVATION" if yahoo_ok or tcmb_ok else "NO_VALID_PROVIDER_QUOTES",
        "observed_at_istanbul": observed_at.astimezone(ISTANBUL).isoformat(),
        "as_of_local_date": today.isoformat(),
        "market_daily": {
            "expected_instruments": len(INSTRUMENTS),
            "verified_delayed_quotes": yahoo_ok,
            "missing_or_unverified": len(INSTRUMENTS) - yahoo_ok,
            "source": SOURCE,
            "checks": checks,
        },
        "official_tcmb": {
            "expected_currencies": len(EXPECTED_FX),
            "verified_indicative_rates": tcmb_ok,
            "missing_or_unverified": len(EXPECTED_FX) - tcmb_ok,
            "checks": fx_checks,
        },
        "unverified_gram_gold": True,
        "full_observation_coverage": yahoo_ok == len(INSTRUMENTS) and tcmb_ok == len(EXPECTED_FX),
        "research_only": True,
        "prices_executable": False,
        "orders": 0,
        "journal_writes": 0,
        "paper_fills": 0,
        "paper_trading_enabled": False,
        "live_trading_enabled": False,
        "scheduler_enabled": False,
    }
    # Strict JSON and no NaN/Infinity, even for malformed network responses.
    json.dumps(result, allow_nan=False)
    return result


def run(*, fetch: bool = False) -> int:
    if not fetch:
        print(json.dumps({
            "status": "DISABLED", "network_requests": 0, "orders": 0,
            "paper_trading_enabled": False, "live_trading_enabled": False,
        }, sort_keys=True))
        return 0
    now = datetime.now(ISTANBUL)
    try:
        overview = build_overview()
    except Exception:
        # Keep source outages visible rather than using a saved or guessed close.
        overview = {}
    try:
        bulletin = get_tcmb_try_display_quotes(today=now.date())
    except Exception:
        bulletin = {}
    result = summarize(overview, bulletin, today=now.date(), observed_at=now)
    print(json.dumps(result, sort_keys=True, ensure_ascii=True, allow_nan=False))
    return 0  # Means audit executed; availability is encoded in status and counts.


def main() -> int:
    p = argparse.ArgumentParser(description="Read-only BIST / TRY source observation; no trades")
    p.add_argument("--fetch", action="store_true", help="Opt in to fixed public price-data GET calls")
    return run(fetch=p.parse_args().fetch)


if __name__ == "__main__":
    raise SystemExit(main())
