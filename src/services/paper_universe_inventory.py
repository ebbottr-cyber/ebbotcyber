"""All-market stock and coin inventory audit; OFFLINE, no orders or price requests."""
from __future__ import annotations

from collections import Counter
import csv
import io
import json
from pathlib import Path
import re
from typing import Any, Iterable

SYMBOL = re.compile(r"^[A-Za-z0-9.^_-]{1,64}$")
MARKET = re.compile(r"^[a-z0-9_-]{2,40}$")
TOKEN = re.compile(r"^[A-Za-z0-9:._+-]{1,128}$")
MAX_FILE_BYTES = 64 * 1024 * 1024


def read_input(path: Path) -> str:
    if path.is_symlink() or not path.is_file() or path.stat().st_size > MAX_FILE_BYTES:
        raise ValueError("unavailable_or_unsafe_inventory_file")
    return path.read_text(encoding="utf-8-sig")


def market_name(value: Any) -> str:
    if not isinstance(value, str) or not MARKET.fullmatch(value.lower()):
        raise ValueError("invalid_market_or_network")
    return value.lower()


def add_stock(stocks: set[tuple[str, str]], markets: Counter[str],
              kinds: Counter[str], market: Any, code: Any, kind: Any) -> bool:
    if not isinstance(code, str) or not SYMBOL.fullmatch(code):
        raise ValueError("invalid_stock_symbol")
    market = market_name(market)
    if kind not in ("stock", "etf"):
        raise ValueError("invalid_stock_type")
    key = (market, code.upper())
    if key in stocks:
        return False
    stocks.add(key)
    markets[market] += 1
    kinds[kind] += 1
    return True


def coins_in_file(path: Path) -> Iterable[dict[str, Any]]:
    raw = read_input(path)
    if path.suffix.lower() == ".jsonl":
        items = [json.loads(line) for line in raw.splitlines() if line.strip()]
    elif path.suffix.lower() == ".json":
        items = json.loads(raw)
        if isinstance(items, dict) and set(items) == {"assets"}:
            items = items["assets"]
    else:
        raise ValueError("unsupported_coin_inventory_format")
    if not isinstance(items, list) or any(not isinstance(x, dict) for x in items):
        raise ValueError("invalid_coin_inventory")
    yield from items


def audit_universe(stock_index: Path, *, stock_manifests: Iterable[Path] = (),
                   coin_manifests: Iterable[Path] = ()) -> dict[str, Any]:
    """Register EVERY listed active instrument, never a selected top-N sample."""
    items = json.loads(read_input(Path(stock_index)))
    if not isinstance(items, list):
        raise ValueError("invalid_stock_index")
    stocks: set[tuple[str, str]] = set()
    coins: set[tuple[str, str]] = set()
    markets: Counter[str] = Counter()
    kinds: Counter[str] = Counter()
    networks: Counter[str] = Counter()
    indices = inactive = duplicates = 0

    for row in items:
        if not isinstance(row, list) or len(row) < 9 or type(row[8]) is not bool:
            raise ValueError("invalid_stock_index_row")
        if not row[8]:
            inactive += 1
            continue
        if row[7] == "index":
            indices += 1
            continue
        if not add_stock(stocks, markets, kinds, row[6], row[0], row[7]):
            duplicates += 1

    for path in stock_manifests:
        path = Path(path)
        if path.suffix.lower() != ".csv":
            raise ValueError("stock_manifest_must_be_csv")
        reader = csv.DictReader(io.StringIO(read_input(path)))
        if not reader.fieldnames or not {"market", "symbol", "source"}.issubset(reader.fieldnames):
            raise ValueError("invalid_stock_manifest_headers")
        for row in reader:
            if not isinstance(row.get("source"), str) or not row["source"].strip():
                raise ValueError("missing_stock_source")
            if row.get("active") == "false":
                inactive += 1
                continue
            kind = row.get("kind") or "stock"
            if kind == "index":
                indices += 1
                continue
            if not add_stock(stocks, markets, kinds, row["market"], row["symbol"], kind):
                duplicates += 1

    for path in coin_manifests:
        for row in coins_in_file(Path(path)):
            network = market_name(row.get("network"))
            address = row.get("asset_id")
            symbol = row.get("symbol")
            source = row.get("source")
            if not isinstance(address, str) or not TOKEN.fullmatch(address):
                raise ValueError("invalid_coin_asset_id")
            if not isinstance(symbol, str) or not (1 <= len(symbol.strip()) <= 64):
                raise ValueError("invalid_coin_symbol")
            if not isinstance(source, str) or not source.strip():
                raise ValueError("missing_coin_source")
            if row.get("active", True) is False:
                inactive += 1
                continue
            key = (network, address if network == "solana" else address.lower())
            if key in coins:
                duplicates += 1
                continue
            coins.add(key)
            networks[network] += 1

    missing = []
    if "tr" not in markets and "bist" not in markets:
        missing.append("bist_inventory_missing")
    if "tw" not in markets:
        missing.append("taiwan_inventory_missing")
    if "de" not in markets:
        missing.append("germany_inventory_missing")
    if not coins:
        missing.append("coin_inventory_missing")

    return {
        "status": "INVENTORY_ONLY",
        "stock_count": len(stocks),
        "coin_count": len(coins),
        "instrument_count": len(stocks) + len(coins),
        "index_records_excluded_from_stocks": indices,
        "inactive_records_excluded": inactive,
        "duplicates_deduplicated": duplicates,
        "stocks_by_market": dict(sorted(markets.items())),
        "stocks_by_kind": dict(sorted(kinds.items())),
        "coins_by_network": dict(sorted(networks.items())),
        "missing_source_inventories": missing,
        "fixed_top_n_cap": False,
        "full_exchange_coverage_verified": False,
        "source_currency_verified": False,
        "prices_loaded": False,
        "paper_trading_enabled": False,
        "live_trading_enabled": False,
        "network_requests": 0,
        "orders": 0,
        "journal_writes": 0,
        "automatic_scheduling_enabled": False,
    }
