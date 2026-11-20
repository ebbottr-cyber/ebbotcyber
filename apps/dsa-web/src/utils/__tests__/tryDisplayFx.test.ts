import { describe, expect, it } from 'vitest';
import { formatTryDisplay, type TryRateEvidence } from '../tryDisplayFx';

const now = new Date('2026-11-20T12:00:00+03:00');
const quote: TryRateEvidence = {
  source: 'TCMB',
  sourceCurrency: 'USD',
  targetCurrency: 'TRY',
  sourceUnit: 1,
  asOfDate: '2026-11-19',
  tryPerUnit: 50.1234,
};

describe('display-only TRY conversion', () => {
  it('converts only with a dated, validated indicative TCMB quote', () => {
    const result = formatTryDisplay(10, 'USD', quote, now);
    expect(result).toEqual({
      text: 'TRY 501,23',
      mode: 'converted',
      convertedAmountTry: 501.234,
      rateSource: 'TCMB',
      rateDate: '2026-11-19',
    });
  });

  it('preserves native TRY without an exchange rate', () => {
    expect(formatTryDisplay(10, 'TRY', null, now)).toMatchObject({
      text: 'TRY 10,00',
      mode: 'native',
      rateSource: null,
    });
  });

  it('does not invent TRY when a quote is missing, invalid, or outdated', () => {
    const badQuotes: Array<TryRateEvidence | null> = [
      null,
      { ...quote, asOfDate: '2026-11-10' },
      { ...quote, asOfDate: '2026-11-21' },
      { ...quote, asOfDate: '2026-02-30' },
      { ...quote, sourceCurrency: 'EUR' },
      { ...quote, targetCurrency: 'USD' as 'TRY' },
      { ...quote, sourceUnit: 100 as 1 },
      { ...quote, tryPerUnit: 0 },
      { ...quote, tryPerUnit: Number.NaN },
    ];
    for (const badQuote of badQuotes) {
      expect(formatTryDisplay(10, 'USD', badQuote, now)).toMatchObject({
        text: 'USD 10,00',
        mode: 'original',
        convertedAmountTry: null,
        rateSource: null,
      });
    }
  });

  it('never converts currencies without an explicit supported quote', () => {
    expect(formatTryDisplay(10, 'JPY', quote, now).text).toBe('JPY 10,00');
    expect(formatTryDisplay(null, 'USD', quote, now).text).toBe('--');
    expect(formatTryDisplay(Number.POSITIVE_INFINITY, 'USD', quote, now).text).toBe('--');
    expect(formatTryDisplay(-10, 'USD', quote, now).text).toBe('TRY -501,23');
  });
});
