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
] as const;
const EXTRA = [
  ['tr', 'ASELS.IS', 'ASELS.IS'],
  ['us', 'MSFT', 'MSFT'],
  ['de', 'SIE.DE', 'SIE.DE'],
  ['hk', 'HK01810', '1810.HK'],
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
    core: 'etre_four_market_core_historical_samples',
    expanded: 'etre_four_market_expanded_historical_samples',
    custom: 'etre_four_market_custom_historical_symbols',
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
      target_symbols: 100,
      remaining_to_target: 100 - subset.length,
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
    target_symbols_per_market: 100,
    target_symbols_total: 400,
    remaining_to_target: 400 - results.length,
    results,
    by_market,
  };
}

describe('ETRE four-market local JSON validation', () => {
  it('accepts each of the four selected markets without implying exchange coverage', () => {
    const parsed = parseFiveMarketSampleReport(report());
    expect(parsed.checked_symbols).toBe(4);
    expect(parsed.analyzed_symbols).toBe(4);
    expect(parsed.markets_checked).toBe(4);
    expect(parsed.results.map(x => x.code)).toEqual(SAMPLES.map(x => x[1]));
    expect(parsed.by_market.de.sample_status).toBe('samples_passed');
  });

  it('accepts eight samples, still representing only four markets', () => {
    const parsed = parseFiveMarketSampleReport(report('expanded'));
    expect(parsed.checked_symbols).toBe(8);
    expect(parsed.markets_checked).toBe(4);
    expect(parsed.by_market.tr.checked_symbols).toBe(2);
  });


  it('rejects Japan as a removed investment market', () => {
    const bad = report();
    bad.results[0] = {
      ...bad.results[0], market: 'jp' as FocusMarket, code: '7203.T', yahoo_symbol: '7203.T',
    };
    expect(() => parseFiveMarketSampleReport(bad)).toThrow();
  });

  it('accepts 400 structurally valid samples with 100 per market, not 401', () => {
    const codes: Record<FocusMarket, string[]> = {
      tr: Array.from({ length: 100 }, (_, i) => `T${String.fromCharCode(65 + Math.floor(i / 26))}${String.fromCharCode(65 + i % 26)}A.IS`),
      us: Array.from({ length: 100 }, (_, i) => `U${String.fromCharCode(65 + Math.floor(i / 26))}${String.fromCharCode(65 + i % 26)}`),
      de: Array.from({ length: 100 }, (_, i) => `D${String(i).padStart(4, '0')}.DE`),
      hk: Array.from({ length: 100 }, (_, i) => `HK${String(i + 1).padStart(5, '0')}`),
    };
    const rows = FOCUS_MARKETS.flatMap(market => codes[market].map(code => {
      const yahoo = market === 'hk' ? `${String(Number(code.slice(2))).padStart(4, '0')}.HK` : code;
      return makeRow(market, code, yahoo);
    }));
    const valid = fromRows(rows);
    const parsed = parseFiveMarketSampleReport(valid);
    expect(parsed.checked_symbols).toBe(400);
    expect(parsed.remaining_to_target).toBe(0);
    expect(parsed.by_market.de.checked_symbols).toBe(100);

    valid.results.push({ ...rows[0] });
    valid.checked_symbols += 1;
    expect(() => parseFiveMarketSampleReport(valid)).toThrow();
  });

  it('rejects a false completed target', () => {
    const bad = report();
    bad.remaining_to_target = 0;
    expect(() => parseFiveMarketSampleReport(bad)).toThrow();
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

  it('rejects a fixed four-market report with substituted symbols or duplicates', () => {
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
