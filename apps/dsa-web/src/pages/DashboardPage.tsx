import type React from 'react';
import { useCallback, useEffect, useMemo, useState } from 'react';
import { Activity, ArrowRight, Bell, BarChart3, CheckCheck, ChevronRight, Newspaper, RefreshCcw, Search, Sparkles } from 'lucide-react';
import { Link, useNavigate } from 'react-router-dom';
import { dashboardApi, type DashboardBar, type DashboardQuote } from '../api/dashboard';
import { coinGeckoApi, type CoinGeckoCoin } from '../api/coinGecko';
import { newsApi, NEWS_CHANGED_EVENT, type NewsArticle, type NewsMarket } from '../api/news';
import { useUiLanguage } from '../contexts/UiLanguageContext';
import { getStockDisplayName } from '../utils/stockDisplayName';

type SelectedMarket = 'all' | NewsMarket;
type MarketTile = { market: NewsMarket; label: string; code: string; short: string };

const STOCK_MARKETS: MarketTile[] = [
  { market: 'tr', label: 'Türkiye', code: 'THYAO.IS', short: 'THYAO' },
  { market: 'us', label: 'ABD', code: 'AAPL', short: 'AAPL' },
  { market: 'de', label: 'Almanya', code: 'SAP.DE', short: 'SAP' },
  { market: 'hk', label: 'Hong Kong', code: '0700.HK', short: '0700.HK' },
];
const MARKETS: Array<{ code: SelectedMarket; label: string; icon: string }> = [
  { code: 'all', label: 'Tümü', icon: '🌐' },
  { code: 'tr', label: 'Türkiye', icon: '🇹🇷' },
  { code: 'us', label: 'ABD', icon: '🇺🇸' },
  { code: 'de', label: 'Almanya', icon: '🇩🇪' },
  { code: 'hk', label: 'Hong Kong', icon: '🇭🇰' },
  { code: 'crypto', label: 'Kripto', icon: '₿' },
];

function formatNumber(number: number | null | undefined, language: string, digits = 2): string {
  if (typeof number !== 'number' || !Number.isFinite(number)) return '—';
  return new Intl.NumberFormat(language === 'tr' ? 'tr-TR' : 'en-US', {
    minimumFractionDigits: 0,
    maximumFractionDigits: number > 0 && number < 1 ? 6 : digits,
  }).format(number);
}

function formatPercent(number: number | null | undefined, language: string): string {
  if (typeof number !== 'number' || !Number.isFinite(number)) return '—';
  return (number > 0 ? '+' : '') + formatNumber(number, language, 2) + '%';
}

function isValidQuote(raw: DashboardQuote | undefined): raw is DashboardQuote {
  return Boolean(raw && Number.isFinite(raw.current_price) && raw.current_price > 0);
}

function movingAverage(bars: DashboardBar[], span: number): number | null {
  if (bars.length < span) return null;
  return bars.slice(-span).reduce((sum, item) => sum + item.close, 0) / span;
}

function movingAveragePath(
  data: DashboardBar[],
  span: number,
  x: (i: number) => number,
  y: (value: number) => number,
): string {
  let path = '';
  for (let i = span - 1; i < data.length; i += 1) {
    const avg = data.slice(i - span + 1, i + 1).reduce((sum, item) => sum + item.close, 0) / span;
    path += (path ? ' L' : 'M') + x(i).toFixed(2) + ',' + y(avg).toFixed(2);
  }
  return path;
}

function StockCandlestickChart({ bars, language }: { bars: DashboardBar[]; language: string }) {
  const data = bars.slice(-70);
  if (data.length < 2) {
    return <div className="etre-chart-placeholder">Grafik için doğrulanmış geçmiş fiyat verisi bulunamadı.</div>;
  }
  const width = 760; const height = 325;
  const left = 25; const right = 65; const top = 18; const bottom = 48;
  const plotWidth = width - left - right;
  const plotHeight = height - top - bottom;
  const low = Math.min(...data.map(item => item.low));
  const high = Math.max(...data.map(item => item.high));
  const extent = high - low || high * 0.04 || 1;
  const min = Math.max(0, low - extent * .06);
  const max = high + extent * .07;
  const y = (value: number) => top + ((max - value) / (max - min)) * plotHeight;
  const x = (index: number) => left + ((index + .5) / data.length) * plotWidth;
  const candleWidth = Math.max(2, Math.min(8, plotWidth / data.length * .64));
  const labels = [0, .25, .5, .75, 1];
  const last = data[data.length - 1];

  return (
    <svg viewBox="0 0 760 325" role="img" aria-label="Gerçek geçmiş OHLC verileriyle çizilmiş mum grafiği">
      {labels.map((tick, i) => {
        const yy = top + tick * plotHeight;
        const price = max - tick * (max - min);
        return <g key={i}>
          <line x1={left} y1={yy} x2={left + plotWidth} y2={yy}
            stroke="currentColor" strokeOpacity=".10" strokeDasharray="3 5" />
          <text x={left + plotWidth + 7} y={yy + 4} fontSize="12"
            fill="currentColor" opacity=".6">{formatNumber(price, language)}</text>
        </g>;
      })}
      {data.map((item, i) => {
        const positive = item.close >= item.open;
        const stroke = positive ? '#12a970' : '#ec5361';
        const topBody = Math.min(y(item.close), y(item.open));
        const bodyHeight = Math.max(1.5, Math.abs(y(item.open) - y(item.close)));
        return <g key={item.date + ':' + i}>
          <line x1={x(i)} y1={y(item.high)} x2={x(i)} y2={y(item.low)}
            stroke={stroke} strokeWidth="1.4" />
          <rect x={x(i) - candleWidth / 2} y={topBody}
            width={candleWidth} height={bodyHeight} fill={stroke} rx=".6" />
        </g>;
      })}
      {([5, 10, 20] as const).map((span, i) => (
        <path key={span} d={movingAveragePath(data, span, x, y)}
          fill="none" stroke={['#2085f7', '#f5a623', '#9b69e8'][i]}
          strokeWidth="2" strokeLinejoin="round" strokeLinecap="round" />
      ))}
      <line x1={left} x2={left + plotWidth} y1={y(last.close)} y2={y(last.close)}
        stroke="#1d79ee" strokeDasharray="4 4" strokeOpacity=".5" />
      {[0, Math.floor(data.length / 3), Math.floor(data.length * 2 / 3), data.length - 1].map(i => (
        <text key={i} x={x(i)} y={height - 16} textAnchor="middle"
          fontSize="12" fill="currentColor" opacity=".62">
          {data[i].date.slice(5)}
        </text>
      ))}
    </svg>
  );
}

const DashboardPage: React.FC = () => {
  const { language } = useUiLanguage();
  const navigate = useNavigate();
  const [filter, setFilter] = useState<SelectedMarket>('all');
  const [watchlist, setWatchlist] = useState<string[]>([]);
  const [watchlistLoaded, setWatchlistLoaded] = useState(false);
  const [quotes, setQuotes] = useState<Record<string, DashboardQuote>>({});
  const [coinRows, setCoinRows] = useState<CoinGeckoCoin[]>([]);
  const [cryptoUnavailable, setCryptoUnavailable] = useState(false);
  const [news, setNews] = useState<NewsArticle[]>([]);
  const [newsError, setNewsError] = useState(false);
  const [unread, setUnread] = useState(0);
  const [selectedCode, setSelectedCode] = useState('THYAO.IS');
  const [days, setDays] = useState(90);
  const [bars, setBars] = useState<DashboardBar[]>([]);
  const [chartLoading, setChartLoading] = useState(false);
  const [chartError, setChartError] = useState(false);
  const [search, setSearch] = useState('');

  useEffect(() => {
    let alive = true;
    const begin = async () => {
      const [stockList, crypto] = await Promise.allSettled([
        dashboardApi.getWatchlist(), coinGeckoApi.getTop100(),
      ]);
      if (!alive) return;
      if (stockList.status === 'fulfilled') {
        setWatchlist(stockList.value);
        if (stockList.value.length > 0) setSelectedCode(stockList.value[0]);
      }
      setWatchlistLoaded(true);
      if (crypto.status === 'fulfilled') {
        setCoinRows(crypto.value.coins);
      } else {
        setCryptoUnavailable(true);
      }
    };
    void begin();
    const marketSymbols = STOCK_MARKETS.map(market => market.code);
    void Promise.allSettled(marketSymbols.map(code =>
      dashboardApi.getQuote(code).then(value => ({ code, value })),
    )).then(results => {
      if (!alive) return;
      const values: Record<string, DashboardQuote> = {};
      for (const result of results) {
        if (result.status === 'fulfilled' && isValidQuote(result.value.value)) {
          values[result.value.code] = result.value.value;
        }
      }
      setQuotes(previous => ({ ...previous, ...values }));
    });
    return () => { alive = false; };
  }, []);

  const loadNews = useCallback(async () => {
    try {
      const [items, status] = await Promise.all([
        newsApi.list({ limit: 25 }), newsApi.status(),
      ]);
      setNews(items);
      setUnread(status.unread_count);
      setNewsError(false);
    } catch {
      setNewsError(true);
    }
  }, []);

  useEffect(() => {
    void loadNews();
    const interval = window.setInterval(() => void loadNews(), 60000);
    window.addEventListener(NEWS_CHANGED_EVENT, loadNews);
    return () => {
      window.clearInterval(interval);
      window.removeEventListener(NEWS_CHANGED_EVENT, loadNews);
    };
  }, [loadNews]);

  useEffect(() => {
    let alive = true;
    setChartLoading(true);
    setChartError(false);
    setBars([]);
    void Promise.allSettled([
      dashboardApi.getHistory(selectedCode, days),
      dashboardApi.getQuote(selectedCode),
    ]).then(results => {
      if (!alive) return;
      if (results[0].status === 'fulfilled') {
        setBars(results[0].value);
        setChartError(results[0].value.length < 2);
      } else {
        setChartError(true);
      }
      if (results[1].status === 'fulfilled' && isValidQuote(results[1].value)) {
        const quote = results[1].value;
        setQuotes(previous => ({ ...previous, [selectedCode]: quote }));
      }
      setChartLoading(false);
    });
    return () => { alive = false; };
  }, [selectedCode, days]);

  const rows = useMemo(() =>
    [...new Set(watchlist)].slice(0, 7), [watchlist]);

  useEffect(() => {
    if (rows.length === 0) return undefined;
    let alive = true;
    const outstanding = rows.filter(code => !quotes[code]);
    if (outstanding.length) {
      void Promise.allSettled(outstanding.map(code =>
        dashboardApi.getQuote(code).then(value => ({ code, value })),
      )).then(results => {
        if (!alive) return;
        setQuotes(previous => {
          const next = { ...previous };
          results.forEach(result => {
            if (result.status === 'fulfilled' && isValidQuote(result.value.value)) {
              next[result.value.code] = result.value.value;
            }
          });
          return next;
        });
      });
    }
    return () => { alive = false; };
    // Initial watchlist snapshot only; quote reloads on individual stock selection.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [rows]);

  const selectedQuote = quotes[selectedCode];
  const ma5 = movingAverage(bars, 5);
  const ma10 = movingAverage(bars, 10);
  const ma20 = movingAverage(bars, 20);
  const lastClose = bars.length > 0 ? bars[bars.length - 1].close : null;
  const trending = ma5 !== null && ma10 !== null && ma20 !== null
    ? ma5 > ma10 && ma10 > ma20 ? 'Yükseliş eğilimi'
      : ma5 < ma10 && ma10 < ma20 ? 'Düşüş eğilimi' : 'Karışık / yatay'
    : 'Yeterli veri yok';
  const visibleNews = useMemo(() => news.filter(item =>
    filter === 'all' || item.market === filter,
  ).slice(0, 6), [news, filter]);

  const applySearch = () => {
    const normalized = search.trim().toUpperCase();
    if (/^[A-Z0-9.^-]{1,20}$/.test(normalized)) {
      setSelectedCode(normalized);
    }
  };

  const readAll = async () => {
    try {
      await newsApi.readAll();
      await loadNews();
    } catch {
      setNewsError(true);
    }
  };

  return (
    <div className="space-y-4" data-testid="etre-light-dashboard">
      <header className="etre-dashboard-head">
        <div>
          <h1 className="etre-dashboard-title">Ana Panel</h1>
          <p className="etre-dashboard-subtitle">Piyasalar, analizler ve haberler tek ekranda.</p>
        </div>
        <div className="etre-top-actions">
          <div className="hidden items-center gap-2 rounded-xl border border-border bg-card px-3 md:flex">
            <Search className="h-4 w-4 text-muted-text" />
            <input aria-label="Hisse kodu ara" placeholder="Hisse kodu ara (AAPL, THYAO.IS...)"
              value={search} onChange={event => setSearch(event.target.value)}
              onKeyDown={event => { if (event.key === 'Enter') applySearch(); }}
              className="w-44 bg-transparent py-2.5 text-xs text-foreground outline-none lg:w-56" />
            <button type="button" onClick={applySearch}
              aria-label="Hisseyi göster" className="text-primary"><ArrowRight className="h-4 w-4" /></button>
          </div>
          <Link className="etre-action-pill" to="/news" aria-label="Haber bildirimleri">
            <Bell className="h-4 w-4" />{unread > 0 ? <span className="etre-nav-badge">{unread > 99 ? '99+' : unread}</span> : null}
          </Link>
          <Link className="etre-action-pill" to="/settings">Ayarlar</Link>
        </div>
      </header>

      <div className="etre-market-filter !border-0 !p-0 !pb-3">
        {MARKETS.map(item => (
          <button type="button" key={item.code} onClick={() => setFilter(item.code)}
            className="etre-filter-button !text-xs" data-active={filter === item.code}>
            <span>{item.icon}</span> {item.label}
          </button>
        ))}
      </div>

      <section aria-label="Piyasa fiyat kartları" className="etre-markets">
        {STOCK_MARKETS.map(item => {
          const quote = quotes[item.code];
          return (
            <div key={item.code} className="etre-panel etre-market-card">
              <div className="etre-market-name">{MARKETS.find(m => m.code === item.market)?.icon} {item.label}</div>
              <div className="etre-market-value">{isValidQuote(quote) ? formatNumber(quote.current_price, language) : '—'}</div>
              <div className="flex flex-wrap items-center gap-2">
                <span className="etre-market-foot">{item.short} · Gösterge hisse</span>
                {isValidQuote(quote) && quote.change_percent !== null ? (
                  <span className={'etre-tag ' + (quote.change_percent >= 0 ? 'etre-tag-up' : 'etre-tag-down')}>
                    {formatPercent(quote.change_percent, language)}
                  </span>
                ) : <span className="etre-tag etre-tag-muted">Fiyat bekleniyor</span>}
              </div>
            </div>
          );
        })}
        <div className="etre-panel etre-market-card">
          <div className="etre-market-name"><span>₿</span> Kripto · BTC</div>
          <div className="etre-market-value">{coinRows.length > 0
            ? '$' + formatNumber(coinRows.find(coin => coin.id === 'bitcoin')?.current_price, language)
            : '—'}</div>
          <div className="flex flex-wrap items-center gap-2">
            <span className="etre-market-foot">CoinGecko · USD</span>
            {(() => {
              const btc = coinRows.find(coin => coin.id === 'bitcoin');
              return btc && btc.price_change_percentage_24h !== null ? (
                <span className={'etre-tag ' + (btc.price_change_percentage_24h >= 0 ? 'etre-tag-up' : 'etre-tag-down')}>
                  {formatPercent(btc.price_change_percentage_24h, language)}
                </span>
              ) : <span className="etre-tag etre-tag-muted">{cryptoUnavailable ? 'Kaynak erişilemiyor' : 'Veri bekleniyor'}</span>;
            })()}
          </div>
        </div>
      </section>

      <div className="etre-grid">
        <section className="etre-dashboard-column" aria-label="Takip listeleri">
          <div className="etre-panel overflow-hidden">
            <div className="etre-panel-head">
              <h2 className="etre-panel-heading">Takip Listem · Hisseler</h2>
              <Link to="/analysis" className="etre-inline-link">Analiz <ChevronRight className="inline h-3.5 w-3.5" /></Link>
            </div>
            {rows.length ? (
              <div className="overflow-x-auto">
                <table className="etre-table">
                  <thead><tr><th>Sembol</th><th>Fiyat</th><th>Değişim</th></tr></thead>
                  <tbody>
                    {rows.map(code => {
                      const quote = quotes[code];
                      return <tr key={code} data-selected={selectedCode === code}>
                        <td><button type="button" className="font-semibold"
                          onClick={() => setSelectedCode(code)}>{code}</button></td>
                        <td>{isValidQuote(quote) ? formatNumber(quote.current_price, language) : '—'}</td>
                        <td className={quote?.change_percent != null
                          ? quote.change_percent >= 0 ? 'text-success' : 'text-danger'
                          : 'text-muted-text'}>
                          {formatPercent(quote?.change_percent, language)}
                        </td>
                      </tr>;
                    })}
                  </tbody>
                </table>
              </div>
            ) : <div className="etre-panel-body text-xs leading-6 text-muted-text">
              {watchlistLoaded ? 'Henüz takip edilen hisse yok. Hisse Analizi bölümünden liste oluşturabilirsiniz.'
                : 'Takip listesi yükleniyor…'}
            </div>}
          </div>

          <div className="etre-panel overflow-hidden">
            <div className="etre-panel-head">
              <h2 className="etre-panel-heading">Kripto · Top 100</h2>
              <Link to="/data" className="etre-inline-link">Tümünü gör <ChevronRight className="inline h-3.5 w-3.5" /></Link>
            </div>
            {coinRows.length ? (
              <div className="overflow-x-auto">
                <table className="etre-table">
                  <thead><tr><th>Coin</th><th>USD</th><th>24s</th></tr></thead>
                  <tbody>
                    {coinRows.slice(0, 6).map(coin => (
                      <tr key={coin.id}>
                        <td className="font-semibold">{coin.symbol.toUpperCase()}</td>
                        <td>{formatNumber(coin.current_price, language)}</td>
                        <td className={coin.price_change_percentage_24h !== null
                          ? coin.price_change_percentage_24h >= 0 ? 'text-success' : 'text-danger'
                          : 'text-muted-text'}>{formatPercent(coin.price_change_percentage_24h, language)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : <p className="etre-panel-body text-xs text-muted-text">
              {cryptoUnavailable ? 'CoinGecko verisine erişilemedi.' : 'Kripto listesi yükleniyor…'}
            </p>}
          </div>
        </section>

        <section className="etre-dashboard-column" aria-label="Fiyat grafiği ve analiz">
          <div className="etre-panel overflow-hidden">
            <div className="etre-chart-toolbar">
              <div className="min-w-0">
                <div className="flex flex-wrap items-center gap-2">
                  <h2 className="text-lg font-bold tracking-tight">{selectedCode}</h2>
                  {isValidQuote(selectedQuote) && selectedQuote.change_percent !== null ? (
                    <span className={'etre-tag ' + (selectedQuote.change_percent >= 0 ? 'etre-tag-up' : 'etre-tag-down')}>
                      {formatPercent(selectedQuote.change_percent, language)}
                    </span>
                  ) : null}
                </div>
                <p className="mt-1 text-xs text-muted-text">
                  {isValidQuote(selectedQuote) ? formatNumber(selectedQuote.current_price, language) : 'Fiyat alınamadı'}
                  {' · '}{selectedQuote ? getStockDisplayName(selectedCode, selectedQuote.stock_name) : 'Günlük mum grafiği'}
                </p>
              </div>
              <div className="flex gap-1">
                {[30, 90, 180].map(value => (
                  <button key={value} type="button" className="etre-filter-button"
                    data-active={days === value} onClick={() => setDays(value)}>
                    {value}G
                  </button>
                ))}
              </div>
            </div>
            <div className="flex flex-wrap gap-4 px-4 pb-1 text-[11px] text-muted-text">
              <span><b className="text-[#2085f7]">●</b> MA5: {formatNumber(ma5, language)}</span>
              <span><b className="text-[#f5a623]">●</b> MA10: {formatNumber(ma10, language)}</span>
              <span><b className="text-[#9b69e8]">●</b> MA20: {formatNumber(ma20, language)}</span>
            </div>
            <div className="etre-chart-frame">
              {chartLoading ? <div className="etre-chart-placeholder">Grafik verisi yükleniyor…</div>
                : chartError ? <div className="etre-chart-placeholder">Bu hisse için geçmiş fiyat verisi alınamadı.</div>
                : <StockCandlestickChart bars={bars} language={language} />}
            </div>
            <div className="flex flex-wrap items-center justify-between gap-2 border-t border-border px-4 py-3">
              <span className="text-[11px] text-muted-text">Kaynak: ETRE hisse geçmişi API'si · Gösterim: günlük OHLC</span>
              <Link className="etre-inline-link" to="/analysis">Detaylı analiz <ArrowRight className="inline h-3.5 w-3.5" /></Link>
            </div>
          </div>

          <div className="grid gap-3 xl:grid-cols-2">
            <div className="etre-panel">
              <div className="etre-panel-head"><h2 className="etre-panel-heading"><BarChart3 className="mr-2 inline h-4 w-4 text-primary" />Teknik Görünüm</h2></div>
              <div className="etre-panel-body space-y-3">
                <div className="flex items-center justify-between">
                  <span className="text-xs text-muted-text">Ortalamalara göre eğilim</span>
                  <span className="text-xs font-semibold">{trending}</span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-xs text-muted-text">Son günlük kapanış</span>
                  <span className="text-xs font-semibold">{formatNumber(lastClose, language)}</span>
                </div>
                <div className="h-2 overflow-hidden rounded-full bg-muted">
                  <div className="h-full rounded-full bg-primary" style={{ width: ma5 && ma10 && ma20 ? '100%' : '0%' }} />
                </div>
                <p className="text-[11px] leading-5 text-muted-text">
                  Bu özet yalnızca MA5/MA10/MA20 sıralamasından hesaplanır. Daily'nin 100 puanlık AI veya alım-satım sinyali değildir.
                </p>
              </div>
            </div>
            <div className="etre-panel">
              <div className="etre-panel-head"><h2 className="etre-panel-heading"><Sparkles className="mr-2 inline h-4 w-4 text-primary" />ETRE AI Analizi</h2></div>
              <div className="etre-panel-body">
                <div className="etre-insight">
                  Güncel AI kararı oluşturmak için Hisse Analizi ekranında seçtiğiniz hisseyi analiz edin. Veri olmadan tavsiye üretilmez.
                </div>
                <button className="mt-3 inline-flex items-center gap-2 rounded-lg bg-primary px-3 py-2 text-xs font-semibold text-primary-foreground"
                  type="button" onClick={() => navigate('/analysis')}>
                  <Activity className="h-4 w-4" />Hisse Analizine Git <ArrowRight className="h-3.5 w-3.5" />
                </button>
              </div>
            </div>
          </div>
        </section>

        <aside className="etre-dashboard-column" aria-label="Son haberler">
          <div className="etre-panel overflow-hidden">
            <div className="etre-panel-head">
              <h2 className="etre-panel-heading"><Newspaper className="mr-1.5 inline h-4 w-4 text-primary" />Haberler</h2>
              {unread > 0 ? (
                <button type="button" onClick={() => void readAll()} className="etre-inline-link">
                  <CheckCheck className="mr-1 inline h-3.5 w-3.5" />Tümünü okundu
                </button>
              ) : <span className="text-xs text-muted-text">Güncel</span>}
            </div>
            <div className="etre-market-filter">
              {MARKETS.map(item => (
                <button type="button" key={item.code} className="etre-filter-button"
                  data-active={filter === item.code} onClick={() => setFilter(item.code)}>
                  {item.label}
                </button>
              ))}
            </div>
            <div className="px-4 pb-2">
              {newsError ? <p className="py-4 text-xs text-muted-text">Haber servisine ulaşılamadı.</p>
                : visibleNews.length === 0 ? <p className="py-4 text-xs text-muted-text">
                  Bu piyasada görüntülenecek haber bulunamadı.
                </p> : visibleNews.map(item => (
                  <article key={item.id} className="etre-news-item">
                    <span className={item.is_read ? 'etre-news-dot !bg-muted-foreground' : 'etre-news-dot'} />
                    <div className="min-w-0 flex-1">
                      <a href={item.url} target="_blank" rel="noopener noreferrer"
                        className="etre-news-title">{item.title}</a>
                      <p className="etre-news-caption">
                        {MARKETS.find(m => m.code === item.market)?.label} · {item.source}
                      </p>
                      <p className="etre-news-caption">
                        {item.ai_status === 'complete' ? 'Türkçe AI özeti hazır' : 'Türkçe çeviri bekleniyor'}
                        {' · '}{new Date(item.published_at).toLocaleDateString(language === 'tr' ? 'tr-TR' : 'en-US')}
                      </p>
                    </div>
                    {!item.is_read ? <span className="etre-tag etre-tag-muted">Yeni</span> : null}
                  </article>
                ))}
            </div>
            <div className="border-t border-border p-3">
              <Link to="/news" className="etre-action-pill !flex !w-full !justify-center">
                Tüm Haberleri Gör <ChevronRight className="h-4 w-4" />
              </Link>
            </div>
          </div>
          <div className="etre-panel etre-panel-body">
            <h3 className="text-sm font-bold">Kaynak ve kapsam</h3>
            <p className="mt-2 text-xs leading-6 text-muted-text">
              Hisse fiyatları ETRE veri sağlayıcılarından, kripto CoinGecko'dan, haberler ücretsiz RSS akışından gelir.
              Geciken veya erişilemeyen veriler için tahmini fiyat gösterilmez.
            </p>
            <Link to="/data" className="etre-inline-link mt-2 inline-flex items-center gap-1">
              Veri Merkezi <RefreshCcw className="h-3.5 w-3.5" />
            </Link>
          </div>
        </aside>
      </div>
    </div>
  );
};

export default DashboardPage;
