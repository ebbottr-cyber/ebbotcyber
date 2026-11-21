# Robinhood Chain AI — EBBot Meme Coin V3 (read-only)

The third strategy `robinhood_chain` is independently scoped to Robinhood
Chain's EVM network. The Solana `new_launch` and `momentum` strategies
retain their separate scanning endpoints and risk boundaries.

## Confirmed network facts

- Robinhood Chain public mainnet went live on 2026-07-01:
  https://robinhood.com/newsroom/robinhood-accelerates-global-expansion-robinhood-chain-mainnet-stock-tokens-agentic-trading/
- Official Chain ID: **4663** (mainnet), **46630** (testnet).
- Native gas token: ETH. Official public RPCs (rate-limited):
  - `https://rpc.mainnet.chain.robinhood.com`
  - `https://rpc.testnet.chain.robinhood.com`
- Official developer documentation: https://docs.robinhood.com/chain/connecting/

## Current implementation

- New `Robinhood Chain AI` strategy card in existing EBBot Meme Coin panel.
- OpenCatz-inspired DEX, liquidity, risk, sentiment analyst *module registry*.
  All modules are **NOT CONNECTED**; no LLM execution is implemented.
- `GET /api/v1/meme-coins/robinhood/status` checks JSON-RPC `eth_chainId`
  then `eth_blockNumber` only, if explicitly enabled.
- Fixed official endpoints and allowlisted read methods only. No user input
  can select an arbitrary URL, specify contract addresses, or execute calls.
- The default network is **testnet** and all outbound RPC is disabled by
  default. A chain ID mismatch fails closed and does not query a block.
- No wallets, private keys, token listings, DEX candidates, swaps, positions,
  simulated fills, strategies in execution, AI agent inference, or orders.
- No role-based purchase permissions or existing Solana/Hype engines modified.

## Environment controls

Disabled by default:

```env
MEME_COIN_ROBINHOOD_RPC_ENABLED=false
MEME_COIN_ROBINHOOD_NETWORK=testnet
```

For *read-only connectivity checking* on a configured installation, opt in:

```env
MEME_COIN_ROBINHOOD_RPC_ENABLED=true
MEME_COIN_ROBINHOOD_NETWORK=testnet
```

Set `MEME_COIN_ROBINHOOD_NETWORK=mainnet` only when the operator intends to
check public mainnet RPC. This setting still never enables trading. Public
endpoints are rate-limited and unsuitable for high-frequency production use.

## OpenCatz approach and trust boundary

OpenCatz is an independent MIT-licensed third-party project:
https://github.com/dizcorvus/opencatz-ai-robinhood-chain

We reference its multi-agent *concept*, not its wallet execution, NPM
dependencies, or claim of trading performance. No code or keys from the third
party repository are run or copied into EBBot in this phase. Third-party code
requires license review, dependency audit, secret isolation and controlled
interface design before any actual adapter is considered.

## Verification

```sh
pytest -q tests/test_meme_coin_robinhood.py tests/test_meme_coin_discovery.py tests/test_meme_coin_strategy_panel.py
cd apps/dsa-web
npm ci
npm test -- MemeCoinPage.test.tsx
npm run build
```

Full CI may still fail due to unrelated legacy workflow / localization
issues in the base branch; report those failures separately and do not merge
untested changes.

## Continuation

Once V1 and V2 are validated and stacked PRs are applied in order, next
implement verified token/contract risk screening and slippage-aware paper
execution for both Solana strategies. Robinhood DEX indexing and actual
OpenCatz AI integration stay isolated behind independent development reviews.
