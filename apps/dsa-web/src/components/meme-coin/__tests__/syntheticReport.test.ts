import { describe, it, expect } from 'vitest';
import { parseSyntheticReport } from '../syntheticReport';

function record(id: string, strategy: string, pnl: string, day = '2026-11-18') {
  return {
    event_id: id, strategy, trading_day: day, synthetic_net_pnl_usd: pnl,
    assumed_fee_bps_per_side: 30, assumed_slippage_bps_per_side: 100,
    trade_executed: false, realized_performance: false,
  };
}

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
        daily_gross_synthetic_losses_usd: { '2026-11-18': '10.00' } as Record<string, string>,
      },
      strategies: {
        new_launch: {
          synthetic_round_trips: 1, synthetic_wins: 1, synthetic_losses: 0,
          synthetic_net_pnl_usd: '5.00',
          daily_gross_synthetic_losses_usd: {},
          records: [record('a', 'new_launch', '5.00')],
        },
        momentum: {
          synthetic_round_trips: 1, synthetic_wins: 0, synthetic_losses: 1,
          synthetic_net_pnl_usd: '-10.00',
          daily_gross_synthetic_losses_usd: { '2026-11-18': '10.00' } as Record<string, string>,
          records: [record('b', 'momentum', '-10.00')],
        },
      },
    },
  };
}

describe('offline synthetic research report parser', () => {
  it('reconciles both journals, audit counts, and produces labelled synthetic win rates', () => {
    const r = parseSyntheticReport(valid());
    expect(r.eventCount).toBe(2);
    expect(r.strategies.new_launch.syntheticNetPnlUsd).toBe('5.00');
    expect(r.strategies.momentum.syntheticNetPnlUsd).toBe('-10.00');
    expect(r.strategies.new_launch.syntheticWinRatePct).toBe('100.00');
    expect(r.strategies.momentum.syntheticWinRatePct).toBe('0.00');
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

  it('rejects mismatching record count and injected markup', () => {
    const payload = valid();
    payload.snapshot.strategies.momentum.synthetic_round_trips = 2;
    expect(() => parseSyntheticReport(payload)).toThrow();
    payload.snapshot.strategies.momentum.synthetic_round_trips = 1;
    payload.snapshot.summary.synthetic_net_pnl_usd = '<img src=x>';
    expect(() => parseSyntheticReport(payload)).toThrow();
  });

  it('rejects mathematically inconsistent PnL, balances and daily loss budgets', () => {
    const cases: Array<(p: ReturnType<typeof valid>) => void> = [
      p => { p.snapshot.summary.synthetic_net_pnl_usd = '-4.00'; },
      p => { p.snapshot.summary.ending_synthetic_equity_usd = '996.00'; },
      p => { p.snapshot.strategies.momentum.synthetic_net_pnl_usd = '-9.00'; },
      p => { p.snapshot.summary.daily_gross_synthetic_losses_usd['2026-11-18'] = '9.00'; },
      p => { p.snapshot.strategies.momentum.daily_gross_synthetic_losses_usd['2026-11-18'] = '9.00'; },
      p => { p.snapshot.strategies.new_launch.synthetic_wins = 0; },
      p => { p.snapshot.strategies.momentum.records[0].synthetic_net_pnl_usd = '-9.00'; },
    ];
    for (const mutate of cases) {
      const payload = valid();
      mutate(payload);
      expect(() => parseSyntheticReport(payload)).toThrow();
    }
  });

  it('rejects duplicate event identifiers, foreign strategy records and unsafe flags', () => {
    const payload = valid();
    payload.snapshot.strategies.momentum.records[0].event_id = 'a';
    expect(() => parseSyntheticReport(payload)).toThrow();
    payload.snapshot.strategies.momentum.records[0].event_id = 'b';
    payload.snapshot.strategies.momentum.records[0].strategy = 'new_launch';
    expect(() => parseSyntheticReport(payload)).toThrow();
    payload.snapshot.strategies.momentum.records[0].strategy = 'momentum';
    payload.snapshot.strategies.momentum.records[0].trade_executed = true;
    expect(() => parseSyntheticReport(payload)).toThrow();
  });

  it('rejects invented empty-journal hash and nonexistent trading date', () => {
    const payload = valid();
    payload.snapshot.strategies.momentum.records[0].trading_day = '2026-02-30';
    expect(() => parseSyntheticReport(payload)).toThrow();
    const empty = valid();
    empty.snapshot.event_count = 0;
    empty.snapshot.summary.synthetic_round_trips = 0;
    empty.snapshot.summary.synthetic_net_pnl_usd = '0.00';
    empty.snapshot.summary.ending_synthetic_equity_usd = '1000.00';
    empty.snapshot.summary.daily_gross_synthetic_losses_usd = {};
    empty.snapshot.strategies.new_launch = {
      synthetic_round_trips: 0, synthetic_wins: 0, synthetic_losses: 0,
      synthetic_net_pnl_usd: '0.00', daily_gross_synthetic_losses_usd: {}, records: [],
    };
    empty.snapshot.strategies.momentum = {
      synthetic_round_trips: 0, synthetic_wins: 0, synthetic_losses: 0,
      synthetic_net_pnl_usd: '0.00', daily_gross_synthetic_losses_usd: {}, records: [],
    };
    expect(() => parseSyntheticReport(empty)).toThrow();
    empty.snapshot.audit_tip_sha256 = '0'.repeat(64);
    expect(parseSyntheticReport(empty).strategies.momentum.syntheticWinRatePct).toBe(null);
  });

  it('checks exact cents, not floating-point sums', () => {
    const payload = valid();
    payload.snapshot.strategies.new_launch.records[0].synthetic_net_pnl_usd = '5.01';
    payload.snapshot.strategies.new_launch.synthetic_net_pnl_usd = '5.01';
    payload.snapshot.summary.synthetic_net_pnl_usd = '-4.99';
    payload.snapshot.summary.ending_synthetic_equity_usd = '995.01';
    expect(parseSyntheticReport(payload).syntheticNetPnlUsd).toBe('-4.99');
  });
});

// All daily figures are derived from successfully reconciled offline synthetic records.
describe('synthetic timeline and risk comparison', () => {
  it('preserves isolated per-strategy curves and exact combined cents', () => {
    const r = parseSyntheticReport(valid());
    expect(r.syntheticTimeline.days).toEqual([
      { day: '2026-11-18', syntheticDailyPnlUsd: '-5.00',
        syntheticCumulativePnlUsd: '-5.00', syntheticRoundTrips: 2 },
    ]);
    expect(r.syntheticTimeline.maxSyntheticDrawdownUsd).toBe('5.00');
    expect(r.syntheticTimeline.worstSyntheticDayUsd).toBe('-5.00');
    expect(r.syntheticTimeline.negativeDays).toBe(1);
    expect(r.strategies.new_launch.syntheticTimeline.maxSyntheticDrawdownUsd).toBe('0.00');
    expect(r.strategies.momentum.syntheticTimeline.maxSyntheticDrawdownUsd).toBe('10.00');
    expect(r.strategies.new_launch.syntheticTimeline.days[0].syntheticDailyPnlUsd).toBe('5.00');
    expect(r.strategies.momentum.syntheticTimeline.days[0].syntheticDailyPnlUsd).toBe('-10.00');
  });

  it('uses dated daily close, including gaps between synthetic scenario days', () => {
    const p = valid();
    p.snapshot.strategies.momentum.records[0].trading_day = '2026-11-20';
    p.snapshot.strategies.momentum.daily_gross_synthetic_losses_usd = { '2026-11-20': '10.00' };
    p.snapshot.summary.daily_gross_synthetic_losses_usd = { '2026-11-20': '10.00' };
    const r = parseSyntheticReport(p);
    expect(r.syntheticTimeline.days.map(d => d.day)).toEqual(['2026-11-18', '2026-11-20']);
    expect(r.syntheticTimeline.days.map(d => d.syntheticCumulativePnlUsd)).toEqual(['5.00', '-5.00']);
    expect(r.syntheticTimeline.maxSyntheticDrawdownUsd).toBe('10.00');
    expect(r.syntheticTimeline.positiveDays).toBe(1);
    expect(r.syntheticTimeline.negativeDays).toBe(1);
    expect(r.strategies.new_launch.syntheticTimeline.days).toHaveLength(1);
    expect(r.strategies.momentum.syntheticTimeline.days).toHaveLength(1);
  });

  it('makes no performance claims without synthetic sample data', () => {
    const empty = valid();
    empty.snapshot.event_count = 0;
    empty.snapshot.audit_tip_sha256 = '0'.repeat(64);
    empty.snapshot.summary.synthetic_round_trips = 0;
    empty.snapshot.summary.synthetic_net_pnl_usd = '0.00';
    empty.snapshot.summary.ending_synthetic_equity_usd = '1000.00';
    empty.snapshot.summary.daily_gross_synthetic_losses_usd = {};
    for (const key of ['new_launch', 'momentum'] as const) {
      empty.snapshot.strategies[key] = {
        synthetic_round_trips: 0, synthetic_wins: 0, synthetic_losses: 0,
        synthetic_net_pnl_usd: '0.00', daily_gross_synthetic_losses_usd: {}, records: [],
      };
    }
    const r = parseSyntheticReport(empty);
    expect(r.syntheticTimeline.days).toEqual([]);
    expect(r.syntheticTimeline.maxSyntheticDrawdownUsd).toBe('0.00');
    expect(r.syntheticTimeline.worstSyntheticDayUsd).toBe(null);
    expect(r.strategies.momentum.syntheticWinRatePct).toBe(null);
  });

  it('does not confuse profitable days with win rate from individual rounds', () => {
    const p = valid();
    p.snapshot.strategies.new_launch.records[0].synthetic_net_pnl_usd = '10.01';
    p.snapshot.strategies.new_launch.synthetic_net_pnl_usd = '10.01';
    p.snapshot.summary.synthetic_net_pnl_usd = '0.01';
    p.snapshot.summary.ending_synthetic_equity_usd = '1000.01';
    const r = parseSyntheticReport(p);
    expect(r.syntheticTimeline.days[0].syntheticDailyPnlUsd).toBe('0.01');
    expect(r.syntheticTimeline.positiveDays).toBe(1);
    expect(r.syntheticTimeline.maxSyntheticDrawdownUsd).toBe('0.00');
  });
});
