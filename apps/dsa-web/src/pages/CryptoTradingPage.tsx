import type React from 'react';
import { useEffect, useState } from 'react';
import { Activity, ArrowRight, Bot, CircleAlert, Database, ExternalLink, Layers, LockKeyhole, RefreshCw, ShieldCheck, Wallet } from 'lucide-react';
import { Link } from 'react-router-dom';
import { cryptoOfficeApi, isObject, type CryptoOfficeDashboard } from '../api/cryptoOffice';
import { CryptoSpotPanel } from '../components/crypto/CryptoSpotPanel';
import { CryptoFuturesPanel } from '../components/crypto/CryptoFuturesPanel';
import { CryptoResearchPanel } from '../components/crypto/CryptoResearchPanel';
import { CryptoRiskPanel } from '../components/crypto/CryptoRiskPanel';

type SectionId =
  | 'overview' | 'spot' | 'futures' | 'analysis' | 'signals'
  | 'agents' | 'scanner' | 'positions' | 'paper' | 'backtest'
  | 'risk' | 'portfolio' | 'performance' | 'history' | 'health';

const SECTIONS: Array<{ id: SectionId; label: string }> = [
  { id: 'overview', label: 'Kripto Genel Bakış' },
  { id: 'spot', label: 'Spot Piyasası' },
  { id: 'futures', label: 'Futures Piyasası' },
  { id: 'analysis', label: 'AI Analiz Merkezi' },
  { id: 'signals', label: 'AI Sinyalleri' },
  { id: 'agents', label: 'Çoklu Ajan Merkezi' },
  { id: 'scanner', label: 'Piyasa Tarayıcı' },
  { id: 'positions', label: 'Açık Pozisyonlar' },
  { id: 'paper', label: 'Paper Trading' },
  { id: 'backtest', label: 'Backtest' },
  { id: 'risk', label: 'Risk Yönetimi' },
  { id: 'portfolio', label: 'Portföy Analizi' },
  { id: 'performance', label: 'Performans Raporları' },
  { id: 'history', label: 'İşlem Geçmişi' },
  { id: 'health', label: 'Sistem Sağlığı' },
];

function formatted(value: unknown, digits = 2): string {
  if (typeof value !== 'number' || !Number.isFinite(value)) return 'Veri yok';
  return new Intl.NumberFormat('tr-TR', { maximumFractionDigits: digits }).format(value);
}

function field(record: unknown, key: string): unknown {
  return isObject(record) ? record[key] : undefined;
}

function asRows(value: unknown): Record<string, unknown>[] {
  return Array.isArray(value) ? value.filter(isObject) : [];
}

function Metric({ title, value, note }: { title: string; value: string; note?: string }) {
  return (
    <div className="rounded-2xl border border-border bg-card p-4 shadow-sm">
      <div className="text-xs font-medium text-muted-text">{title}</div>
      <div className="mt-3 break-words text-xl font-extrabold tracking-tight text-foreground">{value}</div>
      {note ? <div className="mt-2 text-xs text-muted-text">{note}</div> : null}
    </div>
  );
}

function ReadOnlySection({ title, value, description }: {
  title: string; value: unknown; description?: string;
}) {
  const available = isObject(value) || Array.isArray(value);
  return (
    <section className="rounded-2xl border border-border bg-card p-4 shadow-sm">
      <h3 className="text-sm font-bold text-foreground">{title}</h3>
      {description ? <p className="mt-1 text-xs leading-5 text-muted-text">{description}</p> : null}
      {available ? (
        <pre className="mt-3 max-h-[380px] overflow-auto whitespace-pre-wrap break-words rounded-xl bg-surface p-3 font-mono text-xs leading-5 text-secondary-text">
          {JSON.stringify(value, null, 2)}
        </pre>
      ) : (
        <p className="mt-3 text-sm text-muted-text">Bu alan için doğrulanmış veri bulunamadı.</p>
      )}
    </section>
  );
}

const Pending: React.FC<{ label: string }> = ({ label }) => (
  <section className="rounded-2xl border border-border bg-card p-6">
    <div className="flex items-center gap-2 text-foreground"><CircleAlert className="h-4 w-4" /><strong>{label}</strong></div>
    <p className="mt-3 text-sm leading-6 text-muted-text">
      Bu bölüm henüz EBBot API'sine bağlanmadı. Gerçek veri ve güvenlik testleri tamamlanana kadar
      simülasyon sonuçları veya işlem düğmeleri gösterilmeyecek.
    </p>
  </section>
);

function PositionTable({ positions }: { positions: Record<string, unknown>[] }) {
  if (!positions.length) {
    return <p className="py-4 text-sm text-muted-text">Kaydedilmiş açık Paper pozisyon bulunamadı.</p>;
  }
  return <div className="overflow-x-auto">
    <table className="w-full min-w-[560px] text-left text-sm">
      <thead className="text-xs text-muted-text"><tr>
        <th className="border-b border-border px-3 py-3">Piyasa</th>
        <th className="border-b border-border px-3 py-3">Sembol</th>
        <th className="border-b border-border px-3 py-3">Yön</th>
        <th className="border-b border-border px-3 py-3">Miktar</th>
        <th className="border-b border-border px-3 py-3">Fiyat</th>
      </tr></thead>
      <tbody>{positions.map((position, index) => (
        <tr key={String(position.id ?? position.symbol ?? 'pos') + ':' + index}>
          <td className="border-b border-border/60 px-3 py-3">{String(position.market ?? '—')}</td>
          <td className="border-b border-border/60 px-3 py-3 font-semibold">{String(position.symbol ?? '—')}</td>
          <td className="border-b border-border/60 px-3 py-3">{String(position.side ?? '—')}</td>
          <td className="border-b border-border/60 px-3 py-3">{formatted(position.quantity)}</td>
          <td className="border-b border-border/60 px-3 py-3">{formatted(position.mark_price ?? position.current_price)}</td>
        </tr>
      ))}</tbody>
    </table>
  </div>;
}

const CryptoTradingPage: React.FC = () => {
  const [active, setActive] = useState<SectionId>('overview');
  const [data, setData] = useState<CryptoOfficeDashboard | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [requestId, setRequestId] = useState(0);

  useEffect(() => {
    let mounted = true;
    const load = async () => {
      try {
        const next = await cryptoOfficeApi.dashboard();
        if (mounted) { setData(next); setError(''); }
      } catch (reason) {
        if (mounted) {
          // Never retain old balances after a failed or unsafe contract refresh.
          setData(null);
          const status = isObject(reason) && isObject(reason.response) ? reason.response.status : undefined;
          setError(status === 403
            ? 'Güvenlik için EBBot yönetici girişini etkinleştirmeniz gerekiyor.'
            : status === 401
              ? 'Yönetici oturumu gerekli.'
              : status === 503
                ? 'Kripto servisi yapılandırılmamış veya erişilemiyor.'
                : 'Kripto verileri güvenli biçimde doğrulanamadı. Fiyatlar ve bakiyeler gizlendi.');
        }
      } finally {
        if (mounted) setLoading(false);
      }
    };
    void load();
    const interval = window.setInterval(() => void load(), 30_000);
    return () => { mounted = false; window.clearInterval(interval); };
  }, [requestId]);

  const combined = field(data?.portfolio, 'combined');
  const valuationComplete = field(combined, 'valuation_complete') === true;
  const equity = field(combined, 'equity');
  const positions = asRows(field(data?.portfolio, 'open_positions'));
  const performanceDaily = field(data?.performance, 'daily');
  const performanceWeekly = field(data?.performance, 'weekly');
  const performanceMonthly = field(data?.performance, 'monthly');
  const pnl = (value: unknown): string => formatted(field(value, 'net_pnl') ?? field(value, 'pnl'));
  const current = SECTIONS.find(section => section.id === active)?.label ?? SECTIONS[0].label;

  const body = () => {
    if (active === 'spot') return <CryptoSpotPanel />;
    if (active === 'futures') return <CryptoFuturesPanel paperSnapshot={field(data?.portfolio, 'futures')} />;
    if (active === 'risk') return <CryptoRiskPanel />;
    if (active === 'analysis' || active === 'signals' || active === 'agents') {
      return <CryptoResearchPanel view={active} />;
    }
    if (!data) return null;
    switch (active) {
      case 'overview':
        return <div className="grid gap-4 xl:grid-cols-2">
          <ReadOnlySection title="Zorunlu risk kontrolü" value={data.risk}
            description="Kripto servisi risk raporu. Henüz EBBot işlem motoruna yürütme yetkisi verilmedi." />
          <ReadOnlySection title="Sistem operasyonları" value={data.operations}
            description="Scheduler, veri akışı ve servis operasyon bilgileri." />
        </div>;


      case 'positions':
        return <section className="rounded-2xl border border-border bg-card p-4">
          <h3 className="font-semibold">Açık sanal pozisyonlar ({positions.length})</h3>
          <PositionTable positions={positions} />
        </section>;
      case 'paper':
        return <div className="grid gap-4 xl:grid-cols-2">
          <ReadOnlySection title="Spot Paper Trading — salt okunur" value={field(data.portfolio, 'spot')} />
          <ReadOnlySection title="Futures Paper Trading — salt okunur" value={field(data.portfolio, 'futures')} />
        </div>;
      case 'portfolio':
        return <ReadOnlySection title="Spot ve Futures portföy raporu" value={data.portfolio}
          description="Eksik piyasa fiyatı varsa birleşik özsermaye hesaplanmaz." />;
      case 'performance':
        return <div className="grid gap-4 xl:grid-cols-2">
          <ReadOnlySection title="Paper performans raporu" value={data.performance} />
          <ReadOnlySection title="Kapanmış strateji performansı" value={data.strategies} />
        </div>;
      case 'health':
        return <div className="grid gap-4 xl:grid-cols-2">
          <ReadOnlySection title="Operasyonel sağlık" value={data.operations} />
          <ReadOnlySection title="Strateji sonuç doğrulaması" value={data.validation} />
        </div>;
      case 'scanner':
      case 'backtest':
      case 'history':
        return <Pending label={current} />;
    }
  };

  return (
    <div className="space-y-5" data-testid="ebbot-crypto-trading">
      <header className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <div className="flex items-center gap-2 text-xs font-bold uppercase tracking-widest text-primary">
            <Bot className="h-4 w-4" /> EBBot
          </div>
          <h1 className="mt-1 text-2xl font-black tracking-tight text-foreground md:text-3xl">Kripto Trading Merkezi</h1>
          <p className="mt-2 max-w-3xl text-sm text-muted-text">
            Spot ve Futures analizleri, sanal portföy, risk ve ajan değerlendirmeleri.
          </p>
        </div>
        <button type="button" onClick={() => { setLoading(true); setRequestId(n => n + 1); }}
          className="inline-flex items-center gap-2 rounded-xl border border-border bg-card px-3 py-2 text-sm text-foreground">
          <RefreshCw className="h-4 w-4" /> Yenile
        </button>
      </header>

      <div className="flex flex-wrap gap-2">
        <span className="inline-flex items-center gap-2 rounded-full bg-primary/10 px-3 py-1.5 text-xs font-bold text-primary">
          <ShieldCheck className="h-4 w-4" /> SADECE PAPER · GERÇEK EMİR YOK
        </span>
        <span className="inline-flex items-center gap-2 rounded-full border border-border bg-card px-3 py-1.5 text-xs text-secondary-text">
          <LockKeyhole className="h-4 w-4" /> Yönetici oturumuyla korunan veri
        </span>
        {data ? <span className="rounded-full border border-border bg-card px-3 py-1.5 text-xs text-muted-text">
          v{data.application.version ?? '—'} · {new Date(data.generated_at).toLocaleString('tr-TR')}
        </span> : null}
      </div>

      {loading && !data ? <div role="status" className="rounded-2xl border border-border bg-card p-6 text-sm text-muted-text">
        Kripto motorunun doğrulanmış verileri yükleniyor…
      </div> : null}
      {error ? <div role="alert" className="rounded-2xl border border-border bg-card p-5">
        <div className="flex items-start gap-2"><CircleAlert className="h-5 w-5 text-danger" />
          <div><h2 className="font-bold">Bağlantı güvenli değil veya hazır değil</h2>
            <p className="mt-2 text-sm text-muted-text">{error}</p>
            <Link to="/settings" className="mt-3 inline-flex items-center gap-1 text-sm text-primary">
              Ayarları aç <ArrowRight className="h-4 w-4" />
            </Link>
          </div></div>
      </div> : null}

      <div className="grid gap-4 lg:grid-cols-[230px_minmax(0,1fr)]">
        <nav aria-label="Kripto modülü menüsü" className="min-w-0 rounded-2xl border border-border bg-card p-2">
          <p className="px-3 py-2 text-xs font-bold uppercase tracking-widest text-muted-text">15 Modül</p>
          <div className="grid grid-cols-2 gap-1 sm:grid-cols-3 lg:grid-cols-1">
            {SECTIONS.map((item, index) => <button type="button" key={item.id}
              aria-current={active === item.id ? 'page' : undefined}
              onClick={() => setActive(item.id)}
              className={'rounded-xl px-3 py-2.5 text-left text-xs transition-colors ' +
                (active === item.id ? 'bg-primary/10 font-bold text-primary' : 'text-secondary-text hover:bg-hover')}>
              <span className="mr-1 text-muted-text">{String(index + 1).padStart(2, '0')}</span> {item.label}
            </button>)}
          </div>
        </nav>
        <section className="min-w-0 space-y-4" aria-label="Kripto içerik">
          {data ? <>
            <div className="grid grid-cols-2 gap-3 xl:grid-cols-4">
              <Metric title="Birleşik Paper özsermaye"
                value={valuationComplete ? formatted(equity) + ' USDT' : 'Değerlenemiyor'}
                note={valuationComplete ? 'Spot + Futures · Sanal' : 'Eksik piyasa fiyatı mevcut'} />
              <Metric title="Günlük Paper PnL" value={pnl(performanceDaily) + ' USDT'} />
              <Metric title="Haftalık Paper PnL" value={pnl(performanceWeekly) + ' USDT'} />
              <Metric title="Açık Paper pozisyon" value={String(positions.length)} />
            </div>
            <div className="flex flex-wrap items-center justify-between gap-3">
              <h2 className="text-lg font-bold text-foreground">{current}</h2>
              <span className="text-xs text-muted-text"><Activity className="mr-1 inline h-4 w-4" />Yalnızca doğrulanmış kaynak verileri</span>
            </div>
            {body()}
          </> : (['spot', 'futures', 'analysis', 'signals', 'agents', 'risk'] as SectionId[]).includes(active) ? body() : <div className="rounded-2xl border border-border bg-card p-6 text-sm text-muted-text">
            Kripto paneli, doğrulanmış servis yanıtı alınmadan hesap bilgisi göstermez.
          </div>}
        </section>
      </div>
      <footer className="flex flex-wrap items-center gap-3 rounded-xl border border-border bg-card p-3 text-xs text-muted-text">
        <Database className="h-4 w-4" />
        Bu ilk sürüm yalnızca veri okur. Kripto Paper Trading işlem açma/kapama ekranı henüz etkin değil.
        <Link to="/data" className="inline-flex items-center gap-1 font-semibold text-primary">
          CoinGecko Top 100 <ExternalLink className="h-3 w-3" />
        </Link>
        <span className="inline-flex items-center gap-1"><Layers className="h-4 w-4" />Hisse modülleri değişmedi</span>
        <span className="inline-flex items-center gap-1"><Wallet className="h-4 w-4" />Gerçek bakiye izni yok</span>
      </footer>
    </div>
  );
};

export default CryptoTradingPage;
