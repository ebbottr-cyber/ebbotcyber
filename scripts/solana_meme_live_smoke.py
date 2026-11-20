"""Single-use GitHub Actions smoke check against PUBLIC Solana data providers.

Strictly read-only: imports the watchlist scanner, not order or wallet modules.
Logs provider health and aggregate counters, never raw response bodies.
"""
from __future__ import annotations

import argparse
import json
from collections import Counter

from data_provider.solana_meme import is_solana_address
from scripts.scan_solana_meme import scan

SOURCES = {"geckoterminal", "dexscreener"}
STRATEGIES = {"new_coin_hunter", "momentum_watcher"}


def assess(payload: dict, limit: int) -> dict:
    """Reject malformed or unsafe output rather than reporting green smoke."""
    if not isinstance(payload, dict) or payload.get("enabled") is not True:
        raise ValueError("Live read-only scanner did not report enabled")
    if payload.get("trading_enabled") is not False:
        raise ValueError("Scanner trading gate is not explicitly disabled")

    candidates, errors = payload.get("candidates"), payload.get("errors")
    if not isinstance(candidates, list) or not isinstance(errors, list):
        raise ValueError("Scanner returned invalid candidate/error collections")

    mints: set[str] = set()
    counts: Counter = Counter()
    blocked = 0
    watch = 0
    for item in candidates:
        if not isinstance(item, dict):
            raise ValueError("Invalid candidate")
        mint = item.get("mint")
        if not is_solana_address(mint):
            raise ValueError("Candidate has an invalid Solana token address")
        if item.get("strategy") not in STRATEGIES or item.get("source") not in SOURCES:
            raise ValueError("Candidate has an unexpected strategy or source")
        if item.get("status") not in ("watch", "blocked"):
            raise ValueError("Candidate status is not read-only")
        score = item.get("score")
        if type(score) is not int or not 0 <= score <= 100:
            raise ValueError("Invalid heuristic score")
        reasons = item.get("reasons")
        if not isinstance(reasons, (list, tuple)):
            raise ValueError("Missing candidate risk reasons")
        if reasons and item["status"] != "blocked":
            raise ValueError("Risk reasons cannot be marked watch")
        blocked += item["status"] == "blocked"
        watch += item["status"] == "watch"
        counts[item["source"]] += 1
        mints.add(mint)

    if len(mints) > limit or len(candidates) > 2 * limit:
        raise ValueError("Scanner exceeded its bounded per-run token budget")

    failed_providers: set[str] = set()
    for error in errors:
        if not isinstance(error, dict) or not isinstance(error.get("provider"), str):
            raise ValueError("Malformed provider error record")
        failed_providers.add(error["provider"])

    result = (
        "passed" if candidates and not errors else
        "degraded" if candidates else
        "inconclusive"
    )
    return {
        "result": result,
        "mode": "read_only_live_data_once",
        "trading_enabled": False,
        "max_mints": limit,
        "unique_mints": len(mints),
        "candidate_rows": len(candidates),
        "watch_rows_not_trade_signals": watch,
        "blocked_rows": blocked,
        "discovery": {
            source: {
                "candidate_rows": counts[source],
                "provider_error": source in failed_providers,
            }
            for source in sorted(SOURCES)
        },
        "goplus_errors": sum(
            error["provider"] == "goplus" for error in errors
        ),
        "provider_error_types": sorted(failed_providers),
        "note": "Pool/profile discovery is not mint-event proof; scores are unvalidated.",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="One-off read-only Solana API smoke")
    parser.add_argument("--limit", type=int, choices=[1, 2], default=2)
    args = parser.parse_args()
    try:
        payload = scan(live=True, limit=args.limit)
        report = assess(payload, args.limit)
    except Exception as exc:
        # Do not expose raw provider URLs, response bodies or local environment.
        print(json.dumps({
            "result": "failed", "trading_enabled": False,
            "error_class": type(exc).__name__
        }, indent=2))
        return 1
    print(json.dumps(report, indent=2, sort_keys=True))
    # A green check requires a real candidate and zero provider errors.
    # Rate limits, partial connectivity and no candidates must be visible.
    return 0 if report["result"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
