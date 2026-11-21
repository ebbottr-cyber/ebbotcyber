import { describe, expect, it } from 'vitest';
import { calculateIndicators, emaSeries, rsi14 } from '../technicalIndicators';

describe('EBBot technical indicators', () => {
  it('does not invent values for insufficient history', () => {
    expect(calculateIndicators([100, 101, 99])).toEqual({
      rsi14: null, ema20: null, ema50: null,
      macd: null, macdSignal: null, macdHistogram: null,
    });
  });

  it('rejects non-finite, zero and negative prices', () => {
    for (const input of [[100, NaN, 110], [100, Infinity, 110], [100, 0, 110], [100, -2, 110]]) {
      expect(calculateIndicators(input).rsi14).toBeNull();
      expect(emaSeries(input, 2).every((value) => value === null)).toBe(true);
    }
  });

  it('handles rising, falling and flat RSI, with a 15-close minimum', () => {
    expect(rsi14(Array(18).fill(100))).toBe(50);
    expect(rsi14(Array.from({length: 20}, (_, i) => 100 + i))).toBe(100);
    expect(rsi14(Array.from({length: 20}, (_, i) => 100 - i))).toBe(0);
    expect(rsi14(Array(14).fill(100))).toBeNull();
  });

  it('seeds EMA with SMA and smooths subsequent values', () => {
    expect(emaSeries([1, 2, 3, 4, 5], 3)).toEqual([null, null, 2, 3, 4]);
    expect(emaSeries([100, 100, 100], 2)).toEqual([null, 100, 100]);
  });

  it('requires 34 closing prices for MACD signal and 50 for EMA50', () => {
    const input = Array.from({length: 50}, (_, i) => 100 + i * 0.8);
    expect(calculateIndicators(input.slice(0, 33)).macd).toBeNull();
    expect(calculateIndicators(input.slice(0, 34)).macd).not.toBeNull();
    expect(calculateIndicators(input.slice(0, 49)).ema50).toBeNull();
    const result = calculateIndicators(input);
    expect(result.macdSignal).not.toBeNull();
    expect(result.macdHistogram).not.toBeNull();
    expect(result.ema20 as number).toBeGreaterThan(result.ema50 as number);
  });

  it('shows neutral rather than buy or sell for flat prices', () => {
    const result = calculateIndicators(Array(60).fill(110));
    expect(result.rsi14).toBe(50);
    expect(result.macd).toBeCloseTo(0, 8);
    expect(result.macdSignal).toBeCloseTo(0, 8);
    expect(result.macdHistogram).toBeCloseTo(0, 8);
  });
});
