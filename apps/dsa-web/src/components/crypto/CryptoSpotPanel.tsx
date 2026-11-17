import type React from 'react';
import { useEffect, useMemo, useState } from 'react';
import { Activity, Database, RefreshCw, ShieldCheck } from 'lucide-react';
import {
  cryptoSpotApi, type SpotCandle, type SpotOHLCV,
  type SpotOrderbook, type SpotTicker, type SpotTimeframe,
} from '../../api/cryptoSpot';

const POPULAR = ['BTC/USDT', 'ETH/USDT', 'SOL/USDT', 'BNB/USDT', 'XRP/USDT'];
const TIMEFRAMES: SpotTimeframe[] = ['1m', '5m', '15m', '1h', '4h', '1d'];

function number(value: number | null | undefined, digits = 4): string {
  return typeof value === 'number' && Number.isFinite(value)
    ? new Intl.NumberFormat('tr-TR', { maximumFractionDigits: digits }).format(value)
    : '—';
}

function FeedState({ message }: { message: string }) {
  return <div role="status" className="rounded-xl bg-surface p-4 text-sm text-muted-text">{message}</div>;
}

function CandleChart({ data }: { data: SpotCandle[] }) {
  const candles = useMemo(() => data.slice(-75), [data]);
  if (candles.length < 2) return <FeedState message="Grafik oluşturmak için yeterli mum verisi bulunamadı." />;
  const lowest = Math.min(...candles.map(c => c.low));
  const highest = Math.max(...candles.map(c => c.high));
  const spread = highest - lowest || highest * .01 || 1;
  const minimum = Math.max(0, lowest - spread * .07);
  const maximum = highest + spread * .07;
  const left = 12; const right = 660; const top = 12; const bottom = 252;
  const y = (price: number) => top + ((maximum - price) / (maximum - minimum)) * (bottom - top);
  const x = (i: number) => left + ((i + .5) / candles.length) * (right - left);
  const width = Math.max(2, (right - left) / candles.length * .57);

  return <svg viewBox="0 0 760 288" width="100%" role="img"
    aria-label="Binance Spot gerçek geçmiş OHLCV mum grafiği" className="h-auto w-full">
    {[0, 1, 2, 3, 4].map(i => {
      const py = top + i * (bottom - top) / 4;
      return <g key={i}>
        <line x1={left} y1={py} x2={right} y2={py} stroke="currentColor" strokeOpacity=".10" strokeDasharray="3 5"/>
        <text x={right + 8} y={py + 4} fill="currentColor" opacity=".65" fontSize="12">
          {number(maximum - (maximum - minimum) * i / 4, 4)}
        </text>
      </g>;
    })}
    {candles.map((item, i) => {
      const color = item.close >= item.open ? '#10a879' : '#e35063';
      const high = Math.min(y(item.open), y(item.close));
      const low = Math.max(y(item.open), y(item.close));
      return <g key={item.timestamp}>
        <line x1={x(i)} y1={y(item.high)} x2={x(i)} y2={y(item.low)} stroke={color} strokeWidth="1.5"/>
        <rect x={x(i) - width / 2} y={high} width={width} height={Math.max(1.4, low - high)}
          fill={color} rx=".7"/>
      </g>;
    })}
    {[0, Math.floor(candles.length / 2), candles.length - 1].map(i => (
      <text key={i} x={x(i)} y={bottom + 22} fill="currentColor"
        textAnchor="middle" opacity=".65" fontSize="12">
        {new Date(candles[i].timestamp).toLocaleDateString('tr-TR', { day: '2-digit', month: '2-digit' })}
      </text>
    ))}
  </svg>;
}

export const CryptoSpotPanel: React.FC = () => {
  const [symbol, setSymbol] = useState('BTC/USDT');
  const [input, setInput] = useState('BTC/USDT');
  const [timeframe, setTimeframe] = useState<SpotTimeframe>('1h');
  const [quote, setQuote] = useState<SpotTicker | null>(null);
  const [bars, setBars] = useState<SpotOHLCV | null>(null);
  const [book, setBook] = useState<SpotOrderbook | null>(null);
  const [errors, setErrors] = useState<string[]>([]);
  const [loading, setLoading] = useState(false);
  const [revision, setRevision] = useState(0);
  const [inputError, setInputError] = useState('');

  useEffect(() => {
    const timer = window.setInterval(() => setRevision(v => v + 1), 30_000);
    return () => window.clearInterval(timer);
  }, []);

  useEffect(() => {
    let mounted = true;
    setQuote(null);
    setBars(null);
    setBook(null);
    setErrors([]);
    setLoading(true);
    void Promise.allSettled([
      cryptoSpotApi.ticker(symbol),
      cryptoSpotApi.ohlcv(symbol, timeframe, 100),
      cryptoSpotApi.orderbook(symbol, 20),
    ]).then(results => {
      if (!mounted) return;
      setQuote(results[0].status === 'fulfilled' ? results[0].value : null);
      setBars(results[1].status === 'fulfilled' ? results[1].value : null);
      setBook(results[2].status === 'fulfilled' ? results[2].value : null);
      const failed = ['Fiyat', 'Mum verisi', 'Emir defteri'].filter((_, i) => results[i].status === 'rejected');
      setErrors(failed);
      setLoading(false);
    });
    return () => { mounted = false; };
  }, [symbol, timeframe, revision]);

  const selectSymbol = (value: string) => {
    setSymbol(value);
    setInput(value);
    setInputError('');
  };
  const submit = (event: React.FormEvent) => {
    event.preventDefault();
    const next = input.trim().toUpperCase();
    if (!/^[A-Z0-9]{2,20}\/(?:USDT|USDC|BTC|ETH)$/.test(next)) {
      setInputError('Örn: BTC/USDT, ETH/USDT veya SOL/USDT biçiminde geçerli bir çift gir.');
      return;
    }
    selectSymbol(next);
  };

  return <div className="space-y-4" data-testid="ebbot-binance-spot">
    <div className="rounded-2xl border border-border bg-card p-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h3 className="text-base font-bold text-foreground">Binance Spot · Canlı piyasa verileri</h3>
          <p className="mt-1 text-xs leading-5 text-muted-text">
            Kaynak: Trading Office / Binance public API · REST güncellemesi yaklaşık 30 saniye.
            API anahtarı tarayıcıya aktarılmaz; emir gönderilmez.
          </p>
        </div>
        <button type="button" onClick={() => setRevision(v => v + 1)}
          className="inline-flex items-center gap-2 rounded-lg border border-border px-3 py-2 text-xs font-semibold text-foreground">
          <RefreshCw className="h-4 w-4" /> Yenile
        </button>
      </div>
      <form onSubmit={submit} className="mt-4 flex flex-wrap items-center gap-2">
        <label htmlFor="spot-symbol" className="text-xs font-semibold text-secondary-text">İşlem çifti</label>
        <input id="spot-symbol" type="text" value={input} onChange={e => setInput(e.target.value)}
          maxLength={26} className="w-36 rounded-lg border border-border bg-background px-3 py-2 font-mono text-sm text-foreground"/>
        <button type="submit" className="rounded-lg bg-primary px-3 py-2 text-sm font-bold text-primary-foreground">
          Göster
        </button>
        {POPULAR.map(pair => <button key={pair} type="button" onClick={() => selectSymbol(pair)}
          aria-pressed={pair === symbol} className={'rounded-lg border px-2.5 py-2 text-xs ' +
            (pair === symbol ? 'border-primary bg-primary/10 font-bold text-primary' : 'border-border text-muted-text')}>
          {pair}
        </button>)}
      </form>
      {inputError ? <p role="alert" className="mt-2 text-xs text-danger">{inputError}</p> : null}
      <div className="mt-3 flex flex-wrap gap-2">
        {TIMEFRAMES.map(value => <button key={value} type="button"
          aria-pressed={timeframe === value} onClick={() => setTimeframe(value)}
          className={'rounded-lg border px-3 py-1.5 text-xs ' +
            (timeframe === value ? 'border-primary bg-primary/10 font-bold text-primary' : 'border-border text-muted-text')}>
          {value}
        </button>)}
      </div>
      <div className="mt-3 flex items-center gap-2 text-xs text-muted-text">
        <ShieldCheck className="h-4 w-4 text-success"/> Sadece veri okuma · TRADING_ENABLED=false
      </div>
      {quote && (
        <p className="mt-2 text-xs text-muted-text" role="status">
          Fiyat kaynağı: Binance · {quote.quality === 'ok' ? 'Zaman damgası güncel' :
            'Kaynak zaman damgası yok; güncelliği doğrulanamadı'}
          {' · '}Denetim: {new Date(quote.checked_at).toLocaleTimeString('tr-TR')}
        </p>
      )}
    </div>

    {loading ? <FeedState message={symbol + ' piyasa verileri doğrulanıyor…'} /> : null}
    {!loading && errors.length ? <div role="alert" className="rounded-xl border border-border bg-card p-3 text-xs text-danger">
      {errors.join(', ')} alınamadı veya güvenilirlik kontrolünden geçmedi. Eksik verinin yerine sıfır kullanılmadı.
    </div> : null}

    <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
      {([
        ['Son fiyat', quote ? number(quote.last, 6) : 'Veri yok'],
        ['Alış / Satış', quote ? number(quote.bid, 6) + ' / ' + number(quote.ask, 6) : 'Veri yok'],
        ['24s Yüksek / Düşük', quote ? number(quote.high_24h, 5) + ' / ' + number(quote.low_24h, 5) : 'Veri yok'],
        ['24s Hacim (' + symbol.split('/')[1] + ')', quote ? number(quote.quote_volume_24h, 2) : 'Veri yok'],
      ] as const).map(([label, value]) => <div key={label} className="rounded-xl border border-border bg-card p-4">
        <p className="text-xs text-muted-text">{label}</p>
        <p className="mt-2 break-words text-lg font-bold tabular-nums text-foreground">{value}</p>
      </div>)}
    </div>

    <div className="grid gap-4 xl:grid-cols-[minmax(0,1.8fr)_minmax(260px,1fr)]">
      <div className="rounded-2xl border border-border bg-card p-4">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <h3 className="text-sm font-bold">{symbol} · {timeframe} · OHLCV</h3>
          <span className="text-xs text-muted-text">
            {bars ? bars.count + ' mum · ' + (bars.quality === 'ok' ? 'Güncel' : 'Güncellik bilinmiyor') : 'Veri yok'}
          </span>
        </div>
        <div className="mt-3">
          {bars ? <CandleChart data={bars.candles} /> : <FeedState message="Doğrulanmış mum verisi yok." />}
        </div>
        <p className="mt-2 text-xs text-muted-text">
          OHLCV gerçek Binance Spot mumlarından gelir. Bu grafik alım/satım önerisi değildir.
        </p>
      </div>
      <div className="rounded-2xl border border-border bg-card p-4">
        <h3 className="text-sm font-bold">Spot emir defteri · İlk 20 seviye</h3>
        <p className="mt-1 text-xs text-muted-text">
          {book?.quality === 'ok' ? 'Kaynak zaman damgası güncel' :
            book?.quality === 'unknown' ? 'Kaynak güncelliği doğrulanamıyor' : 'Veri yok'}
        </p>
        {book ? <>
          <div className="mt-3 grid grid-cols-2 gap-3">
            {(['bids', 'asks'] as const).map(side => <div key={side}>
              <h4 className={'mb-2 text-xs font-bold ' + (side === 'bids' ? 'text-success' : 'text-danger')}>
                {side === 'bids' ? 'Alış' : 'Satış'}
              </h4>
              <div className="space-y-1 font-mono text-xs tabular-nums">
                {book[side].slice(0, 12).map((level, index) =>
                  <div key={index} className="flex justify-between gap-2">
                    <span>{number(level[0], 5)}</span><span className="text-muted-text">{number(level[1], 4)}</span>
                  </div>)}
              </div>
            </div>)}
          </div>
          <div className="mt-4 border-t border-border pt-3 text-xs text-muted-text">
            Alış derinliği: {number(book.bid_quote_depth, 2)} · Satış derinliği: {number(book.ask_quote_depth, 2)}
          </div>
        </> : <FeedState message="Doğrulanmış emir defteri verisi yok." />}
      </div>
    </div>
    <div className="flex items-center gap-2 rounded-xl border border-border bg-card p-3 text-xs text-muted-text">
      <Database className="h-4 w-4" /> Fiyat verisinin zaman damgası yoksa güncellik bilinmiyor olarak işaretlenir.
      <Activity className="h-4 w-4" /> WebSocket ve Spot Paper emir yürütme sonraki aşamalardadır.
    </div>
  </div>;
};
