import { beforeEach, describe, expect, it, vi } from 'vitest';
import apiClient from '../index';
import { memeRadarApi } from '../memeRadar';

vi.mock('../index', () => ({
  default: { get: vi.fn(), post: vi.fn() },
}));

describe('read-only Radar and strategy namespaces', () => {
  beforeEach(() => {
    vi.resetAllMocks();
  });

  it('fetches only the independent Radar status endpoint', async () => {
    vi.mocked(apiClient.get).mockResolvedValue({
      data: {
        available: true, live_enabled: false, trading_enabled: false,
        strategies: ['new_coin_hunter', 'momentum_watcher'],
      },
    });
    const result = await memeRadarApi.status();
    expect(apiClient.get).toHaveBeenCalledWith('/api/v1/meme-radar/status');
    expect(apiClient.post).not.toHaveBeenCalled();
    expect(result.trading_enabled).toBe(false);
    expect(result.live_enabled).toBe(false);
  });

  it('only uses manual Radar scan URI and never sends trade instructions', async () => {
    vi.mocked(apiClient.post).mockResolvedValue({
      data: { enabled: true, trading_enabled: false, candidates: [], errors: [] },
    });
    const result = await memeRadarApi.scan(5);
    expect(apiClient.post).toHaveBeenCalledWith(
      '/api/v1/meme-radar/scan',
      { limit: 5 },
      { timeout: 90000 },
    );
    expect(apiClient.get).not.toHaveBeenCalled();
    expect(result.trading_enabled).toBe(false);
  });
});
