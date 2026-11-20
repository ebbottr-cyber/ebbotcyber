import type { PortfolioDisplayFxRates, PortfolioSnapshotResponse } from '../types/portfolio';

/** Convert ONLY presentation values; never rewrite source prices, positions or ledgers. */
export function toTryDisplayValue(
  amount: number | null | undefined,
  currency: string,
  fx: PortfolioDisplayFxRates | null,
  sourceFxStale = false,
  now = Date.now(),
): number | null {
  if (amount == null || !Number.isFinite(amount) || sourceFxStale) return null;
  const code = currency.trim().toUpperCase();
  if (code === 'TRY') return amount;
  if (!fx || fx.status !== 'current' || !fx.asOf) return null;
  const quoteTime = Date.parse(fx.asOf);
  if (!Number.isFinite(quoteTime) || now < quoteTime || now - quoteTime > 1_800_000) return null;
  const factor = code === 'USD' ? fx.usdTry : code === 'CNY' ? fx.cnyTry : null;
  if (factor == null || !Number.isFinite(factor) || factor <= 0) return null;
  return amount * factor;
}

/** Unknown or stale rates never silently produce a TRY value. */
export function formatTryDisplay(
  amount: number | null | undefined,
  currency: string,
  fx: PortfolioDisplayFxRates | null,
  sourceFxStale = false,
  now = Date.now(),
): string {
  const value = toTryDisplayValue(amount, currency, fx, sourceFxStale, now);
  if (value == null || !Number.isFinite(value)) return '—';
  return new Intl.NumberFormat('tr-TR', {
    style: 'currency',
    currency: 'TRY',
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(value);
}


type PortfolioMonetaryTotal = 'totalEquity' | 'totalMarketValue' | 'totalCash';

/** Sum each account AFTER conversion instead of trusting the legacy aggregate CNY fallback. */
export function formatPortfolioSnapshotTry(
  snapshot: PortfolioSnapshotResponse | null,
  field: PortfolioMonetaryTotal,
  fx: PortfolioDisplayFxRates | null,
  now = Date.now(),
): string {
  if (!snapshot || !Array.isArray(snapshot.accounts) ||
      snapshot.accountCount !== snapshot.accounts.length ||
      snapshot.fxStale || snapshot.accounts.length === 0) return '—';
  let total = 0;
  for (const account of snapshot.accounts) {
    if (account.fxStale || account.dataQuality === 'partial') return '—';
    const converted = toTryDisplayValue(account[field], account.baseCurrency, fx, false, now);
    if (converted == null) return '—';
    total += converted;
  }
  return formatTryDisplay(total, 'TRY', null, false, now);
}
