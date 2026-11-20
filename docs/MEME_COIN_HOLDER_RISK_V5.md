# Meme Coin V5 — Solana token-account concentration research

This step extends V4 in a separate draft PR. It is **not** a live or paper
trading feature.

## Source and limitations

- `getTokenSupply`: supply in raw token base units.
- `getTokenLargestAccounts`: up to 20 largest **token accounts**, not wallets
  or ultimate beneficial owners.
- The two calls use the fixed public Solana mainnet endpoint, commitment
  `confirmed`, with a maximum allowed snapshot slot difference of 150.
- Neither endpoint identifies controlling owners. A DEX vault, custody account,
  exchange, program-controlled account or related token accounts may feature
  among the largest. Therefore this is a concentration **signal**, not an
  ownership map or automated fraud/quality label.

Official RPC references:
- https://solana.com/docs/rpc/http/gettokensupply
- https://solana.com/docs/rpc/http/gettokenlargestaccounts

## Data contract

Read-only `GET /api/v1/meme-coins/solana/concentration?mint=<base58-address>`

Response includes token-account percentages of total reported supply:
- `top_account_pct`
- `top_ten_accounts_pct` (up to ten observed token accounts)
- `observed_top_twenty_pct` (up to twenty observed accounts)
- supply/account context slots, warning flags and observation time.
- `interpretation=token_accounts_not_wallets`.
- `owner_identity_verified=false`, `pool_vaults_classified=false`,
  `full_safety_verified=false` and `tradable=false` **always**.

Conservative heuristic warnings:
- Single token account holds at least 20% of reported mint supply.
- Up to ten largest token accounts hold at least 70%.

Below these levels is **not a safety clearance**. Percentages can be distorted
by timing differences, custodians, vaults or controlled multiple addresses.
Malformed RPC results, duplicate accounts, inconsistent slots, missing data,
impossible totals, bad supply and other failures are unavailable, not safe.

## Configuration

```env
MEME_COIN_SOLANA_HOLDER_AUDIT_ENABLED=false
```

No provider calls unless explicitly enabled. Enable only on a secured
installation with authenticated administrator access:

```env
MEME_COIN_SOLANA_HOLDER_AUDIT_ENABLED=true
```

There is a 90-second in-process cache, including transient failure cooldown.
It is not a cluster-wide rate limiter, so avoid multi-worker high frequency
polling of a public RPC. The UI calls on explicit candidate review, not in a
scheduler.

## UI

Under EBBot → Meme Coin → New Launch or Momentum, scan candidate pools,
then use the existing **Mint ve maliyeti incele** action. The result will show
mint authority status, hypothetical CPMM cost estimate, and token-account
concentration in one read-only research view. Robinhood Chain remains separate.

## Next step

- Identify token-account controlling owners and classify exchange/pool vaults.
- Verify actual pool reserves, withdrawal authority/LP ownership, token
  transfer restrictions and sell feasibility using independent sources.
- Only then design isolated realistic quote-based paper fills (never permit
  actual wallet operations before separate security review).

## Tests

```sh
pytest -q tests/test_meme_coin_strategy_panel.py tests/test_meme_coin_discovery.py tests/test_meme_coin_robinhood.py tests/test_meme_coin_solana_risk.py tests/test_meme_coin_solana_holders.py
cd apps/dsa-web
npm test -- MemeCoinPage.test.tsx
```
