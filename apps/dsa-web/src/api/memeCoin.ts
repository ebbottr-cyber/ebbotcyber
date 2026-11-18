import apiClient from './index';
import { toCamelCase } from './utils';

export type MemeCoinStrategyId = 'new_launch' | 'momentum' | 'robinhood_chain';
export type SolanaMemeCoinStrategyId = Exclude<MemeCoinStrategyId, 'robinhood_chain'>;

export type MemeCoinStrategy = {
  id: MemeCoinStrategyId;
  name: string;
  market: 'solana' | 'robinhood_chain';
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

export type RobinhoodRpcStatus = {
  network: 'testnet' | 'mainnet' | 'unknown';
  chainIdExpected: number | null;
  chainIdSeen: number | null;
  blockNumber: number | null;
  status: 'disabled' | 'ok' | 'unavailable' | 'mismatch';
  checkedAt: string | null;
  error: string | null;
  tradingEnabled: false;
};

export type MemeCoinCandidate = {
  strategy: SolanaMemeCoinStrategyId;
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
  strategy: SolanaMemeCoinStrategyId;
  status: 'disabled' | 'ok' | 'unavailable';
  source: 'geckoterminal';
  observedAt: string | null;
  candidates: MemeCoinCandidate[];
  error: string | null;
};

export const memeCoinApi = {
  async getRobinhoodStatus(): Promise<RobinhoodRpcStatus> {
    const { data } = await apiClient.get('/api/v1/meme-coins/robinhood/status');
    return toCamelCase<RobinhoodRpcStatus>(data);
  },
  async scanCandidates(strategy: SolanaMemeCoinStrategyId): Promise<MemeCoinDiscoveryResponse> {
    const { data } = await apiClient.get('/api/v1/meme-coins/candidates', { params: { strategy } });
    return toCamelCase<MemeCoinDiscoveryResponse>(data);
  },
  async getOverview(): Promise<MemeCoinOverview> {
    const { data } = await apiClient.get('/api/v1/meme-coins/overview');
    return toCamelCase<MemeCoinOverview>(data);
  },
};
