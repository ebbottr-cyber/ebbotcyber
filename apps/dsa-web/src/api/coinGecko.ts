import apiClient from './index';

export type CoinGeckoCoin = {
  id: string; name: string; symbol: string; market_cap_rank: number | null;
  current_price: number | null; market_cap: number | null; total_volume: number | null;
  price_change_percentage_24h: number | null;
};

export type CoinGeckoRoster = {
  source: 'CoinGecko'; market: 'crypto'; vs_currency: 'usd';
  count: number; target_count: 100; as_of: string;
  cached: boolean; stale: boolean; coins: CoinGeckoCoin[];
};

export type CoinGeckoTechnical = {
  coin: Pick<CoinGeckoCoin, 'id' | 'name' | 'symbol'>;
  source: 'CoinGecko'; strategy: string; as_of: string; last_completed_day: string;
  daily_bars: number; score: number; signal: string; trend: string;
  macd_status: string; rsi_status: string; rsi_12: number;
  ma5: number; ma10: number; ma20: number; bias_ma5: number;
  volume_ratio_5d: number; support_levels: number[];
  resistance_levels: number[]; cached: boolean; limitations: string[];
};

export function validateCoinGeckoRoster(raw: unknown): CoinGeckoRoster {
  if (!raw || typeof raw !== 'object' || Array.isArray(raw)) {
    throw new Error('CoinGecko listesi geçersiz.');
  }
  const value = raw as Record<string, unknown>;
  if (value.source !== 'CoinGecko' || value.market !== 'crypto' || value.vs_currency !== 'usd' ||
      value.count !== 100 || value.target_count !== 100 || typeof value.as_of !== 'string' ||
      typeof value.cached !== 'boolean' || typeof value.stale !== 'boolean' ||
      !Array.isArray(value.coins) || value.coins.length !== 100) {
    throw new Error('CoinGecko Top 100 listesi eksik veya geçersiz.');
  }
  const seen = new Set<string>();
  for (const item of value.coins) {
    if (!item || typeof item !== 'object' || Array.isArray(item)) throw new Error('Geçersiz coin kaydı.');
    const coin = item as Record<string, unknown>;
    if (typeof coin.id !== 'string' || !/^[a-z0-9][a-z0-9-]{0,119}$/.test(coin.id) ||
        seen.has(coin.id) || typeof coin.name !== 'string' || !coin.name.trim() ||
        typeof coin.symbol !== 'string' || !coin.symbol.trim()) {
      throw new Error('CoinGecko kimliği eksik veya tekrarlı.');
    }
    seen.add(coin.id);
  }
  return value as CoinGeckoRoster;
}

export const coinGeckoApi = {
  async getTop100(): Promise<CoinGeckoRoster> {
    const res = await apiClient.get<unknown>('/api/v1/crypto/top100');
    return validateCoinGeckoRoster(res.data);
  },
  async getTechnical(id: string): Promise<CoinGeckoTechnical> {
    if (!/^[a-z0-9][a-z0-9-]{0,119}$/.test(id)) throw new Error('Geçersiz CoinGecko kimliği.');
    const res = await apiClient.get<CoinGeckoTechnical>('/api/v1/crypto/' + encodeURIComponent(id) + '/technical');
    return res.data;
  },
};
