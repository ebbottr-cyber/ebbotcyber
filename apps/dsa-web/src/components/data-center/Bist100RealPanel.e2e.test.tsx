// @vitest-environment jsdom
/** Browser-DOM integration with actual archived 100-stock historical Yahoo report.
 * This test never reaches the network or sends orders; the report comes from
 * a SHA-256-verified GitHub artifact in the dedicated CI job only.
 */
import { readFileSync } from 'node:fs';
import { createHash } from 'node:crypto';
import React from 'react';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { parseBist100TechnicalReport } from '../../utils/bist100TechnicalReport';
import { Bist100TechnicalPanel } from './Bist100TechnicalPanel';

const HISTORIC_SHA256 = '42a0834b5633b9667979966acc847fde6f431fb8f57ced16c432161fb287b06a';
const reportPath = process.env.BIST100_REAL_REPORT_PATH;
if (!reportPath) throw new Error('Real report artifact required for DOM integration test');
const historicalBytes = readFileSync(reportPath);
if (createHash('sha256').update(historicalBytes).digest('hex') !== HISTORIC_SHA256) {
  throw new Error('Unexpected report source fingerprint');
}
const report = parseBist100TechnicalReport(JSON.parse(historicalBytes.toString('utf8')) as unknown);

vi.mock('../../api/bist100Technical', () => ({
  bist100TechnicalApi: {
    getSavedReport: vi.fn(async () => report),
  },
}));

afterEach(() => {
  // Testing Library/Vitest may not use the global afterEach auto cleanup.
  document.body.innerHTML = '';
});

describe('actual 100-stock Yahoo report shown by BIST100 React panel', () => {
  it('shows dated original rank, full coverage, actual MACD and real initial 20 rows', async () => {
    render(<Bist100TechnicalPanel />);
    expect(await screen.findByText('GARAN.IS')).toBeTruthy();
    expect(screen.getByText('TSKB.IS')).toBeTruthy();
    expect(screen.getByText(/Bu görünümde: 100/)).toBeTruthy();
    expect(screen.getByText(/Son tamamlanan seans: 2026-11-13/)).toBeTruthy();
    expect(screen.getByText('MACD hist.')).toBeTruthy();
    expect(screen.getByText('Sayfa 1 / 5')).toBeTruthy();
    expect(screen.getAllByRole('row')).toHaveLength(21);
  });

  it('searches a real historical ticker, preserving its original rank', async () => {
    render(<Bist100TechnicalPanel />);
    await screen.findByText('GARAN.IS');
    fireEvent.change(screen.getByRole('searchbox', { name: 'BIST100 hisse kodu ara' }), {
      target: { value: 'thyao' },
    });
    expect(await screen.findByText('THYAO.IS')).toBeTruthy();
    expect(screen.getByText(/Bu görünümde: 1/)).toBeTruthy();
    expect(screen.queryByText('GARAN.IS')).toBeNull();
    expect(screen.getAllByRole('row')).toHaveLength(2);
  });

  it('shows 80+ as 2 existing scores, not newly generated recommendations', async () => {
    render(<Bist100TechnicalPanel />);
    await screen.findByText('GARAN.IS');
    fireEvent.change(screen.getByLabelText('En düşük teknik puanı seç'), {
      target: { value: '80' },
    });
    await waitFor(() => expect(screen.getByText(/Bu görünümde: 2/)).toBeTruthy());
    expect(screen.getByText('GARAN.IS')).toBeTruthy();
    expect(screen.getByText('TSKB.IS')).toBeTruthy();
    expect(screen.queryByText('ALBRK.IS')).toBeNull();
  });

  it('shows only three MA5 warning rows without changing the full analyzed count', async () => {
    render(<Bist100TechnicalPanel />);
    await screen.findByText('GARAN.IS');
    fireEvent.change(screen.getByLabelText('MA5 mesafe riskini filtrele'), {
      target: { value: 'chase-risk' },
    });
    expect(await screen.findByText(/Bu görünümde: 3/)).toBeTruthy();
    expect(screen.getAllByRole('row')).toHaveLength(4);
    expect(screen.getByText(/Analiz edilen: 100/)).toBeTruthy();
  });
});
