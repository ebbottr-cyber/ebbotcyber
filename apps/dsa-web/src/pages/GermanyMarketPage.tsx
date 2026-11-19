import { useCallback, useEffect, useRef, useState } from 'react';
import type React from 'react';
import { AlertTriangle, Database, Search, ShieldCheck } from 'lucide-react';
import { xetraApi, type XetraInventory, type XetraQuoteReport } from '../api/xetra';
import { useUiLanguage } from '../contexts/UiLanguageContext';

const copy = {
  tr: {
    title: 'Almanya (Xetra)',
    subtitle: 'Resmî Xetra hisse adayları ve manuel, gecikmeli fiyat kontrolü',
    inventory: 'Hisse envanteri',
    sourceDate: 'Kaynak tarihi',
    status: 'Araştırma modu · Alım-satım kapalı',
    explain: 'Bu liste işlem onayı değildir. Fiyat kontrolü yalnızca isteğiniz üzerine çalışır; ISIN eşleşmesi ve Türkiye broker erişimi doğrulanmamıştır.',
    search: 'Sembol ara (örn. SAP)',
    searchButton: 'Ara',
    loading: 'Xetra listesi yükleniyor…',
    unavailable: 'Xetra envanteri yüklenemedi. Fiyatlar gösterilmiyor.',
    empty: 'Eşleşen hisse bulunamadı.',
    add: 'Seç',
    remove: 'Kaldır',
    selected: 'Manuel fiyat kontrolü için seçilenler (en fazla 5)',
    check: 'Fiyatları kontrol et',
    checking: 'Fiyatlar denetleniyor…',
    checkOff: 'Manuel sorgulama sunucuda kapalı. Yönetici oturumu ve EBBOT_XETRA_QUOTES_UI_ENABLED=true gerekir.',
    blocked: 'Fiyat sağlayıcısı yanıtı doğrulanamadı veya sorgu kullanılamıyor.',
    matched: 'Gecikmeli fiyat metaverisi eşleşti',
    unknown: 'Doğrulanmış fiyat yok',
    price: 'Fiyat (EUR)',
    time: 'Fiyatın tarihi',
    source: 'Veri: Yahoo Finance / Xetra. Gerçek zamanlı, işlem yapılabilir kotasyon değildir.',
    delayed: 'Gecikmeli olabilir',
    stale: 'Kaynak listesi eski veya ileri tarihli; güncel ve doğru tarihli liste gereklidir.',
    unknownError: 'Fiyat kontrolü başarısız; doğrulanmamış fiyat gösterilmiyor.',
    refresh: 'Listeyi yenile',
    footer: 'Sinyal, portföy emri veya sanal alım-satım oluşturulmaz.',
  },
  en: {
    title: 'Germany (Xetra)',
    subtitle: 'Official Xetra share candidates and manual delayed quote checks',
    inventory: 'Share inventory',
    sourceDate: 'Source date',
    status: 'Research only · Trading disabled',
    explain: 'These are candidates, not trade approval. Quotes are requested only on click. ISIN identity and local broker access are not verified.',
    search: 'Find a ticker (e.g. SAP)',
    searchButton: 'Search',
    loading: 'Loading Xetra inventory…',
    unavailable: 'Xetra inventory unavailable. No prices shown.',
    empty: 'No matching shares.',
    add: 'Select',
    remove: 'Remove',
    selected: 'Selected for manual price checks (max 5)',
    check: 'Check prices',
    checking: 'Checking quote metadata…',
    checkOff: 'Manual requests disabled on server. Requires admin auth and EBBOT_XETRA_QUOTES_UI_ENABLED=true.',
    blocked: 'The provider quote cannot be validated or is unavailable.',
    matched: 'Delayed quote metadata matched',
    unknown: 'No verified quote',
    price: 'Price (EUR)',
    time: 'Quote timestamp',
    source: 'Source: Yahoo Finance / Xetra. Not a real-time or executable quote.',
    delayed: 'May be delayed',
    stale: 'Source inventory is stale or future-dated; a valid dated snapshot is required.',
    unknownError: 'Quote validation failed; no unverified price shown.',
    refresh: 'Reload list',
    footer: 'No trade signals, portfolio orders or paper fills.',
  },
  zh: {
    title: '德国（Xetra）',
    subtitle: 'Xetra 官方股票候选清单与手动延时价格核验',
    inventory: '股票清单',
    sourceDate: '来源日期',
    status: '仅研究 · 交易已禁用',
    explain: '候选股票不代表交易许可。价格仅在点击后请求；未核验 ISIN 对应关系或券商权限。',
    search: '搜索代码（例如 SAP）',
    searchButton: '搜索',
    loading: '正在加载股票清单…',
    unavailable: '无法加载清单，不显示价格。',
    empty: '未找到匹配股票。',
    add: '选择',
    remove: '移除',
    selected: '手动核验的股票（最多 5 只）',
    check: '核验价格',
    checking: '正在核验价格…',
    checkOff: '服务器未开启手动查询。需管理员登录及 EBBOT_XETRA_QUOTES_UI_ENABLED=true。',
    blocked: '供应商价格无法核验或不可用。',
    matched: '延时价格元数据匹配',
    unknown: '无已核验价格',
    price: '价格（欧元）',
    time: '报价时间',
    source: '来源：Yahoo Finance / Xetra。非实时或可成交报价。',
    delayed: '可能延迟',
    stale: '来源清单已过期或日期在未来，需要有效日期的数据。',
    unknownError: '价格核验失败，不显示未经核验的价格。',
    refresh: '刷新清单',
    footer: '不生成交易信号、真实订单或模拟成交。',
  },
} as const;

const initialSelected = ['SAP.DE', 'SIE.DE'];

const formatDate = (value: string | undefined) => {
  if (!value) return '—';
  const stamp = Date.parse(value);
  return Number.isFinite(stamp) ? new Date(stamp).toLocaleString('tr-TR') : '—';
};

const GermanyMarketPage: React.FC = () => {
  const { language } = useUiLanguage();
  const t = copy[language] ?? copy.tr;
  const [inventory, setInventory] = useState<XetraInventory | null>(null);
  const [search, setSearch] = useState('');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);
  const [selected, setSelected] = useState<string[]>(initialSelected);
  const [report, setReport] = useState<XetraQuoteReport | null>(null);
  const [quoteBusy, setQuoteBusy] = useState(false);
  const [quoteError, setQuoteError] = useState(false);
  const generation = useRef(0);

  useEffect(() => {
    document.title = t.title + ' - EBBot';
  }, [t.title]);

  const load = useCallback(async (term: string) => {
    const id = ++generation.current;
    setLoading(true);
    setError(false);
    setReport(null);
    setQuoteError(false);
    try {
      const data = await xetraApi.getInventory(term);
      if (id === generation.current) setInventory(data);
    } catch {
      if (id === generation.current) {
        setInventory(null);
        setError(true);
      }
    } finally {
      if (id === generation.current) setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load('');
    return () => { generation.current += 1; };
  }, [load]);

  const choose = (symbol: string) => {
    setSelected((items) => items.includes(symbol) || items.length >= 5 ? items : [...items, symbol]);
    setReport(null);
    setQuoteError(false);
  };

  const remove = (symbol: string) => {
    setSelected((items) => items.filter((item) => item !== symbol));
    setReport(null);
    setQuoteError(false);
  };

  const check = async () => {
    if (!inventory?.manualQuoteCheckEnabled || !selected.length || quoteBusy) return;
    setQuoteBusy(true);
    setQuoteError(false);
    setReport(null);
    try {
      const next = await xetraApi.checkQuotes(selected);
      setReport(next);
    } catch {
      setReport(null);
      setQuoteError(true);
    } finally {
      setQuoteBusy(false);
    }
  };

  return (
    <div className="mx-auto max-w-6xl space-y-5 px-2 pb-20 pt-3 sm:px-5">
      <header className="rounded-2xl border border-[#dce8f7] bg-white p-5 shadow-sm">
        <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
          <h1 className="text-2xl font-bold text-[#19395e]">{t.title}</h1>
          <span className="rounded-full bg-[#edf5ff] px-3 py-1 text-xs font-semibold text-[#2366ae]">{t.status}</span>
        </div>
        <p className="text-sm text-[#617a9b]">{t.subtitle}</p>
        <p className="mt-3 text-xs leading-5 text-[#6c829e]">{t.explain}</p>
      </header>

      {error ? <div role="alert" className="rounded-xl border border-red-200 bg-white p-4 text-sm text-red-700">{t.unavailable}</div> : null}

      <section className="rounded-2xl border border-[#dce8f7] bg-white p-5 shadow-sm">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <h2 className="flex items-center gap-2 text-base font-bold text-[#19395e]">
            <Database className="h-5 w-5 text-blue-600" />{t.inventory}
          </h2>
          <button type="button" onClick={() => void load(search)} className="text-sm font-semibold text-[#2875ce]">{t.refresh}</button>
        </div>
        {loading ? <p className="mt-4 text-sm text-[#617a9b]">{t.loading}</p> : null}
        {inventory ? (
          <>
            <div className="mt-4 grid gap-3 sm:grid-cols-2">
              <div className="rounded-xl bg-[#f4f8fe] p-4">
                <div className="text-xs text-[#617a9b]">{t.inventory}</div>
                <div className="text-2xl font-bold text-[#19395e]">{inventory.candidateCount.toLocaleString('tr-TR')}</div>
              </div>
              <div className="rounded-xl bg-[#f4f8fe] p-4">
                <div className="text-xs text-[#617a9b]">{t.sourceDate}</div>
                <div className="text-lg font-bold text-[#19395e]">{inventory.sourceAsOfDate}</div>
              </div>
            </div>
            {inventory.sourceStale ? <p role="status" className="mt-3 flex items-center gap-2 text-xs text-amber-700"><AlertTriangle className="h-4 w-4" />{t.stale}</p> : null}
            <form className="mt-4 flex gap-2" onSubmit={(event) => { event.preventDefault(); void load(search); }}>
              <input
                aria-label={t.search}
                value={search}
                onChange={(event) => setSearch(event.target.value.toUpperCase())}
                maxLength={30}
                placeholder={t.search}
                className="min-w-0 flex-1 rounded-lg border border-[#d6e2f0] px-3 py-2 text-sm text-[#19395e]"
              />
              <button type="submit" className="inline-flex items-center gap-2 rounded-lg bg-[#286fc4] px-3 py-2 text-sm font-semibold text-white">
                <Search className="h-4 w-4" />{t.searchButton}
              </button>
            </form>
            {!loading ? (
              <div className="mt-3 max-h-72 overflow-y-auto rounded-xl border border-[#e5edf7]">
                {inventory.items.length ? inventory.items.map((item) => (
                  <div key={item.symbol} className="flex items-center justify-between gap-2 border-b border-[#e5edf7] px-3 py-2 text-sm last:border-0">
                    <div className="min-w-0">
                      <div className="font-semibold text-[#1c416b]">{item.symbol}</div>
                      <div className="text-xs text-[#7a8ca6]">{item.isin}</div>
                    </div>
                    <button
                      type="button"
                      disabled={selected.includes(item.symbol) || selected.length >= 5}
                      onClick={() => choose(item.symbol)}
                      className="rounded-lg border border-[#b8d3f4] px-3 py-1.5 text-xs font-semibold text-[#286fc4] disabled:opacity-40"
                    >{t.add}</button>
                  </div>
                )) : <p className="p-3 text-sm text-[#6c829e]">{t.empty}</p>}
              </div>
            ) : null}
          </>
        ) : null}
      </section>

      <section className="rounded-2xl border border-[#dce8f7] bg-white p-5 shadow-sm">
        <h2 className="flex items-center gap-2 text-base font-bold text-[#19395e]"><ShieldCheck className="h-5 w-5 text-blue-600" />{t.selected}</h2>
        <div className="mt-4 flex flex-wrap gap-2">
          {selected.map((symbol) => (
            <button key={symbol} type="button" onClick={() => remove(symbol)} aria-label={t.remove + ' ' + symbol}
              className="rounded-full bg-[#edf5ff] px-3 py-1.5 text-xs font-semibold text-[#235e9b]">
              {symbol} ×
            </button>
          ))}
        </div>
        {inventory && !inventory.manualQuoteCheckEnabled && !inventory.sourceStale ? <p className="mt-3 text-xs text-amber-700">{t.checkOff}</p> : null}
        <button type="button" onClick={() => void check()}
          disabled={!inventory?.manualQuoteCheckEnabled || !selected.length || quoteBusy}
          className="mt-4 rounded-lg bg-[#286fc4] px-4 py-2 text-sm font-semibold text-white disabled:cursor-not-allowed disabled:opacity-45"
        >{quoteBusy ? t.checking : t.check}</button>
        {quoteError ? <div role="alert" className="mt-4 text-sm text-red-700">{t.unknownError}</div> : null}
        {report ? (
          <div className="mt-4 space-y-3" role="region" aria-label={t.check}>
            {report.checks.map((item) => {
              const valid = item.status === 'QUOTE_METADATA_MATCH'
                && item.quoteMetadataMatched
                && item.providerCurrency === 'EUR'
                && item.providerExchange === 'XETRA'
                && typeof item.regularMarketPriceEur === 'number'
                && Number.isFinite(item.regularMarketPriceEur) && item.regularMarketPriceEur > 0;
              return (
                <div key={item.symbol} className="rounded-xl border border-[#e1e9f5] p-3">
                  <div className="flex flex-wrap justify-between gap-2">
                    <strong className="text-[#19395e]">{item.symbol}</strong>
                    <span className={'text-xs font-semibold ' + (valid ? 'text-blue-700' : 'text-amber-700')}>{valid ? t.matched : t.unknown}</span>
                  </div>
                  <p className="mt-2 text-xl font-bold text-[#19395e]">{t.price}: {valid ? item.regularMarketPriceEur!.toLocaleString('tr-TR', { style: 'currency', currency: 'EUR' }) : '—'}</p>
                  <p className="mt-1 text-xs text-[#6c829e]">{t.time}: {valid ? formatDate(item.regularMarketTimeUtc) : '—'}</p>
                  <p className="mt-1 text-xs text-[#8b9cb4]">{valid ? t.delayed : t.blocked}</p>
                </div>
              );
            })}
            <p className="text-xs leading-5 text-[#6c829e]">{t.source}</p>
          </div>
        ) : null}
        <p className="mt-4 text-xs text-[#8295ae]">{t.footer}</p>
      </section>
    </div>
  );
};

export default GermanyMarketPage;
