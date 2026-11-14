"""Regression tests for Turkish output routing in the agent, pipeline, history, and poster.

These tests use deterministic inputs and must never make network/LLM calls.
"""

import ast
import copy
from pathlib import Path
from types import SimpleNamespace
from typing import Optional

from tests.litellm_stub import ensure_litellm_stub

ensure_litellm_stub()

from src.agent.executor import AgentExecutor, _build_language_section
from src.core.pipeline import StockAnalysisPipeline
from src.share_image import (
    _POSTER_TEXT,
    _poster_html_language,
    _poster_label,
    _is_market_review_title,
    _market_label,
    _poster_language,
    _poster_text,
)


def test_agent_turkish_chat_and_dashboard_prompts():
    chat = _build_language_section("tr", chat_mode=True)
    dashboard = _build_language_section("tr")
    assert "Türkçe" in chat
    assert "JSON" in chat
    assert "Türkçe" in dashboard
    assert "buy|hold|sell" in dashboard
    assert "默认使用中文" not in chat
    assert "所有面向用户" not in dashboard


def test_agent_turkish_request_field():
    agent = AgentExecutor.__new__(AgentExecutor)
    result = agent._build_user_message("Analyze AAPL", {"stock_code": "AAPL", "report_type": "detailed", "report_language": "tr"})
    assert "Hisse Kodu: AAPL" in result
    assert "Rapor Türü: detailed" in result
    assert "股票代码" not in result
    assert "Çıktı dili: Türkçe" in result
    assert "输出语言: 中文" not in result


def test_pipeline_turkish_summary_and_trend_fallbacks():
    sample = SimpleNamespace(trend_prediction="Yükseliş", operation_advice="Al")
    summary = StockAnalysisPipeline._summary_fallback_from_result(sample, "tr")
    assert summary == "Trend değerlendirmesi: Yükseliş; işlem önerisi: Al."
    trend = SimpleNamespace(trend_status=SimpleNamespace(value="bullish"))
    assert StockAnalysisPipeline._trend_label_fallback(trend, "tr") == "Yükseliş"


def _extract_history_label_helper():
    """Execute the actual nested history label helper without creating a DB connection."""
    path = Path(__file__).resolve().parents[1] / "src/services/history_service.py"
    tree = ast.parse(path.read_text(encoding="utf-8"))
    cls = next(node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == "HistoryService")
    method = next(node for node in cls.body if isinstance(node, ast.FunctionDef) and node.name == "_generate_single_stock_markdown")
    nested = next(node for node in method.body if isinstance(node, ast.FunctionDef) and node.name == "_label")
    isolated = copy.deepcopy(nested)
    isolated.decorator_list = []
    scope = {"report_language": "tr", "Optional": Optional}
    module = ast.fix_missing_locations(ast.Module(body=[isolated], type_ignores=[]))
    exec(compile(module, str(path), "exec"), scope)
    return scope["_label"]


def test_history_turkish_report_headings():
    label = _extract_history_label_helper()
    assert label("Analysis Date", "分析日期", "분석일", "Analiz Tarihi") == "Analiz Tarihi"
    assert label("Risk Warning", "风险提示", "리스크 경고", "Risk Uyarısı") == "Risk Uyarısı"
    # The helper must continue to handle an omitted Turkish override safely.
    assert label("Fallback", "后备", "대체") == "Fallback"


def test_share_poster_turkish_language_and_labels():
    payload = {"report_language": "tr"}
    assert _poster_language("# Stock Report", payload) == "tr"
    assert _poster_language("# Hisse Analiz Raporu") == "tr"
    assert _poster_html_language("tr") == "tr"
    assert _poster_text("tr", "brand") == "EBBOT-CYBER Hisse Analizi"
    assert _poster_text("tr", "risk_alerts") == "Risk Uyarıları"
    assert _poster_label("tr", "止损") == "Zarar Durdur"
    assert _poster_label("tr", "观察 Destek") == "İzle Destek"


def test_share_poster_preserves_english_and_korean():
    assert _poster_text("en", "brand") == "AI Stock Analysis"
    assert _poster_text("ko", "brand") == "AI 주식 분석"
    assert all(key in _POSTER_TEXT["tr"] for key in _POSTER_TEXT["en"])


def test_share_poster_turkish_market_review_recognition():
    assert _is_market_review_title("Piyasa Değerlendirmesi")
    assert _is_market_review_title("ABD Hisse Piyasası Özeti")
    assert _market_label("ABD Hisse Piyasası Özeti") == "美股"
    assert _market_label("Çin Hisse Piyasası Özeti") == "A股"
