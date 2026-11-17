import { describe, expect, it } from 'vitest';
import {
  validateSpotTicker, validateSpotOHLCV, validateSpotOrderbook,
} from './cryptoSpot';

const timestamp = () => Date.now() - 30_000;
const ticker = () => ({
  market: 'spot', symbol: 'BTC/USDT', provider: 'Binance',
  source: 'Binance public market data', checked_at: new Date().toISOString(),
  orders_enabled: false, cached: false, quality: 'ok',
  last: 45000, bid: 44999, ask: 45001,
  high_24h: 46000, low_24h: 44000,
  base_volume_24h: 100, quote_volume_24h: 50000,
  timestamp: timestamp(),
});
const candle = (ts: number) => ({
  timestamp: ts, open: 100, high: 102, low: 99, close: 101, volume: 1000,
});
const ohlcv = () => {
  const candles = Array.from({ length: 20 }, (_, i) => candle(timestamp() - (19 - i) * 60_000));
  return {
    market: 'spot', symbol: 'BTC/USDT', provider: 'Binance',
    source: 'Binance public market data', checked_at: new Date().toISOString(),
    orders_enabled: false, cached: false, quality: 'ok',
    timeframe: '1m', count: candles.length, candles,
    last_candle_timestamp: candles[candles.length - 1].timestamp,
  };
};
const book = () => ({
  market: 'spot', symbol: 'BTC/USDT', provider: 'Binance',
  source: 'Binance public order book', checked_at: new Date().toISOString(),
  orders_enabled: false, cached: false, quality: 'ok',
  timestamp: timestamp(),
  bids: [[44999, 3], [44998, 1]], asks: [[45000, 2], [45001, 1]],
  bid_quote_depth: 179995, ask_quote_depth: 135001, depth_imbalance: .142,
});

describe('EBBot Binance Spot contracts', () => {
  it('keeps only validated read-only quotes', () => {
    const value = validateSpotTicker(ticker(), 'BTC/USDT');
    expect(value.orders_enabled).toBe(false);
    expect(value.last).toBe(45000);
  });

  it('rejects bad identity, wrong market, stale data and fake prices', () => {
    expect(() => validateSpotTicker({ ...ticker(), market: 'futures' }, 'BTC/USDT')).toThrow();
    expect(() => validateSpotTicker({ ...ticker(), symbol: 'ETH/USDT' }, 'BTC/USDT')).toThrow();
    expect(() => validateSpotTicker({ ...ticker(), last: 0 }, 'BTC/USDT')).toThrow();
    expect(() => validateSpotTicker({ ...ticker(), orders_enabled: true }, 'BTC/USDT')).toThrow();
    expect(() => validateSpotTicker({ ...ticker(), timestamp: Date.now() - 600_000 }, 'BTC/USDT')).toThrow();
  });

  it('rejects malformed or duplicate candles', () => {
    expect(validateSpotOHLCV(ohlcv(), 'BTC/USDT', '1m').count).toBe(20);
    const malformed = ohlcv();
    malformed.candles[1].timestamp = malformed.candles[0].timestamp;
    expect(() => validateSpotOHLCV(malformed, 'BTC/USDT', '1m')).toThrow();
    const badPrice = ohlcv();
    badPrice.candles[2].high = 95;
    expect(() => validateSpotOHLCV(badPrice, 'BTC/USDT', '1m')).toThrow();
    expect(() => validateSpotOHLCV(ohlcv(), 'BTC/USDT', '1d')).toThrow();
  });

  it('rejects crossed/unsorted orderbooks', () => {
    expect(validateSpotOrderbook(book(), 'BTC/USDT').bids).toHaveLength(2);
    const crossed = book();
    crossed.bids[0][0] = crossed.asks[0][0];
    expect(() => validateSpotOrderbook(crossed, 'BTC/USDT')).toThrow();
    const unsorted = book();
    unsorted.asks.reverse();
    expect(() => validateSpotOrderbook(unsorted, 'BTC/USDT')).toThrow();
  });

  it('flags unavailable timestamp without inventing freshness', () => {
    const missing = { ...ticker(), timestamp: null, quality: 'unknown' };
    expect(validateSpotTicker(missing, 'BTC/USDT').quality).toBe('unknown');
  });
});
