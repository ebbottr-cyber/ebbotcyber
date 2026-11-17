import { describe, expect, it } from 'vitest';
import type { PortfolioFxRefreshResponse, PortfolioPositionItem } from '../types/portfolio';
import {
  buildFxRefreshFeedback,
  formatBrokerLabel,
  formatCashDirectionLabel,
  formatCorporateActionLabel,
  formatMoney,
  formatSideLabel,
  getPositionPriceLabel,
} from './portfolioFormat';

describe('portfolio presentation localization', () => {
  it('shows Turkish amounts while preserving the actual currency', () => {
    expect(formatMoney(1234.56, 'TRY', 'tr')).toBe('TRY 1.234,56');
    expect(formatMoney(1234.56, 'USD', 'en')).toBe('USD 1,234.56');
    expect(formatMoney(null, 'HKD', 'tr')).toBe('--');
  });

  it('translates movement labels without translating their machine values', () => {
    expect(formatSideLabel('buy', 'tr')).toBe('Alış');
    expect(formatSideLabel('sell', 'en')).toBe('Sell');
    expect(formatSideLabel('buy', 'zh')).toBe('买入');
    expect(formatCashDirectionLabel('in', 'tr')).toBe('Para girişi');
    expect(formatCorporateActionLabel('cash_dividend', 'tr')).toBe('Nakit temettü');
    expect(formatCorporateActionLabel('split_adjustment', 'en')).toContain('Split');
  });

  it('uses Latin broker names in Turkish without changing broker identifiers', () => {
    expect(formatBrokerLabel('huatai', '华泰', 'tr')).toBe('huatai (Huatai)');
    expect(formatBrokerLabel('huatai', '华泰', 'zh')).toBe('huatai（华泰）');
    expect(formatBrokerLabel('unknown', '未知', 'tr')).toBe('unknown');
    expect(formatBrokerLabel('custom', 'Custom Securities', 'tr')).toBe('custom (Custom Securities)');
  });

  it('localizes price-source indicators without altering the provider', () => {
    const row = {
      priceSource: 'realtime_quote',
      priceAvailable: true,
      priceProvider: 'Yahoo',
      lastPrice: 10,
    } as PortfolioPositionItem;
    expect(getPositionPriceLabel(row, 'tr')).toBe('Canlı fiyat · Yahoo');
    expect(getPositionPriceLabel({ ...row, priceSource: 'missing' }, 'tr'))
      .toBe('Fiyat bulunamadı');
  });

  it('localizes FX refresh outcomes from unchanged numeric results', () => {
    const result = {
      refreshEnabled: true, pairCount: 2, updatedCount: 1, staleCount: 1, errorCount: 0,
    } as PortfolioFxRefreshResponse;
    const tr = buildFxRefreshFeedback(result, 'tr');
    expect(tr.tone).toBe('warning');
    expect(tr.text).toContain('Güncellenen: 1');
    expect(tr.text).not.toMatch(/[\u3400-\u9fff]/);
    expect(buildFxRefreshFeedback(result, 'zh').text).toContain('更新');
    expect(buildFxRefreshFeedback({ ...result, refreshEnabled: false }, 'tr').text)
      .toContain('kapalı');
  });
});
