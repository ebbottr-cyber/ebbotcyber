import { describe, expect, it } from 'vitest';
import { validateCoinGeckoRoster } from './coinGecko';

const coins = Array.from({ length: 100 }, (_, i) => ({
  id: 'test-coin-' + i, symbol: 'DUP', name: 'Coin ' + i,
  market_cap_rank: i + 1, current_price: 1, market_cap: 100000 - i,
  total_volume: 500, price_change_percentage_24h: 0,
}));
const response = {
  source: 'CoinGecko', market: 'crypto', vs_currency: 'usd', count: 100,
  target_count: 100, cached: false, stale: false,
  as_of: '2026-11-16T00:00:00+00:00', coins,
};

describe('CoinGecko Top100 parser', () => {
  it('preserves 100 distinct CoinGecko identities when ticker symbols repeat', () => {
    expect(validateCoinGeckoRoster(response).coins).toHaveLength(100);
    expect(validateCoinGeckoRoster(response).coins[1].symbol).toBe('DUP');
  });

  it('refuses partial lists or duplicate IDs rather than filling gaps', () => {
    expect(() => validateCoinGeckoRoster({ ...response, coins: coins.slice(0, 99) })).toThrow();
    expect(() => validateCoinGeckoRoster({
      ...response, coins: [...coins.slice(0, 99), coins[0]],
    })).toThrow();
  });
});
