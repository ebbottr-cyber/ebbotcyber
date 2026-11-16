import { describe, expect, it } from 'vitest';

import { getSettingsHelpContent } from './settingsHelp';
import { getFieldDescriptionZh } from '../utils/systemConfigI18n';

const flattenHelp = (help: ReturnType<typeof getSettingsHelpContent>) => [
  help?.summary,
  help?.usage,
  ...(help?.valueNotes ?? []),
  ...(help?.impact ?? []),
  ...(help?.notes ?? []),
].filter(Boolean).join(' ');

describe('SearXNG settings help', () => {
  it('describes public SearXNG discovery as opt-in in Chinese', () => {
    const description = getFieldDescriptionZh('SEARXNG_PUBLIC_INSTANCES_ENABLED');

    expect(description).toContain('默认关闭');
    expect(description).toContain('设为 true');
    expect(description).not.toContain('设为 false 可禁用该默认行为');
  });
});

describe('Skill Outcome auto-weight settings help', () => {
  it('describes the attributable Outcome threshold in Chinese', () => {
    const help = getSettingsHelpContent(
      'settings.agent.AGENT_SKILL_AUTOWEIGHT',
      undefined,
      'zh',
    );
    const visibleCopy = flattenHelp(help);

    expect(visibleCopy).toContain('Outcome');
    expect(visibleCopy).toContain('30');
    expect(visibleCopy).toContain('1.0');
    expect(visibleCopy).toContain('不使用全局回测胜率');
    expect(visibleCopy).not.toContain('依赖回测');
    expect(getFieldDescriptionZh('AGENT_SKILL_AUTOWEIGHT')).toContain('Outcome');
  });

  it('describes the attributable Outcome threshold in English', () => {
    const help = getSettingsHelpContent(
      'settings.agent.AGENT_SKILL_AUTOWEIGHT',
      undefined,
      'en',
    );
    const visibleCopy = flattenHelp(help);

    expect(visibleCopy).toContain('Outcome');
    expect(visibleCopy).toContain('30');
    expect(visibleCopy).toContain('1.0');
    expect(visibleCopy).toContain('Global backtest win rates never substitute');
    expect(visibleCopy).not.toContain('Depends on backtest');
  });

  it('does not present Backtest as the Skill auto-weight data source', () => {
    const zhHelp = flattenHelp(getSettingsHelpContent(
      'settings.backtest.BACKTEST_ENABLED',
      undefined,
      'zh',
    ));
    const enHelp = flattenHelp(getSettingsHelpContent(
      'settings.backtest.BACKTEST_ENABLED',
      undefined,
      'en',
    ));

    expect(zhHelp).toContain('Skill Outcome');
    expect(zhHelp).toContain('不直接');
    expect(enHelp).toContain('Skill Outcome');
    expect(enHelp).toContain('does not directly');
  });
});


describe('Turkish locale help fallback', () => {
  it('never falls back to Chinese help text for Turkish settings', () => {
    const help = getSettingsHelpContent('settings.base.STOCK_LIST', undefined, 'tr');
    expect(help?.title).toBe("Watchlist");
    expect(flattenHelp(help)).not.toMatch(/[\u3400-\u9fff]/);
  });

  it('retains Chinese only for the explicitly selected Chinese locale', () => {
    const help = getSettingsHelpContent('settings.base.STOCK_LIST', undefined, 'zh');
    expect(help?.title).toBe('自选股列表');
  });

  it('uses a Turkish title for help without a detailed entry', () => {
    const help = getSettingsHelpContent('no-such-config-key', 'Fallback details', 'tr');
    expect(help?.title).toBe('Yapılandırma yardımı');
  });
});
