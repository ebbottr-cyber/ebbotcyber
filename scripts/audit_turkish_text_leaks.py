"""Read-only Chinese text audit for Turkish EBBot reporting routes."""
from __future__ import annotations

import argparse
import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path

HAN = re.compile(r"[\u3400-\u9fff\uf900-\ufaff]")
SOURCES = (
    "src/analyzer.py",
    "src/market_analyzer.py",
    "src/report_language.py",
    "src/core/pipeline.py",
    "src/notification.py",
    "apps/dsa-web/src/i18n/uiText.ts",
)


@dataclass(frozen=True)
class Finding:
    severity: str
    path: str
    line: int
    code: str
    detail: str


def audit_sources(root: Path, *, include_candidates: bool = False) -> tuple[list[Finding], dict[str, int]]:
    findings = []
    counts = {}
    for name in SOURCES:
        path = root / name
        if not path.is_file():
            findings.append(Finding("warning", name, 0, "source_missing", "Source not found"))
            continue
        text = path.read_text(encoding="utf-8")
        lines = text.splitlines()
        counts[name] = sum(bool(HAN.search(line)) for line in lines)
        if include_candidates:
            for index, line in enumerate(lines, 1):
                if HAN.search(line):
                    findings.append(Finding("review", name, index, "chinese_source_literal", "Inspect reachability before translating"))
        if name == "src/market_analyzer.py":
            for index, line in enumerate(lines, 1):
                if 'return "en" if language == "ko" else language' in line:
                    findings.append(Finding("error", name, index, "turkish_market_chinese_fallback", "Turkish reaches Chinese market review template"))
                if "shell_language_label =" in line and "English" in line and "Turkish" not in line:
                    findings.append(Finding("error", name, index, "turkish_prompt_says_english", "Turkish prompt routes to English output"))
        if name == "src/analyzer.py" and 'normalize_report_language(report_language) in ("en", "ko", "tr")' in text:
            findings.append(Finding("warning", name, 0, "turkish_quote_labels_english", "Turkish price labels are English"))
        if name.endswith("uiText.ts"):
            start = re.search(r"const tr\s*:\s*Record<UiTextKey, string>\s*=\s*\{", text)
            if start:
                stop = text.find("\n};", start.end())
                if stop >= 0:
                    for index, line in enumerate(text[start.end():stop].splitlines(), 1):
                        if HAN.search(line) and "'language.short.zh': '中'" not in line:
                            findings.append(Finding("error", name, text[:start.end()].count("\n") + index, "turkish_ui_han", "Chinese literal in Turkish UI dictionary"))
    return findings, counts


def audit_report(path: Path) -> list[Finding]:
    text = path.read_text(encoding="utf-8")
    if path.suffix.lower() != ".json":
        return [Finding("error", str(path), i, "turkish_report_han", "Han characters in rendered text")
                for i, line in enumerate(text.splitlines(), 1) if HAN.search(line)]
    data = json.loads(text)
    if not isinstance(data, dict):
        raise ValueError("Expected JSON report object")
    report = data.get("report", data)
    if not isinstance(report, dict):
        raise ValueError("Expected report dictionary")
    meta = report.get("meta") or {}
    if not isinstance(meta, dict):
        raise ValueError("Expected report metadata object")
    language = meta.get("report_language") or report.get("report_language") or report.get("language") or data.get("report_language")
    if language != "tr":
        raise ValueError("Only JSON reports explicitly marked report_language=tr can be inspected")
    excluded = {"raw_result", "provider_payload", "context_snapshot", "provider_raw", "stock_name"}
    findings = []
    def walk(value, key):
        if isinstance(value, dict):
            for field, sub in value.items():
                if field not in excluded:
                    walk(sub, f"{key}.{field}")
        elif isinstance(value, list):
            for i, sub in enumerate(value):
                walk(sub, f"{key}[{i}]")
        elif isinstance(value, str) and HAN.search(value):
            findings.append(Finding("error", str(path), 0, "turkish_report_han", f"Han text in {key}"))
    walk(report, "report")
    return findings


def main() -> int:
    parser = argparse.ArgumentParser(description="Read-only Turkish report leakage audit (no providers)")
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument("--report", type=Path, default=None)
    parser.add_argument("--include-candidates", action="store_true")
    args = parser.parse_args()
    findings, counts = audit_sources(args.root, include_candidates=args.include_candidates)
    if args.report is not None:
        findings.extend(audit_report(args.report))
    print(json.dumps({"han_source_line_counts": counts, "findings": [asdict(f) for f in findings]}, ensure_ascii=False, indent=2))
    return 1 if any(f.severity == "error" for f in findings) else 0


if __name__ == "__main__":
    raise SystemExit(main())
