import { TrendingDown, TrendingUp } from 'lucide-react';
import type { TrMarketItem, TrMarketKey } from '../../api/trMarketOverview';

const MARKET_CARDS: ReadonlyArray<{ key: TrMarketKey; label: string }> = [
  { key: 'bist100', label: 'BIST 100' },
  { key: 'bist30', label: 'BIST 30' },
  { key: 'usdtry', label: 'USD/TRY' },
  { key: 'eurtry', label: 'EUR/TRY' },
  { key: 'gramgold', label: 'Gram Altın' },
];

const surface = 'rounded-2xl border border-[#e1e9f5] bg-white shadow-[0_8px_25px_rgba(30,69,130,0.045)]';

function formatPrice(value: number, key: TrMarketKey): string {
  const currencyPair = key === 'usdtry' || key === 'eurtry';
  return new Intl.NumberFormat('tr-TR', {
    minimumFractionDigits: 2,
    maximumFractionDigits: currencyPair ? 4 : 2,
  }).format(value);
}

function formatPct(value: number): string {
  const magnitude = new Intl.NumberFormat('tr-TR', {
    minimumFractionDigits: 2, maximumFractionDigits: 2,
  }).format(Math.abs(value));
  return (value > 0 ? '+' : value < 0 ? '−' : '') + magnitude + '%';
}

function shortDate(date: string): string {
  const parsed = new Date(date + 'T12:00:00Z');
  return Number.isNaN(parsed.getTime()) ? date : parsed.toLocaleDateString('tr-TR', { timeZone: 'UTC' });
}

interface Props {
  items: TrMarketItem[];
  loading: boolean;
  failed: boolean;
}

export function TurkeyMarketCards({ items, loading, failed }: Props) {
  return (
    <section aria-label="Türkiye piyasa kartları" data-testid="turkey-market-cards">
      <div tabIndex={0} aria-label="Piyasa kartları, sağa sola kaydırın"
        className="flex snap-x snap-mandatory gap-3 overflow-x-auto overscroll-x-contain pb-2 focus-visible:outline focus-visible:outline-2 focus-visible:outline-[#2977d5]">
        {MARKET_CARDS.map(({ key, label }) => {
          const item = items.find((row) => row.key === key);
          const ready = item?.status === 'ready' &&
            typeof item.price === 'number' && Number.isFinite(item.price) && item.price > 0;
          const change = ready && typeof item?.changePct === 'number' && Number.isFinite(item.changePct)
            ? item.changePct : null;
          const message = loading ? 'Yükleniyor…' : failed ? 'Kaynağa erişilemedi'
            : item?.status === 'stale' ? 'Eski veri – fiyat gizlendi'
              : item?.note || 'Veri yok';
          return (
            <article key={key} aria-label={label}
              className={surface + ' min-w-[160px] flex-1 snap-start px-3 py-3 sm:min-w-[180px] sm:px-4'}>
              <p className="text-xs font-semibold text-[#536a88]">{label}</p>
              <p className="mt-1 text-lg font-extrabold tabular-nums text-[#183055]">
                {ready ? formatPrice(item.price as number, key) : '—'}
              </p>
              {ready ? (
                <>
                  <p className={'mt-0.5 flex items-center gap-1 text-xs font-semibold ' +
                    (change === null ? 'text-[#8494aa]' : change >= 0 ? 'text-[#14a870]' : 'text-[#e45a5a]')}>
                    {change !== null ? change >= 0
                      ? <TrendingUp className="h-3.5 w-3.5" />
                      : <TrendingDown className="h-3.5 w-3.5" /> : null}
                    {change === null ? 'Değişim yok' : formatPct(change)}
                  </p>
                  <p className="mt-2 text-[10px] text-[#8a9ab1]">{item?.asOf ? 'Veri günü: ' + shortDate(item.asOf) : 'Veri günü bilinmiyor'}</p>
                </>
              ) : (
                <p className="mt-1 line-clamp-2 min-h-[36px] text-[11px] leading-[18px] text-[#8494aa]">{message}</p>
              )}
            </article>
          );
        })}
      </div>
      <p className="mt-1 text-[11px] text-[#8494ab]">
        Kaynak: Yahoo Finance, gecikmeli günlük piyasa verisi. Anlık veya işlem yapılabilir fiyat değildir.
        Gram altın için doğrulanmış TRY/gram kaynağı bekleniyor.
      </p>
    </section>
  );
}

export default TurkeyMarketCards;
