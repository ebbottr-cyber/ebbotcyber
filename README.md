# EBBOT-CYBER

Custom market-analysis project based on [ZhuLinsen/daily_stock_analysis](https://github.com/ZhuLinsen/daily_stock_analysis).

## Project status

- Customized application source imported into the `main` branch.
- Turkish web UI localization is partially implemented, with English fallback.
- Turkish analysis-report language support is partial; live Turkish output validation remains pending.
- Frontend build and backend runtime tests are **pending**.
- Nasdaq end-to-end validation is the first milestone; BIST support follows after stability.
- Existing crypto and Solana Hype components are outside the scope of this project.

## Next steps

1. From `apps/dsa-web`, run `npm ci` then `npm run build`.
2. Configure the application with the upstream setup instructions, using local secrets only.
3. Validate a Nasdaq analysis end to end.
4. Verify Turkish reports end to end and finish translating the web interface.
5. Integrate BIST support after the Nasdaq path is stable.

See [Turkish localization status](docs/turkish-localization-status.md) for progress and verification steps.

## Maintenance

Keep technical documentation and code identifiers in English. Preserve upstream attribution and license notices. Do not commit API keys or local `.env` files. GitHub Actions workflows were moved to `workflows_disabled` during import to avoid unwanted runs.
