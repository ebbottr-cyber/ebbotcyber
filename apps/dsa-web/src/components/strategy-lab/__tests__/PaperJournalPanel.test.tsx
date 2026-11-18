import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { UiLanguageProvider } from '../../../contexts/UiLanguageContext';
import { UI_LANGUAGE_STORAGE_KEY } from '../../../utils/uiLanguage';
import PaperJournalPanel from '../PaperJournalPanel';

const mocks = vi.hoisted(() => ({ inspectPaperJournal: vi.fn() }));

vi.mock('../../../api/strategyLab', () => ({
  inspectPaperJournal: mocks.inspectPaperJournal,
}));

const validReport = {
  status: 'PAPER_ONLY',
  researchOnly: true,
  source: 'MockAdjusted',
  assetCode: '510300',
  recordCount: 2,
  firstSession: '2026-11-13',
  lastSession: '2026-11-16',
  lastObservedAtUtc: '2026-11-16T10:00:00+00:00',
  lastEquity: 0.9985,
  observedReturnPct: -0.15,
  observedMaxDrawdownPct: 0.15,
  paperBuyCount: 1,
  paperSellCount: 0,
  invested: true,
  nextExpectedSession: '2026-11-17',
  events: [{ session: '2026-11-16', paperFill: 'BUY', paperInvested: true, signalRecorded: false, equity: 0.9985 }],
  verifiedHashChain: true,
  note: 'Integrity checked',
};

function mount() {
  render(<UiLanguageProvider><PaperJournalPanel /></UiLanguageProvider>);
}

function upload(content: string, filename = 'paper.jsonl') {
  const file = new File([content], filename, { type: 'text/plain' });
  Object.defineProperty(file, 'text', { value: vi.fn().mockResolvedValue(content) });
  fireEvent.change(screen.getByLabelText(/Günlüğü kontrol et/), { target: { files: [file] } });
}

beforeEach(() => {
  localStorage.clear();
  localStorage.setItem(UI_LANGUAGE_STORAGE_KEY, 'tr');
  vi.clearAllMocks();
  mocks.inspectPaperJournal.mockResolvedValue(validReport);
});

describe('PaperJournalPanel', () => {
  it('does not load remote data or use demo values on mount', () => {
    mount();
    expect(screen.getByText(/Henüz sanal işlem günlüğü seçilmedi/)).toBeInTheDocument();
    expect(mocks.inspectPaperJournal).not.toHaveBeenCalled();
    expect(screen.queryByText('510300')).not.toBeInTheDocument();
  });

  it('uploads selected local JSONL only for inspection and displays returned metrics', async () => {
    mount();
    upload('{"seq":0}\n');
    await waitFor(() => expect(mocks.inspectPaperJournal).toHaveBeenCalledWith('{"seq":0}\n'));
    expect(await screen.findByText('-%0.15')).toBeInTheDocument();
    expect(screen.getByText('MockAdjusted', { exact: false })).toBeInTheDocument();
    expect(screen.getByText('0.9985')).toBeInTheDocument();
    expect(screen.getByText(/Kayıt bütünlüğü doğrulandı/)).toBeInTheDocument();
  });

  it('never shows numbers when authentication or integrity validation fails', async () => {
    mocks.inspectPaperJournal.mockRejectedValue(new Error('403 auth_required'));
    mount();
    upload('bad\n');
    expect(await screen.findByRole('alert')).toHaveTextContent(/Günlük doğrulanamadı/);
    expect(screen.queryByText('-%0.15')).not.toBeInTheDocument();
  });

  it('rejects overlarge local files before upload', async () => {
    mount();
    const file = new File(['x'.repeat(524289)], 'huge.jsonl', { type: 'text/plain' });
    fireEvent.change(screen.getByLabelText(/Günlüğü kontrol et/), { target: { files: [file] } });
    expect(await screen.findByRole('alert')).toHaveTextContent(/512 KiB/);
    expect(mocks.inspectPaperJournal).not.toHaveBeenCalled();
  });
});
