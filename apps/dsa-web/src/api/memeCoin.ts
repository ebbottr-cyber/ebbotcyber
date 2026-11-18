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

export type MemeCoinCandidate = {
  strategy: MemeCoinStrategyId;
  symbol: string;
  tokenAddress: string;
  poolAddress: string;
  liquidityUsd: number;
  volume5mUsd: number;
  change5mPct: number;
  ageMinutes: number;
  buys5m: number;
  sells5m: number;
  researchScore: number;
  riskStatus: 'unverified';
  tradable: false;
  source: 'geckoterminal';
};

export type MemeCoinDiscoveryResponse = {
  strategy: MemeCoinStrategyId;
  status: 'disabled' | 'ok' | 'unavailable';
  source: 'geckoterminal';
  observedAt: string | null;
  candidates: MemeCoinCandidate[];
  error: string | null;
};

export const memeCoinApi = {
  async scanCandidates(strategy: MemeCoinStrategyId): Promise<MemeCoinDiscoveryResponse> {
    const { data } = await apiClient.get('/api/v1/meme-coins/candidates', { params: { strategy } });
    return toCamelCase<MemeCoinDiscoveryResponse>(data);
  },
  async getOverview(): Promise<MemeCoinOverview> {
    const { data } = await apiClient.get('/api/v1/meme-coins/overview');
    return toCamelCase<MemeCoinOverview>(data);
  },
};
