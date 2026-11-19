# EBBot: Four Equity Market Inventory (offline)

Only Türkiye/BIST (tr), United States (us), Germany/Xetra (de), and Hong
Kong (hk) are included in this report. Other markets in the stored global
index are excluded from selected counts, but the underlying index is not
modified. Crypto, Meme Coin, Spot and Futures code is untouched.

No stock count is clipped to 100. Inventory entries are **candidates**, not
proved exhaustive listings, broker permissions, quote availability, or live
trading signals. No scheduled scan, external request, price check, journal,
paper fill or real order is performed by this feature.

## Verified Xetra stock inventory imported on 18 November 2026

The source-derived snapshot is checked in at
`data/market_snapshots/de/xetra-candidates.csv`. The offline
`python -m scripts.audit_four_market_equities` command automatically reads
this dated manifest (1,749 unique active XETR common-stock candidates). The
official raw Xetra CSV was retrieved and validated by the read-only GitHub
Actions source check. The snapshot remains historical after 18 November 2026;
it does NOT update automatically and cannot prove current exchange listing,
real-time stock prices, valid Yahoo symbols, market-data redistribution rights,
or Turkish broker access. The remaining BIST inventory must still be provided
as an operator KAP CSV in order to complete all four-market counts.

Never enable live or simulated orders based only on these candidate symbols.
Do not confuse the snapshot with a verified price feed.

## Inputs and limitations

* US and HK: existing repository stock index, not fresh-source verified.
* TR: manual operator-provided KAP company-directory CSV from the
  existing source collector. Company codes do not prove current listing.
* DE: manual, dated original T7 XETR all-tradable-instruments CSV obtained
  from the official Deutsche Boerse downloads page:
  https://www.cashmarket.deutsche-boerse.com/cash-en/trading/Tradable-Instruments-Xetra/Downloads

The Germany parser requires the official Market: XETR line, source date,
semicolon-delimited header and required T7 column names. It retains
only Active product + Active instrument + MIC XETR + Instrument Type CS
(common equity). ETFs, funds, ETCs, ETNs and inactive rows are excluded.
Different ISINs sharing a mnemonic are blocked for manual correction.
A raw mnemonic becomes a tentative .DE provider symbol; **actual Yahoo
mapping and country-specific broker availability have not been proved**.
No source CSV is automatically downloaded or silently overwritten.

## Manual commands (PowerShell, repository root)

First create the external output directory, download the original Xetra T7
CSV manually there and save it as xetra-original.csv.

    New-Item -ItemType Directory -Force "$HOME\EBBotPaperData"
    python -m scripts.audit_four_market_equities
    python -m scripts.audit_four_market_equities --xetra-input "$HOME\EBBotPaperData\xetra-original.csv" --xetra-output "$HOME\EBBotPaperData\xetra-candidates.csv"

When the KAP CSV is also available:

    python -m scripts.audit_four_market_equities --stocks "$HOME\EBBotPaperData\kap-bist-all.csv" --stocks "$HOME\EBBotPaperData\xetra-candidates.csv"

The original T7 file must have an update date within seven calendar days.
Existing output paths are rejected rather than overwritten. The converted
file is local only and has an unverified price-symbol marker.

## Regression and release gates

    python -m unittest discover -s tests -p test_four_market_equities.py -v
    python -m scripts.audit_four_market_equities

Branch-scoped GitHub Actions runs both steps offline. Synthetic tests are
not actual live-source checks. Before enabling scans or paper trading,
independently check source freshness, ISIN mapping, price currency/quality,
holidays, delists, market-data licenses and broker access from Türkiye.
Neither automatic paper trading nor live trading is enabled here.
