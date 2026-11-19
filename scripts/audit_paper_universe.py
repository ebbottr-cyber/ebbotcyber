"""Manual all-market inventory check. No data fetching, wallet, broker or writes."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from src.services.paper_universe_inventory import audit_universe

INDEX = Path(__file__).resolve().parents[1] / "apps/dsa-web/public/stocks.index.json"


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="EBBot all-market inventory, OFFLINE ONLY")
    p.add_argument("--index", type=Path, default=INDEX)
    p.add_argument("--stocks", type=Path, action="append", default=[],
                   help="Repeat for every external full-market CSV list")
    p.add_argument("--coins", type=Path, action="append", default=[],
                   help="Repeat for each coin provider JSON / JSONL snapshot")
    p.add_argument("--contracts", type=Path, action="append", default=[],
                   help="Separate futures contract JSON files (never Spot coins)")
    return p


def run(args: argparse.Namespace) -> int:
    try:
        report = audit_universe(
            args.index, stock_manifests=args.stocks,
            coin_manifests=args.coins, contract_manifests=args.contracts,
        )
        result = 0
    except (ValueError, OSError, UnicodeError, json.JSONDecodeError) as error:
        report = {
            "status": "BLOCKED",
            "reason": str(error) if isinstance(error, ValueError) else "invalid_input",
            "orders": 0, "network_requests": 0, "journal_writes": 0,
            "paper_trading_enabled": False, "live_trading_enabled": False,
        }
        result = 1
    print(json.dumps(report, sort_keys=True, ensure_ascii=False, allow_nan=False))
    return result


if __name__ == "__main__":
    sys.exit(run(parser().parse_args()))
