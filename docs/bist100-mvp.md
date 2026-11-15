# BIST100 MVP — Phase 1

This is the isolated starting point for Turkish BIST100 support.

- Turkish equities use explicit `TICKER.IS` Yahoo Finance notation (e.g., `THYAO.IS`, `ASELS.IS`, `AKFYE.IS`); do **not** strip `.IS` or infer a Turkish market from a bare ticker.
- The `XU100.IS` BIST100 benchmark is an **index**, not the 101st stock.
- Syntax validation alone does **not** confirm BIST100 membership, actual quotes, liquidity, prices, or market hours.
- Before main analysis/screening use, add explicit `tr` routing, TRY currency, `Europe/Istanbul` time zone and source-quality data. Never fall back to Chinese A-share feeds on Yahoo quote failure.
- Build a **dated, source-verified membership snapshot** for the current Oct 1–Dec 31, 2026 index period. Borsa İstanbul’s quarterly changes are only **additions/removals**, not a complete roster; do not treat substitute stocks as current members. See https://www.borsaistanbul.com/en/announcement/15598/bist-stock-indices-periodic-review and https://www.borsaistanbul.com/en/index/xu100.
- The first commit contains only stand-alone symbol validation, offline tests, and this scope note. It does **not** connect the existing screens, provider, market context or production execution.

Track integration in the BIST100 MVP GitHub issue.

## Phase 2 — explicit routing contracts (candidate, not deployed)

- The `tr` market label is emitted only for valid, explicitly suffixed `.IS` equities; `XU100.IS` is not a constituent.
- BIST equity daily history is **Yahoo Finance only**. If Yahoo is missing or unavailable, report no data. Never fall back to AkShare, Efinance, mainland A-share or an unknown custom fetcher.
- The `XIST` exchange calendar in `exchange-calendars 4.13.3` uses `Europe/Istanbul`. Special trading half-days still require additional production validation.
- Not yet complete: live Yahoo Finance validation of all 100 constituents, web input, integrated 100-stock screener, TRY data-source metadata validation and quote staleness/coverage reporting.

## Phase 3 — date-bounded 100-member candidate snapshot

- `src/data/bist100_constituents_2026q4.json` stores the **100 unique members** for **2026-10-01 through 2026-12-31**, last independent list check `as_of=2026-11-08`, with provenance and source URLs. The snapshot was cross-checked 2026-11-15 against two independent full listings: https://bistsirketleri.com/bist-100-sirketleri/ and https://borsamorsa.com/bist-100-hisseleri/.
- Official Borsa İstanbul 2026-Q4 periodic review confirms the **27 additions, 27 exclusions and 3 substitute stocks**; it does not by itself publish all 100 active members in that delta table. Source: https://www.borsaistanbul.com/duyuru/15598/bist-pay-endeksleri-donemsel-degisiklikleri.
- `src/services/bist100_universe.py` is the offline, dependency-light loader. It refuses use outside the effective range, rejects duplicates/missing members/non-.IS codes, validates membership changes and sources, and returns symbols in canonical `.IS` Yahoo form. The benchmark `XU100.IS` is never a stock.
- `tests/test_bist100_universe.py` verifies counts, official additions/exclusions, substitutes, metadata, source provenance, and stale-period rejection.
- **Important release boundary:** This is a dated, source-cross-checked **candidate** roster, not a claim of independently fetched official full 100-member CSV, a live quote-coverage result, or permission to distribute exchange market data. Do not deploy or claim 100/100 analyzed until provider checks and a working screener/report exist.
- Separate CI baseline issues (`.github/workflows/*`, `.env.example`, Turkish notification text) remain outside this feature. Changes must stay on Draft PR #8, separate from Draft security PR #2 and unchanged `main`.

