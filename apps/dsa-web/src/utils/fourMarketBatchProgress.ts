/**
 * Browser-side validation of the operator-generated, read-only --status JSON.
 *
 * This is a structural consistency check, not proof of Yahoo provenance.
 * Neither data fetching nor market orders are ever initiated by this module.
 */
import { FOUR_ACTIVE_MARKETS, type FourMarket } from './fourMarketScanPlan';

export type ProgressAction =
  | 'inspect_invalid_batches'
  | 'run_next_missing_batch'
  | 'review_or_retry_failed_batches'
  | 'all_samples_passed';

export type MarketBatchCount = {
  target_symbols: 100;
  checked_symbols: number;
  analyzed_symbols: number;
  failed_symbols: number;
  pending_symbols: number;
};

export type FailedBatchStock = {
  batch_index: number;
  market: FourMarket;
  code: string;
  status: string;
};

export type InvalidBatch = {
  batch_index: number;
  filename: string;
  reason: string;
};

export type FourMarketBatchProgress = {
  scope: 'etre_four_market_batch_progress';
  as_of: string;
  source_as_of: string;
  manifest_sha256: string;
  market_scope: FourMarket[];
  target_symbols_per_market: 100;
  target_symbols_total: 400;
  checked_symbols: number;
  analyzed_symbols: number;
  failed_symbols: number;
  pending_symbols: number;
  checked_all: boolean;
  all_analyzed: boolean;
  batch_size: number;
  batches_total: number;
  verified_batch_indices: number[];
  clean_batch_indices: number[];
  failed_batch_indices: number[];
  missing_batch_indices: number[];
  invalid_batches: InvalidBatch[];
  next_missing_batch_index: number | null;
  failed_rows: FailedBatchStock[];
  by_market: Record<FourMarket, MarketBatchCount>;
  next_action: ProgressAction;
  network_requests: 0;
};

const ACTIONS = new Set<ProgressAction>([
  'inspect_invalid_batches', 'run_next_missing_batch',
  'review_or_retry_failed_batches', 'all_samples_passed',
]);

const STOCK_PATTERNS: Record<FourMarket, RegExp> = {
  tr: /^[A-Z]{4,6}\.IS$/,
  us: /^[A-Z]{1,5}(?:\.[A-Z])?$/,
  de: /^[A-Z][A-Z0-9]{0,7}\.DE$/,
  hk: /^HK[0-9]{5}$/,
};
const RESULT_STATUSES = new Set([
  'unavailable', 'routing_mismatch', 'routing_error', 'calendar_unavailable',
  'fetch_error', 'no_data', 'invalid_data', 'incomplete_or_future_data',
  'insufficient_history', 'stale_price', 'currency_unverified',
  'currency_mismatch', 'analysis_error',
]);

function record(value: unknown): value is Record<string, unknown> {
  return value !== null && typeof value === 'object' && !Array.isArray(value);
}

function integer(value: unknown, low: number, high: number): value is number {
  return typeof value === 'number' && Number.isInteger(value)
    && value >= low && value <= high;
}

function isoDate(value: unknown): value is string {
  if (typeof value !== 'string' || !/^\d{4}-\d{2}-\d{2}$/.test(value)) return false;
  const d = new Date(value + 'T12:00:00Z');
  return !Number.isNaN(d.valueOf()) && d.toISOString().slice(0, 10) === value;
}

function ascendingIndices(value: unknown, max: number): number[] {
  if (!Array.isArray(value) || value.length > max) throw new Error('Invalid batch indices');
  let last = -1;
  const out: number[] = [];
  for (const n of value) {
    if (!integer(n, 0, max - 1) || n <= last) throw new Error('Unsorted or duplicate batch indices');
    out.push(n);
    last = n;
  }
  return out;
}

function expect(condition: unknown): asserts condition {
  if (!condition) throw new Error('Inconsistent or unsupported 400-stock progress report');
}

export function parseFourMarketBatchProgress(raw: unknown): FourMarketBatchProgress {
  expect(record(raw));
  expect(raw.scope === 'etre_four_market_batch_progress');
  expect(isoDate(raw.as_of) && isoDate(raw.source_as_of) && raw.source_as_of <= raw.as_of);
  expect(typeof raw.manifest_sha256 === 'string' && /^[a-f0-9]{64}$/.test(raw.manifest_sha256));
  expect(Array.isArray(raw.market_scope) && raw.market_scope.length === 4
    && FOUR_ACTIVE_MARKETS.every((market, index) => (raw.market_scope as unknown[])[index] === market));
  expect(raw.target_symbols_per_market === 100 && raw.target_symbols_total === 400);
  expect(integer(raw.batch_size, 1, 25));
  const size = raw.batch_size as number;
  const total = Math.ceil(400 / size);
  expect(raw.batches_total === total);
  expect(integer(raw.checked_symbols, 0, 400)
    && integer(raw.analyzed_symbols, 0, 400)
    && integer(raw.failed_symbols, 0, 400)
    && integer(raw.pending_symbols, 0, 400));
  expect(raw.network_requests === 0);
  expect(typeof raw.checked_all === 'boolean' && typeof raw.all_analyzed === 'boolean');
  expect(ACTIONS.has(raw.next_action as ProgressAction));

  const verified = ascendingIndices(raw.verified_batch_indices, total);
  const clean = ascendingIndices(raw.clean_batch_indices, total);
  const failed = ascendingIndices(raw.failed_batch_indices, total);
  const missing = ascendingIndices(raw.missing_batch_indices, total);
  const verifiedSet = new Set(verified);
  const cleanSet = new Set(clean);
  const failedSet = new Set(failed);
  const missingSet = new Set(missing);
  expect(verified.length === clean.length + failed.length);
  expect([...clean, ...failed].every(n => verifiedSet.has(n)));
  expect([...verified].every(n => cleanSet.has(n) !== failedSet.has(n)));

  expect(Array.isArray(raw.invalid_batches) && raw.invalid_batches.length <= total);
  const invalid: InvalidBatch[] = [];
  const invalidSet = new Set<number>();
  for (const item of raw.invalid_batches) {
    expect(record(item));
    expect(integer(item.batch_index, 0, total - 1) && !invalidSet.has(item.batch_index));
    const index = item.batch_index as number;
    expect(item.filename === 'batch-' + String(index + 1).padStart(3, '0')
      + '-of-' + String(total).padStart(3, '0') + '.json');
    expect(typeof item.reason === 'string' && item.reason.length > 0
      && item.reason.length <= 180);
    invalidSet.add(index);
    invalid.push({ batch_index: index, filename: item.filename as string,
      reason: item.reason as string });
  }
  // Each possible batch is exactly one of: verified, missing, invalid.
  expect(verified.length + missing.length + invalid.length === total);
  for (let index = 0; index < total; index++) {
    const numberOfCategories = Number(verifiedSet.has(index))
      + Number(missingSet.has(index)) + Number(invalidSet.has(index));
    expect(numberOfCategories === 1);
  }
  expect(raw.next_missing_batch_index === (missing[0] ?? null));

  const calculatedMarkets: Record<FourMarket, number> = { tr: 0, us: 0, de: 0, hk: 0 };
  for (const index of verified) {
    const first = index * size;
    const last = Math.min(400, first + size);
    for (const market of FOUR_ACTIVE_MARKETS) {
      const marketIndex = FOUR_ACTIVE_MARKETS.indexOf(market);
      const start = marketIndex * 100;
      calculatedMarkets[market] += Math.max(0, Math.min(last, start + 100) - Math.max(first, start));
    }
  }

  expect(record(raw.by_market));
  expect(Object.keys(raw.by_market).length === 4);
  const byMarket = {} as Record<FourMarket, MarketBatchCount>;
  for (const market of FOUR_ACTIVE_MARKETS) {
    const item = raw.by_market[market];
    expect(record(item));
    expect(integer(item.checked_symbols, 0, 100)
      && integer(item.analyzed_symbols, 0, 100)
      && integer(item.failed_symbols, 0, 100)
      && integer(item.pending_symbols, 0, 100));
    expect(item.target_symbols === 100 && item.checked_symbols === calculatedMarkets[market]);
    expect(item.checked_symbols === item.analyzed_symbols + item.failed_symbols);
    expect(item.pending_symbols === 100 - item.checked_symbols);
    byMarket[market] = {
      target_symbols: 100,
      checked_symbols: item.checked_symbols as number,
      analyzed_symbols: item.analyzed_symbols as number,
      failed_symbols: item.failed_symbols as number,
      pending_symbols: item.pending_symbols as number,
    };
  }
  const checked = FOUR_ACTIVE_MARKETS.reduce((sum, market) => sum + byMarket[market].checked_symbols, 0);
  const analyzed = FOUR_ACTIVE_MARKETS.reduce((sum, market) => sum + byMarket[market].analyzed_symbols, 0);
  expect(raw.checked_symbols === checked && raw.analyzed_symbols === analyzed);
  expect(raw.failed_symbols === checked - analyzed && raw.pending_symbols === 400 - checked);
  expect(raw.checked_all === (checked === 400));
  expect(raw.all_analyzed === (analyzed === 400 && checked === 400));

  expect(Array.isArray(raw.failed_rows) && raw.failed_rows.length === checked - analyzed);
  const rows: FailedBatchStock[] = [];
  const rowCounts: Record<FourMarket, number> = { tr: 0, us: 0, de: 0, hk: 0 };
  const seenCodes = new Set<string>();
  const batchHasFailures = new Set<number>();
  for (const item of raw.failed_rows) {
    expect(record(item));
    expect(integer(item.batch_index, 0, total - 1) && failedSet.has(item.batch_index));
    expect(typeof item.market === 'string' && FOUR_ACTIVE_MARKETS.some(m => m === item.market));
    const market = item.market as FourMarket;
    expect(typeof item.code === 'string' && STOCK_PATTERNS[market].test(item.code)
      && !seenCodes.has(item.code));
    expect(typeof item.status === 'string' && RESULT_STATUSES.has(item.status));
    const code = item.code as string;
    const batchIndex = item.batch_index as number;
    const start = batchIndex * size;
    const end = Math.min(400, start + size);
    const section = FOUR_ACTIVE_MARKETS.indexOf(market);
    expect(end > section * 100 && start < section * 100 + 100);
    seenCodes.add(code);
    batchHasFailures.add(batchIndex);
    rowCounts[market] += 1;
    rows.push({ batch_index: batchIndex, market, code, status: item.status as string });
  }
  for (const market of FOUR_ACTIVE_MARKETS) {
    expect(rowCounts[market] === byMarket[market].failed_symbols);
  }
  expect(failed.length === batchHasFailures.size);
  for (const index of failed) expect(batchHasFailures.has(index));

  const expectedAction: ProgressAction = invalid.length ? 'inspect_invalid_batches'
    : missing.length ? 'run_next_missing_batch'
      : failed.length ? 'review_or_retry_failed_batches' : 'all_samples_passed';
  expect(raw.next_action === expectedAction);

  return {
    scope: 'etre_four_market_batch_progress',
    as_of: raw.as_of as string,
    source_as_of: raw.source_as_of as string,
    manifest_sha256: raw.manifest_sha256 as string,
    market_scope: [...FOUR_ACTIVE_MARKETS],
    target_symbols_per_market: 100,
    target_symbols_total: 400,
    checked_symbols: checked,
    analyzed_symbols: analyzed,
    failed_symbols: checked - analyzed,
    pending_symbols: 400 - checked,
    checked_all: checked === 400,
    all_analyzed: checked === 400 && analyzed === 400,
    batch_size: size,
    batches_total: total,
    verified_batch_indices: verified,
    clean_batch_indices: clean,
    failed_batch_indices: failed,
    missing_batch_indices: missing,
    invalid_batches: invalid,
    next_missing_batch_index: missing[0] ?? null,
    failed_rows: rows,
    by_market: byMarket,
    next_action: expectedAction,
    network_requests: 0,
  };
}
