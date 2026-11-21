// @vitest-environment jsdom
import { afterEach, describe, expect, it, vi } from 'vitest';
import { cleanup, render, screen } from '@testing-library/react';
import { dataCapabilityApi } from '../../api/dataCapability';
import type { BistIdentitySummary } from '../../types/bistIdentity';
import BistIdentityPanel from './BistIdentityPanel';

vi.mock('../../api/dataCapability', () => ({
  dataCapabilityApi: { getBistIdentitySummary: vi.fn() },
}));

const unavailable: BistIdentitySummary = {
  status: 'unavailable',
  reason: 'operator_report_not_configured',
  as_of_utc_date: null,
  counts: null,
  prices_file_supplied: false,
  provider_mapping_file_supplied: false,
  source_kind: 'operator_local_bist_identity_report',
  independent_listing_verified: false,
  licensed_prices_verified: false,
  paper_trading_enabled: false,
  live_trading_enabled: false,
};

const evidence: BistIdentitySummary = {
  ...unavailable,
  status: 'unverified',
  reason: 'operator_bist_reference_comparison_only',
  as_of_utc_date: '2026-11-21',
  prices_file_supplied: true,
  provider_mapping_file_supplied: true,
  counts: {
    kap_candidate_count: 3,
    exchange_reference_count: 3,
    exchange_active_count: 2,
    exchange_halted_or_delisted_count: 1,
    matched_kap_exchange_count: 2,
    matched_active_kap_exchange_count: 1,
    kap_not_in_exchange_count: 1,
    exchange_not_in_kap_count: 1,
    active_without_declared_provider_mapping_count: 1,
    active_with_ohlcv_in_supplied_file_count: 1,
    active_without_ohlcv_in_supplied_file_count: 1,
    stale_kap_reference_rows: 0,
    stale_exchange_reference_rows: 0,
    stale_provider_mapping_rows: 0,
  },
};

describe('BistIdentityPanel', () => {
  afterEach(() => {
    cleanup();
    vi.resetAllMocks();
  });

  it('never invents zero stocks when local report is absent', async () => {
    vi.mocked(dataCapabilityApi.getBistIdentitySummary).mockResolvedValue(unavailable);
    render(<BistIdentityPanel />);
    expect(await screen.findByText(/BIST eşleştirme raporu bulunamadı/)).toBeTruthy();
    expect(screen.queryByRole('table')).toBeNull();
  });

  it('shows KAP versus BIST differences separately and disclaims verification', async () => {
    vi.mocked(dataCapabilityApi.getBistIdentitySummary).mockResolvedValue(evidence);
    render(<BistIdentityPanel />);
    expect(await screen.findByRole('table')).toBeTruthy();
    expect(screen.getByText('KAP şirket adayı')).toBeTruthy();
    expect(screen.getByText('BIST aktif bildirilen')).toBeTruthy();
    expect(screen.getByText('KAP ve BIST eşleşen aktif')).toBeTruthy();
    expect(screen.getByText(/Bağımsız kaynak onayı bekliyor/)).toBeTruthy();
    expect(screen.getByText(/Gerçek ve sanal emirler kapalıdır/)).toBeTruthy();
  });

  it('marks supplied source as stale instead of displaying it as verified', async () => {
    vi.mocked(dataCapabilityApi.getBistIdentitySummary).mockResolvedValue({
      ...evidence,
      status: 'stale',
    });
    render(<BistIdentityPanel />);
    expect(await screen.findByText(/Kaynak eski, yeniden doğrulama gerekli/)).toBeTruthy();
  });

  it('shows unknown rather than zero OHLCV when no bars file was provided', async () => {
    vi.mocked(dataCapabilityApi.getBistIdentitySummary).mockResolvedValue({
      ...evidence,
      prices_file_supplied: false,
      counts: {
        ...evidence.counts!,
        active_with_ohlcv_in_supplied_file_count: null,
        active_without_ohlcv_in_supplied_file_count: null,
      },
    });
    render(<BistIdentityPanel />);
    expect(await screen.findByText(/Gerçek OHLCV dosyası bu denetime verilmedi/)).toBeTruthy();
    expect(screen.getAllByText('—').length).toBeGreaterThanOrEqual(2);
  });

  it('clearly blocks local report visibility while admin authentication is disabled', async () => {
    vi.mocked(dataCapabilityApi.getBistIdentitySummary).mockResolvedValue({
      ...unavailable,
      reason: 'administrator_auth_required',
    });
    render(<BistIdentityPanel />);
    expect(await screen.findByText(/Yönetici kimlik doğrulaması kapalı/)).toBeTruthy();
    expect(screen.queryByRole('table')).toBeNull();
  });

  it('keeps source files missing status unknown', async () => {
    vi.mocked(dataCapabilityApi.getBistIdentitySummary).mockResolvedValue({
      ...unavailable,
      reason: 'bist_reference_files_missing',
    });
    render(<BistIdentityPanel />);
    expect(await screen.findByText(/Aktif hisse sayısı ve veri kapsamı bilinmiyor/)).toBeTruthy();
    expect(screen.queryByRole('table')).toBeNull();
  });

  it('does not show optimistic data when API request fails', async () => {
    vi.mocked(dataCapabilityApi.getBistIdentitySummary).mockRejectedValue(new Error('offline'));
    render(<BistIdentityPanel />);
    expect(await screen.findByRole('alert')).toBeTruthy();
    expect(screen.queryByRole('table')).toBeNull();
  });
});
