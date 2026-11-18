# EBBot Meme Coin — Solana preliminary risk checks (V4)

This is a **read-only, research-only** extension, stacked after V3.
It does NOT turn the new-launch or momentum strategy into a trading bot.

## Solana mint control checks

GET `/api/v1/meme-coins/solana/mint-review?mint=<base58-pubkey>`

- **Disabled by default** (`MEME_COIN_SOLANA_MINT_AUDIT_ENABLED=false`).
- Uses a fixed official mainnet RPC (`getAccountInfo`, `encoding=jsonParsed`).
- Verifies the account's owner is the classic SPL Token Program and parsed type is `mint`.
- Checks whether `mintAuthority` and `freezeAuthority` are revoked; an active authority blocks the preliminary screen.
- Rejects Token-2022 and unknown token program owners until all extensions can be verified.
- Missing, malformed, or unavailable RPC data fails closed.
- Never infers that an authority check is proof of safety: even a `review_only` verdict is **not tradable**.
- Explicitly unverified: holder concentration, liquidity ownership/withdrawal, pool provenance and sale feasibility.
- Uses 90s process-local request cache; no wallet, transaction or order API.
- Wrapped SOL and USDC are excluded as non-meme assets if encountered.

Official references:
- https://solana.com/docs/rpc/http/getaccountinfo
- https://solana.com/docs/tokens/basics/create-mint
- https://solana.com/docs/tokens/extensions

## Hypothetical constant-product cost estimate

GET `/api/v1/meme-coins/solana/impact?liquidity_usd=60000&order_usd=25`

The model assumes **a hypothetical 50/50 USD-value classic CPMM pool**:

```
assumed_input_reserve_usd = pool_total_liquidity_usd / 2
net_input_usd = order_usd * (1 - fee_bps / 10000)
modeled_output_usd = assumed_input_reserve_usd * net_input_usd
                   / (assumed_input_reserve_usd + net_input_usd)
modeled_price_impact_pct = 100 * (1 - modeled_output_usd / net_input_usd)
modeled_total_cost_pct = 100 * (1 - modeled_output_usd / order_usd)
modeled_lower_bound_usd = modeled_output_usd * (1 - adverse_slippage_bps / 10000)
```

This estimate is **not** an executable quote, a real route, an observed fill,
or a guaranteed minimum. The 1% adverse-slippage term is an illustrative
buffer and **is separate** from price impact. Actual fees, CLMM/bin liquidity,
token taxes, pool reserve imbalance, MEV, RPC delays and failed transactions
are not captured.

An illustrative paper-review flag is raised when model impact exceeds 3%
or example order size exceeds 1% of reported pool USD liquidity. Thresholds
are research guardrails, **not permission to trade**. Every result has
`real_quote_available=false` and `tradable=false`.

## UI

In EBBot → Meme Coin → choose New Launch or Momentum → Scan candidates.
With discovery opt-in enabled, each candidate has a **Review mint & costs**
button. Example trade size can be set to $25/$50/$100. RPC checks are opt-in;
the cost model runs without external calls. Failures stay visible and do not
produce fake risk or return numbers.

Robinhood Chain RPC and the four OpenCatz-inspired disconnected agents remain
unchanged in this phase.

## Tests

- `pytest -q tests/test_meme_coin_solana_risk.py tests/test_meme_coin_robinhood.py tests/test_meme_coin_discovery.py tests/test_meme_coin_strategy_panel.py`
- `cd apps/dsa-web && npm test -- MemeCoinPage.test.tsx`
- Typecheck and build of the entire repository may still be blocked by pre-existing locale and unrelated CI issues.

## Next stage

Implement independent pool reserves / LP-ownership and holder-concentration
checks; only then develop realistic quote-based paper execution with
transaction fees, actual available route liquidity, and failure modeling.
Never connect a wallet until an explicit, separately reviewed authorization
and kill-switch layer exists.
