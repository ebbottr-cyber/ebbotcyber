import { describe, expect, it } from 'vitest';
import type { SetupStatusCheck } from '../../types/systemConfig';
import { localizeSetupCheck } from '../setupStatusI18n';

function setup(
  key: string,
  status: SetupStatusCheck['status'],
  message: string,
  nextStep: string | null = null,
): SetupStatusCheck {
  return { key, status, title: '原始标题', message, nextStep, category: 'base', required: status !== 'optional' };
}

describe('first-run setup localization', () => {
  it('translates the exact missing-model states from the setup API without changing status', () => {
    const llm = setup(
      'llm_primary', 'needs_action', '尚未检测到主模型配置',
      '请配置 LITELLM_MODEL、LLM_CHANNELS、LITELLM_CONFIG 或 legacy provider API Key。',
    );
    const translated = localizeSetupCheck(llm, 'tr');
    expect(translated.title).toBe('Ana Yapay Zekâ Modeli');
    expect(translated.message).toContain('Henüz ana model');
    expect(translated.nextStep).toContain('LITELLM_MODEL');
    expect(translated.status).toBe('needs_action');
    expect(llm.title).toBe('原始标题');
  });

  it('translates the Agent missing-model message and preserves its required flag', () => {
    const agent = setup(
      'llm_agent', 'needs_action',
      'Agent 未配置独立模型，且 LLM 主渠道尚不可用。',
      '请先补齐 LLM 主渠道配置。',
    );
    const translated = localizeSetupCheck(agent, 'tr');
    expect(translated.message).toContain('henüz kullanılabilir değil');
    expect(translated.nextStep).toContain('LITELLM_MODEL');
    expect(translated.required).toBe(true);
  });

  it('preserves configured stock counts and database paths', () => {
    const stock = localizeSetupCheck(setup('stock_list', 'configured', '已配置 12 只股票。'), 'tr');
    const db = localizeSetupCheck(setup('storage', 'configured', '数据库路径可用: data\\stock_analysis.db'), 'tr');
    expect(stock.message).toContain('12 hisse');
    expect(db.message).toContain('data\\stock_analysis.db');
  });

  it('labels optional notifications without incorrectly blocking the first run', () => {
    const check = setup('notification', 'optional', '通知为可选项，未配置也不影响首次跑通。');
    const translated = localizeSetupCheck(check, 'tr');
    expect(translated.title).toBe('Bildirim Kanalı');
    expect(translated.status).toBe('optional');
    expect(translated.message).toContain('isteğe bağlı');
  });

  it('keeps the original Chinese payload in Chinese mode and unknown keys intact', () => {
    const check = setup('llm_primary', 'needs_action', '尚未检测到主模型配置');
    expect(localizeSetupCheck(check, 'zh')).toBe(check);
    const unknown = setup('future_check', 'needs_action', '新状态');
    expect(localizeSetupCheck(unknown, 'tr')).toBe(unknown);
  });

  it('provides English rather than Chinese for common visible statuses', () => {
    const check = setup('stock_list', 'needs_action', '当前 STOCK_LIST 为空。', '请至少添加 1 只股票用于首次试跑。');
    const translated = localizeSetupCheck(check, 'en');
    expect(translated.title).toBe('Watchlist');
    expect(translated.message).toContain('currently empty');
    expect(translated.nextStep).toContain('at least one');
  });
});
