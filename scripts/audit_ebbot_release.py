#!/usr/bin/env python3
"""Offline, fail-closed source audit. Never deploys, accesses secrets or trades."""
from __future__ import annotations
import argparse
import json
import re
from pathlib import Path
from typing import Any

REQUIRED = (
    "apps/dsa-web/public/manifest.webmanifest",
    "apps/dsa-web/public/sw.js",
    "apps/dsa-web/src/pages/DashboardOverviewPage.tsx",
    "apps/dsa-web/src/pages/MemeCoinPage.tsx",
    "api/v1/endpoints/meme_coin.py",
    "src/services/meme_coin_discovery.py",
    ".github/workflows/ebbot-integration.yml",
)
LEGACY = (
    ".github/workflows/ci.yml",
    ".github/workflows/00-daily-analysis.yml",
    ".env.example",
)
MANUAL = (
    "Production admin authorization and HTTPS require real-server checks.",
    "iPhone Safari and Android Chrome PWA installation require real-device checks.",
    "Financial data redistribution licences and delayed quote labels need review.",
    "Legacy CI/env tests must be reconciled and full backend regression rerun.",
    "Re-compare the other Meme Coin branch before merging.",
)

def audit(root: Path) -> dict[str, Any]:
    checks, blockers, reviews = [], [], []
    for name in REQUIRED:
        (checks if (root / name).is_file() else blockers).append(
            ("Present: " if (root / name).is_file() else "Missing required integration file: ") + name
        )
    mf = root / "apps/dsa-web/public/manifest.webmanifest"
    if mf.is_file():
        try:
            m = json.loads(mf.read_text(encoding="utf-8"))
            if (m.get("id"), m.get("scope"), m.get("start_url"), m.get("display")) == (
                "/", "/", "/overview", "standalone"
            ):
                checks.append("PWA identity, scope and launch path are consistent.")
            else:
                blockers.append("PWA identity, scope or launch path differs.")
        except (ValueError, OSError):
            blockers.append("PWA manifest cannot be read.")
    endpoint = root / "api/v1/endpoints/meme_coin.py"
    if endpoint.is_file():
        src = endpoint.read_text(encoding="utf-8")
        if "@router.get" in src and not re.search(
            r"@router\.(post|put|patch|delete)\s*\(", src, re.I
        ):
            checks.append("Meme Coin endpoint declarations are GET-only.")
        else:
            blockers.append("Meme Coin write endpoint or missing read-only routes.")
    discovery = root / "src/services/meme_coin_discovery.py"
    if discovery.is_file():
        src = discovery.read_text(encoding="utf-8")
        pattern = r"""os\.getenv\(\s*["']MEME_COIN_DISCOVERY_ENABLED["']\s*,\s*["']false["']\s*\)"""
        if re.search(pattern, src):
            checks.append("Meme Coin discovery is off by default.")
        else:
            blockers.append("Disabled-by-default meme scanning not verified.")
    active = root / ".github/workflows/00-daily-analysis.yml"
    archived = root / "workflows_disabled/00-daily-analysis.yml.disabled"
    if active.is_file():
        blockers.append("Scheduled legacy daily-analysis workflow was reactivated.")
    elif archived.is_file():
        checks.append("Legacy scheduled daily analysis is archived and disabled.")
    else:
        reviews.append("Legacy daily analysis archive not found.")
    for name in LEGACY:
        if not (root / name).is_file():
            reviews.append("Legacy full-suite contract still expects: " + name)
    return {
        "status": "blocked" if blockers or reviews or MANUAL else "ready",
        "scope": "offline_source_only",
        "checks": checks,
        "technical_blockers": blockers,
        "legacy_contract_reviews": reviews,
        "manual_release_gates": list(MANUAL),
        "enables_live_trading": False,
    }

def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args()
    report = audit(args.root.resolve())
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print("EBBot release status:", report["status"].upper())
        for key in ("technical_blockers", "legacy_contract_reviews", "manual_release_gates"):
            for value in report[key]:
                print(" -", key + ":", value)
    return int(args.strict and report["status"] != "ready")

if __name__ == "__main__":
    raise SystemExit(main())
