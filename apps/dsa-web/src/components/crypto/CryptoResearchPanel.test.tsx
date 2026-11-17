import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { cryptoResearchApi } from '../../api/cryptoResearch';
import { CryptoResearchPanel } from './CryptoResearchPanel';

vi.mock('../../api/cryptoResearch', async importOriginal => {
  const original = await importOriginal<typeof import('../../api/cryptoResearch')>();
  return {
    ...original,
    cryptoResearchApi: {
      catalog: vi.fn(), journal: vi.fn(), weights: vi.fn(),
      analyze: vi.fn(), strategy: vi.fn(), decisions: vi.fn(),
    },
  };
});

const STRATEGIES = [
  'scalping', 'intraday', 'swing', 'trend_following',
  'mean_reversion', 'momentum', 'breakout',
];
const AGENTS = [
  'trend', 'scalping', 'momentum', 'mean_reversion',
  'breakout', 'intraday', 'swing', 'volume', 'orderbook',
];

const result = () => ({
  market: 'spot', symbol: 'BTC/USDT', timeframe: '1h',
  action: 'HOLD', confidence: 0, agreement: 0,
  votes: { buy: 0, sell: 0, hold: 9 },
  agents: AGENTS.map(agent => ({
    agent, action: 'HOLD', confidence: 0, rationale: 'No trade confirmation.',
    regime_weight: 1, performance_weight: 1,
  })),
  market_regime: 'range_bound', news_context: { risk_level: 'unknown', article_count: 0 },
  last_close: 80000, candle_timestamp: Date.now() - 60000,
  journal_recorded: 0, audit_id: 29,
  engine: 'deterministic_ensemble', training: false, risk_approved: false,
  execution: 'disabled', orders_placed: false, checked_at: new Date().toISOString(),
});

describe('EBBot manually triggered crypto research UI', () => {
  beforeEach(() => {
    vi.mocked(cryptoResearchApi.catalog).mockReset().mockResolvedValue({
      strategies: STRATEGIES.map(name => ({ name, description: 'Research only.' })),
      mode: 'research_only', orders_placed: false,
    } as never);
    vi.mocked(cryptoResearchApi.journal).mockReset().mockResolvedValue({
      signals: [], count: 0, total_matching: 0,
      mode: 'journal_only', orders_placed: false, execution: 'disabled',
    } as never);
    vi.mocked(cryptoResearchApi.weights).mockReset().mockResolvedValue({
      weights: {}, min_samples: 10,
      method: 'closed_signal_outcomes_with_sample_shrinkage',
      training: false, orders_placed: false,
    } as never);
    vi.mocked(cryptoResearchApi.analyze).mockReset().mockResolvedValue(result() as never);
    vi.mocked(cryptoResearchApi.strategy).mockReset().mockResolvedValue({
      ...result(), strategy: 'trend_following', rationale: 'No trend',
      entry_reference: 80000, stop_reference: null,
      take_profit_reference: null, risk_reward: null,
    } as never);
    vi.mocked(cryptoResearchApi.decisions).mockReset().mockResolvedValue({
      decisions: [{
        id: 29, created_at: new Date().toISOString(), decision_kind: 'ensemble',
        market: 'spot', symbol: 'BTC/USDT', timeframe: '1h',
        action: 'HOLD', confidence: 0, candle_timestamp: Date.now() - 60_000,
        journal_recorded: 0, risk_approved: false, orders_placed: false,
      }],
      count: 1, orders_placed: false,
    } as never);
  });

  it('never auto-runs an analysis when the page loads', async () => {
    render(<CryptoResearchPanel view="analysis" />);
    await screen.findByRole('button', { name: 'Stratejiyi değerlendir' });
    expect(cryptoResearchApi.analyze).not.toHaveBeenCalled();
    expect(cryptoResearchApi.strategy).not.toHaveBeenCalled();
    expect(screen.getAllByText(/risk onayı|merkezî risk/i).length).toBeGreaterThan(0);
  });

  it('requires a manual click, displays nine independent HOLD votes and audit id', async () => {
    render(<CryptoResearchPanel view="analysis" />);
    fireEvent.click(screen.getByRole('button', { name: '9 Ajanı Çalıştır' }));
    await waitFor(() => expect(cryptoResearchApi.analyze).toHaveBeenCalledWith({
      market: 'spot', symbol: 'BTC/USDT', timeframe: '1h',
    }));
    expect(await screen.findByText(/EBBot karar kayıt no: 29/)).toBeInTheDocument();
    expect(screen.getByText('AL 0 · SAT 0 · BEKLE 9')).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /Emir ver|Pozisyon aç|Canlı işlem/ })).not.toBeInTheDocument();
  });


  it('shows signal journal and HOLD-inclusive audit without running agents', async () => {
    render(<CryptoResearchPanel view="signals" />);
    await waitFor(() => expect(cryptoResearchApi.decisions).toHaveBeenCalledOnce());
    expect(await screen.findByText(/EBBot AI karar günlüğü/)).toBeInTheDocument();
    expect(await screen.findByText('29')).toBeInTheDocument();
    expect(cryptoResearchApi.analyze).not.toHaveBeenCalled();
  });

  it('calculates weights from historical closed signals without training', async () => {
    render(<CryptoResearchPanel view="agents" />);
    await waitFor(() => expect(cryptoResearchApi.weights).toHaveBeenCalledOnce());
    expect(screen.getByText(/model eğitimi/i)).toBeInTheDocument();
    expect(cryptoResearchApi.analyze).not.toHaveBeenCalled();
  });
});
