import { describe, expect, it } from 'vitest';
import { assessSyntheticEvidence, SYNTHETIC_SAMPLE_RULES } from '../syntheticEvidence';
import type { SyntheticReport, SyntheticDailyPoint } from '../syntheticReport';

function dayAt(index: number, count: number, pnl: string): SyntheticDailyPoint {
  const date = new Date(Date.UTC(2026, 0, 1 + index)).toISOString().slice(0, 10);
  return { day: date, syntheticRoundTrips: count,
    syntheticDailyPnlUsd: pnl, syntheticCumulativePnlUsd: '0.00' };
}

function report(
  launch: SyntheticDailyPoint[],
  momentum: SyntheticDailyPoint[] = [],
): SyntheticReport {
  const timeline = (days: SyntheticDailyPoint[]) => ({
    days, maxSyntheticDrawdownUsd: '0.00',
    worstSyntheticDayUsd: days.length ? '0.00' : null, positiveDays: 0, negativeDays: 0,
  });
  const strategy = (days: SyntheticDailyPoint[]) => ({
    syntheticRoundTrips: days.reduce((n, d) => n + d.syntheticRoundTrips, 0),
    syntheticWins: 0, syntheticLosses: 0, syntheticNetPnlUsd: '0.00',
    syntheticWinRatePct: null, syntheticTimeline: timeline(days),
  });
  return {
    eventCount: [...launch, ...momentum].reduce((n, d) => n + d.syntheticRoundTrips, 0),
    auditTipSha256: 'a'.repeat(64), killSwitchLatched: false,
    startingSyntheticEquityUsd: '1000.00', endingSyntheticEquityUsd: '1000.00',
    syntheticNetPnlUsd: '0.00',
    syntheticTimeline: timeline([]),
    strategies: { new_launch: strategy(launch), momentum: strategy(momentum) },
  };
}

function enough(): SyntheticDailyPoint[] {
  // 30 training rounds on 10 days, 15 later rounds on 5 days.
  return Array.from({ length: 15 }, (_, i) =>
    dayAt(i, 3, [1, 6, 12].includes(i) ? '-0.20' : '0.10'));
}

describe('offline synthetic retrospective evidence gate', () => {
  it('requires an explicit cutoff and rejects malformed, non-existent dates', () => {
    for (const cutoff of ['', '2026-02-30', '2026-1-10', 'oops']) {
      const result = assessSyntheticEvidence(report(enough()), cutoff);
      expect(result.status).toBe(cutoff ? 'invalid_cutoff' : 'cutoff_required');
      expect(result.strategies).toBeNull();
      expect(result.readyForTrading).toBe(false);
    }
  });

  it('separates complete dates and meets declared minima but never validates performance', () => {
    const r = assessSyntheticEvidence(report(enough(), enough()), '2026-01-10');
    expect(r.status).toBe('retrospective_only');
    if (r.status !== 'retrospective_only') throw new Error('unexpected state');
    for (const key of ['new_launch', 'momentum'] as const) {
      const s = r.strategies[key];
      expect(s.training.records).toBe(30);
      expect(s.training.distinctDays).toBe(10);
      expect(s.training.negativeDays).toBe(2);
      expect(s.later.records).toBe(15);
      expect(s.later.distinctDays).toBe(5);
      expect(s.later.negativeDays).toBe(1);
      expect(s.training.hypotheticalNetPnlUsd).toBe('0.40');
      expect(s.later.hypotheticalNetPnlUsd).toBe('0.20');
      expect(s.status).toBe('retrospective_sample_rules_met');
      expect(s.reasons).toEqual([]);
      expect(s.independentValidationPassed).toBe(false);
      expect(s.readyForTrading).toBe(false);
    }
    expect(r.independentValidationPassed).toBe(false);
    expect(r.readyForTrading).toBe(false);
    expect(SYNTHETIC_SAMPLE_RULES.minLaterRecords).toBe(15);
  });

  it('keeps the two strategies independent and refuses to grade tiny profitable samples', () => {
    const r = assessSyntheticEvidence(
      report(enough(), [dayAt(0, 1, '100.00')]), '2026-01-10');
    if (r.status !== 'retrospective_only') throw new Error('unexpected state');
    expect(r.strategies.new_launch.status).toBe('retrospective_sample_rules_met');
    expect(r.strategies.momentum.status).toBe('insufficient_synthetic_sample');
    expect(r.strategies.momentum.reasons).toContain('later_records_below_minimum');
    expect(r.strategies.momentum.training.hypotheticalNetPnlUsd).toBe('100.00');
    expect(r.independentValidationPassed).toBe(false);
  });

  it('fails sample rule when later period lacks negative days, even with many wins', () => {
    const onlyPositiveLater = enough().map((d, i) => i >= 10
      ? { ...d, syntheticDailyPnlUsd: '3.00' } : d);
    const r = assessSyntheticEvidence(report(onlyPositiveLater), '2026-01-10');
    if (r.status !== 'retrospective_only') throw new Error('unexpected state');
    expect(r.strategies.new_launch.reasons).toEqual(['later_negative_days_below_minimum']);
    expect(r.strategies.new_launch.status).toBe('insufficient_synthetic_sample');
  });

  it('moves the entire boundary day into training; no later leakage', () => {
    const r = assessSyntheticEvidence(report(enough()), '2026-01-11');
    if (r.status !== 'retrospective_only') throw new Error('unexpected state');
    expect(r.strategies.new_launch.training.records).toBe(33);
    expect(r.strategies.new_launch.later.records).toBe(12);
    expect(r.strategies.new_launch.reasons).toContain('later_records_below_minimum');
    expect(r.strategies.new_launch.later.distinctDays).toBe(4);
  });

  it('does not invent independent validation from a fully synthetic dataset', () => {
    const r = assessSyntheticEvidence(report([]), '2026-01-10');
    if (r.status !== 'retrospective_only') throw new Error('unexpected state');
    expect(r.strategies.momentum.reasons).toHaveLength(6);
    expect(r.strategies.new_launch.later.hypotheticalNetPnlUsd).toBe('0.00');
    expect(r.readyForTrading).toBe(false);
  });
});
