import apiClient from './index';

export type MemeStrategy = 'new_coin_hunter' | 'momentum_watcher';

export type MemeCandidate = {
  strategy: MemeStrategy;
  mint: string;
  symbol: string;
  pool_id: string;
  source: string;
  score: number;
  status: 'watch' | 'blocked';
  reasons: string[];
};

export type MemeRadarStatus = {
  available: boolean;
  live_enabled: boolean;
  trading_enabled: false;
  strategies: MemeStrategy[];
};

export type MemeScanResponse = {
  enabled: boolean;
  trading_enabled: false;
  candidates: MemeCandidate[];
  errors: { provider: string; mint?: string; message: string }[];
  cached?: boolean;
  disclaimer?: string;
};

export const memeRadarApi = {
  async status(): Promise<MemeRadarStatus> {
    const response = await apiClient.get<MemeRadarStatus>('/api/v1/meme-coins/status');
    return response.data;
  },

  async scan(limit = 5): Promise<MemeScanResponse> {
    const response = await apiClient.post<MemeScanResponse>(
      '/api/v1/meme-coins/scan', { limit }, { timeout: 90000 },
    );
    return response.data;
  },
};
