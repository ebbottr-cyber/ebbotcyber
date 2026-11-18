/** Strict local-only, UNTRUSTED synthetic research report verification.
 * Never uses network, orders, persistence or real-market data.
 */
export type SyntheticReportStrategyId = 'new_launch' | 'momentum';

type SyntheticStrategy = {
  syntheticRoundTrips: number;
  syntheticWins: number;
  syntheticLosses: number;
  syntheticNetPnlUsd: string;
  syntheticWinRatePct: string | null;
  syntheticTimeline: SyntheticTimeline;
};
export type SyntheticDailyPoint = {
  day: string;
  syntheticDailyPnlUsd: string;
  syntheticCumulativePnlUsd: string;
  syntheticRoundTrips: number;
};
export type SyntheticTimeline = {
  days: SyntheticDailyPoint[];
  maxSyntheticDrawdownUsd: string;
  worstSyntheticDayUsd: string | null;
  positiveDays: number;
  negativeDays: number;
};

export type SyntheticReport = {
  eventCount: number;
  auditTipSha256: string;
  killSwitchLatched: boolean;
  startingSyntheticEquityUsd: string;
  endingSyntheticEquityUsd: string;
  syntheticNetPnlUsd: string;
  syntheticTimeline: SyntheticTimeline;
  strategies: Record<SyntheticReportStrategyId, SyntheticStrategy>;
};
export const MAX_SYNTHETIC_REPORT_BYTES = 262144;
const REPORT_FORMAT = 'ebbot-synthetic-report-v1';
const RECORD_FIELDS = [
  'assumed_fee_bps_per_side', 'assumed_slippage_bps_per_side',
  'event_id', 'realized_performance', 'strategy',
  'synthetic_net_pnl_usd', 'trade_executed', 'trading_day',
].sort().join(',');

function object(value: unknown): Record<string, unknown> {
  if (!value || typeof value !== 'object' || Array.isArray(value)) throw new Error('invalid_report');
  return value as Record<string, unknown>;
}

function count(value: unknown): number {
  if (typeof value !== 'number' || !Number.isSafeInteger(value) || value < 0 || value > 200) {
    throw new Error('invalid_report');
  }
  return value;
}

function moneyCents(value: unknown): bigint {
  if (typeof value !== 'string'
      || !/^-?(?:0|[1-9][0-9]{0,11})(?:\.[0-9]{1,2})?$/.test(value)) {
    throw new Error('invalid_report');
  }
  const sign = value.startsWith('-') ? -1n : 1n;
  const unsigned = value.replace(/^-/, '');
  const [whole, fraction = ''] = unsigned.split('.');
  const cents = (BigInt(whole) * 100n + BigInt(fraction.padEnd(2, '0'))) * sign;
  if (cents === 0n && sign === -1n) throw new Error('invalid_report');
  return cents;
}

function falseFlag(value: unknown): void {
  if (value !== false) throw new Error('unsafe_report');
}

function tradingDay(value: unknown): string {
  if (typeof value !== 'string' || !/^\d{4}-\d{2}-\d{2}$/.test(value)) {
    throw new Error('invalid_report');
  }
  const date = new Date(value + 'T00:00:00Z');
  if (!Number.isFinite(date.getTime()) || date.toISOString().slice(0, 10) !== value) {
    throw new Error('invalid_report');
  }
  return value;
}

function dailyLossMap(value: unknown): Map<string, bigint> {
  const source = object(value);
  if (Object.keys(source).length > 200) throw new Error('invalid_report');
  const result = new Map<string, bigint>();
  for (const [day, amount] of Object.entries(source)) {
    tradingDay(day);
    const cents = moneyCents(amount);
    if (cents <= 0n) throw new Error('invalid_report');
    result.set(day, cents);
  }
  return result;
}

function sameLosses(actual: Map<string, bigint>, expected: Map<string, bigint>): void {
  if (actual.size !== expected.size) throw new Error('invalid_report');
  for (const [day, value] of expected) {
    if (actual.get(day) !== value) throw new Error('invalid_report');
  }
}

function winRate(wins: number, total: number): string | null {
  if (total === 0) return null;
  const hundredthPercent = (BigInt(wins) * 10000n + BigInt(total) / 2n) / BigInt(total);
  return (Number(hundredthPercent) / 100).toFixed(2);
}

type DayAccumulator = { pnlCents: bigint; count: number };

function addSyntheticDay(
  source: Map<string, DayAccumulator>, day: string, pnlCents: bigint,
): void {
  const prev = source.get(day);
  source.set(day, {
    pnlCents: (prev?.pnlCents ?? 0n) + pnlCents,
    count: (prev?.count ?? 0) + 1,
  });
}

function usdFromCents(cents: bigint): string {
  const negative = cents < 0n;
  const amount = (negative ? -cents : cents).toString().padStart(3, '0');
  return `${negative ? '-' : ''}${amount.slice(0, -2)}.${amount.slice(-2)}`;
}

/** Drawdown is a daily-close USD peak-to-trough loss on SYNTHETIC PnL only.
 * No intra-day fills, market values, investment returns or price series.
 */
function syntheticTimeline(byDay: Map<string, DayAccumulator>): SyntheticTimeline {
  let cumulative = 0n;
  let peak = 0n;
  let maxDrawdown = 0n;
  let worstDay: bigint | null = null;
  let positiveDays = 0;
  let negativeDays = 0;
  const days = [...byDay].sort(([a], [b]) => a.localeCompare(b)).map(([day, value]) => {
    cumulative += value.pnlCents;
    if (cumulative > peak) peak = cumulative;
    const drawdown = peak - cumulative;
    if (drawdown > maxDrawdown) maxDrawdown = drawdown;
    if (worstDay === null || value.pnlCents < worstDay) worstDay = value.pnlCents;
    if (value.pnlCents > 0n) positiveDays++;
    if (value.pnlCents < 0n) negativeDays++;
    return {
      day,
      syntheticDailyPnlUsd: usdFromCents(value.pnlCents),
      syntheticCumulativePnlUsd: usdFromCents(cumulative),
      syntheticRoundTrips: value.count,
    };
  });
  return {
    days,
    maxSyntheticDrawdownUsd: usdFromCents(maxDrawdown),
    worstSyntheticDayUsd: worstDay === null ? null : usdFromCents(worstDay),
    positiveDays,
    negativeDays,
  };
}

export function parseSyntheticReport(payload: unknown): SyntheticReport {
  const root = object(payload);
  if (root.format !== REPORT_FORMAT || Object.keys(root).sort().join(',') !== 'format,snapshot') {
    throw new Error('invalid_report');
  }
  const snap = object(root.snapshot);
  if (snap.mode !== 'offline_synthetic_storage_only'
      || snap.status !== 'synthetic_storage_snapshot') throw new Error('invalid_report');
  falseFlag(snap.trade_executed);
  falseFlag(snap.paper_trading_enabled);
  falseFlag(snap.live_trading_enabled);
  falseFlag(snap.realized_performance);
  if (typeof snap.kill_switch_latched !== 'boolean') throw new Error('invalid_report');
  if (typeof snap.audit_tip_sha256 !== 'string'
      || !/^[a-f0-9]{64}$/.test(snap.audit_tip_sha256)) throw new Error('invalid_report');

  const summary = object(snap.summary);
  const strategies = object(snap.strategies);
  if (Object.keys(strategies).sort().join(',') !== 'momentum,new_launch') {
    throw new Error('invalid_report');
  }

  const seenIds = new Set<string>();
  const allDailyLosses = new Map<string, bigint>();
  const accountDaily = new Map<string, DayAccumulator>();
  const read = (id: SyntheticReportStrategyId): SyntheticStrategy => {
    const strategy = object(strategies[id]);
    const n = count(strategy.synthetic_round_trips);
    const wins = count(strategy.synthetic_wins);
    const losses = count(strategy.synthetic_losses);
    if (!Array.isArray(strategy.records) || strategy.records.length !== n) {
      throw new Error('invalid_report');
    }
    let sum = 0n;
    let positive = 0;
    let negative = 0;
    let priorDay = '';
    const expectedLosses = new Map<string, bigint>();
    const perStrategyDays = new Map<string, DayAccumulator>();
    for (const item of strategy.records) {
      const record = object(item);
      if (Object.keys(record).sort().join(',') !== RECORD_FIELDS) throw new Error('invalid_report');
      falseFlag(record.realized_performance);
      falseFlag(record.trade_executed);
      if (record.strategy !== id) throw new Error('invalid_report');
      if (typeof record.event_id !== 'string'
          || !/^[A-Za-z0-9_-]{1,64}$/.test(record.event_id)
          || seenIds.has(record.event_id)) throw new Error('invalid_report');
      seenIds.add(record.event_id);
      const day = tradingDay(record.trading_day);
      if (day < priorDay) throw new Error('invalid_report');
      priorDay = day;
      if (record.assumed_fee_bps_per_side !== 30
          || record.assumed_slippage_bps_per_side !== 100) throw new Error('invalid_report');
      const pnl = moneyCents(record.synthetic_net_pnl_usd);
      sum += pnl;
      addSyntheticDay(perStrategyDays, day, pnl);
      addSyntheticDay(accountDaily, day, pnl);
      if (pnl > 0n) positive++;
      if (pnl < 0n) {
        negative++;
        expectedLosses.set(day, (expectedLosses.get(day) ?? 0n) - pnl);
      }
    }
    if (wins !== positive || losses !== negative
        || moneyCents(strategy.synthetic_net_pnl_usd) !== sum) throw new Error('invalid_report');
    sameLosses(dailyLossMap(strategy.daily_gross_synthetic_losses_usd), expectedLosses);
    for (const [day, amount] of expectedLosses) {
      allDailyLosses.set(day, (allDailyLosses.get(day) ?? 0n) + amount);
    }
    return {
      syntheticRoundTrips: n,
      syntheticWins: wins,
      syntheticLosses: losses,
      syntheticNetPnlUsd: strategy.synthetic_net_pnl_usd as string,
      syntheticWinRatePct: winRate(wins, n),
      syntheticTimeline: syntheticTimeline(perStrategyDays),
    };
  };

  const newLaunch = read('new_launch');
  const momentum = read('momentum');
  const total = count(snap.event_count);
  if (total !== newLaunch.syntheticRoundTrips + momentum.syntheticRoundTrips
      || count(summary.synthetic_round_trips) !== total
      || seenIds.size !== total) throw new Error('invalid_report');
  if (total === 0 && snap.audit_tip_sha256 !== '0'.repeat(64)) throw new Error('invalid_report');
  if (total > 0 && snap.audit_tip_sha256 === '0'.repeat(64)) throw new Error('invalid_report');

  sameLosses(dailyLossMap(summary.daily_gross_synthetic_losses_usd), allDailyLosses);

  const combined = moneyCents(newLaunch.syntheticNetPnlUsd)
    + moneyCents(momentum.syntheticNetPnlUsd);
  const starting = moneyCents(summary.starting_synthetic_equity_usd);
  const ending = moneyCents(summary.ending_synthetic_equity_usd);
  const account = moneyCents(summary.synthetic_net_pnl_usd);
  if (starting <= 0n || combined !== account || starting + account !== ending) {
    throw new Error('invalid_report');
  }
  const timeline = syntheticTimeline(accountDaily);
  const lastCumulative = timeline.days.at(-1)?.syntheticCumulativePnlUsd ?? '0.00';
  if (moneyCents(lastCumulative) !== account
      || timeline.days.reduce((sum, d) => sum + d.syntheticRoundTrips, 0) !== total) {
    throw new Error('invalid_report');
  }

  return {
    eventCount: total,
    auditTipSha256: snap.audit_tip_sha256,
    killSwitchLatched: snap.kill_switch_latched,
    startingSyntheticEquityUsd: summary.starting_synthetic_equity_usd as string,
    endingSyntheticEquityUsd: summary.ending_synthetic_equity_usd as string,
    syntheticNetPnlUsd: summary.synthetic_net_pnl_usd as string,
    syntheticTimeline: timeline,
    strategies: { new_launch: newLaunch, momentum },
  };
}
