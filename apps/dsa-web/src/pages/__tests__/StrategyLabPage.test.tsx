import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { UiLanguageProvider } from '../../contexts/UiLanguageContext';
import { UI_LANGUAGE_STORAGE_KEY } from '../../utils/uiLanguage';
import StrategyLabPage from '../StrategyLabPage';

const mocks = vi.hoisted(() => ({
  eligibleEtfs: vi.fn(),
  analyzeEtf: vi.fn(),
}));

vi.mock('../../api/strategyLab', () => ({
  strategyLabApi: {
    eligibleEtfs: mocks.eligibleEtfs,
    analyzeEtf: mocks.analyzeEtf,
  },
}));

const sample = {
  assetCode: '510300',
  strategy: 'single_etf_vs_cash',
  researchOnly: true,
  dataSource: 'AdjustedSource',
  historyStart: '2025-01-01',
  historyEnd: '2025-12-30',
  lookbackDays: 60,
  rebalance: 'weekly',
  feeBps: 10,
  slippageBps: 0,
  result: {
    observedReturnPct: 4.5,
    observedMaxDrawdownPct: 8,
    randomMedianReturnPct: 2.0,
    randomP05ReturnPct: -7,
    randomP95ReturnPct: 11,
    randomMedianMaxDrawdownPct: 10,
    fractionRandomAtLeastObserved: 0.25,
    buyAndHoldReturnPct: 3.3,
    entryCount: 3,
    exposureBars: 60,
    totalBars: 100,
    simulations: 500,
    distinctRandomSchedules: 400,
    informative: true,
    seed: 42,
  },
};

function mount() {
  render(<UiLanguageProvider><StrategyLabPage /></UiLanguageProvider>);
}

beforeEach(() => {
  window.localStorage.clear();
  window.localStorage.setItem(UI_LANGUAGE_STORAGE_KEY, 'tr');
  vi.clearAllMocks();
  mocks.eligibleEtfs.mockResolvedValue(['510300', '518880']);
  mocks.analyzeEtf.mockResolvedValue(sample);
});

describe('StrategyLabPage', () => {
  it('renders real API results only after explicitly clicking run', async () => {
    mount();
    await waitFor(() => expect(screen.getByRole('button', { name: /karşılaştır/i })).toBeEnabled());
    expect(mocks.analyzeEtf).not.toHaveBeenCalled();
    fireEvent.click(screen.getByRole('button', { name: /karşılaştır/i }));
    await waitFor(() => expect(mocks.analyzeEtf).toHaveBeenCalledWith('510300', 500));
    expect(await screen.findByText('4.50%')).toBeInTheDocument();
    expect(screen.getByText('25.00%')).toBeInTheDocument();
    expect(screen.getByText('AdjustedSource')).toBeInTheDocument();
    expect(screen.getByText(/gözlem modu/i)).toBeInTheDocument();
  });

  it('never shows old results after changing asset while request is pending', async () => {
    let settle!: (value: typeof sample) => void;
    mocks.analyzeEtf.mockImplementation(() => new Promise<typeof sample>((resolve) => {
      settle = resolve;
    }));
    mount();
    await screen.findByRole('option', { name: '518880' });
    fireEvent.click(screen.getByRole('button', { name: /karşılaştır/i }));
    fireEvent.change(screen.getByLabelText('ETF'), { target: { value: '518880' } });
    settle(sample);
    await waitFor(() => expect(screen.queryByText('4.50%')).not.toBeInTheDocument());
    expect(screen.getByText(/Henüz bir test yapılmadı/i)).toBeInTheDocument();
  });

  it('gives a clear unavailable-history message instead of fabricated metrics', async () => {
    mocks.analyzeEtf.mockRejectedValue(new Error('no adjusted history'));
    mount();
    await screen.findByRole('option', { name: '510300' });
    fireEvent.click(screen.getByRole('button', { name: /karşılaştır/i }));
    expect(await screen.findByRole('alert')).toHaveTextContent(/geçmiş veri yetersiz/i);
    expect(screen.queryByText('4.50%')).not.toBeInTheDocument();
  });

  it('does not enable a comparison when no ETF is configured', async () => {
    mocks.eligibleEtfs.mockResolvedValue([]);
    mount();
    expect(await screen.findByText(/ETF rotasyon havuzunda/i)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /karşılaştır/i })).toBeDisabled();
  });

  it('marks noninformative random timing universes explicitly', async () => {
    mocks.analyzeEtf.mockResolvedValue({ ...sample, result: { ...sample.result, informative: false } });
    mount();
    await screen.findByRole('option', { name: '510300' });
    fireEvent.click(screen.getByRole('button', { name: /karşılaştır/i }));
    expect(await screen.findByRole('alert')).toHaveTextContent(/yeterince farklı zamanlama yok/i);
  });
});
