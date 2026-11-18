import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { UiLanguageProvider } from '../../contexts/UiLanguageContext';
import MemeCoinPage from '../MemeCoinPage';

const { getOverview } = vi.hoisted(() => ({ getOverview: vi.fn() }));

vi.mock('../../api/memeCoin', () => ({
  memeCoinApi: { getOverview },
}));

const overview = {
  market: 'solana',
  mode: 'paper_planned',
  liveTradingEnabled: false,
  sharedRiskEngineConnected: false,
  lastMarketEventAt: null,
  strategies: [
    {
      id: 'new_launch',
      name: 'New Launch',
      market: 'solana',
      dataSources: ['Pump.fun'],
      status: 'not_connected',
      engineConnected: false,
      paperTradingEnabled: false,
      liveTradingEnabled: false,
      riskChecks: ['token_authorities'],
      metrics: { trades: null, netPnlUsd: null, winRatePct: null },
    },
    {
      id: 'momentum',
      name: 'Momentum',
      market: 'solana',
      dataSources: ['GMGN'],
      status: 'not_connected',
      engineConnected: false,
      paperTradingEnabled: false,
      liveTradingEnabled: false,
      riskChecks: ['volume_quality'],
      metrics: { trades: null, netPnlUsd: null, winRatePct: null },
    },
  ],
};

beforeEach(() => {
  vi.clearAllMocks();
  window.localStorage.clear();
  window.localStorage.setItem('dsa.uiLanguage', 'tr');
  getOverview.mockResolvedValue(overview);
});

describe('MemeCoinPage', () => {
  it('shows distinct, non-trading strategies and permits read-only selection', async () => {
    render(<UiLanguageProvider><MemeCoinPage /></UiLanguageProvider>);

    expect(await screen.findByRole('heading', { name: 'Meme Coin Stratejileri' })).toBeInTheDocument();
    expect(screen.getByText('Sanal işlem planlandı')).toBeInTheDocument();
    expect(screen.getAllByText('Canlı işlemler kapalı').length).toBeGreaterThan(0);
    expect(screen.getByText('Pump.fun')).toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: /Momentum Avcısı/ }));
    expect(await screen.findByText('GMGN')).toBeInTheDocument();
    expect(screen.getByText('Hacim kalitesi')).toBeInTheDocument();
    expect(screen.getByText(/Henüz test işlemi/)).toBeInTheDocument();
    expect(getOverview).toHaveBeenCalledTimes(1);
  });

  it('does not fake status or performance when the backend is unreachable', async () => {
    getOverview.mockRejectedValue(new Error('network down'));
    render(<UiLanguageProvider><MemeCoinPage /></UiLanguageProvider>);

    await waitFor(() => {
      expect(screen.getByRole('alert')).toBeInTheDocument();
    });
    expect(screen.queryByText('GMGN')).not.toBeInTheDocument();
    expect(screen.queryByText('Pump.fun')).not.toBeInTheDocument();
  });
});
