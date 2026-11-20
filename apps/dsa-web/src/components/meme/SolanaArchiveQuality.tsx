/**
 * Fixed, independently audited GitHub Actions observation summary.
 *
 * IMPORTANT: this is a dated snapshot, NOT a live data source, approval for
 * paper trading, or a market scanner. Updating the snapshot requires a new
 * read-only GitHub audit and a code review.
 */
const SNAPSHOT = {
  auditDate: '20 Kasım 2026',
  auditRunId: '44791912581',
  blockedAssessments: 18,
  watchAssessments: 0,
  captures: [
    { runId: '44779967482', valid: 6, missing: 0, quality: 'Eksiksiz veri' },
    { runId: '44777830658', valid: 3, missing: 3, quality: 'Eksik veri' },
  ],
} as const;

const totalValid = SNAPSHOT.captures.reduce((sum, capture) => sum + capture.valid, 0);
const totalMissing = SNAPSHOT.captures.reduce((sum, capture) => sum + capture.missing, 0);

function SummaryMetric({ label, value, testId }: { label: string; value: number; testId: string }) {
  return (
    <div className="rounded-lg border border-border/75 bg-surface px-3 py-3">
      <dt className="text-xs text-secondary-text">{label}</dt>
      <dd data-testid={testId} className="mt-1 text-xl font-semibold text-foreground">{value}</dd>
    </div>
  );
}

export default function SolanaArchiveQuality() {
  return (
    <section aria-labelledby="solana-archive-quality-heading" className="rounded-xl border border-border bg-card p-4" data-testid="solana-archive-quality">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h2 id="solana-archive-quality-heading" className="text-lg font-semibold text-foreground">
            Solana arşiv veri kalitesi
          </h2>
          <p className="mt-1 text-sm text-secondary-text">
            {SNAPSHOT.auditDate} tarihinde gerçek GitHub Actions arşivleriyle doğrulanmış sabit kayıt.
            Anlık veri değildir ve otomatik güncellenmez.
          </p>
        </div>
        <span className="rounded-full border border-border px-3 py-1 text-xs font-semibold text-secondary-text">
          Salt okunur · Eksik veri
        </span>
      </div>

      <dl className="mt-4 grid grid-cols-2 gap-3 md:grid-cols-4">
        <SummaryMetric label="Geçerli fiyat gözlemi" value={totalValid} testId="archive-quality-valid" />
        <SummaryMetric label="Eksik fiyat gözlemi" value={totalMissing} testId="archive-quality-missing" />
        <SummaryMetric label="Engellenen strateji değerlendirmesi" value={SNAPSHOT.blockedAssessments} testId="archive-quality-blocked" />
        <SummaryMetric label="İzleme onayı" value={SNAPSHOT.watchAssessments} testId="archive-quality-watch" />
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
            {SNAPSHOT.captures.map((capture) => (
              <tr key={capture.runId} className="border-b border-border/60">
                <td className="px-2 py-3">
                  <a
                    href={`https://github.com/ebbottr-cyber/ebbotcyber/actions/runs/${capture.runId}`}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="font-medium text-primary underline-offset-2 hover:underline"
                  >
                    #{capture.runId}
                  </a>
                </td>
                <td className="px-2 py-3 text-foreground">{capture.valid}/{capture.valid + capture.missing}</td>
                <td className="px-2 py-3 text-secondary-text">{capture.quality}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="mt-4 space-y-2 text-sm text-secondary-text">
        <p>
          Geçerli fiyat, güvenli coin veya alım-satım sinyali anlamına gelmez.
          Güvenlik bilgisi belirsizse strateji engelleri korunur.
        </p>
        <p>
          Bu kısa kayıtlar kârlılık göstermez. Doğrulanmış sanal performans, gerçek işlem,
          otomatik tarama ve kendiliğinden öğrenme etkin değildir.
        </p>
        <p className="text-xs text-muted-text">
          Doğrulama kaynağı:{' '}
          <a
            href={`https://github.com/ebbottr-cyber/ebbotcyber/actions/runs/${SNAPSHOT.auditRunId}`}
            target="_blank"
            rel="noopener noreferrer"
            className="text-primary underline-offset-2 hover:underline"
          >
            GitHub Actions #{SNAPSHOT.auditRunId}
          </a>
          . Yeni arşivler bu sabit özeti kendiliğinden değiştirmez.
        </p>
      </div>
    </section>
  );
}
