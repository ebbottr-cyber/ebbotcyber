#!/usr/bin/env python3
"""Fail closed on duplicate Turkish usage keys from a three-way Git auto-merge.

Only removes exactly the extra 3 main-inserted translations, preserving the
existing, richer candidate TR dictionary. Never edits the repository itself:
CI invokes this on a throwaway detached-worktree source file only.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import re

EXTRA_MAIN_LINES = (
    "  'usage.eyebrow': 'Kullanım',",
    "  'usage.title': 'Token Kullanımı',",
    "  'usage.description': 'Model çağrılarını, token tüketimini ve kullanım ayrıntılarını inceleyin.',",
)
REQUIRED_EXISTING = (
    """  'usage.eyebrow': "KULLANIM",""",
    """  'usage.title': "Token Kullanımı",""",
    """  'usage.description': "Model çağrısı sayısını, istek ve yanıt token kullanımını, model kullanımını ve son çağrı ayrıntılarını inceleyin.",""",
)
KEYS = ("usage.eyebrow", "usage.title", "usage.description")


def deduplicate(source: str) -> str:
    lines = source.splitlines(keepends=True)
    plain = [line.rstrip("\r\n") for line in lines]
    for extra, preserved in zip(EXTRA_MAIN_LINES, REQUIRED_EXISTING):
        if plain.count(extra) != 1 or plain.count(preserved) != 1:
            raise ValueError("Unexpected Turkish usage key layout: require independent review")
    for key in KEYS:
        count = len(re.findall(r"^\s*'"+re.escape(key)+r"'\s*:", source, flags=re.MULTILINE))
        if count != 4:  # zh, en, tr candidate, and newly auto-inserted tr main
            raise ValueError(f"Unexpected duplicate count for {key}: {count}")
    extras = set(EXTRA_MAIN_LINES)
    output = "".join(line for line in lines if line.rstrip("\r\n") not in extras)
    for key in KEYS:
        count = len(re.findall(r"^\s*'"+re.escape(key)+r"'\s*:", output, flags=re.MULTILINE))
        if count != 3:
            raise ValueError(f"TR usage dedup did not restore three language entries: {key}")
    return output


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    original = args.source.read_text(encoding="utf-8")
    fixed = deduplicate(original)
    if fixed == original:
        raise ValueError("Expected three known semantic duplicate keys")
    args.source.write_text(fixed, encoding="utf-8")
    report = {
        "status": "THREE_SEMANTIC_TR_KEYS_RESOLVED",
        "removed_keys": list(KEYS),
        "preserved_candidate_turkish_entries": True,
        "release_status": "BLOCKED",
        "main_or_remote_ref_modified": False,
    }
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
