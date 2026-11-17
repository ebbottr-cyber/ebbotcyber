import { describe, expect, it } from 'vitest';
import { validatePaperHistory, validatePaperSummary, validatePaperV2Capabilities } from './cryptoPaper';

const safe = () => ({
  orders_placed: false, paper_execution_permitted: false,
  real_exchange_orders: false, execution: 'disabled',
});
const summary = () => ({
  mode: 'paper_only', source: 'Trading Office existing SQLite ledgers',
  spot: {
    market: 'spot', mode: 'paper_only', equity: 10001,
    cash: 9900, realized_pnl: 0, unrealized_pnl: 1,
    valuation_complete: true, order_count: 1,
    positions: [{
      market: 'spot', side: 'BUY', symbol: 'BTC/USDT',
      quantity: 1, average_price: 100, mark_price: 101,
      unrealized_pnl: 1, notional: 101,
    }],
  },
  futures: {
    market: 'futures', mode: 'paper_only', equity: 10020,
    wallet_balance: 9550, used_initial_margin: 450,
    realized_pnl: -.45, unrealized_pnl: 20,
    valuation_complete: true, positions: [{
      market: 'futures', symbol: 'BTC/USDT:USDT',
      side: 'LONG', quantity: .1, entry_price: 9000, leverage: 2,
      margin: 450, funding_paid: .2, entry_fee: .45,
      mark_price: 9200, unrealized_pnl: 20, notional: 920,
    }],
    trades: [],
  },
  performance: {
    daily: { realized_net_pnl: -2, event_count: 2, since_utc: new Date().toISOString() },
    weekly: { realized_net_pnl: -2, event_count: 2, since_utc: new Date().toISOString() },
    monthly: { realized_net_pnl: -2, event_count: 2, since_utc: new Date().toISOString() },
  },
  combined_equity: 20021, valuation_complete: true,
  source_was_read_only: true, note: 'Research snapshot only',
  checked_at: new Date().toISOString(), safety: safe(),
});
const history = () => ({
  mode: 'paper_only', source: 'Trading Office existing SQLite ledgers',
  count: 2, market_filter: null, checked_at: new Date().toISOString(),
  safety: safe(),
  events: [
    {
      id: 'funding1', market: 'futures', source: 'futures_ledger',
      symbol: 'BTC/USDT:USDT', action: 'FUNDING',
      created_at: new Date().toISOString(), price: 9200,
      fee: 0, event_pnl: -.2,
    },
    {
      id: 'buy1', market: 'spot', source: 'spot_ledger',
      symbol: 'BTC/USDT', action: 'BUY',
      created_at: new Date().toISOString(), price: 100,
      fee: .1, event_pnl: 0,
    },
  ],
});

describe('EBBot existing Paper Trading view safety contracts', () => {
  it('requires actual existing Spot/Futures paper accounts, not new balances', () => {
    const response = validatePaperSummary(summary());
    expect(response.combined_equity).toBe(20021);
    expect(response.futures.positions[0].funding_paid).toBe(.2);
    expect(response.safety.orders_placed).toBe(false);
    expect(response.safety.paper_execution_permitted).toBe(false);
  });

  it('refuses inconsistent combined valuation or wrong source market', () => {
    expect(() => validatePaperSummary({ ...summary(), combined_equity: 20022 })).toThrow();
    const wrong = summary();
    wrong.futures.market = 'spot';
    expect(() => validatePaperSummary(wrong)).toThrow();
    expect(() => validatePaperSummary({
      ...summary(), source: 'untrusted paper account',
    })).toThrow();
  });

  it('incomplete marks remain unavailable/null, not zero equity', () => {
    const original = summary();
    original.futures.equity = null as never;
    original.futures.unrealized_pnl = null as never;
    original.futures.positions[0].mark_price = null as never;
    original.futures.positions[0].unrealized_pnl = null as never;
    original.futures.positions[0].notional = null as never;
    original.futures.valuation_complete = false;
    original.combined_equity = null as never;
    original.valuation_complete = false;
    expect(validatePaperSummary(original).combined_equity).toBeNull();
    original.combined_equity = 10001 as never;
    expect(() => validatePaperSummary(original)).toThrow();
  });

  it('never accepts real or Paper execution privileges in history', () => {
    expect(validatePaperHistory(history(), null).count).toBe(2);
    expect(() => validatePaperHistory({
      ...history(), safety: { ...safe(), paper_execution_permitted: true },
    }, null)).toThrow();
    expect(() => validatePaperHistory({
      ...history(), safety: { ...safe(), real_exchange_orders: true },
    }, null)).toThrow();
    expect(() => validatePaperHistory({
      ...history(), market_filter: 'spot',
    }, null)).toThrow();
  });

  it('rejects market crossover, fabricated PnL or incomplete events', () => {
    const h = history();
    h.events[0].market = 'spot';
    expect(() => validatePaperHistory(h, null)).toThrow();
    expect(() => validatePaperHistory({
      ...history(), events: [{ ...history().events[0], event_pnl: Number.NaN }],
      count: 1,
    }, null)).toThrow();
    expect(() => validatePaperHistory({
      ...history(), count: 99,
    }, null)).toThrow();
  });

  it('upstream V2 opt-in never grants EBBot Paper execution', () => {
    const source = {
      upstream_v2_present: true, upstream_v2_opted_in: true,
      ebbot_paper_execution_permitted: false,
      real_exchange_orders: false, execution: 'disabled',
      note: 'Source opt-in only',
      checked_at: new Date().toISOString(),
    };
    expect(validatePaperV2Capabilities(source).ebbot_paper_execution_permitted).toBe(false);
    expect(() => validatePaperV2Capabilities({
      ...source, ebbot_paper_execution_permitted: true,
    })).toThrow();
    expect(() => validatePaperV2Capabilities({
      ...source, real_exchange_orders: true,
    })).toThrow();
    expect(() => validatePaperV2Capabilities({
      ...source, upstream_v2_present: false, upstream_v2_opted_in: true,
    })).toThrow();
  });

  it('rejects stale snapshot and unsafe source', () => {
    expect(() => validatePaperSummary({ ...summary(), checked_at: '2020-01-01T00:00:00Z' })).toThrow();
    expect(() => validatePaperSummary({
      ...summary(), safety: { ...safe(), execution: 'enabled' },
    })).toThrow();
  });
});
