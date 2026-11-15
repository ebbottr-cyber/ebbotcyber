import { describe, expect, it } from 'vitest';
import { parseBist100TechnicalReport } from './bist100TechnicalReport';

const analyzed = {
  symbol: 'THYAO.IS', status: 'analyzed', bars: 80,
  last_bar_date: '2026-11-13', score: 72,
  close_try: 100, ma5_try: 99, ma20_try: 97,
  rsi12: 60, macd_histogram: 1.23, bias_ma5_pct: 1.01,
  trend: 'Yükseliş', technical_signal: 'Alım sinyali',
  chase_risk: false, eligible_for_watchlist: true,
};

function fixture() {
  const ranking: Record<string, unknown>[] = [{ ...analyzed, rank: 1 }];
  const results: Record<string, unknown>[] = [
    { ...analyzed },
    { symbol: 'AKFYE.IS', status: 'not_imported' },
  ];
  return {
    index: 'BIST100', mode: 'read_only_local_sqlite', as_of: '2026-11-15',
    last_completed_session: '2026-11-13', universe_total: 100,
    checked: 2, remaining: 98, analyzed: 1, watchlist_eligible: 1,
    status_counts: { analyzed: 1, not_imported: 1 },
    ranking,
    results,
  };
}

type ReportFixture = ReturnType<typeof fixture>;

function mutate(fn: (report: ReportFixture) => void): ReportFixture {
  const report = fixture();
  fn(report);
  return report;
}

describe('BIST100 technical ranking JSON parser', () => {
  it('allows an honest partial local report without claiming 100/100 analyses', () => {
    const result = parseBist100TechnicalReport(fixture());
    expect(result.analyzed).toBe(1);
    expect(result.checked).toBe(2);
    expect(result.remaining).toBe(98);
    expect(result.ranking[0].score).toBe(72);
    expect(result.watchlist_eligible).toBe(1);
  });

  it.each([
    ['inflated counters', (r: ReportFixture) => { r.checked = 100; r.remaining = 0; }],
    ['future session', (r: ReportFixture) => { r.last_completed_session = '2026-11-16'; }],
    ['expired membership', (r: ReportFixture) => { r.as_of = '2027-01-01'; }],
    ['fabricated ranking', (r: ReportFixture) => { r.ranking[0].score = 100; }],
    ['invalid score', (r: ReportFixture) => { r.ranking[0].score = 101; r.results[0].score = 101; }],
    ['false watchlist risk', (r: ReportFixture) => {
      r.ranking[0].chase_risk = true; r.results[0].chase_risk = true;
    }],
    ['duplicate symbols', (r: ReportFixture) => { r.results[1].symbol = 'THYAO.IS'; }],
    ['unsupported benchmark', (r: ReportFixture) => { r.results[1].symbol = 'XU100.IS'; }],
    ['status totals mismatch', (r: ReportFixture) => { r.status_counts.analyzed = 2; }],
    ['wrong last bar', (r: ReportFixture) => {
      r.ranking[0].last_bar_date = '2026-11-12';
      r.results[0].last_bar_date = '2026-11-12';
    }],
  ] as const)('rejects %s', (_label, change) => {
    expect(() => parseBist100TechnicalReport(mutate(change))).toThrow();
  });

  it('does not accept fake AI or live trading modes', () => {
    const value = mutate(r => { r.mode = 'live_trade'; });
    expect(() => parseBist100TechnicalReport(value)).toThrow();
  });
});
