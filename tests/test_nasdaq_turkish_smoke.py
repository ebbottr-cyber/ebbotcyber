"""Offline contract checks for Nasdaq tickers and Turkish analysis requests.

These tests do not contact Yahoo Finance or any LLM provider. They ensure that a
Nasdaq stock code and Turkish report language can pass request validation and
reach the Yahoo Finance symbol adapter unchanged. A live AAPL analysis remains a
separate integration test requiring a configured runtime.
"""

import pytest
from pydantic import ValidationError

from api.v1.schemas.analysis import AnalyzeRequest, MarketReviewRequest
from data_provider.yfinance_fetcher import YfinanceFetcher
from src.report_language import get_report_labels, normalize_report_language


def test_aapl_nasdaq_symbol_does_not_get_chinese_market_suffix():
    fetcher = YfinanceFetcher()
    assert fetcher._convert_stock_code("AAPL") == "AAPL"
    assert fetcher._convert_stock_code(" aapl ") == "AAPL"


def test_turkish_aapl_analysis_request_is_accepted():
    request = AnalyzeRequest.model_validate(
        {
            "stock_code": "AAPL",
            "report_type": "detailed",
            "async_mode": False,
            "notify": False,
            "report_language": "tr",
        }
    )
    assert request.stock_code == "AAPL"
    assert request.report_language == "tr"
    assert normalize_report_language(request.report_language) == "tr"
    assert get_report_labels(request.report_language)["report_title"] == "Hisse Analiz Raporu"


def test_camel_case_report_language_alias_is_accepted():
    request = AnalyzeRequest.model_validate(
        {"stock_code": "AAPL", "reportLanguage": "tr", "notify": False}
    )
    assert request.report_language == "tr"


def test_turkish_us_market_review_request_is_accepted():
    request = MarketReviewRequest.model_validate(
        {"region": "us", "report_language": "tr", "send_notification": False}
    )
    assert request.report_language == "tr"
    assert request.region == "us"


def test_unsupported_report_language_still_rejected():
    with pytest.raises(ValidationError):
        AnalyzeRequest.model_validate({"stock_code": "AAPL", "report_language": "xx"})
