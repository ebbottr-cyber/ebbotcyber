# -*- coding: utf-8 -*-
"""Offline ETRE five-market sample validation; no Yahoo network or orders."""
from datetime import date

import pandas as pd
import pytest

from src.services.five_market_sample_validation import (
    CORE_PROBES,
    EXTRA_PROBES,
    FOCUS_MARKETS,
    validate_five_market_samples,
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


def _check(*, sample_set="core", **overrides):
    specs = CORE_PROBES if sample_set == "core" else CORE_PROBES + EXTRA_PROBES
    markets = {spec.code: spec.market for spec in specs}
    symbols = {spec.code: spec.yahoo for spec in specs}
    currencies = {spec.yahoo: spec.currency for spec in specs}
    called = []

    def fetch_history(symbol, *_):
        called.append(symbol)
        return _ohlcv()

    params = {
        "fetch_history": fetch_history,
        "fetch_currency": currencies.get,
        "sessions_for_market": lambda market, *_: pd.DatetimeIndex([LAST]),
        "detect_market": markets.get,
        "convert_ticker": symbols.get,
        "analyzer": lambda frame, symbol: type("Result", (), {"signal_score": 72})(),
    }
    params.update(overrides)
    return validate_five_market_samples(
        as_of=AS_OF, sample_set=sample_set, **params
    ), called


def test_core_samples_match_exact_five_etre_markets():
    assert FOCUS_MARKETS == ("tr", "us", "de", "hk", "jp")
    assert len(CORE_PROBES) == 5
    assert {spec.market for spec in CORE_PROBES} == set(FOCUS_MARKETS)
    assert {spec.currency for spec in CORE_PROBES} == {"TRY", "USD", "EUR", "HKD", "JPY"}
    assert not {spec.market for spec in CORE_PROBES} & {"cn", "kr", "tw"}


def test_core_sample_reports_all_markets_and_original_stock_codes():
    report, called = _check()
    assert report["checked_symbols"] == report["analyzed_symbols"] == 5
    assert report["markets_checked"] == 5
    assert "checked_markets" not in report
    assert "analyzed_markets" not in report
    assert [x["code"] for x in report["results"]] == [p.code for p in CORE_PROBES]
    assert called == [p.yahoo for p in CORE_PROBES]
    assert all(row["sample_status"] == "samples_passed" for row in report["by_market"].values())
    assert all(row["analyzed_symbols"] == 1 for row in report["by_market"].values())


def test_expanded_samples_count_two_each_without_inventing_new_market():
    report, called = _check(sample_set="expanded")
    assert len(CORE_PROBES + EXTRA_PROBES) == 10
    assert report["checked_symbols"] == report["analyzed_symbols"] == 10
    assert report["markets_checked"] == 5
    assert len(called) == 10
    assert all(row["checked_symbols"] == row["analyzed_symbols"] == 2
               for row in report["by_market"].values())


def test_one_market_failure_is_visible_with_other_four_successful():
    bad_symbol = CORE_PROBES[2].yahoo

    def fetch(symbol, *_):
        if symbol == bad_symbol:
            raise ConnectionError("simulated Xetra outage")
        return _ohlcv()

    report, _ = _check(fetch_history=fetch)
    assert report["checked_symbols"] == 5
    assert report["analyzed_symbols"] == 4
    assert report["by_market"]["de"]["sample_status"] == "samples_failed"
    assert report["by_market"]["de"]["failure_status_counts"] == {"fetch_error": 1}
    assert report["results"][2]["error_type"] == "ConnectionError"
    assert report["by_market"]["tr"]["sample_status"] == "samples_passed"


def test_expanded_partial_market_not_reported_as_passed():
    def fetch(symbol, *_):
        if symbol == "SIE.DE":
            return _ohlcv(last="2026-11-12")
        return _ohlcv()

    report, _ = _check(sample_set="expanded", fetch_history=fetch)
    assert report["analyzed_symbols"] == 9
    assert report["by_market"]["de"]["checked_symbols"] == 2
    assert report["by_market"]["de"]["analyzed_symbols"] == 1
    assert report["by_market"]["de"]["sample_status"] == "partial"
    assert report["by_market"]["de"]["failure_status_counts"] == {"stale_price": 1}


def test_unknown_currency_cannot_count_as_success():
    report, _ = _check(fetch_currency=lambda symbol: None if symbol == "AAPL" else {
        "THYAO.IS": "TRY", "SAP.DE": "EUR", "0700.HK": "HKD", "7203.T": "JPY"
    }[symbol])
    assert report["analyzed_symbols"] == 4
    assert report["by_market"]["us"]["failure_status_counts"] == {"currency_unverified": 1}


@pytest.mark.parametrize("sample_set", ["unknown", "", "all"])
def test_unsupported_sample_set_is_rejected(sample_set):
    with pytest.raises(ValueError, match="core or expanded"):
        validate_five_market_samples(as_of=AS_OF, sample_set=sample_set)


def test_live_adapter_symbol_contracts_for_sampled_equities():
    from data_provider.yfinance_fetcher import YfinanceFetcher
    from src.core.trading_calendar import get_market_for_stock

    adapter = YfinanceFetcher()
    for spec in CORE_PROBES + EXTRA_PROBES:
        assert get_market_for_stock(spec.code) == spec.market
        assert adapter._convert_stock_code(spec.code) == spec.yahoo
