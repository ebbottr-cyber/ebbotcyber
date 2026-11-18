"""Allowlisted, manual-only BIST KAP and Binance Spot catalogue ingestion.

The resulting records are *inventory candidates*, never verified tradable
instruments, current quotes, blockchain mint addresses, or trade instructions.
No refresh is scheduled. Network access requires the CLI's explicit --fetch.
"""
from __future__ import annotations

import csv
import hashlib
from datetime import datetime, timezone
from html.parser import HTMLParser
from io import StringIO
import json
import re
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import HTTPRedirectHandler, Request, build_opener

KAP_URL = "https://www.kap.org.tr/tr/bist-sirketler"
BINANCE_SPOT_URL = "https://data-api.binance.vision/api/v3/exchangeInfo"
MAX_RESPONSE_BYTES = 64 * 1024 * 1024
_KAP_CODE = re.compile(r"^[A-Z0-9]{3,8}$")



class _KapTables(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.tables: list[list[list[str]]] = []
        self.table: list[list[str]] | None = None
        self.row: list[str] | None = None
        self.cell: list[str] | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "table" and self.table is None:
            self.table = []
        elif tag == "tr" and self.table is not None:
            self.row = []
        elif tag in ("td", "th") and self.row is not None:
            self.cell = []

    def handle_data(self, data: str) -> None:
        if self.cell is not None:
            self.cell.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag in ("td", "th") and self.cell is not None and self.row is not None:
            self.row.append(" ".join("".join(self.cell).split()))
            self.cell = None
        elif tag == "tr" and self.row is not None and self.table is not None:
            if self.row:
                self.table.append(self.row)
            self.row = None
        elif tag == "table" and self.table is not None:
            self.tables.append(self.table)
            self.table = None


def kap_bist_to_csv(raw_html: str, observed_at: str) -> tuple[str, int]:
    """Parse *only* a labelled KAP company table; never guess missing tickers."""
    if not isinstance(raw_html, str) or not 50 <= len(raw_html) <= MAX_RESPONSE_BYTES:
        raise ValueError("invalid_kap_html")
    parser = _KapTables()
    parser.feed(raw_html)
    candidates: set[str] = set()
    matching_table = False
    for table in parser.tables:
        header_idx = next((
            i for i, row in enumerate(table)
            if len(row) >= 2 and row[0].strip().lower() == "kod"
            and ("şirket" in row[1].lower() or "sirket" in row[1].lower())
        ), None)
        if header_idx is None:
            continue
        matching_table = True
        for row in table[header_idx + 1:]:
            if len(row) < 2 or not row[1].strip():
                continue
            # KAP sometimes publishes several codes for the same member.
            # These are *listing candidates*, not proof of an active ISIN.
            for part in row[0].upper().split():
                if _KAP_CODE.fullmatch(part):
                    candidates.add(part + ".IS")
    if not matching_table or not candidates:
        raise ValueError("no_verified_kap_company_table")
    # Company count is a weak safety check, not completeness verification.
    output = StringIO(newline="")
    writer = csv.writer(output, lineterminator="\n")
    writer.writerow(["market", "symbol", "source", "kind", "observed_at_utc"])
    for symbol in sorted(candidates):
        writer.writerow(["tr", symbol, "kap_bist_company_directory", "stock", observed_at])
    return output.getvalue(), len(candidates)


def _exchange_asset_name(value: Any) -> str:
    """Binance asset symbols are exchange identifiers, not wallet addresses."""
    if (not isinstance(value, str) or not 1 <= len(value) <= 64
            or value != value.strip() or not value.isprintable()):
        raise ValueError("invalid_binance_asset_symbol")
    return value


def binance_spot_to_json(raw: str, observed_at: str) -> tuple[str, int, int, int, int]:
    """Return all unique Spot assets and all active/halted Spot pair counts.

    Includes both baseAsset and quoteAsset so quote-only assets are not silently
    omitted. Neither an exchange ticker nor hash-ID establishes a chain address.
    """
    try:
        payload = json.loads(raw)
    except (TypeError, json.JSONDecodeError) as exc:
        raise ValueError("invalid_binance_exchange_info_json") from exc
    if not isinstance(payload, dict) or not isinstance(payload.get("symbols"), list):
        raise ValueError("binance_exchange_info_missing_symbols")
    if not payload["symbols"]:
        raise ValueError("empty_binance_exchange_info")
    assets: dict[str, dict[str, Any]] = {}
    seen_pairs: set[str] = set()
    spot_pair_count = 0
    trading_spot_pair_count = 0

    for index, pair in enumerate(payload["symbols"]):
        if not isinstance(pair, dict):
            raise ValueError(f"invalid_binance_pair_at_index_{index}")
        pair_name = _exchange_asset_name(pair.get("symbol"))
        base = _exchange_asset_name(pair.get("baseAsset"))
        quote = _exchange_asset_name(pair.get("quoteAsset"))
        status = pair.get("status")
        allowed = pair.get("isSpotTradingAllowed")
        if not isinstance(status, str) or type(allowed) is not bool:
            raise ValueError(f"invalid_binance_spot_status_at_index_{index}")
        if pair_name in seen_pairs:
            raise ValueError(f"duplicate_binance_pair_at_index_{index}")
        seen_pairs.add(pair_name)
        if not allowed:
            continue
        spot_pair_count += 1
        trading = status == "TRADING"
        if trading:
            trading_spot_pair_count += 1
        for asset in (base, quote):
            if asset not in assets:
                # Stable opaque exchange-scoped identity; NEVER a token contract.
                digest = hashlib.sha256(asset.encode("utf-8")).hexdigest()
                assets[asset] = {
                    "network": "binance_spot_catalog",
                    "asset_id": "binance:asset:" + digest,
                    "symbol": asset,
                    "source": "binance_spot_exchange_info",
                    "active": False,
                    "observed_at_utc": observed_at,
                    "spot_pair_count": 0,
                    "trading_spot_pair_count": 0,
                }
            assets[asset]["spot_pair_count"] += 1
            if trading:
                assets[asset]["trading_spot_pair_count"] += 1
                assets[asset]["active"] = True
    if not assets or not spot_pair_count:
        raise ValueError("empty_binance_spot_catalog")
    records = [assets[name] for name in sorted(assets)]
    active_count = sum(record["active"] for record in records)
    return (
        json.dumps({"assets": records}, ensure_ascii=False, separators=(",", ":")) + "\n",
        len(records),
        active_count,
        spot_pair_count,
        trading_spot_pair_count,
    )


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req: Request, fp: Any, code: int,
                         msg: str, headers: Any, newurl: str) -> None:
        raise ValueError("source_redirect_not_allowed")


def fetch_source(url: str) -> str:
    """Exactly two constant HTTPS endpoints, no arbitrary user-controlled URLs."""
    if url not in (KAP_URL, BINANCE_SPOT_URL):
        raise ValueError("unapproved_inventory_source")
    request = Request(url, headers={
        "User-Agent": "EBBot-Paper-Universe-Manual-Inventory/1.0",
        "Accept": "text/html" if url == KAP_URL else "application/json",
    })
    try:
        with build_opener(_NoRedirect()).open(request, timeout=20) as response:
            data = response.read(MAX_RESPONSE_BYTES + 1)
            if len(data) > MAX_RESPONSE_BYTES:
                raise ValueError("inventory_source_response_too_large")
            content_type = response.headers.get("Content-Type", "").lower()
            expected = "text/html" if url == KAP_URL else "application/json"
            if expected not in content_type:
                raise ValueError("unexpected_inventory_content_type")
            return data.decode("utf-8-sig")
    except (HTTPError, URLError, TimeoutError, UnicodeError) as exc:
        raise ValueError("inventory_provider_unavailable") from exc


def observed_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")
