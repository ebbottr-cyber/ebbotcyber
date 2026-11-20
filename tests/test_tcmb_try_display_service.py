# -*- coding: utf-8 -*-
"""Offline guardrails for optional, read-only TCMB TRY display quotes."""

from __future__ import annotations

import unittest
from datetime import date
from unittest.mock import patch

from src.services import tcmb_try_display_service as service


def bulletin(date_text="19.11.2026", *, usd="50.1000", eur="60.0000", cny="7.0000", cny_unit="1"):
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<Tarih_Date Tarih="{date_text}" Date="11/19/2026" Bulten_No="2026/217">
  <Currency Kod="USD" CurrencyCode="USD"><Unit>1</Unit><ForexSelling>{usd}</ForexSelling></Currency>
  <Currency Kod="EUR" CurrencyCode="EUR"><Unit>1</Unit><ForexSelling>{eur}</ForexSelling></Currency>
  <Currency Kod="CNY" CurrencyCode="CNY"><Unit>{cny_unit}</Unit><ForexSelling>{cny}</ForexSelling></Currency>
</Tarih_Date>""".encode("utf-8")


class TcmbDisplayUnitTest(unittest.TestCase):
    def setUp(self):
        service._CACHE_VALUE = None
        service._CACHE_UNTIL = 0

    def tearDown(self):
        service._CACHE_VALUE = None
        service._CACHE_UNTIL = 0

    def test_bulletin_uses_real_date_and_normalizes_unit(self):
        payload = service.parse_tcmb_bulletin(
            bulletin(cny="700", cny_unit="100"), today=date(2026, 11, 20),
        )
        self.assertEqual(payload["as_of_date"], "2026-11-19")
        self.assertEqual(payload["rate_kind"], "indicative_forex_selling")
        self.assertEqual([x["source_currency"] for x in payload["quotes"]], ["USD", "EUR", "CNY"])
        self.assertAlmostEqual(payload["quotes"][2]["try_per_unit"], 7.0)
        self.assertEqual(payload["quotes"][2]["source_unit"], 1)

    def test_outdated_future_or_inconsistent_bulletins_are_rejected(self):
        for content in (
            bulletin(date_text="11.11.2026"),
            bulletin(date_text="21.11.2026"),
            bulletin(date_text="20.11.2026"),  # disagrees with English date
            bulletin(date_text="not-a-date"),
            bulletin().replace(b"Tarih_Date", b"Other_Date"),
            bulletin().replace(b"CurrencyCode=\"USD\"", b"CurrencyCode=\"EUR\""),
            b"<!DOCTYPE x [<!ENTITY x SYSTEM 'file:///etc/passwd'>]><Tarih_Date/>",
            b"not xml",
            b"x" * (service.MAX_XML_BYTES + 1),
        ):
            with self.subTest(content=content[:80]):
                with self.assertRaises(service.TcmbQuoteUnavailable):
                    service.parse_tcmb_bulletin(content, today=date(2026, 11, 20))

    def test_invalid_prices_fail_closed_without_invented_try(self):
        with self.assertRaises(service.TcmbQuoteUnavailable):
            service.parse_tcmb_bulletin(
                bulletin(usd="NaN", eur="-1", cny="0"),
                today=date(2026, 11, 20),
            )

    def test_partial_bulletin_only_exports_verified_currencies(self):
        p = service.parse_tcmb_bulletin(
            bulletin(usd="", eur="61", cny="NaN"), today=date(2026, 11, 20),
        )
        self.assertEqual([x["source_currency"] for x in p["quotes"]], ["EUR"])

    def test_cache_is_short_lived_and_never_reuses_stale_bulletin(self):
        with patch.object(service, "_download_bulletin", return_value=bulletin()) as download:
            first = service.get_tcmb_try_display_quotes(today=date(2026, 11, 20))
            second = service.get_tcmb_try_display_quotes(today=date(2026, 11, 20))
            self.assertEqual(first, second)
            self.assertEqual(download.call_count, 1)
            with self.assertRaises(service.TcmbQuoteUnavailable):
                service.get_tcmb_try_display_quotes(today=date(2026, 11, 25))
            self.assertEqual(download.call_count, 2)

    def test_network_failure_does_not_cache_unsafe_fallback(self):
        with patch.object(service, "_download_bulletin", side_effect=OSError("unreachable")):
            with self.assertRaises(service.TcmbQuoteUnavailable):
                service.get_tcmb_try_display_quotes(today=date(2026, 11, 20))
            self.assertIsNone(service._CACHE_VALUE)


class TcmbDisplayEndpointTest(unittest.TestCase):
    def test_read_only_api_available_and_unavailable(self):
        from fastapi import FastAPI
        from fastapi.testclient import TestClient
        from api.v1.endpoints import portfolio

        app = FastAPI()
        app.include_router(portfolio.router, prefix="/api/v1/portfolio")
        client = TestClient(app)
        safe = service.parse_tcmb_bulletin(bulletin(), today=date(2026, 11, 20))
        with patch.object(portfolio, "get_tcmb_try_display_quotes", return_value=safe):
            response = client.get("/api/v1/portfolio/fx/try-display")
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()["as_of_date"], "2026-11-19")
        with patch.object(
            portfolio, "get_tcmb_try_display_quotes",
            side_effect=service.TcmbQuoteUnavailable("offline"),
        ):
            response = client.get("/api/v1/portfolio/fx/try-display")
        self.assertEqual(response.status_code, 503)
        self.assertNotIn("try_per_unit", response.text)


if __name__ == "__main__":
    unittest.main()
