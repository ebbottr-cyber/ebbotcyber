import { describe, expect, it } from 'vitest';
import {
  normalizeResearchSymbol, validateAgentReport, validateStrategyReport,
  validateSignalFeed, validateAgentWeights, validateStrategyCatalog,
  validateDecisionFeed, type ResearchRequest,
} from './cryptoResearch';

const request: ResearchRequest = { market: 'spot', symbol: 'BTC/USDT', timeframe: '1h' };
const AGENTS = [
  'trend', 'scalping', 'momentum', 'mean_reversion',
  'breakout', 'intraday', 'swing', 'volume', 'orderbook',
];
const STRATEGIES = [
  'scalping', 'intraday', 'swing', 'trend_following',
  'mean_reversion', 'momentum', 'breakout',
];

const analysis = () => ({
  market: 'spot', symbol: 'BTC/USDT', timeframe: '1h',
  action: 'HOLD', confidence: 0, agreement: 0, votes: { buy: 0, sell: 0, hold: 9 },
  agents: AGENTS.map(agent => ({
    agent, action: 'HOLD', confidence: 0, rationale: 'No signal',
    regime_weight: 1, performance_weight: 1,
  })),
  market_regime: 'range_bound', news_context: { risk_level: 'unknown', article_count: 0 },
  last_close: 80000, candle_timestamp: Date.now() - 60_000,
  journal_recorded: 0, audit_id: 11,
  engine: 'deterministic_ensemble', training: false, risk_approved: false,
  execution: 'disabled', orders_placed: false, checked_at: new Date().toISOString(),
});

const strategy = () => ({
  market: 'spot', symbol: 'BTC/USDT', timeframe: '1h', strategy: 'trend_following',
  action: 'HOLD', confidence: 0, rationale: 'Insufficient alignment',
  entry_reference: 80000, stop_reference: null, take_profit_reference: null,
  risk_reward: null, candle_timestamp: Date.now() - 60_000,
  risk_approved: false, execution: 'disabled', orders_placed: false,
  audit_id: 12, checked_at: new Date().toISOString(),
});

describe('EBBot crypto research contracts', () => {
  it('validates exactly nine non-executable agents and audit presence', () => {
    const result = validateAgentReport(analysis(), request);
    expect(result.agents).toHaveLength(9);
    expect(result.audit_id).toBe(11);
    expect(result.risk_approved).toBe(false);
    expect(result.orders_placed).toBe(false);
  });

  it('rejects live or risky response and missing agents', () => {
    expect(() => validateAgentReport({ ...analysis(), execution: 'enabled' }, request)).toThrow();
    expect(() => validateAgentReport({ ...analysis(), risk_approved: true }, request)).toThrow();
    expect(() => validateAgentReport({ ...analysis(), orders_placed: true }, request)).toThrow();
    expect(() => validateAgentReport({ ...analysis(), audit_id: 0 }, request)).toThrow();
    expect(() => validateAgentReport({ ...analysis(), symbol: 'ETH/USDT' }, request)).toThrow();
    expect(() => validateAgentReport({ ...analysis(), agents: [] }, request)).toThrow();
    expect(() => validateAgentReport({ ...analysis(), votes: { buy: 5, sell: 5, hold: 5 } }, request)).toThrow();
  });

  it('keeps futures contract identity separated from spot', () => {
    expect(normalizeResearchSymbol('futures', 'btc/usdt')).toBe('BTC/USDT');
    expect(() => normalizeResearchSymbol('futures', 'BTC/USDC')).toThrow();
    expect(() => normalizeResearchSymbol('futures', 'BTC/USDT:USDT')).toThrow();
    expect(() => validateAgentReport({
      ...analysis(), market: 'futures', symbol: 'BTC/USDT',
    }, { ...request, market: 'futures' })).toThrow();
  });

  it('only accepts strategy research without execution rights', () => {
    expect(validateStrategyReport(strategy(), request, 'trend_following').audit_id).toBe(12);
    expect(() => validateStrategyReport({ ...strategy(), audit_id: 0 }, request, 'trend_following')).toThrow();
    expect(() => validateStrategyReport({ ...strategy(), stop_reference: -10 }, request, 'trend_following')).toThrow();
    expect(() => validateStrategyReport({ ...strategy(), execution: 'paper' }, request, 'trend_following')).toThrow();
  });

  it('rejects fake or non-journal signal records', () => {
    const feed = {
      signals: [{
        id: 'one', created_at: new Date().toISOString(), market: 'spot',
        symbol: 'BTC/USDT', timeframe: '1h', agent: 'trend', action: 'BUY',
        confidence: .65, entry_price: 80000, exit_price: null,
        outcome: null, pnl_pct: null, strategy_name: 'trend_following',
      }],
      count: 1, total_matching: 1, market: null, mode: 'journal_only',
      execution: 'disabled', orders_placed: false,
    };
    expect(validateSignalFeed(feed).count).toBe(1);
    expect(() => validateSignalFeed({ ...feed, orders_placed: true })).toThrow();
    expect(() => validateSignalFeed({ ...feed, mode: 'paper_order' })).toThrow();
  });

  it('weights require closed-signal method and safe range', () => {
    const weights = {
      weights: { trend: 1.1 }, min_samples: 10,
      method: 'closed_signal_outcomes_with_sample_shrinkage',
      training: false, orders_placed: false,
    };
    expect(validateAgentWeights(weights).weights.trend).toBe(1.1);
    expect(() => validateAgentWeights({ ...weights, training: true })).toThrow();
    expect(() => validateAgentWeights({ ...weights, weights: { trend: 3 } })).toThrow();
  });

  it('requires all seven research strategies', () => {
    const catalog = {
      strategies: STRATEGIES.map(name => ({ name, description: 'Research only' })),
      mode: 'research_only', orders_placed: false,
    };
    expect(validateStrategyCatalog(catalog).strategies).toHaveLength(7);
    expect(() => validateStrategyCatalog({ ...catalog, orders_placed: true })).toThrow();
    expect(() => validateStrategyCatalog({ ...catalog, strategies: [] })).toThrow();
  });

  it('validates HOLD-inclusive immutable decision audit', () => {
    const feed = {
      decisions: [{
        id: 10, created_at: new Date().toISOString(), decision_kind: 'ensemble',
        market: 'spot', symbol: 'BTC/USDT', timeframe: '1h',
        action: 'HOLD', confidence: 0, candle_timestamp: Date.now() - 60_000,
        journal_recorded: 0, risk_approved: false, orders_placed: false,
      }],
      count: 1, orders_placed: false,
    };
    expect(validateDecisionFeed(feed).decisions[0].action).toBe('HOLD');
    expect(() => validateDecisionFeed({ ...feed, orders_placed: true })).toThrow();
    expect(() => validateDecisionFeed({
      ...feed, decisions: [{ ...feed.decisions[0], risk_approved: true }],
    })).toThrow();
  });
});
