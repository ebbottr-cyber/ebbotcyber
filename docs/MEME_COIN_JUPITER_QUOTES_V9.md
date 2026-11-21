# EBBot Meme Coin V9 — Jupiter Swap V2 quote-only preview + offline bridge

This is a stacked draft PR on V8. It adds **manual, read-only** Solana
swap quote previews from Jupiter Swap V2 and a pure offline converter from
captured quotes into independent deterministic paper replay ledgers.

**No live trading, no real/paper order placement, no wallet, no scheduler,
no automatic PnL and no historical backtest accuracy claims.**

## Why Swap V2

Current official Jupiter API uses `GET https://api.jup.ag/swap/v2/order`
**without a `taker` parameter** for walletless quotes. Swap V1 is superseded
and not newly integrated. The implementation never calls Jupiter's
`/execute`, `/build`, `/submit` or wallet paths and will reject any response
that includes a non-null `transaction` payload.

Official:
- https://developers.jup.ag/docs/swap
- https://developers.jup.ag/docs/api-reference/swap/order

## Enable (off by default)

```env
MEME_COIN_JUPITER_QUOTES_ENABLED=false
# optional, server-side only; NEVER commit or expose a real key
JUPITER_API_KEY=
```

Only on a **secured authenticated installation**, explicitly opt in:

```env
MEME_COIN_JUPITER_QUOTES_ENABLED=true
```

`JUPITER_API_KEY` may be left unset for limited ad-hoc testing. Jupiter's
official keyless quote limit is **0.5 requests/second**; this module enforces
a conservative 2.5-second process-level cooldown between attempts. The
cooldown is **not a multi-worker distributed rate limiter**; add one before
multi-worker deployment and respect provider policy. No API key value is
ever returned in the quote response.

## API contract

```
GET /api/v1/meme-coins/solana/quote-preview?
  strategy=new_launch&mint=<solana_meme_mint>&side=buy&amount_raw=25000000
```

The backend constructs only three provider query parameters:
`inputMint`, `outputMint`, and `amount`. Provider host and URL path are fixed;
the user cannot supply a hostname, execute a transaction, or add `taker`.

- `side=buy`: input is native USDC mint (`EPj...TDt1v`),
  output is the requested token. `amount_raw=25000000` means 25 USDC
  (USDC has 6 decimals).
- `side=sell`: input is requested token, output is native USDC.
  `amount_raw` is the **raw smallest token amount**, not necessarily
  human-readable tokens. Token decimals vary; the API does NOT infer them.
- Both strategies are supported: `new_launch` and `momentum`. Robinhood
  Chain cannot use this Solana endpoint.
- Strictly validates Solana addresses, requested/returned mints and raw
  amounts, feeBps, router, quote-only transaction-null semantics.
- No safety approval or transaction estimate. Quote response contains
  `status=ok/disabled/rate_limited/unavailable`, a normalized snapshot
  with a capture ID, UTC receive timestamp, route name and raw amounts.
- Output is **preview-only**. Estimated network/priority fees cannot be known
  from this no-wallet quote and are **not** invented. Exact amount out is a
  route's quote, not a guaranteed fill; network conditions, RFQ expiry,
  slippage, Jito/MEV, transfer taxes and token restrictions remain uncertain.
- `tradable=false`, `wallet_connected=false`,
  `transaction_requested=false`, `transaction_submitted=false`.

The user-facing EBBot panel displays a button only after manually inspecting
a Solana candidate. Choosing BUY uses the selected $25/$50/$100 USDC budget;
SELL requires an explicit positive integer **raw token amount**. The
normalized JSON record can be inspected/copied manually. No background
polling or quote recording is activated by this feature.

## Bridge to independent offline V8 paper replay

The new bridge `src/services/meme_coin_quote_bridge.py` accepts a manually
saved input file. Save the normalized `quote` JSON from the preview, then
provide explicit **scenario assumptions** and known token decimals:

```json
{
  "captures": [
    {
      "quote": {
        "...": "Copy the complete, unmodified quote JSON from EBBot here"
      },
      "token_decimals": 6,
      "attempted_at_ms": 1795000000000,
      "network_fee_usd": "0.01",
      "priority_fee_usd": "0.00",
      "modeled_adverse_slippage_bps": 100,
      "outcome": "success"
    }
  ]
}
```

Set `attempted_at_ms` to an operator-chosen simulated attempt no more than
**3 seconds after** that quote's `captured_at_ms`. It is not a real attempt.
For a SELL, separately capture a quote at the later exit time, then supply
the sell quote snapshot in a subsequent record. Entry/exit prices are never
invented. If you only have a buy quote, there can be no realized PnL.

Run **only in an isolated offline checkout**:

```sh
python -m src.services.meme_coin_quote_bridge \
  --input /path/to/snapshots.json \
  --output /path/to/scenario-report.json
```

The bridge verifies capture format and an integrity SHA-256 (for accidental
modifications, **not** proof the quote came from Jupiter). It uses **known
token decimals supplied by the operator**, not confirmed on chain here, to
convert atomic units into decimal token quantities / USDC values. Jupiter's
`outAmount` already reflects route/platform effects: the bridge does NOT
double-charge `feeBps`. Network/priority fee USD values and transaction
success/failure assumptions are explicitly provided and replayed.

It invokes the existing V8 `replay()` engine to maintain **separate New
Launch and Momentum ledgers**. Every result reports
`data_is_live=false`, `live_trading_enabled=false`,
`simulation_is_realized_return=false` and
`this_is_actual_performance=false`. All actual fee/fill probabilities,
source authenticity, market impact after capture and live-exit execution
remain unverified. This is a *recorded quote scenario*, not a production
simulation or a verified profitability result.

## Verification

```sh
pytest -q tests/test_meme_coin_jupiter_quotes.py tests/test_meme_coin_quote_bridge.py
pytest -q tests/test_meme_coin_strategy_panel.py tests/test_meme_coin_discovery.py tests/test_meme_coin_robinhood.py tests/test_meme_coin_solana_risk.py tests/test_meme_coin_solana_holders.py tests/test_meme_coin_solana_pool.py tests/test_meme_coin_solana_owner_groups.py tests/test_meme_coin_solana_orca.py tests/test_meme_coin_paper_replay.py tests/test_meme_coin_jupiter_quotes.py tests/test_meme_coin_quote_bridge.py
cd apps/dsa-web
npm ci
npm test -- MemeCoinPage.test.tsx
```

## Next before automated meaningful paper operation

Persist immutable time-versioned observed quotes with an append-only audit,
verify mint decimals from on-chain SPL mint data, add buy-then-sell quote
freshness checks and separate per-strategy risk controls. Introduce a dedicated
paper scheduler **only after** auth, data availability, circuit breakers,
crash recovery, fee/MEV/failure calibration, and replay validation are reviewed.
**Real trading remains disabled indefinitely until independent approval.**
