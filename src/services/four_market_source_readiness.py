# -*- coding: utf-8 -*-
"""Explicit, non-blocking real-source compatibility smoke for ETRE US/DE/HK.

Fetches exactly three allowlisted public publisher source URLs in a disposable
environment. Validates *candidate counts* with existing local parsers and
reports only counts, dates, HTTP-failure types, and upstream source hashes.

No market-membership lists, raw licensed files, user credentials, SQLite
writes, Yahoo requests, or brokerage orders are persisted/transmitted.
External publisher network failures are reported as inconclusive, not success.
This is NOT proof of 400 successfully analyzed Yahoo histories.
"""
from __future__ import annotations

import argparse
from datetime import date
import hashlib
import json
from pathlib import Path
import tempfile
from typing import Any, Callable
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import HTTPRedirectHandler, Request, build_opener

from src.services.ishares_oef_us100_import import convert_ishares_oef_csv
from src.services.xetra_t7_de100_import import convert_xetra_t7_csv
from src.services.hkex_hk100_import import convert_hkex_equities


_SOURCES = {
    "us": {
        "url": "https://www.ishares.com/us/products/239723/x/latest-holdings.csv",
        "suffix": ".csv",
        "max_bytes": 2_000_000,
        "hostname": "www.ishares.com",
    },
    "de": {
        "url": (
            "https://www.cashmarket.deutsche-boerse.com/resource/blob/1528/"
            "a4b7965b87cf1ef4621a28b85f145ae9/data/t7-xetr-allTradableInstruments.csv"
        ),
        "suffix": ".csv",
        "max_bytes": 5_000_000,
        "hostname": "www.cashmarket.deutsche-boerse.com",
    },
    "hk": {
        "url": (
            "https://www.hkex.com.hk/eng/services/trading/securities/"
            "securitieslists/ListOfSecurities.xlsx"
        ),
        "suffix": ".xlsx",
        "max_bytes": 8_000_000,
        "hostname": "www.hkex.com.hk",
    },
}
_PARSERS = {
    "us": convert_ishares_oef_csv,
    "de": convert_xetra_t7_csv,
    "hk": convert_hkex_equities,
}
_MARKETS = ("us", "de", "hk")


class _NoCrossHostRedirect(HTTPRedirectHandler):
    """Allow only exact-host redirects; prevents accidental external fetches."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        expected = urlparse(req.full_url).hostname
        parsed = urlparse(newurl)
        if parsed.scheme != "https" or parsed.hostname != expected:
            raise ValueError("Publisher redirected away from its HTTPS host")
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def fetch_official_bytes(market: str) -> bytes:
    """One bounded attempt, with no user-controlled URL and no disk cache."""
    item = _SOURCES[market]
    uri = item["url"]
    parsed = urlparse(uri)
    if parsed.scheme != "https" or parsed.hostname != item["hostname"]:
        raise ValueError("Publisher URL allowlist violation")
    request = Request(
        uri,
        headers={
            "Accept": "text/csv,application/vnd.openxmlformats-officedocument."
                      "spreadsheetml.sheet,application/octet-stream",
            "User-Agent": "ETRE-source-schema-check/1.0 (read-only)",
        },
    )
    with build_opener(_NoCrossHostRedirect()).open(request, timeout=25) as response:
        if urlparse(response.geturl()).hostname != item["hostname"]:
            raise ValueError("Unexpected final publisher host")
        data = response.read(item["max_bytes"] + 1)
    if not 0 < len(data) <= item["max_bytes"]:
        raise ValueError("Publisher source empty or above size cap")
    return data


def check_source(
    market: str, *,
    as_of: date,
    get_bytes: Callable[[str], bytes] = fetch_official_bytes,
) -> dict[str, Any]:
    """Aggregate-only result: never return member identifiers or raw bytes."""
    if market not in _SOURCES:
        raise ValueError("Unsupported market; only us/de/hk")
    info = _SOURCES[market]
    result: dict[str, Any] = {
        "market": market,
        "publisher_url": info["url"],
        "as_of": as_of.isoformat(),
        "status": "unavailable",
        "selected_symbols": 0,
        "eligible_equities_in_source": None,
        "source_date": None,
        "source_sha256": None,
    }
    try:
        blob = get_bytes(market)
        if not isinstance(blob, bytes) or not 0 < len(blob) <= info["max_bytes"]:
            raise ValueError("Publisher payload missing or larger than cap")
        digest = hashlib.sha256(blob).hexdigest()
        # Keep the original licensed export ONLY on a disposable local tempfile,
        # then delete it before returning even if conversion fails.
        with tempfile.TemporaryDirectory(prefix="etre-source-smoke-") as folder:
            source_file = Path(folder) / ("issuer" + info["suffix"])
            source_file.write_bytes(blob)
            roster = _PARSERS[market](source_file, as_of=as_of)
        if roster.get("market") != market or len(roster.get("symbols", [])) != 100:
            raise ValueError("Publisher importer did not select exactly 100 equities")
        result.update({
            "status": "schema_passed",
            "selected_symbols": 100,
            "eligible_equities_in_source": roster["eligible_equities_in_source"],
            "source_date": roster["as_of"],
            "source_sha256": digest,
        })
    except (HTTPError, URLError, TimeoutError, OSError, UnicodeError,
            ValueError, KeyError, TypeError) as exc:
        # No backfill or success claim from synthetic data after network failure.
        result["status"] = "unavailable_or_invalid"
        result["error_type"] = type(exc).__name__
        result["message"] = str(exc)[:180]
    return result


def source_readiness(
    *, as_of: date, markets: tuple[str, ...] = _MARKETS,
    get_bytes: Callable[[str], bytes] = fetch_official_bytes,
) -> dict[str, Any]:
    if len(set(markets)) != len(markets) or any(m not in _MARKETS for m in markets):
        raise ValueError("Only distinct US/DE/HK may be checked")
    items = [check_source(m, as_of=as_of, get_bytes=get_bytes) for m in markets]
    return {
        "scope": "etre_foreign_source_100_compatibility_smoke",
        "as_of": as_of.isoformat(),
        "markets": items,
        "attempted_markets": len(markets),
        "schema_passed_markets": sum(x["status"] == "schema_passed" for x in items),
        "complete_source_checks": all(x["status"] == "schema_passed" for x in items),
        "stock_rosters_exported": 0,
        "yahoo_histories_checked": 0,
        "broker_orders_sent": 0,
        "note": (
            "The importer selected 100 candidates from each passing live source. "
            "No downloaded source or candidate roster is published. "
            "Selection does not prove actual Yahoo price/currency validity, "
            "complete index membership or trading authorization."
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Check live US/DE/HK official reference-file compatibility (aggregate only)"
    )
    parser.add_argument("--as-of", type=date.fromisoformat, default=date.today())
    parser.add_argument("--markets", nargs="+", choices=_MARKETS, default=list(_MARKETS))
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        result = source_readiness(as_of=args.as_of, markets=tuple(args.markets))
    except ValueError as exc:
        parser.error(str(exc))
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n",
                           encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if not result["complete_source_checks"]:
        raise SystemExit("One or more live publisher files were unavailable or invalid")


if __name__ == "__main__":
    main()
