/** Strict local-only, UNTRUSTED visualization of a synthetic research report.
 * No network requests, persistence, candidate matching or trading functions.
 */
export type SyntheticReportStrategyId = 'new_launch' | 'momentum';

type SyntheticStrategy = {
  syntheticRoundTrips: number;
  syntheticWins: number;
  syntheticLosses: number;
  syntheticNetPnlUsd: string;
};
export type SyntheticReport = {
  eventCount: number;
  auditTipSha256: string;
  killSwitchLatched: boolean;
  startingSyntheticEquityUsd: string;
  endingSyntheticEquityUsd: string;
  syntheticNetPnlUsd: string;
  strategies: Record<SyntheticReportStrategyId, SyntheticStrategy>;
};
export const MAX_SYNTHETIC_REPORT_BYTES = 262144;
const REPORT_FORMAT = 'ebbot-synthetic-report-v1';

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

function money(value: unknown): string {
  if (typeof value !== 'string' || !/^-?(?:0|[1-9][0-9]{0,11})(?:\.[0-9]{1,2})?$/.test(value)) {
    throw new Error('invalid_report');
  }
  return value;
}

function falseFlag(value: unknown): void {
  if (value !== false) throw new Error('unsafe_report');
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
  if (typeof snap.audit_tip_sha256 !== 'string' || !/^[a-f0-9]{64}$/.test(snap.audit_tip_sha256)) {
    throw new Error('invalid_report');
  }
  const summary = object(snap.summary);
  const strategies = object(snap.strategies);
  if (Object.keys(strategies).sort().join(',') !== 'momentum,new_launch') throw new Error('invalid_report');
  const read = (id: SyntheticReportStrategyId): SyntheticStrategy => {
    const strategy = object(strategies[id]);
    const n = count(strategy.synthetic_round_trips);
    const wins = count(strategy.synthetic_wins);
    const losses = count(strategy.synthetic_losses);
    if (wins + losses > n) throw new Error('invalid_report');
    if (!Array.isArray(strategy.records) || strategy.records.length !== n) throw new Error('invalid_report');
    // No record/token/event data is copied into the UI. Aggregate fields only.
    return {
      syntheticRoundTrips: n,
      syntheticWins: wins,
      syntheticLosses: losses,
      syntheticNetPnlUsd: money(strategy.synthetic_net_pnl_usd),
    };
  };
  const newLaunch = read('new_launch');
  const momentum = read('momentum');
  const total = count(snap.event_count);
  if (total !== newLaunch.syntheticRoundTrips + momentum.syntheticRoundTrips
      || count(summary.synthetic_round_trips) !== total) throw new Error('invalid_report');
  return {
    eventCount: total,
    auditTipSha256: snap.audit_tip_sha256,
    killSwitchLatched: snap.kill_switch_latched,
    startingSyntheticEquityUsd: money(summary.starting_synthetic_equity_usd),
    endingSyntheticEquityUsd: money(summary.ending_synthetic_equity_usd),
    syntheticNetPnlUsd: money(summary.synthetic_net_pnl_usd),
    strategies: { new_launch: newLaunch, momentum },
  };
}
