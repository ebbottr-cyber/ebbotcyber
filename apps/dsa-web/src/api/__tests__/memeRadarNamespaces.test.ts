import { beforeEach, describe, expect, it, vi } from 'vitest';
import { memeRadarApi } from '../memeRadar';

const { get, post } = vi.hoisted(() => ({ get: vi.fn(), post: vi.fn() }));
vi.mock('../index', () => ({
  default: { get, post },
}));

describe('read-only Radar and strategy namespaces', () => {
  beforeEach(() => {
    vi.resetAllMocks();
  });

  it('fetches only the independent Radar status endpoint', async () => {
    get.mockResolvedValue({
      data: {
        available: true, live_enabled: false, trading_enabled: false,
        strategies: ['new_coin_hunter', 'momentum_watcher'],
      },
    });
    const result = await memeRadarApi.status();
    expect(get).toHaveBeenCalledWith('/api/v1/meme-radar/status');
    expect(post).not.toHaveBeenCalled();
    expect(result.trading_enabled).toBe(false);
    expect(result.live_enabled).toBe(false);
  });

  it('only uses manual Radar scan URI and never sends trade instructions', async () => {
    post.mockResolvedValue({
      data: { enabled: true, trading_enabled: false, candidates: [], errors: [] },
    });
    const result = await memeRadarApi.scan(5);
    expect(post).toHaveBeenCalledWith(
      '/api/v1/meme-radar/scan',
      { limit: 5 },
      { timeout: 90000 },
    );
    expect(get).not.toHaveBeenCalled();
    expect(result.trading_enabled).toBe(false);
  });
});
