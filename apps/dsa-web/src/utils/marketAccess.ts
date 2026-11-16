/**
 * Turkish domestic-broker investment focus (2026-11-16).
 *
 * This is a *product presentation filter*, not a statement that residents of
 * Türkiye can never invest in other markets: international brokers may offer
 * additional exchanges subject to account-specific permissions.
 *
 * Listed equities in Türkiye (BIST), USA (NYSE/Nasdaq), Hong Kong (HKEX)
 * and Japan (TSE) have documented access via Türkiye-serving domestic
 * intermediaries; see NCM Investment's overseas-execution policy and
 * Garanti BBVA Yatırım's exchange list.
 *
 * IMPORTANT: This does NOT grant order permissions or make the current bot
 * capable of executing live trades. Existing backend providers, historical
 * jobs, cross-market tests, and data remain unchanged for compatibility.
 */
import type { StockIndexItem } from '../types/stockIndex';

export const TURKISH_BROKER_MARKETS = ['tr', 'us', 'hk', 'jp'] as const;
export type TurkishBrokerMarket = (typeof TURKISH_BROKER_MARKETS)[number];

const accessibleMarketSet: ReadonlySet<string> = new Set(TURKISH_BROKER_MARKETS);

export function isTurkishBrokerMarket(value: string): value is TurkishBrokerMarket {
  return accessibleMarketSet.has(value.trim().toLowerCase());
}

export function filterTurkishBrokerStockIndex(items: StockIndexItem[]): StockIndexItem[] {
  // Ignore ambiguous INDEX/ETF records until their exchange can be confirmed.
  return items.filter((item) => isTurkishBrokerMarket(item.market));
}
