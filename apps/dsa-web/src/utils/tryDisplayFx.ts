import { formatMoney } from './portfolioFormat';

export type SupportedTrySourceCurrency = 'USD' | 'EUR' | 'CNY';

/**
 * Display-only daily indicative quote, normalized and verified by a trusted backend.
 * TCMB XML must be parsed server-side; this module never downloads or invents rates.
 */
export type TryRateEvidence = {
  source: 'TCMB';
  sourceCurrency: SupportedTrySourceCurrency;
  targetCurrency: 'TRY';
  asOfDate: string; // YYYY-MM-DD, publication date (Europe/Istanbul)
  sourceUnit: 1; // number of source currency units represented by tryPerUnit
  tryPerUnit: number;
};

export type TryDisplayResult = {
  text: string;
  mode: 'original' | 'native' | 'converted';
  convertedAmountTry: number | null;
  rateSource: 'TCMB' | null;
  rateDate: string | null;
};

const DAY_MS = 86_400_000;
export const MAX_TCMB_RATE_AGE_DAYS = 4;

/**
 * Fail closed: if the quote is absent, invalid, dated in the future, or stale,
 * retain the original currency label and amount. Never label it TRY.
 *
 * This is a presentation helper only. Do not use it for orders, position
 * accounting, PnL or strategy calculations.
 */
export function formatTryDisplay(
  amount: number | null | undefined,
  currency: string,
  quote?: TryRateEvidence | null,
  now: Date = new Date(),
): TryDisplayResult {
  const original = formatMoney(amount, currency);
  const fallback: TryDisplayResult = {
    text: original,
    mode: 'original',
    convertedAmountTry: null,
    rateSource: null,
    rateDate: null,
  };
  if (amount == null || !Number.isFinite(amount)) return fallback;
  if (currency === 'TRY') {
    return {
      text: original,
      mode: 'native',
      convertedAmountTry: amount,
      rateSource: null,
      rateDate: null,
    };
  }
  if (currency !== 'USD' && currency !== 'EUR' && currency !== 'CNY') return fallback;
  if (!quote || quote.source !== 'TCMB'
    || quote.targetCurrency !== 'TRY'
    || quote.sourceCurrency !== currency
    || quote.sourceUnit !== 1
    || !Number.isFinite(quote.tryPerUnit)
    || quote.tryPerUnit <= 0
    || !Number.isFinite(now.getTime())
    || !/^\d{4}-\d{2}-\d{2}$/.test(quote.asOfDate)) return fallback;

  const rateDayMs = Date.parse(`${quote.asOfDate}T00:00:00.000Z`);
  if (!Number.isFinite(rateDayMs)
    || new Date(rateDayMs).toISOString().slice(0, 10) !== quote.asOfDate) return fallback;

  const todayInIstanbul = new Intl.DateTimeFormat('en-CA', {
    timeZone: 'Europe/Istanbul',
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
  }).format(now);
  const ageDays = (Date.parse(`${todayInIstanbul}T00:00:00.000Z`) - rateDayMs) / DAY_MS;
  if (!Number.isFinite(ageDays) || ageDays < 0 || ageDays > MAX_TCMB_RATE_AGE_DAYS) return fallback;

  const converted = amount * quote.tryPerUnit;
  if (!Number.isFinite(converted)) return fallback;
  return {
    text: formatMoney(converted, 'TRY'),
    mode: 'converted',
    convertedAmountTry: converted,
    rateSource: 'TCMB',
    rateDate: quote.asOfDate,
  };
}
