/** Deterministic RETROSPECTIVE partitioning of already-verified SYNTHETIC data.
 * Choosing a cutoff after viewing the full file is NOT out-of-sample validation.
 * Nothing here can authorize live trading, publication, or strategy promotion.
 */
import type { SyntheticReport, SyntheticDailyPoint, SyntheticReportStrategyId } from './syntheticReport';

export const SYNTHETIC_SAMPLE_RULES = Object.freeze({
  minTrainingRecords: 30,
  minTrainingDays: 10,
  minTrainingNegativeDays: 2,
  minLaterRecords: 15,
  minLaterDays: 5,
  minLaterNegativeDays: 1,
});

export type EvidenceReason =
  | 'training_records_below_minimum'
  | 'training_days_below_minimum'
  | 'training_negative_days_below_minimum'
  | 'later_records_below_minimum'
  | 'later_days_below_minimum'
  | 'later_negative_days_below_minimum';

export type SyntheticPeriodEvidence = {
  records: number;
  distinctDays: number;
  negativeDays: number;
  hypotheticalNetPnlUsd: string;
};

export type SyntheticStrategyEvidence = {
  strategy: SyntheticReportStrategyId;
  status: 'insufficient_synthetic_sample' | 'retrospective_sample_rules_met';
  reasons: EvidenceReason[];
  training: SyntheticPeriodEvidence;
  later: SyntheticPeriodEvidence;
  // Never claim source provenance or an independent, precommitted holdout.
  independentValidationPassed: false;
  readyForTrading: false;
};

export type SyntheticEvidenceAssessment =
  | { status: 'cutoff_required' | 'invalid_cutoff'; strategies: null;
      independentValidationPassed: false; readyForTrading: false }
  | { status: 'retrospective_only'; cutoffDay: string;
      strategies: Record<SyntheticReportStrategyId, SyntheticStrategyEvidence>;
      independentValidationPassed: false; readyForTrading: false };

function isISOTradingDay(day: string): boolean {
  if (!/^\d{4}-\d{2}-\d{2}$/.test(day)) return false;
  const date = new Date(day + 'T00:00:00Z');
  return Number.isFinite(date.valueOf()) && date.toISOString().slice(0, 10) === day;
}

function cents(value: string): bigint {
  if (!/^-?(?:0|[1-9]\d{0,11})(?:\.\d{1,2})?$/.test(value)) {
    throw new Error('invalid_synthetic_money');
  }
  const sign = value.startsWith('-') ? -1n : 1n;
  const [whole, decimal = ''] = value.replace(/^-/, '').split('.');
  return sign * (BigInt(whole) * 100n + BigInt(decimal.padEnd(2, '0')));
}

function usd(value: bigint): string {
  const abs = (value < 0n ? -value : value).toString().padStart(3, '0');
  return (value < 0n ? '-' : '') + abs.slice(0, -2) + '.' + abs.slice(-2);
}

function period(days: SyntheticDailyPoint[]): SyntheticPeriodEvidence {
  return {
    records: days.reduce((n, item) => n + item.syntheticRoundTrips, 0),
    distinctDays: days.length,
    negativeDays: days.filter(item => cents(item.syntheticDailyPnlUsd) < 0n).length,
    hypotheticalNetPnlUsd: usd(days.reduce(
      (total, item) => total + cents(item.syntheticDailyPnlUsd), 0n,
    )),
  };
}

function forStrategy(
  strategy: SyntheticReportStrategyId,
  report: SyntheticReport,
  cutoffDay: string,
): SyntheticStrategyEvidence {
  // Each entire trading day belongs to exactly one period; never split a day.
  const days = report.strategies[strategy].syntheticTimeline.days;
  const training = period(days.filter(item => item.day <= cutoffDay));
  const later = period(days.filter(item => item.day > cutoffDay));
  const reasons: EvidenceReason[] = [];
  if (training.records < SYNTHETIC_SAMPLE_RULES.minTrainingRecords) {
    reasons.push('training_records_below_minimum');
  }
  if (training.distinctDays < SYNTHETIC_SAMPLE_RULES.minTrainingDays) {
    reasons.push('training_days_below_minimum');
  }
  if (training.negativeDays < SYNTHETIC_SAMPLE_RULES.minTrainingNegativeDays) {
    reasons.push('training_negative_days_below_minimum');
  }
  if (later.records < SYNTHETIC_SAMPLE_RULES.minLaterRecords) {
    reasons.push('later_records_below_minimum');
  }
  if (later.distinctDays < SYNTHETIC_SAMPLE_RULES.minLaterDays) {
    reasons.push('later_days_below_minimum');
  }
  if (later.negativeDays < SYNTHETIC_SAMPLE_RULES.minLaterNegativeDays) {
    reasons.push('later_negative_days_below_minimum');
  }
  return {
    strategy,
    status: reasons.length === 0
      ? 'retrospective_sample_rules_met' : 'insufficient_synthetic_sample',
    reasons,
    training,
    later,
    independentValidationPassed: false,
    readyForTrading: false,
  };
}

/** Pure; uses only explicitly loaded synthetic data. Never fetches data. */
export function assessSyntheticEvidence(
  report: SyntheticReport,
  cutoffDay: string,
): SyntheticEvidenceAssessment {
  if (cutoffDay === '') {
    return {
      status: 'cutoff_required', strategies: null,
      independentValidationPassed: false, readyForTrading: false,
    };
  }
  if (!isISOTradingDay(cutoffDay)) {
    return {
      status: 'invalid_cutoff', strategies: null,
      independentValidationPassed: false, readyForTrading: false,
    };
  }
  return {
    status: 'retrospective_only', cutoffDay,
    strategies: {
      new_launch: forStrategy('new_launch', report, cutoffDay),
      momentum: forStrategy('momentum', report, cutoffDay),
    },
    independentValidationPassed: false,
    readyForTrading: false,
  };
}
