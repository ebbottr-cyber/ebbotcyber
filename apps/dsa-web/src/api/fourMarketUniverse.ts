import apiClient from './index';

export type DatedTurkeyRoster = {
  market: 'tr';
  index: 'BIST100';
  as_of: string;
  effective_from: string;
  effective_to: string;
  verified_on: string;
  source_urls: string[];
  symbols: string[];
  target_symbols: 100;
};

const isRecord = (v: unknown): v is Record<string, unknown> =>
  v !== null && typeof v === 'object' && !Array.isArray(v);

const validDate = (v: unknown): v is string =>
  typeof v === 'string' && /^\d{4}-\d{2}-\d{2}$/.test(v) &&
  !Number.isNaN(Date.parse(v + 'T12:00:00Z')) &&
  new Date(v + 'T12:00:00Z').toISOString().slice(0, 10) === v;

/** Validates only source-dated index membership, not exchange permissions. */
export function parseDatedTurkeyRoster(raw: unknown): DatedTurkeyRoster {
  if (!isRecord(raw) || raw.market !== 'tr' || raw.index !== 'BIST100' ||
    raw.target_symbols !== 100 ||
    !validDate(raw.as_of) || !validDate(raw.effective_from) ||
    !validDate(raw.effective_to) || !validDate(raw.verified_on) ||
    raw.as_of < raw.effective_from || raw.as_of > raw.effective_to ||
    !Array.isArray(raw.symbols) || raw.symbols.length !== 100 ||
    !raw.symbols.every((code: unknown) =>
      typeof code === 'string' && /^[A-Z]{4,6}\.IS$/.test(code)) ||
    !Array.isArray(raw.source_urls) || raw.source_urls.length < 2 ||
    !raw.source_urls.every((url: unknown) =>
      typeof url === 'string' && /^https:\/\/[^/\s]+\/.+/.test(url))
  ) {
    throw new Error('BIST100 kaynak veya üyelik listesi geçersiz.');
  }
  const symbols = raw.symbols as string[];
  if (new Set(symbols).size !== 100 ||
    symbols.some((code, i) => i > 0 && symbols[i - 1] >= code)) {
    throw new Error('BIST100 listesi sıralı veya tekrarsız değil.');
  }
  return {
    market: 'tr',
    index: 'BIST100',
    as_of: raw.as_of,
    effective_from: raw.effective_from,
    effective_to: raw.effective_to,
    verified_on: raw.verified_on,
    source_urls: raw.source_urls as string[],
    symbols: [...symbols],
    target_symbols: 100,
  };
}

/** Never returns a roster when the operator's dated snapshot is unavailable. */
export const fourMarketUniverseApi = {
  async getTurkeyBist100(): Promise<DatedTurkeyRoster> {
    const response = await apiClient.get<unknown>('/api/v1/data/four-market/universe/tr');
    return parseDatedTurkeyRoster(response.data);
  },
};
