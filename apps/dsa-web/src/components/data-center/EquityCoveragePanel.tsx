import { useEffect, useState } from 'react';
import { dataCapabilityApi } from '../../api/dataCapability';
import type { EquityCoverageReport } from '../../types/equityCoverage';

const MARKET_NAMES: Array<['tr' | 'us' | 'de' | 'hk', string]> = [
  ['tr', 'Türkiye / BIST'],
  ['us', 'ABD'],
  ['de', 'Almanya / Xetra'],
  ['hk', 'Hong Kong'],
];

function count(value: number | undefined): string {
  return value === undefined ? '—' : new Intl.NumberFormat('tr-TR').format(value);
}

export default function EquityCoveragePanel() {
  const [report, setReport] = useState<EquityCoverageReport | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);

  useEffect(() => {
    let active = true;
    void dataCapabilityApi.getEquityCoverage().then((data) => {
      if (active) setReport(data);
    }).catch(() => {
      if (active) setError(true);
    }).finally(() => {
      if (active) setLoading(false);
    });
    return () => { active = false; };
  }, []);

  return (
    <section aria-label="Hisse veri kapsamı" className="rounded-xl border border-border/75 bg-card p-4">
      <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
        <h2 className="text-base font-semibold text-foreground">Hisse veri eksiksizliği</h2>
        <span className="rounded-full border border-warning/40 px-2 py-1 text-xs font-medium text-warning">
          Yalnızca denetim · İşlem kapalı
        </span>
      </div>
      <p className="mb-3 text-sm text-secondary-text">
        Kayıtlı hisse adayları, gerçek OHLCV kanıtı ve eksikler. Liste ve fiyat sağlayıcısının doğruluğu
        ayrıca onaylanmadan bu rakamlar işlem yapılabilirlik anlamına gelmez.
      </p>
      {loading && <p role="status" className="text-sm text-secondary-text">Veri kapsam raporu okunuyor…</p>}
      {!loading && error && (
        <p role="alert" className="text-sm text-danger">
          Veri kapsam raporu alınamadı. Sunucu ve oturum durumunu kontrol edin.
        </p>
      )}
      {!loading && !error && report?.status === 'unavailable' && (
        <p role="status" className="text-sm text-warning">
          {report.reason === 'administrator_auth_required'
            ? 'Güvenlik nedeniyle yönetici kimlik doğrulaması kapalıyken yerel piyasa veri kapsamı gösterilmez. Önce yönetici oturumunu etkinleştirin.'
            : 'Henüz güvenilir, yerel bir kapsam raporu tanımlı değil. Bu durum sıfır hisse veya sıfır fiyat bulunduğu anlamına gelmez. Yönetici önce çevrimdışı denetimi çalıştırıp rapor yolunu EBBOT_EQUITY_COVERAGE_REPORT_PATH ile yapılandırmalıdır.'}
        </p>
      )}
      {!loading && !error && report && report.status !== 'unavailable' && (
        <>
          <p className="mb-3 text-xs text-secondary-text">
            Son rapor (UTC): {report.as_of_utc_date ?? 'Bilinmiyor'} ·
            {report.status === 'stale' ? ' Rapor eski, yenileme gerekli.' : ' Kaynak inceleme bekliyor.'}
          </p>
          <div className="overflow-x-auto">
            <table className="w-full min-w-[630px] text-left text-sm">
              <thead className="border-b border-border/70 text-secondary-text">
                <tr>
                  <th scope="col" className="px-3 py-2 font-medium">Piyasa</th>
                  <th scope="col" className="px-3 py-2 font-medium">Aday kayıt</th>
                  <th scope="col" className="px-3 py-2 font-medium">OHLCV bulunan</th>
                  <th scope="col" className="px-3 py-2 font-medium">Geçmişi yetersiz</th>
                  <th scope="col" className="px-3 py-2 font-medium">OHLCV eksik</th>
                  <th scope="col" className="px-3 py-2 font-medium">Eski OHLCV</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border/50">
                {MARKET_NAMES.map(([market, label]) => {
                  const row = report.markets[market];
                  return (
                    <tr key={market}>
                      <th scope="row" className="px-3 py-2 font-medium text-foreground">{label}</th>
                      <td className="px-3 py-2 text-secondary-text">{count(row?.candidate_instruments)}</td>
                      <td className="px-3 py-2 text-secondary-text">{count(row?.with_any_ohlcv)}</td>
                      <td className="px-3 py-2 text-secondary-text">{count(row?.insufficient_history_count)}</td>
                      <td className="px-3 py-2 text-secondary-text">{count(row?.missing_ohlcv_count)}</td>
                      <td className="px-3 py-2 text-secondary-text">{count(row?.stale_ohlcv_count)}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
          <p className="mt-3 text-xs text-warning">
            Bu rapor eksiksiz borsa kotasyonu, lisanslı fiyat erişimi veya Türkiye'den alım-satım izni kanıtlamaz.
            Gerçek ve sanal emirler kapalıdır.
          </p>
        </>
      )}
    </section>
  );
}
