/**
 * Validate a human-reviewed, versioned GitHub Actions quality summary.
 * This is display-only input; it never authorizes scanning, paper performance or orders.
 * A repository PR review is required before changing the published JSON.
 */
export type SolanaQualityResult = 'complete_captures' | 'degraded_capture_data';

export type QualityCapture = {
  run_id: string;
  priced_rows: number;
  missing_rows: number;
  result: 'passed' | 'degraded';
};

export type ReviewedSolanaQuality = {
  schema_version: 1;
  mode: 'reviewed_github_actions_archive_quality';
  audited_at_utc: string;
  audit_run_id: string;
  quality_result: SolanaQualityResult;
  capture_count: number;
  total_priced_rows: number;
  total_missing_rows: number;
  blocked_assessments: number;
  watch_assessments: number;
  trading_enabled: false;
  wallet_enabled: false;
  performance_calculated: false;
  ready_for_verified_paper_performance: false;
  captures: QualityCapture[];
};

const RUN_ID = /^[0-9]{6,20}$/;
const UTC_TIME = /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$/;

function record(value: unknown): value is Record<string, unknown> {
  return value !== null && typeof value === 'object' && !Array.isArray(value);
}

function integer(value: unknown, max: number): value is number {
  return typeof value === 'number' && Number.isSafeInteger(value) && value >= 0 && value <= max;
}

function requireValid(condition: boolean): asserts condition {
  if (!condition) throw new Error('Solana kalite raporu doğrulanamadı');
}

export function parseReviewedSolanaQuality(value: unknown): ReviewedSolanaQuality {
  requireValid(record(value));
  requireValid(value.schema_version === 1);
  requireValid(value.mode === 'reviewed_github_actions_archive_quality');
  requireValid(
    typeof value.audited_at_utc === 'string' &&
    UTC_TIME.test(value.audited_at_utc) &&
    Number.isFinite(Date.parse(value.audited_at_utc)),
  );
  requireValid(typeof value.audit_run_id === 'string' && RUN_ID.test(value.audit_run_id));
  requireValid(value.quality_result === 'complete_captures' || value.quality_result === 'degraded_capture_data');

  // A report can never turn observation data into a performance or trading authorization.
  requireValid(
    value.trading_enabled === false &&
    value.wallet_enabled === false &&
    value.performance_calculated === false &&
    value.ready_for_verified_paper_performance === false,
  );

  requireValid(Array.isArray(value.captures) && value.captures.length >= 1 && value.captures.length <= 6);
  requireValid(integer(value.capture_count, 6) && value.capture_count === value.captures.length);

  const captures: QualityCapture[] = [];
  const seen = new Set<string>();
  for (const candidate of value.captures) {
    requireValid(record(candidate));
    const { run_id, priced_rows, missing_rows, result } = candidate;
    requireValid(typeof run_id === 'string' && RUN_ID.test(run_id));
    requireValid(run_id !== value.audit_run_id && !seen.has(run_id));
    seen.add(run_id);
    requireValid(integer(priced_rows, 8) && integer(missing_rows, 8));
    requireValid(priced_rows + missing_rows > 0 && priced_rows + missing_rows <= 8);
    requireValid(result === 'passed' || result === 'degraded');
    requireValid(result !== 'passed' || missing_rows === 0);
    captures.push({ run_id, priced_rows, missing_rows, result });
  }

  const priced = captures.reduce((sum, capture) => sum + capture.priced_rows, 0);
  const missing = captures.reduce((sum, capture) => sum + capture.missing_rows, 0);
  requireValid(integer(value.total_priced_rows, 48) && value.total_priced_rows === priced);
  requireValid(integer(value.total_missing_rows, 48) && value.total_missing_rows === missing);
  requireValid(integer(value.blocked_assessments, 96) && integer(value.watch_assessments, 96));
  requireValid(value.blocked_assessments + value.watch_assessments === 2 * priced);
  const complete = missing === 0 && captures.every((capture) => capture.result === 'passed');
  requireValid(value.quality_result === (complete ? 'complete_captures' : 'degraded_capture_data'));

  return {
    schema_version: 1,
    mode: 'reviewed_github_actions_archive_quality',
    audited_at_utc: value.audited_at_utc,
    audit_run_id: value.audit_run_id,
    quality_result: value.quality_result,
    capture_count: value.capture_count,
    total_priced_rows: priced,
    total_missing_rows: missing,
    blocked_assessments: value.blocked_assessments,
    watch_assessments: value.watch_assessments,
    trading_enabled: false,
    wallet_enabled: false,
    performance_calculated: false,
    ready_for_verified_paper_performance: false,
    captures,
  };
}
