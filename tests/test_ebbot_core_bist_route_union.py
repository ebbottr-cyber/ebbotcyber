"""PR205 regression: three read-only data routes coexist and private reports stay private.

Real BIST/coverage ASGI middleware tests remain in separate test modules.
This checks the only manually merged API file without network or scheduler use.
"""
from __future__ import annotations

import unittest
from unittest.mock import patch

from fastapi import Response

from api.v1.endpoints import data


class CoreBistReadOnlyRoutesTests(unittest.TestCase):
    def test_combined_router_contains_each_get_only_route_once(self):
        for path in ("/tr-market-overview", "/equity-coverage", "/bist-identity"):
            routes = [route for route in data.router.routes if route.path == path]
            self.assertEqual(len(routes), 1, path)
            self.assertEqual(routes[0].methods, {"GET"}, path)
        self.assertNotEqual(
            data.get_turkish_market_overview,
            data.get_bist_identity_summary,
        )

    def test_both_private_reports_never_open_when_admin_auth_disabled(self):
        with patch("api.v1.endpoints.data.is_auth_enabled", return_value=False):
            with patch(
                "src.services.equity_data_coverage_reader.read_equity_coverage_report",
                side_effect=AssertionError("coverage private file read under auth-off"),
            ), patch(
                "src.services.bist_identity_report_reader.read_bist_identity_summary",
                side_effect=AssertionError("BIST private file read under auth-off"),
            ):
                equity_response = Response()
                bist_response = Response()
                equity = data.get_equity_coverage(equity_response)
                bist = data.get_bist_identity_summary(bist_response)
        self.assertEqual(equity_response.headers["Cache-Control"], "no-store")
        self.assertEqual(bist_response.headers["Cache-Control"], "no-store")
        self.assertEqual(equity["status"], "unavailable")
        self.assertEqual(bist["status"], "unavailable")
        self.assertEqual(equity["reason"], "administrator_auth_required")
        self.assertEqual(bist["reason"], "administrator_auth_required")
        self.assertIsNone(equity["total_candidate_instruments"])
        self.assertIsNone(bist["counts"])

    def test_turkish_market_summary_survived_api_union_without_network(self):
        synthetic = {"as_of": "2026-11-21T00:00:00+03:00",
                     "cadence": "delayed_daily", "items": []}
        with patch("api.v1.endpoints.data.get_tr_market_overview",
                   return_value=synthetic) as producer:
            report = data.get_turkish_market_overview()
        producer.assert_called_once_with()
        self.assertEqual(report.cadence, "delayed_daily")
        self.assertEqual(report.items, [])
        self.assertEqual(report.as_of, synthetic["as_of"])


if __name__ == "__main__":
    unittest.main()
