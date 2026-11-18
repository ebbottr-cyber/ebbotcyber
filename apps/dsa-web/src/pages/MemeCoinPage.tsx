import { useCallback, useEffect, useRef, useState } from 'react';
import { Activity, AlertTriangle, Database, Radar, RefreshCw, ShieldCheck, TrendingUp, Wallet } from 'lucide-react';
import { memeCoinApi, type MemeCoinOverview, type MemeCoinStrategyId, type MemeCoinDiscoveryResponse, type RobinhoodRpcStatus, type SolanaMintReview, type SolanaImpactEstimate } from '../api/memeCoin';
import { AppPage, Badge, Card, PageHeader } from '../components/common';
import { useUiLanguage } from '../contexts/UiLanguageContext';
import type { UiLanguage } from '../i18n/uiText';

const CONTENT = {
  tr: {
    title: 'Meme Coin Stratejileri',
    intro: 'Solana için iki bağımsız strateji ve Robinhood Chain için ayrı EVM modülü. Gerçek işlem yapılmaz.',
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
    robinhood: 'Robinhood Chain AI',
    robinhoodInfo: 'OpenCatz mimarisinden yararlanan, Solana sisteminden bağımsız EVM analiz modülü. DEX taraması ve ajanlar henüz bağlı değil.',
    robinhoodRpc: 'Robinhood Chain ağ durumu (yalnızca okuma)',
    robinhoodProbe: 'RPC bağlantısını kontrol et',
    robinhoodChecking: 'Kontrol ediliyor...',
    robinhoodDisabled: 'RPC kontrolü kapalı. MEME_COIN_ROBINHOOD_RPC_ENABLED=true ile açılabilir.',
    robinhoodUnavailable: 'Robinhood Chain RPC durumuna ulaşılamadı.',
    robinhoodMismatch: 'Ağ kimliği uyuşmuyor. Bu ağ güvenilir değil.',
    robinhoodHealthy: 'Ağ kimliği doğrulandı; bu sonuç token güvenliğini kanıtlamaz.',
    robinhoodNetwork: 'Ağ',
    robinhoodChainId: 'Chain ID',
    robinhoodBlock: 'Son blok',
    robinhoodWarning: 'OpenCatz, DEX taraması ve gerçek alım satım bağlı değil. Bu yalnızca RPC sağlık kontrolüdür.',
    robinhoodAgents: 'AI ajan modülleri (taslak)',
    inspect: 'Mint ve maliyeti incele',
    inspectTitle: 'Solana token ön incelemesi',
    inspectLoading: 'Kontrol ediliyor...',
    inspectAmount: 'Örnek işlem tutarı (USD)',
    mintDisabled: 'On-chain mint denetimi kapalı. MEME_COIN_SOLANA_MINT_AUDIT_ENABLED=true ile etkinleştirilebilir.',
    mintUnavailable: 'Mint kontrolü kullanılamıyor veya veri eksik.',
    mintBlocked: 'Token yetkisi kaynaklı engel veya desteklenmeyen program tespit edildi.',
    mintReviewOnly: 'Mint ve dondurma yetkisi kaldırılmış; bu tokenin güvenli olduğu anlamına GELMEZ.',
    mintAuthority: 'Yeni token basma yetkisi',
    freezeAuthority: 'Cüzdan dondurma yetkisi',
    authorityRevoked: 'Kaldırılmış',
    authorityActive: 'Aktif',
    authorityUnknown: 'Doğrulanamadı',
    unknownSafety: 'Likidite sahipliği, büyük cüzdanlar ve satış yapılabilirliği hâlâ doğrulanmadı. İşlem engeli devam ediyor.',
    impactTitle: 'Varsayımsal havuz maliyet modeli',
    impactWarning: '50/50 sabit çarpım AMM varsayımıdır; gerçek DEX teklifi, gerçek kayma veya gerçekleşecek fiyat değildir.',
    impactPct: 'Model fiyat etkisi',
    costPct: 'Model toplam maliyet',
    feeUsd: 'Model havuz komisyonu',
    worstUsd: 'Ek %1 fiyat değişimi sonrası model alt sınırı',
    impactBlocked: 'Model limitlerini aşıyor; sanal işlem araştırması engellendi.',
    inspectFailed: 'İnceleme verileri alınamadı.',
  },
  en: {
    title: 'Meme Coin Strategies',
    intro: 'Two independent Solana strategies plus a separate Robinhood Chain EVM module. Live trading is disabled.',
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
    robinhood: 'Robinhood Chain AI',
    robinhoodInfo: 'Independent EVM analysis module inspired by OpenCatz architecture. DEX scans and AI agents are not connected yet.',
    robinhoodRpc: 'Robinhood Chain network status (read-only)',
    robinhoodProbe: 'Check RPC connectivity',
    robinhoodChecking: 'Checking...',
    robinhoodDisabled: 'RPC probe is disabled. Set MEME_COIN_ROBINHOOD_RPC_ENABLED=true to opt in.',
    robinhoodUnavailable: 'Robinhood Chain RPC status is unavailable.',
    robinhoodMismatch: 'Chain ID mismatch. The endpoint cannot be trusted.',
    robinhoodHealthy: 'Network chain ID verified; this does not verify token safety.',
    robinhoodNetwork: 'Network',
    robinhoodChainId: 'Chain ID',
    robinhoodBlock: 'Latest block',
    robinhoodWarning: 'OpenCatz, DEX scanning and live trading are not connected. This is only an RPC health check.',
    robinhoodAgents: 'AI agent modules (planned)',
    inspect: 'Review mint & costs',
    inspectTitle: 'Solana token preliminary review',
    inspectLoading: 'Reviewing...',
    inspectAmount: 'Example order size (USD)',
    mintDisabled: 'On-chain mint audit is disabled. Opt in with MEME_COIN_SOLANA_MINT_AUDIT_ENABLED=true.',
    mintUnavailable: 'Mint review is unavailable or lacks required data.',
    mintBlocked: 'Token authority or unsupported program restriction identified.',
    mintReviewOnly: 'Mint and freeze authorities revoked, but this does NOT prove token safety.',
    mintAuthority: 'Mint authority',
    freezeAuthority: 'Freeze authority',
    authorityRevoked: 'Revoked',
    authorityActive: 'Active',
    authorityUnknown: 'Unknown',
    unknownSafety: 'Holder concentration, liquidity ownership and sellability are still unverified. Trading remains blocked.',
    impactTitle: 'Hypothetical pool cost model',
    impactWarning: 'Assumes 50/50 constant-product AMM; NOT an executable quote, actual slippage or real fill price.',
    impactPct: 'Modeled price impact',
    costPct: 'Modeled total cost',
    feeUsd: 'Modeled pool fee',
    worstUsd: 'Modeled floor after extra 1% adverse move',
    impactBlocked: 'Model limits exceeded; paper-trade research blocked.',
    inspectFailed: 'Could not retrieve review data.',
  },
  zh: {
    title: 'Meme Coin 策略',
    intro: 'Solana 双策略和独立的 Robinhood Chain EVM 模块。实盘交易关闭。',
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
    robinhood: 'Robinhood Chain AI',
    robinhoodInfo: '独立的 EVM 分析模块，借鉴 OpenCatz 架构；DEX 扫描和智能代理尚未连接。',
    robinhoodRpc: 'Robinhood Chain 网络状态（只读）',
    robinhoodProbe: '检测 RPC 连接',
    robinhoodChecking: '检测中...',
    robinhoodDisabled: 'RPC 检测未启用。设置 MEME_COIN_ROBINHOOD_RPC_ENABLED=true 后开启。',
    robinhoodUnavailable: 'Robinhood Chain RPC 状态不可用。',
    robinhoodMismatch: '链 ID 不匹配，网络不可信。',
    robinhoodHealthy: '网络 ID 已验证；不代表代币安全。',
    robinhoodNetwork: '网络',
    robinhoodChainId: 'Chain ID',
    robinhoodBlock: '最新区块',
    robinhoodWarning: '尚未连接 OpenCatz、DEX 扫描或实盘。这里只检测 RPC 健康状态。',
    robinhoodAgents: 'AI 代理模块（规划中）',
    inspect: '检查 Mint 与成本',
    inspectTitle: 'Solana 代币初步检查',
    inspectLoading: '检查中...',
    inspectAmount: '模拟订单金额（美元）',
    mintDisabled: '链上 Mint 检查未开启。设置 MEME_COIN_SOLANA_MINT_AUDIT_ENABLED=true 后启用。',
    mintUnavailable: 'Mint 检查不可用或缺少数据。',
    mintBlocked: '检测到代币权限风险或不支持的程序。',
    mintReviewOnly: '铸造和冻结权限已撤销，但不表示代币安全。',
    mintAuthority: '铸币权限',
    freezeAuthority: '冻结权限',
    authorityRevoked: '已撤销',
    authorityActive: '有效',
    authorityUnknown: '未知',
    unknownSafety: '持仓集中度、流动性所有权和可卖性仍未验证，交易继续禁止。',
    impactTitle: '假设的资金池成本模型',
    impactWarning: '采用 50/50 恒定乘积模型，不是真实 DEX 报价、真实滑点或成交价格。',
    impactPct: '模型价格影响',
    costPct: '模型总成本',
    feeUsd: '模型手续费',
    worstUsd: '额外 1% 不利波动后的模型下限',
    impactBlocked: '超出模型限制，不允许模拟研究。',
    inspectFailed: '无法获取检查数据。',
  },
} satisfies Record<UiLanguage, Record<string, string>>;

const STRATEGY_DETAILS: Record<MemeCoinStrategyId, { icon: typeof Radar; accent: string }> = {
  new_launch: { icon: Radar, accent: 'text-cyan' },
  momentum: { icon: TrendingUp, accent: 'text-success' },
  robinhood_chain: { icon: Radar, accent: 'text-purple' },
};

const RISK_LABELS: Record<string, Record<UiLanguage, string>> = {
  token_authorities: { tr: 'Token yetkileri', en: 'Token authorities', zh: '代币权限' },
  holder_concentration: { tr: 'Cüzdan yoğunlaşması', en: 'Holder concentration', zh: '持仓集中度' },
  liquidity: { tr: 'Likidite', en: 'Liquidity', zh: '流动性' },
  sell_simulation: { tr: 'Satış simülasyonu', en: 'Sell simulation', zh: '卖出模拟' },
  volume_quality: { tr: 'Hacim kalitesi', en: 'Volume integrity', zh: '成交量质量' },
  wallet_concentration: { tr: 'Cüzdan yoğunlaşması', en: 'Wallet concentration', zh: '钱包集中度' },
  price_impact: { tr: 'Fiyat etkisi', en: 'Price impact', zh: '价格冲击' },
  evm_contract_permissions: { tr: 'Akıllı sözleşme yetkileri', en: 'Smart contract permissions', zh: '智能合约权限' },
  pool_liquidity: { tr: 'Havuz likiditesi', en: 'Pool liquidity', zh: '资金池流动性' },
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
  const [researchAmount, setResearchAmount] = useState(25);
  const [researchTarget, setResearchTarget] = useState<{ mint: string; symbol: string } | null>(null);
  const [mintResearch, setMintResearch] = useState<SolanaMintReview | null>(null);
  const [impactResearch, setImpactResearch] = useState<SolanaImpactEstimate | null>(null);
  const [mintResearchError, setMintResearchError] = useState(false);
  const [impactResearchError, setImpactResearchError] = useState(false);
  const [researchLoading, setResearchLoading] = useState(false);
  const researchRequestSeq = useRef(0);
  const [robinhoodStatus, setRobinhoodStatus] = useState<RobinhoodRpcStatus | null>(null);
  const [robinhoodLoading, setRobinhoodLoading] = useState(false);
  const [robinhoodError, setRobinhoodError] = useState(false);
  const robinhoodRequestSeq = useRef(0);
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
    if (selected === 'robinhood_chain') return;
    const seq = ++scanRequestSeq.current;
    setScanLoading(true);
    setScanError(false);
    setScanResult(null);
    researchRequestSeq.current += 1;
    setResearchTarget(null);
    setMintResearch(null);
    setImpactResearch(null);
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

  const inspectSolanaCandidate = useCallback(async (mint: string, symbol: string, liquidityUsd: number) => {
    const seq = ++researchRequestSeq.current;
    setResearchTarget({ mint, symbol });
    setMintResearch(null);
    setImpactResearch(null);
    setMintResearchError(false);
    setImpactResearchError(false);
    setResearchLoading(true);
    const [mintResponse, impactResponse] = await Promise.allSettled([
      memeCoinApi.reviewSolanaMint(mint),
      memeCoinApi.estimateSolanaImpact(liquidityUsd, researchAmount),
    ]);
    if (seq !== researchRequestSeq.current) return;
    if (mintResponse.status === 'fulfilled') {
      setMintResearch(mintResponse.value);
    } else {
      setMintResearchError(true);
    }
    if (impactResponse.status === 'fulfilled') {
      setImpactResearch(impactResponse.value);
    } else {
      setImpactResearchError(true);
    }
    setResearchLoading(false);
  }, [researchAmount]);

  const checkRobinhood = useCallback(async () => {
    const seq = ++robinhoodRequestSeq.current;
    setRobinhoodLoading(true);
    setRobinhoodError(false);
    setRobinhoodStatus(null);
    try {
      const data = await memeCoinApi.getRobinhoodStatus();
      if (seq === robinhoodRequestSeq.current) setRobinhoodStatus(data);
    } catch {
      if (seq === robinhoodRequestSeq.current) {
        setRobinhoodStatus(null);
        setRobinhoodError(true);
      }
    } finally {
      if (seq === robinhoodRequestSeq.current) setRobinhoodLoading(false);
    }
  }, []);

  useEffect(() => () => {
    scanRequestSeq.current += 1;
    robinhoodRequestSeq.current += 1;
    researchRequestSeq.current += 1;
  }, []);

  const current = overview?.strategies.find((item) => item.id === selected) ?? overview?.strategies[0];
  const currentDetails = current ? STRATEGY_DETAILS[current.id] : undefined;
  const name = (id: MemeCoinStrategyId) => id === 'new_launch' ? copy.newLaunch : id === 'momentum' ? copy.momentum : copy.robinhood;
  const description = (id: MemeCoinStrategyId) => id === 'new_launch' ? copy.newLaunchInfo : id === 'momentum' ? copy.momentumInfo : copy.robinhoodInfo;

  return (
    <AppPage>
      <div className="space-y-5">
        <PageHeader
          eyebrow="SOLANA + ROBINHOOD CHAIN / EBBOT"
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
          <div className="grid gap-4 md:grid-cols-3">
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
                    robinhoodRequestSeq.current += 1;
                    researchRequestSeq.current += 1;
                    setResearchTarget(null);
                    setMintResearch(null);
                    setImpactResearch(null);
                    setResearchLoading(false);
                    setSelected(item.id);
                    setRobinhoodStatus(null);
                    setRobinhoodError(false);
                    setRobinhoodLoading(false);
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
                  <p className="mt-1 text-sm text-secondary-text">{description(item.id)}</p>
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
            {current.id === 'robinhood_chain' && current.agentModules && current.agentModules.length > 0 && (
              <section>
                <h3 className="mb-2 font-semibold">{copy.robinhoodAgents}</h3>
                <div className="grid gap-2 sm:grid-cols-2">
                  {current.agentModules.map((agent) => (
                    <div key={agent.id} className="flex items-center justify-between gap-2 rounded-lg bg-elevated/60 px-3 py-2 text-sm">
                      <span>{agent.name}</span><Badge>{copy.pending}</Badge>
                    </div>
                  ))}
                </div>
              </section>
            )}
          </Card>
        )}

        {current && current.market === 'solana' && !error && (
          <Card className="space-y-4">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <h3 className="font-semibold">{copy.scanResults}</h3>
              <button type="button" className="btn-secondary inline-flex items-center gap-2" onClick={() => void scanCandidates()} disabled={scanLoading}>
                <Radar className="h-4 w-4" />{scanLoading ? copy.scanLoading : copy.scan}
              </button>
            </div>
            <p className="text-xs text-secondary-text">{copy.scanNote}</p>
            <label className="flex flex-wrap items-center gap-2 text-sm" htmlFor="meme-research-amount">
              {copy.inspectAmount}
              <select
                id="meme-research-amount"
                className="rounded-lg border border-border bg-card px-3 py-1.5"
                value={researchAmount}
                onChange={(event) => {
                  researchRequestSeq.current += 1;
                  setResearchAmount(Number(event.target.value));
                  setResearchTarget(null);
                  setMintResearch(null);
                  setImpactResearch(null);
                  setResearchLoading(false);
                }}
              >
                <option value={25}>$25</option><option value={50}>$50</option><option value={100}>$100</option>
              </select>
            </label>
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
                        <th className="p-2">{copy.scanAge}</th><th className="p-2">{copy.scanTrades}</th><th className="p-2">{copy.inspectTitle}</th>
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
                          <td className="p-2">
                            <button type="button" className="btn-secondary whitespace-nowrap px-2 py-1 text-xs" onClick={() => void inspectSolanaCandidate(coin.tokenAddress, coin.symbol, coin.liquidityUsd)}>
                              {copy.inspect}
                            </button>
                          </td>
                        </tr>
                      ))}</tbody>
                    </table>
                  </div>
                )}
              </>
            )}
            {researchTarget && (
              <div className="space-y-3 border-t border-border/50 pt-3" aria-label={copy.inspectTitle}>
                <h4 className="font-semibold">{copy.inspectTitle}: {researchTarget.symbol}</h4>
                <p className="break-all font-mono text-xs text-secondary-text">{researchTarget.mint}</p>
                {researchLoading && <p className="text-sm text-secondary-text">{copy.inspectLoading}</p>}
                {(mintResearchError || impactResearchError) && <p role="alert" className="text-sm text-danger">{copy.inspectFailed}</p>}
                {mintResearch?.status === 'disabled' && <p className="text-sm text-warning">{copy.mintDisabled}</p>}
                {mintResearch && ['unavailable','unsupported'].includes(mintResearch.status) && <p className="text-sm text-danger">{copy.mintUnavailable}</p>}
                {mintResearch?.status === 'screened' && (
                  <div className="space-y-2">
                    <p className="text-sm">{mintResearch.verdict === 'blocked' ? copy.mintBlocked : copy.mintReviewOnly}</p>
                    <div className="grid gap-2 sm:grid-cols-2">
                      <p className="text-sm">{copy.mintAuthority}: {mintResearch.mintAuthorityRevoked === null ? copy.authorityUnknown : mintResearch.mintAuthorityRevoked ? copy.authorityRevoked : copy.authorityActive}</p>
                      <p className="text-sm">{copy.freezeAuthority}: {mintResearch.freezeAuthorityRevoked === null ? copy.authorityUnknown : mintResearch.freezeAuthorityRevoked ? copy.authorityRevoked : copy.authorityActive}</p>
                    </div>
                    {mintResearch.blockingReasons.length > 0 && <p className="text-xs text-danger">{mintResearch.blockingReasons.join(', ')}</p>}
                  </div>
                )}
                {impactResearch && (
                  <div className="space-y-2 rounded-xl bg-elevated/60 p-3">
                    <h5 className="font-semibold">{copy.impactTitle}</h5>
                    <p className="text-xs text-secondary-text">{copy.impactWarning}</p>
                    <div className="grid grid-cols-2 gap-3 text-sm md:grid-cols-4">
                      <p>{copy.impactPct}: {impactResearch.modeledPriceImpactPct.toFixed(2)}%</p>
                      <p>{copy.costPct}: {impactResearch.modeledTotalCostPct.toFixed(2)}%</p>
                      <p>{copy.feeUsd}: ${impactResearch.modeledFeeUsd.toFixed(4)}</p>
                      <p>{copy.worstUsd}: ${impactResearch.modeledMinOutputValueUsd.toFixed(2)}</p>
                    </div>
                    {impactResearch.paperReviewStatus === 'blocked' && <p className="text-sm text-danger">{copy.impactBlocked}</p>}
                  </div>
                )}
                <p className="text-xs text-warning">{copy.unknownSafety}</p>
              </div>
            )}
          </Card>
        )}

        {current?.id === 'robinhood_chain' && !error && (
          <Card className="space-y-4" title={copy.robinhoodRpc}>
            <div className="flex flex-wrap items-center justify-between gap-3">
              <p className="text-sm text-secondary-text">{copy.robinhoodWarning}</p>
              <button type="button" className="btn-secondary inline-flex items-center gap-2" onClick={() => void checkRobinhood()} disabled={robinhoodLoading}>
                <RefreshCw className={`h-4 w-4 ${robinhoodLoading ? 'animate-spin' : ''}`} />
                {robinhoodLoading ? copy.robinhoodChecking : copy.robinhoodProbe}
              </button>
            </div>
            {robinhoodError && <p role="alert" className="text-sm text-danger">{copy.robinhoodUnavailable}</p>}
            {robinhoodStatus?.status === 'disabled' && <p className="text-sm text-warning">{copy.robinhoodDisabled}</p>}
            {robinhoodStatus?.status === 'unavailable' && <p role="alert" className="text-sm text-danger">{copy.robinhoodUnavailable}</p>}
            {robinhoodStatus?.status === 'mismatch' && <p role="alert" className="text-sm text-danger">{copy.robinhoodMismatch}</p>}
            {robinhoodStatus?.status === 'ok' && (
              <>
                <Badge variant="success">{copy.robinhoodHealthy}</Badge>
                <div className="grid grid-cols-3 gap-3 text-xs">
                  <div><p className="text-secondary-text">{copy.robinhoodNetwork}</p><p>{robinhoodStatus.network}</p></div>
                  <div><p className="text-secondary-text">{copy.robinhoodChainId}</p><p>{robinhoodStatus.chainIdSeen}</p></div>
                  <div><p className="text-secondary-text">{copy.robinhoodBlock}</p><p>{robinhoodStatus.blockNumber?.toLocaleString() ?? '—'}</p></div>
                </div>
                <p className="text-xs text-secondary-text">{robinhoodStatus.checkedAt}</p>
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
