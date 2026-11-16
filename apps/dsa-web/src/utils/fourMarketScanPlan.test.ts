import { describe, expect, it } from 'vitest';
import { FOUR_ACTIVE_MARKETS, STOCKS_PER_MARKET, TOTAL_STOCK_TARGET,
  buildFourMarketScanPlan, detectFourMarketSymbol } from './fourMarketScanPlan';
import { TURKISH_BROKER_MARKETS } from './marketAccess';

function sample400() {
  return [
    ...Array.from({ length: 100 }, (_, i) =>
      'T' + String.fromCharCode(65 + Math.floor(i / 26)) + String.fromCharCode(65 + i % 26) + 'A.IS'),
    ...Array.from({ length: 100 }, (_, i) =>
      'U' + String.fromCharCode(65 + Math.floor(i / 26)) + String.fromCharCode(65 + i % 26)),
    ...Array.from({ length: 100 }, (_, i) => 'D' + String(i).padStart(4, '0') + '.DE'),
    ...Array.from({ length: 100 }, (_, i) => 'HK' + String(i + 1).padStart(5, '0')),
  ];
}

describe('ETRE browser-only 4-market, 400-symbol preparation', () => {
  it('matches the investment allowlist, removing Japan completely', () => {
    expect(FOUR_ACTIVE_MARKETS).toEqual(TURKISH_BROKER_MARKETS);
    expect(STOCKS_PER_MARKET).toBe(100);
    expect(TOTAL_STOCK_TARGET).toBe(400);
    expect(detectFourMarketSymbol('7203.T')).toBeNull();
    expect(detectFourMarketSymbol('005930.KS')).toBeNull();
    expect(detectFourMarketSymbol('600519.SH')).toBeNull();
    expect(detectFourMarketSymbol('2330.TW')).toBeNull();
    expect(detectFourMarketSymbol('SPX')).toBeNull();
  });

  it('accepts four complete blocks of 100 with distinct market identities', () => {
    const stockCodes = sample400();
    const result = buildFourMarketScanPlan(stockCodes.join('\n'));
    expect(result.readyForFullScan).toBe(true);
    expect(result.total).toBe(400);
    expect(result.counts).toEqual({ tr: 100, us: 100, de: 100, hk: 100 });
    expect(result.remaining).toEqual({ tr: 0, us: 0, de: 0, hk: 0 });
    expect(result.errors).toEqual([]);
    expect(result.codes).toEqual(stockCodes);
  });

  it('does not claim a full 400 scan for four sample tickers', () => {
    const result = buildFourMarketScanPlan('THYAO.IS, AAPL; SAP.DE\nHK00700');
    expect(result.readyForFullScan).toBe(false);
    expect(result.total).toBe(4);
    expect(result.remaining).toEqual({ tr: 99, us: 99, de: 99, hk: 99 });
  });

  it('rejects a 101st German stock even with fewer than 400 total', () => {
    const result = buildFourMarketScanPlan(
      [...sample400().slice(200, 300), 'D9999.DE'].join('\n'),
    );
    expect(result.readyForFullScan).toBe(false);
    expect(result.counts.de).toBe(101);
    expect(result.errors.join(' ')).toMatch(/More than 100/);
  });

  it('does not infer Germany from a bare US ticker', () => {
    const r = buildFourMarketScanPlan('SAP, SAP.DE');
    expect(r.counts).toEqual({ tr: 0, us: 1, de: 1, hk: 0 });
  });

  it('identifies duplicates and removed regions without hiding errors', () => {
    const result = buildFourMarketScanPlan('AAPL,aapl,7203.T,HK00700');
    expect(result.total).toBe(2);
    expect(result.errors).toHaveLength(2);
    expect(result.readyForFullScan).toBe(false);
  });

  it('rejects excessive input and does not pretend validation succeeded', () => {
    const result = buildFourMarketScanPlan('AAPL,'.repeat(1000));
    expect(result.total).toBe(0);
    expect(result.errors.length).toBeGreaterThan(0);
  });
});
