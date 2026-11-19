"""Manual, read-only Xetra/Yahoo quote metadata research.

Examples:
  python -m scripts.verify_xetra_quotes
  python -m scripts.verify_xetra_quotes --fetch --symbol SAP.DE --symbol SIE.DE
No background polling, schedule, trades, or auto-validation of any shares.
"""
from __future__ import annotations

import argparse
from datetime import date, datetime, timezone
import json
from pathlib import Path
import sys

from src.services.xetra_quote_guard import (
    check_symbols, fetch_yahoo_chart, read_xetra_manifest,
)

MANIFEST = Path(__file__).resolve().parents[1] / "data/market_snapshots/de/xetra-candidates.csv"


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Manual Xetra quote metadata check (no orders)")
    p.add_argument("--manifest", type=Path, default=MANIFEST)
    p.add_argument("--fetch", action="store_true",
                   help="Explicit opt-in to public Yahoo Finance chart GET requests")
    p.add_argument("--symbol", action="append", default=[],
                   help="Repeat exact official snapshot symbols, e.g. SAP.DE; maximum 20")
    p.add_argument("--output", type=Path,
                   help="Optional new JSON report path; existing files are never overwritten")
    return p


def run(args: argparse.Namespace) -> int:
    if not args.fetch:
        print(json.dumps({
            "status": "DISABLED", "network_requests": 0, "orders": 0,
            "paper_trading_enabled": False, "live_trading_enabled": False,
        }))
        return 0
    try:
        if args.output and (
            args.output.is_symlink() or args.output.exists()
            or not args.output.parent.is_dir() or args.output.parent.is_symlink()
        ):
            raise ValueError("output_requires_new_path_in_existing_directory")
        manifest = read_xetra_manifest(args.manifest)
        dates = {row["source_as_of_date"] for row in manifest.values()}
        if len(dates) != 1:
            raise ValueError("mixed_xetra_snapshot_dates")
        source_age_days = (datetime.now(timezone.utc).date()
                           - date.fromisoformat(next(iter(dates)))).days
        if not 0 <= source_age_days <= 7:
            raise ValueError("stale_or_future_xetra_snapshot")
        report = check_symbols(
            manifest, args.symbol, fetch_yahoo_chart, now=datetime.now(timezone.utc),
        )
        report["network_requests_attempted"] = len(report["checks"])
        code = 0 if report["status"] == "QUOTE_METADATA_SAMPLE_ONLY" else 1
        result = json.dumps(report, ensure_ascii=False, sort_keys=True, allow_nan=False)
        if args.output is not None:
            with args.output.open("x", encoding="utf-8") as stream:
                stream.write(result + "\n")
        print(result)
        return code
    except (ValueError, OSError, json.JSONDecodeError, UnicodeError) as exc:
        reason = str(exc) if isinstance(exc, ValueError) else "invalid_input_or_provider_response"
        print(json.dumps({
            "status": "BLOCKED", "reason": reason,
            "orders": 0, "paper_trading_enabled": False,
            "live_trading_enabled": False,
        }), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(run(parser().parse_args()))
