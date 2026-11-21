"""Turkish report scaffolding must keep existing language and quote semantics."""
from types import SimpleNamespace

from tests.litellm_stub import ensure_litellm_stub

ensure_litellm_stub()

from src.market_analyzer import MarketAnalyzer  # noqa: E402
from src.analyzer import _phase_aware_quote_labels  # noqa: E402


def _analyzer(lang: str, region: str = "us"):
    analyzer = object.__new__(MarketAnalyzer)
    analyzer.config = SimpleNamespace(report_language=lang)
    analyzer.region = region
    return analyzer


def test_turkish_uses_english_structural_base_without_chinese_labels():
    review = _analyzer("tr")
    assert review._get_output_language() == "tr"
    assert review._get_review_language() == "en"
    assert review._get_market_scope_name() == "US market"
    assert review._get_turnover_unit_label() == "USD bn"
    assert review._get_review_title("2026-11-20") == "## 2026-11-20 ABD Piyasa Özeti"


def test_other_output_languages_remain_unchanged():
    assert _analyzer("en")._get_review_language() == "en"
    assert _analyzer("ko")._get_review_language() == "en"
    assert _analyzer("zh")._get_review_language() == "zh"
    assert _analyzer("zh")._get_review_title("2026-11-20") == "## 2026-11-20 大盘复盘"


def test_turkish_quote_labels_stay_distinct_from_english():
    context = {"market_phase_context": {"phase": "intraday", "is_partial_bar": True}}
    assert _phase_aware_quote_labels(context, "tr") == ("Güncel Fiyat Bilgisi", "Gün İçi Tahmini Fiyat")
    assert _phase_aware_quote_labels(context, "en") == ("Latest Quote", "Intraday Estimated Price")


def test_turkish_market_prompt_requests_turkish():
    import re
    from src.core.market_profile import get_profile
    from src.core.market_strategy import get_market_strategy_blueprint
    from src.market_analyzer import MarketOverview

    review = _analyzer("tr")
    review.profile = get_profile("us")
    review.strategy = get_market_strategy_blueprint("us")
    prompt = review._build_review_prompt(MarketOverview(date="2026-11-20"), [])
    assert "Turkish (Türkçe)" in prompt
    assert "## 2026-11-20 ABD Piyasa Özeti" in prompt
    assert not re.search(r"[\u3400-\u9fff]", prompt)
