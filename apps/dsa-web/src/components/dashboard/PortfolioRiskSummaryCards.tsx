import { AlertTriangle, CheckCircle2, Clock3, Database, ShieldAlert, ShieldCheck } from 'lucide-react';
import type { PortfolioRiskResponse, PortfolioSnapshotResponse } from '../../types/portfolio';

const number = (value: number | undefined | null): string =>
  typeof value === 'number' && Number.isFinite(value)
    ? new Intl.NumberFormat('tr-TR', { maximumFractionDigits: 2 }).format(value)
    : '—';
const percent = (value: number | null | undefined): string =>
  typeof value === 'number' && Number.isFinite(value)
    ? new Intl.NumberFormat('tr-TR', { minimumFractionDigits: 1, maximumFractionDigits: 2 }).format(value) + '%'
    : '—';

type PortfolioProps = {
  snapshot: PortfolioSnapshotResponse | null;
  loading: boolean;
  failed: boolean;
};

export function PortfolioSummaryContent({ snapshot, loading, failed }: PortfolioProps) {
  const data = !loading && !failed ? snapshot : null;
  const validEquity = data && Number.isFinite(data.totalEquity) ? data.totalEquity : null;
  const validCash = data && Number.isFinite(data.totalCash) ? data.totalCash : null;
  const validHoldings = data && Number.isFinite(data.totalMarketValue) ? data.totalMarketValue : null;
  const partial = Boolean(data && (data.fxStale || (data.dataQuality && data.dataQuality !== 'ok') || (data.limitations?.length ?? 0) > 0));
  const cashPct = validEquity !== null && validCash !== null && validEquity > 0 && validCash >= 0
    ? Math.min(100, validCash / validEquity * 100) : null;
  return (
    <div data-testid="portfolio-summary-content" className="min-w-0">
      <p className="text-[11px] font-semibold text-[#7e92ad]">Toplam portföy özsermayesi</p>
      <div className="mt-1 flex flex-wrap items-baseline gap-2">
        <strong className="break-words text-2xl font-extrabold tabular-nums text-[#193a67]">{number(validEquity)}</strong>
        {data && <span className="text-xs font-semibold text-[#7290b0]">{data.currency}</span>}
      </div>
      {loading || failed || !data ? (
        <div role="status" className="mt-4 flex min-h-12 items-center gap-2 rounded-xl bg-[#f5f9ff] px-3 text-xs text-[#7187a4]">
          <Database className="h-4 w-4 shrink-0" />
          {loading ? 'Portföy bilgileri yükleniyor…' : failed ? 'Portföy kaynağına erişilemedi.' : 'Portföy kaydı bulunamadı.'}
        </div>
      ) : (
        <>
          <div className="mt-4 grid grid-cols-2 gap-2.5">
            <div className="min-w-0 rounded-xl bg-[#f4f8fe] p-3">
              <p className="text-[11px] text-[#7f93af]">Nakit</p>
              <p className="mt-1 break-words text-sm font-bold tabular-nums text-[#24446f]">{number(validCash)}</p>
            </div>
            <div className="min-w-0 rounded-xl bg-[#f4f8fe] p-3">
              <p className="text-[11px] text-[#7f93af]">Pozisyon değeri</p>
              <p className="mt-1 break-words text-sm font-bold tabular-nums text-[#24446f]">{number(validHoldings)}</p>
            </div>
          </div>
          {cashPct !== null && (
            <div className="mt-3" aria-label="Nakit özsermaye oranı">
              <div className="mb-1 flex items-center justify-between text-[11px] text-[#7389a8]">
                <span>Nakit / özsermaye</span><span className="font-semibold">{percent(cashPct)}</span>
              </div>
              <div className="h-2 overflow-hidden rounded-full bg-[#dceafa]">
                <div className="h-full rounded-full bg-[#3387da]" style={{ width: cashPct + '%' }} />
              </div>
            </div>
          )}
          <div className="mt-3 flex flex-wrap items-center gap-2 text-[11px] text-[#7c90ab]">
            <span>{data.accountCount} hesap</span><span>•</span><span>Değerleme: {data.asOf}</span>
          </div>
          {partial && (
            <div role="status" className="mt-3 flex items-start gap-2 rounded-lg bg-[#fff6e8] p-2 text-[11px] text-[#936424]">
              <AlertTriangle className="mt-0.5 h-3.5 w-3.5 shrink-0" />
              Kısmi veya gecikmeli değerleme: rakamlar kesin güncel tutar olmayabilir.
            </div>
          )}
        </>
      )}
    </div>
  );
}

type RiskProps = {
  risk: PortfolioRiskResponse | null;
  loading: boolean;
  failed: boolean;
};
type RiskMetricProps = { label: string; value: number | null | undefined; alert: boolean | undefined };

function RiskMetric({ label, value, alert }: RiskMetricProps) {
  const usable = typeof value === 'number' && Number.isFinite(value);
  const severity = alert ? '#e8a239' : '#3284d7';
  const width = usable ? Math.min(100, Math.max(0, Math.abs(value))) : 0;
  return (
    <div className="mt-3">
      <div className="flex items-center justify-between gap-2 text-[11px]">
        <span className="text-[#657f9f]">{label}</span>
        <span className="font-bold tabular-nums text-[#29466b]">{usable ? percent(value) : 'Veri yok'}</span>
      </div>
      {usable ? (
        <div role="progressbar" aria-label={label} aria-valuemin={0} aria-valuemax={100}
          aria-valuenow={width} className="mt-1.5 h-2 overflow-hidden rounded-full bg-[#e5edf8]">
          <div className="h-full rounded-full" style={{ width: width + '%', backgroundColor: severity }} />
        </div>
      ) : <p className="mt-1 text-[10px] text-[#98a8bc]">Hesaplanabilir risk ölçümü yok.</p>}
    </div>
  );
}

export function RiskSummaryContent({ risk, loading, failed }: RiskProps) {
  const data = !loading && !failed ? risk : null;
  const alert = Boolean(data && (data.concentration?.alert || data.drawdown?.alert || data.stopLoss?.nearAlert));
  return (
    <div data-testid="risk-summary-content" className="min-w-0">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <span className="flex items-center gap-1.5 text-[11px] text-[#7990ac]">
          {data && !alert ? <ShieldCheck className="h-3.5 w-3.5" /> : <ShieldAlert className="h-3.5 w-3.5" />}
          {loading ? 'Kontroller yükleniyor…' : failed || !data ? 'Risk verisi yok'
            : alert ? 'Limit uyarısı mevcut' : 'Mevcut ölçümlerde limit uyarısı yok'}
        </span>
        {data && <span className={'rounded-full px-2 py-1 text-[10px] font-semibold ' +
          (alert ? 'bg-[#fff3dc] text-[#99681d]' : 'bg-[#eaf5fd] text-[#2467a2]')}>
          {alert ? 'Uyarı' : 'İzleniyor'}
        </span>}
      </div>
      {data ? (
        <>
          <RiskMetric label="En büyük pozisyon ağırlığı" value={data.concentration?.topWeightPct} alert={data.concentration?.alert} />
          <RiskMetric label="Güncel düşüş" value={data.drawdown?.currentDrawdownPct} alert={data.drawdown?.alert} />
          <div className="mt-4 flex items-center justify-between rounded-xl bg-[#f4f8fe] px-3 py-2.5 text-xs">
            <span className="text-[#6782a0]">Tetiklenen zarar-kes kayıtları</span>
            <strong className="text-[#234e7d]">{number(data.stopLoss?.triggeredCount)}</strong>
          </div>
          <p className="mt-3 flex items-center gap-1 text-[10px] text-[#8a9db4]">
            <Clock3 className="h-3 w-3" /> Risk değerlendirme tarihi: {data.asOf ?? 'Bilinmiyor'}
          </p>
          <p className="mt-1 text-[10px] text-[#8a9db4]">Bu özet kesin güvenli işlem onayı anlamına gelmez.</p>
        </>
      ) : (
        <p role="status" className="mt-4 rounded-xl bg-[#f5f9ff] px-3 py-4 text-xs text-[#7187a4]">
          {loading ? 'Risk ölçümleri yükleniyor…' : failed ? 'Risk servisine erişilemedi.' : 'Risk kaydı bulunamadı.'}
        </p>
      )}
    </div>
  );
}
