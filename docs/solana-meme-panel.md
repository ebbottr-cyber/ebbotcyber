# Solana Meme Radar panel — manual, read-only extension

The Meme Radar page at /meme-coins uses two HTTP endpoints:

- GET /api/v1/meme-coins/status — status only; never fetches external market data.
- POST /api/v1/meme-coins/scan — explicitly requested live scan; never trades.

## Safety

External API calls require MEME_RADAR_LIVE_ENABLED=true on the server.

Example server environment setting (disabled by default):

```dotenv
MEME_RADAR_LIVE_ENABLED=false
```

The root `.env.example` is available, and the default for this optional
live-data flag remains disabled when unset. No active credentials are needed
for the public-only one-off smoke test.
The default is disabled, including when the setting is missing. The browser
never receives credentials or a wallet interface. No cron or background scan
is started. Maximum eight unique mints per scan, with a 30-second cache and
exclusive scan lock to reduce provider usage.

Only monitoring candidates with strategy, watch/blocked status, reasons
and heuristic score are returned. Unknown core security fields are blocked.
GoPlus Solana transfer-hook data may be an address object rather than a
simple status flag; any nonempty external hook program address blocks a
candidate. When the provider supplies mutable-metadata or upgrade-authority
flags, active or unknown flags block a candidate as well. Missing optional
extension fields cannot be assumed secure, and this is NOT a complete
on-chain audit (holder concentration, trade restrictions and other risks
require separate validation). Live GoPlus responses are not yet verified.

Enable application authentication and network-level throttling before
exposing optional live scans on an internet-facing deployment.

## Validation

- python -m pytest tests/test_solana_meme_api.py tests/test_solana_meme_radar.py
- cd apps/dsa-web && npm ci && npm run lint && npm run build

## Limitations

No token mint-event feed, auto-training, paper P&L persistence or real
alım-satım execution. Data providers are not yet validated under live load.

## GitHub-only live provider verification

The opt-in Actions workflow `.github/workflows/solana-meme-live-smoke.yml`
can be started under **Actions → Solana Meme Radar one-off live read-only smoke
→ Run workflow** (choose `main`; limit defaults to two mints). The workflow
also runs exactly on pull requests that change this smoke workflow or its
script/tests, so the first revision can provide network evidence without a PC.

This uses GitHub's temporary public runner to call GeckoTerminal,
DEX Screener and (for up to two discovered mints) GoPlus through the existing
read-only scanner. It has **no schedule**, wallet, database, private keys,
trade execution or background service. It prints aggregate source status,
watch/blocked counts and failure classes, never raw token payloads or API
credentials. An empty result, provider error or malformed safety response
produces a non-green result rather than a false positive.

This checks external provider access from a GitHub runner, **not** whether the
Web UI works on a particular user's Windows PC or VPS. GitHub Actions runners
are disposable and cannot replace a persistent paper-trading server. Provider
rate limits or location-dependent blocking can make the smoke fail independently
of code correctness; inspect the run output before diagnosing the cause.

## Real time-spaced observation experiment

A GitHub-only, one-shot, fixed-mint observation workflow is described in
[Turkish observation guide](solana-market-observations.md). It captures three
public quotes one minute apart for up to two mints. It does not compute
profit, send orders, schedule scans or pretend to be historical backtesting.
