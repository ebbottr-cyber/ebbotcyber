import { describe, expect, it } from 'vitest';
import { render, screen } from '@testing-library/react';
import SolanaArchiveQuality from '../SolanaArchiveQuality';

describe('SolanaArchiveQuality', () => {
  it('displays the dated and independently audited archived counts, not live data', () => {
    render(<SolanaArchiveQuality />);

    expect(screen.getByRole('heading', { name: 'Solana arşiv veri kalitesi' })).toBeDefined();
    expect(screen.getByTestId('archive-quality-valid').textContent).toBe('9');
    expect(screen.getByTestId('archive-quality-missing').textContent).toBe('3');
    expect(screen.getByTestId('archive-quality-blocked').textContent).toBe('18');
    expect(screen.getByTestId('archive-quality-watch').textContent).toBe('0');
    expect(screen.getByText(/Anlık veri değildir ve otomatik güncellenmez/)).toBeDefined();
    expect(screen.getByText(/Doğrulanmış sanal performans, gerçek işlem/)).toBeDefined();
  });

  it('shows both source runs separately and links to the real end-to-end audit', () => {
    render(<SolanaArchiveQuality />);

    const complete = screen.getByRole('link', { name: '#44779967482' });
    const degraded = screen.getByRole('link', { name: '#44777830658' });
    const audit = screen.getByRole('link', { name: 'GitHub Actions #44791912581' });
    expect(complete.getAttribute('href')).toBe('https://github.com/ebbottr-cyber/ebbotcyber/actions/runs/44779967482');
    expect(degraded.getAttribute('href')).toBe('https://github.com/ebbottr-cyber/ebbotcyber/actions/runs/44777830658');
    expect(audit.getAttribute('href')).toBe('https://github.com/ebbottr-cyber/ebbotcyber/actions/runs/44791912581');
    expect(screen.getByText('6/6')).toBeDefined();
    expect(screen.getByText('3/6')).toBeDefined();
    expect(screen.getByText('Eksiksiz veri')).toBeDefined();
    expect(screen.getByText('Eksik veri', { exact: true })).toBeDefined();
  });

  it('offers no trading, scanner, scheduler or training controls', () => {
    render(<SolanaArchiveQuality />);

    expect(screen.queryByRole('button')).toBeNull();
    expect(screen.queryByRole('checkbox')).toBeNull();
    expect(screen.queryByRole('textbox')).toBeNull();
  });
});
