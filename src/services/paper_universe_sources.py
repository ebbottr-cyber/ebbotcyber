"""Allowlisted, manual-only BIST KAP and CoinPaprika catalogue ingestion.

The resulting records are *inventory candidates*, never verified tradable
instruments, current quotes, blockchain mint addresses, or trade instructions.
No refresh is scheduled. Network access requires the CLI's explicit --fetch.
"""
from __future__ import annotations

import csv
from datetime import datetime, timezone
from html.parser import HTMLParser
from io import StringIO
import json
import re
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import HTTPRedirectHandler, Request, build_opener

KAP_URL = "https://www.kap.org.tr/tr/bist-sirketler"
COINPAPRIKA_URL = "https://api.coinpaprika.com/v1/coins"
MAX_RESPONSE_BYTES = 64 * 1024 * 1024
_KAP_CODE = re.compile(r"^[A-Z0-9]{3,8}$")
_PAPRIKA_ID = re.compile(r"^[A-Za-z0-9:._+-]{1,128}$")


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


def coinpaprika_to_json(raw: str, observed_at: str) -> tuple[str, int, int]:
    """Preserve every catalogue ID and active flag; never invent chain addresses."""
    try:
        payload = json.loads(raw)
    except (TypeError, json.JSONDecodeError) as exc:
        raise ValueError("invalid_coinpaprika_json") from exc
    if not isinstance(payload, list):
        raise ValueError("coinpaprika_expected_array")
    records: list[dict[str, Any]] = []
    seen: set[str] = set()
    active_count = 0
    for item in payload:
        if not isinstance(item, dict):
            raise ValueError("invalid_coinpaprika_record")
        id_value, symbol, active = item.get("id"), item.get("symbol"), item.get("is_active")
        if not isinstance(id_value, str) or not _PAPRIKA_ID.fullmatch(id_value):
            raise ValueError("invalid_coinpaprika_id")
        if not isinstance(symbol, str) or not 1 <= len(symbol.strip()) <= 64:
            raise ValueError("invalid_coinpaprika_symbol")
        if type(active) is not bool:
            raise ValueError("invalid_coinpaprika_active_flag")
        if id_value in seen:
            raise ValueError("duplicate_coinpaprika_id")
        seen.add(id_value)
        if active:
            active_count += 1
        records.append({
            "network": "coinpaprika_catalog",
            "asset_id": id_value,
            "symbol": symbol.strip(),
            "source": "coinpaprika_coins",
            "active": active,
            "observed_at_utc": observed_at,
        })
    if not records:
        raise ValueError("empty_coinpaprika_catalog")
    return json.dumps({"assets": records}, ensure_ascii=False, separators=(",", ":")) + "\n", len(records), active_count


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req: Request, fp: Any, code: int,
                         msg: str, headers: Any, newurl: str) -> None:
        raise ValueError("source_redirect_not_allowed")


def fetch_source(url: str) -> str:
    """Exactly two constant HTTPS endpoints, no arbitrary user-controlled URLs."""
    if url not in (KAP_URL, COINPAPRIKA_URL):
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
