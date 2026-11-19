"""Deterministic tests: Germany API must never trade or fetch on inventory GET."""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from unittest import TestCase
from unittest.mock import Mock, patch

from fastapi import HTTPException, Response
from api.v1.endpoints import xetra as api
from src.services.xetra_quote_guard import check_symbols

INVENTORY = {
    "SAP.DE": {"isin": "DE0007164600", "source_as_of_date": datetime.now(timezone.utc).date().isoformat()},
    "SIE.DE": {"isin": "DE0007236101", "source_as_of_date": datetime.now(timezone.utc).date().isoformat()},
}


class GermanyPanelApiTests(TestCase):
    def setUp(self):
        # Requests in separate tests must not share the global safety cooldown.
        api._quote_gate = api._ManualQuoteGate()

    def test_current_official_manifest_reports_1750_candidates_without_quotes(self):
        with (patch.object(api, "is_auth_enabled", return_value=False),
              patch.object(api, "fetch_yahoo_chart") as fetch):
            result = api.get_inventory(Response(), query="1ANT", limit=20)
        self.assertEqual(result["candidate_count"], 1750)
        self.assertEqual(result["source_as_of_date"], "2026-11-19")
        self.assertEqual(
            [(item["symbol"], item["isin"], item["price_symbol_verified"])
             for item in result["items"]],
            [("1ANT.DE", "US03703U1079", False)],
        )
        self.assertFalse(result["quotes_auto_loaded"])
        self.assertFalse(result["manual_quote_check_enabled"])
        self.assertFalse(result["paper_trading_enabled"])
        self.assertFalse(result["live_trading_enabled"])
        self.assertEqual(result["orders"], 0)
        fetch.assert_not_called()

    def test_future_snapshot_is_stale_in_inventory_and_blocks_provider(self):
        future = {
            code: {**row, "source_as_of_date": (
                datetime.now(timezone.utc).date() + timedelta(days=1)).isoformat()}
            for code, row in INVENTORY.items()
        }
        with (patch.object(api, "read_xetra_manifest", return_value=future),
              patch.object(api, "is_auth_enabled", return_value=True),
              patch.object(api.os, "getenv", return_value="true"),
              patch.object(api, "fetch_yahoo_chart") as fetch):
            listing = api.get_inventory(Response(), query="", limit=20)
            self.assertEqual(listing["snapshot_age_days"], -1)
            self.assertTrue(listing["source_stale"])
            self.assertFalse(listing["manual_quote_check_enabled"])
            with self.assertRaises(HTTPException) as exc:
                api.check_xetra_quotes(
                    api.XetraQuoteCheckRequest(symbols=["SAP.DE"]), Response())
            self.assertEqual(exc.exception.status_code, 409)
            fetch.assert_not_called()

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

    def test_official_isin_can_find_a_candidate_without_fetching_price(self):
        with (patch.object(api, "read_xetra_manifest", return_value=INVENTORY),
              patch.object(api, "fetch_yahoo_chart") as fetch,
              patch.object(api, "is_auth_enabled", return_value=False)):
            result = api.get_inventory(
                Response(), query="DE0007236101", limit=30,
            )
        self.assertEqual(
            [item["symbol"] for item in result["items"]],
            ["SIE.DE"],
        )
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
        # FastAPI 0.137+ stores nested routers lazily; app routing
        # must be tested via HTTP, not by scanning router.routes.
        from fastapi import FastAPI
        from fastapi.testclient import TestClient
        from api.v1.router import router

        app = FastAPI()
        app.include_router(router, prefix="/api/v1")
        with (patch.object(api, "read_xetra_manifest", return_value=INVENTORY),
              patch.object(api, "is_auth_enabled", return_value=False)):
            response = TestClient(app).get("/api/v1/xetra/inventory?query=SAP")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["items"][0]["symbol"], "SAP.DE")
        self.assertFalse(response.json()["manual_quote_check_enabled"])

    def test_stale_inventory_disables_quote_endpoint_before_network(self):
        stale = {
            code: {**row, "source_as_of_date": (date.today() - timedelta(days=9)).isoformat()}
            for code, row in INVENTORY.items()
        }
        with (patch.object(api, "read_xetra_manifest", return_value=stale),
              patch.object(api, "is_auth_enabled", return_value=True),
              patch.object(api.os, "getenv", return_value="true"),
              patch.object(api, "fetch_yahoo_chart") as fetch):
            listing = api.get_inventory(Response(), query="", limit=20)
            self.assertTrue(listing["source_stale"])
            self.assertFalse(listing["manual_quote_check_enabled"])
            with self.assertRaises(HTTPException) as exc:
                api.check_xetra_quotes(
                    api.XetraQuoteCheckRequest(symbols=["SAP.DE"]), Response())
            self.assertEqual(exc.exception.status_code, 409)
            self.assertEqual(exc.exception.detail, "xetra_snapshot_stale")
            fetch.assert_not_called()

    def test_mixed_source_dates_are_blocked_even_if_some_current(self):
        mixed = {
            "SAP.DE": {**INVENTORY["SAP.DE"], "source_as_of_date": date.today().isoformat()},
            "SIE.DE": {**INVENTORY["SIE.DE"], "source_as_of_date": (
                date.today() - timedelta(days=1)).isoformat()},
        }
        with (patch.object(api, "read_xetra_manifest", return_value=mixed),
              patch.object(api, "is_auth_enabled", return_value=True),
              patch.object(api.os, "getenv", return_value="true"),
              patch.object(api, "fetch_yahoo_chart") as fetch):
            with self.assertRaises(HTTPException) as exc:
                api.get_inventory(Response(), query="", limit=30)
            self.assertEqual(exc.exception.status_code, 503)
            with self.assertRaises(HTTPException) as exc:
                api.check_xetra_quotes(
                    api.XetraQuoteCheckRequest(symbols=["SAP.DE"]), Response())
            self.assertEqual(exc.exception.status_code, 503)
            fetch.assert_not_called()

    def test_manual_cooldown_prevents_repeat_provider_requests(self):
        now = datetime.now(timezone.utc)
        valid = {
            "chart": {"error": None, "result": [{"meta": {
                "symbol": "SAP.DE", "currency": "EUR", "fullExchangeName": "XETRA",
                "exchangeTimezoneName": "Europe/Berlin", "instrumentType": "EQUITY",
                "regularMarketPrice": 190.0,
                "regularMarketTime": int((now - timedelta(hours=2)).timestamp()),
            }}]},
        }
        with (patch.object(api, "is_auth_enabled", return_value=True),
              patch.object(api.os, "getenv", return_value="true"),
              patch.object(api, "read_xetra_manifest", return_value=INVENTORY),
              patch.object(api, "fetch_yahoo_chart", return_value=valid) as fetch):
            req = api.XetraQuoteCheckRequest(symbols=["SAP.DE"])
            first = api.check_xetra_quotes(req, Response())
            self.assertEqual(first["status"], "QUOTE_METADATA_SAMPLE_ONLY")
            with self.assertRaises(HTTPException) as exc:
                api.check_xetra_quotes(req, Response())
            self.assertEqual(exc.exception.status_code, 429)
            self.assertEqual(exc.exception.headers["Retry-After"], "30")
            self.assertEqual(fetch.call_count, 1)

    def test_manual_gate_rejects_concurrent_requests(self):
        gate = api._ManualQuoteGate()
        with gate.request_slot():
            with self.assertRaises(HTTPException) as exc:
                with gate.request_slot():
                    pass
            self.assertEqual(exc.exception.status_code, 429)
