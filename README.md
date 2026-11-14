# EBBOT-CYBER

Custom market-analysis project based on [ZhuLinsen/daily_stock_analysis](https://github.com/ZhuLinsen/daily_stock_analysis).

## Project status

- Customized application source imported into the `main` branch.
- Turkish web UI localization is partially implemented, with English fallback.
- Turkish AI-generated analysis reports are **not yet implemented**.
- Frontend build and backend runtime tests are **pending**.
- Nasdaq validation is the first milestone; BIST support and ETRE integration follow.
- Existing crypto and Solana Hype components are outside the scope of this project.

## Next steps

1. From `apps/dsa-web`, run `npm ci` then `npm run build`.
2. Configure the application with the upstream setup instructions, using local secrets only.
3. Validate a Nasdaq analysis end to end.
4. Implement Turkish reports and finish translating the web interface.
5. Add BIST and ETRE integration after the Nasdaq path is stable.

See [ETRE_SETUP_EN.md](ETRE_SETUP_EN.md) for localization notes.

## Maintenance

Keep technical documentation and code identifiers in English. Preserve upstream attribution and license notices. Do not commit API keys or local `.env` files. GitHub Actions workflows were moved to `workflows_disabled` during import to avoid unwanted runs.
