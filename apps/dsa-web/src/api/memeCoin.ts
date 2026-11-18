import apiClient from './index';
import { toCamelCase } from './utils';

export type MemeCoinStrategyId = 'new_launch' | 'momentum';

export type MemeCoinStrategy = {
  id: MemeCoinStrategyId;
  name: string;
  market: 'solana';
  dataSources: string[];
  status: 'not_connected';
  engineConnected: boolean;
  paperTradingEnabled: boolean;
  liveTradingEnabled: boolean;
  riskChecks: string[];
  metrics: {
    trades: number | null;
    netPnlUsd: number | null;
    winRatePct: number | null;
  };
};

export type MemeCoinOverview = {
  market: 'solana';
  mode: 'paper_planned';
  liveTradingEnabled: boolean;
  sharedRiskEngineConnected: boolean;
  lastMarketEventAt: string | null;
  strategies: MemeCoinStrategy[];
};

export const memeCoinApi = {
  async getOverview(): Promise<MemeCoinOverview> {
    const { data } = await apiClient.get('/api/v1/meme-coins/overview');
    return toCamelCase<MemeCoinOverview>(data);
  },
};
