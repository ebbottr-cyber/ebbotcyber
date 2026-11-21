# EBBot Strategy Lab V9 — Prospective paper observation (opt in)

This feature is an explicitly manual, **single Chinese A-share ETF / cash**
paper observation log. It is not paper orders at a broker, an auto-executing
bot, or retrospective backtesting. Historical prices are only momentum warm-up
for a signal at the **latest confirmed completed close**. The initial entry
starts in cash at virtual equity 1.0. No past trades or returns are attributed
to this prospective account.

The script is **not configured to run automatically**. The repository's
earlier GitHub Actions historical smoke results are NOT prospective paper
performance, and cannot be added to this journal.

## Usage

Use a durable local directory outside the repository, writable only by your
user or server account. Do not store the journal in GitHub or CI artifact
storage. The example ETF `510300` is only a diagnostic example (not a
recommendation or a claim that this market is investable via a Turkish broker).

```bash
mkdir -p "$HOME/ebbot-paper"

# Preview: current exchange-closed ETF history, no journal write.
PYTHONPATH=. python scripts/observe_etf_paper_v9.py \
  --journal "$HOME/ebbot-paper/510300.jsonl" --asset 510300

# Explicitly append today's verified completed session close:
PYTHONPATH=. python scripts/observe_etf_paper_v9.py \
  --journal "$HOME/ebbot-paper/510300.jsonl" --asset 510300 --commit

# Offline status/read: no provider requests or writes.
PYTHONPATH=. python scripts/observe_etf_paper_v9.py \
  --journal "$HOME/ebbot-paper/510300.jsonl" --status
```

Default **preview never writes**. The operator must explicitly pass `--commit`
after the completed market session, then repeat it **on every subsequent
trading session** to generate genuinely new paper observations. If any
session is skipped, the program refuses retroactive catch-up. Start a **new**
journal for a new observation epoch and label it accordingly; do not pass a
historical `--as-of` to artificially create past records (none is supported).

A physical PC/VPS and configured compatible market-data provider are
required for multi-day observation; we have **not deployed** this journal
to a running server and have not enabled scheduled tasks.

## Causal rule and accounting

- Fix `lookback=40`, `rebalance=weekly`, `fee=10 basis points per side`,
  `slippage=5 bp per side` at first entry by default; explicitly change
  flags if needed **before initialization**. Rules are frozen thereafter.
- The ETF service confirms a real exchange session, adjusted daily prices
  and data quality; the source is recorded and frozen too.
- A close-time momentum signal is captured only on the real weekly/monthly
  last trading session using the existing `momentum_scores` and
  `select_holdings` functions. It cannot fill at its own close.
- Only at the **next** completed session close can a pending target buy/sell
  the ETF virtually, applying fee + slippage. The prior day's holdings earn
  the intervening daily close-to-close return. From a fresh journal there
  is no earlier position and no historical profit.
- Missing or duplicate sessions, stale closing data, provider switching,
  bad or revised prior adjusted quotes (>1 basis point), invalid calendars,
  incompatible rule changes and incomplete journal writes cause an explicit
  **BLOCKED** failure. They do not silently fill, forward-fill, repair or
  award performance.
- Cumulative paper equity begins at **1.0** and current maximum drawdown
  is tracked using completed closes. It is a **virtual mark-to-market**
  at daily close, without cash yield, taxes, dividends beyond provider
  adjustment, exchange price limits, slippage calibration or live fills.
- Each JSONL record includes the market date, original observation UTC
  timestamp, last close, source, signal, pending target, fill, exposure,
  virtual equity, frozen parameters and previous record's SHA-256 hash.
  A sibling `.lock` prevents simultaneous writers. The hash chain
  detects corruption but is **not a cryptographically signed audit trail**:
  a person with full file write permissions can rewrite hashes too.
- Do not commit this personal paper journal to GitHub. Back it up using
  restricted file permissions. If a lock remains after a crash, inspect
  the file and recover explicitly: the script never auto-breaks locks.

## How it differs from V8 holdout

V8 replayed old historical periods and, in the final holdout, recorded
about -0.81% on the 510300 toy ETF strategy. V9 must begin **now**
on actual observed sessions. A GitHub CI run with synthetic data verifies
causal mechanics but **cannot substitute** for real consecutive future
sessions. Prospective statistical evidence needs many such observations
and independent review. No result can automatically promote the strategy
to live execution.

## Safety and validation

```bash
python -m pytest -q tests/test_prospective_paper.py
python -m py_compile src/core/prospective_paper.py \
  src/services/prospective_paper_journal.py scripts/observe_etf_paper_v9.py
```

No REST/API/React route, automation, paper broker, database migration,
cron schedule, portfolio import or order path is changed. PR V9 is stacked
on V8/V7/V4/V3/V2/V1 drafts, not on main. No main merge is authorized.
This manual one-ETF research baseline is not available for crypto or
multi-asset ETF strategies yet.
