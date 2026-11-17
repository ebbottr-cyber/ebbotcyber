import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { UiLanguageProvider } from '../contexts/UiLanguageContext';
import NewsPage from './NewsPage';
import { newsApi } from '../api/news';

vi.mock('../api/news', () => ({
  NEWS_CHANGED_EVENT: 'etre:news-updated',
  newsApi: {
    list: vi.fn(), status: vi.fn(), refresh: vi.fn(), ai: vi.fn(),
    read: vi.fn(), readAll: vi.fn(), notifications: vi.fn(),
  },
}));

const article = {
  id: '1'.repeat(64), market: 'tr', title: 'BIST şirketleri',
  title_original: 'BIST şirketleri', title_tr: 'BIST şirketleri',
  summary_tr: 'Şirketlerden yeni açıklamalar geldi.', impact_tr: 'Etkisi belirsiz.',
  source: 'Örnek kaynak', url: 'https://news.google.com/news/example',
  published_at: '2026-11-16T18:00:00+00:00',
  inserted_at: '2026-11-16T18:00:00+00:00',
  severity: 'important', ai_status: 'complete', is_read: false,
};

describe('NewsPage', () => {
  beforeEach(() => {
    vi.mocked(newsApi.list).mockReset().mockResolvedValue([article] as never);
    vi.mocked(newsApi.status).mockReset().mockResolvedValue({
      unread_count: 1,
      notifications_enabled: true,
      ai_enabled: false,
      translation_waiting: 0,
      latest_unread: [],
    });
    vi.mocked(newsApi.read).mockReset().mockResolvedValue();
    vi.mocked(newsApi.readAll).mockReset().mockResolvedValue();
    vi.mocked(newsApi.notifications).mockReset().mockResolvedValue();
    vi.mocked(newsApi.ai).mockReset().mockResolvedValue();
    vi.mocked(newsApi.refresh).mockReset().mockResolvedValue({
      inserted: 0, failed_markets: [],
    });
    window.localStorage.setItem('dsa.uiLanguage', 'tr');
  });

  it('shows Turkish headlines and the publisher with a safe source link', async () => {
    render(<UiLanguageProvider><NewsPage /></UiLanguageProvider>);
    expect(await screen.findByText('BIST şirketleri')).toBeInTheDocument();
    expect(screen.getByText('Örnek kaynak')).toBeInTheDocument();
    expect(screen.getByRole('link', { name: /Kaynağa git/ })).toHaveAttribute(
      'rel', 'noopener noreferrer',
    );
  });

  it('marks all as read without deleting news or muting future arrivals', async () => {
    render(<UiLanguageProvider><NewsPage /></UiLanguageProvider>);
    await screen.findByText('BIST şirketleri');
    fireEvent.click(screen.getByRole('button', { name: /Tümünü okundu işaretle/ }));
    await waitFor(() => expect(newsApi.readAll).toHaveBeenCalledOnce());
    expect(newsApi.notifications).not.toHaveBeenCalled();
  });

  it('can turn off all future foreground alerts separately', async () => {
    render(<UiLanguageProvider><NewsPage /></UiLanguageProvider>);
    await screen.findByText('BIST şirketleri');
    fireEvent.click(screen.getByRole('button', { name: /Bildirimleri kapat/ }));
    await waitFor(() => expect(newsApi.notifications).toHaveBeenCalledWith(false));
  });
});
