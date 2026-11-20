import { describe, expect, it } from 'vitest';
import type { PortfolioDisplayFxRates, PortfolioSnapshotResponse } from '../../types/portfolio';
import { toTryDisplayValue, formatTryDisplay, formatPortfolioSnapshotTry, getPortfolioTryQuoteAsOf } from '../portfolioTryDisplay';

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
    expect(toTryDisplayValue(70, 'cny', fx, false, now)).toBeCloseTo(500);
  });

  it('converts actual USD with USD/TRY and does not treat USD as CNY', () => {
    expect(toTryDisplayValue(70, 'usd', fx, false, now)).toBe(3500);
  });

  it('formats in Turkish lira without relabeling the raw amount', () => {
    const formatted = formatTryDisplay(70, 'cny', fx, false, now);
    expect(formatted).toContain('500,00');
    expect(formatted).toMatch(/₺|TRY/);
  });

  it('refuses stale, unknown, invalid and 1:1 fallback valuations', () => {
    expect(toTryDisplayValue(70, 'cny', { ...fx, status: 'stale' }, false, now)).toBeNull();
    expect(toTryDisplayValue(70, 'cny', fx, true, now)).toBeNull();
    expect(toTryDisplayValue(70, 'hkd', fx, false, now)).toBeNull();
    expect(toTryDisplayValue(70, 'cny', { ...fx, asOf: '2026-11-19T08:00:00.000Z' }, false, now)).toBeNull();
    expect(toTryDisplayValue(70, 'cny', { ...fx, cnyTry: null }, false, now)).toBeNull();
    expect(formatTryDisplay(70, 'hkd', fx, false, now)).toBe('—');
  });

  it('preserves a valid TRY amount without any FX network quote', () => {
    expect(toTryDisplayValue(1000, 'TRY', null, false, now)).toBe(1000);
  });
  it('sums account-native CNY and USD amounts in TRY, not the CNY aggregate', () => {
    const snapshot = {
      accountCount: 2,
      currency: 'cny',
      fxStale: false,
      totalEquity: 999999, // deliberately wrong legacy aggregate
      accounts: [
        { baseCurrency: 'cny', totalEquity: 70, totalCash: 7, totalMarketValue: 63, fxStale: false },
        { baseCurrency: 'usd', totalEquity: 10, totalCash: 4, totalMarketValue: 6, fxStale: false },
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
      pairStatus: { usd: 'current', cny: 'unavailable', hkd: 'current', jpy: 'current', krw: 'current', twd: 'current' },
      pairAsOf: Object.fromEntries(['usd', 'hkd', 'jpy', 'krw', 'twd'].map(code => [code, fx.asOf!])) as PortfolioDisplayFxRates['pairAsOf'],
    };
    expect(toTryDisplayValue(8, 'hkd', multi, false, now)).toBe(50);
    expect(toTryDisplayValue(160, 'jpy', multi, false, now)).toBe(50);
    expect(toTryDisplayValue(1400, 'krw', multi, false, now)).toBeCloseTo(50);
    expect(toTryDisplayValue(32, 'twd', multi, false, now)).toBe(50);
    expect(toTryDisplayValue(7, 'cny', multi, false, now)).toBeNull();
  });

  it('rejects missing pair evidence, pair stale status and future timestamps', () => {
    const valid: PortfolioDisplayFxRates = {
      ...fx, hkdTry: 6.25, pairStatus: { hkd: 'current' }, pairAsOf: { hkd: fx.asOf! },
    };
    expect(toTryDisplayValue(8, 'hkd', valid, false, now)).toBe(50);
    expect(toTryDisplayValue(8, 'hkd', { ...valid, pairAsOf: {} }, false, now)).toBeNull();
    expect(toTryDisplayValue(8, 'hkd', { ...valid, pairStatus: { hkd: 'stale' } }, false, now)).toBeNull();
    expect(toTryDisplayValue(8, 'hkd', { ...valid, pairStatus: { hkd: 'unavailable' } }, false, now)).toBeNull();
    expect(toTryDisplayValue(8, 'hkd', { ...valid, pairAsOf: { hkd: '2026-11-19T10:00:00Z' } }, false, now)).toBeNull();
    expect(toTryDisplayValue(8, 'hkd', { ...valid, pairAsOf: { hkd: '2026-11-19T07:00:00Z' } }, false, now)).toBeNull();
    expect(toTryDisplayValue(8, 'hkd', { ...valid, hkdTry: 0 }, false, now)).toBeNull();
    expect(toTryDisplayValue(8, 'hkd', { ...valid, hkdTry: Infinity }, false, now)).toBeNull();
    expect(toTryDisplayValue(8, 'hkd', { ...valid, hkdTry: NaN }, false, now)).toBeNull();
    expect(toTryDisplayValue(8, 'hkd', { ...valid, hkdTry: 6.25 }, true, now)).toBeNull();
    expect(toTryDisplayValue(8, 'CHF', valid, false, now)).toBeNull();
  });

  it('shows the HKD quote time rather than missing legacy CNY time', () => {
    const snapshot = {
      accountCount: 1, fxStale: false,
      accounts: [{ baseCurrency: 'HKD', totalEquity: 8, fxStale: false }],
    } as PortfolioSnapshotResponse;
    const multi: PortfolioDisplayFxRates = {
      ...fx, status: 'unavailable', cnyTry: null, asOf: null,
      hkdTry: 6.25, pairStatus: { hkd: 'current' },
      pairAsOf: { hkd: '2026-11-19T08:55:00.000Z' },
    };
    expect(formatPortfolioSnapshotTry(snapshot, 'totalEquity', multi, now)).toContain('50,00');
    expect(getPortfolioTryQuoteAsOf(snapshot, multi, now)).toBe('2026-11-19T08:55:00.000Z');
  });

  it('uses the oldest currency quote when combining multi-market TRY totals', () => {
    const snapshot = {
      accountCount: 2, fxStale: false,
      accounts: [
        { baseCurrency: 'HKD', totalEquity: 8, fxStale: false },
        { baseCurrency: 'USD', totalEquity: 1, fxStale: false },
      ],
    } as PortfolioSnapshotResponse;
    const multi: PortfolioDisplayFxRates = {
      ...fx, status: 'unavailable', asOf: null,
      hkdTry: 6.25,
      pairStatus: { usd: 'current', hkd: 'current' },
      pairAsOf: {
        usd: '2026-11-19T08:57:00.000Z',
        hkd: '2026-11-19T08:45:00.000Z',
      },
    };
    expect(getPortfolioTryQuoteAsOf(snapshot, multi, now)).toBe('2026-11-19T08:45:00.000Z');
    expect(getPortfolioTryQuoteAsOf(snapshot, {
      ...multi, pairStatus: { usd: 'current', hkd: 'stale' },
    }, now)).toBeNull();
    expect(getPortfolioTryQuoteAsOf(snapshot, {
      ...multi, pairAsOf: { usd: multi.pairAsOf!.usd },
    }, now)).toBeNull();
  });

  it('never invents an FX timestamp for TRY-only or missing snapshot data', () => {
    const direct = {
      accountCount: 1, fxStale: false,
      accounts: [{ baseCurrency: 'TRY', totalEquity: 1000, fxStale: false }],
    } as PortfolioSnapshotResponse;
    expect(formatPortfolioSnapshotTry(direct, 'totalEquity', null, now)).toContain('1.000,00');
    expect(getPortfolioTryQuoteAsOf(direct, null, now)).toBeNull();
    expect(getPortfolioTryQuoteAsOf({ ...direct, fxStale: true }, fx, now)).toBeNull();
    expect(getPortfolioTryQuoteAsOf(null, fx, now)).toBeNull();
  });

  it('allows a fresh HKD account in a valid snapshot while still requiring aggregate freshness', () => {
    const snapshot = {
      accountCount: 1, fxStale: false,
      accounts: [{ baseCurrency: 'hkd', totalEquity: 8, totalCash: 8, totalMarketValue: 0, fxStale: false }],
    } as PortfolioSnapshotResponse;
    const multi: PortfolioDisplayFxRates = {
      ...fx, hkdTry: 6.25, pairStatus: { hkd: 'current' }, pairAsOf: { hkd: fx.asOf! },
    };
    expect(formatPortfolioSnapshotTry(snapshot, 'totalEquity', multi, now)).toContain('50,00');
    expect(formatPortfolioSnapshotTry(snapshot, 'totalEquity', { ...multi, pairStatus: { hkd: 'stale' } }, now)).toBe('—');
  });

});
