import type React from 'react';
import { useCallback, useEffect, useRef, useState } from 'react';
import { fiveMarketSampleApi } from '../../api/fiveMarketSample';
import { Badge, Card } from '../common';
import { useUiLanguage } from '../../contexts/UiLanguageContext';
import type { UiLanguage } from '../../i18n/uiText';
import {
  FOCUS_MARKETS,
  parseFiveMarketSampleReport,
  type FiveMarketSampleReport,
  type FocusMarket,
  type SampleStatus,
  type SampleQuality,
} from '../../utils/fiveMarketSampleReport';

const MAX_FILE_BYTES = 2_000_000;
const PAGE_SIZE = 20;

const MARKET_NAMES: Record<FocusMarket, Record<UiLanguage, string>> = {
  tr: { tr: 'Türkiye', en: 'Türkiye', zh: '土耳其' },
  us: { tr: 'ABD', en: 'USA', zh: '美国' },
  de: { tr: 'Almanya', en: 'Germany', zh: '德国' },
  hk: { tr: 'Hong Kong', en: 'Hong Kong', zh: '香港' },
};

const LABELS: Record<UiLanguage, {
  title: string; subtitle: string; description: string; import: string;
  reloadServer: string; checkingServer: string; noServerReport: string; savedServerReport: string;
  noReport: string; fileLarge: string; badFile: string;
  date: string; checked: string; analyzed: string; markets: string;
  market: string; marketStatus: string; checkedShort: string; status: string;
  code: string; currency: string; bars: string; session: string; score: string;
  target: string; remaining: string;
  attention: string; note: string; sampleNote: string; previous: string;
  next: string; page: string; missing: string;
}> = {
  tr: {
    title: 'Dört piyasa · 400 hisse hedefi',
    subtitle: 'Kaydedilmiş Yahoo günlük veri raporu · Salt okunur',
    description: 'Yalnızca daha önce oluşturulan JSON raporu görüntülenir. Dosya sunucuya gönderilmez; bu ekran fiyat çekmez, analiz başlatmaz veya emir vermez.',
    import: 'JSON raporu seç',
    reloadServer: 'Sunucu raporunu yenile',
    checkingServer: 'Sunucu raporu kontrol ediliyor…',
    noServerReport: 'Sunucuda doğrulanmış dört piyasa raporu yok veya yönetici erişimi kapalı. Yerel JSON raporu seçebilirsiniz.',
    savedServerReport: 'Sunucuda kayıtlı rapor (salt okunur)',
    noReport: 'Henüz rapor seçilmedi. GitHub Actions test çıktısından veya yerel kontrol komutundan oluşturulmuş dört piyasa JSON dosyasını açabilirsiniz. Kontrol yapılmadıysa başarı varsayılmaz.',
    fileLarge: 'Rapor dosyası en fazla 2 MB olabilir.',
    badFile: 'Rapor okunamadı veya içeriği geçersiz.',
    date: 'Rapor tarihi',
    checked: 'Kontrol edilen hisse',
    analyzed: 'Teknik kontrolü geçen',
    markets: 'Örnek kontrol yapılan piyasa',
    market: 'Piyasa',
    marketStatus: 'Örneklerin durumu',
    checkedShort: 'Geçen / kontrol edilen',
    status: 'Durum',
    code: 'Hisse kodu',
    currency: 'Para birimi',
    bars: 'Günlük veri',
    session: 'Son seans',
    score: 'Teknik puan',
    attention: 'Sorunlu hisse',
    note: 'Raporun biçimi ve sayaç tutarlılığı kontrol edildi; dosyanın gerçek Yahoo verisinden üretildiği kriptografik olarak kanıtlanamaz.',
    sampleNote: 'Başarılı örnekler tüm piyasanın, canlı fiyatların veya aracı kurum işlem izninin doğrulandığı anlamına gelmez. Bu puanlar yatırım tavsiyesi değildir.',
    previous: 'Önceki',
    next: 'Sonraki',
    page: 'Sayfa',
    target: 'Hedef', remaining: 'Hedefe kalan', missing: '—',
  },
  en: {
    title: 'Four markets · 400-stock target',
    subtitle: 'Saved Yahoo daily history report · Read-only',
    description: 'Displays an existing JSON report only. The file is never uploaded; this screen does not fetch prices, run analyses, or place orders.',
    import: 'Choose JSON report',
    reloadServer: 'Refresh server report',
    checkingServer: 'Checking server report…',
    noServerReport: 'No validated four-market report is configured on the server, or admin access is disabled. You can select a local JSON file.',
    savedServerReport: 'Saved server report (read-only)',
    noReport: 'No report selected. Open a four-market JSON file produced by GitHub Actions or the local validation command. No unperformed check is marked successful.',
    fileLarge: 'Report file must be no larger than 2 MB.',
    badFile: 'Report could not be read or validated.',
    date: 'Report date',
    checked: 'Symbols checked',
    analyzed: 'Technical samples passed',
    markets: 'Markets sampled',
    market: 'Market',
    marketStatus: 'Sample status',
    checkedShort: 'Passed / checked',
    status: 'Status',
    code: 'Ticker',
    currency: 'Currency',
    bars: 'Daily bars',
    session: 'Last session',
    score: 'Technical score',
    attention: 'Failed symbols',
    note: 'The file shape and counts are validated; no cryptographic proof that the JSON originated from Yahoo can be provided.',
    sampleNote: 'Passing samples do not prove full exchange coverage, live quotes or brokerage permissions. Scores are not investment advice.',
    previous: 'Previous',
    next: 'Next',
    page: 'Page',
    target: 'Target', remaining: 'Remaining', missing: '—',
  },
  zh: {
    title: '四个市场 · 400只股票目标',
    subtitle: '已保存的 Yahoo 日线报告 · 只读',
    description: '仅显示已生成的 JSON 报告。文件不会上传；此页面不抓取行情、不启动分析，也不下单。',
    import: '选择 JSON 报告',
    reloadServer: '刷新服务器报告',
    checkingServer: '正在检查服务器报告…',
    noServerReport: '服务器未配置经过验证的四市场报告，或管理员权限未开启。可以选择本地 JSON 文件。',
    savedServerReport: '已保存服务器报告（只读）',
    noReport: '尚未选择报告。请选择 GitHub Actions 或本地检查命令生成的四市场 JSON 文件。',
    fileLarge: '报告不得超过 2 MB。',
    badFile: '报告读取或验证失败。',
    date: '报告日期',
    checked: '已检查股票',
    analyzed: '通过技术检查',
    markets: '抽样市场',
    market: '市场',
    marketStatus: '样本状态',
    checkedShort: '通过 / 检查',
    status: '状态',
    code: '股票代码',
    currency: '货币',
    bars: '日线数',
    session: '最后交易日',
    score: '技术分数',
    attention: '失败的股票',
    note: '已校验文件结构和计数，但不能以密码学方式证明 JSON 来自 Yahoo。',
    sampleNote: '样本通过并不代表全市场数据、实时价格或券商交易权限已验证。技术评分不构成投资建议。',
    previous: '上一页',
    next: '下一页',
    page: '页',
    target: '目标', remaining: '距目标剩余', missing: '—',
  },
};

const QUALITY_LABELS: Record<UiLanguage, Record<SampleQuality, string>> = {
  tr: {
    samples_passed: 'Örnekler geçti',
    partial: 'Kısmi',
    samples_failed: 'Örnekler başarısız',
    not_requested: 'Kontrol edilmedi',
  },
  en: {
    samples_passed: 'Samples passed',
    partial: 'Partial',
    samples_failed: 'Samples failed',
    not_requested: 'Not requested',
  },
  zh: {
    samples_passed: '样本通过',
    partial: '部分通过',
    samples_failed: '样本失败',
    not_requested: '未检查',
  },
};

const STATUS_LABELS_TR: Record<SampleStatus, string> = {
  analyzed: 'Teknik kontrol geçti',
  unavailable: 'Kullanılamıyor',
  routing_mismatch: 'Piyasa eşleşmiyor',
  routing_error: 'Yönlendirme hatası',
  calendar_unavailable: 'Piyasa takvimi yok',
  fetch_error: 'Veri kaynağı hatası',
  no_data: 'Veri yok',
  invalid_data: 'Geçersiz fiyat',
  incomplete_or_future_data: 'Eksik / ileri tarihli veri',
  insufficient_history: 'Yetersiz geçmiş',
  stale_price: 'Güncel olmayan fiyat',
  currency_unverified: 'Para birimi doğrulanmadı',
  currency_mismatch: 'Para birimi uyuşmuyor',
  analysis_error: 'Teknik analiz hatası',
};

function summaryTile(label: string, value: number) {
  return (
    <div className="rounded-xl border border-border/70 bg-surface/60 px-4 py-3">
      <div className="text-xs text-secondary-text">{label}</div>
      <div className="mt-2 text-2xl font-semibold text-foreground">{value}</div>
    </div>
  );
}

/** A report viewer only: never fetches prices, persists symbols or runs trades. */
export const FiveMarketSamplePanel: React.FC = () => {
  const { language } = useUiLanguage();
  const t = LABELS[language];
  const [report, setReport] = useState<FiveMarketSampleReport | null>(null);
  const [selectedFile, setSelectedFile] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const [serverLoading, setServerLoading] = useState(false);
  const [serverMessage, setServerMessage] = useState('');
  const [page, setPage] = useState(0);
  const generation = useRef(0);
  const manuallySelected = useRef(false);

  const loadSavedReport = useCallback(async () => {
    if (manuallySelected.current) return;
    const request = ++generation.current;
    setServerLoading(true);
    setServerMessage('');
    try {
      const saved = await fiveMarketSampleApi.getSavedReport();
      if (request !== generation.current || manuallySelected.current) return;
      setReport(saved);
      setSelectedFile(t.savedServerReport);
      setPage(0);
      setError('');
    } catch {
      if (request !== generation.current || manuallySelected.current) return;
      setServerMessage(t.noServerReport);
    } finally {
      if (request === generation.current) setServerLoading(false);
    }
  }, [t]);

  useEffect(() => {
    void loadSavedReport();
    return () => { generation.current += 1; };
  }, [loadSavedReport]);

  const reloadSavedReport = () => {
    manuallySelected.current = false;
    generation.current += 1;
    setReport(null);
    setSelectedFile('');
    setError('');
    setPage(0);
    void loadSavedReport();
  };

  const handleFileChange = async (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.currentTarget.files?.[0];
    event.currentTarget.value = '';
    if (!file) return;
    manuallySelected.current = true;
    const request = ++generation.current;
    setServerLoading(false);
    setServerMessage('');
    setReport(null);
    setSelectedFile('');
    setPage(0);
    setError('');
    if (file.size > MAX_FILE_BYTES) {
      setError(t.fileLarge);
      return;
    }
    setLoading(true);
    try {
      const json: unknown = JSON.parse(await file.text());
      const parsed = parseFiveMarketSampleReport(json);
      if (request !== generation.current) return;
      setReport(parsed);
      setSelectedFile(file.name);
    } catch {
      if (request !== generation.current) return;
      setError(t.badFile);
    } finally {
      if (request === generation.current) setLoading(false);
    }
  };

  const rows = report?.results ?? [];
  const failed = report ? report.checked_symbols - report.analyzed_symbols : 0;
  const maxPage = Math.max(0, Math.ceil(rows.length / PAGE_SIZE) - 1);
  const visible = rows.slice(page * PAGE_SIZE, (page + 1) * PAGE_SIZE);

  return (
    <Card title={t.title} subtitle={t.subtitle} variant="bordered" padding="md">
      <div className="space-y-4">
        <p className="text-sm text-secondary-text">{t.description}</p>
        <div className="flex flex-wrap gap-2">
          <button
            type="button"
            disabled={serverLoading}
            onClick={reloadSavedReport}
            className="rounded-lg border border-border bg-surface px-3 py-2 text-sm text-foreground disabled:opacity-40"
          >{serverLoading ? t.checkingServer : t.reloadServer}</button>
        <label className="inline-flex cursor-pointer items-center rounded-lg border border-border bg-surface px-3 py-2 text-sm font-medium text-foreground">
          {t.import}
          <input
            className="sr-only"
            type="file"
            accept=".json,application/json"
            aria-label={t.import}
            onChange={(event) => { void handleFileChange(event); }}
          />
        </label>
        </div>
        {serverMessage ? <p role="status" className="text-sm text-muted-text">{serverMessage}</p> : null}
        {loading ? <p role="status" className="text-sm text-muted-text">…</p> : null}
        {error ? <p role="alert" className="text-sm text-danger">{error}</p> : null}
        {!report && !loading && !serverLoading && !error ? <p className="text-sm text-muted-text">{t.noReport}</p> : null}

        {report ? (
          <>
            <div className="text-xs text-muted-text">
              {selectedFile} · {t.date}: {report.as_of} · Yahoo Finance · {report.scope}
            </div>
            <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
              {summaryTile(t.checked, report.checked_symbols)}
              {summaryTile(t.analyzed, report.analyzed_symbols)}
              {summaryTile(t.markets, report.markets_checked)}
              {summaryTile(t.attention, failed)}
              {summaryTile(t.target, report.target_symbols_total)}
              {summaryTile(t.remaining, report.remaining_to_target)}
            </div>
            <p className="text-xs text-muted-text" role="note">{t.note}</p>
            <div className="overflow-x-auto">
              <table className="w-full min-w-[550px] text-left text-sm">
                <thead className="border-b border-border/60 text-xs text-muted-text">
                  <tr>
                    <th className="px-3 py-2 font-medium">{t.market}</th>
                    <th className="px-3 py-2 font-medium">{t.marketStatus}</th>
                    <th className="px-3 py-2 font-medium">{t.checkedShort}</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-border/40">
                  {FOCUS_MARKETS.map(market => {
                    const result = report.by_market[market];
                    const variant = result.sample_status === 'samples_passed' ? 'success'
                      : result.sample_status === 'not_requested' ? 'default' : 'warning';
                    return (
                      <tr key={market}>
                        <td className="px-3 py-2 font-medium text-foreground">{MARKET_NAMES[market][language]}</td>
                        <td className="px-3 py-2">
                          <Badge variant={variant}>{QUALITY_LABELS[language][result.sample_status]}</Badge>
                        </td>
                        <td className="px-3 py-2 text-secondary-text">
                          {result.analyzed_symbols} / {result.checked_symbols} · {t.target}: {result.target_symbols} · {t.remaining}: {result.remaining_to_target}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>

            <div className="overflow-x-auto">
              <table className="w-full min-w-[800px] text-left text-sm">
                <thead className="border-b border-border/60 text-xs text-muted-text">
                  <tr>
                    <th className="px-3 py-2 font-medium">{t.code}</th>
                    <th className="px-3 py-2 font-medium">{t.status}</th>
                    <th className="px-3 py-2 font-medium">{t.bars}</th>
                    <th className="px-3 py-2 font-medium">{t.session}</th>
                    <th className="px-3 py-2 font-medium">{t.currency}</th>
                    <th className="px-3 py-2 font-medium">{t.score}</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-border/40">
                  {visible.map(row => (
                    <tr key={row.code}>
                      <td className="px-3 py-2 font-mono text-foreground notranslate" translate="no">{row.code}</td>
                      <td className="px-3 py-2">
                        <Badge variant={row.status === 'analyzed' ? 'success' : 'warning'}>
                          {language === 'tr' ? STATUS_LABELS_TR[row.status] : row.status}
                        </Badge>
                      </td>
                      <td className="px-3 py-2 text-secondary-text">{row.bars ?? t.missing}</td>
                      <td className="px-3 py-2 text-secondary-text">{row.last_bar_date ?? t.missing}</td>
                      <td className="px-3 py-2 text-secondary-text">{row.currency_observed ?? t.missing}</td>
                      <td className="px-3 py-2 text-secondary-text">
                        {row.technical_score === undefined ? t.missing : row.technical_score + '/100'}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            {maxPage > 0 ? (
              <div className="flex items-center justify-end gap-3 text-sm">
                <button
                  type="button"
                  className="rounded-lg border border-border px-3 py-1 disabled:opacity-40"
                  disabled={page === 0}
                  onClick={() => setPage(v => Math.max(0, v - 1))}
                >{t.previous}</button>
                <span className="text-xs text-muted-text">{t.page} {page + 1}/{maxPage + 1}</span>
                <button
                  type="button"
                  className="rounded-lg border border-border px-3 py-1 disabled:opacity-40"
                  disabled={page >= maxPage}
                  onClick={() => setPage(v => Math.min(maxPage, v + 1))}
                >{t.next}</button>
              </div>
            ) : null}
            <p role="note" className="text-xs text-warning">{t.sampleNote}</p>
          </>
        ) : null}
      </div>
    </Card>
  );
};
