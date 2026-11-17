import apiClient from './index';

export type CryptoRiskMarket = 'spot' | 'futures';
export type CryptoRiskSide = 'BUY' | 'SELL';
export type CryptoRiskProposal = {
  market: CryptoRiskMarket;
  symbol: string;
  side: CryptoRiskSide;
  entry_price: number;
  stop_price: number;
  take_profit_price: number;
  risk_percent: number;
  leverage: number;
};

export type CryptoRiskReview = {
  status: 'REVIEW_ONLY' | 'BLOCKED';
  risk_review_passed: boolean;
  reasons: string[];
  market: CryptoRiskMarket;
  symbol: string;
  side: CryptoRiskSide;
  paper_account_equity: number;
  daily_realized_pnl: number;
  risk_budget: number;
  estimated_position_notional: number;
  estimated_quantity: number;
  estimated_loss_with_costs: number;
  estimated_round_trip_fee: number;
  estimated_round_trip_slippage: number;
  estimated_one_period_funding_reserve: number;
  estimated_margin: number;
  net_risk_reward: number | null;
  estimated_aggregate_risk_pct: number;
  liquidation_proxy_distance_pct: number | null;
  limits: Record<string, number>;
  assumptions: string[];
  risk_approved: false;
  paper_execution_permitted: false;
  real_exchange_orders: false;
  execution: 'disabled';
  checked_at: string;
  audit_id: number;
};

export type CryptoRiskHistory = {
  reviews: Array<{
    id: number;
    created_at: string;
    market: CryptoRiskMarket;
    symbol: string;
    status: 'REVIEW_ONLY' | 'BLOCKED';
    reasons: string[];
    risk_review_passed: boolean;
    paper_execution_permitted: false;
    real_exchange_orders: false;
  }>;
  count: number;
  paper_execution_permitted: false;
};

export type CryptoRiskLimits = {
  limits: Record<string, number>;
  mode: 'risk_research_only';
  risk_approved: false;
  paper_execution_permitted: false;
  real_exchange_orders: false;
};

function object(v: unknown): v is Record<string, unknown> {
  return v !== null && typeof v === 'object' && !Array.isArray(v);
}
function number(v: unknown): v is number {
  return typeof v === 'number' && Number.isFinite(v);
}
function positiveInt(v: unknown): v is number {
  return number(v) && Number.isSafeInteger(v) && v > 0;
}
function nonnegative(v: unknown): v is number {
  return number(v) && v >= 0;
}

function safeFlags(raw: unknown): asserts raw is Record<string, unknown> {
  if (!object(raw) || raw.paper_execution_permitted !== false ||
      raw.real_exchange_orders !== false) {
    throw new Error('Kripto risk servisinde yürütme güvenliği doğrulanamadı.');
  }
}

export function validateRiskReview(raw: unknown, proposal: CryptoRiskProposal): CryptoRiskReview {
  safeFlags(raw);
  if (raw.risk_approved !== false || raw.execution !== 'disabled' ||
      !['REVIEW_ONLY', 'BLOCKED'].includes(String(raw.status)) ||
      raw.market !== proposal.market || raw.symbol !== proposal.symbol ||
      raw.side !== proposal.side || !positiveInt(raw.audit_id) ||
      typeof raw.risk_review_passed !== 'boolean' ||
      raw.risk_review_passed !== (raw.status === 'REVIEW_ONLY') ||
      !Array.isArray(raw.reasons) || raw.reasons.length === 0 ||
      raw.reasons.some(x => typeof x !== 'string') ||
      !object(raw.limits) || !Array.isArray(raw.assumptions) ||
      raw.assumptions.some(x => typeof x !== 'string')) {
    throw new Error('Kripto risk değerlendirme yanıtı geçersiz.');
  }
  for (const key of [
    'paper_account_equity', 'risk_budget', 'estimated_position_notional',
    'estimated_quantity', 'estimated_loss_with_costs',
    'estimated_round_trip_fee', 'estimated_round_trip_slippage',
    'estimated_one_period_funding_reserve', 'estimated_margin',
    'estimated_aggregate_risk_pct',
  ]) {
    if (!nonnegative(raw[key])) throw new Error('Risk büyüklükleri geçersiz.');
  }
  if (!number(raw.daily_realized_pnl) ||
      !(raw.net_risk_reward === null || nonnegative(raw.net_risk_reward)) ||
      !(raw.liquidation_proxy_distance_pct === null || number(raw.liquidation_proxy_distance_pct)) ||
      typeof raw.checked_at !== 'string' || !Number.isFinite(Date.parse(raw.checked_at)) ||
      Date.now() - Date.parse(raw.checked_at) > 120_000 ||
      Date.parse(raw.checked_at) - Date.now() > 300_000) {
    throw new Error('Risk verileri eksik veya eski.');
  }
  return raw as unknown as CryptoRiskReview;
}

export function validateRiskHistory(raw: unknown): CryptoRiskHistory {
  safeFlags(raw);
  if (!Array.isArray(raw.reviews) || raw.reviews.length > 100 ||
      raw.count !== raw.reviews.length) throw new Error('Risk geçmişi geçersiz.');
  for (const row of raw.reviews) {
    if (!object(row) || !positiveInt(row.id) ||
        row.paper_execution_permitted !== false || row.real_exchange_orders !== false ||
        !['REVIEW_ONLY', 'BLOCKED'].includes(String(row.status)) ||
        typeof row.risk_review_passed !== 'boolean' ||
        row.risk_review_passed !== (row.status === 'REVIEW_ONLY') ||
        !['spot', 'futures'].includes(String(row.market)) ||
        typeof row.symbol !== 'string' || !Array.isArray(row.reasons)) {
      throw new Error('Risk geçmişindeki kayıt doğrulanamadı.');
    }
  }
  return raw as unknown as CryptoRiskHistory;
}

export function validateRiskLimits(raw: unknown): CryptoRiskLimits {
  safeFlags(raw);
  if (raw.mode !== 'risk_research_only' || raw.risk_approved !== false ||
      !object(raw.limits) || !number(raw.limits.max_leverage) ||
      !number(raw.limits.max_risk_per_trade_pct)) {
    throw new Error('Risk limitleri doğrulanamadı.');
  }
  return raw as unknown as CryptoRiskLimits;
}

export const cryptoRiskApi = {
  async limits(): Promise<CryptoRiskLimits> {
    const r = await apiClient.get<unknown>('/api/v1/crypto-office/risk/limits');
    return validateRiskLimits(r.data);
  },
  async history(): Promise<CryptoRiskHistory> {
    const r = await apiClient.get<unknown>('/api/v1/crypto-office/risk/history', {
      params: { limit: 30 },
    });
    return validateRiskHistory(r.data);
  },
  async review(proposal: CryptoRiskProposal): Promise<CryptoRiskReview> {
    if (!/^[A-Z0-9]{2,20}\/USDT$/.test(proposal.symbol) ||
        !number(proposal.entry_price) || proposal.entry_price <= 0 ||
        !number(proposal.stop_price) || proposal.stop_price <= 0 ||
        !number(proposal.take_profit_price) || proposal.take_profit_price <= 0 ||
        !number(proposal.risk_percent) || proposal.risk_percent <= 0 ||
        proposal.risk_percent > 2 || !Number.isInteger(proposal.leverage) ||
        proposal.leverage < 1 || proposal.leverage > 5 ||
        (proposal.market === 'spot' && (proposal.side !== 'BUY' || proposal.leverage !== 1))) {
      throw new Error('Risk girişlerini kontrol et. İşlem değerlendirmesi başlatılamadı.');
    }
    const r = await apiClient.post<unknown>('/api/v1/crypto-office/risk/review', proposal, {
      timeout: 60_000,
    });
    return validateRiskReview(r.data, proposal);
  },
};
