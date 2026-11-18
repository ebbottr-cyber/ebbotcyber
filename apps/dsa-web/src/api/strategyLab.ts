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


export type PaperJournalEvent = {
  session: string;
  paperFill: 'BUY' | 'SELL' | null;
  paperInvested: boolean;
  signalRecorded: boolean;
  equity: number;
};

export type PaperJournalSummary = {
  status: 'PAPER_ONLY';
  researchOnly: true;
  source: string;
  assetCode: string;
  recordCount: number;
  firstSession: string;
  lastSession: string;
  lastObservedAtUtc: string;
  lastEquity: number;
  observedReturnPct: number;
  observedMaxDrawdownPct: number;
  paperBuyCount: number;
  paperSellCount: number;
  invested: boolean;
  nextExpectedSession: string;
  events: PaperJournalEvent[];
  verifiedHashChain: true;
  note: string;
};

export async function inspectPaperJournal(journalJsonl: string): Promise<PaperJournalSummary> {
  const { data } = await apiClient.post<Record<string, unknown>>('/api/v1/strategy-lab/paper/inspect', {
    journal_jsonl: journalJsonl,
  });
  return toCamelCase<PaperJournalSummary>(data);
}
