import type React from 'react';
import { useCallback, useEffect, useRef, useState } from 'react';
import { fourMarketBatchProgressApi } from '../../api/fourMarketBatchProgress';
import { Badge, Card } from '../common';
import { useUiLanguage } from '../../contexts/UiLanguageContext';
import type { UiLanguage } from '../../i18n/uiText';
import { FOUR_ACTIVE_MARKETS, type FourMarket } from '../../utils/fourMarketScanPlan';
import {
  parseFourMarketBatchProgress,
  type FourMarketBatchProgress,
} from '../../utils/fourMarketBatchProgress';

const FILE_BYTES_LIMIT = 2_000_000;
const MAX_DISPLAY_ROWS = 12;

const MARKETS: Record<FourMarket, Record<UiLanguage, string>> = {
  tr: { tr: 'Türkiye', en: 'Türkiye', zh: '土耳其' },
  us: { tr: 'ABD', en: 'USA', zh: '美国' },
  de: { tr: 'Almanya', en: 'Germany', zh: '德国' },
  hk: { tr: 'Hong Kong', en: 'Hong Kong', zh: '香港' },
};

const LABELS: Record<UiLanguage, {
  title: string; subtitle: string; intro: string; select: string; empty: string;
  malformed: string; oversized: string; checked: string; analyzed: string;
  failed: string; pending: string; invalidBatches: string;
  analyzedWithin: string; nextBatch: string; noBatch: string; ready: string;
  inspect: string; retry: string; run: string; invalid: string;
  failedRows: string; errorType: string; batch: string; status: string;
  date: string; source: string; totalBatches: string; omitted: string;
  footer: string; market: string;
  refreshServer: string; loadingServer: string; noServer: string; savedServer: string;
}> = {
  tr: {
    title: '400 hisse · Tarama ilerlemesi',
    subtitle: 'Önceden oluşturulmuş JSON · Salt okunur',
    intro: 'Yönetici erişimi açıksa sunucuda kayıtlı --status raporu otomatik gösterilir. İsterseniz yerel JSON da seçebilirsiniz; yerel dosya yüklenmez, tarama veya emir başlatılmaz.',
    select: 'İlerleme JSON dosyasını seç',
    empty: 'Henüz ilerleme raporu seçilmedi. Kontrol edilmemiş hisseleri başarılı saymıyoruz.',
    malformed: 'Raporun biçimi, sayaçları veya parti dağılımı geçersiz. Başarı bilgisi gösterilmedi.',
    oversized: 'En fazla 2 MB JSON seçebilirsiniz.',
    checked: 'Kontrol edilen',
    analyzed: 'Başarılı analiz',
    failed: 'Başarısız',
    pending: 'Bekleyen',
    invalidBatches: 'Bozuk parti',
    analyzedWithin: 'Başarılı / kontrol edilen',
    nextBatch: 'Sıradaki eksik parti (1 tabanlı)',
    noBatch: 'Eksik parti yok',
    ready: '400 hisse veri kontrolü geçti. Bu, anlık fiyat veya işlem yetkisi kanıtı değildir.',
    inspect: 'Önce bozuk veya farklı kaynak listesine ait parti dosyalarını inceleyin.',
    retry: 'Eksik parti kalmadı; başarısız hisseleri --retry-failed ile ayrı kontrol edin.',
    run: 'Önce sıradaki eksik partiyi manuel olarak çalıştırın.',
    invalid: 'Tutarsız veya bozuk partiler (başarıya sayılmaz)',
    failedRows: 'Başarısız hisse sonuçları',
    errorType: 'Hata durumu',
    batch: 'Parti',
    status: 'İşlem durumu',
    date: 'Rapor tarihi',
    source: 'Kaynak tarihi',
    totalBatches: 'Doğrulanan parti',
    omitted: 'Diğer satırlar gösterilmedi; detaylar rapor dosyasında.',
    footer: 'Bu ekran yalnızca yerel raporun biçimini ve sayaç tutarlılığını doğrular. Kaynağın gerçekten Yahoo olduğu, kodların kotasyonu ve aracı kurum izinleri bağımsız olarak doğrulanmış değildir.',
    market: 'Piyasa',
    refreshServer: 'Sunucu raporunu yenile',
    loadingServer: 'Sunucu ilerlemesi okunuyor…',
    noServer: 'Sunucuda yönetici tarafından onaylanmış ilerleme raporu yok veya yönetici oturumu kapalı. Yerel JSON dosyası seçebilirsiniz.',
    savedServer: 'Sunucuda kayıtlı ilerleme raporu (salt okunur)',
  },
  en: {
    title: '400-stock · Batch progress',
    subtitle: 'Existing JSON report · Read-only',
    intro: 'An operator-approved saved --status report loads automatically with admin access. Local JSON remains an option; no file upload, scan or order placement.',
    select: 'Choose progress JSON',
    empty: 'No progress report selected. No unperformed scan is marked successful.',
    malformed: 'Report structure, totals or batch partition is inconsistent. No success was recorded.',
    oversized: 'JSON file must be no larger than 2 MB.',
    checked: 'Checked',
    analyzed: 'Analyzed successfully',
    failed: 'Failed',
    pending: 'Pending',
    invalidBatches: 'Invalid batches',
    analyzedWithin: 'Passed / checked',
    nextBatch: 'Next missing batch (1-based)',
    noBatch: 'No missing batches',
    ready: 'All 400 historical checks passed. Not proof of live quotes or brokerage permissions.',
    inspect: 'Inspect invalid or out-of-source batch files first.',
    retry: 'No batches missing; use --retry-failed for unsuccessful stock records.',
    run: 'Run the next missing batch manually.',
    invalid: 'Invalid or corrupted batches (not counted as success)',
    failedRows: 'Failed equity records',
    errorType: 'Error status',
    batch: 'Batch',
    status: 'Next action',
    date: 'Report date',
    source: 'Source date',
    totalBatches: 'Verified batches',
    omitted: 'More records are in the local report file.',
    footer: 'Only the local report shape and totals are validated. Yahoo origin, true listings, and brokerage permissions have not been independently verified.',
    market: 'Market',
    refreshServer: 'Refresh saved progress',
    loadingServer: 'Loading saved progress…',
    noServer: 'No operator-approved progress report is configured, or admin access is disabled. Select a local JSON file instead.',
    savedServer: 'Saved server progress (read-only)',
  },
  zh: {
    title: '400只股票 · 批次进度',
    subtitle: '已生成JSON报告 · 只读',
    intro: '管理员访问开启时会自动读取服务器保存的--status报告；也可选择本地JSON。文件不会上传，不会扫描或下单。',
    select: '选择进度JSON',
    empty: '尚未选择报告。未执行的检查不会标记为成功。',
    malformed: '报告格式、计数或批次分配不一致。未显示成功结果。',
    oversized: 'JSON文件不得超过2 MB。',
    checked: '已检查',
    analyzed: '分析成功',
    failed: '失败',
    pending: '待处理',
    invalidBatches: '无效批次',
    analyzedWithin: '成功 / 检查',
    nextBatch: '下一个缺失批次（从1开始）',
    noBatch: '无缺失批次',
    ready: '400只股票的历史检查全部通过；不代表实时行情或交易授权。',
    inspect: '请先检查损坏或来源不匹配的批次文件。',
    retry: '无缺失批次；请用--retry-failed重查失败股票。',
    run: '请手动运行下一个缺失批次。',
    invalid: '无效或损坏批次（不计为成功）',
    failedRows: '失败的股票记录',
    errorType: '错误状态',
    batch: '批次',
    status: '下一步',
    date: '报告日期',
    source: '来源日期',
    totalBatches: '已验证批次',
    omitted: '其余记录请查看本地报告文件。',
    footer: '仅验证本地报告格式和计数。未独立验证Yahoo来源、真实上市状态或券商授权。',
    market: '市场',
    refreshServer: '刷新服务器进度',
    loadingServer: '正在读取进度…',
    noServer: '服务器没有管理员批准的进度报告，或管理员访问已禁用。可使用本地JSON文件。',
    savedServer: '服务器已存进度（只读）',
  },
};

function stat(label: string, value: number) {
  return (
    <div className="rounded-xl border border-border/70 bg-surface/60 p-3">
      <div className="text-xs text-secondary-text">{label}</div>
      <div className="mt-2 text-xl font-semibold text-foreground">{value}</div>
    </div>
  );
}

export const FourMarketBatchProgressPanel: React.FC = () => {
  const { language } = useUiLanguage();
  const t = LABELS[language];
  const [report, setReport] = useState<FourMarketBatchProgress | null>(null);
  const [fileLabel, setFileLabel] = useState('');
  const [error, setError] = useState('');
  const [serverLoading, setServerLoading] = useState(false);
  const [serverMessage, setServerMessage] = useState('');
  const generation = useRef(0);
  const selectedLocal = useRef(false);

  const loadSaved = useCallback(async () => {
    if (selectedLocal.current) return;
    const request = ++generation.current;
    setServerLoading(true);
    setServerMessage('');
    try {
      const saved = await fourMarketBatchProgressApi.getSavedReport();
      if (request !== generation.current || selectedLocal.current) return;
      setReport(saved);
      setFileLabel(t.savedServer);
      setError('');
    } catch {
      if (request !== generation.current || selectedLocal.current) return;
      setServerMessage(t.noServer);
    } finally {
      if (request === generation.current) setServerLoading(false);
    }
  }, [t]);

  useEffect(() => {
    void loadSaved();
    return () => { generation.current += 1; };
  }, [loadSaved]);

  const reloadSaved = () => {
    selectedLocal.current = false;
    generation.current += 1;
    setReport(null);
    setFileLabel('');
    setError('');
    void loadSaved();
  };

  const chooseFile = async (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.currentTarget.files?.[0];
    event.currentTarget.value = '';
    if (!file) return;
    selectedLocal.current = true;
    setServerLoading(false);
    setServerMessage('');
    const selected = ++generation.current;
    setReport(null);
    setFileLabel('');
    setError('');
    if (file.size > FILE_BYTES_LIMIT) {
      setError(t.oversized);
      return;
    }
    try {
      const parsed: unknown = JSON.parse(await file.text());
      const validated = parseFourMarketBatchProgress(parsed);
      if (selected !== generation.current) return;
      setReport(validated);
      setFileLabel(file.name);
    } catch {
      if (selected !== generation.current) return;
      setError(t.malformed);
    }
  };

  const actionMessage = report?.next_action === 'inspect_invalid_batches' ? t.inspect
    : report?.next_action === 'run_next_missing_batch' ? t.run
      : report?.next_action === 'review_or_retry_failed_batches' ? t.retry
        : t.ready;

  return (
    <Card title={t.title} subtitle={t.subtitle} variant="bordered" padding="md">
      <div className="space-y-4">
        <p className="text-sm text-secondary-text">{t.intro}</p>
        <div className="flex flex-wrap gap-2">
          <button
            type="button"
            disabled={serverLoading}
            onClick={reloadSaved}
            className="rounded-lg border border-border bg-surface px-3 py-2 text-sm font-medium text-foreground disabled:opacity-40"
          >{serverLoading ? t.loadingServer : t.refreshServer}</button>
        <label className="inline-flex cursor-pointer items-center rounded-lg border border-border bg-surface px-3 py-2 text-sm font-medium text-foreground">
          {t.select}
          <input
            type="file"
            className="sr-only"
            accept=".json,application/json"
            aria-label={t.select}
            onChange={event => { void chooseFile(event); }}
          />
        </label>
        </div>
        {serverMessage ? <p role="status" className="text-xs text-muted-text">{serverMessage}</p> : null}
        {error ? <p role="alert" className="text-sm text-danger">{error}</p> : null}
        {!report && !error && !serverLoading ? <p className="text-sm text-muted-text">{t.empty}</p> : null}
        {report ? (
          <>
            <div className="text-xs text-muted-text">
              {fileLabel} · {t.date}: {report.as_of} · {t.source}: {report.source_as_of}
            </div>
            <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
              {stat(t.checked, report.checked_symbols)}
              {stat(t.analyzed, report.analyzed_symbols)}
              {stat(t.failed, report.failed_symbols)}
              {stat(t.pending, report.pending_symbols)}
            </div>
            <div className="space-y-2">
              <div className="h-2 w-full overflow-hidden rounded-full bg-surface">
                <div
                  role="progressbar"
                  aria-label={t.checked}
                  aria-valuemin={0}
                  aria-valuemax={400}
                  aria-valuenow={report.checked_symbols}
                  className="h-full rounded-full bg-primary"
                  style={{ width: (report.checked_symbols / 400 * 100) + '%' }}
                />
              </div>
              <p className="text-xs text-muted-text">
                {t.totalBatches}: {report.verified_batch_indices.length} / {report.batches_total}
                {' · '}{t.invalidBatches}: {report.invalid_batches.length}
              </p>
            </div>
            <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
              {FOUR_ACTIVE_MARKETS.map(market => {
                const counts = report.by_market[market];
                return (
                  <div key={market} className="rounded-xl border border-border/70 bg-surface/60 p-3">
                    <div className="font-semibold text-foreground">{MARKETS[market][language]}</div>
                    <div className="mt-1 text-lg font-semibold text-foreground">
                      {counts.checked_symbols} / {counts.target_symbols}
                    </div>
                    <div className="text-xs text-secondary-text">
                      {t.analyzedWithin}: {counts.analyzed_symbols} / {counts.checked_symbols}
                    </div>
                    <div className="text-xs text-muted-text">
                      {t.failed}: {counts.failed_symbols} · {t.pending}: {counts.pending_symbols}
                    </div>
                  </div>
                );
              })}
            </div>
            <div className="rounded-lg border border-border/70 p-3 text-sm">
              <div className="font-medium text-foreground">{t.status}</div>
              <div className="mt-1 text-secondary-text">{actionMessage}</div>
              <div className="mt-2 text-xs text-muted-text">
                {t.nextBatch}: {report.next_missing_batch_index === null
                  ? t.noBatch : (report.next_missing_batch_index + 1) + ' / ' + report.batches_total}
              </div>
            </div>
            {report.invalid_batches.length ? (
              <div className="space-y-2">
                <div className="font-semibold text-foreground">{t.invalid}</div>
                <ul className="space-y-1 text-xs text-danger">
                  {report.invalid_batches.slice(0, MAX_DISPLAY_ROWS).map(batch => (
                    <li key={batch.batch_index}>
                      {batch.filename}: {batch.reason}
                    </li>
                  ))}
                </ul>
                {report.invalid_batches.length > MAX_DISPLAY_ROWS
                  ? <p className="text-xs text-muted-text">{t.omitted}</p> : null}
              </div>
            ) : null}
            {report.failed_rows.length ? (
              <div className="space-y-2">
                <div className="font-semibold text-foreground">{t.failedRows}</div>
                <div className="overflow-x-auto">
                  <table className="w-full min-w-[430px] text-left text-xs">
                    <thead className="border-b border-border/60 text-muted-text">
                      <tr>
                        <th className="px-2 py-2 font-medium">{t.batch}</th>
                        <th className="px-2 py-2 font-medium">{t.market}</th>
                        <th className="px-2 py-2 font-medium">{t.failedRows}</th>
                        <th className="px-2 py-2 font-medium">{t.errorType}</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-border/40">
                      {report.failed_rows.slice(0, MAX_DISPLAY_ROWS).map(row => (
                        <tr key={row.code}>
                          <td className="px-2 py-2">{row.batch_index + 1}</td>
                          <td className="px-2 py-2">{MARKETS[row.market][language]}</td>
                          <td className="px-2 py-2 font-mono notranslate" translate="no">{row.code}</td>
                          <td className="px-2 py-2"><Badge variant="warning">{row.status}</Badge></td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
                {report.failed_rows.length > MAX_DISPLAY_ROWS
                  ? <p className="text-xs text-muted-text">{t.omitted}</p> : null}
              </div>
            ) : null}
            <p role="note" className="text-xs leading-relaxed text-muted-text">{t.footer}</p>
          </>
        ) : null}
      </div>
    </Card>
  );
};
