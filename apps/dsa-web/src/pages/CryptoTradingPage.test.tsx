import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { MemoryRouter } from 'react-router-dom';
import { cryptoOfficeApi } from '../api/cryptoOffice';
import CryptoTradingPage from './CryptoTradingPage';

vi.mock('../api/cryptoOffice', async (importOriginal) => {
  const original = await importOriginal<typeof import('../api/cryptoOffice')>();
  return { ...original, cryptoOfficeApi: { dashboard: vi.fn() } };
});

const valid = () => ({
  schema_version: '1.1', mode: 'paper_only',
  generated_at: new Date().toISOString(),
  application: { name: 'Trading Office', version: '6.9.3' },
  safety: { real_exchange_orders: false, live_trading_enabled: false },
  portfolio: {
    combined: { equity: null, valuation_complete: false },
    spot: { cash: 10000 }, futures: { cash: 10000 }, open_positions: [],
  },
  risk: { portfolio: { status: 'unavailable' } },
  performance: { daily: { net_pnl: 0 }, weekly: { net_pnl: 0 }, monthly: { net_pnl: 0 } },
  validation: {}, agents: { weights: {} }, strategies: {}, operations: { status: 'healthy' },
});

const mount = () => render(
  <MemoryRouter>
    <CryptoTradingPage />
  </MemoryRouter>,
);

describe('EBBot Kripto Trading read-only panel', () => {
  beforeEach(() => {
    vi.mocked(cryptoOfficeApi.dashboard).mockReset().mockResolvedValue(valid() as never);
  });

  it('shows 15 crypto modules and never enables live order controls', async () => {
    mount();
    await screen.findByText('Değerlenemiyor');
    expect(screen.getByRole('navigation', { name: 'Kripto modülü menüsü' }).querySelectorAll('button')).toHaveLength(15);
    expect(screen.getByText(/SADECE PAPER/)).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /Gerçek emir|Canlı alım|Long aç/i })).not.toBeInTheDocument();
  });

  it('keeps Spot and Futures portfolios on separate tabs', async () => {
    mount();
    await screen.findByText('Değerlenemiyor');
    fireEvent.click(screen.getByRole('button', { name: /02 Spot Piyasası/ }));
    expect(await screen.findByText('Spot sanal hesap')).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: /03 Futures Piyasası/ }));
    expect(await screen.findByText('Futures sanal hesap')).toBeInTheDocument();
  });

  it('replaces balances with error on failed refresh rather than keeping stale values', async () => {
    mount();
    await screen.findByText('Değerlenemiyor');
    vi.mocked(cryptoOfficeApi.dashboard).mockRejectedValueOnce(new Error('provider failed'));
    fireEvent.click(screen.getByRole('button', { name: 'Yenile' }));
    await waitFor(() => expect(screen.getByRole('alert')).toBeInTheDocument());
    expect(screen.queryByText('Değerlenemiyor')).not.toBeInTheDocument();
  });
});
