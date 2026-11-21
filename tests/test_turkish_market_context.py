"""Turkish analyzer market context must never introduce Chinese scaffolding.

These tests cover all supported market-code families and preserve the
existing Chinese and English market-context behavior. No order/trading logic.
"""
from __future__ import annotations

import pytest

from src.market_context import get_market_guidelines, get_market_role


@pytest.mark.parametrize("code", ["600519", "00700.HK", "AAPL", "7203.T", "005930.KS", "2330.TW"])
def test_turkish_market_context_uses_existing_english_scaffold(code: str) -> None:
    assert get_market_guidelines(code, "tr") == get_market_guidelines(code, "en")
    assert get_market_role(code, "tr") == get_market_role(code, "en")
    assert not any("\u4e00" <= ch <= "\u9fff" for ch in get_market_guidelines(code, "tr"))


@pytest.mark.parametrize("code", ["600519", "00700.HK", "AAPL", "7203.T", "005930.KS", "2330.TW"])
def test_chinese_market_guidelines_are_not_replaced_with_english(code: str) -> None:
    assert get_market_guidelines(code, "zh") != get_market_guidelines(code, "en")
    assert get_market_role(code, "zh") != get_market_role(code, "en")


def test_korean_keeps_existing_english_market_context() -> None:
    assert get_market_role("AAPL", "ko") == get_market_role("AAPL", "en")
    assert get_market_guidelines("AAPL", "ko") == get_market_guidelines("AAPL", "en")
