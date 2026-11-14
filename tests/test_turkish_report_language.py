"""Regression checks for the Turkish analysis-report localization."""

from src.report_language import (
    SUPPORTED_REPORT_LANGUAGES,
    get_no_data_text,
    get_report_labels,
    get_sentiment_label,
    get_signal_level,
    is_supported_report_language_value,
    localize_confidence_level,
    localize_operation_advice,
    localize_strategy_signal,
    localize_trend_prediction,
    normalize_report_language,
)


def test_turkish_language_aliases_and_support():
    assert "tr" in SUPPORTED_REPORT_LANGUAGES
    assert normalize_report_language("tr-TR") == "tr"
    assert normalize_report_language("Turkish") == "tr"
    assert normalize_report_language("Türkçe") == "tr"
    assert is_supported_report_language_value("tr")
    assert normalize_report_language("unsupported") == "zh"


def test_turkish_report_labels_and_fallback():
    labels = get_report_labels("tr")
    assert labels["dashboard_title"] == "Karar Paneli"
    assert labels["stop_loss_label"] == "Zarar Durdur"
    assert labels["report_title"] == "Hisse Analiz Raporu"
    assert labels["not_investment_advice"].endswith("yatırım tavsiyesi değildir.")
    assert get_no_data_text("tr") == "Veri yok"
    # Every supported report label must remain available through English fallback.
    assert set(get_report_labels("en")) == set(labels)


def test_turkish_signals_and_sentiment():
    assert localize_operation_advice("strong buy", "tr") == "Güçlü Al"
    assert localize_operation_advice("卖出", "tr") == "Sat"
    assert localize_trend_prediction("bullish", "tr") == "Yükseliş"
    assert localize_confidence_level("high", "tr") == "Yüksek"
    assert localize_strategy_signal("sell", "tr") == "Sat"
    assert get_signal_level("buy", 65, "tr")[0] == "Al"
    assert get_sentiment_label(85, "tr") == "Çok Olumlu"
