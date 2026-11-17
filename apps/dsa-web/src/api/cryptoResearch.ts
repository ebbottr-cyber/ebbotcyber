import apiClient from './index';

export type ResearchMarket = 'spot' | 'futures';
export type ResearchTimeframe = '1m' | '5m' | '15m' | '1h' | '4h' | '1d';
export type ResearchAction = 'BUY' | 'SELL' | 'HOLD';
export type ResearchStrategyId =
  | 'scalping' | 'intraday' | 'swing' | 'trend_following'
  | 'mean_reversion' | 'momentum' | 'breakout';

export type ResearchRequest = {
  market: ResearchMarket;
  symbol: string;
  timeframe: ResearchTimeframe;
};
export type AgentVote = {
  agent: string;
  action: ResearchAction;
  confidence: number;
  rationale: string;
  regime_weight: number;
  performance_weight: number;
};
export type AgentReport = {
  market: ResearchMarket;
  symbol: string;
  timeframe: ResearchTimeframe;
  action: ResearchAction;
  confidence: number;
  agreement: number;
  votes: { buy: number; sell: number; hold: number };
  agents: AgentVote[];
  market_regime: string | null;
  news_context: { risk_level: string; article_count: number };
  last_close: number;
  candle_timestamp: number;
  journal_recorded: number;
  audit_id: number;
  engine: 'deterministic_ensemble';
  training: false;
  risk_approved: false;
  execution: 'disabled';
  orders_placed: false;
  checked_at: string;
};
export type StrategyReport = ResearchRequest & {
  strategy: ResearchStrategyId;
  action: ResearchAction;
  confidence: number;
  rationale: string;
  entry_reference: number | null;
  stop_reference: number | null;
  take_profit_reference: number | null;
  risk_reward: number | null;
  candle_timestamp: number;
  audit_id: number;
  risk_approved: false;
  execution: 'disabled';
  orders_placed: false;
  checked_at: string;
};
export type SignalRow = {
  id: string; created_at: string;
  market: ResearchMarket; symbol: string; timeframe: string;
  agent: string; action: 'BUY' | 'SELL'; confidence: number;
  entry_price: number; exit_price: number | null;
  outcome: 'WIN' | 'LOSS' | 'BREAKEVEN' | null;
  pnl_pct: number | null; strategy_name: string;
};
export type SignalFeed = {
  signals: SignalRow[]; count: number; total_matching: number;
  market: ResearchMarket | null; mode: 'journal_only';
  orders_placed: false; execution: 'disabled';
};
export type AgentWeights = {
  weights: Record<string, number>;
  min_samples: number; method: string; training: false; orders_placed: false;
};
export type StrategyCatalog = {
  strategies: { name: ResearchStrategyId; description: string }[];
  mode: 'research_only'; orders_placed: false;
};

export type DecisionFeed = {
  decisions: Array<{
    id: number;
    created_at: string;
    decision_kind: 'ensemble' | 'strategy';
    market: ResearchMarket;
    symbol: string;
    timeframe: string;
    action: ResearchAction;
    confidence: number;
    candle_timestamp: number;
    journal_recorded: number;
    risk_approved: false;
    orders_placed: false;
  }>;
  count: number;
  orders_placed: false;
};

const STRATEGIES = new Set<string>([
  'scalping', 'intraday', 'swing', 'trend_following',
  'mean_reversion', 'momentum', 'breakout',
]);
const AGENTS = new Set<string>([
  'trend', 'scalping', 'momentum', 'mean_reversion',
  'breakout', 'intraday', 'swing', 'volume', 'orderbook',
]);
const ACTIONS = ['BUY', 'SELL', 'HOLD'];
const record = (x: unknown): x is Record<string, unknown> =>
  x !== null && typeof x === 'object' && !Array.isArray(x);
const finite = (x: unknown): x is number =>
  typeof x === 'number' && Number.isFinite(x);
const score = (x: unknown) => finite(x) && x >= 0 && x <= 1;
const nonnegativeInt = (x: unknown): x is number =>
  typeof x === 'number' && Number.isSafeInteger(x) && x >= 0;
const noOrders = (x: unknown): x is Record<string, unknown> =>
  record(x) && x.orders_placed === false;
const checked = (x: unknown) => {
  if (typeof x !== 'string') return false;
  const t = Date.parse(x);
  return Number.isFinite(t) && Date.now() - t < 5 * 60_000 && t - Date.now() < 5 * 60_000;
};

export function normalizeResearchSymbol(market: ResearchMarket, input: string): string {
  const symbol = input.trim().toUpperCase();
  const pattern = market === 'futures'
    ? /^[A-Z0-9]{2,20}\/USDT$/
    : /^[A-Z0-9]{2,20}\/(?:USDT|USDC|BTC|ETH)$/;
  if (!pattern.test(symbol)) throw new Error('Geçerli bir kripto işlem çifti girin.');
  return symbol;
}

export function validateAgentReport(x: unknown, request: ResearchRequest): AgentReport {
  const identity = request.market === 'futures'
    ? request.symbol + ':USDT' : request.symbol;
  if (!noOrders(x) || x.market !== request.market || x.symbol !== identity ||
      x.timeframe !== request.timeframe || x.execution !== 'disabled' ||
      x.engine !== 'deterministic_ensemble' || x.training !== false ||
      x.risk_approved !== false || !checked(x.checked_at) ||
      !ACTIONS.includes(String(x.action)) || !score(x.confidence) ||
      !score(x.agreement) || !finite(x.last_close) || x.last_close <= 0 ||
      !nonnegativeInt(x.candle_timestamp) || x.candle_timestamp === 0 ||
      !nonnegativeInt(x.journal_recorded) || !nonnegativeInt(x.audit_id) || x.audit_id === 0 || !record(x.votes) ||
      !Array.isArray(x.agents) || x.agents.length !== 9) {
    throw new Error('Ajan analizinin güvenlik veya veri sözleşmesi geçersiz.');
  }
  const votes = x.votes;
  if (!nonnegativeInt(votes.buy) || !nonnegativeInt(votes.sell) ||
      !nonnegativeInt(votes.hold) || votes.buy + votes.sell + votes.hold !== 9) {
    throw new Error('Ajan oyları doğrulanamadı.');
  }
  const names = new Set<string>();
  for (const agent of x.agents) {
    if (!record(agent) || !AGENTS.has(String(agent.agent)) ||
        !ACTIONS.includes(String(agent.action)) || !score(agent.confidence) ||
        typeof agent.rationale !== 'string' ||
        !finite(agent.regime_weight) || agent.regime_weight < 0 ||
        !finite(agent.performance_weight) || agent.performance_weight < 0) {
      throw new Error('Bağımsız ajan değerlendirmelerinden biri geçersiz.');
    }
    names.add(String(agent.agent));
  }
  if (names.size !== 9) throw new Error('Bağımsız ajanlar eksik veya tekrar ediyor.');
  if (!record(x.news_context) || typeof x.news_context.risk_level !== 'string' ||
      !nonnegativeInt(x.news_context.article_count)) {
    throw new Error('Haber riski alanı geçersiz.');
  }
  return x as unknown as AgentReport;
}

export function validateStrategyReport(x: unknown, request: ResearchRequest, strategy: ResearchStrategyId): StrategyReport {
  const identity = request.market === 'futures' ? request.symbol + ':USDT' : request.symbol;
  if (!noOrders(x) || x.market !== request.market || x.symbol !== identity ||
      x.timeframe !== request.timeframe || x.strategy !== strategy ||
      x.execution !== 'disabled' || x.risk_approved !== false ||
      !checked(x.checked_at) || !ACTIONS.includes(String(x.action)) ||
      !score(x.confidence) || typeof x.rationale !== 'string' ||
      !nonnegativeInt(x.candle_timestamp) || x.candle_timestamp === 0 ||
      !nonnegativeInt(x.audit_id) || x.audit_id === 0) {
    throw new Error('Strateji analizi veri kontrolünden geçemedi.');
  }
  for (const field of ['entry_reference', 'stop_reference', 'take_profit_reference']) {
    const v = x[field];
    if (v !== null && (!finite(v) || v <= 0)) throw new Error('Strateji fiyat seviyesi geçersiz.');
  }
  if (x.risk_reward !== null && (!finite(x.risk_reward) || x.risk_reward < 0)) {
    throw new Error('Strateji risk/getiri verisi geçersiz.');
  }
  return x as unknown as StrategyReport;
}

export function validateSignalFeed(x: unknown): SignalFeed {
  if (!noOrders(x) || x.mode !== 'journal_only' || x.execution !== 'disabled' ||
      !Array.isArray(x.signals) || !nonnegativeInt(x.count) ||
      !nonnegativeInt(x.total_matching) || x.count !== x.signals.length ||
      x.total_matching < x.count || x.signals.length > 100) {
    throw new Error('Kayıtlı araştırma sinyalleri doğrulanamadı.');
  }
  for (const row of x.signals) {
    if (!record(row) || !['spot', 'futures'].includes(String(row.market)) ||
        !['BUY', 'SELL'].includes(String(row.action)) ||
        typeof row.agent !== 'string' || !score(row.confidence) ||
        !finite(row.entry_price) || row.entry_price <= 0 ||
        (row.pnl_pct !== null && !finite(row.pnl_pct)) ||
        (row.outcome !== null && !['WIN', 'LOSS', 'BREAKEVEN'].includes(String(row.outcome)))) {
      throw new Error('Sinyal günlüğü satırı geçersiz.');
    }
  }
  return x as unknown as SignalFeed;
}

export function validateAgentWeights(x: unknown): AgentWeights {
  if (!noOrders(x) || x.training !== false ||
      x.method !== 'closed_signal_outcomes_with_sample_shrinkage' ||
      !record(x.weights) || !nonnegativeInt(x.min_samples)) {
    throw new Error('Ajan ağırlıkları doğrulanamadı.');
  }
  for (const [name, weight] of Object.entries(x.weights)) {
    if (!AGENTS.has(name) || !finite(weight) || weight < .75 || weight > 1.25) {
      throw new Error('Ajan ağırlığı güvenli aralıkta değil.');
    }
  }
  return x as unknown as AgentWeights;
}

export function validateStrategyCatalog(x: unknown): StrategyCatalog {
  if (!noOrders(x) || x.mode !== 'research_only' ||
      !Array.isArray(x.strategies) || x.strategies.length !== 7) {
    throw new Error('Kripto strateji listesi doğrulanamadı.');
  }
  const names = new Set<string>();
  for (const item of x.strategies) {
    if (!record(item) || !STRATEGIES.has(String(item.name)) ||
        typeof item.description !== 'string') {
      throw new Error('Strateji kimliği geçersiz.');
    }
    names.add(String(item.name));
  }
  if (names.size !== 7) throw new Error('Bazı araştırma stratejileri bulunamadı.');
  return x as unknown as StrategyCatalog;
}

export function validateDecisionFeed(x: unknown): DecisionFeed {
  if (!noOrders(x) || !Array.isArray(x.decisions) ||
      x.decisions.length > 100 || x.count !== x.decisions.length) {
    throw new Error('Kalıcı kripto AI karar günlüğü geçersiz.');
  }
  for (const row of x.decisions) {
    if (!record(row) || !nonnegativeInt(row.id) || row.id === 0 ||
        !['ensemble', 'strategy'].includes(String(row.decision_kind)) ||
        !['spot', 'futures'].includes(String(row.market)) ||
        !ACTIONS.includes(String(row.action)) ||
        !score(row.confidence) || !nonnegativeInt(row.candle_timestamp) ||
        !nonnegativeInt(row.journal_recorded) ||
        row.orders_placed !== false || row.risk_approved !== false ||
        typeof row.symbol !== 'string' || typeof row.timeframe !== 'string') {
      throw new Error('Kripto AI karar günlüğünde doğrulanamayan kayıt var.');
    }
  }
  return x as unknown as DecisionFeed;
}

export const cryptoResearchApi = {
  async decisions(): Promise<DecisionFeed> {
    const response = await apiClient.get<unknown>('/api/v1/crypto-office/research/decisions', {
      params: { limit: 30 },
    });
    return validateDecisionFeed(response.data);
  },
  async catalog(): Promise<StrategyCatalog> {
    const response = await apiClient.get<unknown>('/api/v1/crypto-office/research/strategies');
    return validateStrategyCatalog(response.data);
  },
  async journal(market: ResearchMarket | null = null): Promise<SignalFeed> {
    const response = await apiClient.get<unknown>('/api/v1/crypto-office/research/signals', {
      params: market ? { market, limit: 50 } : { limit: 50 },
    });
    return validateSignalFeed(response.data);
  },
  async weights(): Promise<AgentWeights> {
    const response = await apiClient.get<unknown>('/api/v1/crypto-office/research/weights', {
      params: { min_samples: 10 },
    });
    return validateAgentWeights(response.data);
  },
  async analyze(input: ResearchRequest): Promise<AgentReport> {
    const request = { ...input, symbol: normalizeResearchSymbol(input.market, input.symbol) };
    const response = await apiClient.post<unknown>('/api/v1/crypto-office/research/analyze', request);
    return validateAgentReport(response.data, request);
  },
  async strategy(input: ResearchRequest, strategy: ResearchStrategyId): Promise<StrategyReport> {
    const request = { ...input, symbol: normalizeResearchSymbol(input.market, input.symbol) };
    const response = await apiClient.post<unknown>('/api/v1/crypto-office/research/strategy', {
      ...request, strategy,
    });
    return validateStrategyReport(response.data, request, strategy);
  },
};
