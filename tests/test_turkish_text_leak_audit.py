"""Offline regression contracts for the Turkish leakage checker."""
import json
from pathlib import Path

from scripts.audit_turkish_text_leaks import audit_report, audit_sources


def test_market_language_branch_is_flagged(tmp_path: Path):
    file = tmp_path / "src/market_analyzer.py"
    file.parent.mkdir(parents=True)
    file.write_text('return "en" if language == "ko" else language\n'
                    'shell_language_label = "Korean" if language == "ko" else "English"\n', encoding="utf-8")
    findings, _ = audit_sources(tmp_path)
    codes = {item.code for item in findings}
    assert {"turkish_market_chinese_fallback", "turkish_prompt_says_english"} <= codes


def test_chinese_ui_dictionary_is_not_mistaken_for_turkish(tmp_path: Path):
    file = tmp_path / "apps/dsa-web/src/i18n/uiText.ts"
    file.parent.mkdir(parents=True)
    file.write_text("const zh = {'a': '测试'};\n"
                    "const tr: Record<UiTextKey, string> = {\n"
                    "  ...en,\n  'a': 'Deneme',\n  'language.short.zh': '中',\n};\n", encoding="utf-8")
    findings, _ = audit_sources(tmp_path)
    assert "turkish_ui_han" not in {item.code for item in findings}
    file.write_text(file.read_text(encoding="utf-8").replace("'a': 'Deneme'", "'a': '测试'"), encoding="utf-8")
    findings, _ = audit_sources(tmp_path)
    assert "turkish_ui_han" in {item.code for item in findings}


def test_user_visible_risk_warning_is_flagged_not_provider_payload(tmp_path: Path):
    file = tmp_path / "report.json"
    report = {"report": {"meta": {"report_language": "tr", "stock_name": "苹果"},
                         "summary": {"risk_warning": "Risk var", "raw_result": {"news": "新闻"}}}}
    file.write_text(json.dumps(report, ensure_ascii=False), encoding="utf-8")
    assert audit_report(file) == []
    report["report"]["summary"]["risk_warning"] = "请注意风险"
    file.write_text(json.dumps(report, ensure_ascii=False), encoding="utf-8")
    findings = audit_report(file)
    assert any("risk_warning" in item.detail for item in findings)
