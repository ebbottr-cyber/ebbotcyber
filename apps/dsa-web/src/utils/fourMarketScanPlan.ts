/**
 * Browser-only ETRE batch-plan validator. It does not fetch market data or
 * claim that syntactically valid symbols are listed/tradable at a brokerage.
 * Canonical identity and trading permissions are still enforced server-side.
 */
export const FOUR_ACTIVE_MARKETS = ['tr', 'us', 'de', 'hk'] as const;
export type FourMarket = (typeof FOUR_ACTIVE_MARKETS)[number];
export const STOCKS_PER_MARKET = 100;
export const TOTAL_STOCK_TARGET = STOCKS_PER_MARKET * FOUR_ACTIVE_MARKETS.length;

const PATTERNS: Record<FourMarket, RegExp> = {
  tr: /^[A-Z]{4,5}\.IS$/,
  us: /^[A-Z]{1,5}(?:\.[A-Z])?$/,
  de: /^[A-Z][A-Z0-9]{0,7}\.DE$/,
  hk: /^HK[0-9]{5}$/,
};

// Exclude index aliases from the generic US share-code shape.
const INDEX_CODES = new Set([
  'SPX', 'SP500', 'DJI', 'DJIA', 'NDX', 'IXIC', 'COMP', 'RUT', 'VIX',
]);

export type FourMarketScanPlan = {
  codes: string[];
  counts: Record<FourMarket, number>;
  remaining: Record<FourMarket, number>;
  errors: string[];
  readyForFullScan: boolean;
  total: number;
};

export function detectFourMarketSymbol(code: string): FourMarket | null {
  if (PATTERNS.tr.test(code)) return 'tr';
  if (PATTERNS.de.test(code)) return 'de';
  if (PATTERNS.hk.test(code)) return 'hk';
  if (PATTERNS.us.test(code) && !INDEX_CODES.has(code)) return 'us';
  return null;
}

export function buildFourMarketScanPlan(text: string): FourMarketScanPlan {
  const counts = { tr: 0, us: 0, de: 0, hk: 0 };
  const errors: string[] = [];
  const codes: string[] = [];
  const seen = new Set<string>();
  const input = text.trim();
  const values = input ? input.split(/[\s,;]+/) : [];
  if (text.length > 20_000 || values.length > TOTAL_STOCK_TARGET + 100) {
    errors.push('List is too long; at most 400 distinct equity codes are supported.');
    return { codes: [], counts, remaining: { tr: 100, us: 100, de: 100, hk: 100 },
      errors, readyForFullScan: false, total: 0 };
  }
  for (const entry of values) {
    const code = entry.trim().toUpperCase();
    if (!code) continue;
    if (seen.has(code)) {
      errors.push('Repeated ticker: ' + code);
      continue;
    }
    seen.add(code);
    const market = detectFourMarketSymbol(code);
    if (!market) {
      errors.push('Unsupported or ambiguous symbol: ' + code);
      continue;
    }
    counts[market] += 1;
    codes.push(code);
    if (counts[market] > STOCKS_PER_MARKET) {
      errors.push('More than 100 symbols in market ' + market.toUpperCase());
    }
  }
  const remaining = {
    tr: Math.max(0, STOCKS_PER_MARKET - counts.tr),
    us: Math.max(0, STOCKS_PER_MARKET - counts.us),
    de: Math.max(0, STOCKS_PER_MARKET - counts.de),
    hk: Math.max(0, STOCKS_PER_MARKET - counts.hk),
  };
  const readyForFullScan = errors.length === 0 && codes.length === TOTAL_STOCK_TARGET &&
    FOUR_ACTIVE_MARKETS.every(market => counts[market] === STOCKS_PER_MARKET);
  return { codes, counts, remaining, errors, readyForFullScan, total: codes.length };
}
