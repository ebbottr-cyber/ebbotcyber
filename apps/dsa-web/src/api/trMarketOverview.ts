import apiClient from './index';
import { toCamelCase } from './utils';

export type TrMarketStatus = 'ready' | 'stale' | 'unavailable';
export type TrMarketKey = 'bist100' | 'bist30' | 'usdtry' | 'eurtry' | 'gramgold';

export interface TrMarketItem {
  key: TrMarketKey;
  label: string;
  symbol: string | null;
  currency: string;
  price: number | null;
  changePct: number | null;
  asOf: string | null;
  status: TrMarketStatus;
  source: string | null;
  note: string;
}

export interface TrMarketOverviewResponse {
  asOf: string;
  cadence: 'delayed_daily';
  items: TrMarketItem[];
}

/** Delayed public daily prices only. Never an executable or real-time quote. */
export const trMarketApi = {
  async getOverview(): Promise<TrMarketOverviewResponse> {
    const response = await apiClient.get<Record<string, unknown>>('/api/v1/data/tr-market-overview');
    return toCamelCase<TrMarketOverviewResponse>(response.data);
  },
};
