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

export type FxRefreshFeedback = {
  tone: 'neutral' | 'success' | 'warning';
  text: string;
};

export type PortfolioAlertVariant = 'info' | 'success' | 'warning' | 'danger';

export function getTodayIso(): string {
  return toDateInputValue(new Date());
}

export function formatMoney(value: number | undefined | null, currency = 'CNY'): string {
  if (value == null || Number.isNaN(value)) return '--';
  return `${currency} ${Number(value).toLocaleString('zh-CN', {
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

export function getPositionPriceLabel(row: PortfolioPositionItem, language: UiLanguage = 'zh'): string {
  const labels = {
    zh: { missing: '缺价', realtime: '实时价', close: '收盘价', unknown: '未知来源' },
    en: { missing: 'Price unavailable', realtime: 'Live quote', close: 'Closing price', unknown: 'Unknown source' },
    tr: { missing: 'Fiyat bulunamadı', realtime: 'Anlık fiyat', close: 'Kapanış fiyatı', unknown: 'Bilinmeyen kaynak' },
  }[language];
  if (!hasPositionPrice(row)) return labels.missing;
  if (row.priceSource === 'realtime_quote') {
    return row.priceProvider ? `${labels.realtime} · ${row.priceProvider}` : labels.realtime;
  }
  if (row.priceSource === 'history_close') {
    return row.priceStale && row.priceDate ? `${labels.close} · ${row.priceDate}` : labels.close;
  }
  return row.priceSource || labels.unknown;
}

export function formatSideLabel(value: PortfolioSide): string {
  return value === 'buy' ? '买入' : '卖出';
}

export function formatCashDirectionLabel(value: PortfolioCashDirection): string {
  return value === 'in' ? '流入' : '流出';
}

export function formatCorporateActionLabel(value: PortfolioCorporateActionType): string {
  return value === 'cash_dividend' ? '现金分红' : '拆并股调整';
}

export function formatBrokerLabel(value: string, displayName?: string, language: UiLanguage = 'zh'): string {
  // The broker ID is used for imports; only its displayed name is localized.
  const brokerNames: Record<string, { zh: string; tr: string; en: string }> = {
    huatai: { zh: '华泰', tr: 'Huatai', en: 'Huatai' },
    citic: { zh: '中信', tr: 'CITIC Securities', en: 'CITIC Securities' },
    cmb: { zh: '招商', tr: 'China Merchants Securities', en: 'China Merchants Securities' },
  };
  const known = brokerNames[value];
  const name = (language !== 'zh' && known)
    ? known[language]
    : (displayName?.trim() || known?.zh);
  if (!name) return value;
  return language === 'zh' ? `${value}（${name}）` : `${value} (${name})`;
}

export function buildFxRefreshFeedback(data: PortfolioFxRefreshResponse, language: UiLanguage = 'zh'): FxRefreshFeedback {
  if (data.refreshEnabled === false) {
    return {
      tone: 'neutral',
      text: language === 'zh' ? '汇率在线刷新已被禁用。' : language === 'tr' ? 'Çevrimiçi kur yenileme devre dışı.' : 'Online FX refresh is disabled.',
    };
  }

  if (data.pairCount === 0) {
    return {
      tone: 'neutral',
      text: language === 'zh' ? '当前范围无可刷新的汇率对。' : language === 'tr' ? 'Bu kapsamda yenilenecek döviz çifti yok.' : 'There are no FX pairs to refresh in this scope.',
    };
  }

  if (data.updatedCount > 0 && data.staleCount === 0 && data.errorCount === 0) {
    return {
      tone: 'success',
      text: language === 'zh' ? `汇率已刷新，共更新 ${data.updatedCount} 对。` : language === 'tr' ? `${data.updatedCount} döviz çifti yenilendi.` : `Updated ${data.updatedCount} FX pair(s).`,
    };
  }

  const summary = language === 'zh'
    ? `更新 ${data.updatedCount} 对，仍过期 ${data.staleCount} 对，失败 ${data.errorCount} 对。`
    : language === 'tr'
      ? `Güncellenen: ${data.updatedCount}; eski: ${data.staleCount}; başarısız: ${data.errorCount}.`
      : `Updated: ${data.updatedCount}; stale: ${data.staleCount}; failed: ${data.errorCount}.`;
  if (data.staleCount > 0) {
    return {
      tone: 'warning',
      text: language === 'zh' ? `已尝试刷新，但仍有部分货币对使用 stale/fallback 汇率。${summary}` : language === 'tr' ? `Kur yenilemesi denendi; bazı çiftlerde eski/yedek kur kullanılıyor. ${summary}` : `FX refresh attempted; some pairs still use stale/fallback rates. ${summary}`,
    };
  }

  return {
    tone: 'warning',
    text: language === 'zh' ? `在线刷新未完全成功。${summary}` : language === 'tr' ? `Kur yenilemesi tam olarak tamamlanamadı. ${summary}` : `FX refresh was incomplete. ${summary}`,
  };
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
