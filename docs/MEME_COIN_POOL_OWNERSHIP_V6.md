# Meme Coin V6 — Solana pool liquidity consistency + sampled owner grouping

Stacked on V5, and **research-only**. Two independent Solana strategies can
use the same read-only checks; Robinhood Chain remains separate.

## 1) Pool liquidity review

`GET /api/v1/meme-coins/solana/pool-review?mint=<base58>&pool=<base58>`

**Opt-in** via `MEME_COIN_SOLANA_LIQUIDITY_REVIEW_ENABLED=true`; default
`false`, no outbound calls. On explicit UI review, it:

1. Fetches the exact Solana pool address from GeckoTerminal and requires
   the returned base token mint to match the selected mint.
2. Fetches the same `pairAddress` from DEX Screener, requires
   `chainId=solana` and `baseToken.address` equal to the same mint.
3. Reads the pool address with the fixed Solana RPC `getAccountInfo`; checks
   whether an account exists, its owner program and basic account metadata.
4. Compares each provider's reported USD liquidity. Greater than **35%**
   difference, less than **$10,000** reported liquidity, missing on-chain
   account, or unexpected basic account state produces a risk flag.

**Critical limitations:**

- These two aggregators may share upstream market data: matching values are
  *not* independently verified on-chain reserves.
- Checking Solana account existence/owner program does **not** prove the
  address is an authentic DEX pool or that liquidity belongs to the trader.
- LP lock, LP token holder, withdrawal authority, actual token reserves,
  liquidity vault ownership, CLMM liquidity in-range, and sellability are
  **not verified**, even if the result is `review_only`.
- Every result is `tradable=false`, with explicit false verification fields.
- Missing, mismatched, malformed or unavailable provider data fails closed.

APIs:
- https://docs.dexscreener.com/api/reference
- https://api.geckoterminal.com/docs/index.html
- https://solana.com/docs/rpc/http/getaccountinfo

## 2) On-chain owner address grouping of sampled token accounts

`GET /api/v1/meme-coins/solana/owner-groups?mint=<base58>`

**Opt-in** with `MEME_COIN_SOLANA_OWNER_GROUPS_ENABLED=true`; default
`false`. Uses only Solana mainnet read methods:

- `getTokenSupply`, `getTokenLargestAccounts`, and
  `getMultipleAccounts` (jsonParsed, up to 10 largest token accounts).
- Verifies account program, mint, exact raw balances, slot consistency and
  parsed SPL account-owner fields. Groups account balances by that field.
- Flags an observed on-chain owner group holding at least **20% of total
  reported token supply**. The percentage refers to sampled accounts only,
  not a full global ownership graph.

**Interpretation:** one owner field is NOT the beneficial investor. A single
human may control many owners. DEX vaults, custodians, multisigs and delegated
accounts are not classified. The program owner's identity must never be
presented as a verified human or known fraudster. Both a passing and flagged
sample remain `tradable=false`; user-facing statuses distinguish findings
from safe outcomes.

Methods:
- https://solana.com/docs/rpc/http/gettokensupply
- https://solana.com/docs/rpc/http/gettokenlargestaccounts
- https://solana.com/docs/rpc/http/getmultipleaccounts

## How to inspect

In EBBot → Meme Coin → Solana New Launch or Momentum → Scan → click
**Mint ve maliyeti incele** for a candidate. V6 augments the already present
authority, token-account concentration, and hypothetical cost panels with
the two new read-only findings. All providers use a 90-second process-local
cache to limit request volume. Use an authenticated deployment and shared
rate limits before enabling external API calls in a multi-worker environment.

## Verification

```sh
pytest -q tests/test_meme_coin_strategy_panel.py tests/test_meme_coin_discovery.py tests/test_meme_coin_robinhood.py tests/test_meme_coin_solana_risk.py tests/test_meme_coin_solana_holders.py tests/test_meme_coin_solana_pool.py tests/test_meme_coin_solana_owner_groups.py
cd apps/dsa-web
npm ci
npm test -- MemeCoinPage.test.tsx
```

## Next gates before any paper trading

Reconcile decoded on-chain pool vault reserves with quoted liquidity for a
specific DEX implementation, classify LP token/burn/lock and vault control,
and use actual quote providers for simulated entry and exit including
fees, transaction failures, price changes and MEV. This V6 adds none of
those execution or wallet privileges.
