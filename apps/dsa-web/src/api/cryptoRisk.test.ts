import { describe, expect, it } from 'vitest';
import {
  validateRiskHistory, validateRiskLimits, validateRiskReview,
  type CryptoRiskProposal,
} from './cryptoRisk';

const proposal: CryptoRiskProposal = {
  market: 'spot', symbol: 'BTC/USDT', side: 'BUY',
  entry_price: 100, stop_price: 95, take_profit_price: 115,
  risk_percent: .5, leverage: 1,
};
const report = () => ({
  status: 'REVIEW_ONLY', risk_review_passed: true,
  reasons: ['Araştırma için sınırlar içinde; işlem onayı değildir.'],
  market: 'spot', symbol: 'BTC/USDT', side: 'BUY',
  paper_account_equity: 10000,
  daily_realized_pnl: 0,
  risk_budget: 50, estimated_position_notional: 900,
  estimated_quantity: 9, estimated_loss_with_costs: 48,
  estimated_round_trip_fee: 1.8,
  estimated_round_trip_slippage: .9,
  estimated_one_period_funding_reserve: 0,
  estimated_margin: 900, net_risk_reward: 2.5,
  estimated_aggregate_risk_pct: .48,
  estimated_combined_risk_pct: .24,
  combined_daily_loss_basis_pnl: 0,
  upstream_risk_multiplier: 1,
  liquidation_proxy_distance_pct: null,
  limits: { max_leverage: 5, max_risk_per_trade_pct: 2 },
  assumptions: ['Research only'],
  risk_approved: false,
  paper_execution_permitted: false,
  real_exchange_orders: false,
  execution: 'disabled',
  checked_at: new Date().toISOString(),
  audit_id: 3,
});

describe('EBBot crypto risk preflight contract', () => {
  it('accepts research-only risk preview and persistent audit ID', () => {
    const result = validateRiskReview(report(), proposal);
    expect(result.status).toBe('REVIEW_ONLY');
    expect(result.paper_execution_permitted).toBe(false);
    expect(result.risk_approved).toBe(false);
    expect(result.audit_id).toBe(3);
  });

  it('never accepts an order authorization disguised as a risk review', () => {
    expect(() => validateRiskReview({ ...report(), risk_approved: true }, proposal)).toThrow();
    expect(() => validateRiskReview({ ...report(), paper_execution_permitted: true }, proposal)).toThrow();
    expect(() => validateRiskReview({ ...report(), real_exchange_orders: true }, proposal)).toThrow();
    expect(() => validateRiskReview({ ...report(), execution: 'enabled' }, proposal)).toThrow();
    expect(() => validateRiskReview({ ...report(), audit_id: 0 }, proposal)).toThrow();
  });

  it('refuses mismatched symbol or incomplete accounting', () => {
    expect(() => validateRiskReview({ ...report(), symbol: 'ETH/USDT' }, proposal)).toThrow();
    expect(() => validateRiskReview({ ...report(), risk_budget: null }, proposal)).toThrow();
    expect(() => validateRiskReview({ ...report(), daily_realized_pnl: NaN }, proposal)).toThrow();
    expect(() => validateRiskReview({ ...report(), estimated_loss_with_costs: -1 }, proposal)).toThrow();
    expect(() => validateRiskReview({ ...report(), checked_at: '2020-01-01T00:00:00Z' }, proposal)).toThrow();
  });

  it('requires consistent blocked flags and reasons', () => {
    const blocked = {
      ...report(), status: 'BLOCKED', risk_review_passed: false,
      reasons: ['spot_daily_loss_limit'],
    };
    expect(validateRiskReview(blocked, proposal).status).toBe('BLOCKED');
    expect(() => validateRiskReview({
      ...blocked, risk_review_passed: true,
    }, proposal)).toThrow();
  });

  it('only accepts bounded non-executable risk history', () => {
    const history = {
      reviews: [{
        id: 2, created_at: new Date().toISOString(), market: 'spot',
        symbol: 'BTC/USDT', status: 'BLOCKED',
        reasons: ['daily_loss_limit'], risk_review_passed: false,
        paper_execution_permitted: false, real_exchange_orders: false,
      }],
      count: 1, paper_execution_permitted: false, real_exchange_orders: false,
    };
    expect(validateRiskHistory(history).reviews[0].status).toBe('BLOCKED');
    expect(() => validateRiskHistory({
      ...history, reviews: [{ ...history.reviews[0], paper_execution_permitted: true }],
    })).toThrow();
  });

  it('validates immutable upper limits', () => {
    const limits = {
      limits: { max_leverage: 5, max_risk_per_trade_pct: 2 },
      mode: 'risk_research_only', risk_approved: false,
      paper_execution_permitted: false, real_exchange_orders: false,
    };
    expect(validateRiskLimits(limits).limits.max_leverage).toBe(5);
    expect(() => validateRiskLimits({ ...limits, risk_approved: true })).toThrow();
    expect(() => validateRiskLimits({ ...limits, limits: {} })).toThrow();
  });
});
