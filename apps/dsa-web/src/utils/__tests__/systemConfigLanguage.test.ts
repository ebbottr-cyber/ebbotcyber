import { describe, expect, it } from 'vitest';
import {
  getCategoryDescription,
  getCategoryTitle,
  getFieldOptionLabel,
} from '../systemConfigI18n';
import { formatDateTime } from '../../components/run-flow/utils';

const t = (key: string) => key;

describe('Turkish UI coverage', () => {
  it('translates configuration category headings and descriptions without falling back to Chinese', () => {
    expect(getCategoryTitle('base', undefined, 'tr')).toBe('Temel Ayarlar');
    expect(getCategoryTitle('notification', undefined, 'tr')).toBe('Bildirimler');
    expect(getCategoryDescription('data_source', undefined, 'tr')).toContain('Piyasa veri');
    expect(getCategoryDescription('backtest', undefined, 'tr')).toContain('test');
    expect(getCategoryTitle('base', undefined, 'zh')).toBe('基础设置');
    expect(getCategoryTitle('base', undefined, 'en')).toBe('Base settings');
  });

  it('uses understandable English option names in Turkish when no Turkish option table exists', () => {
    expect(getFieldOptionLabel('REPORT_TYPE', 'simple', undefined, 'tr')).toBe('Simple');
    expect(getFieldOptionLabel('REPORT_TYPE', 'simple', undefined, 'zh')).toBe('简洁');
    expect(getFieldOptionLabel('REPORT_TYPE', 'simple', undefined, 'en')).toBe('Simple');
    expect(getFieldOptionLabel('NOT_A_REAL_OPTION', 'mystery', 'Server label', 'tr')).toBe('Server label');
  });

  it('formats run-flow dates with Turkish locale and preserves earlier locale behavior', () => {
    const value = '2026-11-18T12:34:00Z';
    expect(formatDateTime(value, 'tr', t)).toBe(new Date(value).toLocaleString('tr-TR'));
    expect(formatDateTime(value, 'en', t)).toBe(new Date(value).toLocaleString('en-US'));
    expect(formatDateTime(value, 'zh', t)).toBe(new Date(value).toLocaleString('zh-CN'));
    expect(formatDateTime(null, 'tr', t)).toBe('runFlow.valueUnavailable');
  });
});
