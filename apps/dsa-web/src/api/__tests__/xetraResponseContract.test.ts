import { describe, expect, it } from 'vitest';
import { toCamelCase } from '../utils';
import type { XetraInventory, XetraQuoteReport } from '../xetra';

describe('Germany API snake_case → frontend contract', () => {
  it('maps nested candidate inventory without dropping the source date or safety gates', () => {
    const response = toCamelCase<XetraInventory>({
      status: 'CANDIDATE_INVENTORY_ONLY',
      market: 'XETR',
      currency_expected: 'EUR',
      candidate_count: 1750,
      source_as_of_date: '2026-11-19',
      snapshot_age_days: 0,
      source_stale: false,
      manual_quote_check_enabled: false,
      quotes_auto_loaded: false,
      broker_access_verified: false,
      paper_trading_enabled: false,
      live_trading_enabled: false,
      orders: 0,
      items: [{ symbol: '1ANT.DE', isin: 'US03703U1079', price_symbol_verified: false }],
    });
    expect(response.candidateCount).toBe(1750);
    expect(response.sourceAsOfDate).toBe('2026-11-19');
    expect(response.items[0]).toEqual({
      symbol: '1ANT.DE', isin: 'US03703U1079', priceSymbolVerified: false,
    });
    expect(response.manualQuoteCheckEnabled).toBe(false);
    expect(response.orders).toBe(0);
  });

  it('maps provider metadata in deep nested checks, without asserting actual tradeability', () => {
    const report = toCamelCase<XetraQuoteReport>({
      status: 'QUOTE_METADATA_SAMPLE_ONLY',
      candidate_count_in_manifest: 1750,
      requested_symbols: 1,
      quote_metadata_matches: 1,
      blocked_count: 0,
      observed_at_utc: '2026-11-19T09:00:00Z',
      checks: [{
        symbol: 'SAP.DE',
        status: 'QUOTE_METADATA_MATCH',
        reason: null,
        quote_metadata_matched: true,
        isin_identity_verified: false,
        broker_access_verified: false,
        real_time_price_verified: false,
        candidate_isin: 'DE0007164600',
        candidate_snapshot_date: '2026-11-19',
        provider_currency: 'EUR',
        provider_exchange: 'XETRA',
        regular_market_price_eur: 190.25,
        regular_market_time_utc: '2026-11-19T08:58:00Z',
        quote_may_be_delayed: true,
        orders: 0,
      }],
      all_isin_mappings_verified: false,
      all_market_prices_verified: false,
      paper_trading_enabled: false,
      live_trading_enabled: false,
      orders: 0,
    });
    expect(report.candidateCountInManifest).toBe(1750);
    expect(report.checks[0].regularMarketPriceEur).toBe(190.25);
    expect(report.checks[0].providerCurrency).toBe('EUR');
    expect(report.checks[0].candidateIsin).toBe('DE0007164600');
    expect(report.checks[0].quoteMetadataMatched).toBe(true);
    expect(report.checks[0].isinIdentityVerified).toBe(false);
    expect(report.checks[0].realTimePriceVerified).toBe(false);
    expect(report.allMarketPricesVerified).toBe(false);
    expect(report.orders).toBe(0);
  });
});
