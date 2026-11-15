import { describe, expect, it } from 'vitest';
import type { TechnicalRankedRow } from './bist100TechnicalReport';
import { selectBist100Ranking, type Bist100RankingViewOptions } from './bist100RankingView';

const template: TechnicalRankedRow = {
  rank: 1, symbol: 'GARAN.IS', status: 'analyzed', bars: 200,
  last_bar_date: '2026-11-13', score: 81,
  close_try: 124.6, ma5_try: 120, ma20_try: 119,
  rsi12: 60, macd_histogram: 1.34, bias_ma5_pct: 3.83,
  trend: 'Yükseliş', technical_signal: 'Alım sinyali',
  chase_risk: false, eligible_for_watchlist: true,
};
const ranking: TechnicalRankedRow[] = [
  { ...template, rank: 1, symbol: 'GARAN.IS', score: 81, rsi12: 60 },
  { ...template, rank: 2, symbol: 'TSKB.IS', score: 81, rsi12: 72 },
  {
    ...template, rank: 3, symbol: 'OTKAR.IS', score: 79, rsi12: 48,
    chase_risk: true, eligible_for_watchlist: false, bias_ma5_pct: 8.12,
  },
  { ...template, rank: 4, symbol: 'AKBNK.IS', score: 78, rsi12: 55 },
];

const defaults: Bist100RankingViewOptions = {
  symbolQuery: '', risk: 'all', minScore: 0, sort: 'rank',
};

describe('BIST100 historical technical report view controls', () => {
  it('keeps validated official ranks in the default view', () => {
    const rows = selectBist100Ranking(ranking, defaults);
    expect(rows.map(r => r.symbol)).toEqual(ranking.map(r => r.symbol));
    expect(rows.map(r => r.rank)).toEqual([1, 2, 3, 4]);
    expect(rows).not.toBe(ranking);
  });

  it('searches symbols without losing the actual original rank', () => {
    const rows = selectBist100Ranking(ranking, { ...defaults, symbolQuery: '  akbnk ' });
    expect(rows.map(r => [r.symbol, r.rank])).toEqual([['AKBNK.IS', 4]]);
  });

  it('filters MA5 high-distance warning but does not invent investment eligibility', () => {
    const clear = selectBist100Ranking(ranking, { ...defaults, risk: 'ma5-clear' });
    expect(clear.map(r => r.symbol)).not.toContain('OTKAR.IS');
    const risk = selectBist100Ranking(ranking, { ...defaults, risk: 'chase-risk' });
    expect(risk.map(r => r.symbol)).toEqual(['OTKAR.IS']);
  });

  it('combines a score threshold with partial matching', () => {
    const rows = selectBist100Ranking(ranking, {
      ...defaults, symbolQuery: 'AR', minScore: 80,
    });
    expect(rows.map(r => r.symbol)).toEqual(['GARAN.IS']);
  });

  it('sorts by ticker or RSI without overwriting source ranking numbers', () => {
    const alphabetical = selectBist100Ranking(ranking, { ...defaults, sort: 'symbol' });
    expect(alphabetical.map(r => r.symbol)).toEqual(['AKBNK.IS', 'GARAN.IS', 'OTKAR.IS', 'TSKB.IS']);
    expect(alphabetical[0].rank).toBe(4);
    const byRsi = selectBist100Ranking(ranking, { ...defaults, sort: 'rsi' });
    expect(byRsi.map(r => r.symbol)).toEqual(['TSKB.IS', 'GARAN.IS', 'AKBNK.IS', 'OTKAR.IS']);
    expect(byRsi[0].rank).toBe(2);
  });

  it('does not mutate the original ranking or pretend there is a fresh dataset', () => {
    const before = JSON.stringify(ranking);
    selectBist100Ranking(ranking, { ...defaults, minScore: 95, risk: 'chase-risk' });
    expect(JSON.stringify(ranking)).toBe(before);
    expect(selectBist100Ranking([], defaults)).toEqual([]);
    expect(selectBist100Ranking(ranking, { ...defaults, symbolQuery: 'NOT-A-TICKER' })).toEqual([]);
  });

  it('handles invalid threshold defensively', () => {
    expect(selectBist100Ranking(ranking, { ...defaults, minScore: Number.NaN })).toHaveLength(4);
    expect(selectBist100Ranking(ranking, { ...defaults, minScore: 999 })).toHaveLength(0);
  });
});
