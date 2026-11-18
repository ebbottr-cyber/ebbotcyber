import { useCallback, useEffect, useRef, useState } from 'react';
import { Activity, AlertTriangle, Database, Radar, RefreshCw, ShieldCheck, TrendingUp, Wallet } from 'lucide-react';
import { memeCoinApi, type MemeCoinOverview, type MemeCoinStrategyId, type MemeCoinDiscoveryResponse } from '../api/memeCoin';
import { AppPage, Badge, Card, PageHeader } from '../components/common';
import { useUiLanguage } from '../contexts/UiLanguageContext';
import type { UiLanguage } from '../i18n/uiText';

const CONTENT = {
  tr: {
    title: 'Meme Coin Stratejileri',
    intro: 'Solana için bağımsız iki strateji. Bu panelin ilk sürümü yalnızca hazırlık ve bağlantı durumunu gösterir.',
    refresh: 'Durumu yenile',
    unavailable: 'Strateji durumuna ulaşılamadı. Canlı veri veya işlem varmış gibi gösterilmiyor.',
    notConnected: 'Bağlı değil',
    planned: 'Sanal işlem planlandı',
    disabled: 'Canlı işlemler kapalı',
    newLaunch: 'Yeni Coin Avcısı',
    momentum: 'Momentum Avcısı',
    newLaunchInfo: 'Yeni token ve likidite havuzlarını tespit edip güvenlik incelemesi yapacak ayrı motor.',
    momentumInfo: 'Hacim, fiyat hareketi ve büyük cüzdan aktivitelerini inceleyecek ayrı motor.',
    strategy: 'Strateji ayrıntıları',
    sources: 'Planlanan veri kaynakları',
    checks: 'Planlanan risk kontrolleri',
    paper: 'Sanal işlem motoru',
    execution: 'Gerçek emir yürütme',
    ready: 'Etkin',
    pending: 'Henüz bağlı değil',
    data: 'Veri akışı',
    performance: 'Doğrulanmış performans',
    noResults: 'Henüz test işlemi veya performans kaydı bulunmuyor.',
    next: 'Sonraki geliştirme',
    nextInfo: 'Gerçek zamanlı Solana veri adaptörleri, risk filtreleri ve komisyon/kayma modellemeli sanal işlemler ayrı servis olarak eklenecek.',
    safety: 'Cüzdan bağlanmadı, alım satım yapılmıyor. Mevcut EBBot ve Solana Hype işlemleri değiştirilmedi.',
    noStrategies: 'Henüz kayıtlı strateji bulunmuyor.',
    scan: 'Aday coinleri tara',
    scanLoading: 'Taranıyor...',
    scanDisabled: 'Keşif özelliği sunucuda kapalı. MEME_COIN_DISCOVERY_ENABLED=true ile açılabilir.',
    scanUnavailable: 'Veri kaynağına ulaşılamıyor; aday listesi oluşturulmadı.',
    scanEmpty: 'Seçili koşullara uygun havuz bulunamadı.',
    scanResults: 'Araştırma adayları (alım sinyali değil)',
    scanNote: 'Havuz verileri gecikmeli olabilir. Token yetkileri, cüzdan dağılımı ve satılabilirlik doğrulanmadığı için tüm adaylar yalnızca izleme amaçlıdır.',
    scanScore: 'Araştırma puanı',
    scanLiquidity: 'Likidite (USD)',
    scanVolume: '5 dk hacim (USD)',
    scanChange: '5 dk değişim',
    scanAge: 'Havuz yaşı (dk)',
    scanTrades: 'Alış / Satış',
    scanUnverified: 'Güvenlik doğrulanmadı',
    scanTimestamp: 'Veri zamanı',
  },
  en: {
    title: 'Meme Coin Strategies',
    intro: 'Two isolated strategies for Solana. V1 shows preparation and connectivity only.',
    refresh: 'Refresh status',
    unavailable: 'Strategy status is unavailable. Live data and trades are not fabricated.',
    notConnected: 'Not connected',
    planned: 'Paper trading planned',
    disabled: 'Live trading disabled',
    newLaunch: 'New Launch Hunter',
    momentum: 'Momentum Hunter',
    newLaunchInfo: 'Independent engine planned to discover new tokens and liquidity pools with safety checks.',
    momentumInfo: 'Independent engine planned to examine volume, price action, and wallet activity.',
    strategy: 'Strategy details',
    sources: 'Planned data sources',
    checks: 'Planned risk checks',
    paper: 'Paper execution engine',
    execution: 'Real order execution',
    ready: 'Enabled',
    pending: 'Not connected yet',
    data: 'Data feed',
    performance: 'Verified performance',
    noResults: 'No simulation trades or performance results exist yet.',
    next: 'Next development',
    nextInfo: 'Build isolated live Solana data adapters, risk filters, and realistic simulated fills including fees and slippage.',
    safety: 'No wallet is connected and no trades are placed. Existing EBBot and Solana Hype operations are unchanged.',
    noStrategies: 'No strategies registered.',
    scan: 'Scan candidates',
    scanLoading: 'Scanning...',
    scanDisabled: 'Discovery is disabled on this server. Set MEME_COIN_DISCOVERY_ENABLED=true to opt in.',
    scanUnavailable: 'Market source unavailable. No candidates shown.',
    scanEmpty: 'No pools pass the selected research filters.',
    scanResults: 'Research candidates (not buy signals)',
    scanNote: 'Pool data may be delayed. Token authorities, holders and sellability are not verified; every candidate is watch-only.',
    scanScore: 'Research score',
    scanLiquidity: 'Liquidity (USD)',
    scanVolume: '5m volume (USD)',
    scanChange: '5m change',
    scanAge: 'Pool age (min)',
    scanTrades: 'Buys / sells',
    scanUnverified: 'Risk unverified',
    scanTimestamp: 'Snapshot at',
  },
  zh: {
    title: 'Meme Coin 策略',
    intro: '两个独立的 Solana 策略。V1 仅展示准备和连接状态。',
    refresh: '刷新状态',
    unavailable: '无法获取策略状态。不展示虚构的实时数据或交易。',
    notConnected: '未连接',
    planned: '计划模拟交易',
    disabled: '实盘已关闭',
    newLaunch: '新币发现',
    momentum: '动量发现',
    newLaunchInfo: '计划独立发现新代币及流动性池并进行安全检查。',
    momentumInfo: '计划独立分析成交量、价格波动和钱包活动。',
    strategy: '策略详情',
    sources: '计划数据源',
    checks: '计划风控检查',
    paper: '模拟执行引擎',
    execution: '实盘执行',
    ready: '已启用',
    pending: '尚未连接',
    data: '行情数据',
    performance: '已验证业绩',
    noResults: '尚无模拟交易或业绩记录。',
    next: '下一阶段',
    nextInfo: '搭建独立的 Solana 数据适配器、风控过滤器和包含费用及滑点的模拟成交。',
    safety: '未连接钱包、未执行交易。现有 EBBot 与 Solana Hype 不受影响。',
    noStrategies: '暂无策略。',
    scan: '扫描候选池',
    scanLoading: '扫描中...',
    scanDisabled: '服务器未启用扫描。设置 MEME_COIN_DISCOVERY_ENABLED=true 后启用。',
    scanUnavailable: '数据源不可用，未显示候选资产。',
    scanEmpty: '没有符合条件的流动性池。',
    scanResults: '研究候选（非买入信号）',
    scanNote: '池数据可能延迟。代币权限、持有分布和可卖性未验证，仅供观察。',
    scanScore: '研究评分',
    scanLiquidity: '流动性 (USD)',
    scanVolume: '5分钟成交额',
    scanChange: '5分钟涨跌',
    scanAge: '池年龄（分钟）',
    scanTrades: '买入 / 卖出',
    scanUnverified: '风险未验证',
    scanTimestamp: '快照时间',
  },
} satisfies Record<UiLanguage, Record<string, string>>;

const STRATEGY_DETAILS: Record<MemeCoinStrategyId, { icon: typeof Radar; accent: string }> = {
  new_launch: { icon: Radar, accent: 'text-cyan' },
  momentum: { icon: TrendingUp, accent: 'text-success' },
};

const RISK_LABELS: Record<string, Record<UiLanguage, string>> = {
  token_authorities: { tr: 'Token yetkileri', en: 'Token authorities', zh: '代币权限' },
  holder_concentration: { tr: 'Cüzdan yoğunlaşması', en: 'Holder concentration', zh: '持仓集中度' },
  liquidity: { tr: 'Likidite', en: 'Liquidity', zh: '流动性' },
  sell_simulation: { tr: 'Satış simülasyonu', en: 'Sell simulation', zh: '卖出模拟' },
  volume_quality: { tr: 'Hacim kalitesi', en: 'Volume integrity', zh: '成交量质量' },
  wallet_concentration: { tr: 'Cüzdan yoğunlaşması', en: 'Wallet concentration', zh: '钱包集中度' },
  price_impact: { tr: 'Fiyat etkisi', en: 'Price impact', zh: '价格冲击' },
};

export default function MemeCoinPage() {
  const { language } = useUiLanguage();
  const copy = CONTENT[language];
  const [overview, setOverview] = useState<MemeCoinOverview | null>(null);
  const [selected, setSelected] = useState<MemeCoinStrategyId>('new_launch');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);
  const [scanResult, setScanResult] = useState<MemeCoinDiscoveryResponse | null>(null);
  const [scanLoading, setScanLoading] = useState(false);
  const [scanError, setScanError] = useState(false);
  const scanRequestSeq = useRef(0);
  const requestSeq = useRef(0);

  const refresh = useCallback(async () => {
    const seq = ++requestSeq.current;
    setLoading(true);
    setError(false);
    try {
      const data = await memeCoinApi.getOverview();
      if (seq === requestSeq.current) setOverview(data);
    } catch {
      if (seq === requestSeq.current) {
        setOverview(null);
        setError(true);
      }
    } finally {
      if (seq === requestSeq.current) setLoading(false);
    }
  }, []);

  useEffect(() => {
    void refresh();
    return () => { requestSeq.current += 1; };
  }, [refresh]);

  const scanCandidates = useCallback(async () => {
    const seq = ++scanRequestSeq.current;
    setScanLoading(true);
    setScanError(false);
    setScanResult(null);
    try {
      const result = await memeCoinApi.scanCandidates(selected);
      if (seq === scanRequestSeq.current) setScanResult(result);
    } catch {
      if (seq === scanRequestSeq.current) {
        setScanResult(null);
        setScanError(true);
      }
    } finally {
      if (seq === scanRequestSeq.current) setScanLoading(false);
    }
  }, [selected]);

  useEffect(() => () => { scanRequestSeq.current += 1; }, []);

  const current = overview?.strategies.find((item) => item.id === selected) ?? overview?.strategies[0];
  const currentDetails = current ? STRATEGY_DETAILS[current.id] : undefined;
  const name = (id: MemeCoinStrategyId) => id === 'new_launch' ? copy.newLaunch : copy.momentum;

  return (
    <AppPage>
      <div className="space-y-5">
        <PageHeader
          eyebrow="SOLANA / EBBOT"
          title={copy.title}
          description={copy.intro}
          actions={
            <button type="button" className="btn-secondary inline-flex items-center gap-2" onClick={() => void refresh()} disabled={loading}>
              <RefreshCw className={`h-4 w-4 ${loading ? 'animate-spin' : ''}`} />
              {copy.refresh}
            </button>
          }
        />

        <Card className="space-y-3">
          <div className="flex flex-wrap items-center gap-2">
            <Badge variant="warning">{copy.planned}</Badge>
            <Badge variant="default">{copy.disabled}</Badge>
            <Badge variant="default">{copy.notConnected}</Badge>
          </div>
          <p className="flex gap-2 text-sm text-secondary-text"><ShieldCheck className="mt-0.5 h-4 w-4 shrink-0" />{copy.safety}</p>
        </Card>

        {error && <div role="alert"><Card className="flex gap-2 border border-danger/30 text-danger">
          <AlertTriangle className="h-5 w-5 shrink-0" />{copy.unavailable}
        </Card></div>}

        {!error && (
          <div className="grid gap-4 md:grid-cols-2">
            {overview?.strategies.map((item) => {
              const details = STRATEGY_DETAILS[item.id];
              const Icon = details.icon;
              return (
                <button
                  key={item.id}
                  type="button"
                  aria-pressed={selected === item.id}
                  onClick={() => {
                    scanRequestSeq.current += 1;
                    setSelected(item.id);
                    setScanResult(null);
                    setScanError(false);
                    setScanLoading(false);
                  }}
                  className={`rounded-2xl border p-5 text-left transition-colors ${selected === item.id ? 'border-cyan/60 bg-card shadow-soft-card' : 'border-border/60 bg-card/65 hover:bg-hover'}`}
                >
                  <div className="flex items-start justify-between gap-3">
                    <Icon className={`h-6 w-6 ${details.accent}`} />
                    <Badge>{copy.notConnected}</Badge>
                  </div>
                  <h2 className="mt-3 text-lg font-semibold text-foreground">{name(item.id)}</h2>
                  <p className="mt-1 text-sm text-secondary-text">{item.id === 'new_launch' ? copy.newLaunchInfo : copy.momentumInfo}</p>
                  <p className="mt-3 text-xs text-secondary-text">{copy.data}: {item.engineConnected ? copy.ready : copy.pending}</p>
                </button>
              );
            })}
            {loading && !overview && <Card>{copy.pending}</Card>}
            {!loading && !overview && !error && <Card>{copy.noStrategies}</Card>}
          </div>
        )}

        {current && currentDetails && !error && (
          <Card title={`${copy.strategy} — ${name(current.id)}`} className="space-y-5">
            <div className="grid gap-4 md:grid-cols-3">
              <div className="rounded-xl bg-elevated/60 p-4">
                <Database className="mb-2 h-5 w-5 text-secondary-text" />
                <p className="text-xs text-secondary-text">{copy.data}</p>
                <p className="mt-1 font-medium">{current.engineConnected ? copy.ready : copy.pending}</p>
              </div>
              <div className="rounded-xl bg-elevated/60 p-4">
                <Activity className="mb-2 h-5 w-5 text-secondary-text" />
                <p className="text-xs text-secondary-text">{copy.paper}</p>
                <p className="mt-1 font-medium">{current.paperTradingEnabled ? copy.ready : copy.pending}</p>
              </div>
              <div className="rounded-xl bg-elevated/60 p-4">
                <Wallet className="mb-2 h-5 w-5 text-secondary-text" />
                <p className="text-xs text-secondary-text">{copy.execution}</p>
                <p className="mt-1 font-medium">{current.liveTradingEnabled ? copy.ready : copy.disabled}</p>
              </div>
            </div>
            <div className="grid gap-5 md:grid-cols-2">
              <section>
                <h3 className="font-semibold">{copy.sources}</h3>
                <ul className="mt-2 list-inside list-disc space-y-1 text-sm text-secondary-text">
                  {current.dataSources.map((source) => <li key={source}>{source}</li>)}
                </ul>
              </section>
              <section>
                <h3 className="font-semibold">{copy.checks}</h3>
                <ul className="mt-2 list-inside list-disc space-y-1 text-sm text-secondary-text">
                  {current.riskChecks.map((check) => <li key={check}>{RISK_LABELS[check]?.[language] ?? check}</li>)}
                </ul>
              </section>
            </div>
          </Card>
        )}

        {current && !error && (
          <Card className="space-y-4">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <h3 className="font-semibold">{copy.scanResults}</h3>
              <button type="button" className="btn-secondary inline-flex items-center gap-2" onClick={() => void scanCandidates()} disabled={scanLoading}>
                <Radar className="h-4 w-4" />{scanLoading ? copy.scanLoading : copy.scan}
              </button>
            </div>
            <p className="text-xs text-secondary-text">{copy.scanNote}</p>
            {scanError && <p role="alert" className="text-sm text-danger">{copy.scanUnavailable}</p>}
            {scanResult?.status === 'disabled' && <p className="text-sm text-warning">{copy.scanDisabled}</p>}
            {scanResult?.status === 'unavailable' && <p role="alert" className="text-sm text-danger">{copy.scanUnavailable}</p>}
            {scanResult?.status === 'ok' && (
              <>
                <p className="text-xs text-secondary-text">{copy.scanTimestamp}: {scanResult.observedAt ?? '—'} · GeckoTerminal</p>
                {scanResult.candidates.length === 0 ? (
                  <p className="text-sm text-secondary-text">{copy.scanEmpty}</p>
                ) : (
                  <div className="overflow-x-auto">
                    <table className="w-full min-w-[720px] text-left text-xs">
                      <thead><tr className="border-b border-border/60 text-secondary-text">
                        <th className="p-2">Token</th><th className="p-2">{copy.scanScore}</th><th className="p-2">{copy.scanLiquidity}</th>
                        <th className="p-2">{copy.scanVolume}</th><th className="p-2">{copy.scanChange}</th>
                        <th className="p-2">{copy.scanAge}</th><th className="p-2">{copy.scanTrades}</th>
                      </tr></thead>
                      <tbody>{scanResult.candidates.map((coin) => (
                        <tr key={coin.tokenAddress} className="border-b border-border/40">
                          <td className="p-2">
                            <span className="font-semibold">{coin.symbol}</span>
                            <span className="block font-mono text-[10px] text-secondary-text">{coin.tokenAddress.slice(0, 6)}…{coin.tokenAddress.slice(-5)}</span>
                            <span className="text-[10px] text-warning">{copy.scanUnverified}</span>
                          </td>
                          <td className="p-2">{coin.researchScore.toFixed(1)}</td>
                          <td className="p-2">{coin.liquidityUsd.toLocaleString()}</td>
                          <td className="p-2">{coin.volume5mUsd.toLocaleString()}</td>
                          <td className="p-2">{coin.change5mPct.toFixed(2)}%</td>
                          <td className="p-2">{coin.ageMinutes.toFixed(0)}</td>
                          <td className="p-2">{coin.buys5m} / {coin.sells5m}</td>
                        </tr>
                      ))}</tbody>
                    </table>
                  </div>
                )}
              </>
            )}
          </Card>
        )}

        <div className="grid gap-4 md:grid-cols-2">
          <Card title={copy.performance}>
            <p className="text-sm text-secondary-text">{copy.noResults}</p>
          </Card>
          <Card title={copy.next}>
            <p className="text-sm text-secondary-text">{copy.nextInfo}</p>
          </Card>
        </div>
      </div>
    </AppPage>
  );
}
