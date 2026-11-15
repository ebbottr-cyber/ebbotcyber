import type React from 'react';
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { bist100TechnicalApi } from '../../api/bist100Technical';
import { sixMarketSmokeApi } from '../../api/sixMarketSmoke';
import type { Bist100TechnicalReport } from '../../utils/bist100TechnicalReport';
import {
  parseSixMarketEvidence, selectSevenMarketEvidence,
  type SixMarketEvidence, type EvidenceState,
} from '../../utils/sevenMarketEvidence';
import { Badge, Card } from '../common';

const STATUS: Record<EvidenceState, string> = {
  not_loaded: 'Kaydedilmiş kanıt yok',
  historical_analyzed: 'Tarihsel raporda analiz var',
  historical_failed: 'Tarihsel raporda sorun var',
};

/** Seven historical coverage views. Does not call price / analysis / trading APIs. */
export const SevenMarketEvidencePanel: React.FC = () => {
  const [bist, setBist] = useState<Bist100TechnicalReport | null>(null);
  const [six, setSix] = useState<SixMarketEvidence | null>(null);
  const [sixSource, setSixSource] = useState<'none' | 'server' | 'local'>('none');
  const [sixWarning, setSixWarning] = useState('');
  const [sixLoading, setSixLoading] = useState(false);
  const [filename, setFilename] = useState('');
  const [error, setError] = useState('');
  const [serverWarning, setServerWarning] = useState('');
  const [loading, setLoading] = useState(false);
  const generation = useRef(0);
  const sixGeneration = useRef(0);
  const manuallySelectedSix = useRef(false);

  const loadBist = useCallback(async () => {
    const request = ++generation.current;
    setLoading(true);
    setServerWarning('');
    try {
      const saved = await bist100TechnicalApi.getSavedReport();
      if (request !== generation.current) return;
      setBist(saved);
    } catch {
      if (request !== generation.current) return;
      setBist(null);
      setServerWarning('BIST100 kaydedilmiş teknik raporu yok veya yönetici erişimi kapalı.');
    } finally {
      if (request === generation.current) setLoading(false);
    }
  }, []);

  useEffect(() => {
    void loadBist();
    return () => { generation.current += 1; };
  }, [loadBist]);

  const loadSavedSix = useCallback(async () => {
    const request = ++sixGeneration.current;
    setSixLoading(true);
    setSixWarning('');
    try {
      const saved = await sixMarketSmokeApi.getSavedReport();
      if (request !== sixGeneration.current || manuallySelectedSix.current) return;
      setSix(saved);
      setSixSource('server');
      setFilename('Yönetici tarafından onaylanmış sunucu raporu');
      setError('');
    } catch {
      if (request !== sixGeneration.current || manuallySelectedSix.current) return;
      setSix(null);
      setSixSource('none');
      setFilename('');
      setSixWarning('Sunucuda onaylanmış altı piyasa örnek raporu yok veya yönetici erişimi kapalı.');
    } finally {
      if (request === sixGeneration.current) setSixLoading(false);
    }
  }, []);

  useEffect(() => {
    void loadSavedSix();
    return () => { sixGeneration.current += 1; };
  }, [loadSavedSix]);

  const reloadSavedSix = () => {
    manuallySelectedSix.current = false;
    setSix(null);
    setSixSource('none');
    setFilename('');
    setError('');
    void loadSavedSix();
  };

  const onSixFile = async (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.currentTarget.files?.[0];
    event.currentTarget.value = '';
    if (!file) return;
    manuallySelectedSix.current = true;
    const request = ++sixGeneration.current;
    setSixLoading(false);
    setSixWarning('');
    setError('');
    setFilename('');
    setSix(null);
    setSixSource('none');
    if (file.size > 2_000_000) {
      setError('Örnek piyasa JSON dosyası en fazla 2 MB olabilir.');
      return;
    }
    try {
      const next = parseSixMarketEvidence(JSON.parse(await file.text()) as unknown);
      if (request !== sixGeneration.current) return;
      setSix(next);
      setSixSource('local');
      setFilename(file.name);
    } catch (cause) {
      if (request !== sixGeneration.current) return;
      setError(cause instanceof Error ? cause.message : 'Örnek piyasa raporu okunamadı.');
    }
  };

  const rows = useMemo(() => selectSevenMarketEvidence(bist, six), [bist, six]);
  const withEvidence = rows.filter(row => row.state !== 'not_loaded').length;
  return (
    <Card title="7 piyasa · Tarihsel doğrulama görünümü"
      subtitle="BIST100 tam evren raporu ve 6 ayrı piyasanın birer örnek sembol testi · Salt okunur"
      variant="bordered" padding="md">
      <div className="space-y-4">
        <p className="text-sm text-secondary-text">
          Buradaki bilgiler canlı borsa bağlantısı, bütün hisselerin analizi veya yatırım önerisi değildir.
          BIST100 için sunucuda kayıtlı teknik rapor okunur; diğer altı piyasa için
          yönetici tarafından önceden kaydedilmiş ve doğrulanmış örnek rapor sunucudan okunabilir.
          Alternatif olarak tarihsel Yahoo örnek-test JSON dosyasını tarayıcıda seçebilirsiniz.
          Bir örnek sembolün analiz edilmiş olması tüm piyasanın tarandığı anlamına gelmez.
        </p>
        <div className="flex flex-wrap gap-2">
          <button type="button" onClick={() => void loadBist()} disabled={loading}
            className="rounded-lg border border-border px-3 py-2 text-sm text-foreground disabled:opacity-50">
            {loading ? 'BIST100 raporu okunuyor…' : 'BIST100 kaydedilmiş raporu yenile'}
          </button>
          <button type="button" onClick={reloadSavedSix} disabled={sixLoading}
            className="rounded-lg border border-border px-3 py-2 text-sm text-foreground disabled:opacity-50">
            {sixLoading ? 'Altı piyasa raporu okunuyor…' : 'Altı piyasa sunucu raporunu yenile'}
          </button>
          <label className="inline-flex cursor-pointer items-center rounded-lg border border-border bg-surface px-3 py-2 text-sm text-foreground">
            Altı piyasa örnek JSON'u seç
            <input type="file" accept=".json,application/json"
              className="sr-only" aria-label="Altı piyasa örnek raporu seç"
              onChange={event => { void onSixFile(event); }}/>
          </label>
          {sixSource === 'local' ? (
            <button type="button" onClick={reloadSavedSix}
              className="rounded-lg border border-border px-3 py-2 text-sm text-secondary-text">
              Yerel örnek raporu temizle
            </button>
          ) : null}
        </div>
        <p className="text-xs text-muted-text" role="status">
          Kaydedilmiş tarihsel kanıt bulunan piyasa: {withEvidence}/7.
          {' '}BIST100: en fazla 100 hisse; diğer piyasalar: her biri yalnızca 1 örnek.
        </p>
        {serverWarning ? <p className="text-xs text-warning">{serverWarning}</p> : null}
        {sixWarning ? <p className="text-xs text-warning">{sixWarning}</p> : null}
        {error ? <p role="alert" className="text-sm text-danger">{error}</p> : null}
        {six ? (
          <p className="text-xs text-warning">
            {filename} · Rapor tarihi: {six.asOf} · Kaydedilmiş örnek analiz: {six.analyzedMarkets}/6.
            {sixSource === 'local' ? (
              <> {' '}Yerel JSON dosyası sunucuya yüklenmez; kaynağı ve borsa takvimini
              tarayıcı bağımsız doğrulayamaz. Yalnızca dosyanın iç tutarlılığı kontrol edilir.</>
            ) : (
              <> {' '}Kaydedilmiş sunucu raporu dosya SHA-256 değeri, örnek kimliği ve
              piyasa takvimi açısından doğrulandı. Tarihsel testtir, canlı fiyat değildir.</>
            )}
          </p>
        ) : (
          <p className="text-xs text-muted-text">
            Diğer altı piyasa için onaylı sunucu raporu veya yerel test dosyası bulunamadı;
            güncel başarı veya doğrulanmış fiyat verisi varsayılmıyor.
          </p>
        )}
        <div className="overflow-x-auto">
          <table className="w-full min-w-[900px] text-left text-sm">
            <thead className="border-b border-border/70 text-xs uppercase text-muted-text">
              <tr>
                <th className="px-3 py-2 font-medium">Piyasa</th>
                <th className="px-3 py-2 font-medium">Kanıt kapsamı</th>
                <th className="px-3 py-2 font-medium">Tarihsel durum</th>
                <th className="px-3 py-2 font-medium">Rapor / son seans</th>
                <th className="px-3 py-2 font-medium">Kontrol / analiz</th>
                <th className="px-3 py-2 font-medium">Para birimi</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border/40">
              {rows.map(row => (
                <tr key={row.market}>
                  <td className="px-3 py-3 font-medium text-foreground">{row.label}</td>
                  <td className="px-3 py-3 text-secondary-text">
                    {row.scope === 'bist100_constituents'
                      ? 'BIST100 üyelik listesi · 100 hisse'
                      : `Tek örnek: ${row.ticker}`}
                  </td>
                  <td className="px-3 py-3">
                    <Badge variant={row.state === 'not_loaded' ? 'default' : 'warning'}>
                      {STATUS[row.state]}
                    </Badge>
                    {row.sampleStatus && row.sampleStatus !== 'analyzed' ? (
                      <div className="mt-1 text-xs text-warning">{row.sampleStatus}</div>
                    ) : null}
                  </td>
                  <td className="px-3 py-3 text-secondary-text">
                    {row.asOf ?? '—'} / {row.lastSession ?? '—'}
                  </td>
                  <td className="px-3 py-3 text-secondary-text">
                    {row.state === 'not_loaded' ? '—' : `${row.checked} / ${row.analyzed}`}
                  </td>
                  <td className="px-3 py-3 text-secondary-text">{row.currency}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <p className="text-xs text-muted-text">
          Eski tarihli sonuçlar kendiliğinden güncellenmez. Bir piyasanın gerçek zamanlı veri kalitesi
          ve tüm hisse evreni, ayrıca doğrulanmış canlı/veri-kapsama raporu gerektirir.
          Bu ekran Yahoo sorgusu, AI çalıştırma, veri yükleme, SQLite yazma veya emir gönderme işlemi yapmaz.
        </p>
      </div>
    </Card>
  );
};
