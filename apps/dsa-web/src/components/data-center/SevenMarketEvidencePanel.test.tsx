// @vitest-environment jsdom
import { afterEach, describe, expect, it, vi } from 'vitest';
import { cleanup, render, screen } from '@testing-library/react';
import { SevenMarketEvidencePanel } from './SevenMarketEvidencePanel';
import { sixMarketSmokeApi } from '../../api/sixMarketSmoke';
import { bist100TechnicalApi } from '../../api/bist100Technical';

vi.mock('../../api/sixMarketSmoke', () => ({
  sixMarketSmokeApi: { getSavedReport: vi.fn() },
}));
vi.mock('../../api/bist100Technical', () => ({
  bist100TechnicalApi: { getSavedReport: vi.fn() },
}));
afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

function oneSymbolEach() {
  const markets = ['cn', 'hk', 'us', 'jp', 'kr', 'tw'] as const;
  const sample = Object.fromEntries(markets.map(market => [
    market, {
      market, status: 'analyzed',
      expected_last_session: '2026-11-13', last_bar_date: '2026-11-13',
      bars: 80, technical_score: 71,
    },
  ]));
  return {
    asOf: '2026-11-15', results: sample, analyzedMarkets: 6,
  } as Awaited<ReturnType<typeof sixMarketSmokeApi.getSavedReport>>;
}

describe('seven-market Data Center saved report integration', () => {
  it('automatically loads six server-approved example rows, not full-market coverage', async () => {
    vi.mocked(bist100TechnicalApi.getSavedReport).mockRejectedValue(new Error('BIST not configured'));
    vi.mocked(sixMarketSmokeApi.getSavedReport).mockResolvedValue(oneSymbolEach());
    render(<SevenMarketEvidencePanel />);
    expect(await screen.findByText(/Kaydedilmiş tarihsel kanıt bulunan piyasa: 6\/7/)).toBeTruthy();
    expect(screen.getByText(/Yönetici tarafından onaylanmış sunucu raporu/)).toBeTruthy();
    expect(screen.getAllByText('Tarihsel raporda analiz var')).toHaveLength(6);
    expect(screen.getByText('Tek örnek: AAPL')).toBeTruthy();
    expect(screen.getByText('Tek örnek: 2330.TW')).toBeTruthy();
    expect(screen.getByText('BIST100 üyelik listesi · 100 hisse')).toBeTruthy();
    expect(vi.mocked(sixMarketSmokeApi.getSavedReport)).toHaveBeenCalledTimes(1);
  });

  it('shows no positive international evidence when saved file is missing/forbidden', async () => {
    vi.mocked(bist100TechnicalApi.getSavedReport).mockRejectedValue(new Error('BIST unavailable'));
    vi.mocked(sixMarketSmokeApi.getSavedReport).mockRejectedValue(new Error('HTTP 404'));
    render(<SevenMarketEvidencePanel />);
    expect(await screen.findByText(/Sunucuda onaylanmış altı piyasa örnek raporu yok/)).toBeTruthy();
    expect(screen.getByText(/Kaydedilmiş tarihsel kanıt bulunan piyasa: 0\/7/)).toBeTruthy();
    expect(screen.getAllByText('Kaydedilmiş kanıt yok')).toHaveLength(7);
    expect(screen.getByText(/onaylı sunucu raporu veya yerel test dosyası bulunamadı/)).toBeTruthy();
  });
});
