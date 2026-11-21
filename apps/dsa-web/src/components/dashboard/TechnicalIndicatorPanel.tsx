import { useMemo } from 'react';
import { Activity, Info } from 'lucide-react';
import type { StockHistoryCandle } from '../../api/stocks';
import { calculateIndicators } from '../../utils/technicalIndicators';

const format = (v: number | null): string => v === null ? '—' :
  new Intl.NumberFormat('tr-TR', { minimumFractionDigits: 2, maximumFractionDigits: 2 }).format(v);

function IndicatorRow({ label, value, note }: { label: string; value: string; note: string }) {
  return (
    <div className="border-b border-[#e5edf8] py-2.5 last:border-b-0">
      <div className="flex items-center justify-between gap-2">
        <dt className="text-[11px] font-semibold text-[#536b8c]">{label}</dt>
        <dd className="text-sm font-bold tabular-nums text-[#1d416c]">{value}</dd>
      </div>
      <p className="mt-1 text-[10px] leading-4 text-[#8899ae]">{note}</p>
    </div>
  );
}

export function TechnicalIndicatorPanel({ candles }: { candles: StockHistoryCandle[] }) {
  const summary = useMemo(() => calculateIndicators(candles.map((row) => row.close)), [candles]);
  const last = candles[candles.length - 1];
  const rsiNote = summary.rsi14 === null ? 'En az 15 kapanış gerekli.'
    : summary.rsi14 > 70 ? '70 üzeri RSI bölgesi.'
    : summary.rsi14 < 30 ? '30 altı RSI bölgesi.' : '30–70 RSI aralığı.';
  const macdNote = summary.macdHistogram === null ? 'En az 34 kapanış gerekli.'
    : summary.macdHistogram >= 0 ? 'MACD, sinyal çizgisinin üstünde.'
    : 'MACD, sinyal çizgisinin altında.';
  const emaNote = (ema: number | null, count: number) =>
    ema === null || !last ? 'En az ' + count + ' kapanış gerekli.'
    : last.close > ema ? 'Kapanış EMA üzerinde.'
    : last.close < ema ? 'Kapanış EMA altında.' : 'Kapanış EMA ile eşit.';
  return (
    <aside data-testid="technical-indicator-panel" aria-label="Günlük teknik göstergeler"
      className="min-w-0 rounded-xl border border-[#dce7f5] bg-[#f8fbff] p-3">
      <div className="flex items-center gap-2">
        <Activity className="h-4 w-4 text-[#247cd7]" />
        <h3 className="text-xs font-bold text-[#1b3f6c]">Teknik Göstergeler</h3>
      </div>
      <p className="mt-1 text-[10px] text-[#7c90ab]">Günlük kapanışlar • {last?.date ?? '—'}</p>
      <dl className="mt-2">
        <IndicatorRow label="RSI (14)" value={format(summary.rsi14)} note={rsiNote} />
        <IndicatorRow label="MACD (12/26/9)" value={format(summary.macd)} note={macdNote} />
        <IndicatorRow label="EMA (20)" value={format(summary.ema20)} note={emaNote(summary.ema20, 20)} />
        <IndicatorRow label="EMA (50)" value={format(summary.ema50)} note={emaNote(summary.ema50, 50)} />
      </dl>
      <p className="mt-2 flex items-start gap-1.5 rounded-lg bg-white px-2 py-2 text-[10px] leading-4 text-[#7c8ea5]">
        <Info className="mt-0.5 h-3.5 w-3.5 shrink-0" />
        Hesaplanan göstergelerdir; AI al/sat sinyali veya yatırım tavsiyesi değildir.
      </p>
    </aside>
  );
}
