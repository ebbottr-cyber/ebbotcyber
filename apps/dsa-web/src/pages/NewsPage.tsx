import type React from 'react';
import { useCallback, useEffect, useMemo, useState } from 'react';
import { Bell, BellOff, CheckCheck, ExternalLink, RefreshCw, Search } from 'lucide-react';
import { newsApi, NEWS_CHANGED_EVENT, type NewsArticle, type NewsMarket } from '../api/news';
import { useUiLanguage } from '../contexts/UiLanguageContext';
import type { UiLanguage } from '../i18n/uiText';
import { AppPage, Card, PageHeader } from '../components/common';

type MarketChoice = NewsMarket | 'all';
const CATEGORIES: Record<UiLanguage, Record<MarketChoice, string>> = {
  tr: { all: 'Tümü', tr: 'Türkiye', us: 'ABD', de: 'Almanya', hk: 'Hong Kong', crypto: 'Kripto' },
  en: { all: 'All', tr: 'Türkiye', us: 'USA', de: 'Germany', hk: 'Hong Kong', crypto: 'Crypto' },
  zh: { all: '全部', tr: '土耳其', us: '美国', de: '德国', hk: '香港', crypto: '加密货币' },
};
const LABELS: Record<UiLanguage, Record<string, string>> = {
  tr: {
    title: 'Haberler', description: 'Türkiye, ABD, Almanya, Hong Kong ve kriptodan piyasa haberleri',
    info: 'Ücretsiz Google Haberler RSS kaynakları kullanılır. Başlık, kaynak bağlantısı ve izin verilen özet gösterilir; makalenin tamamı kopyalanmaz.',
    allRead: 'Tümünü okundu işaretle', showUnread: 'Yalnızca okunmamışlar',
    read: 'Okundu işaretle', unread: 'Okunmadı', readDone: 'Okundu',
    refresh: 'Şimdi yenile', loading: 'Haberler yükleniyor…', empty: 'Bu filtrede haber bulunamadı.',
    search: 'Haber başlığı veya kaynak ara', published: 'Yayın tarihi',
    normal: 'Genel', important: 'Önemli', breaking: 'Son dakika',
    aiReady: 'AI değerlendirildi', aiWaiting: 'AI / Türkçe çeviri bekleniyor',
    aiFailed: 'AI çevirisi alınamadı', impact: 'AI piyasa etkisi', summary: 'Türkçe özet',
    source: 'Kaynağa git', enabled: 'Haber bildirimleri açık',
    disabled: 'Haber bildirimleri kapalı', toggleOn: 'Bildirimleri aç',
    toggleOff: 'Bildirimleri kapat', browserOn: 'Tarayıcı bildirimi izni ver',
    browserHint: 'Tarayıcı bildirimi yalnızca ETRE sekmesi açıkken ve izin verildiğinde çalışır.',
    readCount: 'Okunmamış haber', failed: 'Haber servisine bağlanılamadı.',
    recent: 'Yeni haberler geldikçe burada listelenir.',
    note: 'AI etkisi yalnızca haber başlığına dayanır; kesin fiyat yönü veya işlem tavsiyesi değildir. Türkçe çeviri için ETRE AI modeli yapılandırılmalı ve NEWS_AI_ENABLED=true olarak açılmalıdır.',
    refreshing: 'RSS kaynakları kontrol ediliyor…',
  },
  en: {
    title: 'News', description: 'Market headlines from Türkiye, USA, Germany, Hong Kong and crypto',
    info: 'Free Google News RSS metadata and links. Full copyrighted articles are not reproduced.',
    allRead: 'Mark all as read', showUnread: 'Unread only', read: 'Mark read', unread: 'Unread', readDone: 'Read',
    refresh: 'Refresh now', loading: 'Loading news…', empty: 'No news matches this filter.',
    search: 'Search headlines or sources', published: 'Published',
    normal: 'General', important: 'Important', breaking: 'Breaking',
    aiReady: 'AI evaluated', aiWaiting: 'Awaiting AI / Turkish translation',
    aiFailed: 'AI translation unavailable', impact: 'AI market impact', summary: 'Turkish summary',
    source: 'Open source', enabled: 'News alerts on', disabled: 'News alerts off',
    toggleOn: 'Enable alerts', toggleOff: 'Mute alerts', browserOn: 'Enable browser alerts',
    browserHint: 'Browser alerts only work while ETRE is open and permission is granted.',
    readCount: 'Unread', failed: 'News service unavailable.', recent: 'New stories appear here as they arrive.',
    note: 'AI impact is based only on the headline, not a trading signal. Turkish translation needs a configured ETRE AI model and NEWS_AI_ENABLED=true.',
    refreshing: 'Checking RSS sources…',
  },
  zh: {
    title: '新闻', description: '土耳其、美国、德国、香港和加密货币市场资讯',
    info: '免费 Google 新闻 RSS 标题与来源链接；不复制完整版权文章。',
    allRead: '全部标为已读', showUnread: '只看未读', read: '标为已读', unread: '未读', readDone: '已读',
    refresh: '立即刷新', loading: '加载新闻…', empty: '没有匹配的新闻。',
    search: '搜索标题或来源', published: '发布时间',
    normal: '普通', important: '重要', breaking: '突发',
    aiReady: 'AI 已分析', aiWaiting: '等待 AI / 土耳其语翻译',
    aiFailed: 'AI 翻译不可用', impact: 'AI 市场影响', summary: '土耳其语摘要',
    source: '查看原文', enabled: '通知开启', disabled: '通知已关闭',
    toggleOn: '开启通知', toggleOff: '关闭通知', browserOn: '启用浏览器提醒',
    browserHint: '浏览器提醒仅在 ETRE 打开并授权时工作。',
    readCount: '未读新闻', failed: '新闻服务不可用。', recent: '新新闻将持续更新。',
    note: 'AI 影响仅根据标题推断，不构成交易建议。土耳其语翻译需要启用 ETRE AI 和 NEWS_AI_ENABLED=true。',
    refreshing: '检查 RSS…',
  },
};

const order: MarketChoice[] = ['all', 'tr', 'us', 'de', 'hk', 'crypto'];
const level: Record<NewsArticle['severity'], string> = {
  normal: 'bg-surface text-secondary-text',
  important: 'border border-warning/50 text-warning',
  breaking: 'border border-danger/50 text-danger',
};

const NewsPage: React.FC = () => {
  const { language } = useUiLanguage();
  const t = LABELS[language];
  const [articles, setArticles] = useState<NewsArticle[]>([]);
  const [unreadCount, setUnreadCount] = useState(0);
  const [notificationsEnabled, setNotificationsEnabled] = useState(true);
  const [market, setMarket] = useState<MarketChoice>('all');
  const [unreadOnly, setUnreadOnly] = useState(false);
  const [search, setSearch] = useState('');
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState(false);

  const load = useCallback(async () => {
    try {
      const [news, status] = await Promise.all([
        newsApi.list({ limit: 200 }),
        newsApi.status(),
      ]);
      setArticles(news);
      setUnreadCount(status.unread_count);
      setNotificationsEnabled(status.notifications_enabled);
      setError(false);
    } catch {
      setError(true);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
    const interval = window.setInterval(() => void load(), 60000);
    window.addEventListener(NEWS_CHANGED_EVENT, load);
    return () => {
      window.clearInterval(interval);
      window.removeEventListener(NEWS_CHANGED_EVENT, load);
    };
  }, [load]);

  const visible = useMemo(() => articles.filter(article =>
    (market === 'all' || article.market === market) &&
    (!unreadOnly || !article.is_read) &&
    (article.title_original + ' ' + (article.title_tr ?? '') + ' ' + article.source)
      .toLocaleLowerCase().includes(search.toLocaleLowerCase())
  ), [articles, market, unreadOnly, search]);

  const refresh = async () => {
    setRefreshing(true);
    try {
      await newsApi.refresh();
      await load();
      window.dispatchEvent(new Event(NEWS_CHANGED_EVENT));
    } catch {
      setError(true);
    } finally {
      setRefreshing(false);
    }
  };

  const markRead = async (id: string) => {
    try { await newsApi.read(id); await load(); } catch { setError(true); }
  };
  const readAll = async () => {
    try { await newsApi.readAll(); await load(); } catch { setError(true); }
  };
  const changeAlerts = async () => {
    try { await newsApi.notifications(!notificationsEnabled); await load(); } catch { setError(true); }
  };
  const allowBrowser = () => {
    if ('Notification' in window) void Notification.requestPermission();
  };

  return (
    <AppPage className="space-y-5">
      <PageHeader eyebrow={t.title} title={t.title} description={t.description} />
      <Card variant="bordered" padding="md">
        <div className="space-y-4">
          <p className="text-sm text-secondary-text">{t.info}</p>
          <div className="flex flex-wrap items-center gap-2">
            <strong className="rounded-full border border-border px-3 py-1 text-sm">
              {t.readCount}: {unreadCount}
            </strong>
            <button type="button" onClick={() => void readAll()} disabled={unreadCount === 0}
              className="inline-flex items-center gap-2 rounded-lg border border-border px-3 py-2 text-sm text-foreground disabled:opacity-40">
              <CheckCheck className="h-4 w-4" />{t.allRead}
            </button>
            <button type="button" onClick={() => void changeAlerts()}
              className="inline-flex items-center gap-2 rounded-lg border border-border px-3 py-2 text-sm text-foreground">
              {notificationsEnabled ? <Bell className="h-4 w-4" /> : <BellOff className="h-4 w-4" />}
              {notificationsEnabled ? t.toggleOff : t.toggleOn}
            </button>
            <button type="button" onClick={() => void refresh()} disabled={refreshing}
              className="inline-flex items-center gap-2 rounded-lg border border-border px-3 py-2 text-sm text-foreground disabled:opacity-40">
              <RefreshCw className="h-4 w-4" />{refreshing ? t.refreshing : t.refresh}
            </button>
            {'Notification' in window && Notification.permission === 'default' && (
              <button type="button" onClick={allowBrowser}
                className="rounded-lg border border-border px-3 py-2 text-sm text-foreground">
                {t.browserOn}
              </button>
            )}
          </div>
          <p className="text-xs text-muted-text">{notificationsEnabled ? t.enabled : t.disabled} · {t.browserHint}</p>
          <div className="flex flex-wrap gap-2">
            {order.map(category => (
              <button key={category} type="button" onClick={() => setMarket(category)}
                aria-pressed={market === category}
                className={'rounded-lg border px-3 py-2 text-xs ' +
                  (market === category ? 'border-primary bg-primary/10 text-foreground' : 'border-border text-secondary-text')}>
                {CATEGORIES[language][category]}
              </button>
            ))}
          </div>
          <div className="flex flex-wrap gap-3">
            <label className="inline-flex items-center gap-2 text-xs text-secondary-text">
              <input type="checkbox" checked={unreadOnly} onChange={e => setUnreadOnly(e.target.checked)} />
              {t.showUnread}
            </label>
            <div className="flex min-w-0 flex-1 items-center gap-2 rounded-lg border border-border px-3">
              <Search className="h-4 w-4 text-muted-text" />
              <input className="w-full bg-transparent py-2 text-sm outline-none" placeholder={t.search}
                aria-label={t.search} value={search} onChange={e => setSearch(e.target.value)} />
            </div>
          </div>
        </div>
      </Card>
      {error ? <p role="alert" className="text-sm text-danger">{t.failed}</p> : null}
      {loading ? <p className="text-sm text-muted-text">{t.loading}</p> : null}
      {!loading && visible.length === 0 ? <p className="text-sm text-muted-text">{t.empty} {t.recent}</p> : null}
      <div className="space-y-3">
        {visible.map(item => (
          <article key={item.id} className={'rounded-xl border p-4 ' +
            (item.is_read ? 'border-border/60 bg-card/50' : 'border-primary/40 bg-card/85')}>
            <div className="mb-2 flex flex-wrap items-center gap-2 text-xs text-muted-text">
              <span className="font-semibold">{CATEGORIES[language][item.market]}</span>
              <span>{item.source}</span>
              <span>{new Date(item.published_at).toLocaleString(language === 'tr' ? 'tr-TR' : language === 'zh' ? 'zh-CN' : 'en-US')}</span>
              <span className={'rounded-full px-2 py-1 ' + level[item.severity]}>{t[item.severity]}</span>
              <span>{item.is_read ? t.readDone : t.unread}</span>
            </div>
            <h2 className="text-base font-semibold leading-relaxed text-foreground">{item.title}</h2>
            {item.summary_tr ? <p className="mt-2 text-sm text-secondary-text">{t.summary}: {item.summary_tr}</p> : null}
            {item.impact_tr ? <p className="mt-2 text-sm text-secondary-text">{t.impact}: {item.impact_tr}</p> : null}
            <p className="mt-2 text-xs text-muted-text">{item.ai_status === 'complete' ? t.aiReady :
              item.ai_status === 'failed' ? t.aiFailed : t.aiWaiting}</p>
            <div className="mt-3 flex flex-wrap gap-3">
              <a href={item.url} target="_blank" rel="noopener noreferrer"
                className="inline-flex items-center gap-1 text-sm text-primary underline">
                {t.source} <ExternalLink className="h-3.5 w-3.5" />
              </a>
              {!item.is_read && <button type="button" onClick={() => void markRead(item.id)}
                className="text-sm text-foreground underline">{t.read}</button>}
            </div>
          </article>
        ))}
      </div>
      <p role="note" className="text-xs leading-relaxed text-muted-text">{t.note}</p>
    </AppPage>
  );
};

export default NewsPage;
