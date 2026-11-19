"""Binance USDⓈ-M and COIN-M Futures public contract inventories, read-only.

No authenticated API keys, orders, wallet access, prices, leverage, funding
accrual or simulated fills. Futures are derivatives and never merged into Spot.
"""
from __future__ import annotations

from hashlib import sha256
import json
import re
from typing import Any

# Binance futures instruments are exchange-scoped opaque UTF-8 identifiers,
# NOT local file names, URL paths, wallet addresses or stock symbols.
# Reject invisible/control characters; do not lose legitimate Unicode glyphs.
_OPAQUE_EXCHANGE_SYMBOL = re.compile(r"^.{1,128}$")
_ENUM_TOKEN = re.compile(r"^[A-Z0-9_+-]{1,64}$")
_TYPES = {"usdm", "coinm"}


def _field(row: dict[str, Any], name: str, pattern: re.Pattern[str], *,
           row_index: int) -> str:
    value = row.get(name)
    if (not isinstance(value, str) or not pattern.fullmatch(value)
            or value != value.strip() or not value.isprintable()):
        # A bounded repr and the row position make future provider schema
        # changes diagnosable without silently deleting any contracts.
        detail = repr(value)[:100]
        raise ValueError(f"invalid_binance_futures_{name}_at_index_{row_index}: {detail}")
    return value


def futures_to_json(raw: str, observed_at: str, *, kind: str) -> tuple[str, int, int, int, int]:
    """Return (JSON, all, trading, perpetual, delivery), with zero symbol truncation.

    Contract type and status are kept even when not currently tradable.
    The Binance contract symbol is the identity, not base asset or Spot ticker.
    """
    if kind not in _TYPES:
        raise ValueError("unsupported_futures_type")
    try:
        payload = json.loads(raw)
    except (TypeError, json.JSONDecodeError) as exc:
        raise ValueError("invalid_binance_futures_json") from exc
    if not isinstance(payload, dict) or not isinstance(payload.get("symbols"), list):
        raise ValueError("binance_futures_missing_symbols")
    if not payload["symbols"]:
        raise ValueError("empty_binance_futures_catalog")
    network = "binance_" + kind + "_futures"
    source = "binance_" + kind + "_exchange_info"
    key = "status" if kind == "usdm" else "contractStatus"
    contracts: list[dict[str, Any]] = []
    seen: set[str] = set()
    trading = perpetual = delivery = 0
    for index, row in enumerate(payload["symbols"]):
        if not isinstance(row, dict):
            raise ValueError("invalid_futures_row_at_" + str(index))
        symbol = _field(row, "symbol", _OPAQUE_EXCHANGE_SYMBOL, row_index=index)
        base = _field(row, "baseAsset", _OPAQUE_EXCHANGE_SYMBOL, row_index=index)
        quote = _field(row, "quoteAsset", _OPAQUE_EXCHANGE_SYMBOL, row_index=index)
        margin = _field(row, "marginAsset", _OPAQUE_EXCHANGE_SYMBOL, row_index=index)
        contract_type = _field(row, "contractType", _ENUM_TOKEN, row_index=index)
        status = _field(row, key, _ENUM_TOKEN, row_index=index)
        if symbol in seen:
            raise ValueError("duplicate_binance_futures_symbol")
        seen.add(symbol)
        is_trading = status == "TRADING"
        trading += int(is_trading)
        perpetual += int(contract_type == "PERPETUAL")
        delivery += int(contract_type != "PERPETUAL")
        # Namespace is preserved in "market", and contract symbol is retained.
        item: dict[str, Any] = {
            "market": network,
            "instrument_kind": "derivative_contract",
            "asset_id": "futures:" + sha256((kind + ":" + symbol).encode("utf-8")).hexdigest(),
            "symbol": symbol,
            "contract_symbol": symbol,
            "base_asset": base,
            "quote_asset": quote,
            "margin_asset": margin,
            "contract_type": contract_type,
            "contract_status": status,
            "source": source,
            "active": is_trading,
            "observed_at_utc": observed_at,
            "leveraged_trading_enabled": False,
            "execution_enabled": False,
        }
        # Information required by a future contract-size aware paper model.
        size = row.get("contractSize")
        if size is not None:
            if isinstance(size, bool) or not isinstance(size, (int, float, str)):
                raise ValueError("invalid_binance_futures_contract_size")
            item["contract_size_unverified"] = str(size)
        delivery_date = row.get("deliveryDate")
        if delivery_date is not None:
            if type(delivery_date) is not int or delivery_date < 0:
                raise ValueError("invalid_binance_futures_delivery_date")
            item["delivery_date_ms"] = delivery_date
        contracts.append(item)
    return (
        json.dumps({"contracts": contracts}, ensure_ascii=False, separators=(",", ":")) + "\n",
        len(contracts), trading, perpetual, delivery,
    )
