# EBBot Meme Coin V8 — deterministic offline paper replay

**Status: offline test harness only.** This PR extends V7 with an explicitly
manual, local, deterministic price-quote replay engine for the two separate
Solana strategies `new_launch` and `momentum`. It is not automated live
paper trading, it uses no real-time market data, and it never sends any orders.

## Trust boundary

- Input consists solely of **operator-supplied, explicitly synthetic**
  `offline_fixture` JSON quotes. Prices, liquidity and future sell quotes are
  never fabricated by the engine.
- The replay cannot read from Jupiter, GMGN, GeckoTerminal, wallets or network.
- The module has no private keys, trading adapters or HTTP routes that mutate
  positions. A single **read-only** `GET /api/v1/meme-coins/paper/status`
  endpoint reports the availability of this offline harness, not performance.
- UI shows two strategy cards, both **not running**; no historical/actual
  profit is displayed. Existing EBBot and Robinhood Chain remain unchanged.
- Use the full project authentication/rate-limiting review before using the
  API in a public deployment; the new endpoint itself is read-only.

## Quote/replay input contract

```json
{
  "events": [
    {
      "id": "synthetic-1",
      "strategy": "new_launch",
      "mint": "So11111111111111111111111111111111111111112",
      "side": "buy",
      "source": "offline_fixture",
      "quote_observed_at_ms": 1000,
      "attempted_at_ms": 1200,
      "amount_in": "50",
      "expected_out": "100",
      "network_fee_usd": "0.01",
      "priority_fee_usd": "0.00",
      "modeled_adverse_slippage_bps": 100,
      "outcome": "success"
    }
  ]
}
```

This sample is **invented fixture data**, not any historical trade or valid
buy opportunity for the example mint.

For BUY, `amount_in` is USD and `expected_out` is *token amount*.
For SELL, `amount_in` is held token amount and `expected_out` is USD.
Expected outputs are interpreted as **already after DEX/pool/route fees**.
Network and priority fees are separate USD values and are charged once,
not added a second time to the quoted output.

A successful scenario uses
`modeled_output = expected_out * (1 - adverse_slippage_bps / 10000)`.
No separate token tax, AMM model, routing or price impact is implied by that
formula. A source quote must provide those effects before the hypothetical
adverse move is applied.

Events must have unique IDs, monotonic attempted times, quote timestamps
not later than the simulated attempts, quote age <=3 seconds, valid amounts,
and at most 10% scenario slippage. Invalid event structure aborts replay;
risk/cost conditions create explicit rejected audit rows. Network timeouts
and pre-chain rejections have no assumed fee and no fill; a modeled on-chain
failure charges the supplied network/priority fees but records no trade.
Timeout fee treatment is an intentionally optimistic simplification and
requires later reconciliation with on-chain signature tracking.

## Separate strategy ledgers

Each strategy has a completely separate initial USD cash balance (default
$1,000), token quantities, FIFO-independent *weighted average* cost basis,
realized profit/loss on simulated sells, fee totals, and event-level audit.
The two strategies may hold the same mint, but they never share a cash
balance or cost basis.

Conservative *offline fixture* guardrails:
- Up to $100 per example buy.
- Up to $200 modeled exposure/cost basis per token and strategy.
- Up to 3 concurrent token positions per strategy.
- Sell amount cannot exceed previously simulated holdings.
- No unrealized P&L unless separately supplied future market marks (not
  implemented). Sells, if provided as future fixture events, create **sample
  realized** P&L only — not investment results.
- No live portfolio synchronization, daily drawdown control, order retry,
  routing fee discovery, fill probability model, or data persistence service.
  These are outstanding risk and operational controls before automation.

## Run manually in a trusted checkout

```sh
python -m src.services.meme_coin_paper_replay --input /path/to/synthetic_fixture.json --output /path/to/replay_result.json
```

Do not confuse the output with actual trades. The JSON includes
`data_is_live=false`, `quote_adapter_connected=false`,
`simulation_is_realized_return=false` and
`execution_is_real=false` audit flags.

## Verification

```sh
pytest -q tests/test_meme_coin_paper_replay.py
pytest -q tests/test_meme_coin_strategy_panel.py tests/test_meme_coin_discovery.py tests/test_meme_coin_robinhood.py tests/test_meme_coin_solana_risk.py tests/test_meme_coin_solana_holders.py tests/test_meme_coin_solana_pool.py tests/test_meme_coin_solana_owner_groups.py tests/test_meme_coin_solana_orca.py tests/test_meme_coin_paper_replay.py
cd apps/dsa-web
npm ci
npm test -- MemeCoinPage.test.tsx
```

## Next stage — before meaningful automated paper results

Add versioned time-stamped historical quotes for entry **and** exit from
a real provider, track route validity/fees, simulate failed fills and queueing,
persist ledgers atomically, implement global as well as per-strategy circuit
breakers, reconcile timestamps and run walk-forward performance tests with
out-of-sample data. Do not enable automatic live trading at that stage.
