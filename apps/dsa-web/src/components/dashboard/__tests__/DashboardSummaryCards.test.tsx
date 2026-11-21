import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { PortfolioSummaryContent, RiskSummaryContent } from '../PortfolioRiskSummaryCards';
import { TaskFeedContent, WatchlistOverviewContent, taskStatus } from '../WatchlistTaskCards';
import type { PortfolioRiskResponse, PortfolioSnapshotResponse } from '../../../types/portfolio';
import type { HistoryItem, TaskInfo } from '../../../types/analysis';

const portfolio = {
  asOf: '2026-11-17', accountCount: 2, currency: 'TRY', totalEquity: 10000,
  totalCash: 2500, totalMarketValue: 7500, fxStale: false, dataQuality: 'ok',
} as PortfolioSnapshotResponse;

const risk = {
  asOf: '2026-11-17',
  concentration: { topWeightPct: 42, alert: false },
  drawdown: { currentDrawdownPct: 3.5, alert: false },
  stopLoss: { triggeredCount: 0, nearAlert: false },
} as PortfolioRiskResponse;

const report = {
  id: 5, queryId: 'Q1', stockCode: 'THYAO.IS', stockName: 'Türk Hava Yolları',
  currentPrice: 322.1, createdAt: '2026-11-17T10:00:00Z',
} as HistoryItem;

const task = {
  taskId: 'task-1', stockCode: 'THYAO.IS', status: 'processing',
  progress: 58, createdAt: '2026-11-18T10:00:00Z', reportType: 'detailed',
} as TaskInfo;

describe('EBBot white dashboard insight cards', () => {
  it('shows labelled source portfolio values and cash-to-equity ratio', () => {
    render(<PortfolioSummaryContent snapshot={portfolio} loading={false} failed={false} />);
    expect(screen.getByText('10.000')).toBeInTheDocument();
    expect(screen.getByText('2.500')).toBeInTheDocument();
    expect(screen.getByText('7.500')).toBeInTheDocument();
    expect(screen.getByText('25%')).toBeInTheDocument();
    expect(screen.getByText(/2 hesap/)).toBeInTheDocument();
  });

  it('labels limited portfolio valuation and hides old figures on refresh/error', () => {
    const partial = { ...portfolio, fxStale: true, dataQuality: 'partial' };
    const view = render(<PortfolioSummaryContent snapshot={partial} loading={false} failed={false} />);
    expect(screen.getByText(/Kısmi veya gecikmeli değerleme/)).toBeInTheDocument();
    view.rerender(<PortfolioSummaryContent snapshot={partial} loading failed={false} />);
    expect(screen.queryByText('10.000')).not.toBeInTheDocument();
    expect(screen.getByText(/yükleniyor/)).toBeInTheDocument();
    view.rerender(<PortfolioSummaryContent snapshot={partial} loading={false} failed />);
    expect(screen.queryByText('10.000')).not.toBeInTheDocument();
    expect(screen.getByText(/Portföy kaynağına erişilemedi/)).toBeInTheDocument();
  });

  it('shows actual risk metrics without inventing a global safety score', () => {
    render(<RiskSummaryContent risk={risk} loading={false} failed={false} />);
    expect(screen.getByText('42%')).toBeInTheDocument();
    expect(screen.getByText('3,5%')).toBeInTheDocument();
    expect(screen.getByRole('progressbar', { name: 'Güncel düşüş' })).toHaveAttribute('aria-valuenow', '3.5');
    expect(screen.getByText(/kesin güvenli işlem onayı anlamına gelmez/)).toBeInTheDocument();
  });

  it('does not paint missing or invalid risk measurements as a zero-risk bar', () => {
    const invalid = { ...risk, concentration: { ...risk.concentration, topWeightPct: Number.NaN }, drawdown: { ...risk.drawdown, currentDrawdownPct: undefined } } as unknown as PortfolioRiskResponse;
    render(<RiskSummaryContent risk={invalid} loading={false} failed={false} />);
    expect(screen.queryAllByRole('progressbar')).toHaveLength(0);
    expect(screen.getAllByText('Veri yok')).toHaveLength(2);
    expect(screen.getAllByText('Hesaplanabilir risk ölçümü yok.')).toHaveLength(2);
  });

  it('clears risk details when the service fails', () => {
    render(<RiskSummaryContent risk={risk} loading={false} failed />);
    expect(screen.queryByText('42%')).not.toBeInTheDocument();
    expect(screen.getByText('Risk servisine erişilemedi.')).toBeInTheDocument();
  });

  it('selects a watchlist stock without implying live quotes or requiring a report', () => {
    const onSelect = vi.fn();
    render(<WatchlistOverviewContent codes={['THYAO.IS', 'ASELS.IS']} history={[report]}
      loading={false} currentCode="THYAO.IS" onSelect={onSelect} onManage={vi.fn()} />);
    expect(screen.getByText('322,1')).toBeInTheDocument();
    expect(screen.getByText('Son analiz fiyatı')).toBeInTheDocument();
    expect(screen.getByText('Analiz fiyatı yok')).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'ASELS.IS grafiğini göster' }));
    expect(onSelect).toHaveBeenCalledWith('ASELS.IS');
    expect(screen.getByText(/canlı kotasyon değildir/)).toBeInTheDocument();
  });

  it('maps every task status into Turkish and clamps progress', () => {
    expect(taskStatus('completed').label).toBe('Tamamlandı');
    expect(taskStatus('failed').label).toBe('Hata');
    expect(taskStatus('pending').label).toBe('Sırada');
    expect(taskStatus('cancel_requested').label).toBe('İptal istenmiş');
    expect(taskStatus('cancelled').label).toBe('İptal edildi');
    render(<TaskFeedContent tasks={[{ ...task, progress: 125 }]} loading={false} failed={false} onOpen={vi.fn()} />);
    expect(screen.getByRole('progressbar')).toHaveAttribute('aria-valuenow', '100');
    expect(screen.getByText('100% tamamlandı')).toBeInTheDocument();
  });

  it('only displays progress for running tasks and keeps errors distinct', () => {
    render(<TaskFeedContent tasks={[
      { ...task, taskId: 'pending', status: 'pending', progress: 0 },
      { ...task, taskId: 'failure', status: 'failed', progress: 97, error: 'Kaynağa ulaşılamadı' },
    ]} loading={false} failed={false} onOpen={vi.fn()} />);
    expect(screen.queryByRole('progressbar')).not.toBeInTheDocument();
    expect(screen.getByText('Sırada')).toBeInTheDocument();
    expect(screen.getByText(/Kaynağa ulaşılamadı/)).toBeInTheDocument();
  });

  it('never shows old tasks when the task API is unavailable', () => {
    render(<TaskFeedContent tasks={[task]} loading={false} failed onOpen={vi.fn()} />);
    expect(screen.queryByText('58% tamamlandı')).not.toBeInTheDocument();
    expect(screen.getByText('Görev listesine erişilemedi.')).toBeInTheDocument();
  });
});
