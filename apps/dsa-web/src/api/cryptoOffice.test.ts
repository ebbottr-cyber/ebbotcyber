import { describe, expect, it } from 'vitest';
import { validateCryptoOfficeDashboard } from './cryptoOffice';

function example() {
  return {
    schema_version: '1.1', mode: 'paper_only',
    generated_at: new Date().toISOString(),
    application: { version: '6.9.3' },
    safety: { real_exchange_orders: false, live_trading_enabled: false },
    portfolio: {
      combined: { valuation_complete: false, equity: null },
      spot: {}, futures: {}, open_positions: [],
    },
    risk: {}, performance: {}, validation: {},
    agents: {}, strategies: {}, operations: {},
  };
}

describe('EBBot isolated crypto-office dashboard contract', () => {
  it('accepts a verified read-only contract with unavailable equity', () => {
    const value = validateCryptoOfficeDashboard(example());
    expect(value.portfolio.combined).toEqual({ valuation_complete: false, equity: null });
  });

  it('refuses missing values masquerading as a zero balance', () => {
    const value = example();
    value.portfolio.combined.equity = 0 as never;
    expect(() => validateCryptoOfficeDashboard(value)).toThrow();
  });

  it('refuses a real-order flag or live-trading mode', () => {
    expect(() => validateCryptoOfficeDashboard({
      ...example(), safety: { real_exchange_orders: true, live_trading_enabled: false },
    })).toThrow();
    expect(() => validateCryptoOfficeDashboard({ ...example(), mode: 'live' })).toThrow();
  });

  it('refuses stale data and unsupported versions', () => {
    expect(() => validateCryptoOfficeDashboard({
      ...example(), generated_at: '2020-01-01T00:00:00+00:00',
    })).toThrow();
    expect(() => validateCryptoOfficeDashboard({ ...example(), schema_version: '2.0' })).toThrow();
  });

  it('rejects incomplete portfolio and missing contract sections', () => {
    expect(() => validateCryptoOfficeDashboard({
      ...example(), portfolio: { combined: { valuation_complete: true, equity: null } },
    })).toThrow();
    const value = example() as unknown as Record<string, unknown>;
    delete value.strategies;
    expect(() => validateCryptoOfficeDashboard(value)).toThrow();
  });
});
