import { describe, expect, it } from 'vitest';
import type { StockIndexItem } from '../types/stockIndex';
import { filterTurkishBrokerStockIndex, isTurkishBrokerMarket, TURKISH_BROKER_MARKETS } from './marketAccess';

const instrument = (code: string, market: StockIndexItem['market']): StockIndexItem => ({
  canonicalCode: code,
  displayCode: code,
  nameZh: code,
  market,
  assetType: 'stock',
  active: true,
});

describe('Turkish domestic-broker focus', () => {
  it('keeps the five selected markets in the investment UI', () => {
    expect(TURKISH_BROKER_MARKETS).toEqual(['tr', 'us', 'de', 'hk']);
    expect(isTurkishBrokerMarket('TR')).toBe(true);
    expect(isTurkishBrokerMarket(' US ')).toBe(true);
    expect(isTurkishBrokerMarket('DE')).toBe(true);
    expect(isTurkishBrokerMarket('CN')).toBe(false);
    expect(isTurkishBrokerMarket('KR')).toBe(false);
    expect(isTurkishBrokerMarket('TW')).toBe(false);
    expect(isTurkishBrokerMarket('JP')).toBe(false);
  });

  it('filters both object and decompressed stock index rows without changing symbols', () => {
    const stocks = [
      instrument('THYAO.IS', 'TR'),
      instrument('AAPL', 'US'),
      instrument('SAP.DE', 'DE'),
      instrument('HK00700', 'HK'),
      instrument('7203.T', 'JP'),
      instrument('600519.SH', 'CN'),
      instrument('005930.KS', 'KR'),
      instrument('2330.TW', 'TW'),
      instrument('399001.SZ', 'INDEX'),
    ];
    expect(filterTurkishBrokerStockIndex(stocks).map((row) => row.canonicalCode))
      .toEqual(['THYAO.IS', 'AAPL', 'SAP.DE', 'HK00700']);
    expect(stocks).toHaveLength(9);
  });
});
