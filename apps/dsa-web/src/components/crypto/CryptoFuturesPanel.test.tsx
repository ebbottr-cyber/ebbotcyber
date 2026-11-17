import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { cryptoFuturesApi } from '../../api/cryptoFutures';
import { CryptoFuturesPanel } from './CryptoFuturesPanel';

vi.mock('../../api/cryptoFutures', async importOriginal => {
  const original = await importOriginal<typeof import('../../api/cryptoFutures')>();
  return {
    ...original,
    cryptoFuturesApi: {
      ticker: vi.fn(), ohlcv: vi.fn(), orderbook: vi.fn(),
      funding: vi.fn(), openInterest: vi.fn(),
    },
  };
});

const t = Date.now();
const candles = Array.from({ length: 25 }, (_, i) => ({
  timestamp: t - (25 - i) * 60_000,
  open: 100, high: 105, low: 99, close: 101, volume: 100,
}));

describe('EBBot Futures read-only trading research panel', () => {
  beforeEach(() => {
    vi.mocked(cryptoFuturesApi.ticker).mockReset().mockResolvedValue({
      last: 80000, bid: 79999, ask: 80001,
      quality: 'ok', timestamp: Date.now(),
    } as never);
    vi.mocked(cryptoFuturesApi.ohlcv).mockReset().mockResolvedValue({
      candles, count: 25, timeframe: '1h',
    } as never);
    vi.mocked(cryptoFuturesApi.orderbook).mockReset().mockResolvedValue({
      bids: [[79999, 1]], asks: [[80001, 1]],
      quality: 'ok',
    } as never);
    vi.mocked(cryptoFuturesApi.funding).mockReset().mockResolvedValue({
      funding_rate: .0001,
      funding_interval_hours: 8,
      mark_price: 80000, index_price: 79950,
      next_funding_timestamp: Date.now() + 3600000,
    } as never);
    vi.mocked(cryptoFuturesApi.openInterest).mockReset().mockResolvedValue({
      open_interest: 1234.56, unit: 'BTC', timestamp: Date.now(),
    } as never);
  });

  it('separates Futures from Spot and renders verified market feeds', async () => {
    render(<CryptoFuturesPanel />);
    expect(await screen.findByRole('img', { name: /Binance USD-M Futures OHLCV/ })).toBeInTheDocument();
    expect(screen.getByText(/1\.234,56 BTC/)).toBeInTheDocument();
    expect(screen.getByText('8 saat')).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /Emir gönder|Pozisyon aç|Long aç/i })).not.toBeInTheDocument();
    expect(cryptoFuturesApi.funding).toHaveBeenCalledWith('BTC/USDT');
  });

  it('calculates scenario PnL without any order endpoint', async () => {
    render(<CryptoFuturesPanel />);
    expect(await screen.findByRole('img', { name: /Binance USD-M Futures OHLCV/ })).toBeInTheDocument();
    expect(screen.getByText('-6 USDT')).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'SHORT' }));
    expect(screen.getByText('-6 USDT')).toBeInTheDocument();
    expect(screen.getByText(/Gerçek likidasyon seviyesi: hesaplanmadı/)).toBeInTheDocument();
  });

  it('changes timeframe and market pair without adding a trade', async () => {
    render(<CryptoFuturesPanel />);
    await screen.findByRole('img', { name: /Binance USD-M Futures OHLCV/ });
    fireEvent.click(screen.getByRole('button', { name: '4h' }));
    await waitFor(() => expect(cryptoFuturesApi.ohlcv).toHaveBeenCalledWith('BTC/USDT', '4h', 100));
    fireEvent.click(screen.getByRole('button', { name: 'ETH/USDT' }));
    await waitFor(() => expect(cryptoFuturesApi.ticker).toHaveBeenCalledWith('ETH/USDT'));
  });

  it('clears all old values after upstream failure', async () => {
    render(<CryptoFuturesPanel />);
    await screen.findByRole('img', { name: /Binance USD-M Futures OHLCV/ });
    vi.mocked(cryptoFuturesApi.ticker).mockRejectedValueOnce(Error('offline'));
    vi.mocked(cryptoFuturesApi.ohlcv).mockRejectedValueOnce(Error('offline'));
    vi.mocked(cryptoFuturesApi.orderbook).mockRejectedValueOnce(Error('offline'));
    vi.mocked(cryptoFuturesApi.funding).mockRejectedValueOnce(Error('offline'));
    vi.mocked(cryptoFuturesApi.openInterest).mockRejectedValueOnce(Error('offline'));
    fireEvent.click(screen.getByRole('button', { name: 'Yenile' }));
    await waitFor(() => expect(screen.getByRole('alert')).toHaveTextContent('Funding'));
    expect(screen.getAllByText('Veri yok').length).toBeGreaterThan(1);
  });

  it('rejects invalid Futures symbol before API requests', async () => {
    render(<CryptoFuturesPanel />);
    await screen.findByRole('img', { name: /Binance USD-M Futures OHLCV/ });
    fireEvent.change(screen.getByLabelText('Sözleşme'), { target: { value: 'BTC/TRY?secret=1' } });
    fireEvent.click(screen.getByRole('button', { name: 'Getir' }));
    expect(screen.getByRole('alert')).toHaveTextContent(/Geçerli bir USD-M/);
  });
});
