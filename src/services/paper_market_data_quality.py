"""Offline validation for complete BIST and Binance price snapshots.

Research only: Spot 24h window end is NOT last-trade time; futures mark price
is NOT an executable quote. No wallets, trading, PnL, persistence or schedules.
"""
from __future__ import annotations

import csv
from datetime import date
from decimal import Decimal, InvalidOperation
import io
import json
from typing import Any

MAX_MARK_AGE_MS = 120_000
MAX_FUTURE_SKEW_MS = 10_000
MAX_DAILY_AGE_DAYS = 7


def _positive(value: Any) -> bool:
    if not isinstance(value, str) or not 1 <= len(value) <= 80:
        return False
    try:
        number = Decimal(value)
        return number.is_finite() and number > 0
    except (ValueError, InvalidOperation):
        return False


def _read_objects(raw: str, label: str) -> list[dict]:
    try:
        values = json.loads(raw)
    except (ValueError, TypeError) as exc:
        raise ValueError(label + "_invalid_json") from exc
    if not isinstance(values, list) or any(not isinstance(v, dict) for v in values):
        raise ValueError(label + "_invalid_array")
    return values


def _unique(rows: list[dict], label: str) -> dict[str, dict]:
    result: dict[str, dict] = {}
    for index, row in enumerate(rows):
        symbol = row.get("symbol")
        if (not isinstance(symbol, str) or not 1 <= len(symbol) <= 128
                or symbol != symbol.strip() or not symbol.isprintable()):
            raise ValueError(f"{label}_invalid_symbol_at_{index}")
        if symbol in result:
            raise ValueError(f"{label}_duplicate_symbol_at_{index}")
        result[symbol] = row
    return result


def active_spot_assets(raw: str) -> set[str]:
    try:
        payload = json.loads(raw)
    except (ValueError, TypeError) as exc:
        raise ValueError("invalid_spot_inventory_json") from exc
    if not isinstance(payload, dict) or not isinstance(payload.get("assets"), list):
        raise ValueError("invalid_spot_inventory")
    active: set[str] = set()
    for row in payload["assets"]:
        if not isinstance(row, dict) or row.get("network") != "binance_spot_catalog":
            raise ValueError("invalid_spot_inventory_record")
        if row.get("active") is True:
            symbol = row.get("symbol")
            if not isinstance(symbol, str) or not symbol or symbol in active:
                raise ValueError("invalid_spot_asset_symbol")
            active.add(symbol)
    return active


def _spot_price_issue(tick: dict) -> str | None:
    """Reason codes are diagnostic, NOT evidence that an asset is delisted.

    Binance 24h 'count' is the number of trades in the rolling window.
    Neither the count nor 'closeTime' establishes last-trade freshness.
    """
    count = tick.get("count")
    if count is not None and (type(count) is not int or count < 0):
        return "invalid_24h_trade_count"
    raw = tick.get("lastPrice")
    if _positive(raw):
        return None
    if raw is None:
        return "missing_last_price"
    if not isinstance(raw, str):
        return "non_string_last_price"
    try:
        value = Decimal(raw)
    except (ValueError, InvalidOperation):
        return "non_numeric_last_price"
    if not value.is_finite():
        return "non_finite_last_price"
    if value <= 0 and count == 0:
        return "nonpositive_last_price_no_trades_24h"
    if value <= 0:
        return "nonpositive_last_price"
    return "unusable_last_price"


def check_spot(exchange_raw: str, ticker_raw: str, assets: set[str]) -> dict:
    """All TRADING Spot pairs, not a top-N; quote time is unverified."""
    try:
        exchange = json.loads(exchange_raw)
    except (TypeError, ValueError) as exc:
        raise ValueError("invalid_spot_exchange_json") from exc
    if not isinstance(exchange, dict) or not isinstance(exchange.get("symbols"), list):
        raise ValueError("invalid_spot_exchange_info")
    pairs = _unique(exchange["symbols"], "spot_exchange")
    prices = _unique(_read_objects(ticker_raw, "spot_24h"), "spot_24h")
    expected: set[str] = set()
    current_assets: set[str] = set()
    for symbol, pair in pairs.items():
        if pair.get("status") == "TRADING" and pair.get("isSpotTradingAllowed") is True:
            base, quote = pair.get("baseAsset"), pair.get("quoteAsset")
            if not isinstance(base, str) or not isinstance(quote, str):
                raise ValueError("invalid_spot_assets")
            expected.add(symbol)
            current_assets.update((base, quote))
    positive = 0
    invalid_symbols: list[str] = []
    invalid_reasons: dict[str, str] = {}
    zero_trade_symbols: list[str] = []
    missing_symbols: list[str] = []
    for symbol in sorted(expected):
        row = prices.get(symbol)
        if row is None:
            missing_symbols.append(symbol)
        else:
            issue = _spot_price_issue(row)
            # A positive indicative lastPrice can still have zero trades in
            # the rolling period. Report this separately, never equate a
            # window statistic with executable last-trade freshness.
            if row.get("count") == 0 and type(row.get("count")) is int:
                zero_trade_symbols.append(symbol)
            if issue is None:
                positive += 1
            else:
                invalid_symbols.append(symbol)
                invalid_reasons[symbol] = issue
    return {
        "price_kind": "spot_24h_last_price_indicative",
        "timestamp_kind": "rolling_window_end_not_last_trade",
        "expected_active_pairs": len(expected),
        "positive_price_pairs": positive,
        "missing_pairs": len(missing_symbols),
        "missing_price_symbols": missing_symbols,
        "invalid_price_pairs": len(invalid_symbols),
        "invalid_price_symbols": invalid_symbols,
        "invalid_price_reasons": invalid_reasons,
        "zero_trades_24h_symbols": zero_trade_symbols,
        "zero_trades_24h_pairs": len(zero_trade_symbols),
        "issue_codes_are_diagnostics_not_delisting_proof": True,
        "saved_active_assets": len(assets),
        "current_active_assets": len(current_assets),
        "saved_assets_not_current": len(assets - current_assets),
        "current_assets_not_saved": len(current_assets - assets),
        "verified_trade_event_times": 0,
        "executable_prices": 0,
        "paper_ready": False,
    }


def check_futures(contracts_raw: str, marks_raw: str, *, market: str,
                  now_ms: int) -> dict:
    if market not in ("binance_usdm_futures", "binance_coinm_futures"):
        raise ValueError("unsupported_futures_market")
    if type(now_ms) is not int or now_ms <= 0:
        raise ValueError("invalid_clock")
    try:
        manifest = json.loads(contracts_raw)
    except (TypeError, ValueError) as exc:
        raise ValueError("invalid_futures_inventory_json") from exc
    if not isinstance(manifest, dict) or not isinstance(manifest.get("contracts"), list):
        raise ValueError("invalid_futures_inventory")
    expected: dict[str, dict] = {}
    for index, row in enumerate(manifest["contracts"]):
        if not isinstance(row, dict) or row.get("market") != market:
            raise ValueError(f"invalid_futures_market_at_{index}")
        symbol = row.get("symbol")
        if not isinstance(symbol, str) or not symbol or symbol in expected:
            raise ValueError(f"invalid_or_duplicate_futures_symbol_at_{index}")
        expected[symbol] = row
    mark_rows = _unique(_read_objects(marks_raw, "futures_marks"), "futures_marks")
    target = {symbol: row for symbol, row in expected.items() if row.get("active") is True}
    fresh = stale = invalid = missing = 0
    for symbol in target:
        mark = mark_rows.get(symbol)
        if mark is None:
            missing += 1
            continue
        if not _positive(mark.get("markPrice")) or type(mark.get("time")) is not int:
            invalid += 1
            continue
        age_ms = now_ms - mark["time"]
        if age_ms > MAX_MARK_AGE_MS or age_ms < -MAX_FUTURE_SKEW_MS:
            stale += 1
        else:
            fresh += 1
    sizes_missing = sum(
        1 for row in target.values()
        if market == "binance_coinm_futures"
        and not _positive(row.get("contract_size_unverified"))
    )
    return {
        "market": market,
        "price_kind": "mark_price_not_executable",
        "timestamp_kind": "provider_mark_time_ms",
        "expected_active_contracts": len(target),
        "fresh_mark_count": fresh,
        "stale_mark_count": stale,
        "invalid_mark_count": invalid,
        "missing_mark_count": missing,
        "coinm_missing_contract_size": sizes_missing,
        "funding_and_liquidation_model_verified": False,
        "executable_prices": 0,
        "paper_ready": False,
    }


def check_bist(kap_csv: str, daily_csv: str | None, *, today: date) -> dict:
    """Daily close bars, when provided, remain indicative and not intraday."""
    symbols: set[str] = set()
    for index, row in enumerate(csv.DictReader(io.StringIO(kap_csv))):
        symbol = row.get("symbol")
        if (not isinstance(symbol, str) or not symbol.endswith(".IS")
                or not symbol[:-3].isalnum() or row.get("market") != "tr"
                or symbol in symbols):
            raise ValueError(f"invalid_or_duplicate_kap_symbol_at_{index}")
        symbols.add(symbol)
    if not symbols:
        raise ValueError("empty_kap_inventory")
    if daily_csv is None:
        return {
            "bist_company_code_candidates": len(symbols),
            "daily_bars_supplied": False,
            "recent_daily_close": 0,
            "missing_close": len(symbols),
            "invalid_close": 0,
            "stale_close": 0,
            "market_listing_verified": False,
            "intraday_fresh_quotes": 0,
            "paper_ready": False,
        }
    reader = csv.DictReader(io.StringIO(daily_csv))
    if not reader.fieldnames or not {"symbol", "close", "as_of", "source", "currency"}.issubset(reader.fieldnames):
        raise ValueError("invalid_daily_bar_headers")
    rows: dict[str, dict] = {}
    for row in reader:
        symbol = row["symbol"]
        if not symbol or symbol in rows:
            raise ValueError("invalid_or_duplicate_daily_bar_symbol")
        rows[symbol] = row
    recent = stale = invalid = missing = 0
    for symbol in symbols:
        row = rows.get(symbol)
        if row is None:
            missing += 1
        elif not _positive(row.get("close")) or row.get("currency") != "TRY" or not row.get("source"):
            invalid += 1
        else:
            try:
                age_days = (today - date.fromisoformat(row["as_of"])).days
            except (ValueError, TypeError):
                invalid += 1
                continue
            if 0 <= age_days <= MAX_DAILY_AGE_DAYS:
                recent += 1
            else:
                stale += 1
    return {
        "bist_company_code_candidates": len(symbols),
        "daily_bars_supplied": True,
        "recent_daily_close": recent,
        "missing_close": missing,
        "invalid_close": invalid,
        "stale_close": stale,
        "market_listing_verified": False,
        "exchange_calendar_verified": False,
        "intraday_fresh_quotes": 0,
        "paper_ready": False,
    }
