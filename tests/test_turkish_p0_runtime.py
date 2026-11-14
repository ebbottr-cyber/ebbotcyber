"""P0 regression coverage for Turkish report-language runtime tables.

All checks are deterministic and do not access remote data or an AI provider.
"""

from types import SimpleNamespace

from src.report_language import SUPPORTED_REPORT_LANGUAGES
from src.schemas.decision_action import localize_action_label
from src.services.empty_news import empty_news_disclosure


def test_all_supported_report_languages_have_news_disclosures():
    for language in SUPPORTED_REPORT_LANGUAGES:
        unconfigured = empty_news_disclosure(
            SimpleNamespace(news_result_count=None, news_result_count_known=True, news_evidence_present=False),
            language,
        )
        zero_result = empty_news_disclosure(
            SimpleNamespace(news_result_count=0, news_result_count_known=True, news_evidence_present=False),
            language,
        )
        assert isinstance(unconfigured, str) and unconfigured.strip()
        assert isinstance(zero_result, str) and zero_result.strip()
        assert unconfigured != zero_result


def test_turkish_news_disclosures_are_localized_and_evidence_safe():
    absent = SimpleNamespace(news_result_count=0, news_result_count_known=True, news_evidence_present=False)
    present = SimpleNamespace(news_result_count=0, news_result_count_known=True, news_evidence_present=True)
    assert "haber" in empty_news_disclosure(absent, "tr").lower()
    assert empty_news_disclosure(present, "tr") is None


def test_action_labels_exist_for_all_supported_report_languages():
    actions = ("buy", "add", "hold", "reduce", "sell", "watch", "avoid", "alert")
    for language in SUPPORTED_REPORT_LANGUAGES:
        for action in actions:
            label = localize_action_label(action, language)
            assert isinstance(label, str) and label.strip()


def test_turkish_action_labels():
    assert localize_action_label("buy", "tr") == "Al"
    assert localize_action_label("sell", "tr") == "Sat"
    assert localize_action_label("hold", "tr") == "Tut"
