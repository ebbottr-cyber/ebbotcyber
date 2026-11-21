# EBBot Meme Coin V12 — Manual dual-source Solana price comparison

**Research-only preview**, stacked on V11. It adds NO automated paper fills,
portfolio mark provider, wallet, signed transaction, scheduler, order API or
real-money execution. Existing Solana Hype and Robinhood Chain are untouched.

## Data sources and interpretation

On a user click in EBBot → Meme Coin → New Launch or Momentum → select
candidate → **Satış fiyatlarını karşılaştır**, the read-only endpoint:

1. Requests a walletless **SELL** quote from Jupiter Swap V2 via the existing
   V9 `GET /swap/v2/order` code (input = selected SPL mint, output = USDC,
   no `taker` and no transaction submission).
2. Requests `GET /latest/dex/pairs/solana/<pool-address>` from DEX Screener
   and **requires exactly the requested pool address** on Solana, with the
   selected token as `baseToken.address`. A quote-token-side price is not
   silently substituted.
3. Queries the SPL mint with Solana `getAccountInfo` and parses
   *on-chain* token decimals from a classic SPL mint (Token-2022 and missing
   mint accounts are unsupported in this stage).
4. Computes implied Jupiter SELL proceeds **per token** as:
   `(outAmountRaw / 10^6) / (inAmountRaw / 10^mint_decimals)`.
   This is the quoted USD received after expected DEX route effects, not a
   zero-impact market reference.
5. Compares that implied sample sell price with the exact selected DEX
   Screener pool's reported `priceUsd`. Flags divergence **greater than
   10%**, reported liquidity below **$10,000**, a sample notional above
   **0.5%** of reported liquidity, or active mint/freeze authorities.

All untrusted amounts are parsed as finite decimal values. Exact mint/pool
identity, provider quote capture hash, V9 no-transaction flags and response
timestamps are validated. Missing, malformed, inconsistent or stale responses
fail closed as `unavailable`; no price is invented.

Source documentation:
- Jupiter Swap V2 GET order (omit taker): https://developers.jup.ag/docs/api-reference/swap/order
- DEX Screener pair API: https://docs.dexscreener.com/api/reference
- Solana SPL mint account: https://solana.com/docs/rpc/http/getaccountinfo

## Important limits (do not treat `comparison_only` as an approval)

- Jupiter and DEX Screener are **two API sources, NOT two necessarily
  independent price oracles**. They can reflect shared pools and upstream
  data. `source_independence_verified=false` always.
- DEX Screener's public pair response does **not** supply a trustworthy
  provider-internal *price observation time*. We record when our server
  received it, not when the market price was originally sampled.
  `dex_market_observation_timestamp_verified=false` always.
- The quote is for the explicitly requested **sample token amount**.
  A full-position sale may have very different price impact, fees,
  transfer restrictions, expired RFQ routes or inability to exit.
- Jupiter quote receipt and DEX price agreement do NOT verify token
  safety, real execution, withdrawal controls or liquidatability.
  `token_safety_verified=false`, `sell_fill_verified=false`,
  `mark_to_market_execution_verified=false` and `tradable=false`.
- This V12 preview intentionally **does not feed** V11's automatic/ offline
  MTM replay. Recorded comparisons cannot be called independently
  authenticated or executable portfolio marks. There is no online quote
  journal import and no automated paper trading.

## Configuration

Default is fail-closed and **no external requests**:

```env
MEME_COIN_DUAL_SOURCE_MARKS_ENABLED=false
MEME_COIN_JUPITER_QUOTES_ENABLED=false
JUPITER_API_KEY=
```

Only in a secured installation, explicitly enable both separate opt-ins:

```env
MEME_COIN_DUAL_SOURCE_MARKS_ENABLED=true
MEME_COIN_JUPITER_QUOTES_ENABLED=true
```

The V9 Jupiter helper enforces a process-local cooldown; V12 adds a short
2-second local result cache. Neither is a multi-worker rate limiter.
Enforce authentication and global rate limits before any public deployment.
Store any Jupiter API key on the server only.

## API (read-only)

```
GET /api/v1/meme-coins/solana/mark-crosscheck?strategy=new_launch&mint=<base58>&pool=<base58>&amount_raw=1000000
```

Status is `disabled`, `prerequisite_disabled`, `rate_limited`,
`unavailable`, or `screened`. Screened verdict is
`comparison_only` or `flagged`, **never** `safe` / `approved`.
No POST/PUT/transaction endpoints are introduced.

The React panel offers a separate manually requested comparison. It
shows both reported USD/token prices, difference, source caveat and risk
warnings. No performance claims or buy/sell controls are added.

## Validation

```sh
pytest -q tests/test_meme_coin_price_crosscheck.py
pytest -q tests/test_meme_coin_strategy_panel.py tests/test_meme_coin_discovery.py tests/test_meme_coin_robinhood.py tests/test_meme_coin_solana_risk.py tests/test_meme_coin_solana_holders.py tests/test_meme_coin_solana_pool.py tests/test_meme_coin_solana_owner_groups.py tests/test_meme_coin_solana_orca.py tests/test_meme_coin_paper_replay.py tests/test_meme_coin_jupiter_quotes.py tests/test_meme_coin_quote_bridge.py tests/test_meme_coin_quote_journal.py tests/test_meme_coin_paper_guard.py tests/test_meme_coin_paper_mtm.py tests/test_meme_coin_paper_recovery.py tests/test_meme_coin_price_crosscheck.py
cd apps/dsa-web
npm ci
npm test -- MemeCoinPage.test.tsx
```

## Before any unattended paper or live trading

Establish provider observation timestamps, stable authentication/rate
limits, independently validated prices and liquidity, full-position
actual-exit quotes, liquidation stress, fees and rejected transaction
statistics, crash recovery and whole-repo CI review. No real trading
without an additional explicit security review and authorization.
