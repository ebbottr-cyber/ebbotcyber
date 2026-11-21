# Meme Coin Discovery V2 (read-only, opt-in)

Built on top of `feat/meme-coin-strategy-panel-v1`.

- `GET /api/v1/meme-coins/candidates?strategy=new_launch`: recent
  Solana pools, filtered for pool age, liquidity and basic trade activity.
- `GET /api/v1/meme-coins/candidates?strategy=momentum`: trending
  Solana pools, filtered for 5-minute change, liquidity and trade volume.
- Both strategies use GeckoTerminal public API as a **temporary common
  research data provider**. Pump.fun direct feeds and GMGN wallet analytics
  are **not** connected. GeckoTerminal snapshots are not sub-second feeds.
- UI initiates a scan on button press; no new background scheduler is added.
- Each strategy has an independent 60-second process-level response cache
  (including brief cooldown on provider failure) to avoid provider abuse.
- A score is a deterministic *research ranking*, **not** AI confidence,
  prediction, safety rating or an instruction to buy.
- Every returned pool is `risk_status=unverified` and `tradable=false`;
  no token authority, freeze, holder, ownership or sellability checks exist
  yet. No trade route, private-key code, or paper fills are implemented.
- No return or performance figures are fabricated. Provider failures are
  distinguishable from legitimate empty result lists.

## Configuration

By default, no third-party network calls are made:

```
MEME_COIN_DISCOVERY_ENABLED=false
```

To explicitly enable read-only scans on a trusted deployment:

```
MEME_COIN_DISCOVERY_ENABLED=true
```

Do not enable this until the usual authenticated admin access, rate limiting,
and API egress controls are configured. A single-process cache is insufficient
for multi-worker deployments; use a shared distributed rate limiter before scale.

Documentation: https://api.geckoterminal.com/docs/index.html

## Verification

```
pytest -q tests/test_meme_coin_discovery.py tests/test_meme_coin_strategy_panel.py
cd apps/dsa-web
npm ci
npm run build
npm test -- MemeCoinPage.test.tsx
```

NOTE: Existing unrelated TypeScript TR locale errors on `main` may still
block the full frontend build until corrected separately.

## Next phase

- Validate account/contract authorities, pool provenance, liquidity behavior,
  holder concentration, and practical sellability using independent data.
- Persist immutable sample snapshots with provider timestamp and scoring version.
- Record simulated fills/fees/slippage and strategy-separated paper ledgers.
- Build a strict kill switch, authorization and operations checks before any
  proposal to enable real trading.
