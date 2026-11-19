# EBBot Meme Coin V10 — Local quote journal and paper circuit breakers

**Offline development only.** Adds no trading, wallet, scheduler, database
mutation endpoint or automatic paper execution to EBBot. These changes are
stacked after V9; the Solana New Launch and Momentum strategies stay isolated.
Robinhood Chain and existing Solana Hype are not modified.

## 1. Manual local quote archive (SQLite)

Source: `src/services/meme_coin_quote_journal.py`.

The module imports the **complete snake_case JSON quote snapshots** already
exported by the V9 Jupiter walletless preview, *only from a local JSON file*:

```json
{"captures": [
  {"capture_id": "...", "source": "jupiter_swap_v2_order_quote_only",
   "strategy": "new_launch",
   "mint": "<actual validated Solana mint>",
   "...": "all fields from the unmodified V9 snapshot"}
]}
```

This is a contract illustration, not a runnable snapshot. Copy real, complete
quote snapshots and never add API secrets. Do not commit databases or
captured quote archives to Git.

Manual commands in a secure checkout:

```sh
python -m src.services.meme_coin_quote_journal \
  --database /secure/local/meme-quotes.sqlite \
  --input /secure/local/meme-quotes.json

python -m src.services.meme_coin_quote_journal \
  --database /secure/local/meme-quotes.sqlite --verify-only
```

- One SQLite journal table with independent `new_launch` and `momentum`
  hash-chained sequences, atomic batches, immutable-row triggers and
  idempotent retry by capture identity. Quotes are kept verbatim and
  validated against V9 canonical quote/hash before inserting.
- Import and verification fail closed on invalid content, unexpected fields,
  out-of-order timestamps and corrupted chain links. No wallet fields are
  permitted in the serialized payload.
- Hashes are **tamper-evident, not tamper-proof**. A privileged DB
  administrator could rewrite data and entire hash chains. They are **not
  provider signatures or proof of genuine market quotes**.
- Local SQLite durability assumes a stable writable disk, controlled access,
  backups and correct permissions. The backend does not open/read this
  database and cannot report any actual archive count in the EBBot UI.
- No network requests are performed during import or verification; only
  the earlier optional manual V9 quote preview can call Jupiter.
- A maximum 500-record import batch / 10,000 stored quotes per strategy is
  enforced as an initial offline operational guard. Not a high-frequency
  multi-worker storage design.

## 2. Risk-gated offline replay

Source: `src/services/meme_coin_paper_guard.py`.

Each V8 compatible event must have one operator-supplied *scenario* risk
snapshot, keyed by event ID:

```json
{
  "events": [
    {
      "id": "e1", "strategy": "new_launch",
      "mint": "11111111111111111111111111111111",
      "side": "buy", "source": "offline_fixture",
      "quote_observed_at_ms": 1000000, "attempted_at_ms": 1000200,
      "amount_in": "25", "expected_out": "100",
      "network_fee_usd": "0.01", "priority_fee_usd": "0.00",
      "modeled_adverse_slippage_bps": 100, "outcome": "success"
    }
  ],
  "risk_facts": {
    "e1": {
      "source": "offline_assumption",
      "liquidity_usd": "60000",
      "observed_at_ms": 1000100
    }
  }
}
```

**All numbers in this example are invented fixtures**, not market records.
The engine does not claim they come from Jupiter or on-chain pools. The price
and risk data must be supplied for both BUY and SELL fixtures; future sell
quotes are never invented. The V9 offline quote bridge may convert manually
captured quotes to V8 events before assembling this input.

Manual usage:

```sh
python -m src.services.meme_coin_paper_guard \
  --input /secure/local/offline-scenario.json \
  --output /secure/local/risk-report.json

# Hard stop test (blocks every modeled fill; does not send any orders):
python -m src.services.meme_coin_paper_guard \
  --input /secure/local/offline-scenario.json \
  --output /secure/local/stopped-report.json --emergency-stop
```

The optional `MEME_COIN_PAPER_EMERGENCY_STOP=true` environment flag has the
same effect for this **local CLI only**. The API is never connected to a
trading engine.

Scenario safeguards currently evaluated *before* V8 simulated fills:

- Never use risk observations later than a modeled attempt; reject risk
  observations older than **30 seconds**.
- Reject scenarios with *reported* liquidity below **$10,000**.
- Reject new BUY scenarios representing over **0.5%** of the modeled USD
  liquidity, separately from V8's $100 order cap and $200 mint exposure cap.
- Daily **book-equity-at-cost** loss of $50 per strategy blocks further new
  BUY scenarios for that UTC day; a later day can resume this per-strategy
  circuit (unless another stop has fired).
- Global aggregate book loss of $100 across both ledgers is a sticky
  circuit within this replay and blocks new BUY scenarios for both.
- Three consecutive modeled network/chain failures latch the affected
  strategy's new BUY scenarios for the remainder of the replay.
- A hard emergency stop blocks all actions, including SELL scenarios.
- On soft loss/failure circuit trips, SELL scenarios can still be processed
  only with fresh valid quotes and sufficient reported liquidity; this is
  a **hypothetical exit**, not evidence it could be executed in the market.

**Important accounting limitation:** book equity at cost is cash plus
unliquidated position **cost basis**; unrealized market losses are NOT
calculated. Therefore the above $50/$100 limits are *not* full mark-to-market
drawdown limits. They are preliminary scenario guardrails. Live market
liquidity, whale activity, safety audit results, actual fill probability,
priority gas, taxes, MEV and evolving token prices are not authenticated by
these scenarios. Before any autonomous paper test, connect reliable
timestamped market marks and risk facts and thoroughly test crash recovery.

## 3. EBBot panel / API

Read-only `GET /api/v1/meme-coins/paper/risk-readiness` reports two Solana
strategy ledgers with offline risk modules available, but
`paper_engine_running=false`, `journal_online=false`,
`risk_facts_verified_from_market=false` and
`live_trading_enabled=false`. There are NO quote archive upload/write
routes, no execution endpoints and no fabricated PnL or quote counts.

## Verification

```sh
pytest -q tests/test_meme_coin_quote_journal.py tests/test_meme_coin_paper_guard.py
pytest -q tests/test_meme_coin_strategy_panel.py tests/test_meme_coin_discovery.py tests/test_meme_coin_robinhood.py tests/test_meme_coin_solana_risk.py tests/test_meme_coin_solana_holders.py tests/test_meme_coin_solana_pool.py tests/test_meme_coin_solana_owner_groups.py tests/test_meme_coin_solana_orca.py tests/test_meme_coin_paper_replay.py tests/test_meme_coin_jupiter_quotes.py tests/test_meme_coin_quote_bridge.py tests/test_meme_coin_quote_journal.py tests/test_meme_coin_paper_guard.py
cd apps/dsa-web
npm ci
npm test -- MemeCoinPage.test.tsx
```

## Next phase

Production paper simulation would need timestamped quote and source
authentication, distributed persistence, historical market prices/mark-to-market
loss limits, realistic order fill calibration, end-to-end recovery tests and
an authenticated operator kill switch. No live trading before a separate
formal security review and explicit authorization.
