import { useEffect, useState } from 'react';
import { parseReviewedSolanaQuality, type ReviewedSolanaQuality } from './qualityReport';

const REPORT_PATH = '/solana-quality-reviewed.json';
const GITHUB_RUN = 'https://github.com/ebbottr-cyber/ebbotcyber/actions/runs/';

type ReportState =
  | { status: 'loading'; report: null }
  | { status: 'unavailable'; report: null }
  | { status: 'ready'; report: ReviewedSolanaQuality };

function SummaryMetric({ label, value, testId }: { label: string; value: number; testId: string }) {
  return (
    <div className="rounded-lg border border-border/75 bg-surface px-3 py-3">
      <dt className="text-xs text-secondary-text">{label}</dt>
      <dd data-testid={testId} className="mt-1 text-xl font-semibold text-foreground">{value}</dd>
    </div>
  );
}

/** Read only the same-origin, PR-reviewed JSON. Never contact GitHub with a browser token. */
export default function SolanaArchiveQuality() {
  const [state, setState] = useState<ReportState>({ status: 'loading', report: null });

  useEffect(() => {
    let active = true;
    const controller = new AbortController();
    const load = async () => {
      try {
        const response = await fetch(REPORT_PATH, {
          method: 'GET', cache: 'no-store', credentials: 'same-origin', signal: controller.signal,
        });
        if (!response.ok) throw new Error('Quality file unavailable');
        const raw = await response.text();
        if (raw.length > 12_000) throw new Error('Quality file too large');
        const report = parseReviewedSolanaQuality(JSON.parse(raw) as unknown);
        if (active) setState({ status: 'ready', report });
      } catch {
        // Never retain a previous green snapshot when a report is missing, malformed or unsafe.
        if (active) setState({ status: 'unavailable', report: null });
      }
    };
    void load();
    return () => { active = false; controller.abort(); };
  }, []);

  const { report } = state;
  const auditDate = report
    ? new Intl.DateTimeFormat('tr-TR', {
      day: 'numeric', month: 'long', year: 'numeric', timeZone: 'UTC',
    }).format(new Date(report.audited_at_utc))
    : null;

  return (
    <section aria-labelledby="solana-archive-quality-heading" className="rounded-xl border border-border bg-card p-4" data-testid="solana-archive-quality">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h2 id="solana-archive-quality-heading" className="text-lg font-semibold text-foreground">
            Solana arşiv veri kalitesi
          </h2>
          <p className="mt-1 text-sm text-secondary-text">
            GitHub Actions sonuçlarından hazırlanmış, kod incelemesiyle yayımlanan rapor.
            Anlık veri değildir ve otomatik tarama yapmaz.
          </p>
        </div>
        <span className="rounded-full border border-border px-3 py-1 text-xs font-semibold text-secondary-text">
          Salt okunur · {report?.quality_result === 'complete_captures'
            ? 'Gözlemler eksiksiz'
            : report ? 'Eksik veri' : 'Henüz doğrulanmadı'}
        </span>
      </div>

      {state.status === 'loading' && (
        <p role="status" className="mt-4 text-sm text-secondary-text">İncelenmiş kalite raporu yükleniyor…</p>
      )}
      {state.status === 'unavailable' && (
        <p role="alert" className="mt-4 text-sm text-danger">
          İncelenmiş kalite raporu okunamadı veya güvenlik kontrolünü geçemedi.
          Fiyat, risk ya da performans sonucu gösterilmiyor.
        </p>
      )}
      {report && (
        <>
          <p className="mt-3 text-xs text-muted-text">
            Rapor tarihi: {auditDate} · {report.capture_count} kayıt · canlı veri değil
          </p>
          <dl className="mt-4 grid grid-cols-2 gap-3 md:grid-cols-4">
            <SummaryMetric label="Geçerli fiyat gözlemi" value={report.total_priced_rows} testId="archive-quality-valid" />
            <SummaryMetric label="Eksik fiyat gözlemi" value={report.total_missing_rows} testId="archive-quality-missing" />
            <SummaryMetric label="Engellenen strateji değerlendirmesi" value={report.blocked_assessments} testId="archive-quality-blocked" />
            <SummaryMetric label="İzleme onayı (işlem izni değil)" value={report.watch_assessments} testId="archive-quality-watch" />
          </dl>
          <div className="mt-4 overflow-x-auto">
            <table className="w-full min-w-[410px] text-left text-sm">
              <caption className="mb-2 text-left text-sm font-semibold text-foreground">Kaynak arşivler</caption>
              <thead className="border-b border-border text-xs text-muted-text">
                <tr>
                  <th scope="col" className="px-2 py-2">GitHub çalışması</th>
                  <th scope="col" className="px-2 py-2">Fiyat gözlemi</th>
                  <th scope="col" className="px-2 py-2">Kalite</th>
                </tr>
              </thead>
              <tbody>
                {report.captures.map((capture) => (
                  <tr key={capture.run_id} className="border-b border-border/60">
                    <td className="px-2 py-3">
                      <a href={GITHUB_RUN + capture.run_id} target="_blank" rel="noopener noreferrer" className="font-medium text-primary underline-offset-2 hover:underline">
                        #{capture.run_id}
                      </a>
                    </td>
                    <td className="px-2 py-3 text-foreground">{capture.priced_rows}/{capture.priced_rows + capture.missing_rows}</td>
                    <td className="px-2 py-3 text-secondary-text">{capture.result === 'passed' ? 'Eksiksiz veri' : 'Eksik / sorunlu veri'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <p className="mt-4 text-xs text-muted-text">
            Denetim çalışması:{' '}
            <a href={GITHUB_RUN + report.audit_run_id} target="_blank" rel="noopener noreferrer" className="text-primary underline-offset-2 hover:underline">
              GitHub Actions #{report.audit_run_id}
            </a>
            . Yeni rapor yalnızca incelenmiş dosya güncellenirse gösterilir; doğrudan GitHub arşivi sorgulanmaz.
          </p>
        </>
      )}
      <div className="mt-4 space-y-2 text-sm text-secondary-text">
        <p>
          Geçerli fiyat, güvenli coin veya alım-satım sinyali anlamına gelmez.
          Güvenlik bilgisi belirsizse strateji engelleri korunur.
        </p>
        <p>
          Bu kısa kayıtlar kârlılık göstermez. Doğrulanmış sanal performans, gerçek işlem,
          otomatik tarama ve kendiliğinden öğrenme bu raporla etkinleştirilmez.
        </p>
      </div>
    </section>
  );
}
