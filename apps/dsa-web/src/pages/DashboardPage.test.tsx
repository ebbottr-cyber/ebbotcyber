import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { MemoryRouter } from 'react-router-dom';
import { UiLanguageProvider } from '../contexts/UiLanguageContext';
import { dashboardApi } from '../api/dashboard';
import { coinGeckoApi } from '../api/coinGecko';
import { newsApi } from '../api/news';
import DashboardPage from './DashboardPage';

vi.mock('../api/dashboard', () => ({
  dashboardApi: {
    getWatchlist: vi.fn(),
    getQuote: vi.fn(),
    getHistory: vi.fn(),
  },
}));
vi.mock('../api/coinGecko', () => ({
  coinGeckoApi: { getTop100: vi.fn() },
}));
vi.mock('../api/news', () => ({
  NEWS_CHANGED_EVENT: 'etre:news-updated',
  newsApi: { list: vi.fn(), status: vi.fn(), readAll: vi.fn() },
}));

const bars = Array.from({ length: 35 }, (_, index) => {
  const close = 100 + index * .7;
  return {
    date: new Date(Date.UTC(2026, 9, index + 1)).toISOString().slice(0, 10),
    open: close - .3,
    high: close + 1.2,
    low: close - 1.4,
    close,
    volume: 100000,
  };
});

const exampleCoin = {
  id: 'bitcoin', name: 'Bitcoin', symbol: 'btc', market_cap_rank: 1,
  current_price: 104000, market_cap: 2000000000, total_volume: 50000000,
  price_change_percentage_24h: 2.2,
};
const article = {
  id: 'a'.repeat(64), market: 'crypto', title: 'Bitcoin haberi',
  title_original: 'Bitcoin haberi', title_tr: 'Bitcoin haberi',
  summary_tr: 'Piyasa gelişmesi.', impact_tr: null,
  source: 'RSS yayıncısı', url: 'https://news.google.com/test',
  published_at: '2026-11-17T02:00:00+00:00',
  inserted_at: '2026-11-17T02:00:00+00:00',
  severity: 'normal', is_read: false, ai_status: 'complete',
};

function renderDashboard() {
  return render(
    <MemoryRouter>
      <UiLanguageProvider>
        <DashboardPage />
      </UiLanguageProvider>
    </MemoryRouter>,
  );
}

describe('ETRE Design 02 dashboard', () => {
  beforeEach(() => {
    vi.mocked(dashboardApi.getWatchlist).mockReset().mockResolvedValue(['AAPL']);
    vi.mocked(dashboardApi.getQuote).mockReset().mockImplementation(async code => ({
      stock_code: code, stock_name: 'Apple',
      current_price: 185, change: 2.4,
      change_percent: 1.3, update_time: null,
    }));
    vi.mocked(dashboardApi.getHistory).mockReset().mockResolvedValue(bars);
    vi.mocked(coinGeckoApi.getTop100).mockReset().mockResolvedValue({
      coins: [exampleCoin],
    } as never);
    vi.mocked(newsApi.list).mockReset().mockResolvedValue([article] as never);
    vi.mocked(newsApi.status).mockReset().mockResolvedValue({
      unread_count: 1, notifications_enabled: true,
      ai_enabled: false, translation_waiting: 0, latest_unread: [],
    });
    vi.mocked(newsApi.readAll).mockReset().mockResolvedValue();
  });

  it('renders four real-stock market reference cards and CoinGecko data', async () => {
    renderDashboard();
    expect(await screen.findByText('104.000')).toBeInTheDocument();
    expect(screen.getAllByText('Türkiye').length).toBeGreaterThan(0);
    expect(screen.getAllByText('Hong Kong').length).toBeGreaterThan(0);
    expect(screen.getByText('Kripto · BTC')).toBeInTheDocument();
  });

  it('keeps the original stock analysis accessible and uses real history for chart', async () => {
    renderDashboard();
    await waitFor(() => expect(screen.getByRole('img', { name: /Gerçek geçmiş OHLC/ })).toBeInTheDocument());
    expect(screen.getByRole('link', { name: /Detaylı analiz/ })).toHaveAttribute('href', '/analysis');
    expect(dashboardApi.getHistory).toHaveBeenCalled();
  });

  it('marks all current news read with the existing inbox API', async () => {
    renderDashboard();
    fireEvent.click(await screen.findByRole('button', { name: 'Tümünü okundu' }));
    await waitFor(() => expect(newsApi.readAll).toHaveBeenCalledOnce());
  });

  it('does not manufacture prices when quotes and history are unavailable', async () => {
    vi.mocked(dashboardApi.getQuote).mockRejectedValue(new Error('offline'));
    vi.mocked(dashboardApi.getHistory).mockRejectedValue(new Error('offline'));
    renderDashboard();
    expect(await screen.findByText('Bu hisse için geçmiş fiyat verisi alınamadı.')).toBeInTheDocument();
    expect(screen.getAllByText('Fiyat bekleniyor').length).toBeGreaterThan(0);
  });
});
