import apiClient from './index';
import { toCamelCase } from './utils';

export type XetraCandidate = {
  symbol: string;
  isin: string;
  priceSymbolVerified: false;
};

export type XetraInventory = {
  status: 'CANDIDATE_INVENTORY_ONLY';
  market: 'XETR';
  currencyExpected: 'EUR';
  candidateCount: number;
  sourceAsOfDate: string;
  snapshotAgeDays: number;
  sourceStale: boolean;
  items: XetraCandidate[];
  manualQuoteCheckEnabled: boolean;
  quotesAutoLoaded: false;
  brokerAccessVerified: false;
  paperTradingEnabled: false;
  liveTradingEnabled: false;
  orders: 0;
};

export type XetraQuoteCheck = {
  symbol: string;
  status: 'QUOTE_METADATA_MATCH' | 'BLOCKED';
  reason: string | null;
  quoteMetadataMatched: boolean;
  isinIdentityVerified: false;
  brokerAccessVerified: false;
  realTimePriceVerified: false;
  candidateIsin?: string;
  candidateSnapshotDate?: string;
  providerCurrency?: 'EUR';
  providerExchange?: 'XETRA';
  regularMarketPriceEur?: number;
  regularMarketTimeUtc?: string;
  quoteAgeHours?: number;
  quoteMayBeDelayed?: boolean;
  orders: 0;
};

export type XetraQuoteReport = {
  status: 'QUOTE_METADATA_SAMPLE_ONLY' | 'BLOCKED';
  candidateCountInManifest: number;
  requestedSymbols: number;
  quoteMetadataMatches: number;
  blockedCount: number;
  observedAtUtc: string;
  checks: XetraQuoteCheck[];
  allIsinMappingsVerified: false;
  allMarketPricesVerified: false;
  paperTradingEnabled: false;
  liveTradingEnabled: false;
  orders: 0;
};

export const xetraApi = {
  async getInventory(query = ''): Promise<XetraInventory> {
    const { data } = await apiClient.get('/api/v1/xetra/inventory', {
      params: { query, limit: 30 },
    });
    return toCamelCase<XetraInventory>(data);
  },
  /** Invoked ONLY after a deliberate user click; no background price polling. */
  async checkQuotes(symbols: string[]): Promise<XetraQuoteReport> {
    const { data } = await apiClient.post('/api/v1/xetra/quote-check', { symbols });
    return toCamelCase<XetraQuoteReport>(data);
  },
};
