import { describe, it, expect } from 'vitest';
import { parseSyntheticReport } from '../syntheticReport';

function valid() {
  return {
    format: 'ebbot-synthetic-report-v1',
    snapshot: {
      mode: 'offline_synthetic_storage_only',
      status: 'synthetic_storage_snapshot',
      event_count: 2,
      audit_tip_sha256: 'a'.repeat(64),
      kill_switch_latched: true,
      trade_executed: false,
      paper_trading_enabled: false,
      live_trading_enabled: false,
      realized_performance: false,
      summary: {
        synthetic_round_trips: 2,
        starting_synthetic_equity_usd: '1000.00',
        ending_synthetic_equity_usd: '995.00',
        synthetic_net_pnl_usd: '-5.00',
      },
      strategies: {
        new_launch: {
          synthetic_round_trips: 1, synthetic_wins: 1, synthetic_losses: 0,
          synthetic_net_pnl_usd: '5.00', records: [{}],
        },
        momentum: {
          synthetic_round_trips: 1, synthetic_wins: 0, synthetic_losses: 1,
          synthetic_net_pnl_usd: '-10.00', records: [{}],
        },
      },
    },
  };
}

describe('offline synthetic research report parser', () => {
  it('keeps only separated aggregates, not event records', () => {
    const r = parseSyntheticReport(valid());
    expect(r.eventCount).toBe(2);
    expect(r.strategies.new_launch.syntheticNetPnlUsd).toBe('5.00');
    expect(r.strategies.momentum.syntheticNetPnlUsd).toBe('-10.00');
    expect(r.killSwitchLatched).toBe(true);
    expect('records' in r.strategies.new_launch).toBe(false);
  });

  it('rejects forged live-trading status and unrelated report structure', () => {
    const payload = valid();
    payload.snapshot.live_trading_enabled = true;
    expect(() => parseSyntheticReport(payload)).toThrow();
    expect(() => parseSyntheticReport({ ...valid(), format: 'unknown' })).toThrow();
    expect(() => parseSyntheticReport([])).toThrow();
  });

  it('rejects unmatched per-strategy counts and malformed money strings', () => {
    const payload = valid();
    payload.snapshot.strategies.momentum.synthetic_round_trips = 2;
    expect(() => parseSyntheticReport(payload)).toThrow();
    payload.snapshot.strategies.momentum.synthetic_round_trips = 1;
    payload.snapshot.summary.synthetic_net_pnl_usd = '<img src=x>';
    expect(() => parseSyntheticReport(payload)).toThrow();
  });
});
