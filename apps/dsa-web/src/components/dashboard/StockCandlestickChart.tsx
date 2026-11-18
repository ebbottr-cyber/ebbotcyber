import type React from 'react';
import { useEffect, useMemo, useRef, useState } from 'react';
import { LineChart } from 'lucide-react';
import { stocksApi, type StockHistoryCandle } from '../../api/stocks';

type Days = 30 | 90 | 180 | 365;
type LoadState = 'loading' | 'ready' | 'empty' | 'error';

type Props = {
  stockCode: string;
  refreshKey?: number;
  fallback?: React.ReactNode;
};

const RANGES: ReadonlyArray<{ days: Days; label: string }> = [
  { days: 30, label: '1A' },
  { days: 90, label: '3A' },
  { days: 180, label: '6A' },
  { days: 365, label: '1Y' },
];

const priceFormat = new Intl.NumberFormat('tr-TR', { maximumFractionDigits: 2 });
const volumeFormat = new Intl.NumberFormat('tr-TR', { notation: 'compact', maximumFractionDigits: 1 });
const validCandle = (c: StockHistoryCandle): boolean => (
  Boolean(c.date) &&
  Number.isFinite(Date.parse(c.date)) &&
  [c.open, c.high, c.low, c.close].every((v) => Number.isFinite(v) && v > 0) &&
  c.low <= Math.min(c.open, c.close) &&
  c.high >= Math.max(c.open, c.close) &&
  c.low <= c.high
);

export function normalizeCandles(rows: StockHistoryCandle[]): StockHistoryCandle[] {
  // Keep only coherent OHLC bars, then deduplicate by trading date.
  const dates = new Map<string, StockHistoryCandle>();
  rows.filter(validCandle).forEach((candle) => dates.set(candle.date, candle));
  return Array.from(dates.values()).sort((a, b) => a.date.localeCompare(b.date));
}

function CandlesSvg({ candles, stockCode }: { candles: StockHistoryCandle[]; stockCode: string }) {
  const width = Math.max(720, 86 + candles.length * 7);
  const left = 62;
  const right = width - 16;
  const top = 22;
  const bottom = 214;
  const priceHeight = bottom - top;
  const volumeTop = 236;
  const volumeHeight = 42;
  const highs = candles.map((c) => c.high);
  const lows = candles.map((c) => c.low);
  const topValue = Math.max(...highs);
  const bottomValue = Math.min(...lows);
  const padding = Math.max((topValue - bottomValue) * 0.06, topValue * 0.004, 0.01);
  const max = topValue + padding;
  const min = Math.max(0, bottomValue - padding);
  const yFor = (price: number) => top + (max - price) / (max - min) * priceHeight;
  const step = (right - left) / Math.max(1, candles.length);
  const barWidth = Math.max(2, Math.min(8, step * 0.58));
  const maxVolume = Math.max(1, ...candles.map((c) => c.volume ?? 0).filter((v) => Number.isFinite(v) && v > 0));
  const labelPoints = [0, 0.25, 0.5, 0.75, 1].map((fraction) =>
    Math.round((candles.length - 1) * fraction));

  return (
    <svg
      role="img"
      aria-label={stockCode + ' günlük mum grafiği; ' + candles.length + ' işlem günü'}
      viewBox={'0 0 ' + width + ' 306'}
      width={width}
      height={306}
      className="block h-auto max-w-none"
    >
      <title>{stockCode} — doğrulanmış günlük açılış, en yüksek, en düşük, kapanış ve hacim</title>
      {Array.from({ length: 5 }, (_, index) => {
        const price = min + (max - min) * index / 4;
        const y = yFor(price);
        return (
          <g key={index}>
            <line x1={left} y1={y} x2={right} y2={y} stroke="#e4ecf7" strokeDasharray="3 4" />
            <text x={left - 9} y={y + 4} fontSize="10" textAnchor="end" fill="#7185a3">
              {priceFormat.format(price)}
            </text>
          </g>
        );
      })}
      {candles.map((c, i) => {
        const x = left + (i + 0.5) * step;
        const rising = c.close >= c.open;
        const color = rising ? '#18a77c' : '#e05f68';
        const yOpen = yFor(c.open);
        const yClose = yFor(c.close);
        const bodyTop = Math.min(yOpen, yClose);
        const bodyHeight = Math.max(1.3, Math.abs(yClose - yOpen));
        const volume = typeof c.volume === 'number' && Number.isFinite(c.volume) && c.volume > 0
          ? c.volume : 0;
        const volumeBarHeight = volume / maxVolume * volumeHeight;
        return (
          <g key={c.date} data-testid="ebbot-candle" tabIndex={0} aria-label={
            c.date + ': açılış ' + priceFormat.format(c.open) +
            ', en yüksek ' + priceFormat.format(c.high) +
            ', en düşük ' + priceFormat.format(c.low) +
            ', kapanış ' + priceFormat.format(c.close)
          }>
            <title>{c.date + ' • Açılış: ' + priceFormat.format(c.open) +
              ' • Yüksek: ' + priceFormat.format(c.high) +
              ' • Düşük: ' + priceFormat.format(c.low) +
              ' • Kapanış: ' + priceFormat.format(c.close) +
              (volume > 0 ? ' • Hacim: ' + volumeFormat.format(volume) : '')}</title>
            <line x1={x} x2={x} y1={yFor(c.high)} y2={yFor(c.low)} stroke={color} strokeWidth="1.3" />
            <rect x={x - barWidth / 2} y={bodyTop} width={barWidth} height={bodyHeight} rx="0.7" fill={color} />
            {volume > 0 && (
              <rect x={x - barWidth / 2} y={volumeTop + volumeHeight - volumeBarHeight}
                width={barWidth} height={volumeBarHeight} fill={color} opacity="0.40" />
            )}
          </g>
        );
      })}
      <line x1={left} x2={right} y1={volumeTop} y2={volumeTop} stroke="#e7edf6" />
      <text x={left - 8} y={volumeTop + 12} textAnchor="end" fontSize="10" fill="#7185a3">Hacim</text>
      {labelPoints.map((point, i) => {
        const c = candles[point];
        const x = left + (point + 0.5) * step;
        return (
          <text key={i} x={x} y="298" textAnchor="middle" fontSize="10" fill="#7185a3">
            {c.date.slice(5, 10)}
          </text>
        );
      })}
    </svg>
  );
}

export function StockCandlestickChart({ stockCode, refreshKey = 0, fallback }: Props) {
  const [days, setDays] = useState<Days>(90);
  const [candles, setCandles] = useState<StockHistoryCandle[]>([]);
  const [status, setStatus] = useState<LoadState>('loading');
  const scroll = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const controller = new AbortController();
    if (!stockCode.trim()) return () => controller.abort();

    setStatus('loading');
    setCandles([]);
    stocksApi.getHistory(stockCode, { days, period: 'daily', signal: controller.signal })
      .then((response) => {
        if (controller.signal.aborted) return;
        const valid = normalizeCandles(response.data ?? []);
        setCandles(valid);
        setStatus(valid.length ? 'ready' : 'empty');
      })
      .catch(() => {
        if (!controller.signal.aborted) {
          setCandles([]);
          setStatus('error');
        }
      });
    return () => controller.abort();
  }, [stockCode, days, refreshKey]);

  useEffect(() => {
    if (status === 'ready' && scroll.current) {
      // Start at the latest candle on small screens; swipe left to inspect history.
      scroll.current.scrollLeft = scroll.current.scrollWidth;
    }
  }, [candles, status]);

  const last = useMemo(() => candles[candles.length - 1], [candles]);
  return (
    <div className="min-w-0" data-testid="stock-candlestick-chart">
      <div className="mb-3 flex flex-wrap items-center justify-between gap-3">
        <div>
          <p className="text-xs font-bold text-[#3d5f88]">Günlük mum grafiği</p>
          <p className="mt-0.5 text-[11px] text-[#8397b0]">Kaynak: EBBot hisse geçmişi API'si • Anlık veri değildir</p>
        </div>
        <div className="flex gap-1 rounded-xl bg-[#f0f5fc] p-1" role="group" aria-label="Grafik zaman aralığı">
          {RANGES.map((range) => (
            <button key={range.days} type="button" onClick={() => setDays(range.days)}
              aria-pressed={days === range.days}
              className={'min-h-9 min-w-10 rounded-lg px-2 text-xs font-bold transition ' +
                (days === range.days
                  ? 'bg-[#2977d5] text-white shadow-sm'
                  : 'text-[#627e9e] hover:bg-white')}>
              {range.label}
            </button>
          ))}
        </div>
      </div>
      {status === 'loading' && (
        <div role="status" className="flex min-h-[230px] items-center justify-center rounded-xl bg-[#f7faff] text-sm text-[#7389a6]">Gerçek mum verileri yükleniyor…</div>
      )}
      {status === 'ready' && candles.length > 0 && (
        <>
          <div ref={scroll} data-testid="candle-scroll" tabIndex={0}
            aria-label="Mum grafiği, yatay kaydırılabilir"
            className="w-full overflow-x-auto rounded-xl border border-[#e3ebf7] bg-[#fbfdff] p-2 focus-visible:outline focus-visible:outline-2 focus-visible:outline-[#2977d5]">
            <CandlesSvg candles={candles} stockCode={stockCode} />
          </div>
          <div className="mt-2 flex flex-wrap items-center justify-between gap-2 text-[11px] text-[#7c91aa]">
            <span>Son kayıtlı mum: {last.date} • Kapanış: {priceFormat.format(last.close)}</span>
            <span>{candles.length} mum • Mobilde grafiği yana kaydırın</span>
          </div>
        </>
      )}
      {(status === 'error' || status === 'empty') && (
        <div role="status">
          <div className="mb-3 flex items-center gap-2 rounded-xl border border-[#dce7f5] bg-[#f6faff] px-3 py-3 text-xs text-[#5e7798]">
            <LineChart className="h-4 w-4 shrink-0" />
            {status === 'error'
              ? 'Günlük mum verisi alınamadı. Yalnızca mevcut analiz kayıtları gösteriliyor.'
              : 'Bu sembol için seçilen dönemde günlük mum verisi bulunamadı.'}
          </div>
          {fallback}
        </div>
      )}
    </div>
  );
}

export default StockCandlestickChart;
