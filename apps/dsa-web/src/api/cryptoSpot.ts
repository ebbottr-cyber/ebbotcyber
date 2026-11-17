import apiClient from './index';

export type SpotTimeframe = '1m' | '5m' | '15m' | '1h' | '4h' | '1d';

type BaseSpot = {
  market: 'spot';
  symbol: string;
  provider: 'Binance';
  source: string;
  checked_at: string;
  orders_enabled: false;
  cached: boolean;
  quality: 'ok' | 'unknown';
};

export type SpotTicker = BaseSpot & {
  last: number;
  bid: number | null;
  ask: number | null;
  high_24h: number | null;
  low_24h: number | null;
  base_volume_24h: number | null;
  quote_volume_24h: number | null;
  timestamp: number | null;
};

export type SpotCandle = {
  timestamp: number;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
};

export type SpotOHLCV = BaseSpot & {
  timeframe: SpotTimeframe;
  count: number;
  candles: SpotCandle[];
  last_candle_timestamp: number;
};

export type SpotOrderbook = BaseSpot & {
  timestamp: number | null;
  bids: Array<[number, number]>;
  asks: Array<[number, number]>;
  bid_quote_depth: number;
  ask_quote_depth: number;
  depth_imbalance: number | null;
};

const object = (value: unknown): value is Record<string, unknown> =>
  value !== null && typeof value === 'object' && !Array.isArray(value);
const finite = (v: unknown): v is number => typeof v === 'number' && Number.isFinite(v);
const positive = (v: unknown): v is number => finite(v) && v > 0;
const nonnegative = (v: unknown): v is number => finite(v) && v >= 0;
const optional = (v: unknown, check: (v: unknown) => boolean) => v === null || check(v);
const timestamp = (v: unknown): v is number => Number.isSafeInteger(v) && (v as number) > 0;

function base(raw: unknown, symbol: string, source: string): asserts raw is Record<string, unknown> {
  if (!object(raw) || raw.market !== 'spot' || raw.symbol !== symbol ||
      raw.provider !== 'Binance' || raw.source !== source ||
      raw.orders_enabled !== false ||
      typeof raw.cached !== 'boolean' ||
      !['ok', 'unknown'].includes(String(raw.quality)) ||
      typeof raw.checked_at !== 'string' ||
      !Number.isFinite(Date.parse(raw.checked_at))) {
    throw new Error('Binance Spot verisi güvenlik veya kimlik kontrolünü geçemedi.');
  }
}

export function validateSpotTicker(raw: unknown, symbol: string): SpotTicker {
  base(raw, symbol, 'Binance public market data');
  if (!positive(raw.last) || !optional(raw.bid, positive) || !optional(raw.ask, positive) ||
      !optional(raw.high_24h, positive) || !optional(raw.low_24h, positive) ||
      !optional(raw.base_volume_24h, nonnegative) ||
      !optional(raw.quote_volume_24h, nonnegative) ||
      !(raw.timestamp === null || timestamp(raw.timestamp))) {
    throw new Error('Binance Spot fiyatı hatalı veya eksik.');
  }
  if (typeof raw.bid === 'number' && typeof raw.ask === 'number' && raw.bid > raw.ask) {
    throw new Error('Binance Spot fiyat alış-satış sıralaması geçersiz.');
  }
  if (typeof raw.timestamp === 'number' && Date.now() - raw.timestamp > 180_000) {
    throw new Error('Binance Spot fiyatı güncel değil.');
  }
  return raw as unknown as SpotTicker;
}

export function validateSpotOHLCV(raw: unknown, symbol: string, timeframe: SpotTimeframe): SpotOHLCV {
  base(raw, symbol, 'Binance public market data');
  if (raw.timeframe !== timeframe || !Array.isArray(raw.candles) ||
      raw.candles.length < 1 || raw.candles.length > 300 || raw.count !== raw.candles.length ||
      !timestamp(raw.last_candle_timestamp)) {
    throw new Error('Binance Spot mum verileri eksik.');
  }
  let previous = 0;
  for (const value of raw.candles) {
    if (!object(value) || !timestamp(value.timestamp) || value.timestamp <= previous ||
        !positive(value.open) || !positive(value.high) || !positive(value.low) ||
        !positive(value.close) || !nonnegative(value.volume) ||
        value.high < Math.max(value.open, value.close, value.low) ||
        value.low > Math.min(value.open, value.close, value.high)) {
      throw new Error('Binance Spot mum verilerinde doğrulama hatası.');
    }
    previous = value.timestamp;
  }
  if (raw.last_candle_timestamp !== previous) {
    throw new Error('Binance Spot son mum zaman damgası geçersiz.');
  }
  return raw as unknown as SpotOHLCV;
}

export function validateSpotOrderbook(raw: unknown, symbol: string): SpotOrderbook {
  base(raw, symbol, 'Binance public order book');
  if (!Array.isArray(raw.bids) || !Array.isArray(raw.asks) ||
      !raw.bids.length || !raw.asks.length ||
      raw.bids.length > 100 || raw.asks.length > 100 ||
      !nonnegative(raw.bid_quote_depth) || !nonnegative(raw.ask_quote_depth) ||
      !optional(raw.depth_imbalance, finite) ||
      !(raw.timestamp === null || timestamp(raw.timestamp))) {
    throw new Error('Binance Spot emir defteri geçersiz.');
  }
  const checkSide = (side: unknown[], descending: boolean) => {
    let previous = descending ? Number.POSITIVE_INFINITY : 0;
    for (const row of side) {
      if (!Array.isArray(row) || row.length !== 2 || !positive(row[0]) || !nonnegative(row[1]) ||
          (descending ? row[0] > previous : row[0] < previous)) return false;
      previous = row[0];
    }
    return true;
  };
  if (!checkSide(raw.bids, true) || !checkSide(raw.asks, false) ||
      raw.bids[0][0] >= raw.asks[0][0]) {
    throw new Error('Binance Spot emir defteri derinliği tutarsız.');
  }
  if (typeof raw.timestamp === 'number' && Date.now() - raw.timestamp > 60_000) {
    throw new Error('Binance Spot emir defteri güncel değil.');
  }
  return raw as unknown as SpotOrderbook;
}

function normalizePair(input: string): string {
  const pair = input.trim().toUpperCase();
  if (!/^[A-Z0-9]{2,20}\/(?:USDT|USDC|BTC|ETH)$/.test(pair)) {
    throw new Error('Geçerli bir Spot işlem çifti girin (ör. BTC/USDT).');
  }
  return pair;
}

export const cryptoSpotApi = {
  async ticker(input: string): Promise<SpotTicker> {
    const symbol = normalizePair(input);
    const res = await apiClient.get<unknown>('/api/v1/crypto-office/spot/ticker', { params: { symbol } });
    return validateSpotTicker(res.data, symbol);
  },
  async ohlcv(input: string, timeframe: SpotTimeframe, limit = 100): Promise<SpotOHLCV> {
    const symbol = normalizePair(input);
    const res = await apiClient.get<unknown>('/api/v1/crypto-office/spot/ohlcv', {
      params: { symbol, timeframe, limit },
    });
    return validateSpotOHLCV(res.data, symbol, timeframe);
  },
  async orderbook(input: string, limit = 20): Promise<SpotOrderbook> {
    const symbol = normalizePair(input);
    const res = await apiClient.get<unknown>('/api/v1/crypto-office/spot/orderbook', {
      params: { symbol, limit },
    });
    return validateSpotOrderbook(res.data, symbol);
  },
};
