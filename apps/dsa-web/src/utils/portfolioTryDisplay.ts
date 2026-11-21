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
  if (!fx) return null;
  const factors: Record<string, number | null | undefined> = {
    USD: fx.usdTry,
    CNY: fx.cnyTry,
    HKD: fx.hkdTry,
    JPY: fx.jpyTry,
    KRW: fx.krwTry,
    TWD: fx.twdTry,
  };
  if (!Object.prototype.hasOwnProperty.call(factors, code)) return null;
  // A present pairStatus map is authoritative: never let a missing per-pair
  // timestamp inherit another currency's (possibly fresher) global timestamp.
  const asOf = fx.pairStatus
    ? fx.pairStatus[code.toLowerCase()] === 'current' && fx.pairAsOf?.[code.toLowerCase()]
    : (code === 'USD' || code === 'CNY') && fx.status === 'current' && fx.asOf;
  if (!asOf || typeof asOf !== 'string') return null;
  const quoteTime = Date.parse(asOf);
  if (!Number.isFinite(quoteTime) || now < quoteTime || now - quoteTime > 1_800_000) return null;
  const factor = factors[code];
  if (factor == null || !Number.isFinite(factor) || factor <= 0) return null;
  const converted = amount * factor;
  return Number.isFinite(converted) ? converted : null;
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

/**
 * The oldest verified quote used by the displayed account-native TRY total.
 * The API's top-level asOf describes CNY only; never show that timestamp for
 * an HKD/JPY/KRW/TWD-only portfolio. Null means no verified FX timestamp.
 */
export function getPortfolioTryQuoteAsOf(
  snapshot: PortfolioSnapshotResponse | null,
  fx: PortfolioDisplayFxRates | null,
  now = Date.now(),
): string | null {
  if (!snapshot || !Array.isArray(snapshot.accounts) ||
      snapshot.accountCount !== snapshot.accounts.length ||
      snapshot.fxStale || snapshot.accounts.length === 0) return null;

  let oldest: number | null = null;
  for (const account of snapshot.accounts) {
    if (account.fxStale || account.dataQuality === 'partial') return null;
    const code = String(account.baseCurrency || '').trim().toUpperCase();
    if (code === 'TRY') continue;
    if (toTryDisplayValue(account.totalEquity, code, fx, false, now) === null || !fx) return null;
    const key = code.toLowerCase();
    const timestamp = fx.pairStatus
      ? fx.pairAsOf?.[key]
      : (code === 'USD' || code === 'CNY') && fx.status === 'current' ? fx.asOf : null;
    if (typeof timestamp !== 'string') return null;
    const parsed = Date.parse(timestamp);
    if (!Number.isFinite(parsed) || parsed > now || now - parsed > 1_800_000) return null;
    oldest = oldest === null ? parsed : Math.min(oldest, parsed);
  }
  return oldest === null ? null : new Date(oldest).toISOString();
}
