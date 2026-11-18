import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { UiLanguageProvider } from '../../contexts/UiLanguageContext';
import MemeCoinPage from '../MemeCoinPage';

const { getOverview, scanCandidates, getRobinhoodStatus } = vi.hoisted(() => ({ getOverview: vi.fn(), scanCandidates: vi.fn(), getRobinhoodStatus: vi.fn() }));

vi.mock('../../api/memeCoin', () => ({
  memeCoinApi: { getOverview, scanCandidates, getRobinhoodStatus },
}));

const overview = {
  market: 'multi_chain',
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
    {
      id: 'robinhood_chain',
      name: 'Robinhood Chain Agent Research',
      market: 'robinhood_chain',
      dataSources: ['Robinhood Chain RPC (optional health check)', 'OpenCatz AI integration (planned)'],
      status: 'not_connected',
      engineConnected: false,
      paperTradingEnabled: false,
      liveTradingEnabled: false,
      riskChecks: ['evm_contract_permissions'],
      metrics: { trades: null, netPnlUsd: null, winRatePct: null },
    },
  ],
};

beforeEach(() => {
  vi.clearAllMocks();
  window.localStorage.clear();
  window.localStorage.setItem('dsa.uiLanguage', 'tr');
  getOverview.mockResolvedValue(overview);
  scanCandidates.mockResolvedValue({strategy: 'new_launch', status: 'disabled', source: 'geckoterminal', observedAt: null, candidates: [], error: null});
  getRobinhoodStatus.mockResolvedValue({network:'testnet',chainIdExpected:46630,chainIdSeen:null,blockNumber:null,status:'disabled',checkedAt:null,error:null,tradingEnabled:false});
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
  it('only requests a scan on an explicit click and shows disabled state without fake candidates', async () => {
    render(<UiLanguageProvider><MemeCoinPage /></UiLanguageProvider>);
    await screen.findByRole('heading', { name: 'Meme Coin Stratejileri' });
    expect(scanCandidates).not.toHaveBeenCalled();

    fireEvent.click(screen.getByRole('button', { name: 'Aday coinleri tara' }));
    expect(await screen.findByText(/MEME_COIN_DISCOVERY_ENABLED=true/)).toBeInTheDocument();
    expect(scanCandidates).toHaveBeenCalledWith('new_launch');
    expect(screen.queryByText('MEME')).not.toBeInTheDocument();
  });

  it('renders unverified candidates and does not offer buy controls', async () => {
    scanCandidates.mockResolvedValue({
      strategy: 'new_launch', status: 'ok', source: 'geckoterminal',
      observedAt: '2026-11-18T12:00:00Z', error: null,
      candidates: [{
        strategy: 'new_launch', symbol: 'MEME',
        tokenAddress: 'So11111111111111111111111111111111111111112',
        poolAddress: '11111111111111111111111111111111',
        liquidityUsd: 60000, volume5mUsd: 9000, change5mPct: 7,
        ageMinutes: 15, buys5m: 20, sells5m: 12,
        researchScore: 81.5, riskStatus: 'unverified', tradable: false,
        source: 'geckoterminal',
      }],
    });
    render(<UiLanguageProvider><MemeCoinPage /></UiLanguageProvider>);
    await screen.findByRole('heading', { name: 'Meme Coin Stratejileri' });
    fireEvent.click(screen.getByRole('button', { name: 'Aday coinleri tara' }));

    expect(await screen.findByText('MEME')).toBeInTheDocument();
    expect(screen.getByText('Güvenlik doğrulanmadı')).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /satın al|buy/i })).not.toBeInTheDocument();
  });

  it('shows provider failure rather than pretending that an empty scan succeeded', async () => {
    scanCandidates.mockRejectedValue(new Error('API offline'));
    render(<UiLanguageProvider><MemeCoinPage /></UiLanguageProvider>);
    await screen.findByRole('heading', { name: 'Meme Coin Stratejileri' });
    fireEvent.click(screen.getByRole('button', { name: 'Aday coinleri tara' }));

    expect(await screen.findByRole('alert')).toBeInTheDocument();
    expect(screen.getByText(/Veri kaynağına ulaşılamıyor/)).toBeInTheDocument();
  });

  it('shows Robinhood as a third isolated network with read-only RPC status', async () => {
    render(<UiLanguageProvider><MemeCoinPage /></UiLanguageProvider>);
    await screen.findByRole('heading', { name: 'Meme Coin Stratejileri' });

    fireEvent.click(screen.getByRole('button', { name: /Robinhood Chain AI/ }));
    expect(screen.getByText('OpenCatz AI integration (planned)')).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Aday coinleri tara' })).not.toBeInTheDocument();
    expect(getRobinhoodStatus).not.toHaveBeenCalled();

    fireEvent.click(screen.getByRole('button', { name: 'RPC bağlantısını kontrol et' }));
    expect(await screen.findByText(/MEME_COIN_ROBINHOOD_RPC_ENABLED=true/)).toBeInTheDocument();
    expect(getRobinhoodStatus).toHaveBeenCalledTimes(1);
    expect(scanCandidates).not.toHaveBeenCalled();
  });

  it('displays actual RPC status but never implies Robinhood token safety', async () => {
    getRobinhoodStatus.mockResolvedValue({
      network: 'testnet', chainIdExpected: 46630, chainIdSeen: 46630,
      blockNumber: 123456, status: 'ok', checkedAt: '2026-11-18T12:00:00Z',
      error: null, tradingEnabled: false,
    });

    render(<UiLanguageProvider><MemeCoinPage /></UiLanguageProvider>);
    await screen.findByRole('heading', { name: 'Meme Coin Stratejileri' });
    fireEvent.click(screen.getByRole('button', { name: /Robinhood Chain AI/ }));
    fireEvent.click(screen.getByRole('button', { name: 'RPC bağlantısını kontrol et' }));

    expect(await screen.findByText(/Ağ kimliği doğrulandı/)).toBeInTheDocument();
    expect(screen.getByText('46630')).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /buy|satın al/i })).not.toBeInTheDocument();
  });

});
