import { describe, expect, it } from 'vitest';
import {
  normalizeFuturesSymbol, validateFuturesTicker, validateFuturesFunding,
  validateFuturesOHLCV, validateFuturesOpenInterest, validateFuturesDepth,
} from './cryptoFutures';

const pair = 'BTC/USDT';
const contract = 'BTC/USDT:USDT';
const millis = () => Date.now() - 30_000;
const root = (source: string) => ({
  market: 'futures', symbol: pair, contract, provider: 'Binance',
  source, checked_at: new Date().toISOString(), orders_enabled: false,
  cached: false, quality: 'ok',
});
const ticker = () => ({
  ...root('Binance public market data'),
  last: 80000, bid: 79999, ask: 80001,
  high_24h: 82000, low_24h: 78000,
  base_volume_24h: 100, quote_volume_24h: 8000000,
  timestamp: millis(),
});
const candles = () => {
  const rows = Array.from({ length: 20 }, (_, i) => ({
    timestamp: millis() - (19 - i) * 60_000,
    open: 100, high: 102, low: 99, close: 101, volume: 100,
  }));
  return {
    ...root('Binance public market data'), timeframe: '1m',
    count: rows.length, candles: rows,
    last_candle_timestamp: rows[rows.length - 1].timestamp,
  };
};
const funding = () => ({
  ...root('Binance USD-M Futures public market data'),
  funding_rate: .0001, mark_price: 80000, index_price: 79900,
  funding_interval_hours: 8, funding_interval_ms: 28800000,
  funding_timestamp: millis(), next_funding_timestamp: Date.now() + 3600000,
  quality: 'unknown',
});
const orderbook = () => ({
  ...root('Binance public order book'), timestamp: millis(),
  bids: [[79999, 1], [79998, 2]], asks: [[80001, 1], [80002, 2]],
  bid_quote_depth: 239995, ask_quote_depth: 240005, depth_imbalance: -.00002,
});
const openInterest = () => ({
  ...root('Binance USD-M Futures public openInterest'),
  binance_symbol: 'BTCUSDT', open_interest: 1234.5, unit: 'BTC',
  timestamp: millis(),
});

describe('EBBot USD-M Futures read-only data contract', () => {
  it('keeps USD-M perpetual CCXT identity distinct from Spot', () => {
    expect(normalizeFuturesSymbol('btc/usdt')).toBe(pair);
    expect(() => normalizeFuturesSymbol('BTC/USDT:USDT')).toThrow();
    expect(() => normalizeFuturesSymbol('BTC/TRY')).toThrow();
    expect(validateFuturesTicker(ticker(), pair).contract).toBe(contract);
  });

  it('rejects live orders, market crossover, bad quotes and timestamps', () => {
    expect(() => validateFuturesTicker({ ...ticker(), market: 'spot' }, pair)).toThrow();
    expect(() => validateFuturesTicker({ ...ticker(), orders_enabled: true }, pair)).toThrow();
    expect(() => validateFuturesTicker({ ...ticker(), contract: 'BTC/USDT' }, pair)).toThrow();
    expect(() => validateFuturesTicker({ ...ticker(), last: 0 }, pair)).toThrow();
    expect(() => validateFuturesTicker({ ...ticker(), timestamp: Date.now() - 900000 }, pair)).toThrow();
  });

  it('validates OHLCV without inventing any price', () => {
    expect(validateFuturesOHLCV(candles(), pair, '1m').count).toBe(20);
    const wrong = candles();
    wrong.candles[2].high = 40;
    expect(() => validateFuturesOHLCV(wrong, pair, '1m')).toThrow();
    expect(() => validateFuturesOHLCV(candles(), pair, '4h')).toThrow();
  });

  it('requires mark, index consistency, funding interval and rate', () => {
    expect(validateFuturesFunding(funding(), pair).mark_price).toBe(80000);
    expect(() => validateFuturesFunding({ ...funding(), mark_price: 0 }, pair)).toThrow();
    expect(() => validateFuturesFunding({ ...funding(), funding_rate: Infinity }, pair)).toThrow();
    expect(() => validateFuturesFunding({ ...funding(), funding_interval_hours: 3 }, pair)).toThrow();
    expect(() => validateFuturesFunding({ ...funding(), market: 'spot' }, pair)).toThrow();
  });

  it('validates public open interest with actual source time and base units', () => {
    expect(validateFuturesOpenInterest(openInterest(), pair).open_interest).toBe(1234.5);
    expect(() => validateFuturesOpenInterest({ ...openInterest(), open_interest: null }, pair)).toThrow();
    expect(() => validateFuturesOpenInterest({ ...openInterest(), timestamp: Date.now() - 800000 }, pair)).toThrow();
    expect(() => validateFuturesOpenInterest({ ...openInterest(), binance_symbol: 'ETHUSDT' }, pair)).toThrow();
  });

  it('refuses crossed or untrustworthy orderbooks', () => {
    expect(validateFuturesDepth(orderbook(), pair).bids).toHaveLength(2);
    expect(() => validateFuturesDepth({ ...orderbook(), bids: [[80002, 1]] }, pair)).toThrow();
    expect(() => validateFuturesDepth({ ...orderbook(), market: 'spot' }, pair)).toThrow();
  });
});
