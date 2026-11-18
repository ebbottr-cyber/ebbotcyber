"""Offline audit for TR / US / DE / HK equities only.

Optional Xetra ingestion is a deliberate local file conversion, not a fetch.
No price request, automatic scan, paper fill, account access or trade.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from src.services.four_market_equity import (
    audit_four_market_equities, xetra_equities_to_manifest,
)
from src.services.paper_universe_inventory import read_input

INDEX = Path(__file__).resolve().parents[1] / "apps/dsa-web/public/stocks.index.json"


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="EBBot four-market equity catalog audit (offline)")
    p.add_argument("--index", type=Path, default=INDEX)
    p.add_argument("--stocks", type=Path, action="append", default=[],
                   help="Repeat for manually obtained, source-labelled stock CSV snapshots")
    p.add_argument("--xetra-input", type=Path,
                   help="Downloaded official dated XETR T7 all-instruments CSV")
    p.add_argument("--xetra-output", type=Path,
                   help="New destination for common-stock-only .DE candidate manifest")
    return p


def run(args: argparse.Namespace) -> int:
    try:
        stock_files = list(args.stocks)
        xetra = None
        if (args.xetra_input is None) != (args.xetra_output is None):
            raise ValueError("xetra_input_and_output_must_be_given_together")
        if args.xetra_input is not None:
            output = args.xetra_output
            if (output.is_symlink() or output.exists()
                    or not output.parent.is_dir() or output.parent.is_symlink()):
                raise ValueError("xetra_output_must_be_new_file_in_existing_real_directory")
            manifest, xetra = xetra_equities_to_manifest(read_input(args.xetra_input))
            # Exclusive creation: never overwrite an operator's prior source snapshot.
            with output.open("x", encoding="utf-8", newline="") as stream:
                stream.write(manifest)
            stock_files.append(output)
        report = audit_four_market_equities(args.index, stock_manifests=stock_files)
        if xetra is not None:
            report["xetra_source_audit"] = xetra
        status = 0
    except (ValueError, OSError, UnicodeError, json.JSONDecodeError) as exc:
        report = {
            "status": "BLOCKED",
            "reason": str(exc) if isinstance(exc, ValueError) else "invalid_input",
            "network_requests": 0, "orders": 0,
            "paper_trading_enabled": False, "live_trading_enabled": False,
        }
        status = 1
    print(json.dumps(report, ensure_ascii=False, sort_keys=True, allow_nan=False))
    return status


if __name__ == "__main__":
    sys.exit(run(parser().parse_args()))
