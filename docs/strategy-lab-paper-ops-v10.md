# EBBot Strategy Lab V10 — paper journal review and opt-in daily operations

**This is an opt-in preview / paper-recording tool, not a deployed service.**
V10 does not run after this PR is created: it adds no scheduler, worker, broker,
wallet, account position write, trading instruction, or background task.

## What operators and the panel can do

1. Run the V9 paper observer on a persistent machine. The first prospectively
   observed completed ETF close records a from-cash journal. No old backtests
   or synthetic GitHub smoke outputs may be imported as real prospective P&L.
2. View `/strategy-lab` and choose the **local JSONL journal file** under the
   'Sanal İşlem Günlüğü' section. A user-chosen journal is sent to the existing
   Web API via `POST /api/v1/strategy-lab/paper/inspect`, **only when admin
   authentication is enabled and a valid session is present**.
3. The server validates the full V9 JSONL SHA-256 chain, monotonic session
   sequence, frozen ETF/source rules, file structure and size (up to 512 KiB /
   5,000 records). It responds with only sanitized state, percent return,
   observed drawdown, simulated buy/sell counts and the most recent 40 rows.
   **No journal path is accepted, no file is saved, and no market data is fetched
   from the read-only import route**.
4. When `ADMIN_AUTH_ENABLED=false`, the import endpoint **returns 403**,
   even though the broader app sometimes permits read-only API requests.
   Keep the paper journal on a trusted machine; do not upload journal files
   to an unknown remote EBBot installation.

This panel is deliberately **manual file import**: no real-time streaming or
server-side automatic journal polling has been implemented. Do not show empty
journals as zero-profit trading performance, and do not treat a SHA-256 chain
as independently notarized pricing or real-money execution proof. File upload
works only after deploying the Web/API code from the reviewed PR stack.

## Optional daily operator wrapper

**Default**: preview-only, not persistent. Supply `--commit` explicitly to
append exactly one latest *completed* Chinese ETF market session. No
historical catch-up, no same-day fill, no changing frozen parameters/provider.

```bash
# Work from the checked out EBBot repository on a persistent Linux PC/VPS.
mkdir -p "$HOME/ebbot-paper"
chmod 700 "$HOME/ebbot-paper"

# Safe preview with a local health status; journal remains unchanged:
PYTHONPATH=. python scripts/run_etf_paper_daily_v10.py \
  --journal "$HOME/ebbot-paper/510300.jsonl" \
  --status-file "$HOME/ebbot-paper/510300.health.json"

# After preview and reviewing configuration, opt in to paper recording:
PYTHONPATH=. python scripts/run_etf_paper_daily_v10.py \
  --journal "$HOME/ebbot-paper/510300.jsonl" \
  --status-file "$HOME/ebbot-paper/510300.health.json" \
  --commit --notify-on-error
```

`--notify-on-error` is an additional **opt-in** and only sends a generic
failure notice through existing configured `NotificationService` channels
when available. No private journal path, equity, secrets or market-data history
are included in that notice. This mode does **not** send daily performance
notifications or create schedules, and delivery is not guaranteed when the
notification provider is unavailable. A redacted local health JSON status is
written atomically on success or failure. Failure exits nonzero.

For daily observation an operator may separately schedule the **second**
command using their operating system's cron / Task Scheduler **after the
Shanghai exchange closes** (prefer an appropriate post-close delay). The
scheduler must use a persistent working directory, account, journal volume,
and market-data credentials/permissions where needed. Coordinate timezone
and exchange holidays explicitly; if the exchange is closed or a session is
skipped the observer may block until an operator reviews the journal. V10 does
not install or activate a schedule in any environment.

Example crontab line **only if the host's timezone is Asia/Shanghai** and
after deliberate operator consent (not installed by this PR):

```cron
30 16 * * 1-5 cd /path/to/checked-out/ebbot && /usr/bin/python3 scripts/run_etf_paper_daily_v10.py --journal /private/paper/510300.jsonl --status-file /private/paper/510300.health.json --commit --notify-on-error >> /private/paper/observer.log 2>&1
```

Treat all paths as **illustrative placeholders**. Do not copy without
configuring the actual server, paths, interpreter, and notification channels.
Do not store journal/health files or alert credentials in the source repo or
GitHub Actions artifacts.

## Design boundaries and failure modes

- V9 paper accounting is based on the existing `momentum_scores` and
  `select_holdings`, with an actual next-session virtual fill and per-side
  fees/slippage. It uses **one A-share ETF vs cash** only.
- Forward-adjusted data can be revised by vendors. The V9 observer blocks
  material revisions to yesterday's adjusted price, provider switches and
  missing sessions; V10 never auto-corrects or restarts these journals.
- If no provider is available, the append lock is stale, files are corrupt,
  the last session was skipped or authentication is disabled, errors remain
  explicit; the UI never displays fabricated outcomes. A failed notification
  does not turn a failed observation into success.
- The front end translates the display in Turkish, English and Chinese.
  There are no new general application configuration variables or secrets.
- The app import is explicitly **read-only**; there is no API to append
  records, start/stop paper sessions, schedule jobs or submit trades.
- No actual prospective multi-session trading record has been collected
  on the user's persistent host by this PR. Historical simulations and
  synthetic tests must never be labeled as real future paper performance.
- The full stack depends on prior unmerged drafts #30, #32, #34, #37, #42,
  #44 and #46. Main-branch integration/full CI and visual UI evidence remain
  independent review requirements.

## Focused verification

```bash
python -m pytest -q tests/test_strategy_lab_paper_ops_v10.py \
  tests/test_prospective_paper_cli.py tests/test_prospective_paper.py
cd apps/dsa-web
npx vitest run src/components/strategy-lab/__tests__/PaperJournalPanel.test.tsx \
  src/pages/__tests__/StrategyLabPage.test.tsx
npx tsc -p tsconfig.app.json --noEmit
npm run build
```

No screenshots yet: this is a draft that has not been deployed to a running
authenticated Web server. UI visual confirmation and testing with an actual
persistent post-close journal are required before production merge.
