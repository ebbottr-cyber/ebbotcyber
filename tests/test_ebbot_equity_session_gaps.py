"""Deterministic offline four-market session and ticker identity gap tests."""
from __future__ import annotations

from contextlib import redirect_stdout
from datetime import date
import io
import json
from pathlib import Path
import tempfile
import unittest

from scripts.audit_ebbot_market_data_coverage import AuditInputError
from scripts.audit_ebbot_equity_session_gaps import (
    compact, parser, run, session_gap_audit,
)

DAY = date(2026, 11, 21)


class EquitySessionGapTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.index = self.root / "index.json"
        self.index.write_text("[]", encoding="utf-8")

    def write(self, name: str, content: str) -> Path:
        path = self.root / name
        path.write_text(content, encoding="utf-8")
        return path

    def universe(self) -> Path:
        return self.write(
            "universe.csv",
            "market,symbol,source,kind,source_as_of_date\n"
            "tr,THYAO.IS,kap,stock,2026-11-20\n"
            "us,AAPL,nasdaq,stock,2026-11-20\n"
            "de,SAP.DE,xetra,stock,2026-11-20\n"
            "hk,0700.HK,hkex,stock,2026-11-20\n",
        )

    def calendars(self) -> Path:
        return self.write(
            "sessions.csv",
            "market,session,source,source_as_of_date\n"
            "tr,2026-11-19,market_schedule,2026-11-20\n"
            "tr,2026-11-20,market_schedule,2026-11-20\n"
            "us,2026-11-19,market_schedule,2026-11-20\n"
            "us,2026-11-20,market_schedule,2026-11-20\n"
            "de,2026-11-19,market_schedule,2026-11-20\n"
            "de,2026-11-20,market_schedule,2026-11-20\n"
            "hk,2026-11-19,market_schedule,2026-11-20\n"
            "hk,2026-11-20,market_schedule,2026-11-20\n",
        )

    def mappings(self) -> Path:
        return self.write(
            "mapping.csv",
            "market,symbol,provider,provider_symbol,source,source_as_of_date\n"
            "tr,THYAO.IS,licensed_data,THYAO,manual,2026-11-20\n"
            "us,AAPL,licensed_data,AAPL,manual,2026-11-20\n"
            "de,SAP.DE,licensed_data,SAP,manual,2026-11-20\n"
            "hk,0700.HK,licensed_data,700,manual,2026-11-20\n",
        )

    def bars(self, *, wrong: bool = False, non_session: bool = False) -> Path:
        day = "2026-11-18" if non_session else "2026-11-19"
        provider_symbol = "WRONG" if wrong else "AAPL"
        return self.write(
            "prices.csv",
            "market,symbol,session,open,high,low,close,volume,source,currency,provider,provider_symbol\n"
            f"us,AAPL,{day},100,102,99,101,10000,daily_feed,USD,licensed_data,{provider_symbol}\n",
        )

    def report(self, **kwargs):
        return session_gap_audit(
            index_path=self.index,
            stocks=[self.universe()],
            as_of=DAY,
            **kwargs,
        )

    def test_missing_calendar_is_unknown_not_zero_gaps(self):
        result = self.report()
        self.assertEqual(result["markets_without_calendar"], ["tr", "us", "de", "hk"])
        self.assertIsNone(result["markets"]["us"]["potential_missing_symbol_session_slots"])
        self.assertEqual(result["markets"]["us"]["symbols_without_ohlcv"], 1)
        self.assertFalse(result["licensed_ohlcv_verified"])
        self.assertEqual(result["network_requests"], 0)
        self.assertEqual(result["orders"], 0)

    def test_declared_calendar_reports_potential_not_verified_session_gaps(self):
        result = self.report(calendars=[self.calendars()], bars=[self.bars()])
        self.assertEqual(result["markets_without_calendar"], [])
        self.assertEqual(result["markets"]["us"]["declared_recent_market_sessions"], 2)
        self.assertEqual(result["markets"]["us"]["potential_missing_symbol_session_slots"], 1)
        self.assertEqual(result["markets"]["us"]["symbols_with_potential_session_gaps"], 1)
        self.assertEqual(result["markets"]["tr"]["potential_missing_symbol_session_slots"], 2)
        self.assertEqual(result["markets"]["us"]["symbols_with_any_ohlcv"], 1)
        self.assertEqual(result["status"], "BLOCKED_REQUIRES_INDEPENDENT_MARKET_DATA_VALIDATION")
        self.assertFalse(result["security_listing_and_trading_status_verified"])
        self.assertFalse(result["market_calendar_completeness_verified"])

    def test_all_declared_sessions_observed_still_not_trade_approved(self):
        extra = self.write(
            "both.csv",
            "market,symbol,session,open,high,low,close,volume,source,currency\n"
            "us,AAPL,2026-11-19,100,102,99,101,10000,daily_feed,USD\n"
            "us,AAPL,2026-11-20,100,102,99,101,10000,daily_feed,USD\n",
        )
        result = self.report(calendars=[self.calendars()], bars=[extra])
        self.assertEqual(result["markets"]["us"]["potential_missing_symbol_session_slots"], 0)
        self.assertEqual(result["markets"]["us"]["symbols_with_potential_session_gaps"], 0)
        self.assertFalse(result["provider_symbol_mapping_independently_verified"])
        self.assertFalse(result["licensed_ohlcv_verified"])
        self.assertFalse(result["live_trading_enabled"])

    def test_explicit_identity_matching_counted_as_declared_only(self):
        result = self.report(
            calendars=[self.calendars()],
            mappings=[self.mappings()],
            bars=[self.bars()],
        )
        self.assertEqual(result["markets"]["us"]["declared_provider_mappings"], 1)
        self.assertEqual(result["bar_identity_diagnostics"]["bar_rows_matching_declared_map"], 1)
        self.assertEqual(result["bar_identity_diagnostics"]["bar_rows_without_identity_evidence"], 0)
        self.assertFalse(result["provider_symbol_mapping_independently_verified"])

    def test_mismatched_raw_provider_symbol_fails_closed(self):
        with self.assertRaisesRegex(AuditInputError, "bar_provider_symbol_mapping_mismatch"):
            self.report(mappings=[self.mappings()], bars=[self.bars(wrong=True)])

    def test_bar_without_declared_provider_metadata_is_unresolved(self):
        old = self.write(
            "old.csv",
            "market,symbol,session,open,high,low,close,volume,source,currency\n"
            "us,AAPL,2026-11-19,100,102,99,101,123,daily_feed,USD\n",
        )
        result = self.report(mappings=[self.mappings()], bars=[old])
        self.assertEqual(result["bar_identity_diagnostics"]["bar_rows_without_identity_evidence"], 1)

    def test_calendar_never_fabricates_weekdays_or_holidays(self):
        c = self.write(
            "one.csv",
            "market,session,source,source_as_of_date\n"
            "us,2026-11-20,official,2026-11-20\n",
        )
        result = self.report(calendars=[c])
        self.assertEqual(result["markets"]["us"]["declared_recent_market_sessions"], 1)
        self.assertEqual(result["markets"]["us"]["potential_missing_symbol_session_slots"], 1)
        self.assertIsNone(result["markets"]["tr"]["potential_missing_symbol_session_slots"])

    def test_bar_inside_calendar_interval_on_non_session_fails_closed(self):
        result = self.report(calendars=[self.calendars()], bars=[self.bars(non_session=True)])
        self.assertEqual(result["markets"]["us"]["potential_missing_symbol_session_slots"], 2)
        # 18th is *outside* the declared 19-20 window. It is not automatically a holiday.
        self.assertEqual(result["markets"]["us"]["symbols_with_any_ohlcv"], 1)
        c = self.write(
            "gapped-calendar.csv",
            "market,session,source,source_as_of_date\n"
            "us,2026-11-18,source,2026-11-20\n"
            "us,2026-11-20,source,2026-11-20\n",
        )
        in_window = self.bars()
        with self.assertRaisesRegex(AuditInputError, "ohlcv_date_not_in_declared_calendar"):
            self.report(calendars=[c], bars=[in_window])

    def test_duplicate_calendar_session_is_rejected(self):
        original = self.calendars()
        with self.assertRaisesRegex(AuditInputError, "duplicate_calendar_session"):
            self.report(calendars=[original, original])

    def test_calendar_source_cannot_precede_session_or_future(self):
        c = self.write(
            "future-session.csv",
            "market,session,source,source_as_of_date\n"
            "us,2026-11-22,official,2026-11-22\n",
        )
        with self.assertRaisesRegex(AuditInputError, "future_calendar_evidence"):
            self.report(calendars=[c])
        c = self.write(
            "early-source.csv",
            "market,session,source,source_as_of_date\n"
            "us,2026-11-20,official,2026-11-19\n",
        )
        with self.assertRaisesRegex(AuditInputError, "calendar_source_predates_session"):
            self.report(calendars=[c])

    def test_mapping_for_unknown_equity_rejected(self):
        file = self.write(
            "badmap.csv",
            "market,symbol,provider,provider_symbol,source,source_as_of_date\n"
            "us,MSFT,feed,MSFT,manual,2026-11-20\n",
        )
        with self.assertRaisesRegex(AuditInputError, "mapping_symbol_missing_from_inventory"):
            self.report(mappings=[file])

    def test_mapping_provider_symbol_collision_rejected(self):
        stocks = self.universe()
        collision = self.write(
            "collision.csv",
            "market,symbol,source,kind,source_as_of_date\n"
            "us,MSFT,nasdaq,stock,2026-11-20\n",
        )
        mapping = self.write(
            "colliding-map.csv",
            "market,symbol,provider,provider_symbol,source,source_as_of_date\n"
            "us,AAPL,feed,X,manual,2026-11-20\n"
            "us,MSFT,feed,X,manual,2026-11-20\n",
        )
        with self.assertRaisesRegex(AuditInputError, "provider_symbol_collides_across_equities"):
            session_gap_audit(index_path=self.index, stocks=[stocks, collision],
                              mappings=[mapping], as_of=DAY)

    def test_invalid_ohlcv_prices_fail_as_in_prior_gate(self):
        bar = self.write(
            "nan.csv",
            "market,symbol,session,open,high,low,close,volume,source,currency\n"
            "us,AAPL,2026-11-19,nan,102,99,101,10000,daily_feed,USD\n",
        )
        with self.assertRaisesRegex(AuditInputError, "invalid_ohlcv_number"):
            self.report(bars=[bar])

    def test_no_top_n_cutoff_and_full_detail_json(self):
        index = self.index
        index.write_text(json.dumps([
            [f"U{i}", "", "", "", "", "", "US", "stock", True] for i in range(151)
        ]), encoding="utf-8")
        cal = self.write(
            "single.csv",
            "market,session,source,source_as_of_date\nus,2026-11-20,feed,2026-11-20\n",
        )
        result = session_gap_audit(index_path=index, calendars=[cal], as_of=DAY)
        self.assertEqual(result["markets"]["us"]["candidate_symbols"], 151)
        self.assertEqual(result["markets"]["us"]["potential_missing_symbol_session_slots"], 151)
        self.assertEqual(len(result["full_symbol_gap_details"]["us"]), 151)
        self.assertEqual(len(compact(result)["markets"]["us"]["sample_potential_gaps"]), 10)
        self.assertNotIn("full_symbol_gap_details", compact(result))
        target = self.root / "gap-detail.json"
        args = parser().parse_args([
            "--index", str(index), "--calendar", str(cal),
            "--as-of", DAY.isoformat(), "--report-json", str(target),
        ])
        with redirect_stdout(io.StringIO()) as stdout:
            self.assertEqual(run(args), 0)
        self.assertIn("BLOCKED_REQUIRES_INDEPENDENT", stdout.getvalue())
        saved = json.loads(target.read_text(encoding="utf-8"))
        self.assertEqual(len(saved["full_symbol_gap_details"]["us"]), 151)
        with redirect_stdout(io.StringIO()) as stdout:
            self.assertEqual(run(args), 1)
        self.assertIn("BLOCKED_INVALID_SESSION_DATA", stdout.getvalue())

    def test_stale_calendar_and_mapping_reported_not_approved(self):
        c = self.write(
            "stale.csv",
            "market,session,source,source_as_of_date\n"
            "us,2026-11-01,feed,2026-11-02\n",
        )
        m = self.write(
            "oldmapping.csv",
            "market,symbol,provider,provider_symbol,source,source_as_of_date\n"
            "us,AAPL,feed,AAPL,manual,2026-11-01\n",
        )
        result = self.report(calendars=[c], mappings=[m], max_age_days=7)
        self.assertEqual(result["calendar_diagnostics"]["calendar_row_diagnostics"]["us_stale_calendar_rows"], 1)
        self.assertEqual(result["mapping_diagnostics"]["stale_provider_mapping_rows"], 1)
        self.assertFalse(result["licensed_ohlcv_verified"])


if __name__ == "__main__":
    unittest.main()
