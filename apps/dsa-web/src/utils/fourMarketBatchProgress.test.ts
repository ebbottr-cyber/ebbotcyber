import { describe, expect, it } from 'vitest';
import {
  parseFourMarketBatchProgress,
  type FourMarketBatchProgress,
} from './fourMarketBatchProgress';

type RawReport = Record<string, unknown>;
const DIGEST = 'a'.repeat(64);
const MARKETS = ['tr', 'us', 'de', 'hk'] as const;
const byMarket = (tr = 0, us = 0, de = 0, hk = 0, fails = { tr: 0, us: 0, de: 0, hk: 0 }) =>
  Object.fromEntries(MARKETS.map((market, index) => {
    const checked = [tr, us, de, hk][index];
    const failed = fails[market];
    return [market, {
      target_symbols: 100,
      checked_symbols: checked,
      analyzed_symbols: checked - failed,
      failed_symbols: failed,
      pending_symbols: 100 - checked,
    }];
  }));

function emptyReport(size = 10): RawReport {
  const total = Math.ceil(400 / size);
  return {
    scope: 'etre_four_market_batch_progress',
    as_of: '2026-11-16',
    source_as_of: '2026-11-16',
    manifest_sha256: DIGEST,
    market_scope: [...MARKETS],
    target_symbols_per_market: 100,
    target_symbols_total: 400,
    checked_symbols: 0,
    analyzed_symbols: 0,
    failed_symbols: 0,
    pending_symbols: 400,
    checked_all: false,
    all_analyzed: false,
    batch_size: size,
    batches_total: total,
    verified_batch_indices: [],
    clean_batch_indices: [],
    failed_batch_indices: [],
    missing_batch_indices: Array.from({ length: total }, (_, index) => index),
    invalid_batches: [],
    next_missing_batch_index: 0,
    failed_rows: [],
    by_market: byMarket(),
    next_action: 'run_next_missing_batch',
    network_requests: 0,
  };
}

function partial(): RawReport {
  const raw = emptyReport();
  raw.verified_batch_indices = [0, 1];
  raw.clean_batch_indices = [0];
  raw.failed_batch_indices = [1];
  raw.missing_batch_indices = Array.from({ length: 38 }, (_, i) => i + 2);
  raw.next_missing_batch_index = 2;
  raw.checked_symbols = 20;
  raw.analyzed_symbols = 19;
  raw.failed_symbols = 1;
  raw.pending_symbols = 380;
  raw.by_market = byMarket(20, 0, 0, 0, { tr: 1, us: 0, de: 0, hk: 0 });
  raw.failed_rows = [{ batch_index: 1, market: 'tr', code: 'THYAO.IS', status: 'fetch_error' }];
  return raw;
}

describe('ETRE offline four-market progress report checks', () => {
  it('shows 0/400 as pending when no valid batch exists', () => {
    const report = parseFourMarketBatchProgress(emptyReport());
    expect(report.checked_symbols).toBe(0);
    expect(report.analyzed_symbols).toBe(0);
    expect(report.pending_symbols).toBe(400);
    expect(report.next_missing_batch_index).toBe(0);
    expect(report.all_analyzed).toBe(false);
  });

  it('shows failed stock separately from 380 unprocessed stocks', () => {
    const report = parseFourMarketBatchProgress(partial());
    expect(report.checked_symbols).toBe(20);
    expect(report.analyzed_symbols).toBe(19);
    expect(report.failed_symbols).toBe(1);
    expect(report.pending_symbols).toBe(380);
    expect(report.by_market.tr.failed_symbols).toBe(1);
    expect(report.by_market.jp).toBeUndefined();
    expect(report.failed_rows[0]).toEqual({
      batch_index: 1, market: 'tr', code: 'THYAO.IS', status: 'fetch_error',
    });
    expect(report.next_action).toBe('run_next_missing_batch');
  });

  it('treats corrupt batch as pending and never counts its symbols', () => {
    const raw = emptyReport();
    raw.invalid_batches = [{
      batch_index: 0, filename: 'batch-001-of-040.json', reason: 'Invalid counters',
    }];
    raw.missing_batch_indices = Array.from({ length: 39 }, (_, i) => i + 1);
    raw.next_missing_batch_index = 1;
    raw.next_action = 'inspect_invalid_batches';
    const result = parseFourMarketBatchProgress(raw);
    expect(result.invalid_batches).toHaveLength(1);
    expect(result.checked_symbols).toBe(0);
    expect(result.pending_symbols).toBe(400);
  });

  it('accepts full 400 only when every batch and market passed', () => {
    const raw = emptyReport();
    raw.verified_batch_indices = Array.from({ length: 40 }, (_, i) => i);
    raw.clean_batch_indices = raw.verified_batch_indices;
    raw.missing_batch_indices = [];
    raw.next_missing_batch_index = null;
    raw.checked_symbols = 400;
    raw.analyzed_symbols = 400;
    raw.pending_symbols = 0;
    raw.checked_all = true;
    raw.all_analyzed = true;
    raw.by_market = byMarket(100, 100, 100, 100);
    raw.next_action = 'all_samples_passed';
    const result = parseFourMarketBatchProgress(raw);
    expect(result.checked_all).toBe(true);
    expect(result.all_analyzed).toBe(true);
    expect(result.verified_batch_indices).toHaveLength(40);
    expect(result.network_requests).toBe(0);
  });

  it('does not mark 400 checked with one failure as 400 analyzed', () => {
    const raw = emptyReport();
    const all = Array.from({ length: 40 }, (_, i) => i);
    raw.verified_batch_indices = all;
    raw.clean_batch_indices = all.slice(1);
    raw.failed_batch_indices = [0];
    raw.missing_batch_indices = [];
    raw.next_missing_batch_index = null;
    raw.checked_symbols = 400;
    raw.analyzed_symbols = 399;
    raw.failed_symbols = 1;
    raw.pending_symbols = 0;
    raw.checked_all = true;
    raw.all_analyzed = false;
    raw.by_market = byMarket(100, 100, 100, 100, { tr: 1, us: 0, de: 0, hk: 0 });
    raw.failed_rows = [{ batch_index: 0, market: 'tr', code: 'ASELS.IS', status: 'stale_price' }];
    raw.next_action = 'review_or_retry_failed_batches';
    const result = parseFourMarketBatchProgress(raw);
    expect(result.checked_all).toBe(true);
    expect(result.all_analyzed).toBe(false);
    raw.all_analyzed = true;
    expect(() => parseFourMarketBatchProgress(raw)).toThrow();
  });

  it('recomputes market coverage even if a batch crosses the 100-market boundary', () => {
    const raw = emptyReport(17);
    raw.verified_batch_indices = [5];
    raw.clean_batch_indices = [5];
    raw.missing_batch_indices = (raw.missing_batch_indices as number[]).filter(n => n !== 5);
    raw.checked_symbols = 17;
    raw.analyzed_symbols = 17;
    raw.pending_symbols = 383;
    raw.by_market = byMarket(15, 2, 0, 0);
    const result = parseFourMarketBatchProgress(raw);
    expect(result.by_market.tr.checked_symbols).toBe(15);
    expect(result.by_market.us.checked_symbols).toBe(2);
  });

  it('rejects fake market and success counters, removed Japan, and omitted failures', () => {
    const inflated = partial();
    inflated.analyzed_symbols = 20;
    expect(() => parseFourMarketBatchProgress(inflated)).toThrow();

    const extra = partial();
    (extra.by_market as Record<string, unknown>).jp = { checked_symbols: 100 };
    expect(() => parseFourMarketBatchProgress(extra)).toThrow();

    const fabricated = partial();
    fabricated.failed_rows = [];
    expect(() => parseFourMarketBatchProgress(fabricated)).toThrow();

    const pending = partial();
    pending.next_missing_batch_index = 99;
    expect(() => parseFourMarketBatchProgress(pending)).toThrow();
  });

  it('rejects overlapping, missing, duplicate, or out of range batch identities', () => {
    const duplicated = partial();
    duplicated.verified_batch_indices = [0, 0, 1];
    expect(() => parseFourMarketBatchProgress(duplicated)).toThrow();

    const overlapped = partial();
    overlapped.missing_batch_indices = Array.from({ length: 39 }, (_, i) => i + 1);
    expect(() => parseFourMarketBatchProgress(overlapped)).toThrow();

    const bad = partial();
    bad.failed_batch_indices = [40];
    expect(() => parseFourMarketBatchProgress(bad)).toThrow();

    const notPartitioned = partial();
    notPartitioned.clean_batch_indices = [];
    expect(() => parseFourMarketBatchProgress(notPartitioned)).toThrow();
  });

  it('rejects unsupported origin, arbitrary network count, wrong files, or invalid dates', () => {
    const old = partial();
    old.market_scope = ['tr', 'us', 'de', 'jp'];
    expect(() => parseFourMarketBatchProgress(old)).toThrow();

    const suspicious = partial();
    suspicious.network_requests = 200;
    expect(() => parseFourMarketBatchProgress(suspicious)).toThrow();

    const invalid = partial();
    invalid.as_of = '2026-11-31';
    expect(() => parseFourMarketBatchProgress(invalid)).toThrow();

    const missing = partial();
    missing.manifest_sha256 = 'xyz';
    expect(() => parseFourMarketBatchProgress(missing)).toThrow();
  });

  it('normalizes the trusted result rather than passing through supplied extra fields', () => {
    const raw = partial();
    raw.credentials = 'should-not-render';
    (raw.failed_rows as Record<string, unknown>[])[0].unexpected = 'x';
    const parsed: FourMarketBatchProgress = parseFourMarketBatchProgress(raw);
    expect('credentials' in parsed).toBe(false);
    expect('unexpected' in parsed.failed_rows[0]).toBe(false);
  });
});
