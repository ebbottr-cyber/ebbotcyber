import { describe, expect, it } from 'vitest';
import {
  FOCUS_MARKETS, MARKET_CURRENCIES, parseFiveMarketSampleReport,
  type FocusMarket,
  type SampleResult,
} from './fiveMarketSampleReport';

const SAMPLES = [
  ['tr', 'THYAO.IS', 'THYAO.IS'],
  ['us', 'AAPL', 'AAPL'],
  ['de', 'SAP.DE', 'SAP.DE'],
  ['hk', 'HK00700', '0700.HK'],
  ['jp', '7203.T', '7203.T'],
] as const;
const EXTRA = [
  ['tr', 'ASELS.IS', 'ASELS.IS'],
  ['us', 'MSFT', 'MSFT'],
  ['de', 'SIE.DE', 'SIE.DE'],
  ['hk', 'HK01810', '1810.HK'],
  ['jp', '6758.T', '6758.T'],
] as const;

function makeRow(market: FocusMarket, code: string, yahoo: string): SampleResult {
  return {
    market, code, yahoo_symbol: yahoo,
    currency_expected: MARKET_CURRENCIES[market],
    currency_observed: MARKET_CURRENCIES[market],
    status: 'analyzed', bars: 80,
    expected_last_session: '2026-11-13',
    last_bar_date: '2026-11-13',
    technical_score: 75,
  };
}

function report(kind: 'core' | 'expanded' | 'custom' = 'core') {
  const items = kind === 'expanded' ? [...SAMPLES, ...EXTRA] : SAMPLES;
  const results = items.map(([market, code, yahoo]) => makeRow(market, code, yahoo));
  return fromRows(results, kind);
}

function fromRows(results: SampleResult[], kind: 'core' | 'expanded' | 'custom' = 'custom') {
  const names = {
    core: 'etre_five_market_core_historical_samples',
    expanded: 'etre_five_market_expanded_historical_samples',
    custom: 'etre_five_market_custom_historical_symbols',
  };
  const by_market = Object.fromEntries(FOCUS_MARKETS.map(market => {
    const subset = results.filter(r => r.market === market);
    const passed = subset.filter(r => r.status === 'analyzed').length;
    const failureCounts: Record<string, number> = {};
    subset.forEach(r => {
      if (r.status !== 'analyzed') failureCounts[r.status] = (failureCounts[r.status] ?? 0) + 1;
    });
    const sample_status = !subset.length ? 'not_requested'
      : passed === subset.length ? 'samples_passed'
      : passed ? 'partial' : 'samples_failed';
    return [market, {
      checked_symbols: subset.length,
      analyzed_symbols: passed,
      sample_status,
      failure_status_counts: failureCounts,
    }];
  }));
  return {
    scope: names[kind], source: 'Yahoo Finance',
    as_of: '2026-11-15',
    checked_symbols: results.length,
    analyzed_symbols: results.filter(r => r.status === 'analyzed').length,
    markets_checked: new Set(results.map(r => r.market)).size,
    market_scope: [...FOCUS_MARKETS],
    results,
    by_market,
  };
}

describe('ETRE five-market local JSON validation', () => {
  it('accepts each of the five selected markets without implying exchange coverage', () => {
    const parsed = parseFiveMarketSampleReport(report());
    expect(parsed.checked_symbols).toBe(5);
    expect(parsed.analyzed_symbols).toBe(5);
    expect(parsed.markets_checked).toBe(5);
    expect(parsed.results.map(x => x.code)).toEqual(SAMPLES.map(x => x[1]));
    expect(parsed.by_market.de.sample_status).toBe('samples_passed');
  });

  it('accepts ten samples, still representing only five markets', () => {
    const parsed = parseFiveMarketSampleReport(report('expanded'));
    expect(parsed.checked_symbols).toBe(10);
    expect(parsed.markets_checked).toBe(5);
    expect(parsed.by_market.tr.checked_symbols).toBe(2);
  });

  it('accepts partial custom scope but labels untouched markets not requested', () => {
    const parsed = parseFiveMarketSampleReport(
      fromRows([makeRow('de', 'BMW.DE', 'BMW.DE')]),
    );
    expect(parsed.checked_symbols).toBe(1);
    expect(parsed.markets_checked).toBe(1);
    expect(parsed.by_market.de.sample_status).toBe('samples_passed');
    expect(parsed.by_market.tr.sample_status).toBe('not_requested');
  });

  it('rejects inflated headline numbers, unknown and removed markets', () => {
    const inflated = report();
    inflated.analyzed_symbols = 8;
    expect(() => parseFiveMarketSampleReport(inflated)).toThrow();

    const removed = report();
    removed.results[0] = { ...removed.results[0], market: 'cn' as FocusMarket };
    expect(() => parseFiveMarketSampleReport(removed)).toThrow();
  });

  it('rejects a fixed five-market report with substituted symbols or duplicates', () => {
    const substituted = report();
    substituted.results[0] = makeRow('tr', 'ASELS.IS', 'ASELS.IS');
    expect(() => parseFiveMarketSampleReport(substituted)).toThrow();

    const duplicate = report();
    duplicate.results[1] = { ...duplicate.results[0] };
    expect(() => parseFiveMarketSampleReport(duplicate)).toThrow();
  });

  it('refuses an analyzed result with wrong currency or stale dates', () => {
    const currency = report();
    currency.results[2] = { ...currency.results[2], currency_observed: 'USD' };
    expect(() => parseFiveMarketSampleReport(currency)).toThrow();

    const stale = report();
    stale.results[2] = { ...stale.results[2], last_bar_date: '2026-11-12' };
    expect(() => parseFiveMarketSampleReport(stale)).toThrow();
  });

  it('accepts partial sample results only when market tallies agree', () => {
    const broken = makeRow('de', 'BMW.DE', 'BMW.DE');
    broken.status = 'stale_price';
    delete broken.technical_score;
    broken.last_bar_date = '2026-11-12';
    const valid = fromRows([makeRow('de', 'SAP.DE', 'SAP.DE'), broken]);
    expect(parseFiveMarketSampleReport(valid).by_market.de.sample_status).toBe('partial');
    valid.by_market.de.sample_status = 'samples_passed';
    expect(() => parseFiveMarketSampleReport(valid)).toThrow();
  });

  it('rejects future dates and missing currency for a purported success', () => {
    const future = report();
    future.results[0] = { ...future.results[0], last_bar_date: '2027-01-01' };
    expect(() => parseFiveMarketSampleReport(future)).toThrow();
    const missing = report();
    missing.results[0] = { ...missing.results[0], currency_observed: null };
    expect(() => parseFiveMarketSampleReport(missing)).toThrow();
  });
});
