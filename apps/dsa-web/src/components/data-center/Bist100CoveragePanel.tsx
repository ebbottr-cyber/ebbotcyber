import type React from 'react';
import { useCallback, useEffect, useRef, useState } from 'react';
import { bist100CoverageApi } from '../../api/bist100Coverage';
import { Badge, Card } from '../common';
import { parseBist100CoverageReport, type Bist100CoverageReport } from '../../utils/bist100CoverageReport';

const PER_PAGE = 25;
const LABELS: Record<string, string> = {
  ready: 'Veri hazır',
  no_data: 'Veri yok',
  fetch_error: 'Sağlayıcı hatası',
  invalid_data: 'Geçersiz veri',
  no_completed_bars: 'Tamamlanmış seans yok',
  stale_price: 'Eski fiyat',
  insufficient_history: 'Yetersiz geçmiş',
  currency_mismatch: 'Para birimi uyuşmuyor',
  currency_unverified: 'Para birimi doğrulanmadı',
  calendar_unavailable: 'Takvim doğrulanamadı',
};

function summaryValue(label: string, count: number, note: string) {
  return (
    <div className="rounded-xl border border-border/70 bg-surface/60 px-4 py-3">
      <div className="text-xs text-secondary-text">{label}</div>
      <div className="mt-1 text-2xl font-semibold text-foreground">{count}</div>
      <div className="text-xs text-muted-text">{note}</div>
    </div>
  );
}

/** Read-only report viewer; never calls a pricing API or performs analysis. */
export const Bist100CoveragePanel: React.FC = () => {
  const [report, setReport] = useState<Bist100CoverageReport | null>(null);
  const [error, setError] = useState('');
  const [page, setPage] = useState(0);
  const [filename, setFilename] = useState('');
  const [serverMessage, setServerMessage] = useState('');
  const [serverLoading, setServerLoading] = useState(false);
  const requestGeneration = useRef(0);
  const manuallySelected = useRef(false);

  const loadSavedReport = useCallback(async () => {
    const generation = ++requestGeneration.current;
    setServerLoading(true);
    setServerMessage('');
    try {
      const saved = await bist100CoverageApi.getSavedReport();
      if (generation !== requestGeneration.current || manuallySelected.current) return;
      setReport(saved);
      setPage(0);
      setFilename('Sunucu raporu (salt okunur)');
      setError('');
    } catch {
      if (generation !== requestGeneration.current || manuallySelected.current) return;
      setServerMessage(
        'Sunucuda doğrulanmış BIST100 raporu bulunamadı veya yönetici erişimi kapalı. ' +
        'İsterseniz yerel JSON raporu seçebilirsiniz.'
      );
    } finally {
      if (generation === requestGeneration.current) setServerLoading(false);
    }
  }, []);

  useEffect(() => {
    void loadSavedReport();
    return () => { requestGeneration.current += 1; };
  }, [loadSavedReport]);

  const reloadSavedReport = () => {
    manuallySelected.current = false;
    setReport(null);
    setFilename('');
    setError('');
    setPage(0);
    void loadSavedReport();
  };

  const onFileChange = async (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.currentTarget.files?.[0];
    // Re-importing the same filename must trigger a new change event.
    event.currentTarget.value = '';
    if (!file) return;
    manuallySelected.current = true;
    const generation = ++requestGeneration.current;
    setServerLoading(false);
    setServerMessage('');
    setError('');
    setReport(null);
    setFilename('');
    setPage(0);
    if (file.size > 2_000_000) {
      setError('JSON dosyası en fazla 2 MB olabilir.');
      return;
    }
    try {
      const parsed: unknown = JSON.parse(await file.text());
      const next = parseBist100CoverageReport(parsed);
      if (generation !== requestGeneration.current) return;
      setReport(next);
      setFilename(file.name);
    } catch (cause) {
      if (generation !== requestGeneration.current) return;
      setError(cause instanceof Error ? cause.message : 'Rapor okunamadı.');
    }
  };

  const visible = report?.results.slice(page * PER_PAGE, (page + 1) * PER_PAGE) ?? [];
  const pages = report ? Math.max(1, Math.ceil(report.checked / PER_PAGE)) : 1;
  const problemCount = report ? report.checked - report.ready : 0;

  return (
    <Card title="BIST100 · Yahoo veri kapsaması" subtitle="Kaydedilmiş sunucu raporu veya yerel JSON · salt okunur" variant="bordered" padding="md">
      <div className="space-y-4">
        <p className="text-sm text-secondary-text">
          Sunucuda doğrulanmış bir rapor varsa otomatik gösterilir; ayrıca yerel JSON raporu da seçebilirsiniz.
          Yerel dosya sunucuya gönderilmez. Veri hazır olması, AI analizinin tamamlandığı anlamına gelmez.
        </p>
        <button type="button"
          className="inline-flex items-center rounded-lg border border-border bg-surface px-3 py-2 text-sm text-foreground disabled:opacity-50"
          disabled={serverLoading} onClick={reloadSavedReport}>
          {serverLoading ? 'Sunucu raporu kontrol ediliyor…' : 'Sunucu raporunu yenile'}
        </button>
        <label className="inline-flex cursor-pointer items-center gap-2 rounded-lg border border-border bg-surface px-3 py-2 text-sm text-foreground">
          JSON raporu seç
          <input type="file" accept=".json,application/json" onChange={(event) => { void onFileChange(event); }}
            className="sr-only" aria-label="BIST100 JSON raporu seç" />
        </label>
        {serverMessage ? <p role="status" className="text-sm text-muted-text">{serverMessage}</p> : null}
        {error ? <p role="alert" className="text-sm text-danger">{error}</p> : null}
        {!report && !error && !serverLoading ? (
          <p className="text-sm text-muted-text">
            Doğrulanmış rapor yok. Canlı veri taraması yapılmış veya 100 hissenin analiz edilmiş olduğu varsayılmıyor.
          </p>
        ) : null}
        {report ? (
          <>
            <div className="text-xs text-muted-text">
              {filename} · Rapor tarihi: {report.as_of} · Kaynak: {report.source} · TRY · XIST
              {report.complete ? ' · 100 hisse kontrol edildi' : ' · Kısmi tarama'}
            </div>
            <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
              {summaryValue('Kontrol edilen', report.checked, 'Toplam 100 hisse')}
              {summaryValue('Veri hazır', report.ready, 'Tamamlanan seans ve TRY doğrulandı')}
              {summaryValue('Sorunlu / eksik', problemCount, 'Kontrol edilen hisseler içinde')}
              {summaryValue('Henüz kontrol edilmedi', report.remaining, 'Hazır sayılmaz')}
            </div>
            {!report.complete ? (
              <p className="text-sm text-warning" role="status">
                Bu rapor kısmi: {report.remaining} hisse henüz kontrol edilmedi. Sonuç 100/100 başarı olarak gösterilemez.
              </p>
            ) : null}
            <div className="flex flex-wrap gap-2">
              {Object.entries(report.status_counts).sort(([a], [b]) => a.localeCompare(b)).map(([status, count]) => (
                <Badge key={status} variant={status === 'ready' ? 'success' : 'warning'}>
                  {LABELS[status] || status}: {count}
                </Badge>
              ))}
            </div>
            <div className="overflow-x-auto">
              <table className="w-full min-w-[650px] text-left text-sm">
                <thead className="border-b border-border/60 text-xs uppercase text-muted-text">
                  <tr>
                    <th className="px-3 py-2">Hisse</th>
                    <th className="px-3 py-2">Veri durumu</th>
                    <th className="px-3 py-2">Günlük satır</th>
                    <th className="px-3 py-2">Son seans verisi</th>
                    <th className="px-3 py-2">Para birimi</th>
                    <th className="px-3 py-2">Not</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-border/40">
                  {visible.map((item) => (
                    <tr key={item.symbol}>
                      <td className="px-3 py-2 font-mono text-foreground">{item.symbol}</td>
                      <td className="px-3 py-2">
                        <Badge variant={item.status === 'ready' ? 'success' : 'warning'}>
                          {LABELS[item.status] || item.status}
                        </Badge>
                      </td>
                      <td className="px-3 py-2 text-secondary-text">{item.rows}</td>
                      <td className="px-3 py-2 text-secondary-text">{item.last_bar_date || '—'}</td>
                      <td className="px-3 py-2 text-secondary-text">{item.observed_currency || '—'}</td>
                      <td className="px-3 py-2 text-secondary-text">
                        {[...item.issues, item.error_type].filter(Boolean).join(', ') || '—'}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            {pages > 1 ? (
              <div className="flex items-center justify-end gap-3">
                <button type="button" className="rounded-lg border border-border px-3 py-1 text-sm disabled:opacity-50"
                  disabled={page === 0} onClick={() => setPage(value => value - 1)}>Önceki</button>
                <span className="text-xs text-secondary-text">Sayfa {page + 1} / {pages}</span>
                <button type="button" className="rounded-lg border border-border px-3 py-1 text-sm disabled:opacity-50"
                  disabled={page >= pages - 1} onClick={() => setPage(value => value + 1)}>Sonraki</button>
              </div>
            ) : null}
          </>
        ) : null}
      </div>
    </Card>
  );
};
