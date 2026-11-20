"""No-network tests for the GitHub-only live Solana smoke command."""
import unittest
from unittest.mock import patch

from scripts.solana_meme_live_smoke import assess, main

MINT = "So11111111111111111111111111111111111111112"


def candidate(*, status="blocked", reasons=("security_unknown",)):
    return {
        "mint": MINT, "symbol": "TEST", "pool_id": "solana_pool",
        "source": "geckoterminal", "strategy": "new_coin_hunter",
        "score": 75, "status": status, "reasons": reasons,
    }


def payload(candidates=None, errors=None):
    return {
        "enabled": True, "trading_enabled": False,
        "candidates": [candidate()] if candidates is None else candidates,
        "errors": [] if errors is None else errors,
    }


class SolanaLiveSmokeTest(unittest.TestCase):
    def test_read_only_candidate_passes(self):
        result = assess(payload(), 2)
        self.assertEqual(result["result"], "passed")
        self.assertEqual(result["unique_mints"], 1)
        self.assertEqual(result["blocked_rows"], 1)
        self.assertFalse(result["trading_enabled"])

    def test_trade_gate_cannot_be_enabled(self):
        data = payload()
        data["trading_enabled"] = True
        with self.assertRaisesRegex(ValueError, "trading gate"):
            assess(data, 2)

    def test_missing_market_data_does_not_pass(self):
        self.assertEqual(assess(payload(candidates=[]), 2)["result"], "inconclusive")
        self.assertEqual(
            assess(payload(errors=[{"provider": "goplus", "message": "429"}]), 2)["result"],
            "degraded",
        )

    def test_incorrect_watch_status_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "Risk reasons"):
            assess(payload(candidates=[candidate(status="watch")]), 2)

    def test_invalid_token_or_too_many_mints_rejected(self):
        bad = candidate()
        bad["mint"] = "not-a-solana-address"
        with self.assertRaisesRegex(ValueError, "invalid Solana"):
            assess(payload(candidates=[bad]), 2)
        with self.assertRaisesRegex(ValueError, "token budget"):
            assess(payload(candidates=[candidate(), candidate(), candidate()]), 1)

    def test_only_explicit_run_calls_live_scanner(self):
        with patch("scripts.solana_meme_live_smoke.scan", return_value=payload()) as mock_scan:
            with patch("sys.argv", ["solana_meme_live_smoke", "--limit", "2"]):
                self.assertEqual(main(), 0)
            mock_scan.assert_called_once_with(live=True, limit=2)


if __name__ == "__main__":
    unittest.main()
