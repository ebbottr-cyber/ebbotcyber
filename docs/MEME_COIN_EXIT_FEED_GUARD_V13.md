# EBBot Meme Coin — V13 offline full-position SELL quote & feed guard

**Status:** isolated, manual, OFFLINE scenario preflight. This is **not**
autonomous paper trading, not a connected live quote feed, and NEVER
a real-money trading feature. Solana Hype and Robinhood Chain are untouched.
All preceding PRs are still stacked drafts.

## What was added

- `src/services/meme_coin_exit_feed_guard.py`: deterministic preflight of
  **full-position Jupiter V2 walletless SELL quote snapshots** against the
  existing isolated New Launch / Momentum V11 paper positions.
- The preflight recomputes current simulated holdings from earlier accepted
  steps. Before each proposed BUY scenario, it requires a quote covering
  100% of each *existing* paper position **plus the projected new token
  quantity**. Separate strategies holding the same token require separate
  quotes for their independent quantities.
- Requires a strict quote capture identity: exactly corresponding strategy,
  mint, SELL direction, raw amount, USDC output mint, canonical integrity
  hash, transaction-free quote fields, and a local capture time no more than
  **3 seconds** before the scenario attempt.
- Requires a synthetic feed health heartbeat no more than **5 seconds**
  old, with flags for Jupiter / DEX Screener / Solana RPC.
- Applies a **hypothetical** 1% adverse exit move and $0.01 extra network
  fee against quoted USDC proceeds. Rejects an assumed full exit worth
  less than $1 net. This is a scenario cost assumption, not a quote-derived
  actual fee or a guarantee of route liquidity.
- Rejects missing/invalid/stale/wrong-size quote, missing or stale
  heartbeat, connectivity loss, bad decimals and corrupted identity.
  The blocked BUY is recorded in the V11 ledger with an explicit
  `exit_quote_<reason>` audit. An outage does not automatically force a
  SELL; it prevents prospective fixture BUYs and can be re-evaluated with a
  fresh test heartbeat.
- V11 `replay_marked_guarded` now accepts *blocked-only*
  `exit_quote_gate={status:"blocked",reason:"..."}` metadata on an
  existing event step. A caller cannot directly inject `approved`
  metadata. The V11 local SQLite replay and crash recovery preserve such
  blocked steps deterministically.
- Read-only `GET /api/v1/meme-coins/paper/exit-guard-readiness`
  reports this offline harness as **not running**. The React panel displays
  its capability and limits without market P&L or buy/sell actions.

## Data contracts and limitations

For a local test file, provide `steps` in the same V11 fixture format
and `exit_evidence` keyed by BUY event ID. Each evidence record contains:

```json
{
  "provider_status": {
    "source": "offline_fixture",
    "jupiter_online": true,
    "dexscreener_online": true,
    "solana_rpc_online": true,
    "observed_at_ms": 1000100
  },
  "token_decimals": {
    "<mint>": 6
  },
  "full_sell_quotes": {
    "new_launch:<mint>": {
      "...": "complete normalized snake_case Jupiter V9 SELL capture"
    }
  }
}
```

This is a **schema illustration**; not a valid executable sample without
complete, internally consistent captures. Operators can assemble actual
normalized V9 quote snapshots manually, but they MUST NOT infer authenticity
from the SHA-256 capture hash. The quoted full-size SELL output is matched to
the modeled paper quantity. This stage deliberately supports only mint
decimals **0 through 9** to avoid inventing precision beyond V11's nine-
decimal paper ledger. Valid Solana tokens with 10–18 decimals are marked
unsupported in this provisional simulation.

All `provider_status` flags and mint decimals in this OFFLINE tool
are **operator-supplied fixtures**, not verified connections or current
on-chain decimals. They are not propagated to any deployed trading engine.
The DEX Screener provider price's internal observation timestamp is still
unavailable (as identified in V12); comparing it with Jupiter does not
establish independent oracle agreement or actual market recency. The
Jupiter no-taker quote does **not** prove sell execution and may not
include actual priority fees, transfer taxes, MEV or market impact after
capture. Neither the 3s/5s windows nor full-size quote identity can
authenticate the quote's provider or deliver executable guarantees.

An accepted quote is **scenario coverage only**; output always includes
`quote_provider_signature_verified=false`,
`provider_market_observation_time_verified=false` and
`automatic_paper_execution_enabled=false`. No automated paper runner
or real trade is started.

## Local command

Save fixture data with exact top-level shape:

```json
{"steps": [], "exit_evidence": {}}
```

The empty example is deliberately a **no-trade** dry run.

```sh
python -m src.services.meme_coin_exit_feed_guard \
  --input /private/v13-test-data.json \
  --output /private/v13-report.json
```

The local output includes `gated_steps` (reproducible offline steps),
`gate_audit` and a V11 `replay_report`. No files are opened by the API,
no network calls occur in this CLI, and no private keys are accepted.

If using V11 SQLite recovery for further offline testing, an operator may
separately import `gated_steps`. Replaying the accepted quote scenario
later does **not** reauthenticate the original provider; to assert
historical provenance would require signed, independently verifiable
quote evidence and dedicated proof persistence. Do not treat a previous
green scenario as current permission to trade.

## Test commands

```sh
pytest -q tests/test_meme_coin_exit_feed_guard.py
pytest -q tests/test_meme_coin_strategy_panel.py tests/test_meme_coin_discovery.py tests/test_meme_coin_robinhood.py tests/test_meme_coin_solana_risk.py tests/test_meme_coin_solana_holders.py tests/test_meme_coin_solana_pool.py tests/test_meme_coin_solana_owner_groups.py tests/test_meme_coin_solana_orca.py tests/test_meme_coin_paper_replay.py tests/test_meme_coin_jupiter_quotes.py tests/test_meme_coin_quote_bridge.py tests/test_meme_coin_quote_journal.py tests/test_meme_coin_paper_guard.py tests/test_meme_coin_paper_mtm.py tests/test_meme_coin_paper_recovery.py tests/test_meme_coin_price_crosscheck.py tests/test_meme_coin_exit_feed_guard.py
cd apps/dsa-web
npm ci
npm test -- MemeCoinPage.test.tsx
```

## Remaining gates before autonomous paper tests

Real multi-worker provider-health verification with rate limiting, a
durable timestamped market data feed, **on-chain** mint precision verification
for each quote, full-position quote provenance, deterministic recovery and
reconciliation, mark-to-liquidation estimates, data gap fail-closed policy,
real loss calibration, rigorous out-of-sample tests and complete repository
CI must be independently reviewed. Live execution needs separate explicit
approval and security controls; **it is not enabled in V13**.
