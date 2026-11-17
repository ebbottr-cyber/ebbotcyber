import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { cryptoRiskApi } from '../../api/cryptoRisk';
import { CryptoRiskPanel } from './CryptoRiskPanel';

vi.mock('../../api/cryptoRisk', () => ({
  cryptoRiskApi: {
    limits: vi.fn(), history: vi.fn(), review: vi.fn(),
  },
}));

function fill() {
  fireEvent.change(screen.getByLabelText('Giriş referansı (USDT)'), {
    target: { value: '100' },
  });
  fireEvent.change(screen.getByLabelText('Stop Loss (USDT)'), {
    target: { value: '95' },
  });
  fireEvent.change(screen.getByLabelText('Take Profit (USDT)'), {
    target: { value: '115' },
  });
}

describe('EBBot crypto risk research UI', () => {
  beforeEach(() => {
    vi.mocked(cryptoRiskApi.limits).mockReset().mockResolvedValue({
      limits: {
        max_risk_per_trade_pct: 2,
        max_aggregate_risk_pct: 2,
        max_leverage: 5,
        max_gross_futures_pct: 100,
        max_directional_futures_pct: 70,
        daily_loss_ceiling_usdt: 200,
      },
      mode: 'risk_research_only', risk_approved: false,
      paper_execution_permitted: false, real_exchange_orders: false,
    } as never);
    vi.mocked(cryptoRiskApi.history).mockReset().mockResolvedValue({
      reviews: [], count: 0, paper_execution_permitted: false,
    } as never);
    vi.mocked(cryptoRiskApi.review).mockReset().mockResolvedValue({
      status: 'REVIEW_ONLY', risk_review_passed: true,
      reasons: ['Sınırlar içinde; emir izni verilmez.'],
      market: 'spot', symbol: 'BTC/USDT', side: 'BUY',
      paper_account_equity: 10000,
      risk_budget: 50, estimated_position_notional: 900,
      estimated_loss_with_costs: 47,
      estimated_round_trip_fee: 1.8,
      estimated_round_trip_slippage: .9,
      estimated_one_period_funding_reserve: 0,
      estimated_margin: 900, net_risk_reward: 2.5,
      risk_approved: false,
      paper_execution_permitted: false,
      real_exchange_orders: false, execution: 'disabled',
      audit_id: 13,
    } as never);
  });

  it('does not compute preflight or place orders merely by opening tab', async () => {
    render(<CryptoRiskPanel />);
    await screen.findByText(/2x/);
    expect(cryptoRiskApi.review).not.toHaveBeenCalled();
    expect(screen.getByRole('button', { name: /Risk ön kontrolünü çalıştır/ })).toBeDisabled();
    expect(screen.queryByRole('button', { name: /Emir gönder|Canlı işlem|Pozisyon aç/ })).not.toBeInTheDocument();
  });

  it('manually starts risk preflight without making any transaction', async () => {
    render(<CryptoRiskPanel />);
    fill();
    fireEvent.click(screen.getByRole('button', { name: /Risk ön kontrolünü çalıştır/ }));
    await waitFor(() => expect(cryptoRiskApi.review).toHaveBeenCalledWith({
      market: 'spot', symbol: 'BTC/USDT', side: 'BUY', entry_price: 100,
      stop_price: 95, take_profit_price: 115, risk_percent: .5,
      leverage: 1,
    }));
    expect(await screen.findByText('Denetim no: 13')).toBeInTheDocument();
    expect(screen.getByText(/Paper işlem izni: YOK/)).toBeInTheDocument();
  });

  it('keeps Spot and Futures leverage and order sides separate', async () => {
    render(<CryptoRiskPanel />);
    fireEvent.change(screen.getByLabelText('Piyasa'), { target: { value: 'futures' } });
    fireEvent.change(screen.getByLabelText('Yön'), { target: { value: 'SELL' } });
    fireEvent.change(screen.getByLabelText('Kaldıraç'), { target: { value: '4' } });
    fill();
    fireEvent.click(screen.getByRole('button', { name: /Risk ön kontrolünü çalıştır/ }));
    await waitFor(() => expect(cryptoRiskApi.review).toHaveBeenCalledWith(expect.objectContaining({
      market: 'futures', side: 'SELL', leverage: 4,
    })));
  });

  it('clears stale review on changed inputs and failed source calls', async () => {
    render(<CryptoRiskPanel />);
    fill();
    fireEvent.click(screen.getByRole('button', { name: /Risk ön kontrolünü çalıştır/ }));
    await screen.findByText('Denetim no: 13');
    fireEvent.change(screen.getByLabelText('Stop Loss (USDT)'), {
      target: { value: '93' },
    });
    expect(screen.queryByText('Denetim no: 13')).not.toBeInTheDocument();
    vi.mocked(cryptoRiskApi.review).mockRejectedValueOnce(Error('source down'));
    fireEvent.click(screen.getByRole('button', { name: /Risk ön kontrolünü çalıştır/ }));
    expect(await screen.findByRole('alert')).toHaveTextContent('Risk değerlendirmesi engellendi');
    expect(screen.queryByText('Denetim no: 13')).not.toBeInTheDocument();
  });
});
