# Solana Meme Radar panel — manual, read-only extension

The Meme Radar page at /meme-coins uses two HTTP endpoints:

- GET /api/v1/meme-coins/status — status only; never fetches external market data.
- POST /api/v1/meme-coins/scan — explicitly requested live scan; never trades.

## Safety

External API calls require MEME_RADAR_LIVE_ENABLED=true on the server.
The default is disabled, including when the setting is missing. The browser
never receives credentials or a wallet interface. No cron or background scan
is started. Maximum eight unique mints per scan, with a 30-second cache and
exclusive scan lock to reduce provider usage.

Only monitoring candidates with strategy, watch/blocked status, reasons
and heuristic score are returned. Unknown security fields are blocked.

Enable application authentication and network-level throttling before
exposing optional live scans on an internet-facing deployment.

## Validation

- python -m pytest tests/test_solana_meme_api.py tests/test_solana_meme_radar.py
- cd apps/dsa-web && npm ci && npm run lint && npm run build

## Limitations

No token mint-event feed, auto-training, paper P&L persistence or real
alım-satım execution. Data providers are not yet validated under live load.
