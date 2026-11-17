import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { cryptoPaperApi } from '../../api/cryptoPaper';
import { CryptoPaperPanel } from './CryptoPaperPanel';

vi.mock('../../api/cryptoPaper', () => ({
  cryptoPaperApi: { summary: vi.fn(), history: vi.fn(), capabilities: vi.fn() },
}));

const summary = () => ({
  mode: 'paper_only', source: 'Trading Office existing SQLite ledgers',
  spot: {
    market: 'spot', mode: 'paper_only', equity: 10001,
    cash: 9900, realized_pnl: 0, unrealized_pnl: 1,
    valuation_complete: true, order_count: 0, positions: [{
      market: 'spot', side: 'BUY', symbol: 'BTC/USDT',
      quantity: 1, average_price: 100, mark_price: 101,
      unrealized_pnl: 1, notional: 101,
    }],
  },
  futures: {
    market: 'futures', mode: 'paper_only', equity: 10020,
    wallet_balance: 9550, used_initial_margin: 450,
    realized_pnl: -.45, unrealized_pnl: 20,
    valuation_complete: true,
    positions: [{
      market: 'futures', side: 'LONG', symbol: 'BTC/USDT:USDT',
      quantity: .1, entry_price: 9000, mark_price: 9200,
      unrealized_pnl: 20, notional: 920, margin: 450,
      leverage: 2, funding_paid: .2, entry_fee: .45,
    }],
    trades: [{
      id: 'f1', symbol: 'BTC/USDT:USDT',
      action: 'FUNDING', realized_pnl: -.2,
    }],
  },
  performance: {
    daily: { realized_net_pnl: -2, event_count: 2, since_utc: new Date().toISOString() },
    weekly: { realized_net_pnl: -2, event_count: 2, since_utc: new Date().toISOString() },
    monthly: { realized_net_pnl: -2, event_count: 2, since_utc: new Date().toISOString() },
  },
  combined_equity: 20021, valuation_complete: true,
  checked_at: new Date().toISOString(), safety: {
    orders_placed: false, paper_execution_permitted: false,
    real_exchange_orders: false, execution: 'disabled',
  },
  note: 'Research snapshot only',
});
const history = () => ({
  mode: 'paper_only', count: 2, market_filter: null,
  source: 'Trading Office existing SQLite ledgers',
  checked_at: new Date().toISOString(),
  safety: {
    orders_placed: false, paper_execution_permitted: false,
    real_exchange_orders: false, execution: 'disabled',
  },
  events: [{
    id: 'funding1', market: 'futures', symbol: 'BTC/USDT:USDT',
    source: 'futures_ledger', action: 'FUNDING',
    price: 9200, fee: 0, event_pnl: -.2,
    created_at: new Date().toISOString(),
  }, {
    id: 'buy1', market: 'spot', symbol: 'BTC/USDT',
    source: 'spot_ledger', action: 'BUY',
    price: 100, fee: .1, event_pnl: 0,
    created_at: new Date().toISOString(),
  }],
});

describe('EBBot existing Trading Office Paper account UI', () => {
  beforeEach(() => {
    vi.mocked(cryptoPaperApi.capabilities).mockReset().mockResolvedValue({
      upstream_v2_present: false, upstream_v2_opted_in: false,
      ebbot_paper_execution_permitted: false,
      real_exchange_orders: false, execution: 'disabled',
      checked_at: new Date().toISOString(),
      note: 'Only source readiness',
    } as never);
    vi.mocked(cryptoPaperApi.summary).mockReset().mockResolvedValue(summary() as never);
    vi.mocked(cryptoPaperApi.history).mockReset().mockResolvedValue(history() as never);
  });

  it('shows existing Spot account without ever exposing an order action', async () => {
    const onOpenRisk = vi.fn();
    render(<CryptoPaperPanel view="paper" onOpenRisk={onOpenRisk}/>);
    expect(await screen.findByText('20.021 USDT')).toBeInTheDocument();
    expect(screen.getByText('9.900 USDT')).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /Emir gönder|Pozisyon aç|Long aç|Spot al/i })).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: /Risk Yönetimini aç/ }));
    expect(onOpenRisk).toHaveBeenCalledOnce();
  });

  it('keeps Spot and Futures isolated margin positions separate', async () => {
    render(<CryptoPaperPanel view="paper" onOpenRisk={vi.fn()}/>);
    await screen.findByText('20.021 USDT');
    fireEvent.click(screen.getByRole('button', { name: 'Futures Sanal Hesabı' }));
    expect(screen.getByText(/9.550 USDT/)).toBeInTheDocument();
    expect(screen.getAllByText(/450 USDT/).length).toBeGreaterThan(0);
    expect(screen.getByText('BTC/USDT:USDT')).toBeInTheDocument();
  });

  it('shows both markets positions without inventing live prices', async () => {
    render(<CryptoPaperPanel view="positions" onOpenRisk={vi.fn()}/>);
    await screen.findByText('Toplam açık sanal pozisyon');
    expect(await screen.findByText('BTC/USDT')).toBeInTheDocument();
    expect(screen.getByText('BTC/USDT:USDT')).toBeInTheDocument();
    expect(cryptoPaperApi.summary).toHaveBeenCalledOnce();
  });

  it('shows funding, life-cycle events and side filters read only', async () => {
    render(<CryptoPaperPanel view="history" onOpenRisk={vi.fn()}/>);
    expect(await screen.findByText('Funding')).toBeInTheDocument();
    expect(screen.getByText('Spot AL')).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'Futures' }));
    await waitFor(() => expect(cryptoPaperApi.history).toHaveBeenCalledWith('futures'));
    expect(cryptoPaperApi.summary).not.toHaveBeenCalled();
  });

  it('never enables orders even when upstream paper v2 opted in', async () => {
    vi.mocked(cryptoPaperApi.capabilities).mockResolvedValueOnce({
      upstream_v2_present: true, upstream_v2_opted_in: true,
      ebbot_paper_execution_permitted: false, real_exchange_orders: false,
      execution: 'disabled', checked_at: new Date().toISOString(),
      note: 'No orders',
    } as never);
    render(<CryptoPaperPanel view="paper" onOpenRisk={vi.fn()}/>);
    expect(await screen.findByText(/Kaynakta deneysel protokol açık/)).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /Emir gönder|Long aç|Spot al/i })).not.toBeInTheDocument();
  });

  it('does not reuse stale account snapshot after provider failure', async () => {
    render(<CryptoPaperPanel view="paper" onOpenRisk={vi.fn()}/>);
    await screen.findByText('20.021 USDT');
    vi.mocked(cryptoPaperApi.summary).mockRejectedValueOnce(Error('upstream unavailable'));
    fireEvent.click(screen.getByRole('button', { name: 'Kayıtları yenile' }));
    expect(await screen.findByRole('alert')).toHaveTextContent(/sanal defteri okunamadı/);
    expect(screen.queryByText('20.021 USDT')).not.toBeInTheDocument();
  });
});
