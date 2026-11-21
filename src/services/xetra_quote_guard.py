"""Fail-closed, opt-in Yahoo quote metadata checks for Xetra share candidates.

No broker calls, AI analysis, paper fills, private credentials, or orders.
A quote match does NOT prove Yahoo-to-ISIN mapping or broker tradability.
"""
from __future__ import annotations

import csv
from datetime import date, datetime, timezone
from io import StringIO
import json
import math
from pathlib import Path
import re
from typing import Any
from urllib.parse import quote
from urllib.request import Request, urlopen

from src.services.paper_universe_inventory import read_input

SOURCE = "deutsche_boerse_xetra_t7"
SYMBOL = re.compile(r"^[A-Z0-9]{1,16}\.DE$")
ISIN = re.compile(r"^[A-Z]{2}[A-Z0-9]{9}[0-9]$")
REQUIRED = {
    "market", "symbol", "source", "kind", "source_as_of_date",
    "isin", "price_symbol_verified",
}
MAX_SYMBOLS = 20
MAX_RESPONSE_BYTES = 2 * 1024 * 1024


def read_xetra_manifest(path: Path) -> dict[str, dict[str, str]]:
    """Require the original dated, *unverified* Xetra manifest."""
    reader = csv.DictReader(StringIO(read_input(path)))
    if not reader.fieldnames or not REQUIRED.issubset(reader.fieldnames):
        raise ValueError("invalid_xetra_manifest_headers")
    entries: dict[str, dict[str, str]] = {}
    for row in reader:
        if None in row or any(not isinstance(v, str) for v in row.values()):
            raise ValueError("invalid_xetra_manifest_row")
        symbol = row["symbol"]
        if (row["market"] != "de" or row["kind"] != "stock"
                or row["source"] != SOURCE or row["price_symbol_verified"] != "false"
                or not SYMBOL.fullmatch(symbol)
                or not ISIN.fullmatch(row["isin"])):
            raise ValueError("invalid_xetra_manifest_row")
        try:
            stamp = date.fromisoformat(row["source_as_of_date"])
        except ValueError as exc:
            raise ValueError("invalid_xetra_manifest_date") from exc
        if stamp > datetime.now(timezone.utc).date():
            raise ValueError("future_xetra_manifest_date")
        if symbol in entries:
            raise ValueError("duplicate_xetra_manifest_symbol")
        entries[symbol] = {
            "isin": row["isin"],
            "source_as_of_date": stamp.isoformat(),
        }
    if not entries:
        raise ValueError("empty_xetra_manifest")
    return entries


def assess_chart_metadata(symbol: str, payload: Any, *, now: datetime) -> dict[str, Any]:
    """Assess provider quote *metadata*, never quote execution or ISIN identity."""
    if now.tzinfo is None:
        raise ValueError("now_must_be_timezone_aware")
    now_utc = now.astimezone(timezone.utc)
    report: dict[str, Any] = {
        "symbol": symbol,
        "status": "BLOCKED",
        "reason": None,
        "quote_metadata_matched": False,
        "isin_identity_verified": False,
        "broker_access_verified": False,
        "real_time_price_verified": False,
        "orders": 0,
    }

    def block(reason: str) -> dict[str, Any]:
        report["reason"] = reason
        return report

    if not SYMBOL.fullmatch(symbol):
        return block("invalid_xetra_symbol")
    if not isinstance(payload, dict):
        return block("invalid_provider_json")
    chart = payload.get("chart")
    if not isinstance(chart, dict) or chart.get("error") is not None:
        return block("provider_error")
    results = chart.get("result")
    if not isinstance(results, list) or len(results) != 1 or not isinstance(results[0], dict):
        return block("missing_or_multiple_quote_results")
    metadata = results[0].get("meta")
    if not isinstance(metadata, dict):
        return block("missing_quote_metadata")

    if metadata.get("symbol") != symbol:
        return block("provider_symbol_mismatch")
    if metadata.get("currency") != "EUR":
        return block("provider_currency_not_eur")
    if metadata.get("instrumentType") != "EQUITY":
        return block("provider_not_equity")
    if str(metadata.get("fullExchangeName", "")).upper() != "XETRA":
        return block("provider_exchange_not_xetra")
    if metadata.get("exchangeTimezoneName") != "Europe/Berlin":
        return block("provider_timezone_not_berlin")

    price = metadata.get("regularMarketPrice")
    if isinstance(price, bool) or not isinstance(price, (float, int)):
        return block("missing_or_invalid_price")
    if not math.isfinite(price) or price <= 0:
        return block("missing_or_invalid_price")
    quote_time = metadata.get("regularMarketTime")
    if type(quote_time) is not int or quote_time <= 0:
        return block("missing_or_invalid_quote_time")
    age = (now_utc.timestamp() - quote_time) / 86400
    if age < -5 / 1440 or age > 7:
        return block("future_or_stale_quote")
    report.update({
        "status": "QUOTE_METADATA_MATCH",
        "reason": None,
        "quote_metadata_matched": True,
        "provider": "yahoo_finance_chart",
        "provider_currency": "EUR",
        "provider_exchange": "XETRA",
        "regular_market_price_eur": float(price),
        "regular_market_time_utc": datetime.fromtimestamp(
            quote_time, tz=timezone.utc).isoformat(),
        "quote_age_hours": round(max(0, age * 24), 2),
        "quote_may_be_delayed": True,
    })
    return report


def fetch_yahoo_chart(symbol: str, *, timeout: int = 8) -> Any:
    """One fixed, public, read-only endpoint; call ONLY after explicit opt-in."""
    if not SYMBOL.fullmatch(symbol):
        raise ValueError("invalid_xetra_symbol")
    endpoint = (
        "https://query1.finance.yahoo.com/v8/finance/chart/"
        + quote(symbol, safe="") + "?interval=1d&range=5d"
    )
    request = Request(endpoint, headers={
        "User-Agent": "EBBot-Xetra-Research/1.0 (read-only)",
        "Accept": "application/json",
    }, method="GET")
    with urlopen(request, timeout=timeout) as response:
        if response.status != 200:
            raise ValueError("provider_http_error")
        raw = response.read(MAX_RESPONSE_BYTES + 1)
        if len(raw) > MAX_RESPONSE_BYTES:
            raise ValueError("oversized_provider_response")
    return json.loads(raw)


def check_symbols(
    manifest: dict[str, dict[str, str]],
    symbols: list[str],
    provider_fetch,
    *,
    now: datetime,
) -> dict[str, Any]:
    """Never request an arbitrary or off-manifest symbol."""
    if not symbols or len(symbols) > MAX_SYMBOLS or len(set(symbols)) != len(symbols):
        raise ValueError("symbols_must_be_unique_and_between_1_and_20")
    if any(symbol not in manifest for symbol in symbols):
        raise ValueError("symbol_not_in_official_xetra_snapshot")
    checks = []
    for symbol in symbols:
        try:
            payload = provider_fetch(symbol)
        except Exception:
            checks.append({
                "symbol": symbol, "status": "BLOCKED",
                "reason": "provider_request_failed", "quote_metadata_matched": False,
                "isin_identity_verified": False, "broker_access_verified": False,
                "real_time_price_verified": False, "orders": 0,
            })
            continue
        check = assess_chart_metadata(symbol, payload, now=now)
        check["candidate_isin"] = manifest[symbol]["isin"]
        check["candidate_snapshot_date"] = manifest[symbol]["source_as_of_date"]
        checks.append(check)
    matched = sum(c["status"] == "QUOTE_METADATA_MATCH" for c in checks)
    return {
        "status": "QUOTE_METADATA_SAMPLE_ONLY" if matched == len(checks) else "BLOCKED",
        "candidate_count_in_manifest": len(manifest),
        "requested_symbols": len(checks),
        "quote_metadata_matches": matched,
        "blocked_count": len(checks) - matched,
        "observed_at_utc": now.astimezone(timezone.utc).isoformat(),
        "checks": checks,
        "all_isin_mappings_verified": False,
        "all_market_prices_verified": False,
        "paper_trading_enabled": False,
        "live_trading_enabled": False,
        "orders": 0,
    }
