# -*- coding: utf-8 -*-
"""Read-only, indicative TCMB currency quotes for optional TRY UI display.

This service is intentionally independent from portfolio accounting and the
portfolio FX cache. It must never be used for trading or historical PnL.
"""

from __future__ import annotations

import logging
import threading
import time
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from zoneinfo import ZoneInfo

LOGGER = logging.getLogger(__name__)
TCMB_DAILY_XML_URL = "https://www.tcmb.gov.tr/kurlar/today.xml"
SUPPORTED_CURRENCIES = frozenset({"USD", "EUR", "CNY"})
MAX_XML_BYTES = 131_072
MAX_QUOTE_AGE_DAYS = 4
CACHE_SECONDS = 600
_CACHE_LOCK = threading.Lock()
_CACHE_VALUE: dict | None = None
_CACHE_UNTIL = 0.0


class TcmbQuoteUnavailable(ValueError):
    """No trustworthy, current published reference rate is available."""


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def _download_bulletin() -> bytes:
    # Fixed official URL, no user-controlled host/path or redirects.
    opener = urllib.request.build_opener(_NoRedirect)
    request = urllib.request.Request(
        TCMB_DAILY_XML_URL,
        headers={"User-Agent": "EBBot-TRY-Display/1.0", "Accept": "application/xml, text/xml"},
    )
    with opener.open(request, timeout=5) as response:
        payload = response.read(MAX_XML_BYTES + 1)
    if not payload or len(payload) > MAX_XML_BYTES:
        raise TcmbQuoteUnavailable("TCMB feed size is invalid")
    return payload


def parse_tcmb_bulletin(xml_bytes: bytes, *, today: date | None = None) -> dict:
    """Parse one official bulletin. Never derive a publication date from fetch time."""
    if not isinstance(xml_bytes, bytes) or len(xml_bytes) > MAX_XML_BYTES or not xml_bytes:
        raise TcmbQuoteUnavailable("TCMB bulletin payload is invalid")
    if b"<!doctype" in xml_bytes.lower() or b"<!entity" in xml_bytes.lower():
        raise TcmbQuoteUnavailable("XML document type declarations are not allowed")
    try:
        root = ET.fromstring(xml_bytes)
    except ET.ParseError as exc:
        raise TcmbQuoteUnavailable("TCMB XML is malformed") from exc
    if root.tag != "Tarih_Date":
        raise TcmbQuoteUnavailable("Unexpected TCMB document root")

    bulletin_date = root.attrib.get("Tarih", "")
    try:
        published = datetime.strptime(bulletin_date, "%d.%m.%Y").date()
    except ValueError as exc:
        raise TcmbQuoteUnavailable("TCMB bulletin date is missing or invalid") from exc

    english_date = root.attrib.get("Date")
    if english_date:
        try:
            if datetime.strptime(english_date, "%m/%d/%Y").date() != published:
                raise TcmbQuoteUnavailable("TCMB bulletin date fields disagree")
        except ValueError as exc:
            raise TcmbQuoteUnavailable("TCMB bulletin English date is invalid") from exc

    local_today = today or datetime.now(ZoneInfo("Europe/Istanbul")).date()
    day_age = (local_today - published).days
    if day_age < 0 or day_age > MAX_QUOTE_AGE_DAYS:
        raise TcmbQuoteUnavailable("TCMB bulletin is future-dated or too old")

    rates: dict[str, dict] = {}
    seen: set[str] = set()
    for item in root.findall("Currency"):
        code = item.get("CurrencyCode", "").upper().strip()
        if code not in SUPPORTED_CURRENCIES:
            continue
        if code in seen:
            raise TcmbQuoteUnavailable("Duplicate TCMB currency code")
        seen.add(code)
        if item.get("Kod") != code:
            raise TcmbQuoteUnavailable("TCMB currency identifiers disagree")
        unit_text = (item.findtext("Unit") or "").strip()
        selling_text = (item.findtext("ForexSelling") or "").strip()
        try:
            unit = int(unit_text)
            selling = Decimal(selling_text)
            if unit <= 0 or unit > 1000 or not selling.is_finite() or selling <= 0:
                continue
            per_unit = selling / Decimal(unit)
            rate = float(per_unit)
            if not 0 < rate < float("inf"):
                continue
        except (ValueError, InvalidOperation, OverflowError, ZeroDivisionError):
            continue
        rates[code] = {
            "source": "TCMB",
            "source_currency": code,
            "target_currency": "TRY",
            "source_unit": 1,
            "try_per_unit": rate,
            "as_of_date": published.isoformat(),
        }

    if not rates:
        raise TcmbQuoteUnavailable("TCMB bulletin has no supported rates")

    return {
        "available": True,
        "source": "TCMB",
        "rate_kind": "indicative_forex_selling",
        "as_of_date": published.isoformat(),
        "quotes": [rates[code] for code in ("USD", "EUR", "CNY") if code in rates],
    }


def get_tcmb_try_display_quotes(*, today: date | None = None) -> dict:
    """Short-lived success-only cache. Date validation also runs on a cache hit."""
    global _CACHE_VALUE, _CACHE_UNTIL
    local_today = today or datetime.now(ZoneInfo("Europe/Istanbul")).date()
    with _CACHE_LOCK:
        if _CACHE_VALUE is not None and time.monotonic() < _CACHE_UNTIL:
            issued = date.fromisoformat(_CACHE_VALUE["as_of_date"])
            if 0 <= (local_today - issued).days <= MAX_QUOTE_AGE_DAYS:
                return dict(_CACHE_VALUE)
        try:
            payload = _download_bulletin()
            result = parse_tcmb_bulletin(payload, today=local_today)
        except (OSError, urllib.error.URLError, TcmbQuoteUnavailable) as exc:
            LOGGER.warning("TCMB display quote unavailable: %s", exc)
            raise TcmbQuoteUnavailable("Valid dated TCMB quotes are unavailable") from exc
        _CACHE_VALUE = result
        _CACHE_UNTIL = time.monotonic() + CACHE_SECONDS
        return dict(result)
