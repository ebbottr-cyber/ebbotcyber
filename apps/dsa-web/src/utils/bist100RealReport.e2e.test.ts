/** One-time real GitHub Actions historical report integration verification.
 *
 * Must receive the actual public-price-derived 100-symbol JSON from the
 * BIST100 2026-11-15 Actions artifact. No synthetic substitute or test skip.
 * Runs only in the explicitly gated real-report CI job, not the ordinary UI
 * unit test job. No live orders, server writes or price downloads.
 */
import { createHash } from 'node:crypto';
import { readFileSync } from 'node:fs';
import { describe, expect, it } from 'vitest';
import { parseBist100TechnicalReport } from './bist100TechnicalReport';
import { selectBist100Ranking, type Bist100RankingViewOptions } from './bist100RankingView';

const EXPECTED_SHA256 = '42a0834b5633b9667979966acc847fde6f431fb8f57ced16c432161fb287b06a';
const inputPath = process.env.BIST100_REAL_REPORT_PATH;
if (!inputPath) {
  throw new Error('BIST100_REAL_REPORT_PATH not set: the verified historical GitHub artifact is mandatory');
}
const sourceBytes = readFileSync(inputPath);
const actualHash = createHash('sha256').update(sourceBytes).digest('hex');
if (actualHash !== EXPECTED_SHA256) {
  throw new Error('BIST100 real-report artifact hash mismatch: do not substitute a synthetic dataset');
}
const report = parseBist100TechnicalReport(JSON.parse(sourceBytes.toString('utf8')) as unknown);

const defaultView: Bist100RankingViewOptions = {
  symbolQuery: '', risk: 'all', minScore: 0, sort: 'rank',
};

describe('100-stock real BIST100 Yahoo history -> saved report -> UI view', () => {
  it('uses the exact previous GitHub artifact and verified historical session', () => {
    expect(actualHash).toBe(EXPECTED_SHA256);
    expect(report.as_of).toBe('2026-11-15');
    expect(report.last_completed_session).toBe('2026-11-13');
    expect(report.universe_total).toBe(100);
    expect(report.checked).toBe(100);
    expect(report.remaining).toBe(0);
    expect(report.analyzed).toBe(100);
    expect(report.watchlist_eligible).toBe(97);
    expect(report.status_counts).toEqual({ analyzed: 100 });
  });

  it('renders all 100 saved technical scores in original verified rank order', () => {
    const rows = selectBist100Ranking(report.ranking, defaultView);
    expect(rows).toHaveLength(100);
    expect(new Set(rows.map(row => row.symbol)).size).toBe(100);
    expect(rows.map(row => row.rank)).toEqual(Array.from({ length: 100 }, (_, i) => i + 1));
    expect(rows.slice(0, 5).map(row => [row.symbol, row.score])).toEqual([
      ['GARAN.IS', 81], ['TSKB.IS', 81], ['ALBRK.IS', 79],
      ['OTKAR.IS', 79], ['TAVHL.IS', 79],
    ]);
    expect(rows.every(row => Number.isFinite(row.rsi12) &&
      Number.isFinite(row.macd_histogram) && row.bars >= 60)).toBe(true);
  });

  it('shows the 97/3 actual MA5-distance split without producing a buy list', () => {
    const clear = selectBist100Ranking(report.ranking, { ...defaultView, risk: 'ma5-clear' });
    const warned = selectBist100Ranking(report.ranking, { ...defaultView, risk: 'chase-risk' });
    expect(clear).toHaveLength(97);
    expect(warned).toHaveLength(3);
    expect(clear.every(row => !row.chase_risk)).toBe(true);
    expect(warned.every(row => row.chase_risk)).toBe(true);
    expect(clear.length + warned.length).toBe(report.analyzed);
  });

  it('respects actual score filters and source ranking', () => {
    const eighty = selectBist100Ranking(report.ranking, { ...defaultView, minScore: 80 });
    expect(eighty.map(row => [row.symbol, row.score, row.rank])).toEqual([
      ['GARAN.IS', 81, 1], ['TSKB.IS', 81, 2],
    ]);
    const seventy = selectBist100Ranking(report.ranking, { ...defaultView, minScore: 70 });
    expect(seventy).toHaveLength(21);
    expect(seventy.every(row => row.score >= 70)).toBe(true);
  });

  it('can search the actual report and sort by RSI without changing official rank', () => {
    const thyao = selectBist100Ranking(report.ranking, { ...defaultView, symbolQuery: ' thyao ' });
    expect(thyao).toHaveLength(1);
    expect(thyao[0].symbol).toBe('THYAO.IS');
    const byRsi = selectBist100Ranking(report.ranking, { ...defaultView, sort: 'rsi' });
    expect(byRsi).toHaveLength(100);
    expect(byRsi[0].rsi12).toBeGreaterThanOrEqual(byRsi[1].rsi12);
    const original = report.ranking.find(row => row.symbol === byRsi[0].symbol);
    expect(byRsi[0].rank).toBe(original?.rank);
  });

  it('preserves the historical report and produces a clear empty-filter view', () => {
    const baseline = JSON.stringify(report);
    const none = selectBist100Ranking(report.ranking, {
      ...defaultView, symbolQuery: 'NOT-A-BIST-SYMBOL',
    });
    expect(none).toHaveLength(0);
    expect(JSON.stringify(report)).toBe(baseline);
    expect(report.analyzed).toBe(100);
  });
});
