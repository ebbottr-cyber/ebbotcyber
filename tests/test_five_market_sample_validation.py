# -*- coding: utf-8 -*-
"""Offline ETRE four-market sample validation; no Yahoo network or orders."""
from datetime import date

import pandas as pd
import pytest

from src.services.five_market_sample_validation import (
    CORE_PROBES,
    EXTRA_PROBES,
    FOCUS_MARKETS,
    build_custom_probes,
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


def test_core_samples_match_exact_four_etre_markets():
    assert FOCUS_MARKETS == ("tr", "us", "de", "hk")
    assert len(CORE_PROBES) == 4
    assert {spec.market for spec in CORE_PROBES} == set(FOCUS_MARKETS)
    assert {spec.currency for spec in CORE_PROBES} == {"TRY", "USD", "EUR", "HKD"}
    assert not {spec.market for spec in CORE_PROBES} & {"cn", "kr", "tw", "jp"}


def test_core_sample_reports_all_markets_and_original_stock_codes():
    report, called = _check()
    assert report["checked_symbols"] == report["analyzed_symbols"] == 3
    assert report["markets_checked"] == 4
    assert "checked_markets" not in report
    assert "analyzed_markets" not in report
    assert report["target_symbols_total"] == 400
    assert report["target_symbols_per_market"] == 100
    assert report["remaining_to_target"] == 396
    assert all(item["target_symbols"] == 100 and item["remaining_to_target"] == 99 for item in report["by_market"].values())
    assert [x["code"] for x in report["results"]] == [p.code for p in CORE_PROBES]
    assert called == [p.yahoo for p in CORE_PROBES]
    assert all(row["sample_status"] == "samples_passed" for row in report["by_market"].values())
    assert all(row["analyzed_symbols"] == 1 for row in report["by_market"].values())


def test_expanded_samples_count_two_each_without_inventing_new_market():
    report, called = _check(sample_set="expanded")
    assert len(CORE_PROBES + EXTRA_PROBES) == 8
    assert report["checked_symbols"] == report["analyzed_symbols"] == 8
    assert report["markets_checked"] == 4
    assert len(called) == 8
    assert all(row["checked_symbols"] == row["analyzed_symbols"] == 2
               for row in report["by_market"].values())


def test_one_market_failure_is_visible_with_other_four_successful():
    bad_symbol = CORE_PROBES[2].yahoo

    def fetch(symbol, *_):
        if symbol == bad_symbol:
            raise ConnectionError("simulated Xetra outage")
        return _ohlcv()

    report, _ = _check(fetch_history=fetch)
    assert report["checked_symbols"] == 4
    assert report["analyzed_symbols"] == 3
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
    assert report["analyzed_symbols"] == 7
    assert report["by_market"]["de"]["checked_symbols"] == 2
    assert report["by_market"]["de"]["analyzed_symbols"] == 1
    assert report["by_market"]["de"]["sample_status"] == "partial"
    assert report["by_market"]["de"]["failure_status_counts"] == {"stale_price": 1}


def test_unknown_currency_cannot_count_as_success():
    report, _ = _check(fetch_currency=lambda symbol: None if symbol == "AAPL" else {
        "THYAO.IS": "TRY", "SAP.DE": "EUR", "0700.HK": "HKD"
    }[symbol])
    assert report["analyzed_symbols"] == 3
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


def test_custom_symbols_accept_only_explicit_four_market_equities():
    symbols = (" THYAO.IS ", "aapl", "sap.de", "HK00700")
    probes = build_custom_probes(symbols)
    assert [(p.market, p.code, p.yahoo, p.currency) for p in probes] == [
        ("tr", "THYAO.IS", "THYAO.IS", "TRY"),
        ("us", "AAPL", "AAPL", "USD"),
        ("de", "SAP.DE", "SAP.DE", "EUR"),
        ("hk", "HK00700", "0700.HK", "HKD"),
    ]


@pytest.mark.parametrize("symbols", [
    (),
    ("AAPL", "aapl"),
    ("",),
    ("600519.SH",),
    ("005930.KS",),
    ("2330.TW",),
    ("SPX",),
    ("XU100.IS",),
    ("1234.DE",),
    ("HK00ABC",),
    ("7203",),
    ("7203.T",),
    ("BAD-TICKER",),
    tuple(["AAPL"] * 401),
])
def test_custom_symbols_reject_unsupported_ambiguous_or_duplicate_request(symbols):
    with pytest.raises(ValueError):
        build_custom_probes(symbols)


def test_custom_validation_reports_only_one_requested_market_without_false_green():
    report = validate_five_market_samples(
        as_of=AS_OF,
        symbols=("AAPL",),
        fetch_history=lambda symbol, *_: _ohlcv(),
        fetch_currency=lambda symbol: "USD",
        sessions_for_market=lambda market, *_: pd.DatetimeIndex([LAST]),
        analyzer=lambda frame, symbol: type("Result", (), {"signal_score": 62})(),
    )
    assert report["scope"] == "etre_four_market_custom_historical_symbols"
    assert report["markets_checked"] == 1
    assert report["market_scope"] == ["tr", "us", "de", "hk"]
    assert report["analyzed_symbols"] == 1
    assert report["by_market"]["us"]["sample_status"] == "samples_passed"
    for market in ("tr", "de", "hk"):
        assert report["by_market"][market]["sample_status"] == "not_requested"
        assert report["by_market"][market]["checked_symbols"] == 0


def test_custom_symbols_do_not_infer_xetra_from_us_adr_ticker():
    probes = build_custom_probes(("SAP", "SAP.DE"))
    assert [(p.code, p.market) for p in probes] == [
        ("SAP", "us"),
        ("SAP.DE", "de"),
    ]


def _synthetic_four_market_codes():
    """Formats only: not claiming these are listed shares or trading permissions."""
    names = [f"T{chr(65 + n // 26)}{chr(65 + n % 26)}A.IS" for n in range(100)]
    names += [f"U{chr(65 + n // 26)}{chr(65 + n % 26)}" for n in range(100)]
    names += [f"D{n:04d}.DE" for n in range(100)]
    names += [f"HK{n + 1:05d}" for n in range(100)]
    return tuple(names)


def test_four_market_ticker_validator_accepts_max_100_per_market():
    codes = _synthetic_four_market_codes()
    assert len(codes) == len(set(codes)) == 400
    probes = build_custom_probes(codes)
    counts = {market: sum(p.market == market for p in probes) for market in FOCUS_MARKETS}
    assert counts == {"tr": 100, "us": 100, "de": 100, "hk": 100}
    assert not any(p.market == "jp" for p in probes)


def test_per_market_overflow_fails_before_400_total():
    codes = _synthetic_four_market_codes()
    # 101 German symbols despite the total remaining below 400
    with pytest.raises(ValueError, match="Market de exceeds 100"):
        build_custom_probes(codes[200:300] + ("D9999.DE",))
