import { describe, expect, it } from 'vitest';
import { parseBist100CoverageReport } from './bist100CoverageReport';

const goodRow = {
  symbol: 'THYAO.IS', status: 'ready', rows: 75,
  first_bar_date: '2026-08-01', last_bar_date: '2026-11-13',
  observed_currency: 'TRY', expected_last_session: '2026-11-13',
  issues: [], error_type: null,
};

const missingRow = {
  symbol: 'AKFYE.IS', status: 'no_data', rows: 0,
  first_bar_date: null, last_bar_date: null,
  observed_currency: null, expected_last_session: '2026-11-13',
  issues: [], error_type: null,
};

function report() {
  return {
    index: 'BIST100', as_of: '2026-11-15',
    expected_last_completed_session: '2026-11-13',
    source: 'Yahoo Finance', currency_expected: 'TRY',
    calendar: 'XIST', timezone: 'Europe/Istanbul',
    universe_total: 100, checked: 2, remaining: 98, complete: false,
    ready: 1, with_valid_price_bars: 1,
    status_counts: { ready: 1, no_data: 1 },
    results: [{ ...goodRow }, { ...missingRow }],
  };
}

describe('BIST100 coverage JSON import validation', () => {
  it('recognizes a legitimate incomplete 2/100 report without claiming analyses', () => {
    const parsed = parseBist100CoverageReport(report());
    expect(parsed.checked).toBe(2);
    expect(parsed.remaining).toBe(98);
    expect(parsed.complete).toBe(false);
    expect(parsed.ready).toBe(1);
  });

  it('rejects fabricated 100/100 totals and duplicate symbols', () => {
    const inflated = report();
    inflated.checked = 100;
    inflated.remaining = 0;
    inflated.complete = true;
    expect(() => parseBist100CoverageReport(inflated)).toThrow();
    const duplicate = report();
    duplicate.results[1] = { ...missingRow, symbol: 'THYAO.IS' };
    expect(() => parseBist100CoverageReport(duplicate)).toThrow();
  });

  it('rejects summary/status mismatch and false ready currency', () => {
    const mismatch = report();
    mismatch.ready = 2;
    expect(() => parseBist100CoverageReport(mismatch)).toThrow();
    const falseReady = report();
    falseReady.results[0] = { ...goodRow, observed_currency: 'USD' };
    expect(() => parseBist100CoverageReport(falseReady)).toThrow();
  });

  it('rejects a benchmark as the 101st stock or a foreign code', () => {
    const index = report();
    index.results[0] = { ...goodRow, symbol: 'XU100.IS' };
    expect(() => parseBist100CoverageReport(index)).toThrow();
    const foreign = report();
    foreign.results[0] = { ...goodRow, symbol: 'AAPL' };
    expect(() => parseBist100CoverageReport(foreign)).toThrow();
  });

  it('rejects contradictory top-level and row session metadata', () => {
    const mismatch = report();
    mismatch.expected_last_completed_session = '2026-11-12';
    expect(() => parseBist100CoverageReport(mismatch)).toThrow();
  });

  it('rejects an impossible future completed session', () => {
    const future = report();
    future.expected_last_completed_session = '2026-11-16';
    future.results[0].expected_last_session = '2026-11-16';
    future.results[1].expected_last_session = '2026-11-16';
    expect(() => parseBist100CoverageReport(future)).toThrow();
  });

  it('allows unverified diagnostic coverage but never calls it ready', () => {
    const unavailable = report();
    unavailable.expected_last_completed_session = null as unknown as string;
    unavailable.results = unavailable.results.map(row => ({
      ...row, status: 'calendar_unavailable', expected_last_session: null,
      issues: ['calendar_unavailable'],
    })) as typeof unavailable.results;
    unavailable.ready = 0;
    unavailable.status_counts = { ready: 0, no_data: 0, calendar_unavailable: 2 };
    delete (unavailable.status_counts as Record<string, number>).ready;
    delete (unavailable.status_counts as Record<string, number>).no_data;
    const parsed = parseBist100CoverageReport(unavailable);
    expect(parsed.ready).toBe(0);
    expect(parsed.expected_last_completed_session).toBeNull();
  });

  it('rejects missing source or inconsistent candle counts', () => {
    const unknownSource = report();
    unknownSource.source = 'Unverified';
    expect(() => parseBist100CoverageReport(unknownSource)).toThrow();
    const noBarDates = report();
    const malformed = { ...goodRow, last_bar_date: null };
    expect(() => parseBist100CoverageReport({
      ...noBarDates, results: [malformed, ...noBarDates.results.slice(1)],
    })).toThrow();
  });
});
