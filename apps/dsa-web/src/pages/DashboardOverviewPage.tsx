import type React from 'react';
import { useEffect, useMemo, useState } from 'react';
import {
  Activity, AlertTriangle, ArrowRight, BarChart3, Bell, BrainCircuit,
  Clock3, Database, Layers3, LineChart, RefreshCcw, ShieldCheck,
  TrendingDown, TrendingUp, Wallet,
} from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import { alertsApi } from '../api/alerts';
import { analysisApi } from '../api/analysis';
import { historyApi } from '../api/history';
import { portfolioApi } from '../api/portfolio';
import { trMarketApi, type TrMarketItem } from '../api/trMarketOverview';
import { TurkeyMarketCards } from '../components/dashboard/TurkeyMarketCards';
import { useWatchlist } from '../hooks/useWatchlist';
import { StockCandlestickChart } from '../components/dashboard/StockCandlestickChart';
import type { HistoryItem, TaskInfo } from '../types/analysis';
import type { AlertTriggerItem } from '../types/alerts';
import type { PortfolioRiskResponse, PortfolioSnapshotResponse } from '../types/portfolio';

type BlockProps = { title: string; icon: React.ReactNode; children: React.ReactNode; action?: React.ReactNode };
const surface = 'rounded-2xl border border-[#e1e9f5] bg-white shadow-[0_8px_25px_rgba(30,69,130,0.045)]';

function Block({ title, icon, children, action }: BlockProps) {
  return (
    <section className={surface + ' min-w-0 p-4 sm:p-5'}>
      <div className="mb-4 flex items-center justify-between gap-3">
        <h2 className="flex items-center gap-2 text-sm font-bold text-[#182b4e]">{icon}{title}</h2>
        {action}
      </div>
      {children}
    </section>
  );
}

const formatAmount = (value: number | null | undefined) =>
  typeof value === 'number' && Number.isFinite(value)
    ? new Intl.NumberFormat('tr-TR', { maximumFractionDigits: 2 }).format(value)
    : '—';
const formatChange = (value: number | null | undefined) =>
  typeof value === 'number' && Number.isFinite(value)
    ? (value > 0 ? '+' : '') + new Intl.NumberFormat('tr-TR', { maximumFractionDigits: 2 }).format(value) + '%'
    : 'Veri yok';

function ReportPriceHistory({ points }: { points: HistoryItem[] }) {
  const priced = points
    .filter((item) => typeof item.currentPrice === 'number' && Number.isFinite(item.currentPrice) && item.currentPrice > 0)
    .sort((a, b) => Date.parse(a.createdAt) - Date.parse(b.createdAt))
    .slice(-16);
  if (priced.length < 2) {
    return (
      <div className="flex min-h-[210px] flex-col items-center justify-center gap-2 rounded-xl border border-dashed border-[#dce7f5] bg-[#fbfdff] px-5 text-center">
        <LineChart className="h-8 w-8 text-[#7ba9e5]" />
        <p className="text-sm font-semibold text-[#253c62]">Fiyat geçmişi henüz oluşmadı</p>
        <p className="max-w-sm text-xs text-[#7b8da9]">Grafik yalnızca gerçek, kayıtlı analiz fiyatlarından oluşturulur. İki veya daha fazla rapor gerektiğinde çizilir.</p>
      </div>
    );
  }
  const values = priced.map((item) => item.currentPrice as number);
  const low = Math.min(...values);
  const high = Math.max(...values);
  const span = Math.max(high - low, 0.01);
  const line = values.map((value, index) => {
    const x = 18 + 624 * index / (values.length - 1);
    const y = 144 - (value - low) / span * 118;
    return x.toFixed(1) + ',' + y.toFixed(1);
  }).join(' ');
  const lastX = 642;
  const lastY = 144 - (values[values.length - 1] - low) / span * 118;
  return (
    <div className="min-w-0">
      <svg className="w-full" viewBox="0 0 660 178" role="img" aria-label="Gerçek analiz raporlarından alınan fiyat geçmişi">
        {[32, 69, 106, 144].map((y) => (
          <line key={y} x1="16" x2="644" y1={y} y2={y} stroke="#e8eef6" strokeWidth="1" />
        ))}
        <polyline points={line} fill="none" stroke="#258cda" strokeWidth="3.5" strokeLinecap="round" strokeLinejoin="round" />
        <circle cx={lastX} cy={lastY} r="5" fill="#1a69c8" stroke="white" strokeWidth="2" />
        <text x="18" y="171" fontSize="11" fill="#7d8fa9">{new Date(priced[0].createdAt).toLocaleDateString('tr-TR')}</text>
        <text x="642" y="171" textAnchor="end" fontSize="11" fill="#7d8fa9">{new Date(priced[priced.length - 1].createdAt).toLocaleDateString('tr-TR')}</text>
        <text x="640" y="16" textAnchor="end" fontSize="11" fill="#526e96">{formatAmount(high)}</text>
      </svg>
      <p className="text-[11px] text-[#899bb3]">Canlı mum grafiği değildir; analiz raporlarına kaydedilmiş fiyatlar gösterilir.</p>
    </div>
  );
}

const DashboardOverviewPage: React.FC = () => {
  const navigate = useNavigate();
  const watchlist = useWatchlist();
  const [refreshNumber, setRefreshNumber] = useState(0);
  const [loading, setLoading] = useState(true);
  const [failed, setFailed] = useState<string[]>([]);
  const [history, setHistory] = useState<HistoryItem[]>([]);
  const [portfolio, setPortfolio] = useState<PortfolioSnapshotResponse | null>(null);
  const [risk, setRisk] = useState<PortfolioRiskResponse | null>(null);
  const [alerts, setAlerts] = useState<AlertTriggerItem[]>([]);
  const [tasks, setTasks] = useState<TaskInfo[]>([]);
  const [marketItems, setMarketItems] = useState<TrMarketItem[]>([]);
  const [marketLoadFailed, setMarketLoadFailed] = useState(false);
  const [selectedCode, setSelectedCode] = useState('');
  const [news, setNews] = useState<Array<{ title: string; snippet: string; url: string }>>([]);
  const [newsUnavailable, setNewsUnavailable] = useState(false);

  useEffect(() => {
    document.title = 'EBBot | Piyasa Özeti';
    let active = true;
    setLoading(true);
    setFailed([]);
    async function load() {
      const [historyResult, portfolioResult, riskResult, alertsResult, tasksResult, reviewResult] = await Promise.allSettled([
        historyApi.getList({ limit: 60 }),
        portfolioApi.getSnapshot(),
        portfolioApi.getRisk(),
        alertsApi.listTriggers({ pageSize: 5 }),
        analysisApi.getTasks({ limit: 8 }),
        trMarketApi.getOverview(),
      ]);
      if (!active) return;
      const errors: string[] = [];
      if (historyResult.status === 'fulfilled') setHistory(historyResult.value.items.filter((item) => item.reportType !== 'market_review'));
      else errors.push('Analiz geçmişi');
      if (portfolioResult.status === 'fulfilled') setPortfolio(portfolioResult.value);
      else errors.push('Portföy');
      if (riskResult.status === 'fulfilled') setRisk(riskResult.value);
      else errors.push('Risk');
      if (alertsResult.status === 'fulfilled') setAlerts(alertsResult.value.items);
      else errors.push('Uyarılar');
      if (tasksResult.status === 'fulfilled') setTasks(tasksResult.value.tasks);
      else errors.push('Görevler');
      if (reviewResult.status === 'fulfilled') {
        setMarketItems(reviewResult.value.items);
        setMarketLoadFailed(false);
      } else {
        setMarketItems([]);
        setMarketLoadFailed(true);
        errors.push('Türkiye piyasaları');
      }
      setFailed(errors);
      if (active) setLoading(false);
    }
    void load();
    return () => { active = false; };
  }, [refreshNumber]);

  const currentCode = selectedCode || history[0]?.stockCode || '';
  const matching = useMemo(() => history.filter((item) => item.stockCode === currentCode), [history, currentCode]);
  const latest = matching[0] ?? null;

  useEffect(() => {
    let active = true;
    setNews([]);
    setNewsUnavailable(false);
    if (!latest?.id) return () => { active = false; };
    historyApi.getNews(latest.id, 4)
      .then((response) => { if (active) setNews(response.items); })
      .catch(() => { if (active) setNewsUnavailable(true); });
    return () => { active = false; };
  }, [latest?.id]);

  const uniqueStocks = useMemo(() =>
    Array.from(new Map(history.map((item) => [item.stockCode, item])).values()).slice(0, 7),
    [history],
  );

  const openAnalysis = (stockCode?: string) =>
    navigate('/', { state: stockCode ? { stockCode, autoAnalyze: false } : undefined });

  return (
    <div data-testid="ebbot-white-overview" className="min-h-[calc(100vh-3rem)] rounded-[24px] bg-[#f5f8fe] px-3 pb-20 pt-4 text-[#233758] sm:px-5 sm:pb-8 sm:pt-6 xl:px-7">
      <div className="mx-auto max-w-[1500px] space-y-5">
        <header className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <p className="flex items-center gap-2 text-xs font-semibold text-[#2b7bd6]"><BarChart3 className="h-4 w-4" /> EBBot • AI Yatırım Asistanı</p>
            <h1 className="mt-1 text-xl font-extrabold tracking-tight text-[#162a4a] sm:text-2xl">Piyasa Özeti</h1>
            <p className="mt-1 text-xs text-[#778da8]">Gerçek veri kaynakları • Eksik veriler tahmin edilmez</p>
          </div>
          <div className="flex items-center gap-2">
            <button type="button" disabled={loading} onClick={() => { setRefreshNumber((n) => n + 1); void watchlist.refresh(); }} className="flex h-10 items-center gap-2 rounded-xl border border-[#d6e2f2] bg-white px-3 text-xs font-semibold text-[#255187] hover:bg-[#f2f7ff] disabled:opacity-50">
              <RefreshCcw className="h-4 w-4" /> {loading ? 'Yükleniyor' : 'Yenile'}
            </button>
            <button type="button" onClick={() => openAnalysis()} className="flex h-10 items-center gap-2 rounded-xl bg-[#2676da] px-3 text-xs font-semibold text-white hover:bg-[#135fc3]">
              Analiz Çalışma Alanı <ArrowRight className="h-4 w-4" />
            </button>
          </div>
        </header>

        {failed.length > 0 ? (
          <div role="status" className="flex items-start gap-2 rounded-xl border border-[#efd4ab] bg-[#fff9ed] px-4 py-3 text-xs text-[#845d25]">
            <AlertTriangle className="h-4 w-4 shrink-0" /> Bağlanamayan bölümler: {failed.join(', ')}. Veriler gizlendi; yeniden deneyebilirsiniz.
          </div>
        ) : null}

        <TurkeyMarketCards items={marketItems} loading={loading} failed={marketLoadFailed} />

        <div className="grid items-start gap-4 xl:grid-cols-[minmax(0,1.95fr)_minmax(300px,1fr)]">
          <div className="min-w-0 space-y-4">
            <Block title="Hisse Analizi" icon={<BarChart3 className="h-4 w-4 text-[#2580dc]" />} action={
              <button type="button" onClick={() => openAnalysis(currentCode || undefined)} className="text-xs font-semibold text-[#2675d8] hover:underline">Ayrıntılı analiz →</button>
            }>
              {latest ? (
                <>
                  <div className="mb-3 flex flex-wrap items-center gap-x-4 gap-y-2 border-b border-[#e9eff8] pb-4">
                    <div className="min-w-0 flex-1">
                      <p className="text-lg font-extrabold text-[#19365f]">{latest.stockCode} <span className="font-medium text-[#7185a1]"> {latest.stockName ?? ''}</span></p>
                      <p className="text-[11px] text-[#8496ac]">Son kayıt: {new Date(latest.createdAt).toLocaleString('tr-TR')}</p>
                    </div>
                    <div className="text-right">
                      <p className="text-xl font-extrabold tabular-nums text-[#19365f]">{formatAmount(latest.currentPrice)}</p>
                      <p className={'text-xs font-semibold ' + (typeof latest.changePct === 'number' && latest.changePct >= 0 ? 'text-[#15a372]' : 'text-[#d65c62]')}>{formatChange(latest.changePct)}</p>
                    </div>
                  </div>
                  <StockCandlestickChart stockCode={currentCode} refreshKey={refreshNumber} fallback={<ReportPriceHistory points={matching} />} />
                  <div className="mt-3 flex flex-wrap gap-2">
                    {uniqueStocks.map((item) => (
                      <button type="button" key={item.stockCode} onClick={() => setSelectedCode(item.stockCode)}
                        className={'rounded-lg border px-2.5 py-1.5 text-xs font-semibold ' +
                          (currentCode === item.stockCode ? 'border-[#317bd2] bg-[#e9f3ff] text-[#1661bc]' : 'border-[#e0e9f4] bg-[#fafcff] text-[#68819f] hover:border-[#317bd2]')}>
                        {item.stockCode}
                      </button>
                    ))}
                  </div>
                  {latest.analysisSummary ? <p className="mt-4 line-clamp-3 rounded-xl bg-[#f3f8ff] p-3 text-xs leading-5 text-[#3e5a7b]">{latest.analysisSummary}</p> : null}
                </>
              ) : (
                <div className="flex min-h-[265px] flex-col items-center justify-center gap-3 text-center">
                  <LineChart className="h-10 w-10 text-[#9ebfe9]" />
                  <p className="text-sm font-semibold text-[#2a4163]">Henüz analiz raporu yok</p>
                  <p className="max-w-xs text-xs text-[#8a9bb2]">İlk hisse analizini başlattığınızda sonuçlar burada görüntülenecek.</p>
                  <button type="button" className="rounded-lg bg-[#2c7de0] px-4 py-2 text-sm text-white" onClick={() => openAnalysis()}>Analize git</button>
                </div>
              )}
            </Block>

            <div className="grid gap-4 md:grid-cols-2">
              <Block title="Portföy Özeti" icon={<Wallet className="h-4 w-4 text-[#2781dc]" />} action={
                <button type="button" onClick={() => navigate('/portfolio')} className="text-xs font-semibold text-[#2675d8] hover:underline">Detaylar →</button>
              }>
                <p className="text-xs text-[#7c8ba2]">Toplam özsermaye</p>
                <p className="mt-1 text-2xl font-extrabold tabular-nums text-[#1e375f]">{portfolio ? formatAmount(portfolio.totalEquity) : '—'} <span className="text-sm font-semibold text-[#7084a1]">{portfolio?.currency ?? ''}</span></p>
                <div className="mt-4 grid grid-cols-2 gap-3">
                  <div className="rounded-xl bg-[#f5f9ff] p-3"><p className="text-[11px] text-[#7d91ac]">Nakit</p><p className="mt-1 text-sm font-bold tabular-nums">{portfolio ? formatAmount(portfolio.totalCash) : '—'}</p></div>
                  <div className="rounded-xl bg-[#f5f9ff] p-3"><p className="text-[11px] text-[#7d91ac]">Pozisyon değeri</p><p className="mt-1 text-sm font-bold tabular-nums">{portfolio ? formatAmount(portfolio.totalMarketValue) : '—'}</p></div>
                </div>
                <p className="mt-3 text-[11px] text-[#8a9db4]">{portfolio?.fxStale ? 'Kur verilerinin bir bölümü güncel olmayabilir.' : portfolio ? (portfolio.accountCount + ' hesap • ' + portfolio.asOf) : 'Portföy verisi bekleniyor'}</p>
              </Block>
              <Block title="Risk Paneli" icon={<ShieldCheck className="h-4 w-4 text-[#2781dc]" />} action={
                <button type="button" onClick={() => navigate('/portfolio')} className="text-xs font-semibold text-[#2675d8] hover:underline">Risk detayları →</button>
              }>
                <div className="space-y-4">
                  {[
                    { label: 'En büyük pozisyon ağırlığı', val: risk?.concentration.topWeightPct, alert: risk?.concentration.alert },
                    { label: 'Güncel düşüş', val: risk?.drawdown.currentDrawdownPct, alert: risk?.drawdown.alert },
                  ].map(({ label, val, alert }) => (
                    <div key={label}>
                      <div className="mb-1 flex justify-between gap-2 text-xs"><span className="text-[#66809b]">{label}</span><span className="font-bold tabular-nums">{formatChange(val)}</span></div>
                      <div className="h-2 overflow-hidden rounded-full bg-[#e7eef8]"><div className={'h-full rounded-full ' + (alert ? 'bg-[#eab044]' : 'bg-[#36bd8a]')} style={{ width: (typeof val === 'number' ? Math.min(Math.abs(val), 100) : 0) + '%' }} /></div>
                    </div>
                  ))}
                  <div className="flex items-center justify-between rounded-xl bg-[#f5f9ff] p-3 text-xs"><span className="text-[#617a99]">Tetiklenen zarar-kes uyarıları</span><strong>{risk ? risk.stopLoss.triggeredCount : '—'}</strong></div>
                </div>
              </Block>
            </div>
          </div>

          <div className="min-w-0 space-y-4">
            <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-1">
              <Block title="Takip Listem" icon={<Layers3 className="h-4 w-4 text-[#2781dc]" />} action={<span className="text-xs text-[#8296b0]">{watchlist.isLoading ? 'Yükleniyor' : watchlist.watchlistCodes.length + ' sembol'}</span>}>
                {watchlist.watchlistCodes.length ? (
                  <div className="divide-y divide-[#edf1f7]">
                    {watchlist.watchlistCodes.slice(0, 6).map((code) => {
                      const item = history.find((entry) => entry.stockCode === code);
                      return <button type="button" onClick={() => openAnalysis(code)} key={code} className="flex w-full items-center justify-between gap-3 py-2 text-left text-xs hover:text-[#2473cd]">
                        <span className="font-semibold text-[#254366]">{code}</span>
                        <span className="text-[#7991ae]">{item?.currentPrice != null ? formatAmount(item.currentPrice) : 'Analiz verisi yok'}</span>
                      </button>;
                    })}
                  </div>
                ) : <p className="text-xs text-[#8296af]">{watchlist.isLoading ? 'Takip listesi yükleniyor...' : 'Takip listenize henüz sembol eklenmedi.'}</p>}
                <button type="button" onClick={() => openAnalysis()} className="mt-3 text-xs font-semibold text-[#2675d8]">Takip listesini düzenle →</button>
              </Block>

              <Block title="Finans Haberleri" icon={<Database className="h-4 w-4 text-[#2781dc]" />}>
                {news.length ? <div className="space-y-3">{news.map((item, index) => (
                  <a key={item.url + index} href={item.url} target="_blank" rel="noopener noreferrer" className="block rounded-lg border border-[#e5edf7] p-2.5 text-xs hover:border-[#8fbceb]">
                    <p className="line-clamp-2 font-semibold text-[#2e4567]">{item.title}</p>
                    {item.snippet ? <p className="mt-1 line-clamp-2 text-[#7d8fa8]">{item.snippet}</p> : null}
                  </a>
                ))}</div> : <p className="text-xs text-[#8296af]">{newsUnavailable ? 'Haber kaynağına erişilemedi.' : latest ? 'Bu analize ait haber kaydı yok.' : 'Haberler için bir analiz raporu seçin.'}</p>}
              </Block>

              <Block title="AI Analiz Akışı" icon={<BrainCircuit className="h-4 w-4 text-[#2781dc]" />} action={
                <button type="button" onClick={() => openAnalysis()} className="text-xs font-semibold text-[#2675d8]">Görevler →</button>
              }>
                {tasks.length ? <div className="space-y-2">{tasks.slice(0, 4).map((task) => (
                  <div className="flex items-start gap-2 rounded-lg bg-[#f5f9ff] p-2.5 text-xs" key={task.taskId}>
                    <Activity className="mt-0.5 h-4 w-4 shrink-0 text-[#3182d9]" />
                    <div className="min-w-0 flex-1"><p className="truncate font-semibold text-[#315077]">{task.stockCode || 'Genel analiz'}</p><p className="text-[#8799b1]">{task.status} • %{task.progress ?? 0}</p></div>
                  </div>
                ))}</div> : <p className="text-xs text-[#8296af]">Gösterilecek son analiz görevi yok.</p>}
              </Block>
            </div>

            <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-1">
              <Block title="Uyarılar" icon={<Bell className="h-4 w-4 text-[#d99a2d]" />} action={
                <button type="button" onClick={() => navigate('/alerts')} className="text-xs font-semibold text-[#2675d8]">Tümü →</button>
              }>
                {alerts.length ? <div className="space-y-2">{alerts.slice(0, 3).map((alert) => (
                  <div key={alert.id} className="flex items-start gap-2 border-b border-[#edf1f7] pb-2 text-xs last:border-0">
                    <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-[#e1a849]" />
                    <p className="min-w-0 text-[#526a89]"><strong>{alert.target}</strong> — {alert.reason ?? alert.status}</p>
                  </div>
                ))}</div> : <p className="text-xs text-[#8296af]">Son uyarı kaydı bulunamadı.</p>}
              </Block>
              <Block title="Sistem ve Görevler" icon={<Clock3 className="h-4 w-4 text-[#2781dc]" />}>
                <div className="flex items-center justify-between gap-3 text-xs"><span className="text-[#667f9c]">Listelenen görev</span><span className="font-bold">{tasks.length}</span></div>
                <div className="mt-3 flex items-center justify-between gap-3 text-xs"><span className="text-[#667f9c]">İşlemde olan</span><span className="font-bold">{tasks.filter((task) => task.status === 'processing' || task.status === 'pending').length}</span></div>
                <p className="mt-3 text-[11px] text-[#8296af]">Bu kart sunucu sağlığını doğrulamaz; yalnızca görev listesini gösterir.</p>
              </Block>
            </div>
          </div>
        </div>
      </div>
      <nav aria-label="Mobil hızlı gezinme" className="fixed bottom-0 left-0 right-0 z-30 grid grid-cols-4 border-t border-[#dce7f6] bg-white/95 px-2 pb-[max(env(safe-area-inset-bottom),8px)] pt-2 backdrop-blur sm:hidden">
        {[
          { text: 'Pano', icon: BarChart3, path: '/overview' },
          { text: 'Analiz', icon: LineChart, path: '/' },
          { text: 'Portföy', icon: Wallet, path: '/portfolio' },
          { text: 'Uyarılar', icon: Bell, path: '/alerts' },
        ].map(({ text, icon: Icon, path }) => (
          <button type="button" key={path} onClick={() => navigate(path)} className={'flex flex-col items-center gap-1 py-1 text-[10px] ' + (path === '/overview' ? 'font-bold text-[#2374d5]' : 'text-[#7288a4]')}>
            <Icon className="h-4 w-4" />{text}
          </button>
        ))}
      </nav>
    </div>
  );
};

export default DashboardOverviewPage;
