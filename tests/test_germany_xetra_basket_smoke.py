# -*- coding: utf-8 -*-
"""Offline three-German-stock smoke; all data injected, no network/orders."""
from datetime import date

import pandas as pd

from src.services.germany_xetra_basket_smoke import (
    GERMANY_BASKET_PROBES,
    probe_germany_xetra_basket,
)

AS_OF = date(2026, 11, 15)
LAST = date(2026, 11, 13)


def _ohlcv(*, last="2026-11-13"):
    dates = pd.bdate_range(end=last, periods=80)
    return pd.DataFrame({
        "Date": dates,
        "Open": [95.0 + i / 5 for i in range(80)],
        "High": [99.0 + i / 5 for i in range(80)],
        "Low": [92.0 + i / 5 for i in range(80)],
        "Close": [97.0 + i / 5 for i in range(80)],
        "Volume": [1000.0 + i for i in range(80)],
    })


def _check(**overrides):
    called = []
    kwargs = {
        "fetch_history": lambda symbol, *_: called.append(symbol) or _ohlcv(),
        "fetch_currency": lambda symbol: "EUR",
        "sessions_for_market": lambda market, *_: pd.DatetimeIndex([LAST]),
        "detect_market": lambda code: "de",
        "convert_ticker": lambda code: code,
        "analyzer": lambda frame, code: type("Result", (), {"signal_score": 73})(),
    }
    kwargs.update(overrides)
    return probe_germany_xetra_basket(as_of=AS_OF, **kwargs), called


def test_basket_has_three_distinct_xetra_tickers_not_us_symbols():
    assert [(p.code, p.yahoo, p.currency) for p in GERMANY_BASKET_PROBES] == [
        ("SAP.DE", "SAP.DE", "EUR"),
        ("SIE.DE", "SIE.DE", "EUR"),
        ("BMW.DE", "BMW.DE", "EUR"),
    ]
    assert {p.market for p in GERMANY_BASKET_PROBES} == {"de"}


def test_three_equities_report_individual_scores_and_currency():
    report, called = _check()
    assert report["scope"] == "germany_xetra_yahoo_three_equities"
    assert report["market"] == "de"
    assert "checked_markets" not in report
    assert "analyzed_markets" not in report
    assert report["checked_equities"] == report["analyzed_equities"] == 3
    assert called == ["SAP.DE", "SIE.DE", "BMW.DE"]
    assert [r["code"] for r in report["results"]] == called
    assert all(r["status"] == "analyzed" and r["currency_observed"] == "EUR"
               and r["technical_score"] == 73 and r["bars"] == 80
               for r in report["results"])


def test_failed_second_stock_is_not_hidden_by_two_successes():
    def history(symbol, *_):
        if symbol == "SIE.DE":
            raise ConnectionError("simulated Yahoo failure")
        return _ohlcv()

    report, _ = _check(fetch_history=history)
    assert report["checked_equities"] == 3
    assert report["analyzed_equities"] == 2
    assert [r["status"] for r in report["results"]] == [
        "analyzed", "fetch_error", "analyzed"
    ]
    assert report["results"][1]["error_type"] == "ConnectionError"


def test_wrong_bmw_currency_cannot_be_reported_as_success():
    report, _ = _check(fetch_currency=lambda symbol: "USD" if symbol == "BMW.DE" else "EUR")
    assert report["analyzed_equities"] == 2
    assert report["results"][2]["status"] == "currency_mismatch"
    assert report["results"][2]["currency_observed"] == "USD"


def test_xetra_routing_mismatch_never_queries_mismatched_stock():
    called = []

    def history(symbol, *_):
        called.append(symbol)
        return _ohlcv()

    report, _ = _check(
        detect_market=lambda symbol: "us" if symbol == "SIE.DE" else "de",
        fetch_history=history,
    )
    assert called == ["SAP.DE", "BMW.DE"]
    assert report["analyzed_equities"] == 2
    assert report["results"][1]["status"] == "routing_mismatch"


def test_stale_bmw_candle_fails_just_bmw():
    report, _ = _check(
        fetch_history=lambda symbol, *_: _ohlcv(
            last="2026-11-12" if symbol == "BMW.DE" else "2026-11-13"
        )
    )
    assert report["analyzed_equities"] == 2
    assert report["results"][2]["status"] == "stale_price"
    assert "technical_score" not in report["results"][2]
