import apiClient from './index';

export type PaperMarket = 'spot' | 'futures';
export type PaperPosition = {
  market: PaperMarket;
  symbol: string; side: 'BUY' | 'LONG' | 'SHORT';
  quantity: number;
  mark_price: number | null;
  unrealized_pnl: number | null;
  notional: number | null;
  average_price?: number;
  entry_price?: number;
  leverage?: number;
  margin?: number;
  funding_paid?: number;
  entry_fee?: number;
  opened_at?: string;
  estimated_liquidation_price?: number | null;
};
export type PaperAccount = {
  mode: 'paper_only';
  market: PaperMarket;
  equity: number | null;
  realized_pnl: number;
  unrealized_pnl: number | null;
  valuation_complete: boolean;
  positions: PaperPosition[];
  cash?: number;
  wallet_balance?: number;
  used_initial_margin?: number;
  order_count?: number;
  trades?: unknown[];
};
export type PaperPerformancePeriod = {
  realized_net_pnl: number;
  event_count: number;
  since_utc: string;
};
export type PaperSummary = {
  mode: 'paper_only';
  source: 'Trading Office existing SQLite ledgers';
  spot: PaperAccount;
  futures: PaperAccount;
  performance: {
    daily: PaperPerformancePeriod;
    weekly: PaperPerformancePeriod;
    monthly: PaperPerformancePeriod;
  };
  combined_equity: number | null;
  valuation_complete: boolean;
  checked_at: string;
  safety: PaperSafety;
  note: string;
};
export type PaperEvent = {
  id: string;
  market: PaperMarket;
  source: 'spot_ledger' | 'futures_ledger' | 'trade_lifecycle';
  symbol: string;
  action: string;
  created_at: string;
  price: number | null;
  fee: number | null;
  event_pnl: number;
};
export type PaperSafety = {
  orders_placed: false;
  paper_execution_permitted: false;
  real_exchange_orders: false;
  execution: 'disabled';
};
export type PaperV2Capabilities = {
  upstream_v2_present: true;
  upstream_v2_opted_in: boolean;
  source_state: 'SOURCE_INSTALLED_DISABLED' | 'SOURCE_FLAG_ON_UNVERIFIED';
  source_claims_atomic_risk_gate: true;
  readiness_verified: false;
  ebbot_paper_execution_permitted: false;
  real_exchange_orders: false;
  execution: 'disabled';
  note: string;
  checked_at: string;
};

export type PaperHistory = {
  mode: 'paper_only';
  source: 'Trading Office existing SQLite ledgers';
  events: PaperEvent[];
  count: number;
  market_filter: PaperMarket | null;
  checked_at: string;
  safety: PaperSafety;
};

const obj = (v: unknown): v is Record<string, unknown> =>
  v !== null && typeof v === 'object' && !Array.isArray(v);
const finite = (v: unknown): v is number => typeof v === 'number' && Number.isFinite(v);
const nonnegative = (v: unknown): v is number => finite(v) && v >= 0;
const validSymbol = (v: unknown, market: PaperMarket): boolean =>
  typeof v === 'string' &&
  (market === 'futures'
    ? /^[A-Z0-9]{2,20}\/USDT(?::USDT)?$/.test(v)
    : /^[A-Z0-9]{2,20}\/(?:USDT|USDC|BTC|ETH)$/.test(v));
const fresh = (v: unknown) => {
  if (typeof v !== 'string') return false;
  const parsed = Date.parse(v);
  return Number.isFinite(parsed) && Date.now() - parsed < 120_000 && parsed - Date.now() < 300_000;
};
function safe(v: unknown): asserts v is PaperSafety {
  if (!obj(v) || v.orders_placed !== false || v.paper_execution_permitted !== false ||
      v.real_exchange_orders !== false || v.execution !== 'disabled') {
    throw new Error('Paper API yürütme güvenliği doğrulanamadı.');
  }
}
function account(v: unknown, market: PaperMarket): asserts v is PaperAccount {
  if (!obj(v) || v.mode !== 'paper_only' || v.market !== market ||
      typeof v.valuation_complete !== 'boolean' ||
      !finite(v.realized_pnl) ||
      (v.equity !== null && !nonnegative(v.equity)) ||
      (v.unrealized_pnl !== null && !finite(v.unrealized_pnl)) ||
      (v.valuation_complete && (v.equity === null || v.unrealized_pnl === null)) ||
      (!v.valuation_complete && (v.equity !== null || v.unrealized_pnl !== null)) ||
      !Array.isArray(v.positions) || v.positions.length > 300) {
    throw new Error('Sanal hesap doğrulanamadı.');
  }
  for (const p of v.positions) {
    if (!obj(p) || p.market !== market || !validSymbol(p.symbol, market) ||
        !finite(p.quantity) || p.quantity <= 0 ||
        !(p.mark_price === null || (finite(p.mark_price) && p.mark_price > 0)) ||
        !(p.unrealized_pnl === null || finite(p.unrealized_pnl)) ||
        !(p.notional === null || nonnegative(p.notional))) {
      throw new Error('Sanal pozisyon bilgileri geçersiz.');
    }
    if (market === 'futures' && (!['LONG', 'SHORT'].includes(String(p.side)) ||
        !finite(p.entry_price) || p.entry_price <= 0 ||
        !nonnegative(p.margin) || !finite(p.funding_paid) ||
        !Number.isInteger(p.leverage) || (p.leverage as number) > 5)) {
      throw new Error('Futures teminat ve marjin kaydı geçersiz.');
    }
    if (market === 'spot' && (p.side !== 'BUY' ||
        !finite(p.average_price) || p.average_price <= 0)) {
      throw new Error('Spot sanal pozisyon kaydı geçersiz.');
    }
  }
}
export function validatePaperSummary(v: unknown): PaperSummary {
  if (!obj(v) || v.mode !== 'paper_only' ||
      v.source !== 'Trading Office existing SQLite ledgers' ||
      typeof v.valuation_complete !== 'boolean' || !fresh(v.checked_at) ||
      typeof v.note !== 'string' || !obj(v.performance)) {
    throw new Error('Paper Trading özet sözleşmesi geçersiz.');
  }
  safe(v.safety);
  account(v.spot, 'spot');
  account(v.futures, 'futures');
  const combined = v.combined_equity;
  if (v.valuation_complete) {
    if (!nonnegative(combined) || v.spot.equity === null ||
        v.futures.equity === null || Math.abs(combined - v.spot.equity - v.futures.equity) > .01) {
      throw new Error('Spot/Futures sanal özsermaye toplamı tutarsız.');
    }
  } else if (combined !== null) throw new Error('Eksik sanal değerleme sıfır kabul edilemez.');
  for (const period of ['daily', 'weekly', 'monthly']) {
    const item = v.performance[period];
    if (!obj(item) || !finite(item.realized_net_pnl) ||
        !Number.isSafeInteger(item.event_count) || (item.event_count as number) < 0 ||
        typeof item.since_utc !== 'string' || !Number.isFinite(Date.parse(item.since_utc))) {
      throw new Error('Sanal performans raporu hatalı.');
    }
  }
  return v as unknown as PaperSummary;
}
export function validatePaperHistory(v: unknown, market: PaperMarket | null): PaperHistory {
  if (!obj(v) || v.mode !== 'paper_only' ||
      v.source !== 'Trading Office existing SQLite ledgers' ||
      v.market_filter !== market || !fresh(v.checked_at) ||
      !Array.isArray(v.events) || v.events.length > 200 ||
      v.count !== v.events.length) {
    throw new Error('Paper Trading işlem geçmişi eksik veya yanlış.');
  }
  safe(v.safety);
  for (const event of v.events) {
    if (!obj(event) || !['spot', 'futures'].includes(String(event.market)) ||
        (market !== null && event.market !== market) ||
        !['spot_ledger', 'futures_ledger', 'trade_lifecycle'].includes(String(event.source)) ||
        (event.source === 'spot_ledger' && event.market !== 'spot') ||
        (event.source === 'futures_ledger' && event.market !== 'futures') ||
        !validSymbol(event.symbol, event.market as PaperMarket) ||
        typeof event.id !== 'string' ||
        typeof event.action !== 'string' ||
        !Number.isFinite(Date.parse(String(event.created_at))) ||
        !finite(event.event_pnl) ||
        !(event.fee === null || nonnegative(event.fee)) ||
        !(event.price === null || (finite(event.price) && event.price > 0))) {
      throw new Error('Sanal işlem kaydı geçersiz.');
    }
  }
  return v as unknown as PaperHistory;
}

export function validatePaperV2Capabilities(v: unknown): PaperV2Capabilities {
  if (!obj(v) || v.ebbot_paper_execution_permitted !== false ||
      v.real_exchange_orders !== false || v.execution !== 'disabled' ||
      v.upstream_v2_present !== true ||
      typeof v.upstream_v2_opted_in !== 'boolean' ||
      v.source_claims_atomic_risk_gate !== true ||
      v.readiness_verified !== false ||
      !['SOURCE_INSTALLED_DISABLED', 'SOURCE_FLAG_ON_UNVERIFIED'].includes(String(v.source_state)) ||
      (v.upstream_v2_opted_in !== (v.source_state === 'SOURCE_FLAG_ON_UNVERIFIED')) ||
      typeof v.note !== 'string' || !fresh(v.checked_at)) {
    throw new Error('Paper V2 kaynak protokol durumu güvenle doğrulanamadı.');
  }
  return v as unknown as PaperV2Capabilities;
}

export const cryptoPaperApi = {
  async capabilities(): Promise<PaperV2Capabilities> {
    const result = await apiClient.get<unknown>('/api/v1/crypto-office/paper/capabilities');
    return validatePaperV2Capabilities(result.data);
  },
  async summary(): Promise<PaperSummary> {
    const res = await apiClient.get<unknown>('/api/v1/crypto-office/paper/summary', { timeout: 45_000 });
    return validatePaperSummary(res.data);
  },
  async history(market: PaperMarket | null = null): Promise<PaperHistory> {
    const res = await apiClient.get<unknown>('/api/v1/crypto-office/paper/history', {
      params: { limit: 100, ...(market ? { market } : {}) },
      timeout: 25_000,
    });
    return validatePaperHistory(res.data, market);
  },
};
