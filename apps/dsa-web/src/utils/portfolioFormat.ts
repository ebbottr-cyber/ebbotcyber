import type {
  PortfolioCashDirection,
  PortfolioCorporateActionType,
  PortfolioFxRefreshResponse,
  PortfolioImportCommitResponse,
  PortfolioImportParseResponse,
  PortfolioPositionItem,
  PortfolioSide,
} from '../types/portfolio';
import { toDateInputValue } from './format';
import type { UiLanguage } from '../i18n/uiText';

// Presentation-only labels. Portfolio movements, broker identifiers,
// currencies and persisted records are never translated.
const PORTFOLIO_LABELS = {
  tr: {
    priceMissing: 'Fiyat bulunamadı', livePrice: 'Canlı fiyat', closePrice: 'Kapanış fiyatı',
    unknownSource: 'Bilinmeyen kaynak', buy: 'Alış', sell: 'Satış', cashIn: 'Para girişi',
    cashOut: 'Para çıkışı', dividend: 'Nakit temettü', split: 'Bölünme/birleşme düzeltmesi',
    fxDisabled: 'Çevrimiçi döviz kuru yenilemesi kapalı.',
    fxEmpty: 'Bu kapsamda yenilenecek döviz çifti yok.',
    fxSuccess: (n: number) => `Döviz kurları yenilendi: ${n} parite güncellendi.`,
    fxSummary: (updated: number, stale: number, failed: number) =>
      `Güncellenen: ${updated}, güncel olmayan: ${stale}, başarısız: ${failed} parite.`,
    fxStale: 'Yenileme denendi ancak bazı paritelerde eski/yedek kur kullanılıyor. ',
    fxPartial: 'Çevrimiçi yenileme tam başarılı olmadı. ',
  },
  en: {
    priceMissing: 'Price unavailable', livePrice: 'Live price', closePrice: 'Closing price',
    unknownSource: 'Unknown source', buy: 'Buy', sell: 'Sell', cashIn: 'Cash inflow',
    cashOut: 'Cash outflow', dividend: 'Cash dividend', split: 'Split adjustment',
    fxDisabled: 'Online exchange-rate refresh is disabled.',
    fxEmpty: 'There are no exchange-rate pairs to refresh.',
    fxSuccess: (n: number) => `Exchange rates refreshed: ${n} pairs updated.`,
    fxSummary: (updated: number, stale: number, failed: number) =>
      `Updated: ${updated}; stale: ${stale}; failed: ${failed} pairs.`,
    fxStale: 'Refresh completed but some pairs still use stale or fallback rates. ',
    fxPartial: 'Online refresh did not fully succeed. ',
  },
  zh: {
    priceMissing: '缺价', livePrice: '实时价', closePrice: '收盘价',
    unknownSource: '未知来源', buy: '买入', sell: '卖出', cashIn: '流入',
    cashOut: '流出', dividend: '现金分红', split: '拆并股调整',
    fxDisabled: '汇率在线刷新已被禁用。',
    fxEmpty: '当前范围无可刷新的汇率对。',
    fxSuccess: (n: number) => `汇率已刷新，共更新 ${n} 对。`,
    fxSummary: (updated: number, stale: number, failed: number) =>
      `更新 ${updated} 对，仍过期 ${stale} 对，失败 ${failed} 对。`,
    fxStale: '已尝试刷新，但仍有部分货币对使用 stale/fallback 汇率。',
    fxPartial: '在线刷新未完全成功。',
  },
} as const;



export type FxRefreshFeedback = {
  tone: 'neutral' | 'success' | 'warning';
  text: string;
};

export type PortfolioAlertVariant = 'info' | 'success' | 'warning' | 'danger';

export function getTodayIso(): string {
  return toDateInputValue(new Date());
}

export function formatMoney(value: number | undefined | null, currency = 'CNY', language: UiLanguage = 'tr'): string {
  if (value == null || Number.isNaN(value)) return '--';
  return `${currency} ${Number(value).toLocaleString(language === 'zh' ? 'zh-CN' : language === 'en' ? 'en-US' : 'tr-TR', {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })}`;
}

export function formatPct(value: number | undefined | null): string {
  if (value == null || Number.isNaN(value)) return '--';
  return `${value.toFixed(2)}%`;
}

export function formatSignedPct(value: number | undefined | null): string {
  if (value == null || Number.isNaN(value)) return '--';
  const sign = value > 0 ? '+' : '';
  return `${sign}${value.toFixed(2)}%`;
}

export function hasPositionPrice(row: PortfolioPositionItem): boolean {
  return row.priceAvailable !== false && row.priceSource !== 'missing';
}

export function formatPositionPrice(row: PortfolioPositionItem): string {
  if (!hasPositionPrice(row)) return '--';
  return row.lastPrice.toFixed(4);
}

export function formatPositionMoney(value: number, row: PortfolioPositionItem): string {
  if (!hasPositionPrice(row)) return '--';
  return formatMoney(value, row.valuationCurrency);
}

export function getPositionPriceLabel(row: PortfolioPositionItem, language: UiLanguage = 'tr'): string {
  const labels = PORTFOLIO_LABELS[language];
  if (!hasPositionPrice(row)) return labels.priceMissing;
  if (row.priceSource === 'realtime_quote') {
    return row.priceProvider ? `${labels.livePrice} · ${row.priceProvider}` : labels.livePrice;
  }
  if (row.priceSource === 'history_close') {
    return row.priceStale && row.priceDate ? `${labels.closePrice} · ${row.priceDate}` : labels.closePrice;
  }
  return row.priceSource || labels.unknownSource;
}

export function formatSideLabel(value: PortfolioSide, language: UiLanguage = 'tr'): string {
  const labels = PORTFOLIO_LABELS[language];
  return value === 'buy' ? labels.buy : labels.sell;
}

export function formatCashDirectionLabel(value: PortfolioCashDirection, language: UiLanguage = 'tr'): string {
  const labels = PORTFOLIO_LABELS[language];
  return value === 'in' ? labels.cashIn : labels.cashOut;
}

export function formatCorporateActionLabel(value: PortfolioCorporateActionType, language: UiLanguage = 'tr'): string {
  const labels = PORTFOLIO_LABELS[language];
  return value === 'cash_dividend' ? labels.dividend : labels.split;
}

export function formatBrokerLabel(value: string, displayName?: string, language: UiLanguage = 'tr'): string {
  // Known broker names may be shown in Latin letters when the selected
  // interface uses a Latin script. Do not alter broker IDs or CSV values.
  const latinAliases: Record<string, string> = {
    huatai: 'Huatai', citic: 'CITIC', cmb: 'China Merchants',
  };
  const latinName = (displayName || '').trim();
  const isChinese = /[\u3400-\u9fff]/u.test(latinName);
  const name = language === 'zh'
    ? latinName
    : isChinese ? latinAliases[value] || value : latinName;
  if (name && name !== value) {
    return language === 'zh' ? `${value}（${name}）` : `${value} (${name})`;
  }
  if (language === 'zh') {
    const zhAliases: Record<string, string> = { huatai: '华泰', citic: '中信', cmb: '招商' };
    return zhAliases[value] ? `${value}（${zhAliases[value]}）` : value;
  }
  return latinAliases[value] ? `${value} (${latinAliases[value]})` : value;
}

export function buildFxRefreshFeedback(
  data: PortfolioFxRefreshResponse,
  language: UiLanguage = 'tr',
): FxRefreshFeedback {
  const labels = PORTFOLIO_LABELS[language];
  if (data.refreshEnabled === false) {
    return { tone: 'neutral', text: labels.fxDisabled };
  }
  if (data.pairCount === 0) {
    return { tone: 'neutral', text: labels.fxEmpty };
  }
  if (data.updatedCount > 0 && data.staleCount === 0 && data.errorCount === 0) {
    return { tone: 'success', text: labels.fxSuccess(data.updatedCount) };
  }
  const summary = labels.fxSummary(data.updatedCount, data.staleCount, data.errorCount);
  if (data.staleCount > 0) {
    return { tone: 'warning', text: labels.fxStale + summary };
  }
  return { tone: 'warning', text: labels.fxPartial + summary };
}

export function getFxRefreshFeedbackVariant(tone: FxRefreshFeedback['tone']): PortfolioAlertVariant {
  if (tone === 'success') return 'success';
  if (tone === 'warning') return 'warning';
  return 'info';
}

export function getCsvParseVariant(result: PortfolioImportParseResponse): PortfolioAlertVariant {
  return result.errorCount > 0 || result.skippedCount > 0 ? 'warning' : 'info';
}

export function getCsvCommitVariant(result: PortfolioImportCommitResponse, isDryRun: boolean): PortfolioAlertVariant {
  if (isDryRun) return 'info';
  return result.failedCount > 0 || result.duplicateCount > 0 ? 'warning' : 'success';
}
