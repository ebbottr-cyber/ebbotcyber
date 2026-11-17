import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { cryptoSpotApi } from '../../api/cryptoSpot';
import { CryptoSpotPanel } from './CryptoSpotPanel';

vi.mock('../../api/cryptoSpot', () => ({
  cryptoSpotApi: {
    ticker: vi.fn(),
    ohlcv: vi.fn(),
    orderbook: vi.fn(),
  },
}));

const candles = Array.from({ length: 25 }, (_, i) => ({
  timestamp: Date.now() - (25 - i) * 60_000,
  open: 100, high: 102, low: 99, close: 101, volume: 300,
}));

describe('EBBot Spot panel (public data only)', () => {
  beforeEach(() => {
    vi.mocked(cryptoSpotApi.ticker).mockReset().mockResolvedValue({
      symbol: 'BTC/USDT', last: 50000, bid: 49999, ask: 50001,
      high_24h: 51000, low_24h: 49000,
      quote_volume_24h: 200000,
      quality: 'ok', checked_at: new Date().toISOString(),
    } as never);
    vi.mocked(cryptoSpotApi.ohlcv).mockReset().mockResolvedValue({
      count: candles.length, candles, timeframe: '1h', quality: 'ok',
    } as never);
    vi.mocked(cryptoSpotApi.orderbook).mockReset().mockResolvedValue({
      bids: [[49999, 1]], asks: [[50001, 1]],
      bid_quote_depth: 49999, ask_quote_depth: 50001, quality: 'ok',
    } as never);
  });

  it('displays actual public price and Binance candlestick chart', async () => {
    render(<CryptoSpotPanel />);
    expect(await screen.findByRole('img', { name: /Binance Spot gerçek geçmiş OHLCV/ })).toBeInTheDocument();
    expect(screen.getAllByText('50.000').length).toBeGreaterThan(0);
    expect(screen.queryByRole('button', { name: /Gerçek emir|Canlı işlem/i })).not.toBeInTheDocument();
    expect(cryptoSpotApi.ticker).toHaveBeenCalledWith('BTC/USDT');
  });

  it('changes timeframe without triggering a trade', async () => {
    render(<CryptoSpotPanel />);
    await screen.findByRole('img', { name: /Binance Spot gerçek geçmiş OHLCV/ });
    fireEvent.click(screen.getByRole('button', { name: '4h' }));
    await waitFor(() => expect(cryptoSpotApi.ohlcv).toHaveBeenCalledWith('BTC/USDT', '4h', 100));
  });

  it('refuses invalid symbol and does not request unauthorised paths', async () => {
    render(<CryptoSpotPanel />);
    await screen.findByRole('img', { name: /Binance Spot gerçek geçmiş OHLCV/ });
    fireEvent.change(screen.getByLabelText('İşlem çifti'), { target: { value: 'BTC/TRY?../' } });
    fireEvent.click(screen.getByRole('button', { name: 'Göster' }));
    expect(screen.getByRole('alert')).toHaveTextContent(/geçerli bir çift/);
    expect(cryptoSpotApi.ticker).not.toHaveBeenCalledWith('BTC/TRY?../');
  });

  it('clears the old quote instead of inventing values after a provider outage', async () => {
    render(<CryptoSpotPanel />);
    await screen.findByRole('img', { name: /Binance Spot gerçek geçmiş OHLCV/ });
    vi.mocked(cryptoSpotApi.ticker).mockRejectedValueOnce(new Error('offline'));
    vi.mocked(cryptoSpotApi.ohlcv).mockRejectedValueOnce(new Error('offline'));
    vi.mocked(cryptoSpotApi.orderbook).mockRejectedValueOnce(new Error('offline'));
    fireEvent.click(screen.getByRole('button', { name: 'Yenile' }));
    await waitFor(() => expect(screen.getByRole('alert')).toHaveTextContent(/alınamadı/));
    expect(screen.getAllByText('Veri yok').length).toBeGreaterThan(0);
  });
});
