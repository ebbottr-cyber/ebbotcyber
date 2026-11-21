import { describe, expect, it } from 'vitest';
import { formatUiText } from '../../i18n/uiText';
import { PORTFOLIO_LEDGER_TEXT } from '../../locales/portfolioLedgerText';
import { buildFxRefreshFeedback, formatBrokerLabel, getPositionPriceLabel } from '../portfolioFormat';
import type { PortfolioFxRefreshResponse, PortfolioPositionItem } from '../../types/portfolio';

describe('Portfolio ledger localization', () => {
  it('keeps trade identifiers stable and localizes visible labels', () => {
    expect(PORTFOLIO_LEDGER_TEXT.tr.buy).toBe('Alış');
    expect(PORTFOLIO_LEDGER_TEXT.en.buy).toBe('Buy');
    expect(PORTFOLIO_LEDGER_TEXT.zh.buy).toBe('买入');
    const message = formatUiText(PORTFOLIO_LEDGER_TEXT.tr.tradeDeleteConfirm, {
      date: '2026-11-19', side: PORTFOLIO_LEDGER_TEXT.tr.buy,
      symbol: 'AAPL', quantity: 2, price: 100,
    });
    expect(message).toContain('AAPL');
    expect(message).toContain('Adet: 2');
    expect(message).toContain('Fiyat: 100');
    expect(message).not.toMatch(/[\u3400-\u9fff]/u);
  });

  it('displays known Chinese broker names in Latin letters without changing their keys', () => {
    expect(formatBrokerLabel('huatai', '华泰', 'zh')).toBe('huatai（华泰）');
    expect(formatBrokerLabel('huatai', '华泰', 'tr')).toBe('huatai (Huatai)');
    expect(formatBrokerLabel('citic', '中信', 'tr')).toContain('CITIC Securities');
    expect(formatBrokerLabel('unknown', 'Custom Broker', 'tr')).toBe('unknown (Custom Broker)');
  });

  it('localizes price-source status while preserving the original provider identifier', () => {
    const row = {
      priceAvailable: true,
      priceSource: 'realtime_quote',
      priceProvider: 'provider-id',
    } as PortfolioPositionItem;
    expect(getPositionPriceLabel(row, 'tr')).toBe('Anlık fiyat · provider-id');
    expect(getPositionPriceLabel(row, 'zh')).toBe('实时价 · provider-id');
  });

  it('localizes the FX refresh outcome without changing refresh state', () => {
    const refresh = {
      refreshEnabled: true,
      pairCount: 1,
      updatedCount: 0,
      staleCount: 1,
      errorCount: 0,
    } as PortfolioFxRefreshResponse;
    const tr = buildFxRefreshFeedback(refresh, 'tr');
    expect(tr.tone).toBe('warning');
    expect(tr.text).toContain('eski/yedek kur');
    expect(tr.text).not.toMatch(/[\u3400-\u9fff]/u);
    expect(buildFxRefreshFeedback(refresh).text).toContain('已尝试刷新');
  });
});
