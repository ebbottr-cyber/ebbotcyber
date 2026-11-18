"""Deterministic tests: Germany API must never trade or fetch on inventory GET."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest import TestCase
from unittest.mock import Mock, patch

from fastapi import HTTPException, Response
from api.v1.endpoints import xetra as api
from src.services.xetra_quote_guard import check_symbols

INVENTORY = {
    "SAP.DE": {"isin": "DE0007164600", "source_as_of_date": "2026-11-18"},
    "SIE.DE": {"isin": "DE0007236101", "source_as_of_date": "2026-11-18"},
}


class GermanyPanelApiTests(TestCase):
    def test_get_inventory_lists_official_candidates_without_provider_call(self):
        with (patch.object(api, "read_xetra_manifest", return_value=INVENTORY),
              patch.object(api, "fetch_yahoo_chart") as fetch,
              patch.object(api, "is_auth_enabled", return_value=False)):
            response = Response()
            result = api.get_inventory(response, query="SAP", limit=20)
        self.assertEqual(result["candidate_count"], 2)
        self.assertEqual(result["items"][0]["symbol"], "SAP.DE")
        self.assertEqual(result["items"][0]["isin"], "DE0007164600")
        self.assertFalse(result["items"][0]["price_symbol_verified"])
        self.assertFalse(result["manual_quote_check_enabled"])
        self.assertFalse(result["quotes_auto_loaded"])
        self.assertFalse(result["live_trading_enabled"])
        self.assertEqual(response.headers.get("Cache-Control"), "no-store")
        fetch.assert_not_called()

    def test_quote_api_disallowed_when_auth_or_explicit_toggle_off(self):
        request = api.XetraQuoteCheckRequest(symbols=["SAP.DE"])
        for admin, feature in ((False, "true"), (True, ""), (True, "false")):
            with self.subTest(admin=admin, feature=feature):
                with (patch.object(api, "is_auth_enabled", return_value=admin),
                      patch.object(api.os, "getenv", return_value=feature),
                      patch.object(api, "fetch_yahoo_chart") as fetch):
                    with self.assertRaises(HTTPException) as exc:
                        api.check_xetra_quotes(request, Response())
                    self.assertEqual(exc.exception.status_code, 403)
                    fetch.assert_not_called()

    def test_wrong_or_duplicate_symbols_fail_before_provider_fetch(self):
        with (patch.object(api, "is_auth_enabled", return_value=True),
              patch.object(api.os, "getenv", return_value="true"),
              patch.object(api, "read_xetra_manifest", return_value=INVENTORY),
              patch.object(api, "fetch_yahoo_chart") as fetch):
            for code_list in (["NOTLISTED.DE"], ["SAP.DE", "SAP.DE"]):
                with self.subTest(codes=code_list):
                    with self.assertRaises(HTTPException) as exc:
                        api.check_xetra_quotes(api.XetraQuoteCheckRequest(symbols=code_list), Response())
                    self.assertEqual(exc.exception.status_code, 422)
            fetch.assert_not_called()

    def test_manual_sample_calls_fixed_verifier_once_per_selected_candidate(self):
        now = datetime.now(timezone.utc)
        payload = {
            "chart": {"error": None, "result": [{"meta": {
                "symbol": "SAP.DE",
                "currency": "EUR",
                "fullExchangeName": "XETRA",
                "exchangeTimezoneName": "Europe/Berlin",
                "instrumentType": "EQUITY",
                "regularMarketPrice": 192.15,
                "regularMarketTime": int((now - timedelta(hours=2)).timestamp()),
            }}]},
        }
        with (patch.object(api, "is_auth_enabled", return_value=True),
              patch.object(api.os, "getenv", return_value="true"),
              patch.object(api, "read_xetra_manifest", return_value=INVENTORY),
              patch.object(api, "fetch_yahoo_chart", return_value=payload) as fetch):
            response = Response()
            result = api.check_xetra_quotes(api.XetraQuoteCheckRequest(symbols=["SAP.DE"]), response)
        self.assertEqual(fetch.call_count, 1)
        self.assertEqual(fetch.call_args.args, ("SAP.DE",))
        self.assertEqual(result["quote_metadata_matches"], 1)
        self.assertEqual(result["checks"][0]["status"], "QUOTE_METADATA_MATCH")
        self.assertFalse(result["checks"][0]["isin_identity_verified"])
        self.assertFalse(result["checks"][0]["real_time_price_verified"])
        self.assertFalse(result["paper_trading_enabled"])
        self.assertFalse(result["live_trading_enabled"])
        self.assertEqual(result["orders"], 0)
        self.assertEqual(response.headers.get("Cache-Control"), "no-store")

    def test_provider_failure_yields_no_approved_quote(self):
        with (patch.object(api, "is_auth_enabled", return_value=True),
              patch.object(api.os, "getenv", return_value="true"),
              patch.object(api, "read_xetra_manifest", return_value=INVENTORY),
              patch.object(api, "fetch_yahoo_chart", side_effect=TimeoutError)):
            result = api.check_xetra_quotes(
                api.XetraQuoteCheckRequest(symbols=["SAP.DE"]), Response())
        self.assertEqual(result["status"], "BLOCKED")
        self.assertEqual(result["checks"][0]["reason"], "provider_request_failed")
        self.assertEqual(result["orders"], 0)

    def test_route_mount(self):
        from api.v1.router import router
        routes = {r.path: r.methods for r in router.routes if hasattr(r, "methods")}
        detail = {"router_type": str(type(router)), "route_count": len(router.routes),
                  "route_types": [str(type(r)) for r in router.routes[:5]],
                  "route_paths": [getattr(r, "path", None) for r in router.routes[:10]]}
        self.assertIn("/xetra/inventory", routes, repr(detail))
        self.assertIn("GET", routes["/xetra/inventory"])
        self.assertIn("POST", routes["/xetra/quote-check"])
