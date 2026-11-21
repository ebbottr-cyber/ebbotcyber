# EBBot Meme Coin — V7 on-chain Orca Whirlpool vault research

This module extends V6. All current actions are **read-only**. No wallet,
swap, simulated fill, paper order, or approval path has been added.

## Protocol-specific support

Initial support is limited to the **official Orca Whirlpools** program:
`whirLbMiicVdio4qvUfM5KAg6Ct8VwpYzGff3uctyCc`.

The account's expected 653-byte Anchor Whirlpool layout and discriminator
`3f95d10ce1806309` are taken from Orca's official source:

- https://github.com/orca-so/whirlpools/blob/main/programs/whirlpool/src/state/whirlpool.rs

For a requested pool, the read-only service:

1. Uses a fixed public Solana mainnet RPC `getAccountInfo` (base64) to fetch
   the pool, check its owning **Orca program** and discriminator.
2. Decodes the two token mint addresses and two vault account addresses
   from documented Whirlpool account fields.
3. Checks that the selected token mint belongs to that exact pool.
4. Calls `getMultipleAccounts` (jsonParsed) for the two decoded vaults.
5. Requires both vault accounts to be classic SPL-token accounts, with
   the expected mints and the Whirlpool pool account as their on-chain
   token authority; rejects unknown or delegated accounts.
6. Reads **raw integer vault balances** and the Whirlpool stored CLMM
   liquidity field, without converting them to fiat.
7. Flags empty vaults and zero reported CLMM liquidity. The query fails
   closed on missing accounts, mismatches, corrupt layouts or materially
   inconsistent RPC slot snapshots.

## Scope and limitations

- This is **NOT** a 50/50 CPMM. Whirlpool is a concentrated-liquidity AMM.
  Raw vault balances are *not* the amount that can be traded at the current
  price. Real execution requires tick arrays, active positions, swap quote
  math, fees and transfer restrictions.
- The read-only vault authority match is **not** a token lock, LP lock,
  pool ownership or withdrawal-authority safety verification. The program
  and its upgrade/admin controls are not audited here.
- Classic SPL token vaults only. Token-2022 and unknown token-account
  programs fail closed in this stage.
- Other DEX pools return `unsupported` rather than being reported as safe.
- No live or simulated trading is permitted; all states include
  `tradable=false`, `active_swap_depth_verified=false`,
  `liquidity_lock_verified=false`,
  `lp_withdrawal_authority_verified=false` and
  `sellability_verified=false` even on a successful read.
- Full provenance, authenticity, LP/position controls and real quote
  comparisons remain for later independent work.

## Configuration

All remote requests are **off by default**:

```env
MEME_COIN_ORCA_VAULT_AUDIT_ENABLED=false
```

To opt into read-only audit checks on a secured deployment:

```env
MEME_COIN_ORCA_VAULT_AUDIT_ENABLED=true
```

API: `GET /api/v1/meme-coins/solana/orca-vaults?mint=<base58>&pool=<base58>`.
Use EBBot → Meme Coin → New Launch or Momentum → Scan → select candidate →
**Orca kasalarını incele**. This separate click avoids requesting the Orca
RPC for every coin regardless of DEX. A process-local 90s cache is used;
deploy a shared distributed rate limiter before high-volume use.

## Verification

```sh
pytest -q tests/test_meme_coin_strategy_panel.py tests/test_meme_coin_discovery.py tests/test_meme_coin_robinhood.py tests/test_meme_coin_solana_risk.py tests/test_meme_coin_solana_holders.py tests/test_meme_coin_solana_pool.py tests/test_meme_coin_solana_owner_groups.py tests/test_meme_coin_solana_orca.py
cd apps/dsa-web
npm ci
npm test -- MemeCoinPage.test.tsx
```

## Next gates

For realistic paper trading, build **separate** swap-quote adapters and
tick-aware quote validation per DEX. Simulations must record observed and
used quote timestamps, real fees, per-strategy isolated wallets/ledgers,
slippage, failure rates, cancellation, MEV assumptions and audit events.
Live execution remains blocked until explicit authorization, real
risk/guardrail review and controlled deployment.
