# EBBot: Solana Meme Radar (isolated preview)

This module is an **opt-in read-only preview**. It is not mounted in the main API, scheduled jobs, UI, order router, wallet, or notification pipeline. It deliberately cannot execute transactions. Existing stock strategies remain unchanged.

## What is implemented

- **GeckoTerminal**: `GET /api/v2/networks/solana/new_pools?page=1` discovers **recently listed pools** on Solana. A new pool is *not proof* that a token was minted just then.
- **DEX Screener**: `GET /token-profiles/latest/v1`, then `GET /tokens/v1/solana/{mints}` reads the latest **token profile updates** and their current pairs. A new profile is *not* a newly minted token. The module does **not** label these as new mints.
- **GoPlus Solana Token Security (beta)**: `GET /api/v1/solana/token_security?contract_addresses={mint}`. Missing response or missing risk fields => **blocked**. Risks include mint authority, freeze authority, closable program, nontransferable token, transfer hook, and malicious creator. These are preliminary safety checks, **not a comprehensive audit**. No bearer token is stored or hardcoded.

## Two independent watchlist rules

1. `new_coin_hunter`: Gecko new pool feed; pool age 0-4 hours; price > 0, liquidity >= $10k, 24h volume >= $2k, >= 5 buys in 5 minutes, buys > sells; and complete negative risk flags.
2. `momentum_watcher`: price rise in 5 minutes of 2%-20%, 24h volume >= $50k, >= 20 buys in 5 minutes, buys > sells; same liquidity/price and safety checks.

Scores are **0-100 points** as a simple ranking signal. `status=blocked` overrides the numerical score. These thresholds are *unvalidated starting heuristics*, not trading advice or a proven strategy. Security flags must be verified against live responses before use in any paper execution engine. API-derived timestamps are not guarantees of true mint/launch time. Inadequate data or stale observations block the watchlist.

## Run manually

From repository root:

```bash
python -m scripts.scan_solana_meme                # safe default: no network
python -m scripts.scan_solana_meme --live --limit 5 # API calls, read-only, JSON output
python -m pytest tests/test_solana_meme_radar.py
```

The `--live` command makes one Gecko request, up to two DEX requests, and up to `--limit` GoPlus requests. Its default limit is 8; request budget is bounded, but there is no background scheduler/caching yet. Do not run at sub-minute intervals. Network calls have an 8-second timeout and a 2MB body limit. Upstream rate limits / schema may change. Provider failures are returned as `errors`, not silently treated as safe.

## Not yet implemented

- Exchange-level trading or **paper fills** (cannot claim simulated PnL without execution/fee/slippage model).
- Bitquery/Pump.fun stream for true mint creation, Birdeye/Helius high-frequency wallet events, historical OHLCV, cross-provider price reconciliation, persistent store, rate-limit-aware scheduler, or UI integration.
- Authenticated GoPlus quotas and false-positive/false-negative validation on token-2022 extensions.

**Recommended next milestone:** wire results into an *explicitly gated* read-only API endpoint, then develop offline replay with gas/slippage and realistic fees before any live-capable action. Do not turn on real trading.

### API documentation

- https://docs.dexscreener.com/api/reference
- https://api.geckoterminal.com/docs/index.html
- https://docs.gopluslabs.io/reference/solanatokensecurityusingget
- https://docs.gopluslabs.io/reference/response-detail-1
