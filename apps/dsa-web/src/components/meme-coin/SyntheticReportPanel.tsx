import { useRef, useState, type ChangeEvent } from 'react';
import { Card } from '../common';
import type { UiLanguage } from '../../i18n/uiText';
import { MAX_SYNTHETIC_REPORT_BYTES, parseSyntheticReport, type SyntheticReport } from './syntheticReport';

const COPY = {
  tr: {
    title: 'Yerel sentetik test raporu',
    note: 'Bu rakamlar gerçek kazanç, gerçek işlem veya doğrulanmış performans değildir. Dosya yalnızca bu tarayıcıda okunur; sunucuya yüklenmez.',
    import: 'Yerel .json raporunu seç',
    invalid: 'Rapor okunamadı veya sentetik rapor sözleşmesine uymuyor.',
    empty: 'Henüz yerel rapor seçilmedi. Canlı işlemler ve sanal emir motoru kapalı.',
    count: 'Sentetik senaryo',
    pnl: 'Varsayımsal net kâr/zarar (USD)',
    wins: 'Varsayımsal kazançlı / kayıplı',
    rate: 'Varsayımsal kazanma oranı',
    drawdown: 'Varsayımsal en yüksek günlük kapanış düşüşü (USD)',
    timeline: 'Sentetik günlük sonuç karşılaştırması',
    day: 'Test günü',
    totalDaily: 'Ortak günlük PnL (USD)',
    cumulative: 'Birikimli varsayımsal PnL (USD)',
    noDays: 'Henüz karşılaştırılacak sentetik gün yok.',
    periodNote: 'Yalnızca kaydı olan günler gösterilir; gün içi değer veya gerçek piyasa performansı değildir.',
    kill: 'Kalıcı durdurma',
    on: 'Etkin',
    off: 'Devre dışı',
    newLaunch: 'Yeni Coin Avcısı',
    momentum: 'Momentum Avcısı',
    forget: 'Raporu kaldır',
    untrusted: 'Dosya kullanıcı tarafından seçilmiş, kaynağı kriptografik olarak doğrulanmamış test verisidir.',
  },
  en: {
    title: 'Local synthetic test report',
    note: 'These figures are not real profits, executed trades or verified performance. The file stays in this browser and is not uploaded.',
    import: 'Choose local .json report',
    invalid: 'Report is unreadable or not a valid synthetic research report.',
    empty: 'No local report selected. Live trading and paper order execution are disabled.',
    count: 'Synthetic scenarios',
    pnl: 'Hypothetical net P&L (USD)',
    wins: 'Hypothetical wins / losses',
    rate: 'Hypothetical win rate',
    drawdown: 'Hypothetical max daily-close drawdown (USD)',
    timeline: 'Synthetic daily outcome comparison',
    day: 'Research day',
    totalDaily: 'Combined daily PnL (USD)',
    cumulative: 'Cumulative hypothetical PnL (USD)',
    noDays: 'No synthetic days available for comparison.',
    periodNote: 'Only days with records are shown, not intraday results or real-market performance.',
    kill: 'Persistent kill switch',
    on: 'On',
    off: 'Off',
    newLaunch: 'New Launch Hunter',
    momentum: 'Momentum Hunter',
    forget: 'Clear report',
    untrusted: 'This is a user-selected, cryptographically unauthenticated research file.',
  },
  zh: {
    title: '本地合成测试报告',
    note: '数值并非真实收益、真实交易或已验证业绩。文件仅在浏览器中读取，不上传服务器。',
    import: '选择本地 .json 报告',
    invalid: '报告无法读取或不符合合成测试格式。',
    empty: '未选择本地报告，实盘及模拟下单均关闭。',
    count: '合成场景',
    pnl: '假设净损益 (USD)',
    wins: '假设盈利 / 亏损',
    rate: '假设胜率',
    drawdown: '假设日终最大回撤 (USD)',
    timeline: '合成每日结果对比',
    day: '测试日期',
    totalDaily: '合计每日盈亏 (USD)',
    cumulative: '累计假设盈亏 (USD)',
    noDays: '暂无可比较的合成交易日期。',
    periodNote: '仅显示有记录的日期，非日内或真实市场表现。',
    kill: '持久停止开关',
    on: '已启用',
    off: '已关闭',
    newLaunch: '新币发现',
    momentum: '动量发现',
    forget: '清除报告',
    untrusted: '该文件由用户选择，来源未通过加密认证。',
  },
} satisfies Record<UiLanguage, Record<string, string>>;

export function SyntheticReportPanel({ language }: { language: UiLanguage }) {
  const c = COPY[language];
  const [report, setReport] = useState<SyntheticReport | null>(null);
  const [invalid, setInvalid] = useState(false);
  const serial = useRef(0);

  const load = async (event: ChangeEvent<HTMLInputElement>) => {
    const input = event.currentTarget;
    const file = input.files?.[0];
    const request = ++serial.current;
    setReport(null);
    setInvalid(false);
    input.value = '';
    if (!file) return;
    if (!file.name.toLowerCase().endsWith('.json') || file.size > MAX_SYNTHETIC_REPORT_BYTES) {
      setInvalid(true);
      return;
    }
    try {
      const raw = await file.text();
      if (request !== serial.current) return;
      if (raw.length > MAX_SYNTHETIC_REPORT_BYTES) throw new Error('oversized_report');
      setReport(parseSyntheticReport(JSON.parse(raw)));
    } catch {
      if (request === serial.current) setInvalid(true);
    }
  };

  return (
    <Card title={c.title} className="space-y-4">
      <p className="text-sm text-warning">{c.note}</p>
      <label className="block text-sm text-secondary-text">
        <span className="mb-2 block">{c.import}</span>
        <input
          type="file"
          accept=".json,application/json"
          aria-label={c.import}
          onChange={(event) => { void load(event); }}
          className="block w-full text-sm text-secondary-text file:mr-4 file:rounded-lg file:border-0 file:bg-elevated file:px-3 file:py-2 file:text-foreground"
        />
      </label>
      {invalid && <p role="alert" className="text-sm text-danger">{c.invalid}</p>}
      {!report && !invalid && <p className="text-sm text-secondary-text">{c.empty}</p>}
      {report && (
        <div className="space-y-3">
          <p className="text-xs text-secondary-text">{c.untrusted}</p>
          <div className="grid gap-3 md:grid-cols-3">
            <div className="rounded-xl bg-elevated/60 p-3">
              <p className="text-xs text-secondary-text">{c.count}</p>
              <p className="mt-1 font-semibold">{report.eventCount}</p>
            </div>
            <div className="rounded-xl bg-elevated/60 p-3">
              <p className="text-xs text-secondary-text">{c.pnl}</p>
              <p className="mt-1 font-semibold">{report.syntheticNetPnlUsd}</p>
            </div>
            <div className="rounded-xl bg-elevated/60 p-3">
              <p className="text-xs text-secondary-text">{c.kill}</p>
              <p className="mt-1 font-semibold">{report.killSwitchLatched ? c.on : c.off}</p>
            </div>
          </div>
          <div className="grid gap-3 md:grid-cols-2">
            {(['new_launch', 'momentum'] as const).map((id) => {
              const s = report.strategies[id];
              return (
                <div key={id} className="rounded-xl border border-border/60 p-4">
                  <h3 className="font-semibold">{id === 'new_launch' ? c.newLaunch : c.momentum}</h3>
                  <p className="mt-2 text-xs text-secondary-text">{c.count}: {s.syntheticRoundTrips}</p>
                  <p className="mt-1 text-sm">{c.pnl}: <strong>{s.syntheticNetPnlUsd}</strong></p>
                  <p className="mt-1 text-xs text-secondary-text">{c.wins}: {s.syntheticWins} / {s.syntheticLosses}</p>
                  <p className="mt-1 text-xs text-secondary-text">{c.rate}: {s.syntheticWinRatePct === null ? "—" : `${s.syntheticWinRatePct}%`}</p>
                  <p className="mt-1 text-xs text-secondary-text">{c.drawdown}: {s.syntheticTimeline.maxSyntheticDrawdownUsd}</p>
                </div>
              );
            })}
          </div>
          <section aria-label={c.timeline} className="space-y-2">
            <h3 className="font-semibold">{c.timeline}</h3>
            <p className="text-xs text-secondary-text">{c.periodNote}</p>
            <p className="text-xs text-secondary-text">{c.drawdown}: {report.syntheticTimeline.maxSyntheticDrawdownUsd}</p>
            {report.syntheticTimeline.days.length === 0 ? (
              <p className="text-sm text-secondary-text">{c.noDays}</p>
            ) : (
              <div className="max-h-72 overflow-auto rounded-xl border border-border/60">
                <table className="w-full min-w-[640px] text-left text-xs">
                  <thead className="sticky top-0 bg-card text-secondary-text">
                    <tr>
                      <th scope="col" className="p-2">{c.day}</th>
                      <th scope="col" className="p-2">{c.newLaunch} (USD)</th>
                      <th scope="col" className="p-2">{c.momentum} (USD)</th>
                      <th scope="col" className="p-2">{c.totalDaily}</th>
                      <th scope="col" className="p-2">{c.cumulative}</th>
                    </tr>
                  </thead>
                  <tbody>
                    {report.syntheticTimeline.days.map((day) => {
                      const launch = report.strategies.new_launch.syntheticTimeline.days
                        .find((item) => item.day === day.day);
                      const momentum = report.strategies.momentum.syntheticTimeline.days
                        .find((item) => item.day === day.day);
                      return (
                        <tr key={day.day} className="border-t border-border/50">
                          <td className="p-2 font-mono">{day.day}</td>
                          <td className="p-2 tabular-nums">{launch?.syntheticDailyPnlUsd ?? '—'}</td>
                          <td className="p-2 tabular-nums">{momentum?.syntheticDailyPnlUsd ?? '—'}</td>
                          <td className="p-2 tabular-nums">{day.syntheticDailyPnlUsd}</td>
                          <td className="p-2 tabular-nums">{day.syntheticCumulativePnlUsd}</td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            )}
          </section>
          <button
            type="button"
            className="btn-secondary"
            onClick={() => { serial.current += 1; setReport(null); setInvalid(false); }}
          >
            {c.forget}
          </button>
        </div>
      )}
    </Card>
  );
}
