import { useCallback, useEffect, useRef, useState } from 'react';
import { Activity, AlertTriangle, Database, Radar, RefreshCw, ShieldCheck, TrendingUp, Wallet } from 'lucide-react';
import { memeCoinApi, type MemeCoinOverview, type MemeCoinStrategyId } from '../api/memeCoin';
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

        {error && <Card className="flex gap-2 border border-danger/30 text-danger" role="alert">
          <AlertTriangle className="h-5 w-5 shrink-0" />{copy.unavailable}
        </Card>}

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
                  onClick={() => setSelected(item.id)}
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
