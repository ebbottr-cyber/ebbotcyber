# -*- coding: utf-8 -*-
"""Six-market Yahoo smoke: offline behavior contracts, no network/trades."""
from datetime import date

import pandas as pd
import pytest

from src.services.six_market_live_smoke import PROBES, probe_six_markets

AS_OF = date(2026, 11, 15)
LAST = date(2026, 11, 13)


def _daily(*, count=80, last="2026-11-13"):
    days = pd.bdate_range(end=last, periods=count)
    return pd.DataFrame({
        "Date": days,
        "Open": [95.0 + i / 5 for i in range(count)],
        "High": [99.0 + i / 5 for i in range(count)],
        "Low": [92.0 + i / 5 for i in range(count)],
        "Close": [97.0 + i / 5 for i in range(count)],
        "Volume": [1000.0 + i for i in range(count)],
    })


def _call(*, history=None, currencies=None, sessions=None, detected=None, converted=None, analyzer=None):
    expected = {spec.code: spec.market for spec in PROBES}
    tickers = {spec.code: spec.yahoo for spec in PROBES}
    money = {spec.yahoo: spec.currency for spec in PROBES}
    calls = []

    def get_frame(symbol, start, end):
        calls.append(symbol)
        return history(symbol, start, end) if history else _daily()

    report = probe_six_markets(
        as_of=AS_OF,
        fetch_history=get_frame,
        fetch_currency=currencies or (lambda symbol: money[symbol]),
        sessions_for_market=sessions or (lambda market, start, end: pd.DatetimeIndex([LAST])),
        detect_market=detected or expected.get,
        convert_ticker=converted or tickers.get,
        analyzer=analyzer or (lambda frame, code: type("Result", (), {"signal_score": 75})()),
    )
    return report, calls


def test_all_six_valid_market_probes_have_unique_symbols_and_currencies():
    assert len(PROBES) == 6
    assert {p.market for p in PROBES} == {"cn", "hk", "us", "jp", "kr", "tw"}
    assert len({p.code for p in PROBES}) == len({p.yahoo for p in PROBES}) == 6
    assert {p.currency for p in PROBES} == {"CNY", "HKD", "USD", "JPY", "KRW", "TWD"}


def test_valid_six_markets_need_six_separate_histories_and_scores():
    report, calls = _call()
    assert report["scope"] == "six_market_yahoo_fallback_one_symbol_each"
    assert report["analyzed_markets"] == 6
    assert len(calls) == 6
    assert [x["status"] for x in report["results"]] == ["analyzed"] * 6
    assert all(x["bars"] == 80 and x["technical_score"] == 75 for x in report["results"])


def test_one_provider_failure_does_not_hide_other_markets():
    failed = PROBES[1].yahoo

    def history(symbol, *_):
        if symbol == failed:
            raise ConnectionError("simulated disconnected market")
        return _daily()

    report, calls = _call(history=history)
    assert len(calls) == 6
    assert report["checked_markets"] == 6
    assert report["analyzed_markets"] == 5
    assert report["results"][1]["status"] == "fetch_error"
    assert report["results"][1]["error_type"] == "ConnectionError"


def test_unknown_currency_does_not_create_a_false_success():
    report, _ = _call(currencies=lambda symbol: None)
    assert report["analyzed_markets"] == 0
    assert {x["status"] for x in report["results"]} == {"currency_unverified"}


def test_missing_calendar_fails_before_fetching_any_prices():
    report, called = _call(sessions=lambda *_: None)
    assert called == []
    assert report["analyzed_markets"] == 0
    assert {x["status"] for x in report["results"]} == {"calendar_unavailable"}


def test_mismatched_routing_never_downloads_a_different_market():
    report, called = _call(converted=lambda code: "AAPL")
    assert called == ["AAPL"]
    assert report["analyzed_markets"] == 1
    assert report["results"][0]["status"] == "routing_mismatch"


@pytest.mark.parametrize("input_frame,status", [
    (_daily(count=34), "insufficient_history"),
    (_daily(last="2026-11-12"), "stale_price"),
    (_daily().assign(High=0.1), "invalid_data"),
    (_daily().assign(Close=float("nan")), "invalid_data"),
])
def test_invalid_or_partial_ohlcv_is_not_analyzed(input_frame, status):
    report, _ = _call(history=lambda *_: input_frame)
    assert report["analyzed_markets"] == 0
    assert {x["status"] for x in report["results"]} == {status}


def test_live_bot_symbol_detection_and_yahoo_conversion_contracts():
    from data_provider.yfinance_fetcher import YfinanceFetcher
    from src.core.trading_calendar import get_market_for_stock

    provider = YfinanceFetcher()
    for spec in PROBES:
        assert get_market_for_stock(spec.code) == spec.market
        assert provider._convert_stock_code(spec.code) == spec.yahoo


def test_existing_analyzer_smoke_needs_no_llm_or_trades():
    from src.stock_analyzer import StockTrendAnalyzer

    report, called = _call(analyzer=StockTrendAnalyzer().analyze)
    assert len(called) == 6
    assert report["analyzed_markets"] == 6
    assert all(0 <= r["technical_score"] <= 100 for r in report["results"])
