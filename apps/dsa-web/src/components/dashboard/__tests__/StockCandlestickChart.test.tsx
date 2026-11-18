import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { stocksApi } from '../../../api/stocks';
import { normalizeCandles, StockCandlestickChart } from '../StockCandlestickChart';

vi.mock('../../../api/stocks', () => ({ stocksApi: { getHistory: vi.fn() } }));

const first = { date: '2026-11-16', open: 100, high: 105, low: 98, close: 103, volume: 1200 };
const second = { date: '2026-11-17', open: 103, high: 106, low: 101, close: 102, volume: 1000 };
const response = { stockCode: 'THYAO.IS', period: 'daily' as const, data: [first, second] };

describe('EBBot gerçek mum grafiği', () => {
  beforeEach(() => vi.resetAllMocks());

  it('sorts bars and discards invalid or duplicate OHLC data', () => {
    expect(normalizeCandles([
      second,
      { date: '2026-11-15', open: 99, high: 96, low: 98, close: 97 },
      first,
      { date: '2026-11-14', open: 0, high: 1, low: 0, close: 1 },
      first,
    ])).toEqual([first, second]);
  });

  it('requests only real OHLC bars from the existing server endpoint', async () => {
    vi.mocked(stocksApi.getHistory).mockResolvedValue(response);
    render(<StockCandlestickChart stockCode="THYAO.IS" />);
    await waitFor(() => expect(screen.getByTestId('candle-scroll')).toBeInTheDocument());
    expect(stocksApi.getHistory).toHaveBeenCalledWith('THYAO.IS', expect.objectContaining({
      days: 90, period: 'daily', signal: expect.any(AbortSignal),
    }));
    expect(screen.getByRole('img', { name: /THYAO.IS günlük mum grafiği/i })).toBeInTheDocument();
    expect(screen.getAllByTestId('ebbot-candle')).toHaveLength(2);
    expect(screen.getByTestId('technical-indicator-panel')).toBeInTheDocument();
    expect(screen.getByText('En az 15 kapanış gerekli.')).toBeInTheDocument();
    expect(screen.getByText(/Son kayıtlı mum: 2026-11-17/)).toBeInTheDocument();
    expect(screen.getByTestId('candle-scroll').className).toContain('overflow-x-auto');
  });

  it('uses only supported day ranges', async () => {
    vi.mocked(stocksApi.getHistory).mockResolvedValue(response);
    render(<StockCandlestickChart stockCode="THYAO.IS" />);
    fireEvent.click(screen.getByRole('button', { name: '6A' }));
    await waitFor(() => expect(stocksApi.getHistory).toHaveBeenCalledWith('THYAO.IS', expect.objectContaining({ days: 180, period: 'daily' })));
    expect(screen.queryByRole('button', { name: '1G' })).not.toBeInTheDocument();
  });

  it('shows a transparent fallback on API failure, not fabricated market data', async () => {
    vi.mocked(stocksApi.getHistory).mockRejectedValue(new Error('unavailable'));
    render(<StockCandlestickChart stockCode="THYAO.IS" fallback={<p>Rapor fiyatları</p>} />);
    expect(await screen.findByText(/Günlük mum verisi alınamadı/)).toBeInTheDocument();
    expect(screen.getByText('Rapor fiyatları')).toBeInTheDocument();
    expect(screen.queryByTestId('ebbot-candle')).not.toBeInTheDocument();
    expect(screen.queryByTestId('technical-indicator-panel')).not.toBeInTheDocument();
  });

  it('aborts an outdated request when the stock changes', async () => {
    vi.mocked(stocksApi.getHistory).mockResolvedValue(response);
    const view = render(<StockCandlestickChart stockCode="THYAO.IS" />);
    await waitFor(() => expect(stocksApi.getHistory).toHaveBeenCalledTimes(1));
    const initialSignal = vi.mocked(stocksApi.getHistory).mock.calls[0]?.[1]?.signal;
    view.rerender(<StockCandlestickChart stockCode="ASELS.IS" />);
    await waitFor(() => expect(stocksApi.getHistory).toHaveBeenCalledWith('ASELS.IS', expect.any(Object)));
    expect(initialSignal?.aborted).toBe(true);
  });
});
