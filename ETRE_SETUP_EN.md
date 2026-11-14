# ETRE Daily Stock — integration notes

Source: ZhuLinsen/daily_stock_analysis. Retain original license and attribution.

## Implemented in this package
- Adds `tr` to the frontend UI language union and browser detection.
- Adds a Turkish UI dictionary with **English fallback** for untranslated keys.
- Changes the UI language switcher cycle to Turkish → English → Chinese.
- Defaults the UI to Turkish when no saved language exists.
- Preserves original backend, API and technical documentation.

## Not yet implemented / tested
- Full translation of all feature-specific strings and every screen.
- Turkish AI report generation: backend currently supports zh/en/ko and needs end-to-end extension.
- Backend runtime and frontend build validation (requires dependencies and API keys).
- BIST support, ETRE API integration, and deployment.

## Next steps
1. Run `npm ci && npm run build` from `apps/dsa-web`.
2. Configure runtime per upstream README and test with a Nasdaq symbol.
3. Extend report language across backend schemas, prompts and UI before enabling `REPORT_LANGUAGE=tr`.
4. Audit remaining English UI strings.
5. Create a private GitHub repository and push after validating.

Never commit secrets or real `.env` files.
