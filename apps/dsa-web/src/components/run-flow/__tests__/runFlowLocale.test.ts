import { describe, expect, it } from 'vitest';
import { formatDateTime } from '../utils';

const t = () => '-';

describe('Run Flow date formatting', () => {
  it('supports the Turkish UI language with the Turkish locale', () => {
    const timestamp = '2026-11-18T20:25:00Z';
    expect(formatDateTime(timestamp, 'tr', t)).toBe(new Date(timestamp).toLocaleString('tr-TR'));
  });

  it('preserves the existing English, Chinese and missing-date behavior', () => {
    const timestamp = '2026-11-18T20:25:00Z';
    expect(formatDateTime(timestamp, 'en', t)).toBe(new Date(timestamp).toLocaleString('en-US'));
    expect(formatDateTime(timestamp, 'zh', t)).toBe(new Date(timestamp).toLocaleString('zh-CN'));
    expect(formatDateTime(null, 'tr', t)).toBe('-');
  });
});
