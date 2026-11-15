/** Read-only validation for manually imported BIST100 Yahoo coverage JSON.
 * This is not the screening API: a data-ready quote is NOT an AI analysis.
 */
const TICKER = /^[A-Z]{4,6}\.IS$/;
const DATE = /^\d{4}-\d{2}-\d{2}$/;
const STATUS = new Set([
  'ready', 'fetch_error', 'no_data', 'invalid_data', 'no_completed_bars',
  'currency_mismatch', 'currency_unverified', 'calendar_unavailable',
  'stale_price', 'insufficient_history',
]);

export type Bist100CoverageRow = {
  symbol: string;
  status: string;
  rows: number;
  first_bar_date: string | null;
  last_bar_date: string | null;
  observed_currency: string | null;
  expected_last_session: string | null;
  issues: string[];
  error_type: string | null;
};

export type Bist100CoverageReport = {
  index: 'BIST100';
  as_of: string;
  source: 'Yahoo Finance';
  checked: number;
  remaining: number;
  complete: boolean;
  ready: number;
  with_valid_price_bars: number;
  universe_total: 100;
  currency_expected: 'TRY';
  calendar: 'XIST';
  timezone: 'Europe/Istanbul';
  status_counts: Record<string, number>;
  results: Bist100CoverageRow[];
};

const isRecord = (v: unknown): v is Record<string, unknown> =>
  typeof v === 'object' && v !== null && !Array.isArray(v);

const isDate = (v: unknown): v is string =>
  typeof v === 'string' && DATE.test(v) &&
  !Number.isNaN(Date.parse(v + 'T12:00:00Z')) &&
  new Date(v + 'T12:00:00Z').toISOString().slice(0, 10) === v;

const isOptionalDate = (v: unknown): v is string | null =>
  v === null || isDate(v);

const int = (v: unknown): v is number =>
  typeof v === 'number' && Number.isSafeInteger(v) && v >= 0;

const optionalString = (v: unknown): v is string | null =>
  v === null || typeof v === 'string';

export function parseBist100CoverageReport(value: unknown): Bist100CoverageReport {
  if (!isRecord(value)) throw new Error('Rapor JSON nesnesi olmalı.');
  const top = value;
  if (top.index !== 'BIST100' || top.source !== 'Yahoo Finance' ||
      top.currency_expected !== 'TRY' || top.calendar !== 'XIST' ||
      top.timezone !== 'Europe/Istanbul' || top.universe_total !== 100 ||
      !isDate(top.as_of)) {
    throw new Error('BIST100, Yahoo, TRY, XIST veya tarih bilgisi uyuşmuyor.');
  }
  if (!Array.isArray(top.results) || top.results.length > 100 ||
      !int(top.checked) || top.checked !== top.results.length ||
      !int(top.remaining) || top.remaining !== 100 - top.checked ||
      typeof top.complete !== 'boolean' || top.complete !== (top.checked === 100) ||
      !int(top.ready) || !int(top.with_valid_price_bars)) {
    throw new Error('Kontrol edilen hisse sayısı veya tamamlanma bilgisi geçersiz.');
  }
  const unique = new Set<string>();
  const rows: Bist100CoverageRow[] = top.results.map((item: unknown) => {
    if (!isRecord(item) || typeof item.symbol !== 'string' ||
        !TICKER.test(item.symbol) || unique.has(item.symbol) ||
        typeof item.status !== 'string' || !STATUS.has(item.status) ||
        !int(item.rows) || !isOptionalDate(item.first_bar_date) ||
        !isOptionalDate(item.last_bar_date) ||
        !optionalString(item.observed_currency) ||
        !isOptionalDate(item.expected_last_session) ||
        !optionalString(item.error_type) || !Array.isArray(item.issues) ||
        !item.issues.every((issue: unknown) => typeof issue === 'string')) {
      throw new Error('Hisse sonucu bozuk, geçersiz veya tekrarlı.');
    }
    unique.add(item.symbol);
    const bothDates = item.first_bar_date !== null && item.last_bar_date !== null;
    const neitherDate = item.first_bar_date === null && item.last_bar_date === null;
    if (item.rows > 0 ? !bothDates : !neitherDate) {
      throw new Error('Fiyat verisi sayısı ve tarihleri tutarsız.');
    }
    if (item.rows > 0) {
      const first = item.first_bar_date;
      const last = item.last_bar_date;
      if (!first || !last || first > last || last > top.as_of) {
        throw new Error('Fiyat verisi tarihleri tutarsız.');
      }
    }
    if (item.status === 'ready' && (item.rows === 0 ||
        item.observed_currency !== 'TRY' || item.expected_last_session !== item.last_bar_date ||
        item.issues.length !== 0)) {
      throw new Error('Veri kalitesi doğrulanmadan hazır sonucu verilemez.');
    }
    return {
      symbol: item.symbol, status: item.status, rows: item.rows,
      first_bar_date: item.first_bar_date, last_bar_date: item.last_bar_date,
      observed_currency: item.observed_currency,
      expected_last_session: item.expected_last_session,
      issues: item.issues as string[], error_type: item.error_type,
    };
  });
  const tally: Record<string, number> = {};
  for (const item of rows) tally[item.status] = (tally[item.status] ?? 0) + 1;
  if (!isRecord(top.status_counts) ||
      Object.keys(top.status_counts).length !== Object.keys(tally).length ||
      Object.keys(tally).some(key => top.status_counts[key] !== tally[key]) ||
      top.ready !== (tally.ready ?? 0) ||
      top.with_valid_price_bars !== rows.filter(row => row.rows > 0).length) {
    throw new Error('Rapordaki özet sayıları hisse sonuçlarıyla uyuşmuyor.');
  }
  return {
    index: 'BIST100', as_of: top.as_of, source: 'Yahoo Finance',
    checked: top.checked, remaining: top.remaining, complete: top.complete,
    ready: top.ready, with_valid_price_bars: top.with_valid_price_bars,
    universe_total: 100, currency_expected: 'TRY',
    calendar: 'XIST', timezone: 'Europe/Istanbul',
    status_counts: tally, results: rows,
  };
}
