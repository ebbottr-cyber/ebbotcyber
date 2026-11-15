// @vitest-environment jsdom
/** GitHub-archived 2026-11-15 actual six-symbol Yahoo smoke -> React DOM.
 *
 * The exact archived file is required. Never substitute generated/fake bars.
 * The whole test lives outside src/ so normal frontend builds do not require
 * Node fs/crypto APIs. This is not a live browser or whole-market proof.
 */
import { createHash } from 'node:crypto';
import { readFileSync } from 'node:fs';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { cleanup, render, screen } from '@testing-library/react';
import { parseSixMarketEvidence, selectSevenMarketEvidence } from '../src/utils/sevenMarketEvidence';
import { SevenMarketEvidencePanel } from '../src/components/data-center/SevenMarketEvidencePanel';
import { sixMarketSmokeApi } from '../src/api/sixMarketSmoke';
import { bist100TechnicalApi } from '../src/api/bist100Technical';

vi.mock('../src/api/sixMarketSmoke', () => ({
  sixMarketSmokeApi: { getSavedReport: vi.fn() },
}));
vi.mock('../src/api/bist100Technical', () => ({
  bist100TechnicalApi: { getSavedReport: vi.fn() },
}));

const FILE_SHA256 = 'e2a4f357add80d7dc11ec305aab7a2fa0707f583763db36258c89cddd84d6bd2';
const sourcePath = process.env.SIX_MARKET_REAL_SOURCE;
if (!sourcePath) throw new Error('Original six-market Yahoo Actions artifact is mandatory');
const bytes = readFileSync(sourcePath);
if (createHash('sha256').update(bytes).digest('hex') !== FILE_SHA256) {
  throw new Error('Wrong real Yahoo artifact SHA-256; no synthetic fallback permitted');
}
const actual = parseSixMarketEvidence(JSON.parse(bytes.toString('utf8')) as unknown);

afterEach(() => {
  cleanup();
  vi.resetAllMocks();
});

describe('actual six-Yahoo-stock historical JSON -> Data Center DOM', () => {
  it('reads all six distinct historical scores and sessions from the verified artifact', () => {
    expect(actual.asOf).toBe('2026-11-15');
    expect(actual.analyzedMarkets).toBe(6);
    expect(actual.results.cn.technical_score).toBe(57);
    expect(actual.results.hk.technical_score).toBe(39);
    expect(actual.results.us.technical_score).toBe(75);
    expect(actual.results.jp.technical_score).toBe(72);
    const rows = selectSevenMarketEvidence(null, actual);
    expect(rows).toHaveLength(7);
    expect(rows[0].state).toBe('not_loaded');
    expect(rows.slice(1).every(row =>
      row.scope === 'one_sample_symbol' &&
      row.state === 'historical_analyzed' &&
      row.analyzed === 1 && row.checked === 1 &&
      row.lastSession === '2026-11-13')).toBe(true);
  });

  it('displays the actual six example stocks via approved saved-report API', async () => {
    vi.mocked(bist100TechnicalApi.getSavedReport).mockRejectedValue(new Error('BIST not configured'));
    vi.mocked(sixMarketSmokeApi.getSavedReport).mockResolvedValue(actual);
    render(<SevenMarketEvidencePanel />);
    expect(await screen.findByText(/Kaydedilmiş tarihsel kanıt bulunan piyasa: 6\/7/)).toBeTruthy();
    expect(screen.getByText(/Yönetici tarafından onaylanmış sunucu raporu/)).toBeTruthy();
    expect(screen.getByText(/Kaydedilmiş örnek analiz: 6\/6/)).toBeTruthy();
    expect(screen.getAllByText('Tarihsel raporda analiz var')).toHaveLength(6);
    expect(screen.getByText('Tek örnek: 600519.SS')).toBeTruthy();
    expect(screen.getByText('Tek örnek: 0700.HK')).toBeTruthy();
    expect(screen.getByText('Tek örnek: AAPL')).toBeTruthy();
    expect(screen.getByText('Tek örnek: 7203.T')).toBeTruthy();
    expect(screen.getByText('Tek örnek: 005930.KS')).toBeTruthy();
    expect(screen.getByText('Tek örnek: 2330.TW')).toBeTruthy();
    expect(vi.mocked(sixMarketSmokeApi.getSavedReport)).toHaveBeenCalledTimes(1);
  });

  it('never shows six successful stocks if no saved artifact was approved on server', async () => {
    vi.mocked(bist100TechnicalApi.getSavedReport).mockRejectedValue(new Error('BIST missing'));
    vi.mocked(sixMarketSmokeApi.getSavedReport).mockRejectedValue(new Error('HTTP 404'));
    render(<SevenMarketEvidencePanel />);
    expect(await screen.findByText(/Sunucuda onaylanmış altı piyasa örnek raporu yok/)).toBeTruthy();
    expect(screen.getByText(/Kaydedilmiş tarihsel kanıt bulunan piyasa: 0\/7/)).toBeTruthy();
    expect(screen.getAllByText('Kaydedilmiş kanıt yok')).toHaveLength(7);
  });
});
