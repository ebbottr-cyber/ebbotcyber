# EBBot Germany: Xetra quote metadata guard (research-only)

This is a separate **stacked review branch** on top of the four-market
Xetra candidate inventory (PR #59). It does not enable portfolio
simulation, scheduled polling, deployment, or any live brokerage action.

## Safety invariant

The canonical 18 November 2026 Xetra reference list contains 1,749
official active common-stock *candidates* in
`data/market_snapshots/de/xetra-candidates.csv`. A candidate mnemonic
with `.DE` does not prove that a price-provider symbol is correct.

The quote guard permits at most 20 explicit symbols per manual call.
They must already exist in the dated Xetra candidate inventory; arbitrary
URL/ticker requests are rejected. A successful Yahoo Finance chart
response must have:

- Exact returned ticker and instrumentType=EQUITY
- currency=EUR and fullExchangeName=XETRA
- exchangeTimezoneName=Europe/Berlin
- Positive, finite regularMarketPrice and dated regularMarketTime
- No future timestamps and no quotes over 7 calendar days old

Provider failure, missing fields, wrong venue, stale timestamps, or
currency mismatch always block the record. A passing quote is labeled
`QUOTE_METADATA_MATCH`, **not** tradeable, guaranteed real-time, or
ISIN-matched. Provider chart metadata does not prove the underlying
company ISIN. Yahoo quotes may be delayed or restricted by usage terms;
they are **not** licensed real-time exchange market data.

## Windows PowerShell (from repository root)

Safest default: NO HTTP calls and NO files written.

```powershell
python -m scripts.verify_xetra_quotes
```

Opt-in manual provider metadata check for two specific official-listed symbols:

```powershell
python -m scripts.verify_xetra_quotes --fetch --symbol SAP.DE --symbol SIE.DE
```

Optional report saved to a **new** filename, never overwritten:

```powershell
python -m scripts.verify_xetra_quotes --fetch --symbol SAP.DE --output "$HOME\EBBotPaperData\xetra-quote-review.json"
```

No API keys or account credentials are necessary. Do not run unattended
provider sweeps or exhaust all 1,749 candidates; bulk pricing requires a
properly licensed and reliability-checked feed. Results are not auto-
imported into the EBBot UI, prices database, journal or paper ledger.

## One-time live public-feed sample (18 Nov 2026)

The read-only GitHub Actions [sample run 44395440152](https://github.com/ebbottr-cyber/ebbotcyber/actions/runs/44395440152)
queried **SAP.DE** and **SIE.DE** (2 HTTP GETs, 0 orders) on 18 Nov 2026
at 20:51:53 UTC. Both matched Yahoo's XETRA/EUR/EQUITY metadata.
The returned **delayed** regular-market values were SAP 193.92 EUR
(16:37:40 UTC) and SIE 266.00 EUR (16:38:55 UTC).
These are timestamped historical *samples*, not current prices, exchange
licensed real-time quotes or proof of ISIN identity. The remaining 1,747
candidate symbols have not been validated. No scan of all shares occurred.

Automatic trigger of the live-sample workflow was removed after the check;
it is manual-only and cannot be dispatched until available on the default
GitHub branch. The operator can instead run the CLI `--fetch` locally.

## Verification

```powershell
python -m unittest discover -s tests -p "test_xetra_quote_guard.py" -v
python -m unittest discover -s tests -p "test_four_market_equities.py" -v
```

The GitHub workflow runs deterministic mock responses only and confirms
the script defaults to disabled. It does not assert a successful live
provider connection or imply an approved order flow.

Remaining steps: independent symbol/ISIN identity verification, provider
license and availability, historical price data accuracy, market
calendar and EUR/TRY exchange treatment, UI read-only integration, then
prospective paper trading with an explicit separate safety review.
