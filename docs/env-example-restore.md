# Restored environment example

The repository's root `.env.example` had been removed while existing
tests, Web settings checks and deployment documentation still relied on it.
This PR restores the full, public, placeholder-only template from the
upstream project `ZhuLinsen/daily_stock_analysis` at the verified blob SHA
`f092e0ca49ec090a6fa902e1ba23dd15a2353245`.

Review highlights:

- 64 uncommented example settings are all registered in the current EBBot
  system configuration registry or explicitly hidden from the Web settings.
- All active credential, token, webhook and password assignments are blank.
- `SCHEDULE_ENABLED=false` remains the default in the example. The old
  daily-analysis GitHub Action itself remains archived and inactive.
- `SEARXNG_PUBLIC_INSTANCES_ENABLED=false` and
  `SEARXNG_TIMEOUT_SECONDS=10` remain the documented defaults.
- The optional Meme Radar live-data toggle is **commented out** to avoid
  presenting an unregistered setting as an active Web configuration field.
  The actual server default is off; details are in
  `docs/solana-meme-panel.md`.

`.env.example` is a template, **not a deployed `.env`**. No server
environment was modified. Operator secrets must be provided privately;
never commit a real `.env` file.

The upstream template retains original explanatory comments, including
Chinese text; user-facing Web localization is a distinct task.
