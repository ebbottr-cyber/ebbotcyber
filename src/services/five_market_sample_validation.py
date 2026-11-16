# -*- coding: utf-8 -*-
"""Read-only sample coverage check for ETRE's five investment-focus markets.

This is a bounded, opt-in Yahoo historical-data diagnostic, not an exchange-wide
stock screener, a buy/sell recommendation, or a broker trading integration.
Never touches SQLite, positions, LLM credentials or order APIs.
"""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import date, datetime
import json
from pathlib import Path
import re
from typing import Any
from zoneinfo import ZoneInfo

from src.services.six_market_live_smoke import MarketProbe, probe_six_markets


# One independently checked equity per selected market.
FOCUS_MARKETS = ("tr", "us", "de", "hk", "jp")
CORE_PROBES: tuple[MarketProbe, ...] = (
    MarketProbe("tr", "THYAO.IS", "THYAO.IS", "TRY"),
    MarketProbe("us", "AAPL", "AAPL", "USD"),
    MarketProbe("de", "SAP.DE", "SAP.DE", "EUR"),
    MarketProbe("hk", "HK00700", "0700.HK", "HKD"),
    MarketProbe("jp", "7203.T", "7203.T", "JPY"),
)
# Bounded expansion for coverage exploration; not an official exchange
# constituent list or a guarantee that these names trade at every broker.
EXTRA_PROBES: tuple[MarketProbe, ...] = (
    MarketProbe("tr", "ASELS.IS", "ASELS.IS", "TRY"),
    MarketProbe("us", "MSFT", "MSFT", "USD"),
    MarketProbe("de", "SIE.DE", "SIE.DE", "EUR"),
    MarketProbe("hk", "HK01810", "1810.HK", "HKD"),
    MarketProbe("jp", "6758.T", "6758.T", "JPY"),
)


# Explicit, conservative equity shapes. US classes (BRK.B) remain allowed;
# known US index aliases, e.g. SPX, are excluded separately.
_MARKET_CODE_PATTERNS = {
    "tr": re.compile(r"[A-Z]{4,5}\.IS"),
    "us": re.compile(r"[A-Z]{1,5}(?:\.[A-Z])?"),
    "de": re.compile(r"[A-Z][A-Z0-9]{0,7}\.DE"),
    "hk": re.compile(r"HK[0-9]{5}"),
    "jp": re.compile(r"[0-9]{4,5}\.T"),
}
_MARKET_CURRENCIES = {
    "tr": "TRY", "us": "USD", "de": "EUR", "hk": "HKD", "jp": "JPY",
}
_MAX_SYMBOLS_PER_MARKET = 100
_MAX_CUSTOM_SYMBOLS = _MAX_SYMBOLS_PER_MARKET * len(FOCUS_MARKETS)
_MAX_SYMBOLS_FILE_BYTES = 64_000


def build_custom_probes(symbols: tuple[str, ...]) -> tuple[MarketProbe, ...]:
    """Validate up to 100 symbols per market, maximum 500, before any fetch.

    Syntax is not evidence that an instrument is listed or broker-tradable.
    Unknown market identities and US indexes are rejected rather than
    sending them to a guessed fallback market.
    """
    from data_provider.us_index_mapping import is_us_index_code
    from data_provider.yfinance_fetcher import YfinanceFetcher
    from src.core.trading_calendar import get_market_for_stock

    if not 1 <= len(symbols) <= _MAX_CUSTOM_SYMBOLS:
        raise ValueError("Select between 1 and 500 stock symbols (100 per market)")
    converter = YfinanceFetcher()
    probes = []
    seen: set[str] = set()
    per_market: Counter[str] = Counter()
    for raw in symbols:
        code = str(raw).strip().upper()
        if not code or code in seen:
            raise ValueError(f"Empty or duplicate stock symbol: {code!r}")
        seen.add(code)
        market = get_market_for_stock(code)
        if (
            market not in FOCUS_MARKETS
            or is_us_index_code(code)
            or _MARKET_CODE_PATTERNS[market].fullmatch(code) is None
        ):
            raise ValueError(f"Unsupported or ambiguous five-market equity symbol: {code}")
        yahoo = converter._convert_stock_code(code)
        if not yahoo or not isinstance(yahoo, str):
            raise ValueError(f"Cannot determine Yahoo ticker for {code}")
        per_market[market] += 1
        if per_market[market] > _MAX_SYMBOLS_PER_MARKET:
            raise ValueError(f"Market {market} exceeds 100 selected stock symbols")
        probes.append(MarketProbe(market, code, yahoo, _MARKET_CURRENCIES[market]))
    return tuple(probes)


def validate_five_market_samples(
    *,
    as_of: date,
    sample_set: str = "core",
    symbols: tuple[str, ...] | None = None,
    **kwargs: Any,
) -> dict[str, Any]:
    """Keep each stock and market's data quality distinct, including failures."""
    if sample_set not in {"core", "expanded"}:
        raise ValueError("sample_set must be core or expanded")
    probes = (
        build_custom_probes(symbols) if symbols is not None else
        CORE_PROBES if sample_set == "core" else CORE_PROBES + EXTRA_PROBES
    )
    if len({probe.code for probe in probes}) != len(probes):
        raise ValueError("duplicate sample symbols")

    result = probe_six_markets(
        as_of=as_of,
        probes=probes,
        scope=(
            "etre_five_market_custom_historical_symbols" if symbols is not None else
            f"etre_five_market_{sample_set}_historical_samples"
        ),
        **kwargs,
    )

    result["checked_symbols"] = result.pop("checked_markets")
    result["analyzed_symbols"] = result.pop("analyzed_markets")
    by_market: dict[str, dict[str, Any]] = {}
    for market in FOCUS_MARKETS:
        subset = [item for item in result["results"] if item["market"] == market]
        statuses = Counter(str(item["status"]) for item in subset)
        successes = statuses.get("analyzed", 0)
        by_market[market] = {
            "checked_symbols": len(subset),
            "analyzed_symbols": successes,
            "target_symbols": _MAX_SYMBOLS_PER_MARKET,
            "remaining_to_target": _MAX_SYMBOLS_PER_MARKET - len(subset),
            "sample_status": (
                "not_requested" if not subset
                else "samples_passed" if successes == len(subset)
                else "partial" if successes > 0 else "samples_failed"
            ),
            "failure_status_counts": {
                key: count for key, count in sorted(statuses.items()) if key != "analyzed"
            },
        }
    result["markets_checked"] = len({spec.market for spec in probes})
    result["target_symbols_per_market"] = _MAX_SYMBOLS_PER_MARKET
    result["target_symbols_total"] = _MAX_CUSTOM_SYMBOLS
    result["remaining_to_target"] = _MAX_CUSTOM_SYMBOLS - len(probes)
    result["market_scope"] = list(FOCUS_MARKETS)
    result["by_market"] = by_market
    result["note"] = (
        "Yahoo daily price, currency, completed session and technical-score "
        "sample validation only. The listed symbols are examples, not full "
        "exchange coverage, live quotes, Midas account permissions or trades."
    )
    return result


def main() -> None:
    parser = argparse.ArgumentParser(
        description="ETRE five-market read-only historical sample validation"
    )
    source = parser.add_mutually_exclusive_group()
    source.add_argument("--sample-set", choices=("core", "expanded"), default="core")
    source.add_argument(
        "--symbols",
        help="Comma-separated stock codes (up to 100 per market, 500 total)",
    )
    source.add_argument(
        "--symbols-file", type=Path,
        help="UTF-8 file of newline/comma-separated stock codes (up to 500)"
    )
    parser.add_argument(
        "--as-of", type=date.fromisoformat,
        default=datetime.now(ZoneInfo("Europe/Istanbul")).date(),
    )
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    symbols = tuple(args.symbols.split(",")) if args.symbols is not None else None
    if args.symbols_file is not None:
        try:
            if not args.symbols_file.is_file() or args.symbols_file.stat().st_size > _MAX_SYMBOLS_FILE_BYTES:
                parser.error("Stock code file missing or exceeds 64 KB")
            content = args.symbols_file.read_text(encoding="utf-8-sig")
        except (OSError, UnicodeError) as exc:
            parser.error(f"Cannot read stock code file: {exc}")
        symbols = tuple(re.split(r"[,\\s]+", content.strip()))
        if not content.strip():
            parser.error("Stock code file is empty")
    report = validate_five_market_samples(
        as_of=args.as_of,
        sample_set=args.sample_set,
        symbols=symbols,
    )
    payload = json.dumps(report, indent=2, ensure_ascii=False) + "\n"
    if args.output:
        args.output.write_text(payload, encoding="utf-8")
    print(payload, end="")
    expected = (
        len(symbols) if symbols is not None else
        len(CORE_PROBES) if args.sample_set == "core" else len(CORE_PROBES + EXTRA_PROBES)
    )
    if report["checked_symbols"] != expected or report["analyzed_symbols"] != expected:
        raise SystemExit(
            f"ETRE {'custom' if symbols is not None else args.sample_set} historical sample check incomplete: "
            f"{report['analyzed_symbols']}/{expected}; inspect JSON per-symbol statuses"
        )


if __name__ == "__main__":
    main()
