"""Export a local offline SYNTHETIC report for manual browser import."""
from __future__ import annotations

import argparse
import json

from src.services.meme_coin_report_export import export_synthetic_report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="LOCAL synthetic research report only (NOT live trading)"
    )
    parser.add_argument("--database", required=True, help="Explicit .sqlite3 test journal")
    parser.add_argument("--equity", required=True, help="Original synthetic starting USD balance")
    parser.add_argument("--output", required=True, help="New .json output path (never overwritten)")
    parser.add_argument("--confirm-synthetic-only", action="store_true",
                        help="Confirm the report is hypothetical and local only")
    args = parser.parse_args(argv)
    result = export_synthetic_report(
        database_path=args.database,
        starting_equity_usd=args.equity,
        output_path=args.output,
        enabled=args.confirm_synthetic_only,
    )
    print(json.dumps(result, ensure_ascii=False))
    return 0 if result["status"] == "exported" else 1


if __name__ == "__main__":
    raise SystemExit(main())
