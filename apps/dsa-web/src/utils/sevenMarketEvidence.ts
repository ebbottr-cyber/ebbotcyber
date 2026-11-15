/** Seven-market historical *evidence*, not live prices or exchange coverage.
 *
 * TR comes from an authenticated, already validated saved BIST100 technical
 * report; the six foreign markets use a user-selected, browser-local JSON
 * output of the one-symbol-per-market Yahoo fallback smoke test.
 *
 * Imported JSON is NOT independently attested as genuinely downloaded Yahoo
 * data. No market, stock order or other server-side action is triggered here.
 */
import type { Bist100TechnicalReport } from './bist100TechnicalReport';

export type MarketKey = 'tr' | 'cn' | 'hk' | 'us' | 'jp' | 'kr' | 'tw';
type SmokeMarket = Exclude<MarketKey, 'tr'>;
export type EvidenceState = 'not_loaded' | 'historical_analyzed' | 'historical_failed';
export type MarketEvidenceRow = {
  market: MarketKey;
  label: string;
  scope: 'bist100_constituents' | 'one_sample_symbol';
  state: EvidenceState;
  ticker: string | null;
  asOf: string | null;
  lastSession: string | null;
  lastBar: string | null;
  checked: number;
  analyzed: number;
  currency: string;
  sampleStatus: string | null;
};

type ProbeIdentity = { market: SmokeMarket; code: string; yahoo: string; currency: string; label: string };

// Exactly the inputs used by src.services.six_market_live_smoke.PROBES;
// these are representative examples, NOT the six exchanges' full universes.
const PROBES: readonly ProbeIdentity[] = [
  { market: 'cn', label: 'Çin', code: '600519', yahoo: '600519.SS', currency: 'CNY' },
  { market: 'hk', label: 'Hong Kong', code: 'HK00700', yahoo: '0700.HK', currency: 'HKD' },
  { market: 'us', label: 'ABD', code: 'AAPL', yahoo: 'AAPL', currency: 'USD' },
  { market: 'jp', label: 'Japonya', code: '7203.T', yahoo: '7203.T', currency: 'JPY' },
  { market: 'kr', label: 'Güney Kore', code: '005930.KS', yahoo: '005930.KS', currency: 'KRW' },
  { market: 'tw', label: 'Tayvan', code: '2330.TW', yahoo: '2330.TW', currency: 'TWD' },
];
const STATUS = new Set([
  'analyzed', 'unavailable', 'routing_mismatch', 'routing_error',
  'calendar_unavailable', 'fetch_error', 'no_data', 'invalid_data',
  'incomplete_or_future_data', 'insufficient_history', 'stale_price',
  'currency_unverified', 'currency_mismatch', 'analysis_error',
]);
const DATE = /^\d{4}-\d{2}-\d{2}$/;
const isRecord = (value: unknown): value is Record<string, unknown> =>
  typeof value === 'object' && value !== null && !Array.isArray(value);
const isDate = (value: unknown): value is string => {
  if (typeof value !== 'string' || !DATE.test(value)) return false;
  const parsed = new Date(value + 'T12:00:00Z');
  return !Number.isNaN(parsed.valueOf()) && parsed.toISOString().slice(0, 10) === value;
};
const count = (value: unknown): value is number =>
  typeof value === 'number' && Number.isSafeInteger(value) && value >= 0;

export type SmokeResult = {
  market: SmokeMarket;
  status: string;
  expected_last_session: string | null;
  last_bar_date: string | null;
  bars: number | null;
  technical_score: number | null;
};
export type SixMarketEvidence = {
  asOf: string;
  results: Readonly<Record<SmokeMarket, SmokeResult>>;
  analyzedMarkets: number;
};

/** Reject a spoofed success, duplicate markets, wrong example ticker and counters.
 * No verification of remote Yahoo provenance or real exchange calendar occurs.
 */
export function parseSixMarketEvidence(input: unknown): SixMarketEvidence {
  if (!isRecord(input) ||
      input.scope !== 'six_market_yahoo_fallback_one_symbol_each' ||
      input.source !== 'Yahoo Finance' || !isDate(input.as_of) ||
      input.checked_markets !== 6 || !Array.isArray(input.results) ||
      input.results.length !== 6 || !count(input.analyzed_markets)) {
    throw new Error('Altı piyasa örnek raporunun kimliği veya sayıları geçersiz.');
  }
  const asOf = input.as_of;
  const parsed = {} as Record<SmokeMarket, SmokeResult>;
  let analyzed = 0;
  for (const item of input.results as unknown[]) {
    if (!isRecord(item) || typeof item.market !== 'string') {
      throw new Error('Altı piyasa örnek kaydı geçersiz.');
    }
    const expected = PROBES.find(probe => probe.market === item.market);
    if (!expected || Object.hasOwn(parsed, expected.market) ||
        item.code !== expected.code || item.yahoo_symbol !== expected.yahoo ||
        item.currency_expected !== expected.currency ||
        typeof item.status !== 'string' || !STATUS.has(item.status)) {
      throw new Error('Örnek piyasa veya sembol kimliği uyuşmuyor.');
    }
    const session = item.expected_last_session;
    const lastBar = item.last_bar_date;
    const bars = item.bars;
    const technicalScore = item.technical_score;
    if ((session !== undefined && session !== null && !isDate(session)) ||
        (lastBar !== undefined && lastBar !== null && !isDate(lastBar)) ||
        (bars !== undefined && bars !== null && !count(bars)) ||
        (technicalScore !== undefined && technicalScore !== null &&
          (typeof technicalScore !== 'number' || !Number.isFinite(technicalScore) ||
           technicalScore < 0 || technicalScore > 100))) {
      throw new Error('Örnek analiz göstergeleri veya tarihleri geçersiz.');
    }
    if (session && (session >= asOf || (lastBar && lastBar > session))) {
      throw new Error('Örnek piyasa seans tarihi tutarsız.');
    }
    if (item.status === 'analyzed') {
      if (!isDate(session) || !isDate(lastBar) || lastBar !== session ||
          !count(bars) || bars < 60 ||
          typeof technicalScore !== 'number' || !Number.isFinite(technicalScore) ||
          technicalScore < 0 || technicalScore > 100 ||
          item.currency_observed !== expected.currency) {
        throw new Error('Doğrulanmamış örnek analiz başarılı gösterilemez.');
      }
      analyzed += 1;
    }
    parsed[expected.market] = {
      market: expected.market, status: item.status,
      expected_last_session: isDate(session) ? session : null,
      last_bar_date: isDate(lastBar) ? lastBar : null,
      bars: count(bars) ? bars : null,
      technical_score: typeof technicalScore === 'number' ? technicalScore : null,
    };
  }
  if (Object.keys(parsed).length !== 6 || analyzed !== input.analyzed_markets) {
    throw new Error('Örnek piyasa sayıları ve rapor özeti uyuşmuyor.');
  }
  return { asOf, results: parsed, analyzedMarkets: analyzed };
}

/** One row per market, always. No report means NO evidence, never success. */
export function selectSevenMarketEvidence(
  bist: Bist100TechnicalReport | null,
  six: SixMarketEvidence | null,
): MarketEvidenceRow[] {
  const tr: MarketEvidenceRow = {
    market: 'tr', label: 'Türkiye · BIST100',
    scope: 'bist100_constituents',
    state: bist ? (bist.analyzed > 0 ? 'historical_analyzed' : 'historical_failed') : 'not_loaded',
    ticker: null, asOf: bist?.as_of ?? null,
    lastSession: bist?.last_completed_session ?? null,
    lastBar: bist?.last_completed_session ?? null,
    checked: bist?.checked ?? 0, analyzed: bist?.analyzed ?? 0,
    currency: 'TRY', sampleStatus: null,
  };
  return [tr, ...PROBES.map(probe => {
    const item = six?.results[probe.market];
    return {
      market: probe.market, label: probe.label,
      scope: 'one_sample_symbol' as const,
      state: item ? (item.status === 'analyzed' ? 'historical_analyzed' : 'historical_failed') : 'not_loaded' as EvidenceState,
      ticker: probe.yahoo,
      asOf: six?.asOf ?? null,
      lastSession: item?.expected_last_session ?? null,
      lastBar: item?.last_bar_date ?? null,
      checked: item ? 1 : 0, analyzed: item?.status === 'analyzed' ? 1 : 0,
      currency: probe.currency,
      sampleStatus: item?.status ?? null,
    };
  })];
}
