/** Defensive validation of a pre-generated, historical BIST100 technical report.
 * Neither the UI nor this module runs stock analysis or trading operations.
 */
const TICKER = /^[A-Z0-9]{4,6}\.IS$/;
const DATE = /^\d{4}-\d{2}-\d{2}$/;
const STATUS = new Set([
  'analyzed', 'not_imported', 'db_error', 'unverified_source',
  'invalid_data', 'insufficient_history', 'stale_price', 'analysis_error',
]);
const TREND = new Set([
  'Güçlü yükseliş', 'Yükseliş', 'Zayıf yükseliş', 'Yatay',
  'Zayıf düşüş', 'Düşüş', 'Güçlü düşüş',
]);
const SIGNAL = new Set([
  'Güçlü alım sinyali', 'Alım sinyali', 'Tut', 'İzle',
  'Satış sinyali', 'Güçlü satış sinyali',
]);

export type TechnicalRankedRow = {
  symbol: string;
  status: 'analyzed';
  rank: number;
  bars: number;
  last_bar_date: string;
  score: number;
  close_try: number;
  ma5_try: number;
  ma20_try: number;
  rsi12: number;
  macd_histogram: number;
  bias_ma5_pct: number;
  trend: string;
  technical_signal: string;
  chase_risk: boolean;
  eligible_for_watchlist: boolean;
};
export type Bist100TechnicalReport = {
  index: 'BIST100';
  mode: 'read_only_local_sqlite';
  as_of: string;
  last_completed_session: string;
  universe_total: 100;
  checked: number;
  remaining: number;
  analyzed: number;
  watchlist_eligible: number;
  status_counts: Record<string, number>;
  ranking: TechnicalRankedRow[];
};

const record = (v: unknown): v is Record<string, unknown> =>
  typeof v === 'object' && v !== null && !Array.isArray(v);

const validDate = (v: unknown): v is string => {
  if (typeof v !== 'string' || !DATE.test(v)) return false;
  const timestamp = new Date(v + 'T12:00:00Z');
  return !Number.isNaN(timestamp.valueOf()) && timestamp.toISOString().slice(0, 10) === v;
};

const count = (v: unknown): v is number =>
  typeof v === 'number' && Number.isSafeInteger(v) && v >= 0;

const finite = (v: unknown): v is number =>
  typeof v === 'number' && Number.isFinite(v);

function analyzedRow(value: unknown, session: string, expectedRank: number): TechnicalRankedRow {
  if (!record(value) || value.rank !== expectedRank || value.status !== 'analyzed' ||
      typeof value.symbol !== 'string' || !TICKER.test(value.symbol) ||
      value.symbol === 'XU100.IS' ||
      !count(value.bars) || value.bars < 60 ||
      !validDate(value.last_bar_date) || value.last_bar_date !== session ||
      !count(value.score) || value.score > 100 ||
      !finite(value.close_try) || value.close_try <= 0 ||
      !finite(value.ma5_try) || value.ma5_try <= 0 ||
      !finite(value.ma20_try) || value.ma20_try <= 0 ||
      !finite(value.rsi12) || value.rsi12 < 0 || value.rsi12 > 100 ||
      !finite(value.macd_histogram) || !finite(value.bias_ma5_pct) ||
      !TREND.has(String(value.trend)) || !SIGNAL.has(String(value.technical_signal)) ||
      typeof value.chase_risk !== 'boolean' ||
      typeof value.eligible_for_watchlist !== 'boolean' ||
      (value.chase_risk && value.eligible_for_watchlist) ||
      (value.bias_ma5_pct > 5.01 && !value.chase_risk) ||
      (value.bias_ma5_pct < 4.99 && value.chase_risk)) {
    throw new Error('Teknik analiz satırı, risk işareti veya sırası geçersiz.');
  }
  return {
    symbol: value.symbol, status: 'analyzed', rank: value.rank,
    bars: value.bars, last_bar_date: value.last_bar_date,
    score: value.score, close_try: value.close_try,
    ma5_try: value.ma5_try, ma20_try: value.ma20_try,
    rsi12: value.rsi12, macd_histogram: value.macd_histogram,
    bias_ma5_pct: value.bias_ma5_pct, trend: String(value.trend),
    technical_signal: String(value.technical_signal),
    chase_risk: value.chase_risk, eligible_for_watchlist: value.eligible_for_watchlist,
  };
}

export function parseBist100TechnicalReport(value: unknown): Bist100TechnicalReport {
  if (!record(value) || value.index !== 'BIST100' ||
      value.mode !== 'read_only_local_sqlite' || value.universe_total !== 100 ||
      !validDate(value.as_of) || !validDate(value.last_completed_session) ||
      // Quarter membership is checked by the authenticated server reader.
      // This browser parser checks date shape and internal consistency only;
      // a hard-coded Q4-2026 window would reject valid reviewed 2027 reports.
      value.last_completed_session >= value.as_of) {
    throw new Error('BIST100 teknik rapor kimliği veya tarihi geçersiz.');
  }
  if (!Array.isArray(value.results) || !Array.isArray(value.ranking) ||
      !count(value.checked) || value.checked < 1 || value.checked > 100 ||
      value.results.length !== value.checked ||
      !count(value.remaining) || value.remaining !== 100 - value.checked ||
      !count(value.analyzed) || value.analyzed !== value.ranking.length ||
      !count(value.watchlist_eligible) || value.watchlist_eligible > value.analyzed) {
    throw new Error('Kontrol edilen ve analiz edilen hisse sayıları uyuşmuyor.');
  }

  const session = value.last_completed_session;
  const seen = new Set<string>();
  const counts: Record<string, number> = {};
  const analyzed = new Map<string, Record<string, unknown>>();
  for (const row of value.results as unknown[]) {
    if (!record(row) || typeof row.symbol !== 'string' ||
        !TICKER.test(row.symbol) || row.symbol === 'XU100.IS' || seen.has(row.symbol) ||
        typeof row.status !== 'string' || !STATUS.has(row.status)) {
      throw new Error('Sonuçlarda geçersiz veya tekrar eden hisse var.');
    }
    seen.add(row.symbol);
    counts[row.status] = (counts[row.status] ?? 0) + 1;
    if (row.status === 'analyzed') analyzed.set(row.symbol, row);
  }
  const reportedCounts = value.status_counts;
  if (!record(reportedCounts) ||
      Object.keys(reportedCounts).length !== Object.keys(counts).length ||
      Object.keys(counts).some(k => reportedCounts[k] !== counts[k]) ||
      analyzed.size !== value.analyzed) {
    throw new Error('Teknik rapor özet sayıları uyuşmuyor.');
  }

  const ranking = value.ranking.map((r: unknown, i: number) => analyzedRow(r, session, i + 1));
  const expected = [...analyzed.values()].sort((a, b) =>
    Number(b.score) - Number(a.score) || String(a.symbol).localeCompare(String(b.symbol), 'en'));
  const fields: (keyof TechnicalRankedRow)[] = [
    'symbol', 'status', 'bars', 'last_bar_date', 'score',
    'close_try', 'ma5_try', 'ma20_try', 'rsi12', 'macd_histogram',
    'bias_ma5_pct', 'trend', 'technical_signal', 'chase_risk',
    'eligible_for_watchlist',
  ];
  if (ranking.length !== expected.length || ranking.some((row: TechnicalRankedRow, i: number) =>
      fields.some(field => row[field] !== expected[i]?.[field]))) {
    throw new Error('Puan sıralaması analiz edilen hisselerle uyuşmuyor.');
  }
  if (ranking.filter((row: TechnicalRankedRow) => row.eligible_for_watchlist).length !== value.watchlist_eligible) {
    throw new Error('İzleme listesi sayısı uyuşmuyor.');
  }
  return {
    index: 'BIST100', mode: 'read_only_local_sqlite',
    as_of: value.as_of, last_completed_session: session, universe_total: 100,
    checked: value.checked, remaining: value.remaining,
    analyzed: value.analyzed, watchlist_eligible: value.watchlist_eligible,
    status_counts: counts, ranking,
  };
}
