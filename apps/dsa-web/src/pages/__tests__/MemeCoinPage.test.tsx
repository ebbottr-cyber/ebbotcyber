import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { UiLanguageProvider } from '../../contexts/UiLanguageContext';
import MemeCoinPage from '../MemeCoinPage';

const { getOverview, scanCandidates } = vi.hoisted(() => ({ getOverview: vi.fn(), scanCandidates: vi.fn() }));

vi.mock('../../api/memeCoin', () => ({
  memeCoinApi: { getOverview, scanCandidates },
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
  scanCandidates.mockResolvedValue({strategy: 'new_launch', status: 'disabled', source: 'geckoterminal', observedAt: null, candidates: [], error: null});
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

  it('shows local synthetic summaries only after explicit import, with no trading action', async () => {
    render(<UiLanguageProvider><MemeCoinPage /></UiLanguageProvider>);
    await screen.findByRole('heading', { name: 'Meme Coin Stratejileri' });

    const data = {
      format: 'ebbot-synthetic-report-v1',
      snapshot: {
        mode: 'offline_synthetic_storage_only',
        status: 'synthetic_storage_snapshot',
        event_count: 1,
        audit_tip_sha256: 'a'.repeat(64),
        kill_switch_latched: false,
        trade_executed: false,
        paper_trading_enabled: false,
        live_trading_enabled: false,
        realized_performance: false,
        summary: {
          synthetic_round_trips: 1,
          starting_synthetic_equity_usd: '1000.00',
          ending_synthetic_equity_usd: '999.74',
          synthetic_net_pnl_usd: '-0.26',
        },
        strategies: {
          new_launch: {
            synthetic_round_trips: 1, synthetic_wins: 0,
            synthetic_losses: 1, synthetic_net_pnl_usd: '-0.26',
            records: [{}],
          },
          momentum: {
            synthetic_round_trips: 0, synthetic_wins: 0,
            synthetic_losses: 0, synthetic_net_pnl_usd: '0.00',
            records: [],
          },
        },
      },
    };
    const file = new File([JSON.stringify(data)], 'synthetic.json', { type: 'application/json' });
    Object.defineProperty(file, 'text', { value: async () => JSON.stringify(data) });
    fireEvent.change(screen.getByLabelText('Yerel .json raporunu seç'), {
      target: { files: [file] },
    });
    expect(await screen.findByText(/Dosya kullanıcı tarafından seçilmiş/)).toBeInTheDocument();
    expect(screen.getAllByText(/-0.26/).length).toBeGreaterThan(0);
    expect(scanCandidates).not.toHaveBeenCalled();
    expect(screen.queryByRole('button', { name: /satın al|buy/i })).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: 'Raporu kaldır' }));
    expect(screen.getByText(/Henüz yerel rapor seçilmedi/)).toBeInTheDocument();
    expect(screen.queryByText(/Dosya kullanıcı tarafından seçilmiş/)).not.toBeInTheDocument();
  });

  it('rejects local reports with live trading enabled', async () => {
    render(<UiLanguageProvider><MemeCoinPage /></UiLanguageProvider>);
    await screen.findByRole('heading', { name: 'Meme Coin Stratejileri' });
    const file = new File(
      [JSON.stringify({ format: 'ebbot-synthetic-report-v1', snapshot: {
        mode: 'offline_synthetic_storage_only', status: 'synthetic_storage_snapshot',
        trade_executed: false, paper_trading_enabled: false, live_trading_enabled: true,
      } })], 'unsafe.json', { type: 'application/json' },
    );
    Object.defineProperty(file, 'text', {
      value: async () => JSON.stringify({ format: 'ebbot-synthetic-report-v1', snapshot: {
        mode: 'offline_synthetic_storage_only', status: 'synthetic_storage_snapshot',
        trade_executed: false, paper_trading_enabled: false, live_trading_enabled: true,
      } }),
    });
    fireEvent.change(screen.getByLabelText('Yerel .json raporunu seç'), {
      target: { files: [file] },
    });
    expect(await screen.findByText(/Rapor okunamadı veya sentetik rapor/)).toBeInTheDocument();
    expect(screen.queryByText(/Dosya kullanıcı tarafından seçilmiş/)).not.toBeInTheDocument();
  });


});
