import { describe, expect, it } from 'vitest';
import type { Bist100TechnicalReport } from './bist100TechnicalReport';
import { parseSixMarketEvidence, selectSevenMarketEvidence } from './sevenMarketEvidence';

const examples = [
  ['cn', '600519', '600519.SS', 'CNY'],
  ['hk', 'HK00700', '0700.HK', 'HKD'],
  ['us', 'AAPL', 'AAPL', 'USD'],
  ['jp', '7203.T', '7203.T', 'JPY'],
  ['kr', '005930.KS', '005930.KS', 'KRW'],
  ['tw', '2330.TW', '2330.TW', 'TWD'],
] as const;
function fixture() {
  return {
    scope: 'six_market_yahoo_fallback_one_symbol_each',
    as_of: '2026-11-15',
    source: 'Yahoo Finance',
    checked_markets: 6,
    analyzed_markets: 6,
    results: examples.map(([market, code, yahoo_symbol, currency_expected]) => ({
      market, code, yahoo_symbol, currency_expected,
      expected_last_session: '2026-11-13',
      last_bar_date: '2026-11-13',
      bars: 80, currency_observed: currency_expected,
      technical_score: 75, status: 'analyzed',
    })),
  };
}

describe('seven-market evidence is dated proof, not live coverage', () => {
  it('shows exactly seven market rows even when nothing is loaded', () => {
    const rows = selectSevenMarketEvidence(null, null);
    expect(rows.map(row => row.market)).toEqual(['tr', 'cn', 'hk', 'us', 'jp', 'kr', 'tw']);
    expect(rows.every(row => row.state === 'not_loaded')).toBe(true);
    expect(rows.every(row => row.checked === 0 && row.analyzed === 0)).toBe(true);
    expect(rows.filter(row => row.scope === 'one_sample_symbol')).toHaveLength(6);
  });

  it('parses six separate one-symbol historical successes without claiming 6 full markets', () => {
    const proof = parseSixMarketEvidence(fixture());
    const rows = selectSevenMarketEvidence(null, proof);
    expect(proof.analyzedMarkets).toBe(6);
    expect(rows.slice(1).map(row => row.ticker)).toEqual(examples.map(item => item[2]));
    expect(rows.slice(1).every(row =>
      row.state === 'historical_analyzed' && row.checked === 1 &&
      row.analyzed === 1 && row.scope === 'one_sample_symbol')).toBe(true);
    expect(rows[0].state).toBe('not_loaded');
    expect(rows[1].asOf).toBe('2026-11-15');
  });

  it('reflects actual BIST report counts, with distinct 100-stock scope', () => {
    const bist = {
      as_of: '2026-11-15', last_completed_session: '2026-11-13',
      checked: 100, analyzed: 97,
    } as Bist100TechnicalReport;
    const rows = selectSevenMarketEvidence(bist, parseSixMarketEvidence(fixture()));
    expect(rows[0]).toMatchObject({
      scope: 'bist100_constituents', checked: 100, analyzed: 97,
      state: 'historical_analyzed', lastSession: '2026-11-13',
    });
    expect(rows[1].checked).toBe(1);
  });

  it('shows a failed international sample rather than hiding the market', () => {
    const raw = fixture();
    raw.results[5].status = 'fetch_error';
    raw.analyzed_markets = 5;
    const proof = parseSixMarketEvidence(raw);
    const tw = selectSevenMarketEvidence(null, proof)[6];
    expect(tw).toMatchObject({ market: 'tw', analyzed: 0, checked: 1, state: 'historical_failed', sampleStatus: 'fetch_error' });
  });

  it('rejects wrong reported counters and missing market', () => {
    const wrong = fixture();
    wrong.analyzed_markets = 5;
    expect(() => parseSixMarketEvidence(wrong)).toThrow();
    const missing = fixture();
    missing.results.pop();
    expect(() => parseSixMarketEvidence(missing)).toThrow();
  });

  it('rejects duplicate markets and substituted market/ticker identities', () => {
    const dup = fixture();
    dup.results[1].market = 'cn';
    expect(() => parseSixMarketEvidence(dup)).toThrow();
    const forged = fixture();
    forged.results[2].yahoo_symbol = '0700.HK';
    expect(() => parseSixMarketEvidence(forged)).toThrow();
    const currency = fixture();
    currency.results[2].currency_observed = 'HKD';
    expect(() => parseSixMarketEvidence(currency)).toThrow();
  });

  it('rejects fake positive scores with insufficient/stale/unverified candles', () => {
    const shallow = fixture();
    shallow.results[1].bars = 1;
    expect(() => parseSixMarketEvidence(shallow)).toThrow();
    const stale = fixture();
    stale.results[4].last_bar_date = '2026-11-12';
    expect(() => parseSixMarketEvidence(stale)).toThrow();
    const missing = fixture();
    missing.results[0].technical_score = Number.NaN;
    expect(() => parseSixMarketEvidence(missing)).toThrow();
  });

  it('rejects future sessions, malformed dates and wrong scope', () => {
    const future = fixture();
    future.results[0].expected_last_session = '2026-11-16';
    future.results[0].last_bar_date = '2026-11-16';
    expect(() => parseSixMarketEvidence(future)).toThrow();
    const wrongDate = fixture();
    wrongDate.as_of = '2026-11-31';
    expect(() => parseSixMarketEvidence(wrongDate)).toThrow();
    const wrongScope = fixture();
    wrongScope.scope = 'all_stocks_fully_verified';
    expect(() => parseSixMarketEvidence(wrongScope)).toThrow();
  });

  it('does not mutate an imported historical report', () => {
    const original = fixture();
    const before = JSON.stringify(original);
    selectSevenMarketEvidence(null, parseSixMarketEvidence(original));
    expect(JSON.stringify(original)).toBe(before);
  });
});
