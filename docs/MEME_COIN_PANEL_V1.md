# Solana Meme Coin Panel — V1 (read-only)

This release adds an isolated EBBot navigation section, strategy inventory,
and authenticated status endpoint. It **does not** add trading, market data,
wallet connectivity, paper fills, performance history, or AI decision-making.

## Endpoints and UI

- GET `/api/v1/meme-coins/overview`: returns two independent strategies.
- Route `/meme-coins`: strategy cards and connection/readiness status.
- `new_launch`: intended for newly launched tokens and pools on Solana.
- `momentum`: intended for rising tokens with independent momentum checks.
- Both are hard-disabled and return unavailable performance metrics (`null`).
- The future simulation mode is labelled `paper_planned`, **not active**.
- Robinhood Chain is explicitly out of scope for this Solana-first release.

## Safety/architecture boundaries

1. The meme-coin API is read-only and uses the existing API auth middleware.
2. Do not share private keys, execution ledgers, or account budgets with stock
   portfolio services or existing Solana Hype deployments.
3. Before activation, add real event streams, integrity and liquidity checks,
   wallet/pool risk review, deterministic simulated fills (fees, slippage,
   failed transactions), isolated per-strategy ledgers, and a shared kill switch.
4. Only expose real trading in a later release behind explicit configuration,
   approvals and independent risk controls. Never reuse the paper ledger.
5. Do not report successful trades, returns, or data freshness unless backed
   by the actual engine and its audit trail.

## Verification

- `pytest -q tests/test_meme_coin_strategy_panel.py`
- From `apps/dsa-web`: `npm ci && npm run build`
- Confirm `/meme-coins` loads and shows two disconnected strategies.
- Confirm no wallet/order mutation routes appear in `/openapi.json`.
