import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import SolanaArchiveQuality from '../SolanaArchiveQuality';
import { parseReviewedSolanaQuality } from '../qualityReport';
import approved from '../../../../public/solana-quality-reviewed.json';

function snapshot() {
  return structuredClone(approved);
}

function respondWith(data: unknown, ok = true) {
  const fetchMock = vi.fn().mockResolvedValue({
    ok,
    text: async () => JSON.stringify(data),
  });
  vi.stubGlobal('fetch', fetchMock);
  return fetchMock;
}

beforeEach(() => {
  respondWith(snapshot());
});
afterEach(() => {
  vi.unstubAllGlobals();
});

describe('SolanaArchiveQuality reviewed data', () => {
  it('loads the reviewed same-origin file, not an external live API or hardcoded counters', async () => {
    const fetchMock = respondWith(snapshot());
    render(<SolanaArchiveQuality />);
    const heading = screen.getByRole('heading', { name: 'Solana arşiv veri kalitesi' });
    expect(heading).toBeDefined();
    expect(await screen.findByTestId('archive-quality-valid')).toHaveTextContent('9');
    expect(screen.getByTestId('archive-quality-missing')).toHaveTextContent('3');
    expect(screen.getByTestId('archive-quality-blocked')).toHaveTextContent('18');
    expect(screen.getByTestId('archive-quality-watch')).toHaveTextContent('0');
    expect(screen.getByText(/20 Kasım 2026/)).toBeDefined();
    expect(fetchMock).toHaveBeenCalledOnce();
    expect(fetchMock).toHaveBeenCalledWith('/solana-quality-reviewed.json', expect.objectContaining({
      method: 'GET', cache: 'no-store', credentials: 'same-origin',
    }));
  });

  it('shows two original source links and the independent audit link', async () => {
    render(<SolanaArchiveQuality />);
    await screen.findByTestId('archive-quality-valid');
    expect(screen.getByRole('link', { name: '#44779967482' })).toHaveAttribute('href',
      'https://github.com/ebbottr-cyber/ebbotcyber/actions/runs/44779967482');
    expect(screen.getByRole('link', { name: '#44777830658' })).toHaveAttribute('href',
      'https://github.com/ebbottr-cyber/ebbotcyber/actions/runs/44777830658');
    expect(screen.getByRole('link', { name: 'GitHub Actions #44791912581' })).toHaveAttribute('href',
      'https://github.com/ebbottr-cyber/ebbotcyber/actions/runs/44791912581');
    expect(screen.getByText('6/6')).toBeDefined();
    expect(screen.getByText('3/6')).toBeDefined();
    expect(screen.getByText('Eksiksiz veri')).toBeDefined();
    expect(screen.getByText('Eksik / sorunlu veri')).toBeDefined();
  });

  it('reads updated reviewed counts without code edits and never interprets them as trade permission', async () => {
    const next = snapshot();
    next.captures[1].priced_rows = 6;
    next.captures[1].missing_rows = 0;
    next.captures[1].result = 'passed';
    next.total_priced_rows = 12;
    next.total_missing_rows = 0;
    next.blocked_assessments = 24;
    next.quality_result = 'complete_captures';
    respondWith(next);
    render(<SolanaArchiveQuality />);
    expect(await screen.findByTestId('archive-quality-valid')).toHaveTextContent('12');
    expect(screen.getByTestId('archive-quality-missing')).toHaveTextContent('0');
    expect(screen.getByText('Salt okunur · Gözlemler eksiksiz')).toBeDefined();
    expect(screen.getByText(/Geçerli fiyat, güvenli coin/)).toBeDefined();
  });

  it('never offers an order, scanner, scheduler or training control', async () => {
    render(<SolanaArchiveQuality />);
    await screen.findByTestId('archive-quality-valid');
    expect(screen.queryByRole('button')).toBeNull();
    expect(screen.queryByRole('checkbox')).toBeNull();
    expect(screen.queryByRole('textbox')).toBeNull();
  });

  it('fails closed when the static report is missing', async () => {
    respondWith({}, false);
    render(<SolanaArchiveQuality />);
    expect(await screen.findByRole('alert')).toHaveTextContent('güvenlik kontrolünü geçemedi');
    expect(screen.queryByTestId('archive-quality-valid')).toBeNull();
    expect(screen.queryByRole('link')).toBeNull();
  });

  it.each([
    ['trading flag', (data: ReturnType<typeof snapshot>) => { data.trading_enabled = true; }],
    ['wallet flag', (data: ReturnType<typeof snapshot>) => { data.wallet_enabled = true; }],
    ['performance flag', (data: ReturnType<typeof snapshot>) => { data.performance_calculated = true; }],
    ['paper readiness', (data: ReturnType<typeof snapshot>) => { data.ready_for_verified_paper_performance = true; }],
    ['fabricated priced count', (data: ReturnType<typeof snapshot>) => { data.total_priced_rows = 99; }],
    ['fabricated blocked count', (data: ReturnType<typeof snapshot>) => { data.blocked_assessments = 0; }],
    ['duplicate source runs', (data: ReturnType<typeof snapshot>) => { data.captures[1].run_id = data.captures[0].run_id; }],
    ['inconsistent capture status', (data: ReturnType<typeof snapshot>) => { data.captures[1].result = 'passed'; }],
    ['fake complete quality', (data: ReturnType<typeof snapshot>) => { data.quality_result = 'complete_captures'; }],
    ['wrong provenance', (data: ReturnType<typeof snapshot>) => { data.mode = 'untrusted'; }],
  ] as const)('rejects %s and does not render figures', async (_caseName, modify) => {
    const next = snapshot();
    modify(next);
    respondWith(next);
    render(<SolanaArchiveQuality />);
    expect(await screen.findByRole('alert')).toBeDefined();
    expect(screen.queryByTestId('archive-quality-valid')).toBeNull();
  });
});

describe('parseReviewedSolanaQuality', () => {
  it('checks the actual committed JSON schema and risk provenance', () => {
    const parsed = parseReviewedSolanaQuality(approved);
    expect(parsed.quality_result).toBe('degraded_capture_data');
    expect(parsed.capture_count).toBe(2);
    expect(parsed.total_priced_rows + parsed.total_missing_rows).toBe(12);
    expect(parsed.ready_for_verified_paper_performance).toBe(false);
  });

  it('rejects non-object, missing and non-finite input', () => {
    expect(() => parseReviewedSolanaQuality(null)).toThrow();
    expect(() => parseReviewedSolanaQuality({})).toThrow();
    const next = snapshot();
    next.total_missing_rows = Number.NaN;
    expect(() => parseReviewedSolanaQuality(next)).toThrow();
  });
});
