# -*- coding: utf-8 -*-
"""Offline Xetra smoke contract; all Yahoo/calendar data injected, no network."""
from datetime import date

import pandas as pd

from src.services.germany_xetra_live_smoke import GERMANY_PROBES, probe_germany_xetra


AS_OF = date(2026, 11, 15)
LAST = date(2026, 11, 13)


def _ohlcv(last="2026-11-13"):
    days = pd.bdate_range(end=last, periods=80)
    return pd.DataFrame({
        "Date": days,
        "Open": [95.0 + i / 5 for i in range(80)],
        "High": [99.0 + i / 5 for i in range(80)],
        "Low": [92.0 + i / 5 for i in range(80)],
        "Close": [97.0 + i / 5 for i in range(80)],
        "Volume": [1000.0 + i for i in range(80)],
    })


def _probe(**overrides):
    kwargs = {
        "fetch_history": lambda symbol, *_: _ohlcv(),
        "fetch_currency": lambda symbol: "EUR",
        "sessions_for_market": lambda market, *_: pd.DatetimeIndex([LAST]),
        "detect_market": lambda symbol: "de",
        "convert_ticker": lambda symbol: symbol,
        "analyzer": lambda frame, symbol: type("Result", (), {"signal_score": 81})(),
    }
    kwargs.update(overrides)
    return probe_germany_xetra(as_of=AS_OF, **kwargs)


def test_xetra_single_symbol_scope_uses_eur_only():
    assert [(x.market, x.code, x.yahoo, x.currency) for x in GERMANY_PROBES] == [
        ("de", "SAP.DE", "SAP.DE", "EUR")
    ]
    report = _probe()
    assert report["scope"] == "germany_xetra_yahoo_one_symbol"
    assert report["checked_markets"] == report["analyzed_markets"] == 1
    result = report["results"][0]
    assert result["market"] == "de"
    assert result["status"] == "analyzed"
    assert result["bars"] == 80
    assert result["technical_score"] == 81
    assert result["currency_observed"] == "EUR"


def test_xetra_wrong_currency_must_not_succeed():
    report = _probe(fetch_currency=lambda symbol: "USD")
    assert report["analyzed_markets"] == 0
    assert report["results"][0]["status"] == "currency_mismatch"


def test_xetra_missing_session_prevents_any_network_fetch():
    called = []
    report = _probe(
        sessions_for_market=lambda market, *_: None,
        fetch_history=lambda *args: called.append(args),
    )
    assert report["analyzed_markets"] == 0
    assert report["results"][0]["status"] == "calendar_unavailable"
    assert called == []


def test_xetra_route_mismatch_never_queries_yahoo():
    called = []
    report = _probe(
        detect_market=lambda symbol: "us",
        fetch_history=lambda *args: called.append(args),
    )
    assert report["results"][0]["status"] == "routing_mismatch"
    assert called == []


def test_xetra_stale_candle_must_not_get_technical_score():
    report = _probe(fetch_history=lambda *args: _ohlcv(last="2026-11-12"))
    assert report["results"][0]["status"] == "stale_price"
    assert report["analyzed_markets"] == 0
