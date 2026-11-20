import { describe, expect, it } from 'vitest';
import { formatDate, formatDateTime, formatReportType } from '../format';

describe('Turkish operator formatters', () => {
  it('uses the Turkish locale for dates without touching backend market-day semantics', () => {
    const date = '2026-11-18T12:34:00Z';
    expect(formatDateTime(date)).toBe(new Intl.DateTimeFormat('tr-TR', {
      year: 'numeric', month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit',
    }).format(new Date(date)));
    expect(formatDate(date)).toBe(new Intl.DateTimeFormat('tr-TR', {
      year: 'numeric', month: '2-digit', day: '2-digit',
    }).format(new Date(date)));
  });

  it('does not leak Chinese report type names in the Turkish operator UI', () => {
    expect(formatReportType('simple')).toBe('Basit');
    expect(formatReportType('detailed')).toBe('Standart');
    expect(formatReportType('full')).toBe('Tam');
    expect(formatReportType('brief')).toBe('Kısa');
    expect(formatReportType('market_review')).toBe('Piyasa Özeti');
    expect(formatReportType('unknown_report')).toBe('unknown_report');
  });
});
