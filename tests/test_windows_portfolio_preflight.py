# -*- coding: utf-8 -*-
"""Offline tests: Windows preflight never needs .env, DB, trading or remote hosts."""

from __future__ import annotations

import io
import json
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch
from urllib import error

from scripts import ebbot_windows_portfolio_preflight as probe


class WindowsPortfolioPreflightTest(unittest.TestCase):
    def test_local_origin_requires_explicit_safe_host_port(self):
        for origin in (
            "https://127.0.0.1:8000",
            "http://8.8.8.8:8000",
            "http://192.168.1.10:8000",
            "http://example.com:8000",
            "http://127.0.0.1:7999",
            "http://127.0.0.1:8101",
            "http://127.0.0.1:8000/api/health",
            "http://127.0.0.1:8000/?a=1",
            "http://user:secret@127.0.0.1:8000",
            "file:///C:/secrets/.env",
            "http://127.0.0.1",
            "http://127.0.0.1:8000/#token",
        ):
            with self.subTest(origin=origin), self.assertRaises(ValueError):
                probe.safe_origin(origin)

    def test_local_origin_accepts_only_loopback(self):
        self.assertEqual(probe.safe_origin("http://127.0.0.1:8000"), "http://127.0.0.1:8000")
        self.assertEqual(probe.safe_origin("http://localhost:8100/"), "http://localhost:8100")
        self.assertEqual(probe.safe_origin("http://[::1]:8001"), "http://[::1]:8001")

    def test_missing_source_files_fail_closed_without_reading_dotenv(self):
        with tempfile.TemporaryDirectory() as temp:
            with patch.object(probe, "_node_version", return_value=(22, 2, 0)):
                results = probe.check_sources(Path(temp))
            self.assertEqual(results[0].status, "blocked")
            self.assertIn("portfolio", results[0].detail.lower())
            self.assertNotIn(".env", results[0].detail)

    def test_source_files_present_and_old_node_is_blocked(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            for path in probe.REQUIRED_SOURCE_FILES:
                item = root / path
                item.parent.mkdir(parents=True, exist_ok=True)
                item.write_text("unit-test", encoding="utf-8")
            with patch.object(probe, "_node_version", return_value=(18, 18, 0)):
                results = probe.check_sources(root)
            self.assertEqual([entry.status for entry in results], ["ok", "ok", "blocked"])
            with patch.object(probe, "_node_version", return_value=(22, 12, 0)):
                results = probe.check_sources(root)
            self.assertEqual([entry.status for entry in results], ["ok", "ok", "ok"])

    def test_desktop_bundle_requires_real_assets_and_blocks_blank_ui(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self.assertEqual(probe.check_frontend_bundle(root)[0].status, "blocked")
            static = root / "static"
            static.mkdir()
            (static / "index.html").write_text('<html><div id="root"></div></html>', encoding="utf-8")
            self.assertEqual(probe.check_frontend_bundle(root)[0].status, "blocked")
            (static / "index.html").write_text(
                '<html><script src="/assets/app.js"></script></html>', encoding="utf-8",
            )
            self.assertEqual(probe.check_frontend_bundle(root)[0].status, "blocked")
            (static / "assets").mkdir()
            (static / "assets" / "app.js").write_text("console.log('hello')", encoding="utf-8")
            self.assertEqual(probe.check_frontend_bundle(root)[0].status, "ok")

    def test_local_health_and_frontend_are_get_only_and_are_verified(self):
        calls = []

        def fetch(_origin, path):
            calls.append(path)
            if path == "/api/health":
                return 200, "application/json", b'{"status":"ok","timestamp":"2026-11-20"}'
            if path == "/":
                return 200, "text/html", b'<html><div id="root"></div><script src="/assets/app.js"></script></html>'
            raise AssertionError("Unexpected request")

        checks = probe.probe_local("http://127.0.0.1:8000", fetch=fetch)
        self.assertEqual([x.status for x in checks], ["ok", "ok"])
        self.assertEqual(calls, ["/api/health", "/"])

    def test_health_200_without_json_ok_is_not_a_pass(self):
        def fetch(_origin, path):
            if path == "/api/health":
                return 200, "text/html", b"OK"
            return 200, "text/html", b'<html><div id="root"></div><script src="/assets/app.js"></script></html>'
        checks = probe.probe_local("http://127.0.0.1:8000", fetch=fetch)
        self.assertEqual(checks[0].status, "blocked")

    def test_frontend_not_built_is_blocked_even_if_backend_healthy(self):
        def fetch(_origin, path):
            if path == "/api/health":
                return 200, "application/json", b'{"status":"ok"}'
            return 200, "text/html", b"<h1>Frontend Not Built</h1>"
        self.assertEqual([c.status for c in probe.probe_local("http://localhost:8000", fetch=fetch)],
                         ["ok", "blocked"])

    def test_display_fx_six_fresh_pairs_can_be_observed_without_ledger_write(self):
        now = datetime(2026, 11, 20, 14, 0, tzinfo=timezone.utc)
        pair_time = (now - timedelta(minutes=5)).isoformat()
        codes = ("usd", "cny", "hkd", "jpy", "krw", "twd")
        payload = {
            "pair_status": {code: "current" for code in codes},
            "pair_as_of": {code: pair_time for code in codes},
            **{f"{code}_try": 1.3 for code in codes},
        }
        calls = []

        def fetch(_origin, path):
            calls.append(path)
            if path == "/api/health":
                return 200, "application/json", b'{"status":"ok"}'
            if path == "/":
                return 200, "text/html", b'<div id="root"></div><script src="/assets/a.js"></script>'
            return 200, "application/json", json.dumps(payload).encode()

        checks = probe.probe_local("http://localhost:8000", fetch=fetch, check_display_fx=True, now=now)
        self.assertEqual([c.status for c in checks], ["ok", "ok", "ok"])
        self.assertEqual(calls, ["/api/health", "/", "/api/v1/portfolio/fx/display-rates"])

    def test_partial_closed_market_data_is_not_reported_as_ready(self):
        now = datetime(2026, 11, 20, tzinfo=timezone.utc)
        def fetch(_origin, path):
            if path == "/api/health":
                return 200, "application/json", b'{"status":"ok"}'
            if path == "/":
                return 200, "text/html", b'<div id="root"></div><script src="/assets/a.js"></script>'
            return 200, "application/json", json.dumps({
                "pair_status": {c: "unavailable" for c in ("usd", "cny", "hkd", "jpy", "krw", "twd")},
                "pair_as_of": {},
            }).encode()
        checks = probe.probe_local("http://localhost:8000", fetch=fetch, check_display_fx=True, now=now)
        self.assertEqual(checks[-1].status, "warning")
        self.assertEqual(probe.summary(checks), "NOT_VERIFIED")

    def test_fake_current_outdated_quote_is_not_accepted(self):
        now = datetime(2026, 11, 20, 10, tzinfo=timezone.utc)
        stale_time = (now - timedelta(days=1)).isoformat()
        def fetch(_origin, path):
            if path == "/api/health":
                return 200, "application/json", b'{"status":"ok"}'
            if path == "/":
                return 200, "text/html", b'<div id="root"></div><script src="/assets/a.js"></script>'
            return 200, "application/json", json.dumps({
                "pair_status": {"usd": "current"},
                "pair_as_of": {"usd": stale_time},
                "usd_try": 42,
            }).encode()
        checks = probe.probe_local("http://localhost:8000", fetch=fetch, check_display_fx=True, now=now)
        self.assertEqual(checks[-1].status, "warning")

    def test_summary_does_not_authorize_trading(self):
        self.assertEqual(probe.summary([probe.Check("x", "ok", "clean")]), "PASSED_READ_ONLY")
        self.assertEqual(probe.summary([probe.Check("x", "blocked", "invalid")]), "BLOCKED")
        self.assertEqual(probe.summary([probe.Check("x", "warning", "partial")]), "NOT_VERIFIED")

    def test_cli_explicit_origin_required_for_desktop_mode(self):
        with self.assertRaises(SystemExit) as captured:
            probe.main(["--mode", "desktop"])
        self.assertEqual(captured.exception.code, 2)

    def test_windows_cp1252_console_still_emits_utf8_turkish_json(self):
        output = io.BytesIO()
        cp1252_stdout = io.TextIOWrapper(output, encoding="cp1252", write_through=True)
        with patch.object(probe.sys, "stdout", cp1252_stdout), patch.object(
            probe, "check_sources", return_value=[
                probe.Check("source_files", "ok", "Türkçe doğrulandı"),
            ],
        ):
            rc = probe.main(["--mode", "source", "--json"])
            cp1252_stdout.flush()
        self.assertEqual(rc, 0)
        self.assertEqual(json.loads(output.getvalue().decode("utf-8"))["checks"][0]["detail"], "Türkçe doğrulandı")

    def test_redirect_to_external_site_is_never_followed(self):
        # No listener or actual network required: fake an HTTP redirect opener.
        class RedirectStub:
            def __init__(self):
                self.calls = []
            def open(self, req, timeout):
                self.calls.append((req.get_method(), req.full_url))
                raise error.HTTPError(req.full_url, 302, "redirect forbidden", {}, None)
        stub = RedirectStub()
        with patch.object(probe.request, "build_opener", return_value=stub):
            with self.assertRaises(error.HTTPError):
                probe.local_get("http://127.0.0.1:8000", "/api/health")
        self.assertEqual(stub.calls, [("GET", "http://127.0.0.1:8000/api/health")])


if __name__ == "__main__":
    unittest.main()
