import { describe, expect, it } from 'vitest';
import { getStockDisplayName } from './stockDisplayName';

describe('Latin-script stock display names', () => {
  it('preserves proper company identities instead of translating brands', () => {
    expect(getStockDisplayName('AAPL', '苹果')).toBe('Apple');
    expect(getStockDisplayName('AAPL.US', 'Elma')).toBe('Apple');
    expect(getStockDisplayName('MSFT', '微软')).toBe('Microsoft');
    expect(getStockDisplayName('NVDA', '英伟达')).toBe('NVIDIA');
    expect(getStockDisplayName('00700.HK', '腾讯控股')).toBe('Tencent');
    expect(getStockDisplayName('HK01810', '小米集团')).toBe('Xiaomi');
  });

  it('shows Hong Kong names in Latin without changing the symbol identity', () => {
    expect(getStockDisplayName('HK00700', '腾讯控股', { nameEn: 'Tencent Holdings' })).toBe('Tencent Holdings');
    expect(getStockDisplayName('0700.HK', 'Tencent Holdings')).toBe('Tencent Holdings');
    expect(getStockDisplayName('HK00700', '腾讯控股')).toBe('Tencent');
    expect(getStockDisplayName('HK09999', '中文公司')).toBe('HK09999');
    expect(getStockDisplayName('09999.HK', '中文公司', { pinyinFull: 'shili gongsi' })).toBe('Shili gongsi');
  });

  it('keeps source-provided Latin names for other instruments', () => {
    expect(getStockDisplayName('THYAO.IS', 'Türk Hava Yolları')).toBe('Türk Hava Yolları');
    expect(getStockDisplayName('UNKNOWN', 'Alphabet Inc.')).toBe('Alphabet Inc.');
    expect(getStockDisplayName('600519.SH', '贵州茅台', { nameEn: 'Kweichow Moutai' }))
      .toBe('Kweichow Moutai');
  });

  it('uses a romanized name instead of a literal translation', () => {
    expect(getStockDisplayName('600519.SH', '贵州茅台', { pinyinFull: 'guizhoumaotai' }))
      .toBe('Guizhoumaotai');
    expect(getStockDisplayName('600519.SH', '贵州茅台', { aliases: ['Guizhou Moutai'] }))
      .toBe('Guizhou Moutai');
  });

  it('falls back to unambiguous ticker when no Latin name is known', () => {
    expect(getStockDisplayName('600519.SH', '贵州茅台')).toBe('600519.SH');
    expect(getStockDisplayName('AAPL', '')).toBe('Apple');
    expect(getStockDisplayName('ZZZZ', '')).toBe('ZZZZ');
  });
});
