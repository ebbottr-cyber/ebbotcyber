# BIST100 MVP — Phase 1

This is the isolated starting point for Turkish BIST100 support.

- Turkish equities use explicit `TICKER.IS` Yahoo Finance notation (e.g., `THYAO.IS`, `ASELS.IS`, `AKFYE.IS`); do **not** strip `.IS` or infer a Turkish market from a bare ticker.
- The `XU100.IS` BIST100 benchmark is an **index**, not the 101st stock.
- Syntax validation alone does **not** confirm BIST100 membership, actual quotes, liquidity, prices, or market hours.
- Before main analysis/screening use, add explicit `tr` routing, TRY currency, `Europe/Istanbul` time zone and source-quality data. Never fall back to Chinese A-share feeds on Yahoo quote failure.
- Build a **dated, source-verified membership snapshot** for the current Oct 1–Dec 31, 2026 index period. Borsa İstanbul’s quarterly changes are only **additions/removals**, not a complete roster; do not treat substitute stocks as current members. See https://www.borsaistanbul.com/en/announcement/15598/bist-stock-indices-periodic-review and https://www.borsaistanbul.com/en/index/xu100.
- The first commit contains only stand-alone symbol validation, offline tests, and this scope note. It does **not** connect the existing screens, provider, market context or production execution.

Track integration in the BIST100 MVP GitHub issue.
