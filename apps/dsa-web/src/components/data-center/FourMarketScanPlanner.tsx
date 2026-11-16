import type React from 'react';
import { useMemo, useState } from 'react';
import { Download } from 'lucide-react';
import { fourMarketUniverseApi } from '../../api/fourMarketUniverse';
import { useUiLanguage } from '../../contexts/UiLanguageContext';
import type { UiLanguage } from '../../i18n/uiText';
import { Card } from '../common';
import {
  FOUR_ACTIVE_MARKETS,
  STOCKS_PER_MARKET,
  TOTAL_STOCK_TARGET,
  buildFourMarketScanPlan,
  replaceTurkeyRosterCodes,
  type FourMarket,
} from '../../utils/fourMarketScanPlan';

const MARKET_LABELS: Record<FourMarket, Record<UiLanguage, string>> = {
  tr: { tr: 'Türkiye', en: 'Türkiye', zh: '土耳其' },
  us: { tr: 'ABD', en: 'USA', zh: '美国' },
  de: { tr: 'Almanya', en: 'Germany', zh: '德国' },
  hk: { tr: 'Hong Kong', en: 'Hong Kong', zh: '香港' },
};

const TEXT: Record<UiLanguage, {
  title: string; subtitle: string; description: string; placeholder: string;
  textarea: string; selected: string; remaining: string;
  invalid: string; ready: string; notReady: string; download: string;
  command: string; note: string; incomplete: string;
  loadTurkey: string; loadingTurkey: string; turkeyLoaded: string; turkeyUnavailable: string;
}> = {
  tr: {
    title: 'Dört piyasa · 400 hisse listesi hazırla',
    subtitle: 'Her piyasadan 100 hisse · Kodsuz tahmin yok · Salt okunur',
    description: 'Doğrulanmış hisse kodlarını satır, virgül veya boşlukla ayırarak yapıştırın. Bu form hiçbir fiyat verisi çekmez ve işlem yapmaz. Şirketlerin borsada gerçekten listelendiği ayrıca doğrulanmalıdır.',
    placeholder: 'THYAO.IS\nAAPL\nSAP.DE\nHK00700',
    textarea: 'Hisse kodları',
    selected: 'Girilen geçerli kod',
    remaining: 'Hedefe kalan',
    invalid: 'Liste sorunları',
    ready: 'Dört piyasada da 100 kod hazır. Bu, 400 hissenin veri analizinden geçtiği anlamına gelmez.',
    notReady: 'Tam liste için dört piyasanın her birinde 100 farklı, geçerli hisse kodu gerekli.',
    download: '400 kodluk TXT listesini indir',
    command: 'Windows PowerShell kontrol komutu',
    note: 'Dosyayı bilgisayarınızın İndirilenler/Downloads klasöründen çalıştırın. Tarama komutu isteğe bağlıdır; rapor başarıya ulaşmadan hiçbir hisse sağlıklı sayılmaz. Sembol biçimi hisse kotasyonu veya aracı kurum izni kanıtı değildir.',
    incomplete: 'Hatalar düzeltilmeden liste indirilemez. Japonya, Çin, Güney Kore ve Tayvan kodları desteklenmez.',
    loadTurkey: 'Kaynaklı BIST100 listesini ekle', loadingTurkey: 'BIST100 listesi kontrol ediliyor…',
    turkeyLoaded: 'Kaynaklı BIST100 listesi eklendi. Fiyat/veri kontrolü henüz yapılmadı.',
    turkeyUnavailable: 'BIST100 listesi alınamadı. Kaynak dönemi dolmuş veya sunucuya ulaşılamıyor.',
  },
  en: {
    title: 'Four markets · Prepare 400-stock list',
    subtitle: '100 shares per market · Read-only · No fabricated tickers',
    description: 'Paste verified equity codes separated by lines, commas or spaces. No prices are fetched and no orders placed. Listing status must be verified separately.',
    placeholder: 'THYAO.IS\nAAPL\nSAP.DE\nHK00700',
    textarea: 'Equity symbols',
    selected: 'Valid symbols entered',
    remaining: 'Remaining to target',
    invalid: 'List issues',
    ready: 'All four blocks have 100 tickers. This does not prove data verification for 400 equities.',
    notReady: 'A complete list requires 100 distinct valid codes for each of the four markets.',
    download: 'Download 400-symbol TXT list',
    command: 'Windows PowerShell check command',
    note: 'Use the downloaded file from your Downloads folder. The scan command is optional and never places orders. Syntactic validity does not prove listing or broker permissions.',
    incomplete: 'Correct errors before downloading. Japan, China, South Korea and Taiwan are excluded.',
    loadTurkey: 'Add sourced BIST100 roster', loadingTurkey: 'Checking BIST100 roster…',
    turkeyLoaded: 'Source-dated BIST100 roster loaded; price data has not been validated.',
    turkeyUnavailable: 'Cannot load BIST100; source period expired or server unavailable.',
  },
  zh: {
    title: '四个市场 · 准备400只股票',
    subtitle: '每市场100只股票 · 只读 · 不生成虚构代码',
    description: '请输入已验证的股票代码，使用换行、逗号或空格分隔。不抓取行情或下单。上市状态需要另行核实。',
    placeholder: 'THYAO.IS\nAAPL\nSAP.DE\nHK00700',
    textarea: '股票代码',
    selected: '有效代码数',
    remaining: '距目标剩余',
    invalid: '列表错误',
    ready: '四个市场均达到100个代码。并不代表400只股票的数据均已验证。',
    notReady: '完整列表要求四个市场各100个不同的有效股票代码。',
    download: '下载400代码TXT列表',
    command: 'Windows PowerShell 检查命令',
    note: '从下载文件夹使用该文件。运行验证为可选，不会下单。格式正确不代表已上市或有券商交易权限。',
    incomplete: '请修复错误再下载。日本、中国、韩国和台湾不在支持范围内。',
    loadTurkey: '加入有来源的BIST100名单', loadingTurkey: '正在检查BIST100名单…',
    turkeyLoaded: '已加入注明来源日期的BIST100名单；价格数据未验证。',
    turkeyUnavailable: '无法获取BIST100；来源已过期或服务器不可用。',
  },
};

// Internal Python module retains its older filename for backward-compatible imports;
// its active market scope and report identity enforce exactly TR/US/DE/HK.
const WINDOWS_COMMAND =
  '& ".\\.venv\\Scripts\\python.exe" -m src.services.five_market_sample_validation ' +
  '--symbols-file "$env:USERPROFILE\\Downloads\\etre-400-tickers.txt" ' +
  '--output "$env:TEMP\\etre-four-market-400.json"';

export const FourMarketScanPlanner: React.FC = () => {
  const { language } = useUiLanguage();
  const t = TEXT[language];
  const [codesText, setCodesText] = useState('');
  const [loadingTurkey, setLoadingTurkey] = useState(false);
  const [turkeyMessage, setTurkeyMessage] = useState('');
  const plan = useMemo(() => buildFourMarketScanPlan(codesText), [codesText]);

  const loadTurkey = async () => {
    setLoadingTurkey(true);
    setTurkeyMessage('');
    try {
      const roster = await fourMarketUniverseApi.getTurkeyBist100();
      setCodesText(current => replaceTurkeyRosterCodes(current, roster.symbols));
      setTurkeyMessage(t.turkeyLoaded + ' · ' + roster.effective_from + ' – ' + roster.effective_to);
    } catch {
      setTurkeyMessage(t.turkeyUnavailable);
    } finally {
      setLoadingTurkey(false);
    }
  };

  const downloadCodes = () => {
    if (!plan.readyForFullScan) return;
    const blob = new Blob([plan.codes.join('\n') + '\n'], {
      type: 'text/plain;charset=utf-8',
    });
    const href = URL.createObjectURL(blob);
    const anchor = document.createElement('a');
    anchor.href = href;
    anchor.download = 'etre-400-tickers.txt';
    document.body.appendChild(anchor);
    anchor.click();
    anchor.remove();
    window.setTimeout(() => URL.revokeObjectURL(href), 1000);
  };

  return (
    <Card title={t.title} subtitle={t.subtitle} variant="bordered" padding="md">
      <div className="space-y-4">
        <p className="text-sm text-secondary-text">{t.description}</p>
        <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
          {FOUR_ACTIVE_MARKETS.map(market => (
            <div key={market} className="rounded-xl border border-border/70 bg-surface/60 p-3">
              <div className="font-semibold text-foreground">{MARKET_LABELS[market][language]}</div>
              <div className="mt-2 text-lg font-semibold text-foreground">
                {plan.counts[market]} / {STOCKS_PER_MARKET}
              </div>
              <div className="text-xs text-muted-text">{t.remaining}: {plan.remaining[market]}</div>
            </div>
          ))}
        </div>
        <button
          type="button"
          disabled={loadingTurkey}
          onClick={() => { void loadTurkey(); }}
          className="rounded-lg border border-border bg-elevated px-3 py-2 text-sm text-foreground disabled:opacity-40"
        >
          {loadingTurkey ? t.loadingTurkey : t.loadTurkey}
        </button>
        {turkeyMessage ? <p role="status" className="text-xs text-muted-text">{turkeyMessage}</p> : null}
        <label className="block text-sm font-medium text-foreground" htmlFor="etre-four-market-codes">
          {t.textarea}
        </label>
        <textarea
          id="etre-four-market-codes"
          aria-label={t.textarea}
          className="min-h-28 w-full rounded-xl border border-border bg-surface p-3 font-mono text-xs text-foreground outline-none focus:ring-2 focus:ring-primary"
          rows={5}
          maxLength={20000}
          spellCheck={false}
          placeholder={t.placeholder}
          value={codesText}
          onChange={event => setCodesText(event.target.value)}
        />
        <p className="text-xs text-muted-text" role="status">
          {t.selected}: {plan.total} / {TOTAL_STOCK_TARGET} · {t.remaining}: {TOTAL_STOCK_TARGET - Math.min(plan.total, TOTAL_STOCK_TARGET)}
        </p>
        {plan.errors.length > 0 ? (
          <div role="alert" className="text-sm text-danger">
            <div className="font-semibold">{t.invalid}</div>
            <ul className="ml-5 list-disc">
              {plan.errors.slice(0, 5).map((item, index) => <li key={index}>{item}</li>)}
            </ul>
            {plan.errors.length > 5 ? <span>+{plan.errors.length - 5}</span> : null}
            <div className="mt-1 text-xs">{t.incomplete}</div>
          </div>
        ) : null}
        <p className="text-sm text-secondary-text">
          {plan.readyForFullScan ? t.ready : t.notReady}
        </p>
        <button
          type="button"
          disabled={!plan.readyForFullScan}
          onClick={downloadCodes}
          className="inline-flex items-center gap-2 rounded-lg border border-border bg-elevated px-3 py-2 text-sm font-medium text-foreground disabled:cursor-not-allowed disabled:opacity-40"
        >
          <Download className="h-4 w-4" /> {t.download}
        </button>
        {plan.readyForFullScan ? (
          <div>
            <div className="mb-2 text-sm font-medium text-foreground">{t.command}</div>
            <pre className="overflow-x-auto rounded-lg border border-border bg-surface p-3 text-xs text-secondary-text">
              <code>{WINDOWS_COMMAND}</code>
            </pre>
          </div>
        ) : null}
        <p role="note" className="text-xs text-muted-text">{t.note}</p>
      </div>
    </Card>
  );
};
