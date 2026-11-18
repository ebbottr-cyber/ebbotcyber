import { describe, expect, it, vi } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import MemeCoinsPage from '../MemeCoinsPage';
import { memeRadarApi } from '../../api/memeRadar';

vi.mock('../../api/memeRadar', () => ({
  memeRadarApi: { status: vi.fn(), scan: vi.fn() },
}));

describe('MemeCoinsPage', () => {
  it('does not allow manual scanning while the server setting is off', async () => {
    vi.mocked(memeRadarApi.status).mockResolvedValue({
      available: true,
      live_enabled: false,
      trading_enabled: false,
      strategies: ['new_coin_hunter', 'momentum_watcher'],
    });
    render(<MemeCoinsPage />);
    expect(screen.getByRole('heading', { name: 'Meme Coin Stratejileri' })).toBeDefined();
    await waitFor(() => expect(
      screen.getByRole('button', { name: 'Coinleri tara' }).hasAttribute('disabled'),
    ).toBe(true));
    expect(memeRadarApi.scan).not.toHaveBeenCalled();
  });
});
