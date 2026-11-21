import { useEffect, useState } from 'react';
import { dataCapabilityApi } from '../../api/dataCapability';
import type { BistIdentityCounts, BistIdentitySummary } from '../../types/bistIdentity';

function count(value: number | null | undefined): string {
  return value == null ? '—' : new Intl.NumberFormat('tr-TR').format(value);
}

const CATEGORIES: Array<{ label: string; key: keyof BistIdentityCounts; note: string }> = [
  { label: 'KAP şirket adayı', key: 'kap_candidate_count', note: 'KAP kaynağına göre; aktif hisse değildir' },
  { label: 'BIST XIST referansı', key: 'exchange_reference_count', note: 'Operatörün sağladığı işlem kayıtları' },
  { label: 'BIST aktif bildirilen', key: 'exchange_active_count', note: 'Borsa tarafından bağımsız doğrulanmadı' },
  { label: 'Durdurulmuş / kotasyondan çıkmış', key: 'exchange_halted_or_delisted_count', note: 'Aktif pay sayısına katılmaz' },
  { label: 'KAP ve BIST eşleşen aktif', key: 'matched_active_kap_exchange_count', note: 'Yalnızca iki dosya arasındaki eşleşme' },
  { label: 'KAP listesinde olup BIST listesinde yok', key: 'kap_not_in_exchange_count', note: 'İki kaynak arasında fark var' },
  { label: 'BIST listesinde olup KAP listesinde yok', key: 'exchange_not_in_kap_count', note: 'Kaynak farkı ayrıca araştırılmalı' },
  { label: 'Aktif, sağlayıcı kodu eşlemesi eksik', key: 'active_without_declared_provider_mapping_count', note: 'Beyan edilmiş sağlayıcı eşleşmesi yok' },
  { label: 'Verilen dosyada OHLCV bulunan aktif', key: 'active_with_ohlcv_in_supplied_file_count', note: 'Fiyatların geçerli lisansı hâlâ doğrulanmadı' },
  { label: 'Verilen dosyada OHLCV bulunmayan aktif', key: 'active_without_ohlcv_in_supplied_file_count', note: 'Dosya verilmemişse sayı bilinmez' },
];

export default function BistIdentityPanel() {
  const [report, setReport] = useState<BistIdentitySummary | null>(null);
  const [loading, setLoading] = useState(true);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    let active = true;
    void dataCapabilityApi.getBistIdentitySummary()
      .then((value) => { if (active) setReport(value); })
      .catch(() => { if (active) setFailed(true); })
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, []);

  return (
    <section aria-label="BIST KAP ve işlem kaydı denetimi" className="rounded-xl border border-border/75 bg-card p-4">
      <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
        <h2 className="text-base font-semibold text-foreground">BIST · KAP ve işlem kaydı eşleştirmesi</h2>
        <span className="rounded-full border border-warning/40 px-2 py-1 text-xs font-medium text-warning">
          Kaynak doğrulaması bekliyor
        </span>
      </div>
      <p className="mb-3 text-sm text-secondary-text">
        KAP şirket adayı ile XIST işlem kaydı aynı şey değildir. Sayılar yalnızca yerel kaynak dosyalarının
        karşılaştırmasıdır; gerçek borsa kotasyonu, lisanslı fiyat veya işlem yapılabilirlik kanıtı değildir.
      </p>
      {loading && <p role="status" className="text-sm text-secondary-text">BIST eşleştirme raporu okunuyor…</p>}
      {!loading && failed && (
        <p role="alert" className="text-sm text-danger">
          BIST raporu okunamadı. Sistem veya oturum durumunu kontrol edin.
        </p>
      )}
      {!loading && !failed && report?.status === 'unavailable' && (
        <p role="status" className="text-sm text-warning">
          {report.reason === 'administrator_auth_required'
            ? 'Yönetici kimlik doğrulaması kapalı; yerel BIST raporu güvenlik nedeniyle gösterilmiyor.'
            : report.reason === 'bist_reference_files_missing'
              ? 'KAP veya BIST işlem referansı eksik. Aktif hisse sayısı ve veri kapsamı bilinmiyor.'
              : 'BIST eşleştirme raporu bulunamadı veya geçerli değil. EBBOT_BIST_IDENTITY_REPORT_PATH ile yerel rapor tanımlanmalı; bilinmeyen değerler sıfır sayılmaz.'}
        </p>
      )}
      {!loading && !failed && report && report.status !== 'unavailable' && report.counts && (
        <>
          <p className="mb-3 text-xs text-secondary-text">
            Son yerel rapor (UTC): {report.as_of_utc_date ?? 'Bilinmiyor'} ·{' '}
            {report.status === 'stale' ? 'Kaynak eski, yeniden doğrulama gerekli.' : 'Bağımsız kaynak onayı bekliyor.'}
          </p>
          <div className="overflow-x-auto">
            <table className="w-full min-w-[580px] text-sm">
              <thead className="border-b border-border/70 text-secondary-text">
                <tr>
                  <th scope="col" className="px-3 py-2 text-left font-medium">BIST denetim ölçütü</th>
                  <th scope="col" className="px-3 py-2 text-right font-medium">Kayıt</th>
                  <th scope="col" className="px-3 py-2 text-left font-medium">Açıklama</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border/50">
                {CATEGORIES.map(({ label, key, note }) => (
                  <tr key={key}>
                    <th scope="row" className="px-3 py-2 text-left font-medium text-foreground">{label}</th>
                    <td className="px-3 py-2 text-right font-mono text-secondary-text">
                      {count(report.counts?.[key])}
                    </td>
                    <td className="px-3 py-2 text-secondary-text">{note}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {!report.prices_file_supplied && (
            <p role="status" className="mt-2 text-xs text-warning">
              Gerçek OHLCV dosyası bu denetime verilmedi; fiyat kapsamı bilinmiyor.
            </p>
          )}
          <p className="mt-3 text-xs text-warning">
            ISIN kontrol basamağı, iki listede eşleşme ve fiyat satırı bulunması lisans veya işlem onayı değildir.
            Gerçek ve sanal emirler kapalıdır.
          </p>
        </>
      )}
    </section>
  );
}
