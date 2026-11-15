import type React from 'react';
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { bist100TechnicalApi } from '../../api/bist100Technical';
import { Badge, Card } from '../common';
import {
  parseBist100TechnicalReport,
  type Bist100TechnicalReport,
} from '../../utils/bist100TechnicalReport';
import {
  selectBist100Ranking,
  type Bist100RiskView,
  type Bist100SortView,
} from '../../utils/bist100RankingView';

const PAGE_SIZE = 20;
const STATUSES: Record<string, string> = {
  analyzed: 'Teknik analiz hazır',
  not_imported: 'Veri içeri aktarılmamış',
  db_error: 'Veritabanı hatası',
  unverified_source: 'Kaynak doğrulanamadı',
  invalid_data: 'Fiyat verisi geçersiz',
  insufficient_history: 'Geçmiş yetersiz',
  stale_price: 'Eski fiyat',
  analysis_error: 'Teknik analiz hatası',
};

function tile(label: string, value: number, detail: string) {
  return (
    <div className="rounded-xl border border-border/70 bg-surface/60 px-4 py-3">
      <div className="text-xs text-secondary-text">{label}</div>
      <div className="mt-1 text-2xl font-semibold text-foreground">{value}</div>
      <div className="text-xs text-muted-text">{detail}</div>
    </div>
  );
}

/** Historical, read-only scoring display. Never invokes LLM or places orders. */
export const Bist100TechnicalPanel: React.FC = () => {
  const [report, setReport] = useState<Bist100TechnicalReport | null>(null);
  const [selectedFile, setSelectedFile] = useState('');
  const [page, setPage] = useState(0);
  const [symbolQuery, setSymbolQuery] = useState('');
  const [riskView, setRiskView] = useState<Bist100RiskView>('all');
  const [minScore, setMinScore] = useState(0);
  const [sortView, setSortView] = useState<Bist100SortView>('rank');
  const [error, setError] = useState('');
  const [serverMessage, setServerMessage] = useState('');
  const [loading, setLoading] = useState(false);
  const generation = useRef(0);
  const manuallySelected = useRef(false);

  const loadSaved = useCallback(async () => {
    const request = ++generation.current;
    setLoading(true);
    setServerMessage('');
    try {
      const next = await bist100TechnicalApi.getSavedReport();
      if (request !== generation.current || manuallySelected.current) return;
      setReport(next);
      setSelectedFile('Sunucu raporu (salt okunur)');
      setPage(0);
      setError('');
    } catch {
      if (request !== generation.current || manuallySelected.current) return;
      setServerMessage(
        'Sunucuda doğrulanmış teknik sıralama bulunamadı veya yönetici erişimi kapalı. ' +
        'Önceden oluşturduğunuz JSON raporunu yerel olarak seçebilirsiniz.'
      );
    } finally {
      if (request === generation.current) setLoading(false);
    }
  }, []);

  useEffect(() => {
    void loadSaved();
    return () => { generation.current += 1; };
  }, [loadSaved]);

  const reload = () => {
    manuallySelected.current = false;
    setReport(null);
    setSelectedFile('');
    setPage(0);
    setError('');
    void loadSaved();
  };

  const chooseFile = async (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.currentTarget.files?.[0];
    event.currentTarget.value = '';
    if (!file) return;
    manuallySelected.current = true;
    const request = ++generation.current;
    setLoading(false);
    setReport(null);
    setSelectedFile('');
    setPage(0);
    setError('');
    setServerMessage('');
    if (file.size > 2_000_000) {
      setError('Teknik rapor JSON dosyası en fazla 2 MB olabilir.');
      return;
    }
    try {
      const json: unknown = JSON.parse(await file.text());
      const parsed = parseBist100TechnicalReport(json);
      if (request !== generation.current) return;
      setReport(parsed);
      setSelectedFile(file.name);
    } catch (cause) {
      if (request !== generation.current) return;
      setError(cause instanceof Error ? cause.message : 'Rapor geçersiz veya okunamadı.');
    }
  };

  const ranking = useMemo(
    () => selectBist100Ranking(report?.ranking ?? [], {
      symbolQuery, risk: riskView, minScore, sort: sortView,
    }),
    [report?.ranking, symbolQuery, riskView, minScore, sortView],
  );
  const maxPage = Math.max(0, Math.ceil(ranking.length / PAGE_SIZE) - 1);
  const visible = ranking.slice(page * PAGE_SIZE, (page + 1) * PAGE_SIZE);
  const format = (value: number, digits = 2) =>
    value.toLocaleString('tr-TR', { maximumFractionDigits: digits, minimumFractionDigits: digits });

  return (
    <Card
      title="BIST100 · Teknik sıralama"
      subtitle="Kaydedilmiş teknik tarama · geçmiş günlük fiyatlar · salt okunur"
      variant="bordered" padding="md"
    >
      <div className="space-y-4">
        <p className="text-sm text-secondary-text">
          Yalnızca daha önce veritabanından oluşturulmuş teknik tarama raporunu gösterir.
          Puanlar MA, RSI, MACD, hacim ve trend hesaplamalarına dayanır; AI analizi
          veya yatırım tavsiyesi değildir. Bu ekran analiz başlatmaz, veri indirmez ve emir göndermez.
        </p>
        <div className="flex flex-wrap gap-2">
          <button type="button"
            className="rounded-lg border border-border bg-surface px-3 py-2 text-sm text-foreground disabled:opacity-50"
            onClick={reload} disabled={loading}>
            {loading ? 'Sunucu raporu kontrol ediliyor…' : 'Sunucu sıralamasını yenile'}
          </button>
          <label className="inline-flex cursor-pointer items-center rounded-lg border border-border bg-surface px-3 py-2 text-sm text-foreground">
            Teknik JSON raporu seç
            <input type="file" accept=".json,application/json" className="sr-only"
              aria-label="BIST100 teknik JSON raporu seç"
              onChange={(event) => { void chooseFile(event); }} />
          </label>
        </div>
        {serverMessage ? <p role="status" className="text-sm text-muted-text">{serverMessage}</p> : null}
        {error ? <p role="alert" className="text-sm text-danger">{error}</p> : null}
        {!report && !error && !loading ? (
          <p className="text-sm text-muted-text">
            Teknik tarama raporu bulunamadı. Henüz hisselerin analiz edildiği varsayılmıyor.
            Önce fiyat geçmişinin içeri aktarılması ve tarama komutunun çalıştırılması gerekir.
          </p>
        ) : null}

        {report ? (
          <>
            <div className="text-xs text-muted-text">
              {selectedFile} · Tarihsel rapor: {report.as_of} · Son tamamlanan seans: {report.last_completed_session}
              {' · '}100 BIST hissesinden {report.checked} tanesi kontrol edildi
            </div>
            {manuallySelected.current ? (
              <p className="text-xs text-warning">
                Yerel JSON dosyası: tarayıcı biçim ve sayaçları denetler, ancak kaynak özgünlüğünü
                veya son işlem seansını borsadan bağımsız doğrulayamaz. Canlı fiyat değildir.
              </p>
            ) : null}
            <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
              {tile('Kontrol edilen', report.checked, 'Toplam 100 hisseden')}
              {tile('Teknik analiz', report.analyzed, 'Gerçek fiyat geçmişiyle')}
              {tile('MA5 mesafe filtresi', report.watchlist_eligible, 'Yalnızca >%5 uzaklık riski yok')}
              {tile('Henüz kontrol edilmedi', report.remaining, 'Analiz edilmiş sayılmaz')}
            </div>
            {report.remaining > 0 ? (
              <p role="status" className="text-sm text-warning">
                Kısmi rapor: {report.remaining} hisse henüz taranmadı; sonuçlar 100 hisseyi temsil etmez.
              </p>
            ) : null}
            <div className="flex flex-wrap gap-2">
              {Object.entries(report.status_counts).sort(([a], [b]) => a.localeCompare(b)).map(([status, count]) => (
                <Badge key={status} variant={status === 'analyzed' ? 'success' : 'warning'}>
                  {STATUSES[status] ?? status}: {count}
                </Badge>
              ))}
            </div>
            {report.analyzed === 0 ? (
              <p className="text-sm text-muted-text">
                Geçerli teknik analiz bulunamadı; boş tabloyu başarılı tarama olarak yorumlamayın.
              </p>
            ) : (
              <>
                <div className="grid grid-cols-1 gap-3 rounded-xl border border-border/70 bg-surface/40 p-3 sm:grid-cols-2 lg:grid-cols-4">
                  <label className="flex flex-col gap-1 text-xs text-secondary-text">
                    Hisse ara
                    <input type="search" value={symbolQuery} maxLength={16}
                      onChange={event => { setSymbolQuery(event.target.value); setPage(0); }}
                      placeholder="Örn: THYAO" aria-label="BIST100 hisse kodu ara"
                      className="rounded-lg border border-border bg-surface px-3 py-2 text-sm text-foreground"
                    />
                  </label>
                  <label className="flex flex-col gap-1 text-xs text-secondary-text">
                    MA5 mesafe uyarısı
                    <select value={riskView}
                      onChange={event => { setRiskView(event.target.value as Bist100RiskView); setPage(0); }}
                      aria-label="MA5 mesafe riskini filtrele"
                      className="rounded-lg border border-border bg-surface px-3 py-2 text-sm text-foreground">
                      <option value="all">Tüm analizler</option>
                      <option value="ma5-clear">Yüksek MA5 mesafesi olmayan</option>
                      <option value="chase-risk">Yüksek MA5 mesafesi olan</option>
                    </select>
                  </label>
                  <label className="flex flex-col gap-1 text-xs text-secondary-text">
                    En düşük teknik puan
                    <select value={minScore}
                      onChange={event => { setMinScore(Number(event.target.value)); setPage(0); }}
                      aria-label="En düşük teknik puanı seç"
                      className="rounded-lg border border-border bg-surface px-3 py-2 text-sm text-foreground">
                      <option value={0}>Hepsi (0+)</option>
                      <option value={60}>60+</option>
                      <option value={70}>70+</option>
                      <option value={80}>80+</option>
                      <option value={90}>90+</option>
                    </select>
                  </label>
                  <label className="flex flex-col gap-1 text-xs text-secondary-text">
                    Görünüm sırası
                    <select value={sortView}
                      onChange={event => { setSortView(event.target.value as Bist100SortView); setPage(0); }}
                      aria-label="Görünüm sırasını seç"
                      className="rounded-lg border border-border bg-surface px-3 py-2 text-sm text-foreground">
                      <option value="rank">Orijinal teknik sıralama</option>
                      <option value="symbol">Hisse koduna göre</option>
                      <option value="rsi">RSI (yüksekten düşüğe)</option>
                    </select>
                  </label>
                </div>
                <p role="status" className="text-xs text-muted-text">
                  Analiz edilen: {report.analyzed} · Bu görünümde: {ranking.length}.
                  {' '}Sıra numaraları orijinal rapordan korunur; filtreleme yeni analiz veya alım sinyali üretmez.
                </p>
                {ranking.length === 0 ? (
                  <p className="text-sm text-muted-text">
                    Bu filtrelerle eşleşen hisse yok. Filtreleri değiştirerek tüm analizleri görebilirsiniz.
                  </p>
                ) : null}
                <div className="overflow-x-auto">
                  <table className="w-full min-w-[900px] text-left text-sm">
                    <thead className="border-b border-border/60 text-xs uppercase text-muted-text">
                      <tr>
                        <th className="px-3 py-2 font-medium">Sıra</th>
                        <th className="px-3 py-2 font-medium">Hisse</th>
                        <th className="px-3 py-2 font-medium">Puan</th>
                        <th className="px-3 py-2 font-medium">Kapanış (₺)</th>
                        <th className="px-3 py-2 font-medium">MA5 (₺)</th>
                        <th className="px-3 py-2 font-medium">RSI(12)</th>
                        <th className="px-3 py-2 font-medium">MACD hist.</th>
                        <th className="px-3 py-2 font-medium">MA5 farkı</th>
                        <th className="px-3 py-2 font-medium">Teknik yorum</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-border/40">
                      {visible.map((item) => (
                        <tr key={item.symbol}>
                          <td className="px-3 py-3 text-secondary-text">{item.rank}</td>
                          <td className="px-3 py-3 font-mono font-semibold text-foreground">{item.symbol}</td>
                          <td className="px-3 py-3 font-semibold text-foreground">{item.score}/100</td>
                          <td className="px-3 py-3 text-secondary-text">{format(item.close_try, 4)}</td>
                          <td className="px-3 py-3 text-secondary-text">{format(item.ma5_try, 4)}</td>
                          <td className="px-3 py-3 text-secondary-text">{format(item.rsi12)}</td>
                          <td className="px-3 py-3 text-secondary-text">{format(item.macd_histogram, 4)}</td>
                          <td className="px-3 py-3 text-secondary-text">{format(item.bias_ma5_pct)}%</td>
                          <td className="px-3 py-3">
                            <div className="text-foreground">{item.trend}</div>
                            <div className="text-xs text-secondary-text">{item.technical_signal}</div>
                            {item.chase_risk ? (
                              <Badge variant="warning">MA5 uzaklığı yüksek · izlemeye uygun değil</Badge>
                            ) : null}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
                {maxPage > 0 ? (
                  <div className="flex items-center justify-between gap-3 text-sm">
                    <span className="text-muted-text">Sayfa {page + 1} / {maxPage + 1}</span>
                    <div className="flex gap-2">
                      <button type="button" disabled={page === 0}
                        className="rounded-lg border border-border px-3 py-1 disabled:opacity-40"
                        onClick={() => setPage(v => Math.max(0, v - 1))}>Önceki</button>
                      <button type="button" disabled={page >= maxPage}
                        className="rounded-lg border border-border px-3 py-1 disabled:opacity-40"
                        onClick={() => setPage(v => Math.min(maxPage, v + 1))}>Sonraki</button>
                    </div>
                  </div>
                ) : null}
              </>
            )}
          </>
        ) : null}
      </div>
    </Card>
  );
};
