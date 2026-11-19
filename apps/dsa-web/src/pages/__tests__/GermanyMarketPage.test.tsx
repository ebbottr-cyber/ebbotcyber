import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { UiLanguageProvider } from '../../contexts/UiLanguageContext';
import GermanyMarketPage from '../GermanyMarketPage';

const { getInventory, checkQuotes } = vi.hoisted(() => ({
  getInventory: vi.fn(),
  checkQuotes: vi.fn(),
}));

vi.mock('../../api/xetra', () => ({
  xetraApi: { getInventory, checkQuotes },
}));

const base = {
  status: 'CANDIDATE_INVENTORY_ONLY',
  market: 'XETR',
  currencyExpected: 'EUR',
  candidateCount: 1749,
  sourceAsOfDate: '2026-11-18',
  snapshotAgeDays: 0,
  sourceStale: false,
  items: [
    { symbol: 'SAP.DE', isin: 'DE0007164600', priceSymbolVerified: false },
    { symbol: 'SIE.DE', isin: 'DE0007236101', priceSymbolVerified: false },
  ],
  manualQuoteCheckEnabled: false,
  quotesAutoLoaded: false,
  brokerAccessVerified: false,
  paperTradingEnabled: false,
  liveTradingEnabled: false,
  orders: 0,
};

beforeEach(() => {
  vi.clearAllMocks();
  window.localStorage.setItem('dsa.uiLanguage', 'tr');
  getInventory.mockResolvedValue(base);
});

describe('GermanyMarketPage', () => {
  it('shows Xetra candidates without requesting a quote automatically', async () => {
    render(<UiLanguageProvider><GermanyMarketPage /></UiLanguageProvider>);
    expect(await screen.findByRole('heading', { name: 'Almanya (Xetra)' })).toBeInTheDocument();
    expect(await screen.findByText('1.749')).toBeInTheDocument();
    expect(screen.getByText('DE0007164600')).toBeInTheDocument();
    expect(screen.getByText(/Alım-satım kapalı/)).toBeInTheDocument();
    expect(checkQuotes).not.toHaveBeenCalled();
    expect(screen.getByRole('button', { name: 'Fiyatları kontrol et' })).toBeDisabled();
    expect(screen.queryByText('193,92')).not.toBeInTheDocument();
  });

  it('only runs manual quote-check after click and shows delayed provenance', async () => {
    getInventory.mockResolvedValue({ ...base, manualQuoteCheckEnabled: true });
    checkQuotes.mockResolvedValue({
      status: 'QUOTE_METADATA_SAMPLE_ONLY',
      candidateCountInManifest: 1749, requestedSymbols: 2,
      quoteMetadataMatches: 1, blockedCount: 1,
      observedAtUtc: '2026-11-18T20:51:54Z',
      allIsinMappingsVerified: false, allMarketPricesVerified: false,
      paperTradingEnabled: false, liveTradingEnabled: false, orders: 0,
      checks: [
        {
          symbol: 'SAP.DE', status: 'QUOTE_METADATA_MATCH', quoteMetadataMatched: true,
          providerCurrency: 'EUR', providerExchange: 'XETRA',
          regularMarketPriceEur: 193.92, regularMarketTimeUtc: '2026-11-18T16:37:40Z',
          quoteMayBeDelayed: true, isinIdentityVerified: false,
          brokerAccessVerified: false, realTimePriceVerified: false, orders: 0,
        },
        {
          symbol: 'SIE.DE', status: 'BLOCKED', reason: 'provider_request_failed',
          quoteMetadataMatched: false, isinIdentityVerified: false,
          brokerAccessVerified: false, realTimePriceVerified: false, orders: 0,
        },
      ],
    });

    render(<UiLanguageProvider><GermanyMarketPage /></UiLanguageProvider>);
    const button = await screen.findByRole('button', { name: 'Fiyatları kontrol et' });
    await waitFor(() => expect(button).toBeEnabled());
    expect(checkQuotes).not.toHaveBeenCalled();
    fireEvent.click(button);
    await waitFor(() => expect(checkQuotes).toHaveBeenCalledWith(['SAP.DE', 'SIE.DE']));
    expect(await screen.findByText(/193,92/)).toBeInTheDocument();
    expect(screen.getByText('Gecikmeli olabilir')).toBeInTheDocument();
    expect(screen.getByText('Doğrulanmış fiyat yok')).toBeInTheDocument();
    expect(screen.getByText(/Veri: Yahoo Finance/)).toBeInTheDocument();
  });

  it('does not display invented prices when API fetch fails', async () => {
    getInventory.mockResolvedValue({ ...base, manualQuoteCheckEnabled: true });
    checkQuotes.mockRejectedValue(new Error('provider failed'));
    render(<UiLanguageProvider><GermanyMarketPage /></UiLanguageProvider>);
    const button = await screen.findByRole('button', { name: 'Fiyatları kontrol et' });
    await waitFor(() => expect(button).toBeEnabled());
    fireEvent.click(button);
    expect(await screen.findByRole('alert')).toHaveTextContent('Fiyat kontrolü başarısız');
    expect(screen.queryByText(/193,92/)).not.toBeInTheDocument();
  });

  it('searches candidate inventory without fetching prices', async () => {
    render(<UiLanguageProvider><GermanyMarketPage /></UiLanguageProvider>);
    const input = await screen.findByRole('textbox', { name: /Sembol ara/ });
    fireEvent.change(input, { target: { value: 'BAS' } });
    fireEvent.click(screen.getByRole('button', { name: 'Ara' }));
    await waitFor(() => expect(getInventory).toHaveBeenCalledWith('BAS'));
    expect(checkQuotes).not.toHaveBeenCalled();
  });

  it('signals that the underlying reference snapshot can be stale', async () => {
    getInventory.mockResolvedValue({ ...base, sourceStale: true, snapshotAgeDays: 12 });
    render(<UiLanguageProvider><GermanyMarketPage /></UiLanguageProvider>);
    expect(await screen.findByText(/Kaynak listesi 7 günden eski/)).toBeInTheDocument();
    expect(checkQuotes).not.toHaveBeenCalled();
  });
});
