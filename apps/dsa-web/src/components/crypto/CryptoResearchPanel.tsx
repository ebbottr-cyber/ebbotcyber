import type React from 'react';
import { useEffect, useState } from 'react';
import { Activity, BookOpen, BrainCircuit, CircleAlert, PlayCircle, RefreshCw, ShieldCheck } from 'lucide-react';
import {
  cryptoResearchApi, type AgentReport, type AgentWeights,
  type ResearchMarket, type ResearchRequest, type ResearchStrategyId,
  type ResearchTimeframe, type SignalFeed, type StrategyCatalog, type StrategyReport,
} from '../../api/cryptoResearch';

type View = 'analysis' | 'signals' | 'agents';
const FRAME_OPTIONS: ResearchTimeframe[] = ['15m', '1h', '4h', '1d', '5m', '1m'];
const STRATEGY_NAMES: Record<ResearchStrategyId, string> = {
  scalping: 'Scalping', intraday: 'Gün İçi', swing: 'Swing',
  trend_following: 'Trend Takibi', mean_reversion: 'Ortalamaya Dönüş',
  momentum: 'Momentum', breakout: 'Kırılım',
};
const AGENT_NAMES: Record<string, string> = {
  trend: 'Trend', scalping: 'Scalping', momentum: 'Momentum',
  mean_reversion: 'Ortalamaya Dönüş', breakout: 'Kırılım',
  intraday: 'Gün İçi', swing: 'Swing', volume: 'Hacim',
  orderbook: 'Emir Defteri',
};
const ACTIONS: Record<string, string> = { BUY: 'AL yönlü', SELL: 'SAT yönlü', HOLD: 'BEKLE' };

function number(value: number | null | undefined, digits = 2) {
  return typeof value === 'number' && Number.isFinite(value)
    ? new Intl.NumberFormat('tr-TR', { maximumFractionDigits: digits }).format(value)
    : '—';
}

function Hint({ message }: { message: string }) {
  return <div className="flex items-start gap-2 rounded-xl border border-border bg-card p-4 text-sm text-muted-text">
    <CircleAlert className="mt-0.5 h-4 w-4 shrink-0" />{message}
  </div>;
}

function ActionTag({ action }: { action: string }) {
  return <span className={'inline-flex rounded-lg px-2 py-1 text-xs font-bold ' +
    (action === 'BUY' ? 'bg-success/10 text-success' :
      action === 'SELL' ? 'bg-danger/10 text-danger' : 'bg-muted text-secondary-text')}>
    {ACTIONS[action] ?? action}
  </span>;
}

export const CryptoResearchPanel: React.FC<{ view: View }> = ({ view }) => {
  const [market, setMarket] = useState<ResearchMarket>('spot');
  const [journalMarket, setJournalMarket] = useState<'all' | ResearchMarket>('all');
  const [symbol, setSymbol] = useState('BTC/USDT');
  const [timeframe, setTimeframe] = useState<ResearchTimeframe>('1h');
  const [catalog, setCatalog] = useState<StrategyCatalog | null>(null);
  const [selectedStrategy, setSelectedStrategy] = useState<ResearchStrategyId>('trend_following');
  const [agentResult, setAgentResult] = useState<AgentReport | null>(null);
  const [strategyResult, setStrategyResult] = useState<StrategyReport | null>(null);
  const [journal, setJournal] = useState<SignalFeed | null>(null);
  const [weights, setWeights] = useState<AgentWeights | null>(null);
  const [busy, setBusy] = useState(false);
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState('');
  const [refresh, setRefresh] = useState(0);

  // Only read persistent journal, strategy catalog or weights on tab opening.
  // Never run agents in an effect: upstream /agents/analyze records journal rows.
  useEffect(() => {
    let alive = true;
    setMessage('');
    setLoading(true);
    setJournal(null);
    setWeights(null);
    setCatalog(null);
    const task = view === 'signals'
      ? cryptoResearchApi.journal(journalMarket)
      : view === 'agents'
        ? cryptoResearchApi.weights()
        : cryptoResearchApi.catalog();
    void task.then(result => {
      if (!alive) return;
      if (view === 'signals') setJournal(result as SignalFeed);
      if (view === 'agents') setWeights(result as AgentWeights);
      if (view === 'analysis') setCatalog(result as StrategyCatalog);
    }).catch(() => {
      if (alive) setMessage('Araştırma servisine ulaşılamadı veya yanıt güvenli biçimde doğrulanamadı.');
    }).finally(() => {
      if (alive) setLoading(false);
    });
    return () => { alive = false; };
  }, [view, journalMarket, refresh]);

  const changeMarket = (value: ResearchMarket) => {
    setMarket(value);
    setSymbol('BTC/USDT');
    setAgentResult(null);
    setStrategyResult(null);
    setMessage('');
  };
  const changeSymbol = (value: string) => {
    setSymbol(value);
    setAgentResult(null);
    setStrategyResult(null);
  };
  const changeFrame = (value: ResearchTimeframe) => {
    setTimeframe(value);
    setAgentResult(null);
    setStrategyResult(null);
  };

  const input = (): ResearchRequest => ({ market, symbol, timeframe });

  const runAgents = async () => {
    if (busy) return;
    setBusy(true);
    setMessage('');
    setAgentResult(null);
    setStrategyResult(null);
    try {
      const report = await cryptoResearchApi.analyze(input());
      setAgentResult(report);
    } catch {
      setMessage('Ajan analizi tamamlanamadı. Kaynak veri, sembol ve güncellik kontrollerini doğrulayın.');
    } finally {
      setBusy(false);
    }
  };

  const runStrategy = async () => {
    if (busy) return;
    setBusy(true);
    setMessage('');
    setStrategyResult(null);
    try {
      const report = await cryptoResearchApi.strategy(input(), selectedStrategy);
      setStrategyResult(report);
    } catch {
      setMessage('Strateji değerlendirmesi tamamlanamadı. Geçersiz veya eksik veriyle sinyal gösterilmez.');
    } finally {
      setBusy(false);
    }
  };

  return <div className="space-y-4" data-testid={'ebbot-crypto-research-' + view}>
    <section className="rounded-2xl border border-border bg-card p-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h3 className="flex items-center gap-2 text-base font-bold">
            <BrainCircuit className="h-5 w-5 text-primary" />
            {view === 'analysis' ? 'Kripto Ajan ve Strateji Analizi' :
              view === 'signals' ? 'Kalıcı Araştırma Sinyal Günlüğü' : '9 Bağımsız Ajan Merkezi'}
          </h3>
          <p className="mt-2 max-w-3xl text-xs leading-6 text-muted-text">
            Trading Office'un kural tabanlı ajanları kullanılır; LLM model eğitimi veya otomatik işlem yoktur.
            Analiz yalnızca isteğinizle çalıştırılır. Üretilen AL/SAT/BEKLE görüşleri emir değildir.
          </p>
        </div>
        <button type="button" onClick={() => setRefresh(n => n + 1)}
          className="inline-flex items-center gap-2 rounded-xl border border-border bg-card px-3 py-2 text-xs">
          <RefreshCw className="h-4 w-4"/> Kayıtları yenile
        </button>
      </div>
      <p className="mt-3 flex items-center gap-2 text-xs text-muted-text">
        <ShieldCheck className="h-4 w-4 text-success"/>
        Paper pozisyon açma kapalı · Merkezi risk onayı verilmedi · Gerçek emir yok
      </p>
    </section>

    {loading ? <div role="status" className="rounded-xl bg-surface p-3 text-xs text-muted-text">
      Araştırma kayıtları doğrulanıyor…
    </div> : null}
    {message ? <div role="alert" className="rounded-xl border border-border bg-card p-4 text-sm text-danger">{message}</div> : null}

    {view === 'analysis' ? <>
      <section className="rounded-2xl border border-border bg-card p-4">
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          <div>
            <label htmlFor="research-market" className="text-xs font-semibold text-secondary-text">Piyasa</label>
            <select id="research-market" value={market} onChange={e => changeMarket(e.target.value as ResearchMarket)}
              className="mt-1 w-full rounded-lg border border-border bg-background px-3 py-2 text-sm">
              <option value="spot">Binance Spot</option>
              <option value="futures">Binance USD-M Futures</option>
            </select>
          </div>
          <div>
            <label htmlFor="research-symbol" className="text-xs font-semibold text-secondary-text">İşlem çifti</label>
            <input id="research-symbol" value={symbol} maxLength={26} onChange={e => changeSymbol(e.target.value)}
              className="mt-1 w-full rounded-lg border border-border bg-background px-3 py-2 font-mono text-sm" />
          </div>
          <div>
            <label htmlFor="research-frame" className="text-xs font-semibold text-secondary-text">Zaman dilimi</label>
            <select id="research-frame" value={timeframe} onChange={e => changeFrame(e.target.value as ResearchTimeframe)}
              className="mt-1 w-full rounded-lg border border-border bg-background px-3 py-2 text-sm">
              {FRAME_OPTIONS.map(frame => <option key={frame} value={frame}>{frame}</option>)}
            </select>
          </div>
          <div className="flex items-end">
            <button type="button" onClick={() => void runAgents()} disabled={busy}
              className="flex w-full items-center justify-center gap-2 rounded-xl bg-primary px-3 py-2.5 text-sm font-bold text-primary-foreground disabled:opacity-50">
              <PlayCircle className="h-4 w-4"/>{busy ? 'Analiz sürüyor…' : '9 Ajanı Çalıştır'}
            </button>
          </div>
        </div>
        <p className="mt-3 text-xs leading-5 text-muted-text">
          Bu işlem Trading Office'ta aynı mum için tekilleştirilen kalıcı araştırma sinyali kayıtları oluşturabilir.
          İşlem veya portföy mutasyonu yapmaz. Güncel 250 mum doğrulanamazsa çalışmaz.
        </p>
      </section>

      {agentResult ? <>
        <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
          <div className="rounded-xl border border-border bg-card p-4">
            <p className="text-xs text-muted-text">Birleşik ajan görüşü</p>
            <div className="mt-2"><ActionTag action={agentResult.action}/></div>
          </div>
          <div className="rounded-xl border border-border bg-card p-4">
            <p className="text-xs text-muted-text">Görüş güven skoru</p>
            <p className="mt-2 text-xl font-bold">{number(agentResult.confidence * 100, 1)}%</p>
          </div>
          <div className="rounded-xl border border-border bg-card p-4">
            <p className="text-xs text-muted-text">Ajan uyumu</p>
            <p className="mt-2 text-xl font-bold">{number(agentResult.agreement * 100, 1)}%</p>
          </div>
          <div className="rounded-xl border border-border bg-card p-4">
            <p className="text-xs text-muted-text">Piyasa rejimi</p>
            <p className="mt-2 text-lg font-semibold">{agentResult.market_regime ?? 'Belirlenemedi'}</p>
          </div>
        </div>
        <section className="rounded-2xl border border-border bg-card p-4">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <h4 className="text-sm font-bold">Bağımsız ajan kararları</h4>
            <span className="text-xs text-muted-text">
              AL {agentResult.votes.buy} · SAT {agentResult.votes.sell} · BEKLE {agentResult.votes.hold}
            </span>
          </div>
          <div className="mt-3 grid gap-2 xl:grid-cols-2">
            {agentResult.agents.map(agent => <article key={agent.agent}
              className="rounded-xl border border-border p-3">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <strong className="text-sm">{AGENT_NAMES[agent.agent] ?? agent.agent}</strong>
                <ActionTag action={agent.action}/>
              </div>
              <p className="mt-2 text-xs text-muted-text">
                Güven {number(agent.confidence * 100, 1)}% · Rejim ağırlığı {number(agent.regime_weight, 3)}
                {' · '}Geçmiş performans ağırlığı {number(agent.performance_weight, 3)}
              </p>
              <p className="mt-2 text-xs leading-5 text-secondary-text">
                Kaynak gerekçesi: {agent.rationale}
              </p>
            </article>)}
          </div>
          <div className="mt-3 rounded-lg bg-surface p-3 text-xs text-muted-text">
            Haber riski: {agentResult.news_context.risk_level}
            {' · '}Haber sayısı: {agentResult.news_context.article_count}
            {' · '}Yeni araştırma günlüğü kaydı: {agentResult.journal_recorded}
            {' · '}Risk onayı: <strong>YOK</strong>
          </div>
        </section>
      </> : <Hint message="Görüş üretmek için piyasayı, çifti ve zaman dilimini seçip 9 ajanı çalıştırın. Varsayılan veya örnek sinyal gösterilmez."/>}

      <section className="rounded-2xl border border-border bg-card p-4">
        <h4 className="mb-3 text-sm font-bold"><BookOpen className="mr-2 inline h-4 w-4 text-primary"/>7 Strateji Motoru</h4>
        <div className="flex flex-wrap gap-2">
          {(catalog?.strategies ?? []).map(item => <button type="button" key={item.name}
            aria-pressed={item.name === selectedStrategy} onClick={() => { setSelectedStrategy(item.name); setStrategyResult(null); }}
            className={'rounded-lg border px-3 py-2 text-xs ' +
              (item.name === selectedStrategy ? 'border-primary bg-primary/10 font-semibold text-primary' : 'border-border')}>
            {STRATEGY_NAMES[item.name]}
          </button>)}
        </div>
        {!catalog ? <p className="mt-3 text-xs text-muted-text">Strateji kataloğu doğrulanmadan değerlendirme çalıştırılamaz.</p> : (
          <div className="mt-4 flex flex-wrap items-center justify-between gap-3">
            <p className="text-xs text-muted-text">
              {catalog.strategies.find(x => x.name === selectedStrategy)?.description}
            </p>
            <button type="button" disabled={busy} onClick={() => void runStrategy()}
              className="rounded-lg border border-primary px-3 py-2 text-xs font-bold text-primary disabled:opacity-50">
              Stratejiyi değerlendir
            </button>
          </div>
        )}
        {strategyResult && <div className="mt-3 rounded-xl bg-surface p-3 text-xs leading-6">
          <div className="flex items-center gap-2">
            <ActionTag action={strategyResult.action}/>
            <strong>{STRATEGY_NAMES[strategyResult.strategy]}</strong>
          </div>
          <p className="mt-2">Güven: {number(strategyResult.confidence * 100, 1)}%</p>
          <p>Referans fiyat: {number(strategyResult.entry_reference, 6)} · Stop referansı:
            {' '}{number(strategyResult.stop_reference, 6)} · Hedef referansı:
            {' '}{number(strategyResult.take_profit_reference, 6)}
          </p>
          <p className="text-muted-text">Kaynak açıklama: {strategyResult.rationale}</p>
          <p className="font-semibold">Risk motoru onayı verilmedi; fiyatlar yalnızca araştırma referansıdır.</p>
        </div>}
      </section>
    </> : null}

    {view === 'signals' ? <>
      <section className="flex flex-wrap items-center gap-2 rounded-xl border border-border bg-card p-3">
        <span className="mr-2 text-xs font-semibold">Günlük filtresi</span>
        {(['all', 'spot', 'futures'] as const).map(value => (
          <button type="button" key={value} onClick={() => setJournalMarket(value)}
            aria-pressed={journalMarket === value}
            className={'rounded-lg border px-3 py-2 text-xs ' +
              (journalMarket === value ? 'border-primary bg-primary/10 font-semibold text-primary' : 'border-border')}>
            {value === 'all' ? 'Tümü' : value === 'spot' ? 'Spot' : 'Futures'}
          </button>
        ))}
      </section>
      {journal ? <section className="overflow-hidden rounded-2xl border border-border bg-card">
        <div className="flex flex-wrap justify-between gap-2 border-b border-border p-4">
          <h4 className="font-bold">Kayıtlı sinyaller ({journal.total_matching})</h4>
          <p className="text-xs text-muted-text">Kalıcı araştırma günlüğü · Yalnızca görüntüleme</p>
        </div>
        {journal.signals.length ? <div className="overflow-x-auto">
          <table className="w-full min-w-[760px] text-left text-xs">
            <thead className="bg-surface text-muted-text"><tr>
              <th className="px-3 py-3">Tarih</th><th className="px-3 py-3">Piyasa</th>
              <th className="px-3 py-3">Coin</th><th className="px-3 py-3">Ajan</th>
              <th className="px-3 py-3">Yön</th><th className="px-3 py-3">Durum</th>
              <th className="px-3 py-3">Net %</th>
            </tr></thead>
            <tbody>{journal.signals.map(row => <tr key={row.id} className="border-t border-border/60">
              <td className="px-3 py-3">{new Date(row.created_at).toLocaleString('tr-TR')}</td>
              <td className="px-3 py-3">{row.market === 'spot' ? 'Spot' : 'Futures'}</td>
              <td className="px-3 py-3 font-semibold">{row.symbol}</td>
              <td className="px-3 py-3">{AGENT_NAMES[row.agent] ?? row.agent}</td>
              <td className="px-3 py-3"><ActionTag action={row.action}/></td>
              <td className="px-3 py-3">{row.outcome === null ? 'Açık kayıt' :
                row.outcome === 'WIN' ? 'Başarılı' : row.outcome === 'LOSS' ? 'Başarısız' : 'Başabaş'}</td>
              <td className="px-3 py-3">{row.pnl_pct !== null ? number(row.pnl_pct, 3) : '—'}</td>
            </tr>)}</tbody>
          </table>
        </div> : <div className="p-5 text-sm text-muted-text">Bu filtrede henüz kaydedilmiş araştırma sinyali yok.</div>}
      </section> : <Hint message="Yalnızca kalıcı ve doğrulanmış araştırma günlüğü kayıtları gösterilir; örnek sinyal üretilmez."/>}
    </> : null}

    {view === 'agents' ? <>
      <section className="rounded-2xl border border-border bg-card p-4">
        <h4 className="font-bold">Kapanmış sinyal sonuçlarından ajan ağırlıkları</h4>
        <p className="mt-2 text-xs leading-6 text-muted-text">
          Ajan ağırlıkları, yalnızca yeterli örneklem bulunan kapanmış araştırma sinyallerinden hesaplanır.
          Model eğitimi veya işlem yönetimi değildir. Boş ağırlık listesi hata değil, yeterli tarihçe olmadığı anlamına gelebilir.
        </p>
        {weights ? <div className="mt-4 grid gap-2 sm:grid-cols-2 xl:grid-cols-3">
          {Object.keys(AGENT_NAMES).map(name => {
            const weight = weights.weights[name];
            return <div key={name} className="rounded-xl border border-border p-3">
              <div className="flex items-center justify-between gap-2">
                <strong className="text-sm">{AGENT_NAMES[name]}</strong>
                <span className="font-mono text-sm font-semibold">{typeof weight === 'number' ? number(weight, 4) : '1,00*'}</span>
              </div>
              <p className="mt-2 text-[11px] text-muted-text">
                {typeof weight === 'number' ? 'Kapanmış sinyal sonucuyla ayarlandı' : 'Yeterli örneklem yok; varsayılan ağırlık'}
              </p>
            </div>;
          })}
        </div> : <Hint message="Ajan ağırlıkları doğrulanamadı veya servis erişilebilir değil."/>}
        <p className="mt-3 text-xs text-muted-text">
          * Varsayılan ağırlık 1,00; kararlar merkezî risk motorundan bağımsız işlem izni almaz.
        </p>
      </section>
    </> : null}

    <footer className="flex items-start gap-2 rounded-xl border border-border bg-card p-3 text-xs leading-5 text-muted-text">
      <Activity className="mt-0.5 h-4 w-4 shrink-0"/>
      Analiz araştırma amaçlıdır, yatırım tavsiyesi veya işlemi yürütme onayı değildir.
      Otomatik işlem, gerçek borsa emri ve risk motorunu atlama kapalıdır.
    </footer>
  </div>;
};
