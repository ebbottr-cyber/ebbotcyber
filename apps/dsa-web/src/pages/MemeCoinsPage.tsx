import type React from 'react';
import { useEffect, useState } from 'react';
import { RefreshCw, ShieldAlert } from 'lucide-react';
import { useUiLanguage } from '../contexts/UiLanguageContext';
import type { UiLanguage } from '../i18n/uiText';
import { memeRadarApi, type MemeRadarStatus, type MemeScanResponse, type MemeStrategy } from '../api/memeRadar';

const COPY: Record<UiLanguage, Record<string, string>> = {
  tr: {
    title: 'Meme Coin Stratejileri',
    description: 'Solana Meme Radar · yalnızca gözlem ve sanal test hazırlığı, gerçek işlem yok.',
    enabled: 'Manuel canlı tarama etkin.',
    disabled: 'Canlı tarama sunucuda kapalı. MEME_RADAR_LIVE_ENABLED ayarını kontrol edin.',
    scan: 'Coinleri tara',
    scanning: 'Taranıyor...',
    all: 'Tüm stratejiler',
    new: 'Yeni Coin Avcısı',
    momentum: 'Momentum İzleyici',
    strategy: 'Strateji',
    token: 'Token',
    score: 'Puan',
    source: 'Kaynak',
    reasons: 'Filtre / risk gerekçeleri',
    watch: 'İzle',
    blocked: 'Riskli / engellendi',
    empty: 'Henüz tarama sonucu yok.',
    warning: 'Veri sağlayıcı uyarıları',
    loadError: 'Meme Radar durumu alınamadı.',
    scanError: 'Tarama tamamlanamadı. Sunucu ve veri kaynaklarını kontrol edin.',
    caution: 'Puanlar yatırım tavsiyesi veya alım-satım izni değildir.',
    cached: 'Önbellek',
  },
  en: {
    title: 'Meme Coin Strategies',
    description: 'Solana Meme Radar · monitoring only; no real transactions.',
    enabled: 'Manual live scan is enabled.',
    disabled: 'Live scans are disabled on the server (MEME_RADAR_LIVE_ENABLED).',
    scan: 'Scan tokens',
    scanning: 'Scanning...',
    all: 'All strategies',
    new: 'New Coin Hunter',
    momentum: 'Momentum Watcher',
    strategy: 'Strategy',
    token: 'Token',
    score: 'Score',
    source: 'Source',
    reasons: 'Filter / risk reasons',
    watch: 'Watch',
    blocked: 'Blocked',
    empty: 'No scan results yet.',
    warning: 'Data provider warnings',
    loadError: 'Could not load Meme Radar status.',
    scanError: 'Scan failed. Check server and providers.',
    caution: 'Scores are not investment advice or trade permissions.',
    cached: 'Cached',
  },
  zh: {
    title: '迷因币策略',
    description: 'Solana Meme Radar · 仅观察，不执行真实交易。',
    enabled: '可以手动扫描实时行情。',
    disabled: '服务器未启用实时扫描 (MEME_RADAR_LIVE_ENABLED)。',
    scan: '扫描代币',
    scanning: '扫描中...',
    all: '全部策略',
    new: '新币发现',
    momentum: '动量观察',
    strategy: '策略',
    token: '代币',
    score: '评分',
    source: '数据来源',
    reasons: '筛选与风险原因',
    watch: '观察',
    blocked: '已阻止',
    empty: '暂无扫描结果。',
    warning: '数据提供方警告',
    loadError: '无法获取 Meme Radar 状态。',
    scanError: '扫描失败，请检查服务器和数据源。',
    caution: '评分不是投资建议或交易许可。',
    cached: '缓存',
  },
};

const STRATEGIES: MemeStrategy[] = ['new_coin_hunter', 'momentum_watcher'];

const MemeCoinsPage: React.FC = () => {
  const { language } = useUiLanguage();
  const copy = COPY[language];
  const [status, setStatus] = useState<MemeRadarStatus | null>(null);
  const [result, setResult] = useState<MemeScanResponse | null>(null);
  const [filter, setFilter] = useState<MemeStrategy | 'all'>('all');
  const [loading, setLoading] = useState(true);
  const [scanning, setScanning] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    document.title = copy.title + ' - EBBot';
    let active = true;
    setLoading(true);
    memeRadarApi.status().then(
      (next) => { if (active) { setStatus(next); setError(''); } },
      () => { if (active) setError(copy.loadError); },
    ).finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [copy.title, copy.loadError]);

  const scan = async () => {
    if (scanning || !status?.live_enabled) return;
    setScanning(true);
    setError('');
    try {
      setResult(await memeRadarApi.scan(5));
    } catch {
      setError(copy.scanError);
    } finally {
      setScanning(false);
    }
  };

  const label = (strategy: MemeStrategy) => strategy === 'new_coin_hunter' ? copy.new : copy.momentum;
  const candidates = (result?.candidates ?? []).filter(
    (item) => filter === 'all' || item.strategy === filter,
  );

  return (
    <main className="mx-auto w-full max-w-6xl space-y-5 px-4 py-6 md:px-8" data-testid="meme-coins-page">
      <header>
        <p className="text-xs uppercase tracking-widest text-muted-text">Solana Meme Radar</p>
        <h1 className="mt-1 text-2xl font-bold text-foreground">{copy.title}</h1>
        <p className="mt-2 text-sm text-secondary-text">{copy.description}</p>
      </header>
      <section className="rounded-xl border border-border bg-card p-4">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <p role="status" className="text-sm text-secondary-text">
            {loading ? '...' : status?.live_enabled ? copy.enabled : copy.disabled}
          </p>
          <button
            type="button"
            onClick={() => void scan()}
            disabled={loading || scanning || !status?.live_enabled}
            className="inline-flex items-center gap-2 rounded-lg border border-border bg-surface px-4 py-2 text-sm font-semibold text-foreground disabled:cursor-not-allowed disabled:opacity-50"
          >
            <RefreshCw className="h-4 w-4" aria-hidden="true" />
            {scanning ? copy.scanning : copy.scan}
          </button>
        </div>
        <p className="mt-3 flex items-center gap-2 text-sm text-secondary-text">
          <ShieldAlert className="h-4 w-4 shrink-0" aria-hidden="true" />
          {copy.caution}
        </p>
        {error && <p role="alert" className="mt-3 text-sm text-danger">{error}</p>}
      </section>
      <section className="rounded-xl border border-border bg-card p-4">
        <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
          <h2 className="text-lg font-semibold text-foreground">{copy.strategy}</h2>
          <select
            aria-label={copy.strategy}
            value={filter}
            onChange={(event) => setFilter(event.target.value as MemeStrategy | 'all')}
            className="rounded-lg border border-border bg-surface px-3 py-2 text-sm text-foreground"
          >
            <option value="all">{copy.all}</option>
            {STRATEGIES.map((strategy) => (
              <option key={strategy} value={strategy}>{label(strategy)}</option>
            ))}
          </select>
        </div>
        {result?.cached && <p className="mb-3 text-xs text-muted-text">{copy.cached}</p>}
        {candidates.length ? (
          <div className="overflow-x-auto">
            <table className="w-full min-w-[680px] text-left text-sm">
              <thead className="border-b border-border text-xs uppercase text-muted-text">
                <tr>
                  <th className="px-3 py-2">{copy.strategy}</th>
                  <th className="px-3 py-2">{copy.token}</th>
                  <th className="px-3 py-2">{copy.score}</th>
                  <th className="px-3 py-2">{copy.source}</th>
                  <th className="px-3 py-2">{copy.reasons}</th>
                </tr>
              </thead>
              <tbody>
                {candidates.map((candidate) => (
                  <tr key={candidate.strategy + ':' + candidate.mint} className="border-b border-border/60 align-top">
                    <td className="px-3 py-3">
                      <div className="font-semibold text-foreground">{label(candidate.strategy)}</div>
                      <div className="text-xs text-muted-text">
                        {candidate.status === 'watch' ? copy.watch : copy.blocked}
                      </div>
                    </td>
                    <td className="px-3 py-3">
                      <div className="font-semibold text-foreground">{candidate.symbol}</div>
                      <div className="break-all font-mono text-xs text-secondary-text">{candidate.mint}</div>
                    </td>
                    <td className="px-3 py-3 font-semibold text-foreground">{candidate.score}/100</td>
                    <td className="px-3 py-3 text-secondary-text">{candidate.source}</td>
                    <td className="px-3 py-3 text-xs text-secondary-text">{candidate.reasons.join(', ') || '—'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : <p className="text-sm text-muted-text">{copy.empty}</p>}
        {Boolean(result?.errors.length) && (
          <div className="mt-4 rounded-lg border border-border p-3">
            <h3 className="font-semibold text-foreground">{copy.warning}</h3>
            {result?.errors.map((item, index) => (
              <p key={item.provider + index} className="mt-1 text-xs text-secondary-text">
                {item.provider}: {item.message}
              </p>
            ))}
          </div>
        )}
      </section>
    </main>
  );
};

export default MemeCoinsPage;
