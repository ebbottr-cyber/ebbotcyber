# EBBot Meme Coin V11 — Offline mark-to-market & crash recovery

**Scope:** V11 is an OFFLINE, manually driven extension of the V10 risk
scenario runner. It does not place transactions, execute paper/live orders,
start a service, open wallet accounts or record verified market profits.
These files are not part of the existing real EBBot trading engine.
All features remain in stacked *draft* PRs until independently reviewed.

## 1. Mark open positions to a hypothetical sale price

`src/services/meme_coin_paper_mtm.py` accepts steps with:
- a V8-compatible offline quote `event` (buy/sell, raw scenario dates,
  fees, output, outcome);
- an `offline_assumption` `risk_fact` describing liquidity and observation
  time, as in V10; and
- `marks`, keyed by SPL token mint, each with `source=offline_assumption`,
  `bid_price_usd` as a nonnegative ASCII decimal string and
  `observed_at_ms`. These are entirely **operator-supplied test values**.

Illustrative fixture, **NOT a real quote or verified valuation**:

```json
{
  "steps": [{
    "event": {
      "id": "scenario-1",
      "strategy": "new_launch",
      "mint": "11111111111111111111111111111111",
      "side": "buy",
      "source": "offline_fixture",
      "quote_observed_at_ms": 1000000,
      "attempted_at_ms": 1000200,
      "amount_in": "25", "expected_out": "100",
      "network_fee_usd": "0.01",
      "priority_fee_usd": "0.00",
      "modeled_adverse_slippage_bps": 100,
      "outcome": "success"
    },
    "risk_fact": {
      "source": "offline_assumption",
      "liquidity_usd": "60000",
      "observed_at_ms": 1000100
    },
    "marks": {
      "11111111111111111111111111111111": {
        "source": "offline_assumption",
        "bid_price_usd": "0.25",
        "observed_at_ms": 1000100
      }
    }
  }]
}
```

For any step, `marks` must include fresh (up to 30 seconds old),
non-future prices for **all currently open positions of both strategies**
to calculate a complete combined equity. A new BUY also requires a fresh mark
for the token being bought. Missing/stale/future marks prevent new BUY
scenarios. A qualified SELL scenario may still be modeled if it reduces
exposure; the report shows `marked_equity_usd=null` if remaining holdings
are not fully marked.

- Each strategy's marked equity = cash + sum(held token quantity × assumed
  sell-side price), excluding actual route costs of liquidation and without
  asserting executable depth.
- Unrealized PnL = marked position value minus book cost basis.
- A $50 drop from the day's first valid marked equity observation latches
  new BUYs for that strategy until the UTC day changes.
- A $100 drawdown from the **highest observed combined marked equity**
  latches new BUYs for BOTH strategies for the rest of the replay.
- The V10 0.5%-of-liquidity buy cap, stale liquidity checks, network failure
  circuit and V8 transaction/fee guardrails remain enforced in V11.
- An explicit per-step `"emergency_stop": true` (optional; not shown in
  example) latches a hard stop for the rest of that replay, including SELLs.
  This stop is part of the history and survives restart.
- No unrealized losses can be computed if current marks are missing.
  Do **not** interpret a previous stored value as an up-to-date valuation.
- Drawdown logic is tested on historical fixtures only; it is NOT calibrated
  to actual token markets, portfolio liquidation, MEV, taxes, failed swaps or
  guaranteed sellability. Real-world thresholds require separate review.

## 2. Atomic SQLite checkpoint and replay recovery

`src/services/meme_coin_paper_recovery.py` is a **LOCAL file CLI**; no web
routes are allowed to invoke its writes. It appends steps into an immutable
hash-linked journal. A complete replay is recalculated and saved as a
checkpoint in the SAME SQLite transaction.

- Transactions use `BEGIN IMMEDIATE`, `WAL` mode and
  `synchronous=FULL`. A failure during append/replay rolls back both
  the step and the derived checkpoint.
- Each restart validates the entire input hash chain, schema, ordered IDs
  and timestamps, then recomputes the full deterministic marked state and
  checks the saved checkpoint exactly.
- An identical event ID + payload can be imported repeatedly without
  duplicating a fill; conflicting IDs fail. Initial cash is immutable for
  a persisted session.
- The emergency stop latch is reconstructed from earlier steps after restart
  and cannot be silently cleared by continuing the same session.
- A corrupt or missing checkpoint **fails closed**; it is never silently
  initialized from old balances.
- Hashes are **not signatures or proof of source authenticity**: privileged
  DB access could rewrite both history and checkpoint. The SQLite archive
  also needs controlled file permissions and periodic backups.
- 2,000 persisted steps max per offline DB, 100 per import batch. It is an
  offline validation design, not a production HFT event journal or
  multi-worker transactional service.

## 3. How to run locally when ready

Save the complete JSON fixture above to `/private/mtm-fixture.json` and run
in a secured checkout with Python CI dependencies installed:

```sh
python -m src.services.meme_coin_paper_recovery \
  --database /private/meme-mtm.sqlite \
  --input /private/mtm-fixture.json

python -m src.services.meme_coin_paper_recovery \
  --database /private/meme-mtm.sqlite --verify-only
```

The second command opens and verifies the same archive after a process
restart. Never commit quote archives, simulations or sensitive files to GitHub.
These commands do not connect to Jupiter or to a trading wallet.

## 4. Panel and API

Read-only `GET /api/v1/meme-coins/paper/mtm-readiness` shows two separate
Solana strategy rows marked NOT RUNNING, with `database_online=false`,
`paper_scheduler_running=false`, `live_trading_enabled=false` and
`mark_source=unverified_offline_assumptions`.

The UI intentionally shows **no** live mark, equity, return, archived count,
wallet or simulated trade initiation button. Robinhood Chain is separate.

## Tests

```sh
pytest -q tests/test_meme_coin_paper_mtm.py tests/test_meme_coin_paper_recovery.py
pytest -q tests/test_meme_coin_strategy_panel.py tests/test_meme_coin_discovery.py tests/test_meme_coin_robinhood.py tests/test_meme_coin_solana_risk.py tests/test_meme_coin_solana_holders.py tests/test_meme_coin_solana_pool.py tests/test_meme_coin_solana_owner_groups.py tests/test_meme_coin_solana_orca.py tests/test_meme_coin_paper_replay.py tests/test_meme_coin_jupiter_quotes.py tests/test_meme_coin_quote_bridge.py tests/test_meme_coin_quote_journal.py tests/test_meme_coin_paper_guard.py tests/test_meme_coin_paper_mtm.py tests/test_meme_coin_paper_recovery.py
cd apps/dsa-web
npm ci
npm test -- MemeCoinPage.test.tsx
```

## Necessary next checks before any automated paper runner

Provider-authenticated price mark and live *exit* quotes, independent
mark sources, Mark-to-liquidation slippage/fee buffers, max drawdown and
exposure calibrations, archive backups and permissions, concurrent-worker
reconciliation, a real authenticated kill switch and full-system CI.
Actual market fills and trade profitability remain unverified.
