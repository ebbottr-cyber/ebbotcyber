"""Offline Solana Meme Radar strategy replay on explicitly synthetic fixtures.

Never contacts a market provider, wallet, exchange or order router. Input
files contain invented snapshots for reproducible accounting tests only.
"""
from __future__ import annotations

import argparse
import json
import math
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

from data_provider.solana_meme import MemeQuote, is_solana_address
from src.services.solana_meme_radar import evaluate
from src.services.solana_paper_replay import replay

_ALLOWED_STRATEGIES = ("new_coin_hunter", "momentum_watcher")
_MAX_FILE_SIZE = 512_000


def _positive_number(value: Any, name: str) -> float:
    if isinstance(value, bool) or value is None:
        raise ValueError(f"Invalid {name}")
    try:
        d = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise ValueError(f"Invalid {name}") from exc
    if not d.is_finite() or d <= 0:
        raise ValueError(f"Invalid {name}")
    f = float(d)
    if not math.isfinite(f) or f <= 0:
        raise ValueError(f"Invalid {name}")
    return f


def _optional_nonnegative(value: Any, name: str) -> float | None:
    if value is None:
        return None
    try:
        f = float(value)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError(f"Invalid {name}") from exc
    if not math.isfinite(f) or f < 0:
        raise ValueError(f"Invalid {name}")
    return f


def _count(value: Any, name: str) -> int | None:
    if value is None:
        return None
    if type(value) is not int or value < 0:
        raise ValueError(f"Invalid {name}")
    return value


def run_fixture(document: dict[str, Any]) -> dict[str, Any]:
    """Feed every snapshot through the current, production watchlist evaluator."""
    if not isinstance(document, dict) or document.get("schema_version") != 1:
        raise ValueError("Unsupported replay schema")
    if document.get("data_origin") != "synthetic":
        raise ValueError("Only explicitly synthetic fixtures accepted in v1")
    mint = document.get("mint")
    if not is_solana_address(mint):
        raise ValueError("Invalid synthetic mint identifier")
    frames = document.get("snapshots")
    if not isinstance(frames, list) or not 3 <= len(frames) <= 2000:
        raise ValueError("Require 3 to 2000 synthetic snapshots")
    started = -1
    rows: dict[str, list[dict[str, Any]]] = {key: [] for key in _ALLOWED_STRATEGIES}
    for frame in frames:
        if not isinstance(frame, dict):
            raise ValueError("Malformed fixture snapshot")
        stamp = frame.get("timestamp_ms")
        if type(stamp) is not int or stamp <= started:
            raise ValueError("Nonchronological snapshot timestamps")
        started = stamp
        source = frame.get("source")
        if source not in ("geckoterminal", "dexscreener"):
            raise ValueError("Invalid source")
        security = frame.get("security")
        if security is not None and not isinstance(security, dict):
            raise ValueError("Invalid security record")
        quoted_price = _positive_number(frame.get("price_usd"), "price_usd")
        liquidity = _optional_nonnegative(frame.get("liquidity_usd"), "liquidity_usd")
        volume = _optional_nonnegative(frame.get("volume_h24_usd"), "volume_h24_usd")
        raw_change = frame.get("change_m5_pct")
        if raw_change is None:
            change = None
        else:
            try:
                change = float(raw_change)
            except (ValueError, TypeError, OverflowError) as exc:
                raise ValueError("Invalid 5-minute change") from exc
            if not math.isfinite(change):
                raise ValueError("Invalid 5-minute change")
        created = frame.get("pool_created_at_ms")
        if created is not None and (type(created) is not int or created < 0):
            raise ValueError("Invalid pool time")
        quote = MemeQuote(
            mint=mint, symbol="SYNTHETIC", source=source,
            pool_id="solana_synthetic_test_pool",
            price_usd=quoted_price, liquidity_usd=liquidity, volume_h24_usd=volume,
            buys_m5=_count(frame.get("buys_m5"), "buys_m5"),
            sells_m5=_count(frame.get("sells_m5"), "sells_m5"),
            change_m5_pct=change, pool_created_at_ms=created,
            observed_at_ms=stamp,
        )
        for strategy in _ALLOWED_STRATEGIES:
            decision = evaluate(quote, strategy, stamp, security)
            rows[strategy].append({
                "timestamp_ms": stamp, "price_usd": frame["price_usd"],
                "status": decision.status, "reasons": list(decision.reasons),
            })
    return {
        "scenario": str(document.get("scenario") or "unnamed")[:80],
        "mode": "offline_synthetic_paper_replay",
        "data_origin": "synthetic",
        "trading_enabled": False, "wallet_enabled": False,
        "external_network_requests": 0,
        "synthetic_mint": mint,
        "strategies": {strategy: replay(data, strategy=strategy)
                       for strategy, data in rows.items()},
        "disclaimer": "Invented price paths only. NOT verified market performance, actual trades or financial advice.",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Offline synthetic Solana paper replay; NO orders")
    parser.add_argument("--fixture", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    try:
        if args.fixture.stat().st_size > _MAX_FILE_SIZE:
            raise ValueError("Fixture exceeds safe size cap")
        doc = json.loads(args.fixture.read_text(encoding="utf-8"))
        report = run_fixture(doc)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        parser.error(f"Invalid offline fixture: {type(exc).__name__}")
    rendered = json.dumps(report, indent=2, ensure_ascii=False, sort_keys=True)
    if args.output is not None:
        args.output.write_text(rendered + "\n", encoding="utf-8")
    print(rendered)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
