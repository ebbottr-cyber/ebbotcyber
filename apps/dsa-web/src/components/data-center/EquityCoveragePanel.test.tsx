// @vitest-environment jsdom
import { afterEach, describe, expect, it, vi } from 'vitest';
import { cleanup, render, screen } from '@testing-library/react';
import { dataCapabilityApi } from '../../api/dataCapability';
import EquityCoveragePanel from './EquityCoveragePanel';
import type { EquityCoverageReport } from '../../types/equityCoverage';

vi.mock('../../api/dataCapability', () => ({
  dataCapabilityApi: { getEquityCoverage: vi.fn() },
}));

const unavailable: EquityCoverageReport = {
  status: 'unavailable',
  reason: 'operator_report_not_configured',
  as_of_utc_date: null,
  markets: {},
  total_candidate_instruments: null,
  source_kind: 'operator_local_report',
  listing_completeness_verified: false,
  licensed_ohlcv_verified: false,
  paper_trading_enabled: false,
  live_trading_enabled: false,
};

const shape = {
  candidate_instruments: 2,
  stocks: 2,
  etfs: 0,
  with_any_ohlcv: 1,
  with_min_bars: 1,
  with_recent_bar: 1,
  undated_inventory_count: 0,
  missing_ohlcv_count: 1,
  insufficient_history_count: 0,
  stale_ohlcv_count: 0,
};

describe('EquityCoveragePanel', () => {
  afterEach(() => {
    cleanup();
    vi.resetAllMocks();
  });

  it('shows a non-trading explanation when no local report is configured', async () => {
    vi.mocked(dataCapabilityApi.getEquityCoverage).mockResolvedValue(unavailable);
    render(<EquityCoveragePanel />);
    expect(await screen.findByText(/Henüz güvenilir, yerel bir kapsam raporu/)).toBeTruthy();
    expect(screen.getByText(/Yalnızca denetim/)).toBeTruthy();
    expect(screen.queryByRole('table')).toBeNull();
  });

  it('shows four markets and transparent counts from a non-verified report', async () => {
    vi.mocked(dataCapabilityApi.getEquityCoverage).mockResolvedValue({
      ...unavailable,
      status: 'unverified',
      as_of_utc_date: '2026-11-21',
      total_candidate_instruments: 8,
      markets: { tr: shape, us: shape, de: shape, hk: shape },
    });
    render(<EquityCoveragePanel />);
    expect(await screen.findByRole('table')).toBeTruthy();
    expect(screen.getByText('Türkiye / BIST')).toBeTruthy();
    expect(screen.getByText('Almanya / Xetra')).toBeTruthy();
    expect(screen.getByText('Hong Kong')).toBeTruthy();
    expect(screen.getByText(/Kaynak inceleme bekliyor/)).toBeTruthy();
    expect(screen.getByText(/Gerçek ve sanal emirler kapalıdır/)).toBeTruthy();
  });

  it('warns on stale audit evidence', async () => {
    vi.mocked(dataCapabilityApi.getEquityCoverage).mockResolvedValue({
      ...unavailable,
      status: 'stale',
      as_of_utc_date: '2026-11-01',
      markets: { tr: shape, us: shape, de: shape, hk: shape },
      total_candidate_instruments: 8,
    });
    render(<EquityCoveragePanel />);
    expect(await screen.findByText(/Rapor eski, yenileme gerekli/)).toBeTruthy();
  });

  it('does not silently show zero market data when API fails', async () => {
    vi.mocked(dataCapabilityApi.getEquityCoverage).mockRejectedValue(new Error('no connection'));
    render(<EquityCoveragePanel />);
    expect(await screen.findByRole('alert')).toBeTruthy();
    expect(screen.queryByRole('table')).toBeNull();
  });
});
