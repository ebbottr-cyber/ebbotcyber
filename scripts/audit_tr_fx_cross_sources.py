"""Read-only, offline comparison of a *single* Yahoo/TCMB observation JSON.

Differences between delayed Yahoo daily data and official TCMB ForexSelling
are diagnostics only. They are NEVER interchangeable, trade-executable prices,
proof of independent BIST verification, or proof of a live market data SLA.
No network access, no database, no broker, no scheduled jobs.
"""
from __future__ import annotations

import argparse
from datetime import date
import json
import math
from pathlib import Path
from typing import Any

from src.services.tr_market_overview_service import SOURCE as MARKET_SOURCE


# Not an execution/risk threshold: only flag a large *indicative* discrepancy
# for manual review. The sources have different methodologies/timestamps.
DIAGNOSTIC_REVIEW_DIFFERENCE_PCT = 1.0
YAHOO_LAG_WATCH_DAYS = 1
TCMB_LAG_WATCH_DAYS = 2

FX_PAIRS = (
    ("USD", "usdtry", "TRY=X"),
    ("EUR", "eurtry", "EURTRY=X"),
)
BIST_KEYS = ("bist100", "bist30")



def _finite_positive(value: Any) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    try:
        v = float(value)
    except (OverflowError, TypeError, ValueError):
        return None
    return v if math.isfinite(v) and v > 0 else None


def _day_age(value: Any, today: date) -> int | None:
    if not isinstance(value, str):
        return None
    try:
        observed = date.fromisoformat(value)
    except ValueError:
        return None
    delta = (today - observed).days
    return delta if delta >= 0 else None


def _unique_by(rows: Any, field: str) -> dict[str, dict[str, Any]]:
    if not isinstance(rows, list):
        return {}
    result: dict[str, dict[str, Any]] = {}
    duplicates: set[str] = set()
    for row in rows:
        if not isinstance(row, dict):
            continue
        key = row.get(field)
        if not isinstance(key, str):
            continue
        if key in result:
            duplicates.add(key)
        else:
            result[key] = row
    return {k: v for k, v in result.items() if k not in duplicates}


def _yahoo(row: Any, symbol: str, today: date) -> tuple[float, str, int] | None:
    if not isinstance(row, dict):
        return None
    price = _finite_positive(row.get("price"))
    recorded_day = row.get("price_date")
    age = _day_age(recorded_day, today)
    if (row.get("symbol") != symbol
            or row.get("status") != "observed_delayed_daily"
            or row.get("source") != MARKET_SOURCE
            or row.get("executable_quote") is not False
            or row.get("indicative_only") is not True
            or price is None or age is None or age > 7):
        return None
    return price, recorded_day, age


def _tcmb(row: Any, currency: str, today: date) -> tuple[float, str, int] | None:
    if not isinstance(row, dict):
        return None
    value = _finite_positive(row.get("try_per_unit"))
    day = row.get("bulletin_date")
    age = _day_age(day, today)
    if (row.get("currency") != currency
            or row.get("target_currency") != "TRY"
            or row.get("status") != "observed_official_indicative"
            or row.get("source") != "TCMB daily ForexSelling"
            or row.get("executable_quote") is not False
            or value is None or age is None or age > 4):
        return None
    return value, day, age


def compare_observations(report: Any) -> dict[str, Any]:
    """Calculate diagnostics only from verified observation rows.

    This is intentionally NOT a second BIST data source.
    """
    if not isinstance(report, dict):
        raise ValueError("invalid_observation_report")
    raw_date = report.get("as_of_local_date")
    if not isinstance(raw_date, str):
        raise ValueError("missing_local_observation_date")
    try:
        today = date.fromisoformat(raw_date)
    except ValueError as exc:
        raise ValueError("invalid_local_observation_date") from exc
    if report.get("research_only") is not True or report.get("prices_executable") is not False:
        raise ValueError("not_a_readonly_observation")
    if (report.get("orders") != 0 or report.get("paper_fills") != 0
            or report.get("journal_writes") != 0
            or report.get("paper_trading_enabled") is not False
            or report.get("live_trading_enabled") is not False):
        raise ValueError("trade_activity_or_ambiguous_guard_flags")

    market = report.get("market_daily")
    fx = report.get("official_tcmb")
    market_rows = _unique_by(market.get("checks"), "key") if isinstance(market, dict) else {}
    fx_rows = _unique_by(fx.get("checks"), "currency") if isinstance(fx, dict) else {}
    comparisons = []
    alerts = []
    for currency, key, symbol in FX_PAIRS:
        left = _yahoo(market_rows.get(key), symbol, today)
        right = _tcmb(fx_rows.get(currency), currency, today)
        status = "insufficient_source_evidence"
        delta = None
        if left and right:
            if left[1] != right[1]:
                status = "different_publication_dates"
                alerts.append(f"{currency}_source_dates_mismatch")
            else:
                diff = abs(left[0] - right[0]) / right[0] * 100
                if math.isfinite(diff):
                    delta = round(diff, 6)
                    status = ("difference_for_manual_review"
                              if delta > DIAGNOSTIC_REVIEW_DIFFERENCE_PCT
                              else "difference_recorded_not_validation")
                    if delta > DIAGNOSTIC_REVIEW_DIFFERENCE_PCT:
                        alerts.append(f"{currency}_indicative_difference_review")
                else:
                    status = "difference_uncomputable"
                    alerts.append(f"{currency}_difference_uncomputable")
        else:
            alerts.append(f"{currency}_comparison_unavailable")

        if left and left[2] > YAHOO_LAG_WATCH_DAYS:
            alerts.append(f"{currency}_yahoo_daily_lag_watch")
        if right and right[2] > TCMB_LAG_WATCH_DAYS:
            alerts.append(f"{currency}_tcmb_bulletin_lag_watch")
        comparisons.append({
            "pair": f"{currency}/TRY",
            "status": status,
            "yahoo_daily_date": left[1] if left else None,
            "tcmb_forex_selling_date": right[1] if right else None,
            "yahoo_daily_age_calendar_days": left[2] if left else None,
            "tcmb_age_calendar_days": right[2] if right else None,
            "absolute_difference_pct_of_tcmb": delta,
            "note": "Different quote methodology and observation times; informational only.",
            "sources_interchangeable": False,
            "execution_quote_verified": False,
        })

    bist = []
    for key in BIST_KEYS:
        row = market_rows.get(key)
        symbol = "XU100.IS" if key == "bist100" else "XU030.IS"
        observation = _yahoo(row, symbol, today)
        if observation and observation[2] > YAHOO_LAG_WATCH_DAYS:
            alerts.append(f"{key}_yahoo_daily_lag_watch")
        if not observation:
            alerts.append(f"{key}_yahoo_daily_unavailable")
        bist.append({
            "key": key,
            "yahoo_daily_age_calendar_days": observation[2] if observation else None,
            "yahoo_daily_date": observation[1] if observation else None,
            "independent_second_source": "not_configured",
            "independently_confirmed": False,
            "execution_quote_verified": False,
        })
    cny = _tcmb(fx_rows.get("CNY"), "CNY", today)
    if cny and cny[2] > TCMB_LAG_WATCH_DAYS:
        alerts.append("CNY_tcmb_bulletin_lag_watch")
    if not cny:
        alerts.append("CNY_tcmb_bulletin_unavailable")
    result = {
        "status": "DIAGNOSTIC_ONLY",
        "as_of_local_date": raw_date,
        "comparison_threshold_pct": DIAGNOSTIC_REVIEW_DIFFERENCE_PCT,
        "threshold_purpose": "manual_review_not_trade_validation",
        "same_date_is_not_same_time": True,
        "yahoo_daily_lag_watch_days": YAHOO_LAG_WATCH_DAYS,
        "tcmb_bulletin_lag_watch_days": TCMB_LAG_WATCH_DAYS,
        "fx_pairs": comparisons,
        "bist_indices": bist,
        "cny": {
            "tcmb_date": cny[1] if cny else None,
            "independent_second_source": "not_configured",
            "independently_confirmed": False,
        },
        "alerts": sorted(set(alerts)),
        "network_requests": 0,
        "orders": 0,
        "paper_fills": 0,
        "journal_writes": 0,
        "research_only": True,
        "prices_executable": False,
        "paper_trading_enabled": False,
        "live_trading_enabled": False,
    }
    json.dumps(result, allow_nan=False)
    return result


def main() -> int:
    p = argparse.ArgumentParser(description="Offline Yahoo/TCMB indicative source difference report")
    p.add_argument("--input", type=Path, required=True,
                   help="JSON output of scripts.audit_tr_fx_public_sources (no network)")
    args = p.parse_args()
    # The existing observation workflow controls the path; never write to input.
    try:
        payload = args.input.read_text(encoding="utf-8")
        result = compare_observations(json.loads(payload))
        print(json.dumps(result, ensure_ascii=True, sort_keys=True, allow_nan=False))
        return 0
    except (OSError, ValueError, TypeError) as exc:
        print(json.dumps({"status": "BLOCKED", "reason": str(exc)[:120],
                          "orders": 0, "live_trading_enabled": False}))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
