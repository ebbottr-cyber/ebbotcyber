# BIST100: safe operator-controlled historical report publication

This is a candidate **local filesystem publication tool**, not a deployment,
automatic recurring scan, new data feed, paid AI request or trading feature.
It never reads or migrates a database. The existing admin-only API
`GET /api/v1/data/bist100/technical-ranking` will serve the saved file **only
after** an operator sets `BIST100_TECHNICAL_REPORT_PATH` in the backend's
runtime configuration and explicitly publishes a validated JSON.

## Operator workflow

1. Obtain a historical technical report independently, e.g. the previously
   validated GitHub Actions BIST100 **100/100** artifact from PR #8 (run
   [43723300907](https://github.com/ebbottr-cyber/ebbotcyber/actions/runs/43723300907))
   or generate a fresh dated report using `src.services.bist100_screener`
   from an **isolated/read-only** SQLite database. Review market-data licensing.
2. Verify the source and its SHA-256 outside the publishing command; for
   the **specific historical 2026-11-15 / XIST 2026-11-13 report**, the
   previously checked SHA-256 was
   `42a0834b5633b9667979966acc847fde6f431fb8f57ced16c432161fb287b06a`.
   This is the JSON file hash, **not** the GitHub artifact ZIP hash.
   A caller-provided hash only proves byte equality; it does not prove
   the real-world provenance of arbitrarily supplied data.
3. Run a **dry-run** verification, without configuring the server target:
   ```bash
   python -m src.services.bist100_report_publisher --source /absolute/path/to/technical-100.json
   ```
   Check the printed source checksum, report date, last XIST session, and counts.
4. Choose an access-controlled existing directory on the machine running
   the backend, configure an absolute target filename ending in `.json`
   as `BIST100_TECHNICAL_REPORT_PATH`. Do not point it to source code or
   any credential / production database files. The command will not create
   directories, write to relative paths, or follow a symlink at the destination.
5. **Only when specifically authorized** publish via:
   ```bash
   python -m src.services.bist100_report_publisher \
     --source /absolute/path/to/technical-100.json \
     --expected-sha256 42a0834b5633b9667979966acc847fde6f431fb8f57ced16c432161fb287b06a \
     --publish
   ```
   If you intend to replace an already published file, independently back up
   the current approved file first and add `--replace-existing`. The
   command does not silently overwrite existing files. No automatic
   replacement, GitHub Actions upload, or API write method exists.
6. With admin authentication enabled and a valid cookie, open the Data Center
   BIST100 technical ranking. The API stays **read-only**, validates the
   report again on every read, and sets `Cache-Control: no-store, private`.
   If the path is missing, the API returns 404; if invalid, 422.
   A historically valid 2026-11-15 report remains labeled as a dated
   snapshot even if an operator reads it in December. It is **not live**.

## Data safety guarantees and limitations

- Default invocation is `validated_preview`; it does not create target files.
- Publishing requires an explicit `--publish` and correctly matched SHA-256,
  a valid dated BIST100 technical report, the exact verified previous XIST
  session, active membership, valid indicators and accurate result counts.
- Writes one temporary file in the already-existing target directory, flushes
  and `fsync`s it, and assigns 0600 permissions. New publications use an
  **atomic exclusive hard link**, so a report created concurrently can never
  be silently overwritten. An explicit `--replace-existing` uses atomic
  replacement. The old file is unchanged on validation, checksum, or other
  pre-write failures.
- Does not fetch Yahoo data, execute trades, call language models, read
  production SQLite or modify the GitHub default branch.
- This tool is intentionally operator-only, **not a web upload endpoint**;
  placing a web-facing write button before authorization, audit logging, path
  restrictions and deployment controls are reviewed would be unsafe.
- Production rollout remains a separate explicitly authorized step. No
  production configuration or actual report publication is performed in CI.
