import { describe, expect, it } from 'vitest';
import { getFieldTitle, getFieldOptionLabel } from './systemConfigI18n';

describe('Turkish configuration presentation', () => {
  it('uses Turkish titles without mutating any configuration key', () => {
    expect(getFieldTitle('STOCK_LIST', undefined, 'tr')).toBe('İzleme listesi');
    expect(getFieldTitle('LITELLM_MODEL', undefined, 'tr')).toBe('Ana yapay zekâ modeli');
    expect(getFieldTitle('FUTU_HK_REALTIME_SOURCE_PRIORITY', undefined, 'tr'))
      .toBe('Hong Kong canlı veri önceliği');
    expect(getFieldTitle('REPORT_LANGUAGE', undefined, 'tr')).toBe('Rapor dili');
    expect(getFieldTitle('STOCK_LIST', 'Watchlist', 'en')).toBe('Watchlist');
  });

  it('localizes option labels while preserving machine-readable values', () => {
    expect(getFieldOptionLabel('NEWS_STRATEGY_PROFILE', 'short', undefined, 'tr'))
      .toBe('Kısa vadeli (3 gün)');
    expect(getFieldOptionLabel('REPORT_LANGUAGE', 'zh', undefined, 'tr')).toBe('Çince');
    expect(getFieldOptionLabel('AGENT_BACKEND', 'auto', undefined, 'tr'))
      .toBe('Otomatik (önerilen)');
    expect(getFieldOptionLabel('GENERATION_FALLBACK_BACKEND', '', undefined, 'tr'))
      .toBe('Devre dışı');
    expect(getFieldOptionLabel('REPORT_TYPE', 'simple', undefined, 'en')).toBe('Simple');
    expect(getFieldOptionLabel('UNLISTED', 'value', 'Original', 'tr')).toBe('Original');
  });
});
