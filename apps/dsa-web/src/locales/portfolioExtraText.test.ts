import { describe, expect, it } from 'vitest';
import { formatUiText } from '../i18n/uiText';
import { portfolioCopy, PORTFOLIO_DYNAMIC_TEXT } from './portfolioExtraText';

describe('portfolio legacy UI localization', () => {
  it('shows Turkish forms without altering Chinese or English locale', () => {
    const key = '手工录入：交易';
    expect(portfolioCopy(key, 'tr')).toBe('Elle giriş: Alım/satım');
    expect(portfolioCopy(key, 'en')).toBe('Manual entry: Trade');
    expect(portfolioCopy(key, 'zh')).toBe(key);
  });

  it('keeps configured currency and stock code as literal dynamic data', () => {
    expect(formatUiText(PORTFOLIO_DYNAMIC_TEXT.tr.currencyPlaceholder, { currency: 'HKD' }))
      .toContain('HKD');
    const confirmation = formatUiText(PORTFOLIO_DYNAMIC_TEXT.tr.deleteTrade, {
      date: '2026-11-16', side: 'Alış', code: '0700.HK', quantity: 10, price: 10.5,
    });
    expect(confirmation).toContain('0700.HK');
    expect(confirmation).toContain('10.5');
    expect(confirmation).not.toMatch(/[\u3400-\u9fff]/);
  });

  it('does not fabricate translations of unknown codes', () => {
    expect(portfolioCopy('HK00700', 'tr')).toBe('HK00700');
  });
});
