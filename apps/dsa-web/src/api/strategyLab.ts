import apiClient from './index';
import { toCamelCase } from './utils';

export type TimingBenchmark = {
  observedReturnPct: number;
  observedMaxDrawdownPct: number;
  randomMedianReturnPct: number;
  randomP05ReturnPct: number;
  randomP95ReturnPct: number;
  randomMedianMaxDrawdownPct: number;
  fractionRandomAtLeastObserved: number;
  buyAndHoldReturnPct: number;
  entryCount: number;
  exposureBars: number;
  totalBars: number;
  simulations: number;
  distinctRandomSchedules: number;
  informative: boolean;
  seed: number;
};

export type EtfStrategyResearch = {
  assetCode: string;
  strategy: 'single_etf_vs_cash';
  researchOnly: true;
  dataSource: string;
  historyStart: string;
  historyEnd: string;
  lookbackDays: number;
  rebalance: string;
  feeBps: number;
  slippageBps: number;
  result: TimingBenchmark;
};

export const strategyLabApi = {
  eligibleEtfs: async (): Promise<string[]> => {
    const { data } = await apiClient.get<{ items: string[] }>('/api/v1/strategy-lab/etfs');
    return data.items;
  },
  analyzeEtf: async (assetCode: string, simulations: number): Promise<EtfStrategyResearch> => {
    const { data } = await apiClient.post<Record<string, unknown>>('/api/v1/strategy-lab/etf', {
      asset_code: assetCode,
      simulations,
    });
    return toCamelCase<EtfStrategyResearch>(data);
  },
};
