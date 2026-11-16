/**
 * Small read-only Xetra search examples, not a complete exchange universe
 * and NOT a claim that any specific broker enables every instrument.
 * Yahoo Finance uses the explicit .DE suffix for Xetra and quotes in EUR.
 * Never derive a German symbol from a bare US-style company ticker.
 */
import type { StockIndexItem } from '../types/stockIndex';

const EXAMPLES = [
  ['SAP.DE', 'SAP SE'],
  ['SIE.DE', 'Siemens AG'],
  ['BMW.DE', 'BMW AG'],
  ['ALV.DE', 'Allianz SE'],
  ['DTE.DE', 'Deutsche Telekom AG'],
  ['MBG.DE', 'Mercedes-Benz Group AG'],
  ['VOW3.DE', 'Volkswagen AG (preferred)'],
  ['BAS.DE', 'BASF SE'],
  ['BAYN.DE', 'Bayer AG'],
  ['ADS.DE', 'adidas AG'],
  ['IFX.DE', 'Infineon Technologies AG'],
] as const;

export const GERMAN_STOCK_EXAMPLES: StockIndexItem[] = EXAMPLES.map(([code, name], i) => ({
  canonicalCode: code,
  displayCode: code,
  nameZh: name,
  nameEn: name,
  aliases: [code.slice(0, -3)],
  market: 'DE',
  assetType: 'stock',
  active: true,
  popularity: Math.max(0, 11 - i),
}));
