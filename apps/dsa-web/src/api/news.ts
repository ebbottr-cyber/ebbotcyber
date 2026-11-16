import apiClient from './index';

export type NewsMarket = 'tr' | 'us' | 'de' | 'hk' | 'crypto';
export type NewsSeverity = 'normal' | 'important' | 'breaking';
export type NewsArticle = {
  id: string; market: NewsMarket; title: string; title_original: string;
  title_tr: string | null; summary_tr: string | null; impact_tr: string | null;
  url: string; source: string; published_at: string; inserted_at: string;
  severity: NewsSeverity; is_read: boolean; ai_status: string;
};

export type NewsStatus = {
  unread_count: number;
  notifications_enabled: boolean;
  latest_unread: Array<{
    id: string; market: NewsMarket; title: string; title_tr: string | null;
    published_at: string; inserted_at: string; severity: NewsSeverity;
    ai_status: string;
  }>;
};

export const NEWS_CHANGED_EVENT = 'etre:news-updated';

export const newsApi = {
  async list(params: { market?: NewsMarket; unread_only?: boolean; limit?: number } = {}): Promise<NewsArticle[]> {
    const response = await apiClient.get<{ items: NewsArticle[] }>('/api/v1/news/items', { params });
    return response.data.items;
  },
  async status(): Promise<NewsStatus> {
    const response = await apiClient.get<NewsStatus>('/api/v1/news/status');
    return response.data;
  },
  async refresh(): Promise<{ inserted: number; failed_markets: string[] }> {
    const response = await apiClient.post('/api/v1/news/refresh');
    return response.data;
  },
  async read(id: string): Promise<void> {
    await apiClient.post('/api/v1/news/' + encodeURIComponent(id) + '/read');
    window.dispatchEvent(new Event(NEWS_CHANGED_EVENT));
  },
  async readAll(): Promise<void> {
    await apiClient.post('/api/v1/news/read-all');
    window.dispatchEvent(new Event(NEWS_CHANGED_EVENT));
  },
  async notifications(enabled: boolean): Promise<void> {
    await apiClient.put('/api/v1/news/notifications', { enabled });
    window.dispatchEvent(new Event(NEWS_CHANGED_EVENT));
  },
};
