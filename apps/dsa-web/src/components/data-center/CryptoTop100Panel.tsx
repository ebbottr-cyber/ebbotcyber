import type React from 'react';
import { useCallback, useEffect, useMemo, useState } from 'react';
import { coinGeckoApi, type CoinGeckoRoster, type CoinGeckoTechnical } from '../../api/coinGecko';
import { useUiLanguage } from '../../contexts/UiLanguageContext';
import type { UiLanguage } from '../../i18n/uiText';
import { Card } from '../common';

const COPY: Record<UiLanguage, {
  title: string; subtitle: string; help: string; refresh: string; loading: string;
  error: string; search: string; rank: string; coin: string; price: string; cap: string;
  volume: string; change: string; analyze: string; analyzing: string; unavailable: string;
  last: string; stale: string; cached: string; score: string; signal: string;
  trend: string; barCount: string; note: string; noMatch: string;
}> = {
  tr: {
    title: 'Kripto · CoinGecko Top 100', subtitle: 'Piyasa değerine göre ilk 100 · USD · Salt okunur',
    help: 'Liste güncel CoinGecko sıralamasından gelir. Aynı sembolü kullanan coinler benzersiz CoinGecko kimlikleriyle ayrılır.',
    refresh: 'Listeyi yenile', loading: 'CoinGecko yükleniyor…',
    error: 'CoinGecko listesi alınamadı. İnternet bağlantısını ve API kotasını kontrol edin.',
    search: 'Coin adı, sembolü veya kimliği', rank: 'Sıra', coin: 'Coin', price: 'Fiyat (USD)',
    cap: 'Piyasa değeri', volume: '24s hacim (USD)', change: '24s %',
    analyze: 'Teknik analiz', analyzing: 'Analiz ediliyor…',
    unavailable: 'Teknik analiz alınamadı. Yeterli fiyat verisi olmayabilir veya CoinGecko kotası dolmuş olabilir.',
    last: 'Güncelleme', stale: 'Eski veri — kaynak erişilemiyor', cached: 'Önbellek',
    score: 'Puan', signal: 'Sinyal', trend: 'Trend', barCount: 'Tamamlanan gün',
    note: 'Araştırma amaçlıdır; yatırım tavsiyesi veya işlem emri değildir. Mevcut hisse stratejisinin eşikleri kriptoya kalibre edilmemiştir. Teknik analiz son 30 günlük OHLC ile ve kayan 24 saatlik hacim göstergesiyle yapılır.',
    noMatch: 'Eşleşen coin bulunamadı.',
  },
  en: {
    title: 'Crypto · CoinGecko Top 100', subtitle: 'Top 100 by market cap · USD · Read-only',
    help: 'Live CoinGecko rankings. Coins with identical tickers retain separate CoinGecko IDs.',
    refresh: 'Refresh list', loading: 'Loading CoinGecko…',
    error: 'Could not load CoinGecko. Check internet connection and API limits.',
    search: 'Coin name, symbol or ID', rank: 'Rank', coin: 'Coin', price: 'Price (USD)',
    cap: 'Market cap', volume: '24h volume (USD)', change: '24h %',
    analyze: 'Technical check', analyzing: 'Analyzing…',
    unavailable: 'Technical data unavailable. Not enough price history or CoinGecko API quota.',
    last: 'Updated', stale: 'Stale data — source unavailable', cached: 'Cached',
    score: 'Score', signal: 'Signal', trend: 'Trend', barCount: 'Completed days',
    note: 'Research only. Not an order or investment advice. Equity thresholds are uncalibrated for crypto. The technical check uses 30 days of OHLC and rolling 24h volume.',
    noMatch: 'No matching coins.',
  },
  zh: {
    title: '加密货币 · CoinGecko 前100', subtitle: '市值前100 · USD · 只读',
    help: '实时 CoinGecko 排名，相同代码使用不同 CoinGecko ID 区分。',
    refresh: '刷新列表', loading: '加载 CoinGecko…',
    error: 'CoinGecko 加载失败，请检查网络或额度。',
    search: '名称、代码或ID', rank: '排名', coin: '币种', price: '价格 (USD)',
    cap: '市值', volume: '24小时交易量', change: '24小时 %',
    analyze: '技术分析', analyzing: '分析中…',
    unavailable: '历史数据不足或 CoinGecko 请求额度不足。',
    last: '更新时间', stale: '旧数据 — 来源不可用', cached: '缓存',
    score: '得分', signal: '信号', trend: '趋势', barCount: '完整天数',
    note: '仅供研究，不构成交易建议。股票策略阈值未经加密货币校准。技术检查基于30天OHLC及滚动24小时成交量。',
    noMatch: '没有匹配币种。',
  },
};

const SIGNAL: Record<string, Record<UiLanguage, string>> = {
  strong_buy: { tr: 'Güçlü alım', en: 'Strong buy', zh: '强烈买入' },
  buy: { tr: 'Alım', en: 'Buy', zh: '买入' },
  hold: { tr: 'Tut', en: 'Hold', zh: '持有' },
  wait: { tr: 'Bekle', en: 'Wait', zh: '观望' },
  sell: { tr: 'Satım', en: 'Sell', zh: '卖出' },
  strong_sell: { tr: 'Güçlü satım', en: 'Strong sell', zh: '强烈卖出' },
};
const TREND: Record<string, Record<UiLanguage, string>> = {
  strong_bull: { tr: 'Güçlü yükseliş', en: 'Strong uptrend', zh: '强势多头' },
  bull: { tr: 'Yükseliş', en: 'Uptrend', zh: '多头' },
  weak_bull: { tr: 'Zayıf yükseliş', en: 'Weak uptrend', zh: '弱势多头' },
  consolidation: { tr: 'Yatay', en: 'Sideways', zh: '盘整' },
  weak_bear: { tr: 'Zayıf düşüş', en: 'Weak downtrend', zh: '弱势空头' },
  bear: { tr: 'Düşüş', en: 'Downtrend', zh: '空头' },
  strong_bear: { tr: 'Güçlü düşüş', en: 'Strong downtrend', zh: '强势空头' },
};

const formatted = (n: number | null, locale: string, compact = false): string =>
  n === null || !Number.isFinite(n) ? '—' : new Intl.NumberFormat(locale, {
    notation: compact ? 'compact' : 'standard',
    maximumFractionDigits: compact ? 2 : Math.abs(n) >= 1 ? 4 : 8,
  }).format(n);

export const CryptoTop100Panel: React.FC = () => {
  const { language } = useUiLanguage();
  const t = COPY[language];
  const locale = language === 'tr' ? 'tr-TR' : language === 'zh' ? 'zh-CN' : 'en-US';
  const [roster, setRoster] = useState<CoinGeckoRoster | null>(null);
  const [query, setQuery] = useState('');
  const [loading, setLoading] = useState(false);
  const [failed, setFailed] = useState(false);
  const [selected, setSelected] = useState<CoinGeckoTechnical | null>(null);
  const [selectedId, setSelectedId] = useState('');
  const [analyzing, setAnalyzing] = useState(false);
  const [analysisFailed, setAnalysisFailed] = useState(false);

  const refresh = useCallback(async (alive: () => boolean) => {
    setLoading(true); setFailed(false);
    try {
      const result = await coinGeckoApi.getTop100();
      if (alive()) setRoster(result);
    } catch {
      if (alive()) setFailed(true);
    } finally {
      if (alive()) setLoading(false);
    }
  }, []);

  useEffect(() => {
    let alive = true;
    void refresh(() => alive);
    return () => { alive = false; };
  }, [refresh]);

  const visible = useMemo(() => (roster?.coins ?? []).filter(coin =>
    (coin.name + ' ' + coin.symbol + ' ' + coin.id).toLocaleLowerCase().includes(query.toLocaleLowerCase()),
  ), [roster, query]);

  const analyze = async (id: string) => {
    setSelectedId(id); setSelected(null); setAnalysisFailed(false); setAnalyzing(true);
    try {
      setSelected(await coinGeckoApi.getTechnical(id));
    } catch {
      setAnalysisFailed(true);
    } finally {
      setAnalyzing(false);
    }
  };

  return (
    <Card title={t.title} subtitle={t.subtitle} variant="bordered" padding="md">
      <div className="space-y-4">
        <p className="text-sm text-secondary-text">{t.help}</p>
        <div className="flex flex-wrap gap-2">
          <button type="button" disabled={loading} onClick={() => void refresh(() => true)}
            className="rounded-lg border border-border bg-surface px-3 py-2 text-sm text-foreground disabled:opacity-50">
            {loading ? t.loading : t.refresh}
          </button>
          <input aria-label={t.search} placeholder={t.search} value={query} onChange={e => setQuery(e.target.value)}
            className="min-w-0 flex-1 rounded-lg border border-border bg-surface px-3 py-2 text-sm text-foreground sm:min-w-[220px]" />
        </div>
        {failed ? <p role="alert" className="text-sm text-danger">{t.error}</p> : null}
        {roster ? (
          <>
            <p className="text-xs text-muted-text">
              {roster.count}/{roster.target_count} · {t.last}: {new Date(roster.as_of).toLocaleString(locale)}
              {roster.cached ? ' · ' + t.cached : ''}{roster.stale ? ' · ' + t.stale : ''}
            </p>
            <div className="max-h-[450px] overflow-auto rounded-lg border border-border/70">
              <table className="w-full min-w-[710px] text-left text-sm">
                <thead className="sticky top-0 bg-card text-xs text-muted-text"><tr>
                  <th className="px-2 py-2">{t.rank}</th><th className="px-2 py-2">{t.coin}</th>
                  <th className="px-2 py-2">{t.price}</th><th className="px-2 py-2">{t.cap}</th>
                  <th className="px-2 py-2">{t.volume}</th><th className="px-2 py-2">{t.change}</th>
                  <th className="px-2 py-2">{t.analyze}</th>
                </tr></thead>
                <tbody className="divide-y divide-border/40">
                  {visible.map(coin => (
                    <tr key={coin.id}>
                      <td className="px-2 py-2">{coin.market_cap_rank ?? '—'}</td>
                      <td className="px-2 py-2"><strong>{coin.name}</strong>
                        <div className="font-mono text-xs text-muted-text">{coin.symbol} · {coin.id}</div></td>
                      <td className="px-2 py-2 font-mono">{formatted(coin.current_price, locale)}</td>
                      <td className="px-2 py-2">{formatted(coin.market_cap, locale, true)}</td>
                      <td className="px-2 py-2">{formatted(coin.total_volume, locale, true)}</td>
                      <td className="px-2 py-2">{coin.price_change_percentage_24h === null ? '—'
                        : formatted(coin.price_change_percentage_24h, locale) + '%'}</td>
                      <td className="px-2 py-2"><button type="button" disabled={analyzing}
                        onClick={() => void analyze(coin.id)}
                        className="rounded-lg border border-border px-2 py-1 text-xs hover:bg-hover disabled:opacity-50">
                        {analyzing && selectedId === coin.id ? t.analyzing : t.analyze}
                      </button></td>
                    </tr>
                  ))}
                </tbody>
              </table>
              {visible.length === 0 ? <p className="p-3 text-sm text-muted-text">{t.noMatch}</p> : null}
            </div>
          </>
        ) : null}
        {analysisFailed ? <p role="alert" className="text-sm text-danger">{t.unavailable}</p> : null}
        {selected ? (
          <section className="rounded-xl border border-border/70 bg-surface/60 p-4">
            <h3 className="font-semibold">{selected.coin.name} ({selected.coin.symbol}) · {selected.last_completed_day}</h3>
            <div className="mt-3 grid grid-cols-2 gap-2 text-sm md:grid-cols-4">
              <span>{t.score}: <strong>{selected.score}/100</strong></span>
              <span>{t.signal}: <strong>{SIGNAL[selected.signal]?.[language] ?? selected.signal}</strong></span>
              <span>{t.trend}: <strong>{TREND[selected.trend]?.[language] ?? selected.trend}</strong></span>
              <span>RSI 12: <strong>{formatted(selected.rsi_12, locale)}</strong></span>
              <span>MA5: <strong>{formatted(selected.ma5, locale)}</strong></span>
              <span>MA10: <strong>{formatted(selected.ma10, locale)}</strong></span>
              <span>MA20: <strong>{formatted(selected.ma20, locale)}</strong></span>
              <span>{t.barCount}: <strong>{selected.daily_bars}</strong></span>
            </div>
            <p className="mt-2 text-xs text-muted-text">MACD: {selected.macd_status}</p>
          </section>
        ) : null}
        <p className="text-xs leading-relaxed text-muted-text">{t.note}</p>
      </div>
    </Card>
  );
};
