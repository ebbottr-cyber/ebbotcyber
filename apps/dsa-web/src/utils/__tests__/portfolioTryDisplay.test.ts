import { describe, expect, it } from 'vitest';
import type { PortfolioDisplayFxRates } from '../../types/portfolio';
import { toTryDisplayValue, formatTryDisplay } from '../portfolioTryDisplay';

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
});
