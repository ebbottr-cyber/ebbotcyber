import apiClient from './index';

export type DashboardQuote = {
  stock_code: string;
  stock_name: string | null;
  current_price: number;
  change: number | null;
  change_percent: number | null;
  update_time: string | null;
};

export type DashboardBar = {
  date: string;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number | null;
};

type HistoryEnvelope = {
  stock_code: string;
  stock_name: string | null;
  period: string;
  data: DashboardBar[];
};

export const dashboardApi = {
  async getWatchlist(): Promise<string[]> {
    const response = await apiClient.get<{ stock_codes: string[] }>('/api/v1/stocks/watchlist');
    const codes = response.data.stock_codes;
    return Array.isArray(codes)
      ? codes.filter((v): v is string => typeof v === 'string' && v.length > 0 && v.length <= 24)
      : [];
  },
  async getQuote(code: string): Promise<DashboardQuote> {
    const response = await apiClient.get<DashboardQuote>(
      '/api/v1/stocks/' + encodeURIComponent(code) + '/quote',
    );
    return response.data;
  },
  async getHistory(code: string, days: number): Promise<DashboardBar[]> {
    const response = await apiClient.get<HistoryEnvelope>(
      '/api/v1/stocks/' + encodeURIComponent(code) + '/history',
      { params: { period: 'daily', days } },
    );
    if (!Array.isArray(response.data.data)) return [];
    return response.data.data
      .filter(bar => (
        typeof bar.date === 'string' &&
        Number.isFinite(bar.open) && Number.isFinite(bar.high) &&
        Number.isFinite(bar.low) && Number.isFinite(bar.close) &&
        bar.open > 0 && bar.high > 0 && bar.low > 0 && bar.close > 0 &&
        bar.high >= Math.max(bar.open, bar.close) &&
        bar.low <= Math.min(bar.open, bar.close)
      ))
      .sort((a, b) => a.date.localeCompare(b.date));
  },
};
