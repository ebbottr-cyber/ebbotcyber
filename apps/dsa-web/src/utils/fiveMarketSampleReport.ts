/**
 * Validate read-only ETRE four-market historical sample JSON before displaying it.
 * Only the browser reads local files; the input is NOT uploaded or executed.
 * Shape checks guard against contradictory "5/5" / per-market claims, but a
 * third-party JSON file is not cryptographically attested proof of price data.
 */
export const FOCUS_MARKETS = ['tr', 'us', 'de', 'hk'] as const;
export type FocusMarket = (typeof FOCUS_MARKETS)[number];
export const PER_MARKET_TARGET = 100;
export const MAX_SYMBOLS = FOCUS_MARKETS.length * PER_MARKET_TARGET;

export const MARKET_CURRENCIES: Record<FocusMarket, string> = {
  tr: 'TRY', us: 'USD', de: 'EUR', hk: 'HKD',
};

const MARKET_CODE: Record<FocusMarket, RegExp> = {
  tr: /^[A-Z]{4,5}\.IS$/,
  us: /^[A-Z]{1,5}(?:\.[A-Z])?$/,
  de: /^[A-Z][A-Z0-9]{0,7}\.DE$/,
  hk: /^HK\d{5}$/,
};

const CORE = ['THYAO.IS', 'AAPL', 'SAP.DE', 'HK00700'] as const;
const EXTRA = ['ASELS.IS', 'MSFT', 'SIE.DE', 'HK01810'] as const;

const SCOPES = new Set([
  'etre_four_market_core_historical_samples',
  'etre_four_market_expanded_historical_samples',
  'etre_four_market_custom_historical_symbols',
]);

export const SAMPLE_STATUSES = [
  'analyzed', 'unavailable', 'routing_mismatch', 'routing_error',
  'calendar_unavailable', 'fetch_error', 'no_data', 'invalid_data',
  'incomplete_or_future_data', 'insufficient_history', 'stale_price',
  'currency_unverified', 'currency_mismatch', 'analysis_error',
] as const;
export type SampleStatus = (typeof SAMPLE_STATUSES)[number];
export type SampleQuality = 'samples_passed' | 'partial' | 'samples_failed' | 'not_requested';

export type SampleResult = {
  market: FocusMarket;
  code: string;
  yahoo_symbol: string;
  currency_expected: string;
  status: SampleStatus;
  bars?: number;
  expected_last_session?: string;
  last_bar_date?: string;
  currency_observed?: string | null;
  technical_score?: number;
  error_type?: string;
};

export type MarketSampleSummary = {
  checked_symbols: number;
  analyzed_symbols: number;
  sample_status: SampleQuality;
  failure_status_counts: Record<string, number>;
  target_symbols: number;
  remaining_to_target: number;
};

export type FiveMarketSampleReport = {
  scope: string;
  source: 'Yahoo Finance';
  as_of: string;
  checked_symbols: number;
  analyzed_symbols: number;
  markets_checked: number;
  market_scope: FocusMarket[];
  target_symbols_per_market: number;
  target_symbols_total: number;
  remaining_to_target: number;
  results: SampleResult[];
  by_market: Record<FocusMarket, MarketSampleSummary>;
};

const isRecord = (v: unknown): v is Record<string, unknown> =>
  v !== null && typeof v === 'object' && !Array.isArray(v);

const validDate = (v: unknown): v is string =>
  typeof v === 'string' && /^\d{4}-\d{2}-\d{2}$/.test(v) &&
  !Number.isNaN(Date.parse(v + 'T12:00:00Z')) &&
  new Date(v + 'T12:00:00Z').toISOString().slice(0, 10) === v;

const nonnegativeInt = (v: unknown): v is number =>
  typeof v === 'number' && Number.isSafeInteger(v) && v >= 0;

const isMarket = (v: unknown): v is FocusMarket =>
  typeof v === 'string' && FOCUS_MARKETS.some(market => market === v);

const isStatus = (v: unknown): v is SampleStatus =>
  typeof v === 'string' && SAMPLE_STATUSES.some(status => status === v);

function expectedYahoo(market: FocusMarket, code: string): string {
  if (market === 'hk') {
    const digits = code.slice(2).replace(/^0+/, '') || '0';
    return digits.padStart(4, '0') + '.HK';
  }
  return code;
}

function parseResult(raw: unknown, asOf: string, seen: Set<string>): SampleResult {
  if (!isRecord(raw) || !isMarket(raw.market) || typeof raw.code !== 'string' ||
      !MARKET_CODE[raw.market].test(raw.code) || seen.has(raw.code) ||
      raw.yahoo_symbol !== expectedYahoo(raw.market, raw.code) ||
      raw.currency_expected !== MARKET_CURRENCIES[raw.market] ||
      !isStatus(raw.status)) {
    throw new Error('Geçersiz, tekrarlı veya başka piyasaya ait hisse kodu.');
  }
  seen.add(raw.code);

  const row: SampleResult = {
    market: raw.market,
    code: raw.code,
    yahoo_symbol: raw.yahoo_symbol,
    currency_expected: raw.currency_expected,
    status: raw.status,
  };
  if (raw.bars !== undefined) {
    if (!nonnegativeInt(raw.bars)) throw new Error('Geçersiz fiyat verisi sayısı.');
    row.bars = raw.bars;
  }
  for (const key of ['expected_last_session', 'last_bar_date'] as const) {
    const value = raw[key];
    if (value !== undefined) {
      if (!validDate(value) || value > asOf) throw new Error('Hatalı veya ileri tarihli seans.');
      row[key] = value;
    }
  }
  if (raw.currency_observed !== undefined) {
    if (raw.currency_observed !== null &&
        (typeof raw.currency_observed !== 'string' || !/^[A-Z]{3}$/.test(raw.currency_observed))) {
      throw new Error('Geçersiz para birimi.');
    }
    row.currency_observed = raw.currency_observed;
  }
  if (raw.technical_score !== undefined) {
    if (!nonnegativeInt(raw.technical_score) || raw.technical_score > 100) {
      throw new Error('Geçersiz teknik puan.');
    }
    row.technical_score = raw.technical_score;
  }
  if (raw.error_type !== undefined) {
    if (typeof raw.error_type !== 'string' || raw.error_type.length > 100) {
      throw new Error('Geçersiz hata türü.');
    }
    row.error_type = raw.error_type;
  }
  if (row.status === 'analyzed') {
    if (row.bars === undefined || row.bars < 60 ||
        !row.expected_last_session || row.last_bar_date !== row.expected_last_session ||
        row.currency_observed !== row.currency_expected ||
        row.technical_score === undefined) {
      throw new Error('Yetersiz veya doğrulanmamış veriyle başarı sonucu bildirilemez.');
    }
  } else if (row.technical_score !== undefined) {
    throw new Error('Başarısız hisse için teknik analiz puanı bildirilemez.');
  }
  if (row.expected_last_session && row.last_bar_date &&
      row.last_bar_date > row.expected_last_session) {
    throw new Error('Tamamlanmamış seansın fiyat verisi kabul edilemez.');
  }
  return row;
}

function exactKeys(actual: Record<string, unknown>, expected: readonly string[]): boolean {
  return Object.keys(actual).length === expected.length &&
    expected.every(key => Object.prototype.hasOwnProperty.call(actual, key));
}

export function parseFiveMarketSampleReport(input: unknown): FiveMarketSampleReport {
  if (!isRecord(input) || !SCOPES.has(String(input.scope)) ||
      input.source !== 'Yahoo Finance' || !validDate(input.as_of) ||
      !Array.isArray(input.results) || input.results.length < 1 ||
      input.results.length > MAX_SYMBOLS || !nonnegativeInt(input.checked_symbols) ||
      !nonnegativeInt(input.analyzed_symbols) || !nonnegativeInt(input.markets_checked) ||
      input.target_symbols_per_market !== PER_MARKET_TARGET ||
      input.target_symbols_total !== MAX_SYMBOLS ||
      !Array.isArray(input.market_scope) ||
      input.market_scope.length !== FOCUS_MARKETS.length ||
      !FOCUS_MARKETS.every((m, i) => (input.market_scope as unknown[])[i] === m) ||
      !isRecord(input.by_market)) {
    throw new Error('Dört piyasa raporunun kimliği veya biçimi geçersiz.');
  }

  const asOf = input.as_of;
  const scope = input.scope as string;
  const seen = new Set<string>();
  const results = input.results.map((r: unknown) => parseResult(r, asOf, seen));
  if (input.checked_symbols !== results.length ||
      input.analyzed_symbols !== results.filter(r => r.status === 'analyzed').length ||
      input.markets_checked !== new Set(results.map(r => r.market)).size ||
      input.remaining_to_target !== MAX_SYMBOLS - results.length ||
      FOCUS_MARKETS.some(m => results.filter(r => r.market === m).length > PER_MARKET_TARGET) ||
      !exactKeys(input.by_market, FOCUS_MARKETS)) {
    throw new Error('Özet sayıları hisse sonuçlarıyla uyuşmuyor.');
  }

  // The fixed sample sets must actually contain the documented market symbols.
  if (scope !== 'etre_four_market_custom_historical_symbols') {
    const expected = scope.includes('_expanded_') ? [...CORE, ...EXTRA] : [...CORE];
    if (results.length !== expected.length ||
        !expected.every(code => seen.has(code))) {
      throw new Error('Sabit örnek raporundaki hisse listesi uyuşmuyor.');
    }
  }

  const byMarket = {} as Record<FocusMarket, MarketSampleSummary>;
  for (const market of FOCUS_MARKETS) {
    const raw = input.by_market[market];
    const rows = results.filter(r => r.market === market);
    const passed = rows.filter(r => r.status === 'analyzed').length;
    const expectedStatus: SampleQuality = !rows.length ? 'not_requested'
      : passed === rows.length ? 'samples_passed'
      : passed ? 'partial' : 'samples_failed';
    const failures: Record<string, number> = {};
    for (const row of rows) {
      if (row.status !== 'analyzed') {
        failures[row.status] = (failures[row.status] ?? 0) + 1;
      }
    }
    if (!isRecord(raw) || raw.checked_symbols !== rows.length ||
        raw.analyzed_symbols !== passed || raw.sample_status !== expectedStatus ||
        raw.target_symbols !== PER_MARKET_TARGET ||
        raw.remaining_to_target !== PER_MARKET_TARGET - rows.length ||
        !isRecord(raw.failure_status_counts) ||
        !exactKeys(raw.failure_status_counts, Object.keys(failures)) ||
        Object.keys(failures).some(key => (raw.failure_status_counts as Record<string, unknown>)[key] !== failures[key])) {
      throw new Error('Piyasa bazında eksik veya çelişkili veri kalitesi sonucu.');
    }
    byMarket[market] = {
      checked_symbols: rows.length,
      analyzed_symbols: passed,
      sample_status: expectedStatus,
      failure_status_counts: failures,
      target_symbols: PER_MARKET_TARGET,
      remaining_to_target: PER_MARKET_TARGET - rows.length,
    };
  }
  return {
    scope, source: 'Yahoo Finance', as_of: asOf,
    checked_symbols: results.length,
    analyzed_symbols: results.filter(r => r.status === 'analyzed').length,
    markets_checked: input.markets_checked,
    market_scope: [...FOCUS_MARKETS],
    target_symbols_per_market: PER_MARKET_TARGET,
    target_symbols_total: MAX_SYMBOLS,
    remaining_to_target: MAX_SYMBOLS - results.length,
    results, by_market: byMarket,
  };
}
