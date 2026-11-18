# EBBot Meme Coin — Synthetic Paper Preview V1 (Phase 50)

## Status: OFFLINE DEMONSTRATION ONLY

`src/services/meme_coin_paper_preview.py` calculates a hypothetical round-trip
using **synthetic, caller-supplied prices**, with explicit fee and slippage
assumptions. It has no I/O, APIs, wallet, orders, persistence, scheduler,
token verification, discovery connection, or executable paper ledger.

Existing dashboard status stays `paper_planned`; strategy
`paper_trading_enabled=false` and `live_trading_enabled=false`. A positive
synthetic return is **not** historical performance or an investment signal.

## Conservative demo policy (not production-validated)

| Guard | Synthetic scenario ceiling |
| --- | --- |
| Single position | USD 25 |
| One position / equity | 2% |
| Pool liquidity | >= USD 50,000 |
| Requested notional / pool | <= 0.05% |
| Synthetic snapshot age | <= 60 seconds |
| Daily realized loss + hypothetical 10% stop exposure | <= 3% of synthetic equity |
| Fee assumption | 30 bps each side |
| Slippage assumption | 100 bps each side |

All limits are deliberately restrictive research assumptions, **not proof** of
real-world fillability, stop execution, liquidity or safe token authorities.

## Test locally

```bash
python -m pytest -q tests/test_meme_coin_paper_preview.py
```

This test is also included in the read-only integration CI. No live price feed
is loaded, no execution is simulated against a wallet, and no winning trades
are written to performance metrics.

## Prerequisites for an actual paper trading engine

1. Independent on-chain mint/freeze/holder and liquidity verification.
2. Durable, timestamped provider snapshots, staleness and data-provenance rules.
3. Separate New Launch / Momentum ledgers with idempotent event IDs and audit history.
4. Deterministic slippage, fees, transaction-failure and exit-path models.
5. Account-wide risk limits, daily loss circuit breaker, kill switch and authentication.
6. Out-of-sample/walk-forward evaluation and reconciled paper PnL.
7. Manual review before any paper engine activation; separate later approval
   required for live trading.

Do not treat this offline preview as permission to re-enable the archived
scheduled analysis workflow or merge/deploy PR #35.
