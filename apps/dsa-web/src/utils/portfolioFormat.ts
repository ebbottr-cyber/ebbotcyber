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

export type FxRefreshFeedback = {
  tone: 'neutral' | 'success' | 'warning';
  text: string;
};

export type PortfolioAlertVariant = 'info' | 'success' | 'warning' | 'danger';

export function getTodayIso(): string {
  return toDateInputValue(new Date());
}

export function formatMoney(value: number | undefined | null, currency = 'CNY'): string {
  if (value == null || !Number.isFinite(value)) return '--';
  return `${currency} ${Number(value).toLocaleString('tr-TR', {
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

export function getPositionPriceLabel(row: PortfolioPositionItem): string {
  if (!hasPositionPrice(row)) return 'Fiyat yok';
  if (row.priceSource === 'realtime_quote') {
    return row.priceProvider ? `Güncel fiyat · ${row.priceProvider}` : 'Güncel fiyat';
  }
  if (row.priceSource === 'history_close') {
    return row.priceStale && row.priceDate ? `Kapanış fiyatı · ${row.priceDate}` : 'Kapanış fiyatı';
  }
  return row.priceSource || 'Kaynak bilinmiyor';
}

export function formatSideLabel(value: PortfolioSide): string {
  return value === 'buy' ? 'Alış' : 'Satış';
}

export function formatCashDirectionLabel(value: PortfolioCashDirection): string {
  return value === 'in' ? 'Para girişi' : 'Para çıkışı';
}

export function formatCorporateActionLabel(value: PortfolioCorporateActionType): string {
  return value === 'cash_dividend' ? 'Nakit temettü' : 'Bölünme/birleşme düzeltmesi';
}

export function formatBrokerLabel(value: string, displayName?: string): string {
  // Broker codes remain unchanged in the API and stored portfolio.
  const brokerNames: Record<string, string> = {
    huatai: 'Huatai Securities',
    citic: 'CITIC Securities',
    cmb: 'China Merchants Bank',
  };
  if (brokerNames[value]) return `${value} (${brokerNames[value]})`;
  if (displayName?.trim()) return `${value} (${displayName.trim()})`;
  return value;
}

export function buildFxRefreshFeedback(data: PortfolioFxRefreshResponse): FxRefreshFeedback {
  if (data.refreshEnabled === false) {
    return {
      tone: 'neutral',
      text: 'Çevrimiçi döviz kuru yenileme kapalı.',
    };
  }

  if (data.pairCount === 0) {
    return {
      tone: 'neutral',
      text: 'Bu kapsamda yenilenebilecek döviz kuru çifti yok.',
    };
  }

  if (data.updatedCount > 0 && data.staleCount === 0 && data.errorCount === 0) {
    return {
      tone: 'success',
      text: `Döviz kurları yenilendi: ${data.updatedCount} çift.`,
    };
  }

  const summary = `Yenilenen: ${data.updatedCount}; güncel olmayan: ${data.staleCount}; başarısız: ${data.errorCount}.`;
  if (data.staleCount > 0) {
    return {
      tone: 'warning',
      text: `Kur yenileme denemesi tamamlandı ancak bazı döviz çiftleri için eski veya yedek kur mevcut. ${summary}`,
    };
  }

  return {
    tone: 'warning',
    text: `Çevrimiçi kur yenileme tam olarak başarılı olmadı. ${summary}`,
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
