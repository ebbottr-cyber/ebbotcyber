import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import type { TrMarketItem } from '../../../api/trMarketOverview';
import { TurkeyMarketCards } from '../TurkeyMarketCards';

const data: TrMarketItem[] = [
  {
    key: 'bist100', label: 'BIST 100', symbol: 'XU100.IS', currency: 'TRY',
    price: 11010.5, changePct: 1.25, asOf: '2026-11-17', status: 'ready',
    source: 'Yahoo Finance', note: 'Günlük fiyat',
  },
  {
    key: 'usdtry', label: 'USD/TRY', symbol: 'TRY=X', currency: 'TRY',
    price: 43.1254, changePct: -0.14, asOf: '2026-11-17', status: 'ready',
    source: 'Yahoo Finance', note: 'Günlük fiyat',
  },
  {
    key: 'bist30', label: 'BIST 30', symbol: 'XU030.IS', currency: 'TRY',
    price: null, changePct: null, asOf: '2026-11-08', status: 'stale',
    source: 'Yahoo Finance', note: 'Son fiyat güncel değil',
  },
  {
    key: 'gramgold', label: 'Gram Altın', symbol: null, currency: 'TRY/g',
    price: null, changePct: null, asOf: null, status: 'unavailable',
    source: null, note: 'Doğrulanmış kaynak henüz bağlı değil',
  },
];

describe('Türkiye piyasaları — kaynaklı, mobil kartlar', () => {
  it('displays real supplied values and distinct forex precision', () => {
    render(<TurkeyMarketCards items={data} loading={false} failed={false} />);
    expect(screen.getByText('11.010,50')).toBeInTheDocument();
    expect(screen.getByText('43,1254')).toBeInTheDocument();
    expect(screen.getByText('+1,25%')).toBeInTheDocument();
    expect(screen.getByText('−0,14%')).toBeInTheDocument();
    expect(screen.getAllByText('Veri günü: 17.11.2026')).toHaveLength(2);
  });

  it('never displays stale or unavailable prices as valid values', () => {
    render(<TurkeyMarketCards items={data} loading={false} failed={false} />);
    expect(screen.getByRole('article', { name: 'BIST 30' })).toHaveTextContent('—');
    expect(screen.getByRole('article', { name: 'BIST 30' })).toHaveTextContent('Eski veri');
    expect(screen.getByRole('article', { name: 'Gram Altın' })).toHaveTextContent('Doğrulanmış kaynak');
    expect(screen.getByRole('article', { name: 'EUR/TRY' })).toHaveTextContent('Veri yok');
  });

  it('shows loading and network failures without fabricated figures', () => {
    const view = render(<TurkeyMarketCards items={[]} loading failed={false} />);
    expect(screen.getAllByText('Yükleniyor…')).toHaveLength(5);
    view.rerender(<TurkeyMarketCards items={[]} loading={false} failed />);
    expect(screen.getAllByText('Kaynağa erişilemedi')).toHaveLength(5);
  });

  it('allows keyboard horizontal scrolling and mobile snap layout', () => {
    render(<TurkeyMarketCards items={[]} loading={false} failed={false} />);
    const section = screen.getByTestId('turkey-market-cards');
    const scroller = screen.getByLabelText('Piyasa kartları, sağa sola kaydırın');
    expect(scroller).toHaveAttribute('tabindex', '0');
    expect(scroller.className).toContain('overflow-x-auto');
    expect(scroller.className).toContain('snap-x');
    expect(section.querySelectorAll('article')).toHaveLength(5);
  });

  it('hides previous prices during refresh and after a network error', () => {
    const view = render(<TurkeyMarketCards items={data} loading={false} failed={false} />);
    expect(screen.getByText('11.010,50')).toBeInTheDocument();
    view.rerender(<TurkeyMarketCards items={data} loading failed={false} />);
    expect(screen.queryByText('11.010,50')).not.toBeInTheDocument();
    expect(screen.getAllByText('Yükleniyor…')).toHaveLength(5);
    view.rerender(<TurkeyMarketCards items={data} loading={false} failed />);
    expect(screen.queryByText('43,1254')).not.toBeInTheDocument();
    expect(screen.getAllByText('Kaynağa erişilemedi')).toHaveLength(5);
  });

  it('clearly labels Yahoo values as delayed and non-executable', () => {
    render(<TurkeyMarketCards items={data} loading={false} failed={false} />);
    expect(screen.getByText(/Anlık veya işlem yapılabilir fiyat değildir/)).toBeInTheDocument();
    expect(screen.getByText(/Gram altın için doğrulanmış/)).toBeInTheDocument();
  });
});
