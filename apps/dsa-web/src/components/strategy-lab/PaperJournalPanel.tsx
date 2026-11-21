import { useRef, useState } from 'react';
import { inspectPaperJournal, type PaperJournalSummary } from '../../api/strategyLab';
import { useUiLanguage } from '../../contexts/UiLanguageContext';
import type { UiLanguage } from '../../i18n/uiText';

const WORDS: Record<UiLanguage, {
  title: string; intro: string; select: string; empty: string; pending: string;
  failed: string; tooLarge: string; unverified: string; last: string;
  first: string; samples: string; source: string; returnLabel: string;
  drawdown: string; bought: string; sold: string; next: string;
  rows: string; session: string; action: string; equity: string; position: string;
  invested: string; cash: string; checked: string;
}> = {
  tr: {
    title: 'Sanal İşlem Günlüğü', intro: 'Kendi V9 .jsonl dosyanı seç. Günlük yalnızca doğrulanıp özetlenir; sunucuda saklanmaz ve al/sat emri verilmez.',
    select: 'Günlüğü kontrol et (.jsonl)', empty: 'Henüz sanal işlem günlüğü seçilmedi.',
    pending: 'Günlük doğrulanıyor…', failed: 'Günlük doğrulanamadı. Dosya bozuk olabilir veya yönetici girişi gerekli olabilir.',
    tooLarge: 'Dosya sınırı 512 KiB.', unverified: 'Bu sanal sonuçlar dışarıdan onaylanmış piyasa performansı değildir.',
    last: 'Son kayıt', first: 'İlk kayıt', samples: 'Gün sayısı',
    source: 'Veri kaynağı', returnLabel: 'Sanal getiri', drawdown: 'Sanal maksimum düşüş',
    bought: 'Sanal alım', sold: 'Sanal satım', next: 'Beklenen sonraki seans',
    rows: 'Son sanal kayıtlar', session: 'Seans', action: 'İşlem',
    equity: 'Sanal bakiye', position: 'Pozisyon', invested: 'ETF', cash: 'Nakit',
    checked: 'Kayıt bütünlüğü doğrulandı',
  },
  en: {
    title: 'Prospective Paper Journal', intro: 'Choose your local V9 .jsonl file. It is validated and summarized but not stored by the server; no orders are placed.',
    select: 'Inspect journal (.jsonl)', empty: 'No paper journal selected.',
    pending: 'Validating journal…', failed: 'Unable to validate journal. It may be corrupt or admin login may be required.',
    tooLarge: 'File limit is 512 KiB.', unverified: 'These simulated results are not independently verified market performance.',
    last: 'Last record', first: 'First record', samples: 'Observed sessions',
    source: 'Data source', returnLabel: 'Virtual return', drawdown: 'Virtual max drawdown',
    bought: 'Paper buys', sold: 'Paper sells', next: 'Expected next session',
    rows: 'Recent paper records', session: 'Session', action: 'Action',
    equity: 'Virtual equity', position: 'Position', invested: 'ETF', cash: 'Cash',
    checked: 'Record integrity checked',
  },
  zh: {
    title: '前瞻模拟交易日志', intro: '选择本地 V9 .jsonl 文件。仅验证并显示摘要，服务器不保留文件，也不会下单。',
    select: '检查日志 (.jsonl)', empty: '尚未选择模拟日志。',
    pending: '正在校验日志…', failed: '日志无法验证，文件可能已损坏或需管理员登录。',
    tooLarge: '文件上限为 512 KiB。', unverified: '这些模拟数据不是独立核实的市场表现。',
    last: '最新记录', first: '首次记录', samples: '观察交易日数',
    source: '数据来源', returnLabel: '模拟收益', drawdown: '模拟最大回撤',
    bought: '模拟买入', sold: '模拟卖出', next: '预计下一交易日',
    rows: '近期模拟记录', session: '日期', action: '操作',
    equity: '模拟净值', position: '持仓', invested: 'ETF', cash: '现金',
    checked: '记录完整性校验通过',
  },
};

function pct(value: number): string {
  return Number.isFinite(value) ? `${value.toFixed(2)}%` : '—';
}

export default function PaperJournalPanel() {
  const { language } = useUiLanguage();
  const labels = WORDS[language];
  const [report, setReport] = useState<PaperJournalSummary | null>(null);
  const [pending, setPending] = useState(false);
  const [error, setError] = useState('');
  const revision = useRef(0);

  const onFile = async (file?: File) => {
    const id = ++revision.current;
    setReport(null);
    setError('');
    if (!file) return;
    if (file.size > 524288) {
      setError(labels.tooLarge);
      return;
    }
    setPending(true);
    try {
      const raw = await file.text();
      // Server also enforces the 512-KiB UTF-8 byte limit.
      if (new TextEncoder().encode(raw).length > 524288) {
        if (id === revision.current) setError(labels.tooLarge);
        return;
      }
      const next = await inspectPaperJournal(raw);
      if (id === revision.current) setReport(next);
    } catch {
      if (id === revision.current) setError(labels.failed);
    } finally {
      if (id === revision.current) setPending(false);
    }
  };

  return (
    <section className="space-y-3 rounded-2xl border border-border bg-surface p-4 sm:p-5"
      aria-label={labels.title} data-testid="paper-journal-panel">
      <h2 className="text-lg font-semibold text-foreground">{labels.title}</h2>
      <p className="text-sm text-secondary-text">{labels.intro}</p>
      <label className="block max-w-md space-y-2 text-sm text-secondary-text">
        <span>{labels.select}</span>
        <input aria-label={labels.select} type="file" accept=".jsonl,text/plain"
          className="block w-full text-sm text-foreground"
          onChange={(event) => { void onFile(event.target.files?.[0]); }}
          disabled={pending} />
      </label>
      {pending && <p className="text-sm text-muted-text">{labels.pending}</p>}
      {error && <p role="alert" className="text-sm text-red-500">{error}</p>}
      {!pending && !error && !report && <p className="text-sm text-muted-text">{labels.empty}</p>}
      {report && (
        <div className="space-y-3">
          <p className="text-sm text-secondary-text">{labels.checked} · {report.assetCode} · {report.source}</p>
          <dl className="grid gap-3 sm:grid-cols-3">
            {[
              [labels.returnLabel, pct(report.observedReturnPct)],
              [labels.drawdown, pct(report.observedMaxDrawdownPct)],
              [labels.samples, String(report.recordCount)],
              [labels.first, report.firstSession],
              [labels.last, report.lastSession],
              [labels.next, report.nextExpectedSession],
              [labels.bought, String(report.paperBuyCount)],
              [labels.sold, String(report.paperSellCount)],
              [labels.position, report.invested ? labels.invested : labels.cash],
            ].map(([name, value]) => (
              <div className="rounded-xl border border-border p-3" key={name}>
                <dt className="text-xs text-secondary-text">{name}</dt>
                <dd className="mt-1 font-semibold tabular-nums text-foreground">{value}</dd>
              </div>
            ))}
          </dl>
          <h3 className="text-sm font-semibold text-foreground">{labels.rows}</h3>
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead><tr className="border-b border-border text-secondary-text">
                <th className="p-2">{labels.session}</th>
                <th className="p-2">{labels.action}</th>
                <th className="p-2">{labels.position}</th>
                <th className="p-2">{labels.equity}</th>
              </tr></thead>
              <tbody>{report.events.slice().reverse().map((entry) => (
                <tr className="border-b border-border/50" key={entry.session}>
                  <td className="p-2">{entry.session}</td>
                  <td className="p-2">{entry.paperFill ?? '—'}</td>
                  <td className="p-2">{entry.paperInvested ? labels.invested : labels.cash}</td>
                  <td className="p-2 tabular-nums">{entry.equity.toFixed(4)}</td>
                </tr>
              ))}</tbody>
            </table>
          </div>
          <p className="text-xs text-muted-text">{labels.unverified}</p>
        </div>
      )}
    </section>
  );
}
