import { describe, expect, it } from 'vitest';
import { parseDatedTurkeyRoster } from './fourMarketUniverse';
import { buildFourMarketScanPlan, replaceTurkeyRosterCodes } from '../utils/fourMarketScanPlan';

const turkey = Array.from({ length: 100 }, (_, i) =>
  'T' + String.fromCharCode(65 + Math.floor(i / 26)) +
  String.fromCharCode(65 + i % 26) + 'A.IS',
);

function report() {
  return {
    market: 'tr',
    index: 'BIST100',
    as_of: '2026-11-16',
    effective_from: '2026-10-01',
    effective_to: '2026-12-31',
    verified_on: '2026-11-15',
    source_urls: ['https://www.borsaistanbul.com/endeks/xu100',
      'https://www.borsaistanbul.com/duyuru/15598/bist-pay-endeksleri-donemsel-degisiklikleri'],
    symbols: [...turkey],
    target_symbols: 100,
  };
}

describe('source-dated BIST100 prefill', () => {
  it('accepts a dated, sorted 100 equity roster and fills exactly the TR block', () => {
    const roster = parseDatedTurkeyRoster(report());
    const combined = replaceTurkeyRosterCodes('AAPL\nSAP.DE\nHK00700', roster.symbols);
    const plan = buildFourMarketScanPlan(combined);
    expect(plan.counts).toEqual({ tr: 100, us: 1, de: 1, hk: 1 });
    expect(plan.total).toBe(103);
    expect(plan.errors).toEqual([]);
    expect(plan.readyForFullScan).toBe(false);
  });

  it('is idempotent and never silently changes foreign codes', () => {
    const once = replaceTurkeyRosterCodes('THYAO.IS, AAPL, SAP.DE, HK00700', turkey);
    const twice = replaceTurkeyRosterCodes(once, turkey);
    expect(once).toBe(twice);
    expect(buildFourMarketScanPlan(twice).counts).toEqual({
      tr: 100, us: 1, de: 1, hk: 1,
    });
  });

  it('refuses a wrong market, wrong period, duplicates and extra symbols', () => {
    const bad = report();
    bad.market = 'jp';
    expect(() => parseDatedTurkeyRoster(bad)).toThrow();

    const expired = report();
    expired.as_of = '2027-01-01';
    expect(() => parseDatedTurkeyRoster(expired)).toThrow();

    const duplicates = report();
    duplicates.symbols[1] = duplicates.symbols[0];
    expect(() => parseDatedTurkeyRoster(duplicates)).toThrow();

    expect(() => replaceTurkeyRosterCodes('', turkey.slice(0, 99))).toThrow();
    expect(() => replaceTurkeyRosterCodes('', [...turkey, 'ZZZZ.IS'])).toThrow();
  });

  it('never treats source validation as live Yahoo coverage', () => {
    const roster = parseDatedTurkeyRoster(report());
    expect(roster.symbols.length).toBe(100);
    const planned = buildFourMarketScanPlan(replaceTurkeyRosterCodes('', roster.symbols));
    expect(planned.readyForFullScan).toBe(false);
    expect(planned.remaining.us + planned.remaining.de + planned.remaining.hk).toBe(300);
  });
});
