# EBBot — Synthetic Journal V1 (Phase 51)

**Offline research only.** Two completely separate in-memory journals:
`new_launch` and `momentum`. No real Solana tokens, live quotes, API endpoint,
wallet, executable paper order, persistence, scheduled job or real PnL.

`replay_synthetic_journal(starting_equity_usd=..., events=[...])` replays
**synthetic, closed round-trip** scenarios. Every event has an immutable ID,
ISO trading day, one strategy, hypothetical entry and exit prices, notional,
pool liquidity and snapshot age. Input is validated before computing output.

Safety mechanisms:
- Same event ID and identical scenario: ignored on replay (no double counting)
- Same ID but changed data: all journal output fails closed
- Strict chronological trading-day order, no extra keys or token identifiers
- One journal per strategy, reconciled hypothetical account-level PnL
- Strategy-level daily gross losses plus assumed stop exposure <= 2% of starting
  synthetic capital (no profit offsetting daily losses)
- Account-wide shared daily gross losses plus assumed stop exposure <= 3%
- Explicit manual kill switch rejects all hypothetical new records
- Next specified trading day gets a fresh daily budget; account equity tracks
  accumulated synthetic outcomes and constrains future hypothetical sizing
- Existing preview adds notional/equity, pool-liquidity, age, fees and slippage
  assumptions; unexpected input rejects the scenario
- Rejected events are listed in the audit but do not change hypothetical PnL

These are not real fills, not verified risk controls for execution, and not
financial results. The return object and any winnings are labeled synthetic.
No strategy dashboard metrics or trading state is changed.

Test: `python -m pytest -q tests/test_meme_coin_paper_preview.py tests/test_meme_coin_synthetic_journal.py`

Next required before a *true* paper broker: market-data snapshot provenance,
mint/authority/holder validations, crash-safe persistent append-only journal,
idempotent durable writes, market impact and failure modeling, authorization,
kill-switch persistence, out-of-sample testing, and independent deployment
review. Live trading remains a separate, explicitly approved later project.
