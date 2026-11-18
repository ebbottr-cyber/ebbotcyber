"""Explicit opt-in manual catalogue fetch (NOT auto-scanning or paper execution).

Usage: python -m scripts.refresh_paper_universe_sources --fetch --output-dir PATH
By default the command does NOT access the internet or modify any file.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile

from src.services.paper_universe_sources import (
    COINPAPRIKA_URL, KAP_URL, coinpaprika_to_json, fetch_source,
    kap_bist_to_csv, observed_now,
)


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Manually fetch KAP and CoinPaprika inventory only")
    p.add_argument("--fetch", action="store_true", help="Required opt-in for external GET requests")
    p.add_argument("--source", choices=["both", "kap", "coinpaprika"], default="both")
    p.add_argument("--output-dir", type=Path, required=True, help="Existing directory outside .git")
    p.add_argument("--replace", action="store_true", help="Opt in to replace existing snapshot files")
    return p


def _save_atomic(path: Path, content: str) -> str:
    raw = content.encode("utf-8")
    temp = None
    try:
        with tempfile.NamedTemporaryFile(dir=path.parent, prefix=".paper-universe-", delete=False) as stream:
            temp = Path(stream.name)
            os.chmod(temp, 0o600)
            stream.write(raw)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temp, path)
    finally:
        if temp is not None:
            temp.unlink(missing_ok=True)
    return hashlib.sha256(raw).hexdigest()


def run(args: argparse.Namespace) -> int:
    if not args.fetch:
        print(json.dumps({"status": "DISABLED", "network_requests": 0,
                          "paper_trading_enabled": False, "live_trading_enabled": False}))
        return 0
    folder = args.output_dir
    if folder.is_symlink() or not folder.is_dir():
        raise ValueError("output_directory_must_exist_and_not_be_symlink")
    names = {
        "kap": "kap-bist-all.csv",
        "coinpaprika": "coinpaprika-all.json",
    }
    chosen = ["kap", "coinpaprika"] if args.source == "both" else [args.source]
    paths = {name: folder / names[name] for name in chosen}
    for path in paths.values():
        if path.is_symlink() or (path.exists() and not args.replace):
            raise ValueError("snapshot_already_exists_or_is_symlink_requires_explicit_replace")
    stamp = observed_now()
    staged: dict[str, str] = {}
    counts: dict[str, int] = {}
    if "kap" in chosen:
        staged["kap"], counts["kap_company_codes"] = kap_bist_to_csv(fetch_source(KAP_URL), stamp)
        if counts["kap_company_codes"] < 100:
            raise ValueError("kap_company_list_looks_truncated")
    if "coinpaprika" in chosen:
        staged["coinpaprika"], counts["coinpaprika_catalog_count"], counts["coinpaprika_active_count"] = (
            coinpaprika_to_json(fetch_source(COINPAPRIKA_URL), stamp)
        )
        if counts["coinpaprika_catalog_count"] < 1000:
            raise ValueError("coin_catalog_looks_truncated")
    digest = {name: _save_atomic(paths[name], staged[name]) for name in chosen}
    print(json.dumps({
        "status": "FETCHED_INVENTORY_ONLY", "observed_at_utc": stamp,
        "source_urls": {name: KAP_URL if name == "kap" else COINPAPRIKA_URL for name in chosen},
        "files": {name: str(paths[name]) for name in chosen},
        "sha256": digest, "counts": counts,
        "prices_loaded": False, "paper_trading_enabled": False,
        "live_trading_enabled": False, "orders": 0,
    }, ensure_ascii=False, sort_keys=True))
    return 0


def main() -> int:
    args = parser().parse_args()
    try:
        return run(args)
    except (ValueError, OSError) as exc:
        print(json.dumps({"status": "BLOCKED", "reason": str(exc),
                          "paper_trading_enabled": False, "live_trading_enabled": False,
                          "orders": 0}, ensure_ascii=False), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
