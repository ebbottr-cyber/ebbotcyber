/** Purely descriptive indicators from validated daily closing prices. */
export type TechnicalIndicators = {
  rsi14: number | null;
  ema20: number | null;
  ema50: number | null;
  macd: number | null;
  macdSignal: number | null;
  macdHistogram: number | null;
};
const valid = (values: readonly number[]) => values.every((x) => Number.isFinite(x) && x > 0);
const safe = (value: number): number | null => Number.isFinite(value) ? value : null;

/** EMA seeded with the first period's simple moving average. */
export function emaSeries(values: readonly number[], period: number, allowSigned = false): Array<number | null> {
  const result: Array<number | null> = Array(values.length).fill(null);
  if (!Number.isInteger(period) || period < 1 || values.length < period ||
      values.some((x) => !Number.isFinite(x) || (!allowSigned && x <= 0))) return result;
  const alpha = 2 / (period + 1);
  let ema = values.slice(0, period).reduce((a, b) => a + b, 0) / period;
  result[period - 1] = safe(ema);
  for (let i = period; i < values.length; i += 1) {
    ema += (values[i] - ema) * alpha;
    result[i] = safe(ema);
  }
  return result;
}

/** Wilder RSI(14); 15 or more closing prices required. */
export function rsi14(values: readonly number[]): number | null {
  if (values.length < 15 || !valid(values)) return null;
  let gains = 0;
  let losses = 0;
  for (let i = 1; i <= 14; i += 1) {
    const change = values[i] - values[i - 1];
    gains += Math.max(0, change);
    losses += Math.max(0, -change);
  }
  gains /= 14;
  losses /= 14;
  for (let i = 15; i < values.length; i += 1) {
    const change = values[i] - values[i - 1];
    gains = (13 * gains + Math.max(0, change)) / 14;
    losses = (13 * losses + Math.max(0, -change)) / 14;
  }
  if (!Number.isFinite(gains) || !Number.isFinite(losses)) return null;
  if (gains === 0 && losses === 0) return 50;
  if (losses === 0) return 100;
  if (gains === 0) return 0;
  return safe(100 - 100 / (1 + gains / losses));
}

/** MACD(12,26,9) becomes available after 34 price observations. */
export function calculateIndicators(values: readonly number[]): TechnicalIndicators {
  const result: TechnicalIndicators = {
    rsi14: null, ema20: null, ema50: null,
    macd: null, macdSignal: null, macdHistogram: null,
  };
  if (!values.length || !valid(values)) return result;
  result.rsi14 = rsi14(values);
  const ema20 = emaSeries(values, 20);
  const ema50 = emaSeries(values, 50);
  result.ema20 = ema20[ema20.length - 1] ?? null;
  result.ema50 = ema50[ema50.length - 1] ?? null;
  const e12 = emaSeries(values, 12);
  const e26 = emaSeries(values, 26);
  const macdValues: number[] = [];
  for (let i = 25; i < values.length; i += 1) {
    const short = e12[i];
    const long = e26[i];
    if (typeof short === 'number' && typeof long === 'number') {
      const delta = safe(short - long);
      if (delta !== null) macdValues.push(delta);
    }
  }
  if (macdValues.length < 9) return result;
  const signal = emaSeries(macdValues, 9, true);
  const latestMacd = macdValues[macdValues.length - 1];
  const latestSignal = signal[signal.length - 1];
  if (typeof latestMacd === 'number' && typeof latestSignal === 'number') {
    result.macd = latestMacd;
    result.macdSignal = latestSignal;
    result.macdHistogram = safe(latestMacd - latestSignal);
  }
  return result;
}
