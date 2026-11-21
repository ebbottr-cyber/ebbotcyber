import { useEffect, useRef, useState } from 'react';
import { strategyLabApi, type EtfStrategyResearch } from '../api/strategyLab';
import { useUiLanguage } from '../contexts/UiLanguageContext';
import PaperJournalPanel from '../components/strategy-lab/PaperJournalPanel';
import type { UiLanguage } from '../i18n/uiText';

const TEXT: Record<UiLanguage, {
  title: string; intro: string; asset: string; simulations: string; run: string; running: string;
  noEtfs: string; loadError: string; analysisError: string; noResult: string; strategy: string;
  random: string; hold: string; drawdown: string; medianDrawdown: string; extremes: string;
  exceed: string; sample: string; insufficient: string; warnings: string; period: string;
  source: string; exposure: string; trades: string; costs: string; observe: string;
}> = {
  tr: {
    title: 'Strateji Başarı Laboratuvarı', intro: 'Gerçek ETF rotasyon işlemlerini aynı süreli rastgele zamanlamalarla karşılaştır. Yalnızca araştırma — al/sat emri gönderilmez.',
    asset: 'ETF', simulations: 'Rastgele karşılaştırma', run: 'Geçmiş verilerle karşılaştır', running: 'Hesaplanıyor…',
    noEtfs: 'ETF rotasyon havuzunda araştırmaya uygun bir kod tanımlı değil.', loadError: 'ETF listesi yüklenemedi.',
    analysisError: 'Geçmiş veri yetersiz veya analiz yapılamadı.', noResult: 'Henüz bir test yapılmadı.',
    strategy: 'Strateji getirisi', random: 'Rastgele ortanca getiri', hold: 'Al ve tut getirisi',
    drawdown: 'Strateji maksimum düşüş', medianDrawdown: 'Rastgele ortanca maksimum düşüş',
    extremes: 'Rastgele getiri aralığı (5.–95. yüzdelik)', exceed: 'Rastgele senaryolardan stratejiye eşit veya daha iyi olanlar',
    sample: 'Farklı rastgele zamanlamalar', insufficient: 'Bu işlem yapısında yeterince farklı zamanlama yok; sonuç ayırt edici değil.',
    warnings: 'Sonuçlar betimseldir, gelecekte kâr veya istatistiksel anlamlılık kanıtı değildir.',
    period: 'Veri dönemi', source: 'Kaynak', exposure: 'Pozisyonda kalınan bar', trades: 'Alım sayısı',
    costs: 'Tek yön komisyon / kayma', observe: 'Gözlem modu — gerçek işlem yapılmaz',
  },
  en: {
    title: 'Strategy Success Lab', intro: 'Compare recorded ETF rotation trades to randomly timed positions with matching holding durations. Research only — no orders.',
    asset: 'ETF', simulations: 'Random trials', run: 'Compare historical data', running: 'Computing…',
    noEtfs: 'No eligible ETF is configured in the rotation pool.', loadError: 'Could not load the ETF list.',
    analysisError: 'Insufficient history or evaluation unavailable.', noResult: 'No comparison has been run yet.',
    strategy: 'Strategy return', random: 'Random median return', hold: 'Buy-and-hold return',
    drawdown: 'Strategy max drawdown', medianDrawdown: 'Random median max drawdown',
    extremes: 'Random return interval (5th–95th percentile)', exceed: 'Random trials matching or exceeding the strategy',
    sample: 'Distinct randomized timings', insufficient: 'Too few distinct valid timings: result is not informative.',
    warnings: 'Results are descriptive, not proof of future profit or statistical significance.',
    period: 'Data range', source: 'Source', exposure: 'Invested bars', trades: 'Entries',
    costs: 'Per-side fees / slippage', observe: 'Observation only — no real trades',
  },
  zh: {
    title: '策略表现实验室', intro: '将已有 ETF 轮动历史成交与相同持仓时长的随机入场时点比较，仅用于研究，不会下单。',
    asset: 'ETF', simulations: '随机试验次数', run: '比较历史数据', running: '计算中…',
    noEtfs: 'ETF 轮动池没有可用于研究的代码。', loadError: 'ETF 列表加载失败。',
    analysisError: '历史数据不足或暂时无法评估。', noResult: '尚未运行比较。',
    strategy: '策略收益', random: '随机中位收益', hold: '买入持有收益',
    drawdown: '策略最大回撤', medianDrawdown: '随机中位最大回撤',
    extremes: '随机收益区间（5–95 百分位）', exceed: '不逊于该策略的随机结果比例',
    sample: '不同随机时序数', insufficient: '可用的不同随机时序太少，无法有效区分。',
    warnings: '此结果仅用于描述，不能证明未来收益或统计显著性。',
    period: '历史区间', source: '数据来源', exposure: '持仓 K 线数', trades: '建仓次数',
    costs: '单边手续费 / 滑点', observe: '观察模式 — 不执行真实交易',
  },
};

function percent(value: number): string {
  return Number.isFinite(value) ? `${value.toFixed(2)}%` : '—';
}

export default function StrategyLabPage() {
  const { language } = useUiLanguage();
  const text = TEXT[language];
  const [etfs, setEtfs] = useState<string[]>([]);
  const [selected, setSelected] = useState('');
  const [trials, setTrials] = useState(500);
  const [loadingList, setLoadingList] = useState(true);
  const [loading, setLoading] = useState(false);
  const [listError, setListError] = useState(false);
  const [analysisError, setAnalysisError] = useState(false);
  const [report, setReport] = useState<EtfStrategyResearch | null>(null);
  const requestId = useRef(0);

  useEffect(() => {
    document.title = text.title;
  }, [text.title]);

  useEffect(() => {
    let active = true;
    void strategyLabApi.eligibleEtfs().then((codes) => {
      if (!active) return;
      setEtfs(codes);
      setSelected(codes[0] ?? '');
    }).catch(() => {
      if (active) setListError(true);
    }).finally(() => {
      if (active) setLoadingList(false);
    });
    return () => {
      active = false;
      requestId.current += 1;
    };
  }, []);

  const changeSelection = (code: string) => {
    requestId.current += 1;
    setSelected(code);
    setReport(null);
    setAnalysisError(false);
    setLoading(false);
  };

  const run = async () => {
    if (!selected || loading) return;
    const id = ++requestId.current;
    setLoading(true);
    setReport(null);
    setAnalysisError(false);
    try {
      const next = await strategyLabApi.analyzeEtf(selected, trials);
      if (requestId.current === id) setReport(next);
    } catch {
      if (requestId.current === id) setAnalysisError(true);
    } finally {
      if (requestId.current === id) setLoading(false);
    }
  };

  const metrics = report?.result;
  return (
    <main className="mx-auto w-full max-w-5xl space-y-5 p-4 sm:p-6" data-testid="strategy-lab-page">
      <header className="space-y-2">
        <h1 className="text-2xl font-semibold text-foreground">{text.title}</h1>
        <p className="max-w-3xl text-sm text-secondary-text">{text.intro}</p>
        <p className="text-xs font-medium text-muted-text">{text.observe}</p>
      </header>

      <section className="rounded-2xl border border-border bg-surface p-4 sm:p-5">
        <div className="flex flex-wrap items-end gap-4">
          <label className="flex min-w-36 flex-1 flex-col gap-2 text-sm text-secondary-text">
            {text.asset}
            <select aria-label={text.asset} className="input-surface h-10 rounded-lg border px-3 text-foreground"
              value={selected} onChange={(event) => changeSelection(event.target.value)} disabled={loadingList || !etfs.length}>
              {etfs.length === 0 ? <option value="">—</option> :
                etfs.map((code) => <option key={code} value={code}>{code}</option>)}
            </select>
          </label>
          <label className="flex min-w-32 flex-col gap-2 text-sm text-secondary-text">
            {text.simulations}
            <select aria-label={text.simulations} className="input-surface h-10 rounded-lg border px-3 text-foreground"
              value={trials} onChange={(event) => { requestId.current += 1; setTrials(Number(event.target.value)); setReport(null); setLoading(false); }}>
              {[100, 500, 1000, 4000].map((count) => <option key={count} value={count}>{count}</option>)}
            </select>
          </label>
          <button type="button" className="btn-primary" onClick={() => void run()} disabled={!selected || loading || loadingList}>
            {loading ? text.running : text.run}
          </button>
        </div>
        {listError && <p className="mt-3 text-sm text-red-500" role="alert">{text.loadError}</p>}
        {!loadingList && !listError && etfs.length === 0 && <p className="mt-3 text-sm text-muted-text">{text.noEtfs}</p>}
        {analysisError && <p className="mt-3 text-sm text-red-500" role="alert">{text.analysisError}</p>}
      </section>

      {!report && !loading && !analysisError &&
        <p className="text-sm text-muted-text">{text.noResult}</p>}

      <PaperJournalPanel />

      {report && metrics && (
        <section className="space-y-4" aria-label={text.title}>
          <div className="grid gap-3 sm:grid-cols-3">
            {[
              { label: text.strategy, value: percent(metrics.observedReturnPct) },
              { label: text.random, value: percent(metrics.randomMedianReturnPct) },
              { label: text.hold, value: percent(metrics.buyAndHoldReturnPct) },
            ].map(({ label, value }) => (
              <div key={label} className="rounded-2xl border border-border bg-surface p-4">
                <p className="text-xs text-secondary-text">{label}</p>
                <p className="mt-2 text-2xl font-semibold tabular-nums text-foreground">{value}</p>
              </div>
            ))}
          </div>
          <dl className="grid gap-3 rounded-2xl border border-border bg-surface p-4 text-sm sm:grid-cols-2">
            {[
              [text.exceed, percent(metrics.fractionRandomAtLeastObserved * 100)],
              [text.extremes, `${percent(metrics.randomP05ReturnPct)} / ${percent(metrics.randomP95ReturnPct)}`],
              [text.drawdown, percent(metrics.observedMaxDrawdownPct)],
              [text.medianDrawdown, percent(metrics.randomMedianMaxDrawdownPct)],
              [text.sample, `${metrics.distinctRandomSchedules} / ${metrics.simulations}`],
              [text.trades, String(metrics.entryCount)],
              [text.exposure, `${metrics.exposureBars} / ${metrics.totalBars}`],
              [text.period, `${report.historyStart} – ${report.historyEnd}`],
              [text.source, report.dataSource],
              [text.costs, `${report.feeBps} / ${report.slippageBps} bp`],
            ].map(([label, value]) => (
              <div key={label} className="flex justify-between gap-3 border-b border-border/50 py-2">
                <dt className="text-secondary-text">{label}</dt>
                <dd className="text-right font-medium text-foreground tabular-nums">{value}</dd>
              </div>
            ))}
          </dl>
          {!metrics.informative && <p role="alert" className="text-sm text-amber-600">{text.insufficient}</p>}
          <p className="text-xs text-muted-text">{text.warnings}</p>
        </section>
      )}
    </main>
  );
}
