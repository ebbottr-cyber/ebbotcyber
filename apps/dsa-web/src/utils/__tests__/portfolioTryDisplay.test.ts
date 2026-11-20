import { describe, expect, it } from 'vitest';
import type { PortfolioDisplayFxRates, PortfolioSnapshotResponse } from '../../types/portfolio';
import { toTryDisplayValue, formatTryDisplay, formatPortfolioSnapshotTry } from '../portfolioTryDisplay';

const now = Date.parse('2026-11-19T09:00:00.000Z');
const fx: PortfolioDisplayFxRates = {
  status: 'current',
  usdTry: 50,
  usdCny: 7,
  cnyTry: 50 / 7,
  asOf: '2026-11-19T08:55:00.000Z',
  source: 'test quote',
};

describe('TRY presentation conversion', () => {
  it('converts CNY using USD/TRY divided by USD/CNY', () => {
    expect(toTryDisplayValue(70, 'CNY', fx, false, now)).toBeCloseTo(500);
  });

  it('converts actual USD with USD/TRY and does not treat USD as CNY', () => {
    expect(toTryDisplayValue(70, 'USD', fx, false, now)).toBe(3500);
  });

  it('formats in Turkish lira without relabeling the raw amount', () => {
    const formatted = formatTryDisplay(70, 'CNY', fx, false, now);
    expect(formatted).toContain('500,00');
    expect(formatted).toMatch(/₺|TRY/);
  });

  it('refuses stale, unknown, invalid and 1:1 fallback valuations', () => {
    expect(toTryDisplayValue(70, 'CNY', { ...fx, status: 'stale' }, false, now)).toBeNull();
    expect(toTryDisplayValue(70, 'CNY', fx, true, now)).toBeNull();
    expect(toTryDisplayValue(70, 'HKD', fx, false, now)).toBeNull();
    expect(toTryDisplayValue(70, 'CNY', { ...fx, asOf: '2026-11-19T08:00:00.000Z' }, false, now)).toBeNull();
    expect(toTryDisplayValue(70, 'CNY', { ...fx, cnyTry: null }, false, now)).toBeNull();
    expect(formatTryDisplay(70, 'HKD', fx, false, now)).toBe('—');
  });

  it('preserves a valid TRY amount without any FX network quote', () => {
    expect(toTryDisplayValue(1000, 'TRY', null, false, now)).toBe(1000);
  });
  it('sums account-native CNY and USD amounts in TRY, not the CNY aggregate', () => {
    const snapshot = {
      accountCount: 2,
      currency: 'CNY',
      fxStale: false,
      totalEquity: 999999, // deliberately wrong legacy aggregate
      accounts: [
        { baseCurrency: 'CNY', totalEquity: 70, totalCash: 7, totalMarketValue: 63, fxStale: false },
        { baseCurrency: 'USD', totalEquity: 10, totalCash: 4, totalMarketValue: 6, fxStale: false },
      ],
    } as PortfolioSnapshotResponse;
    expect(formatPortfolioSnapshotTry(snapshot, 'totalEquity', fx, now)).toContain('1.000,00');
    expect(formatPortfolioSnapshotTry(snapshot, 'totalCash', fx, now)).toContain('250,00');
    expect(formatPortfolioSnapshotTry({ ...snapshot, fxStale: true }, 'totalEquity', fx, now)).toBe('—');
    expect(formatPortfolioSnapshotTry({
      ...snapshot,
      accounts: [{ ...snapshot.accounts[0], fxStale: true }, snapshot.accounts[1]],
    }, 'totalEquity', fx, now)).toBe('—');
  });


  it('converts independently verified HKD, JPY, KRW and TWD without 1:1 guesses', () => {
    const multi: PortfolioDisplayFxRates = {
      ...fx, status: 'unavailable', cnyTry: null, asOf: null,
      hkdTry: 6.25, jpyTry: 0.3125, krwTry: 50 / 1400, twdTry: 1.5625,
      pairStatus: { USD: 'current', CNY: 'unavailable', HKD: 'current', JPY: 'current', KRW: 'current', TWD: 'current' },
      pairAsOf: Object.fromEntries(['USD', 'HKD', 'JPY', 'KRW', 'TWD'].map(code => [code, fx.asOf!])) as PortfolioDisplayFxRates['pairAsOf'],
    };
    expect(toTryDisplayValue(8, 'HKD', multi, false, now)).toBe(50);
    expect(toTryDisplayValue(160, 'JPY', multi, false, now)).toBe(50);
    expect(toTryDisplayValue(1400, 'KRW', multi, false, now)).toBeCloseTo(50);
    expect(toTryDisplayValue(32, 'TWD', multi, false, now)).toBe(50);
    expect(toTryDisplayValue(7, 'CNY', multi, false, now)).toBeNull();
  });

  it('rejects missing pair evidence, pair stale status and future timestamps', () => {
    const valid: PortfolioDisplayFxRates = {
      ...fx, hkdTry: 6.25, pairStatus: { HKD: 'current' }, pairAsOf: { HKD: fx.asOf! },
    };
    expect(toTryDisplayValue(8, 'HKD', valid, false, now)).toBe(50);
    expect(toTryDisplayValue(8, 'HKD', { ...valid, pairAsOf: {} }, false, now)).toBeNull();
    expect(toTryDisplayValue(8, 'HKD', { ...valid, pairStatus: { HKD: 'stale' } }, false, now)).toBeNull();
    expect(toTryDisplayValue(8, 'HKD', { ...valid, pairStatus: { HKD: 'unavailable' } }, false, now)).toBeNull();
    expect(toTryDisplayValue(8, 'HKD', { ...valid, pairAsOf: { HKD: '2026-11-19T10:00:00Z' } }, false, now)).toBeNull();
    expect(toTryDisplayValue(8, 'HKD', { ...valid, pairAsOf: { HKD: '2026-11-19T07:00:00Z' } }, false, now)).toBeNull();
    expect(toTryDisplayValue(8, 'HKD', { ...valid, hkdTry: 0 }, false, now)).toBeNull();
    expect(toTryDisplayValue(8, 'HKD', { ...valid, hkdTry: Infinity }, false, now)).toBeNull();
    expect(toTryDisplayValue(8, 'HKD', { ...valid, hkdTry: NaN }, false, now)).toBeNull();
    expect(toTryDisplayValue(8, 'HKD', { ...valid, hkdTry: 6.25 }, true, now)).toBeNull();
    expect(toTryDisplayValue(8, 'CHF', valid, false, now)).toBeNull();
  });

  it('allows a fresh HKD account in a valid snapshot while still requiring aggregate freshness', () => {
    const snapshot = {
      accountCount: 1, fxStale: false,
      accounts: [{ baseCurrency: 'HKD', totalEquity: 8, totalCash: 8, totalMarketValue: 0, fxStale: false }],
    } as PortfolioSnapshotResponse;
    const multi: PortfolioDisplayFxRates = {
      ...fx, hkdTry: 6.25, pairStatus: { HKD: 'current' }, pairAsOf: { HKD: fx.asOf! },
    };
    expect(formatPortfolioSnapshotTry(snapshot, 'totalEquity', multi, now)).toContain('50,00');
    expect(formatPortfolioSnapshotTry(snapshot, 'totalEquity', { ...multi, pairStatus: { HKD: 'stale' } }, now)).toBe('—');
  });

});
