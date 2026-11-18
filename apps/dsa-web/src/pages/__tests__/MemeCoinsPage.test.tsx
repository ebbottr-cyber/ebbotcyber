import { describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
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

  it('renders results and filters the two read-only strategies after a manual scan', async () => {
    vi.mocked(memeRadarApi.status).mockResolvedValue({
      available: true,
      live_enabled: true,
      trading_enabled: false,
      strategies: ['new_coin_hunter', 'momentum_watcher'],
    });
    vi.mocked(memeRadarApi.scan).mockResolvedValue({
      enabled: true,
      trading_enabled: false,
      errors: [],
      candidates: [
        {
          strategy: 'new_coin_hunter',
          mint: 'So11111111111111111111111111111111111111112',
          symbol: 'NEW',
          pool_id: 'solana_pool1',
          source: 'geckoterminal',
          score: 75,
          status: 'watch',
          reasons: [],
        },
        {
          strategy: 'momentum_watcher',
          mint: 'So11111111111111111111111111111111111111113',
          symbol: 'MOVE',
          pool_id: 'solana_pool2',
          source: 'dexscreener',
          score: 50,
          status: 'blocked',
          reasons: ['security_unknown'],
        },
      ],
    });
    render(<MemeCoinsPage />);
    const scanButton = await screen.findByRole('button', { name: 'Coinleri tara' });
    await waitFor(() => expect(scanButton.hasAttribute('disabled')).toBe(false));
    fireEvent.click(scanButton);
    await waitFor(() => expect(memeRadarApi.scan).toHaveBeenCalledWith(5));
    expect(await screen.findByText('NEW')).toBeDefined();
    expect(screen.getByText('MOVE')).toBeDefined();

    fireEvent.change(screen.getByRole('combobox', { name: 'Strateji' }), {
      target: { value: 'momentum_watcher' },
    });
    expect(screen.queryByText('NEW')).toBeNull();
    expect(screen.getByText('MOVE')).toBeDefined();
  });
});
