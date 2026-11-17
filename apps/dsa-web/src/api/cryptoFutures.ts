import apiClient from './index';
import type { SpotCandle, SpotTimeframe } from './cryptoSpot';

export type FuturesTimeframe = SpotTimeframe;
type FuturesBase = {
  market: 'futures';
  symbol: string;
  provider: 'Binance';
  source: string;
  checked_at: string;
  orders_enabled: false;
  cached: boolean;
  quality: 'ok' | 'unknown';
};
export type FuturesTicker = FuturesBase & {
  contract: string;
  last: number; bid: number | null; ask: number | null;
  high_24h: number | null; low_24h: number | null;
  base_volume_24h: number | null; quote_volume_24h: number | null;
  timestamp: number | null;
};
export type FuturesOHLCV = FuturesBase & {
  contract: string; timeframe: FuturesTimeframe; count: number;
  last_candle_timestamp: number; candles: SpotCandle[];
};
export type FuturesDepth = FuturesBase & {
  contract: string; timestamp: number | null;
  bids: Array<[number, number]>; asks: Array<[number, number]>;
  bid_quote_depth: number; ask_quote_depth: number;
  depth_imbalance: number | null;
};
export type FuturesFunding = FuturesBase & {
  contract: string; funding_rate: number;
  mark_price: number; index_price: number | null;
  funding_interval_hours: number; funding_interval_ms: number;
  funding_timestamp: number | null; next_funding_timestamp: number | null;
};
export type FuturesOpenInterest = FuturesBase & {
  binance_symbol: string; open_interest: number; unit: string; timestamp: number;
};

const object = (x: unknown): x is Record<string, unknown> =>
  x !== null && typeof x === 'object' && !Array.isArray(x);
const finite = (x: unknown): x is number => typeof x === 'number' && Number.isFinite(x);
const positive = (x: unknown): x is number => finite(x) && x > 0;
const nonnegative = (x: unknown): x is number => finite(x) && x >= 0;
const optional = (x: unknown, f: (value: unknown) => boolean) => x === null || f(x);
const milliseconds = (x: unknown): x is number => Number.isSafeInteger(x) && (x as number) > 0;

export function normalizeFuturesSymbol(value: string): string {
  const symbol = value.trim().toUpperCase();
  if (!/^[A-Z0-9]{2,20}\/USDT$/.test(symbol)) {
    throw new Error('USD-M Futures işlem çifti BASE/USDT biçiminde olmalı.');
  }
  return symbol;
}

function base(raw: unknown, symbol: string, source: string, contractRequired: boolean): asserts raw is Record<string, unknown> {
  const settlement = symbol + ':USDT';
  if (!object(raw) || raw.market !== 'futures' || raw.symbol !== symbol ||
      raw.provider !== 'Binance' || raw.source !== source ||
      raw.orders_enabled !== false || typeof raw.cached !== 'boolean' ||
      (raw.quality !== 'ok' && raw.quality !== 'unknown') ||
      typeof raw.checked_at !== 'string' || !Number.isFinite(Date.parse(raw.checked_at)) ||
      Date.now() - Date.parse(raw.checked_at) > 5 * 60_000 ||
      Date.parse(raw.checked_at) - Date.now() > 5 * 60_000 ||
      (contractRequired && raw.contract !== settlement)) {
    throw new Error('Futures verisinin kimliği, yetkisi veya güncelliği geçersiz.');
  }
}

export function validateFuturesTicker(raw: unknown, symbol: string): FuturesTicker {
  base(raw, symbol, 'Binance public market data', true);
  if (!positive(raw.last) || !optional(raw.bid, positive) || !optional(raw.ask, positive) ||
      !optional(raw.high_24h, positive) || !optional(raw.low_24h, positive) ||
      !optional(raw.base_volume_24h, nonnegative) ||
      !optional(raw.quote_volume_24h, nonnegative) ||
      !(raw.timestamp === null || milliseconds(raw.timestamp))) {
    throw new Error('Futures fiyat verisi geçersiz.');
  }
  if (positive(raw.bid) && positive(raw.ask) && raw.bid > raw.ask) {
    throw new Error('Futures alış/satış fiyatı tutarsız.');
  }
  if (milliseconds(raw.timestamp) &&
      (Date.now() - raw.timestamp > 180_000 || raw.timestamp - Date.now() > 300_000)) {
    throw new Error('Futures fiyat verisi bayat.');
  }
  return raw as unknown as FuturesTicker;
}

export function validateFuturesOHLCV(raw: unknown, symbol: string, timeframe: FuturesTimeframe): FuturesOHLCV {
  base(raw, symbol, 'Binance public market data', true);
  if (raw.timeframe !== timeframe || !Array.isArray(raw.candles) ||
      raw.candles.length < 2 || raw.candles.length > 300 ||
      raw.count !== raw.candles.length || !milliseconds(raw.last_candle_timestamp)) {
    throw new Error('Futures mum verileri eksik.');
  }
  let previous = 0;
  for (const candle of raw.candles) {
    if (!object(candle) || !milliseconds(candle.timestamp) ||
        candle.timestamp <= previous || !positive(candle.open) ||
        !positive(candle.high) || !positive(candle.low) || !positive(candle.close) ||
        !nonnegative(candle.volume) ||
        candle.high < Math.max(candle.open, candle.close, candle.low) ||
        candle.low > Math.min(candle.open, candle.close, candle.high)) {
      throw new Error('Futures mum dizisi tutarsız.');
    }
    previous = candle.timestamp;
  }
  if (previous !== raw.last_candle_timestamp) throw new Error('Son mum kimliği geçersiz.');
  const intervals: Record<FuturesTimeframe, number> = {
    '1m': 60, '5m': 300, '15m': 900, '1h': 3600, '4h': 14400, '1d': 86400,
  };
  if (Date.now() - previous > (intervals[timeframe] * 3 + 180) * 1000 ||
      previous - Date.now() > 300_000) {
    throw new Error('Futures mum verisi bayat.');
  }
  return raw as unknown as FuturesOHLCV;
}

export function validateFuturesFunding(raw: unknown, symbol: string): FuturesFunding {
  base(raw, symbol, 'Binance USD-M Futures public market data', true);
  if (!finite(raw.funding_rate) || Math.abs(raw.funding_rate) > 0.1 ||
      !positive(raw.mark_price) || !optional(raw.index_price, positive) ||
      ![1, 2, 4, 8].includes(Number(raw.funding_interval_hours)) ||
      raw.funding_interval_ms !== Number(raw.funding_interval_hours) * 3_600_000 ||
      !(raw.funding_timestamp === null || milliseconds(raw.funding_timestamp)) ||
      !(raw.next_funding_timestamp === null || milliseconds(raw.next_funding_timestamp))) {
    throw new Error('Funding veya mark fiyatı doğrulanamadı.');
  }
  return raw as unknown as FuturesFunding;
}

export function validateFuturesDepth(raw: unknown, symbol: string): FuturesDepth {
  base(raw, symbol, 'Binance public order book', true);
  if (!Array.isArray(raw.bids) || !Array.isArray(raw.asks) ||
      raw.bids.length < 1 || raw.asks.length < 1 ||
      raw.bids.length > 100 || raw.asks.length > 100 ||
      !nonnegative(raw.bid_quote_depth) || !nonnegative(raw.ask_quote_depth) ||
      !(raw.timestamp === null || milliseconds(raw.timestamp))) {
    throw new Error('Futures emir defteri verisi eksik.');
  }
  for (const side of ['bids', 'asks'] as const) {
    let previous = side === 'bids' ? Infinity : 0;
    for (const level of raw[side]) {
      if (!Array.isArray(level) || level.length !== 2 ||
          !positive(level[0]) || !nonnegative(level[1]) ||
          (side === 'bids' ? level[0] > previous : level[0] < previous)) {
        throw new Error('Futures derinlik fiyatları sıralı değil.');
      }
      previous = level[0];
    }
  }
  if ((raw.bids as number[][])[0][0] >= (raw.asks as number[][])[0][0]) {
    throw new Error('Futures alış/satış derinliği çapraz.');
  }
  if (milliseconds(raw.timestamp) && Date.now() - raw.timestamp > 60_000) {
    throw new Error('Futures emir defteri eski.');
  }
  return raw as unknown as FuturesDepth;
}

export function validateFuturesOpenInterest(raw: unknown, symbol: string): FuturesOpenInterest {
  base(raw, symbol, 'Binance USD-M Futures public openInterest', false);
  if (raw.binance_symbol !== symbol.replace('/', '') || !nonnegative(raw.open_interest) ||
      raw.unit !== symbol.split('/')[0] || !milliseconds(raw.timestamp) ||
      Date.now() - raw.timestamp > 180_000 || raw.timestamp - Date.now() > 300_000 ||
      raw.quality !== 'ok') {
    throw new Error('Open interest verisi geçersiz veya eski.');
  }
  return raw as unknown as FuturesOpenInterest;
}

export const cryptoFuturesApi = {
  async ticker(pair: string): Promise<FuturesTicker> {
    const symbol = normalizeFuturesSymbol(pair);
    const res = await apiClient.get<unknown>('/api/v1/crypto-office/futures/ticker', { params: { symbol } });
    return validateFuturesTicker(res.data, symbol);
  },
  async ohlcv(pair: string, timeframe: FuturesTimeframe, limit = 100): Promise<FuturesOHLCV> {
    const symbol = normalizeFuturesSymbol(pair);
    const res = await apiClient.get<unknown>('/api/v1/crypto-office/futures/ohlcv', { params: { symbol, timeframe, limit } });
    return validateFuturesOHLCV(res.data, symbol, timeframe);
  },
  async orderbook(pair: string, limit = 20): Promise<FuturesDepth> {
    const symbol = normalizeFuturesSymbol(pair);
    const res = await apiClient.get<unknown>('/api/v1/crypto-office/futures/orderbook', { params: { symbol, limit } });
    return validateFuturesDepth(res.data, symbol);
  },
  async funding(pair: string): Promise<FuturesFunding> {
    const symbol = normalizeFuturesSymbol(pair);
    const res = await apiClient.get<unknown>('/api/v1/crypto-office/futures/funding', { params: { symbol } });
    return validateFuturesFunding(res.data, symbol);
  },
  async openInterest(pair: string): Promise<FuturesOpenInterest> {
    const symbol = normalizeFuturesSymbol(pair);
    const res = await apiClient.get<unknown>('/api/v1/crypto-office/futures/open-interest', { params: { symbol } });
    return validateFuturesOpenInterest(res.data, symbol);
  },
};
