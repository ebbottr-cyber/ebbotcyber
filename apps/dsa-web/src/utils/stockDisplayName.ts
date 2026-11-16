/**
 * Display-only stock identity formatting.
 *
 * Never machine-translate company or fund names. Names like Apple are legal/
 * branded identities, not Turkish words. Keep the original stock code for
 * lookups, API submissions and persistence; only presentation uses this helper.
 *
 * A small foreign-ticker fallback list mirrors the short public identifiers
 * already recorded by the backend in src/data/stock_mapping.py. Prefer actual
 * Latin source names when present. For other CJK-only records, use index
 * pinyin (if available), otherwise the unambiguous ticker, never a guessed
 * literal translation.
 */

const CJK_NAME = /[\u3400-\u9fff\uf900-\ufaff]/u;

const FOREIGN_COMPANY_NAMES: Record<string, string> = {
  AAPL: 'Apple',
  TSLA: 'Tesla',
  MSFT: 'Microsoft',
  GOOGL: 'Google',
  GOOG: 'Google',
  AMZN: 'Amazon',
  NVDA: 'NVIDIA',
  META: 'Meta',
  AMD: 'AMD',
  INTC: 'Intel',
  BABA: 'Alibaba',
  PDD: 'Pinduoduo',
  JD: 'JD.com',
  BIDU: 'Baidu',
  NIO: 'NIO',
  XPEV: 'XPeng',
  LI: 'Li Auto',
  COIN: 'Coinbase',
  MSTR: 'MicroStrategy',
  '00700': 'Tencent',
  '03690': 'Meituan',
  '01810': 'Xiaomi',
  '09988': 'Alibaba',
  '09618': 'JD.com',
  '09888': 'Baidu',
  '01024': 'Kuaishou',
  '00981': 'SMIC',
  '02015': 'Li Auto',
  '09868': 'XPeng',
  '00005': 'HSBC',
  '01299': 'AIA Group',
  '00941': 'China Mobile',
  '00883': 'CNOOC',
};

function foreignTickerKey(stockCode: string): string {
  const code = stockCode.trim().toUpperCase();
  if (/^HK\d{5}$/.test(code)) return code.slice(2);
  if (/^\d{5}\.HK$/.test(code)) return code.slice(0, 5);
  return code.replace(/\.(US|N|O|A)$/, '');
}

function latinCompanyName(value?: string | null): string {
  const name = (value ?? '').trim();
  return name && /[A-Za-z]/.test(name) && !CJK_NAME.test(name) ? name : '';
}

export interface StockDisplayNameOptions {
  nameEn?: string | null;
  aliases?: string[] | null;
  pinyinFull?: string | null;
}

export function getStockDisplayName(
  code: string,
  rawName?: string | null,
  options: StockDisplayNameOptions = {},
): string {
  const ticker = code.trim();
  const raw = (rawName ?? '').trim();
  // Use a source-provided Latin company name first; do not translate it.
  if (latinCompanyName(raw)) return raw;
  if (latinCompanyName(options.nameEn)) return options.nameEn!.trim();

  const known = FOREIGN_COMPANY_NAMES[foreignTickerKey(ticker)];
  if (known) return known;

  const latinAlias = options.aliases?.map(latinCompanyName).find(Boolean);
  if (latinAlias) return latinAlias;

  const pinyin = latinCompanyName(options.pinyinFull);
  if (pinyin) return pinyin.charAt(0).toUpperCase() + pinyin.slice(1);

  // When no safe Latin identity is known, the ticker is preferable to an
  // invented translation or an unreadable name in a Latin-script workspace.
  return raw && !CJK_NAME.test(raw) ? raw : ticker;
}
