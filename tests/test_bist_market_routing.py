# -*- coding: utf-8 -*-
"""BIST100 integration contracts: offline, no Yahoo network requests."""
from datetime import date
from types import SimpleNamespace
from unittest.mock import patch

import pandas as pd
import pytest

from data_provider.base import DataFetcherManager, _market_tag, normalize_stock_code
from data_provider.yfinance_fetcher import YfinanceFetcher
from src.core import trading_calendar
from src.market_context import detect_market, get_market_guidelines, get_market_role
from src.services.stock_list_parser import ParseStatus, parse_analysis_target


@pytest.mark.parametrize("raw", ["THYAO.IS", "  thyao.is ", "AKFYE.IS", "ASELS.IS"])
def test_bist_equity_roundtrips_as_turkish_stock(raw):
    parsed = parse_analysis_target(raw)
    canonical = raw.strip().upper()
    assert parsed.asset_type == ParseStatus.STOCK
    assert parsed.exchange == "TR"
    assert parsed.canonical_id == canonical
    assert normalize_stock_code(raw) == canonical
    assert _market_tag(canonical) == "tr"
    assert detect_market(canonical) == "tr"
    assert trading_calendar.get_market_for_stock(canonical) == "tr"
    assert YfinanceFetcher()._convert_stock_code(raw) == canonical


@pytest.mark.parametrize("raw", ["XU100.IS", "TH.IS", "12345.IS", "INVALIDTOOLONG.IS"])
def test_unsupported_bist_suffix_never_routes_to_chinese_equities(raw):
    parsed = parse_analysis_target(raw)
    assert parsed.asset_type == ParseStatus.UNSUPPORTED
    assert parsed.exchange == "TR"


@pytest.mark.parametrize("raw", ["XU100.IS", "TH.IS", "12345.IS", "INVALIDTOOLONG.IS"])
def test_realtime_quote_rejects_invalid_bist_and_index_without_cn_fallback(raw):
    manager = DataFetcherManager(fetchers=[])
    with (
        patch("src.config.get_config", return_value=SimpleNamespace(enable_realtime_quote=True)),
        patch.object(manager, "_try_fetcher_quote") as fetch_quote,
        patch.object(manager, "_get_cn_index_realtime_quote") as cn_index,
    ):
        assert manager.get_realtime_quote(raw) is None
    fetch_quote.assert_not_called()
    cn_index.assert_not_called()


def test_realtime_quote_tries_only_yahoo_for_valid_bist():
    manager = DataFetcherManager(fetchers=[])
    with (
        patch("src.config.get_config", return_value=SimpleNamespace(enable_realtime_quote=True)),
        patch.object(manager, "_try_fetcher_quote", return_value=None) as fetch_quote,
    ):
        assert manager.get_realtime_quote("  thyao.is  ") is None
    fetch_quote.assert_called_once_with("THYAO.IS", "YfinanceFetcher")


def test_bist_quotes_must_use_yahoo_only_even_with_unknown_custom_fetchers():
    fetchers = [
        SimpleNamespace(name="AkshareFetcher"),
        SimpleNamespace(name="YfinanceFetcher"),
        SimpleNamespace(name="UnknownCustomFetcher"),
        SimpleNamespace(name="EfinanceFetcher"),
    ]
    selected = DataFetcherManager._filter_daily_fetchers_for_market(fetchers, "tr")
    assert [f.name for f in selected] == ["YfinanceFetcher"]
    assert DataFetcherManager._filter_daily_fetchers_for_market(fetchers[:1], "tr") == []


def test_turkish_market_prompt_never_falls_back_to_china():
    assert "BIST" in get_market_role("THYAO.IS", lang="tr")
    guidelines = get_market_guidelines("THYAO.IS", lang="tr")
    assert "TRY" in guidelines and "Do not apply China" in guidelines
    assert detect_market("AAPL") == "us"
    assert detect_market("005930.KS") == "kr"


def test_bist_calendar_uses_xist_and_istanbul_timezone():
    assert trading_calendar.MARKET_EXCHANGE["tr"] == "XIST"
    assert trading_calendar.MARKET_TIMEZONE["tr"] == "Europe/Istanbul"
    sessions = pd.DatetimeIndex(["2024-10-28", "2024-10-30"], tz="UTC")
    fake = SimpleNamespace(sessions_in_range=lambda start, end: sessions)
    with patch.object(trading_calendar, "_XCALS_AVAILABLE", True), patch.object(
        trading_calendar.xcals, "get_calendar", return_value=fake
    ) as getter:
        result = trading_calendar.get_trading_dates("tr", date(2024, 10, 28), date(2024, 10, 30))
    getter.assert_called_once_with("XIST")
    assert result.equals(pd.DatetimeIndex(["2024-10-28", "2024-10-30"]))


def test_real_xist_republic_day_if_calendar_dependency_installed():
    if not trading_calendar._XCALS_AVAILABLE:
        pytest.skip("exchange-calendars optional")
    assert trading_calendar.is_market_open("tr", date(2024, 10, 29)) is False
    assert trading_calendar.is_market_open("tr", date(2024, 10, 30)) is True
