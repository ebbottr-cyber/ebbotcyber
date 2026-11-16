/**
 * Turkish domestic-broker investment focus (2026-11-16).
 *
 * This is a *product presentation filter*, not a statement that residents of
 * Türkiye can never invest in other markets: international brokers may offer
 * additional exchanges subject to account-specific permissions.
 *
 * Selected markets: Türkiye (BIST), USA (NYSE/Nasdaq), Germany (Xetra),
 * Hong Kong (HKEX), Japan (TSE). Midas officially lists Xetra access;
 * actual instrument access depends on account and broker permissions.
 *
 * IMPORTANT: This does NOT grant order permissions or make the current bot
 * capable of executing live trades. Existing backend providers, historical
 * jobs, cross-market tests, and data remain unchanged for compatibility.
 */
import type { StockIndexItem } from '../types/stockIndex';

export const TURKISH_BROKER_MARKETS = ['tr', 'us', 'de', 'hk', 'jp'] as const;
export type TurkishBrokerMarket = (typeof TURKISH_BROKER_MARKETS)[number];

const accessibleMarketSet: ReadonlySet<string> = new Set(TURKISH_BROKER_MARKETS);

export function isTurkishBrokerMarket(value: string): value is TurkishBrokerMarket {
  return accessibleMarketSet.has(value.trim().toLowerCase());
}

export function filterTurkishBrokerStockIndex(items: StockIndexItem[]): StockIndexItem[] {
  // Ignore ambiguous INDEX/ETF records until their exchange can be confirmed.
  return items.filter((item) => isTurkishBrokerMarket(item.market));
}
