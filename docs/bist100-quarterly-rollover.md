# BIST100 quarterly roster rollover: 2027 readiness without fabricated members

**As of 15 November 2026**, the repository only includes a candidate
**2026-Q4** full 100-stock membership snapshot:
`src/data/bist100_constituents_2026q4.json`, effective
**2026-10-01 through 2026-12-31**. The 2027-Q1 full roster is **not
present or independently verified**. Do not copy or guess it.

## Check readiness safely (offline)

From the repository root, run:

```bash
python -m src.services.bist100_universe --for-date 2026-11-15
python -m src.services.bist100_universe --for-date 2027-01-04
```

The 2026 command checks the current dated file's internal validity and
outputs `status=structurally_valid_not_live_verified`. Without a
new reviewed roster file, the 2027 command exits **2** and prints
`status=blocked_missing_or_invalid_roster` along with
`required_snapshot=bist100_constituents_2027q1.json`. It never
downloads prices, selects a China-market fallback, adds a symbol, triggers
analysis, changes SQLite, uses paid AI or places an order.

The same fail-closed check applies in existing
`bist100_coverage.scan_bist100_history`,
`bist100_import`, `bist100_screener`, and saved BIST report validators
because they already resolve members via `load_bist100_universe(as_of)`.

## Procedure once the next **actual** official review is available

1. Identify the new period's effective **full quarter** and obtain
   the official Borsa İstanbul change announcement for that exact period.
   Independently cross-check **the complete 100-member list**, not just
   the change announcement. Confirm actual .IS equity tickers and TRY/XIST.
   Review official licensing and permitted use.
2. Create **only after factual validation** the file
   `src/data/bist100_constituents_2027q1.json` as an explicitly reviewed
   change. Do not create a speculative placeholder file in production.
3. Set `effective_from=2027-01-01`,
   `effective_to=2027-03-31`, `as_of`, `verified_on`,
   source URLs and written provenance. Include exactly 100 **sorted**
   canonical equity members. `XU100.IS` is a benchmark, not a 101st stock.
4. Populate `official_additions`, `official_exclusions`,
   `official_substitutes` from **that quarter's** official change notice.
   The code confirms actual membership delta versus the preceding checked-in
   2026-Q4 list matches additions/exclusions exactly. It rejects a copied old
   100-member roster, an altered count, a prior-period official URL, duplicate
   symbols, a missing predecessor, invalid dates, and symlinked snapshot files.
   **Do not copy the old Q4-specific 27/27/3 change counts into 2027-Q1**;
   the actual counts may differ.
5. Run `python -m src.services.bist100_universe --for-date 2027-01-04`.
   This confirms **structural** consistency only, **not** the true
   authenticity of remote source URLs, a live Yahoo feed or stock-analysis
   readiness. Require independent human review of links/constituents.
6. Then run only separately approved rate-limited Yahoo quote coverage,
   currency verification, XIST calendar checks, and read-only screener tests
   against an isolated database. Keep a dated report and manual rollback
   option before considering any deployment.

For 2027-Q2 and later, the same filename and delta rules apply:
`bist100_constituents_YYYYqN.json`, exactly one calendar quarter,
and verified difference from the immediate predecessor. A missing or
unreviewed predecessor also blocks the new quarter.

## Testing boundary

`tests/test_bist100_quarterly_rollover.py` uses deliberately
**synthetic, temporary** Q1 membership lists and fake `.invalid`
source links exclusively for deterministic contract tests. No invented
2027 symbols or hypothetical source URLs are checked in as production
data. The existing 2026-Q4 snapshot and its official 27/27/3 checks
remain untouched.

**Release gate:** PRs remain draft, no merge/deployment without explicit
operator approval. No real-world 2027 membership or quote coverage is
claimed by this code or these tests.
