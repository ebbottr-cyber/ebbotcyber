import { afterEach, describe, expect, it, vi } from 'vitest';
import { operatorText } from '../operatorText';

afterEach(() => {
  vi.unstubAllEnvs();
});

describe('operatorText production-only bridge', () => {
  it('keeps legacy Chinese text in compatibility test mode', () => {
    vi.stubEnv('VITE_EBBOT_TURKISH_TEST_MODE', 'false');
    expect(operatorText('告警', 'Uyarı')).toBe('告警');
  });

  it('returns Turkish text with production language lock enabled', () => {
    vi.stubEnv('VITE_EBBOT_TURKISH_TEST_MODE', 'true');
    expect(operatorText('告警', 'Uyarı')).toBe('Uyarı');
  });
});
