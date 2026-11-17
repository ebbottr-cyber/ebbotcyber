import type React from 'react';
import { useEffect, useMemo, useState } from 'react';
import { Activity, AlertTriangle, BarChart3, RefreshCw, ShieldCheck } from 'lucide-react';
import {
  cryptoFuturesApi, normalizeFuturesSymbol,
  type FuturesTicker, type FuturesFunding, type FuturesOHLCV,
  type FuturesDepth, type FuturesOpenInterest, type FuturesTimeframe,
} from '../../api/cryptoFutures';
import type { SpotCandle } from '../../api/cryptoSpot';

const PAIRS = ['BTC/USDT', 'ETH/USDT', 'SOL/USDT', 'BNB/USDT', 'XRP/USDT'];
const TIMEFRAMES: FuturesTimeframe[] = ['1m', '5m', '15m', '1h', '4h', '1d'];

function num(value: number | null | undefined, decimals = 4) {
  return typeof value === 'number' && Number.isFinite(value)
    ? new Intl.NumberFormat('tr-TR', { maximumFractionDigits: decimals }).format(value)
    : 'Veri yok';
}

function time(value: number | null | undefined) {
  return typeof value === 'number' && Number.isFinite(value) && value > 0
    ? new Date(value).toLocaleString('tr-TR')
    : 'Bilinmiyor';
}

function FuturesCandleChart({ bars }: { bars: SpotCandle[] }) {
  const rows = useMemo(() => bars.slice(-75), [bars]);
  if (rows.length < 2) return <p className="p-6 text-sm text-muted-text">Mum grafiği için yeterli veri yok.</p>;
  const low = Math.min(...rows.map(v => v.low));
  const high = Math.max(...rows.map(v => v.high));
  const margin = (high - low || high * .01 || 1) * .08;
  const min = Math.max(0, low - margin);
  const max = high + margin;
  const x = (i: number) => 12 + ((i + .5) / rows.length) * 652;
  const y = (n: number) => 12 + ((max - n) / (max - min)) * 235;
  const bodyWidth = Math.max(2, 652 / rows.length * .6);
  return <svg viewBox="0 0 760 290" width="100%" role="img"
    aria-label="Binance USD-M Futures OHLCV mum grafiği">
    {[0, 1, 2, 3, 4].map(i => {
      const yy = 12 + 235 * (i / 4);
      return <g key={i}>
        <line x1="12" x2="664" y1={yy} y2={yy} stroke="currentColor"
          strokeOpacity=".10" strokeDasharray="4 5"/>
        <text x="675" y={yy + 4} fontSize="12" fill="currentColor" opacity=".65">
          {num(max - (max - min) * i / 4)}
        </text>
      </g>;
    })}
    {rows.map((candle, i) => {
      const color = candle.close >= candle.open ? '#13ae74' : '#e65362';
      const upper = Math.min(y(candle.open), y(candle.close));
      const lower = Math.max(y(candle.open), y(candle.close));
      return <g key={candle.timestamp}>
        <line x1={x(i)} x2={x(i)} y1={y(candle.high)} y2={y(candle.low)}
          stroke={color} strokeWidth="1.4"/>
        <rect x={x(i) - bodyWidth / 2} y={upper} width={bodyWidth}
          height={Math.max(1.5, lower - upper)} fill={color} rx=".6"/>
      </g>;
    })}
    {[0, Math.floor(rows.length / 2), rows.length - 1].map(i => (
      <text key={i} x={x(i)} y="274" textAnchor="middle" fontSize="12" fill="currentColor" opacity=".65">
        {new Date(rows[i].timestamp).toLocaleDateString('tr-TR', { day: '2-digit', month: '2-digit' })}
      </text>
    ))}
  </svg>;
}

function Stat({ label, value, note }: { label: string; value: string; note?: string }) {
  return <div className="min-w-0 rounded-xl border border-border bg-card p-4">
    <p className="text-xs font-medium text-muted-text">{label}</p>
    <p className="mt-2 break-words text-lg font-bold tabular-nums text-foreground">{value}</p>
    {note ? <p className="mt-1 text-[11px] leading-5 text-muted-text">{note}</p> : null}
  </div>;
}

export const CryptoFuturesPanel: React.FC<{ paperSnapshot?: unknown }> = ({ paperSnapshot }) => {
  const [symbol, setSymbol] = useState('BTC/USDT');
  const [draft, setDraft] = useState('BTC/USDT');
  const [timeframe, setTimeframe] = useState<FuturesTimeframe>('1h');
  const [ticker, setTicker] = useState<FuturesTicker | null>(null);
  const [ohlcv, setOhlcv] = useState<FuturesOHLCV | null>(null);
  const [depth, setDepth] = useState<FuturesDepth | null>(null);
  const [funding, setFunding] = useState<FuturesFunding | null>(null);
  const [interest, setInterest] = useState<FuturesOpenInterest | null>(null);
  const [faults, setFaults] = useState<string[]>([]);
  const [inputError, setInputError] = useState('');
  const [revision, setRevision] = useState(0);
  const [loading, setLoading] = useState(true);
  const [direction, setDirection] = useState<'LONG' | 'SHORT'>('LONG');
  const [leverage, setLeverage] = useState(3);
  const [margin, setMargin] = useState(100);
  const [shock, setShock] = useState(2);

  useEffect(() => {
    const interval = window.setInterval(() => setRevision(n => n + 1), 30_000);
    return () => window.clearInterval(interval);
  }, []);

  useEffect(() => {
    let alive = true;
    setTicker(null);
    setOhlcv(null);
    setDepth(null);
    setFunding(null);
    setInterest(null);
    setFaults([]);
    setLoading(true);
    void Promise.allSettled([
      cryptoFuturesApi.ticker(symbol),
      cryptoFuturesApi.ohlcv(symbol, timeframe, 100),
      cryptoFuturesApi.orderbook(symbol, 20),
      cryptoFuturesApi.funding(symbol),
      cryptoFuturesApi.openInterest(symbol),
    ]).then(results => {
      if (!alive) return;
      setTicker(results[0].status === 'fulfilled' ? results[0].value : null);
      setOhlcv(results[1].status === 'fulfilled' ? results[1].value : null);
      setDepth(results[2].status === 'fulfilled' ? results[2].value : null);
      setFunding(results[3].status === 'fulfilled' ? results[3].value : null);
      setInterest(results[4].status === 'fulfilled' ? results[4].value : null);
      setFaults(['Son fiyat', 'Mum verisi', 'Emir defteri', 'Funding', 'Open interest']
        .filter((_, i) => results[i].status === 'rejected'));
      setLoading(false);
    });
    return () => { alive = false; };
  }, [symbol, timeframe, revision]);

  const apply = (event: React.FormEvent) => {
    event.preventDefault();
    try {
      const pair = normalizeFuturesSymbol(draft);
      setSymbol(pair);
      setDraft(pair);
      setInputError('');
    } catch {
      setInputError('Geçerli bir USD-M sürekli sözleşme yaz (örn. BTC/USDT).');
    }
  };
  const selectPair = (pair: string) => {
    setSymbol(pair);
    setDraft(pair);
    setInputError('');
  };

  const notional = margin * leverage;
  // PnL of an illustrative price shock; not a liquidation threshold or
  // executable order quote. The negative scenario is adverse for either side.
  const adversePnl = -(notional * shock / 100);
  const favorablePnl = notional * shock / 100;
  const fundingPayment = funding ? notional * funding.funding_rate *
    (direction === 'LONG' ? -1 : 1) : null;

  return <div className="space-y-4" data-testid="ebbot-binance-futures">
    <header className="rounded-2xl border border-border bg-card p-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h2 className="text-base font-bold text-foreground">Binance USD-M Futures · Perpetual</h2>
          <p className="mt-1 text-xs text-muted-text">
            Spot'tan ayrı piyasa · Sunucu tarafında CCXT sözleşmesi: {symbol}:USDT
          </p>
        </div>
        <button type="button" onClick={() => setRevision(n => n + 1)}
          className="flex items-center gap-2 rounded-lg border border-border px-3 py-2 text-xs">
          <RefreshCw className="h-4 w-4"/> Yenile
        </button>
      </div>
      <form onSubmit={apply} className="mt-4 flex flex-wrap items-center gap-2">
        <label htmlFor="futures-symbol" className="text-xs font-semibold">Sözleşme</label>
        <input id="futures-symbol" value={draft} onChange={e => setDraft(e.target.value)}
          maxLength={26} className="w-36 rounded-lg border border-border bg-background px-3 py-2 font-mono text-sm" />
        <button type="submit" className="rounded-lg bg-primary px-3 py-2 text-xs font-bold text-primary-foreground">
          Getir
        </button>
        {PAIRS.map(pair => <button type="button" key={pair} onClick={() => selectPair(pair)}
          aria-pressed={symbol === pair}
          className={'rounded-lg border px-2 py-1.5 text-xs ' +
            (symbol === pair ? 'border-primary bg-primary/10 text-primary' : 'border-border')}>
          {pair}
        </button>)}
      </form>
      {inputError ? <p role="alert" className="mt-2 text-xs text-danger">{inputError}</p> : null}
      <div className="mt-3 flex flex-wrap gap-1">
        {TIMEFRAMES.map(value => <button type="button" key={value}
          onClick={() => setTimeframe(value)} aria-pressed={timeframe === value}
          className={'rounded-lg border px-3 py-1.5 text-xs ' +
            (value === timeframe ? 'border-primary bg-primary/10 font-bold text-primary' : 'border-border')}>
          {value}
        </button>)}
      </div>
      <p className="mt-3 flex items-center gap-2 text-xs text-muted-text">
        <ShieldCheck className="h-4 w-4 text-success"/> TRADING_ENABLED=false · Yalnızca kamuya açık veri
      </p>
    </header>

    {loading ? <div role="status" className="rounded-xl bg-surface p-4 text-sm text-muted-text">
      USD-M Futures verileri kontrol ediliyor…
    </div> : null}
    {!loading && faults.length > 0 ? <div role="alert" className="rounded-xl border border-border bg-card p-3 text-xs text-danger">
      {faults.join(', ')} alınamadı veya güvenlik doğrulamasını geçmedi. Eksik bilgiye sıfır yazılmadı.
    </div> : null}

    <div className="grid grid-cols-2 gap-3 xl:grid-cols-4">
      <Stat label="Futures son işlem fiyatı" value={ticker ? num(ticker.last, 6) + ' USDT' : 'Veri yok'}
        note={ticker?.quality === 'ok' ? 'Kaynak zaman damgası güncel' :
          ticker?.quality === 'unknown' ? 'Kaynak zaman damgası yok' : undefined} />
      <Stat label="Mark fiyatı" value={funding ? num(funding.mark_price, 6) + ' USDT' : 'Veri yok'}
        note="Funding kaynağında doğrulanmış anlık fiyat zaman damgası yok" />
      <Stat label="Index fiyatı" value={funding?.index_price != null ? num(funding.index_price, 6) + ' USDT' : 'Veri yok'} />
      <Stat label="Açık pozisyon miktarı (OI)" value={interest ? num(interest.open_interest, 4) + ' ' + interest.unit : 'Veri yok'}
        note={interest ? 'Binance /fapi/v1/openInterest · ' + time(interest.timestamp) : 'Kaynak erişimi bekleniyor'} />
    </div>

    <div className="grid gap-4 xl:grid-cols-[1.7fr_1fr]">
      <section className="min-w-0 rounded-2xl border border-border bg-card p-4">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <h3 className="text-sm font-bold"><BarChart3 className="mr-2 inline h-4 w-4 text-primary" />
            {symbol} Futures · OHLCV
          </h3>
          <span className="text-xs text-muted-text">
            {ohlcv ? ohlcv.count + ' mum' : 'Veri yok'}
          </span>
        </div>
        <div className="mt-3">
          {ohlcv ? <FuturesCandleChart bars={ohlcv.candles} /> :
            <p className="py-10 text-center text-xs text-muted-text">Doğrulanmış Futures mum verisi bulunamadı.</p>}
        </div>
      </section>
      <section className="min-w-0 rounded-2xl border border-border bg-card p-4">
        <h3 className="text-sm font-bold">Funding ve Emir Defteri</h3>
        <div className="mt-4 grid grid-cols-2 gap-3 text-xs">
          <div className="rounded-lg bg-surface p-3">
            <p className="text-muted-text">Funding oranı</p>
            <p className="mt-2 text-lg font-bold tabular-nums">{funding ? num(funding.funding_rate * 100, 5) + '%' : 'Veri yok'}</p>
          </div>
          <div className="rounded-lg bg-surface p-3">
            <p className="text-muted-text">Funding aralığı</p>
            <p className="mt-2 text-lg font-bold">{funding ? funding.funding_interval_hours + ' saat' : 'Veri yok'}</p>
          </div>
        </div>
        <p className="mt-3 text-xs text-muted-text">Sonraki funding: {time(funding?.next_funding_timestamp)}</p>
        <p className="mt-1 text-xs text-muted-text">Funding oranı sonraki ödemeden önce değişebilir.</p>
        {depth ? <>
          <div className="mt-4 grid grid-cols-2 gap-3 border-t border-border pt-3">
            {(['bids', 'asks'] as const).map(side => <div key={side} className="min-w-0">
              <p className={'mb-2 text-xs font-semibold ' + (side === 'bids' ? 'text-success' : 'text-danger')}>
                {side === 'bids' ? 'Alış' : 'Satış'}
              </p>
              <div className="space-y-1 font-mono text-[11px]">
                {depth[side].slice(0, 10).map((level, i) =>
                  <div key={i} className="flex justify-between gap-2">
                    <span>{num(level[0], 4)}</span><span className="text-muted-text">{num(level[1], 3)}</span>
                  </div>)}
              </div>
            </div>)}
          </div>
          <p className="mt-3 text-xs text-muted-text">
            {depth.quality === 'ok' ? 'Emir defteri zaman damgası güncel' : 'Kaynak zaman damgası bilinmiyor'}
          </p>
        </> : <p className="mt-4 text-xs text-muted-text">Emir defteri erişilemiyor.</p>}
      </section>
    </div>

    <section className="rounded-2xl border border-border bg-card p-4">
      <h3 className="text-sm font-bold">Long / Short · Varsayımsal risk senaryosu</h3>
      <p className="mt-1 text-xs text-muted-text">
        Bu hesap gerçek emir, işlem sinyali veya likidasyon fiyatı değildir. Komisyon, funding ve maintenance margin
        gereksinimleri ayrı değerlendirilmeden işlem kararı için kullanılamaz.
      </p>
      <div className="mt-4 grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <div>
          <label className="text-xs font-semibold">Yön</label>
          <div className="mt-2 flex gap-2">
            {(['LONG', 'SHORT'] as const).map(side => <button key={side} type="button"
              aria-pressed={direction === side} onClick={() => setDirection(side)}
              className={'rounded-lg border px-3 py-2 text-xs ' +
                (direction === side ? 'border-primary bg-primary/10 font-bold text-primary' : 'border-border')}>
              {side}
            </button>)}
          </div>
        </div>
        <div>
          <label htmlFor="future-margin" className="text-xs font-semibold">Varsayımsal teminat (USDT)</label>
          <input id="future-margin" type="number" min="10" max="10000" step="10" value={margin}
            onChange={e => setMargin(Math.min(10000, Math.max(10, Number(e.target.value) || 10)))}
            className="mt-2 w-full rounded-lg border border-border bg-background px-3 py-2 text-sm" />
        </div>
        <div>
          <label htmlFor="future-leverage" className="text-xs font-semibold">Kaldıraç: {leverage}x</label>
          <input id="future-leverage" type="range" min="1" max="20" step="1" value={leverage}
            onChange={e => setLeverage(Number(e.target.value))} className="mt-3 w-full" />
        </div>
        <div>
          <label htmlFor="future-shock" className="text-xs font-semibold">Fiyat hareketi: %{shock}</label>
          <input id="future-shock" type="range" min="1" max="10" step="1" value={shock}
            onChange={e => setShock(Number(e.target.value))} className="mt-3 w-full" />
        </div>
      </div>
      <div className="mt-4 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        <Stat label="Varsayımsal pozisyon büyüklüğü" value={num(notional, 2) + ' USDT'} />
        <Stat label={'Aleyhe %' + shock + ' hareket / teorik PnL'} value={num(adversePnl, 2) + ' USDT'} />
        <Stat label={'Lehe %' + shock + ' hareket / teorik PnL'} value={'+' + num(favorablePnl, 2) + ' USDT'} />
        <Stat label="Bir periyotta teorik funding nakit akışı" value={fundingPayment === null ?
          'Veri yok' : num(fundingPayment, 5) + ' USDT'} />
      </div>
      <div className="mt-4 flex items-start gap-2 rounded-lg bg-surface p-3 text-xs leading-5 text-muted-text">
        <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-warning"/>
        Eksi PnL teminatın tamamını aşabilir. Bu hesap izole marjin likidasyonu, bakım marjı kademeleri,
        slippage, komisyon ve stop tetikleme modelini içermez. Gerçek likidasyon seviyesi: hesaplanmadı.
      </div>
    </section>

    {paperSnapshot !== undefined && paperSnapshot !== null && <section className="rounded-2xl border border-border bg-card p-4">
      <h3 className="text-sm font-semibold">Futures Paper hesabı · Ayrı kayıt</h3>
      <p className="mt-1 text-xs text-muted-text">Kaynak: doğrulanmış Trading Office dashboard sözleşmesi; emir yürütme kapalı.</p>
      <pre className="mt-3 max-h-64 overflow-auto whitespace-pre-wrap break-words rounded-lg bg-surface p-3 text-xs text-secondary-text">
        {JSON.stringify(paperSnapshot, null, 2)}
      </pre>
    </section>}
    <p className="flex items-center gap-2 text-xs text-muted-text">
      <Activity className="h-4 w-4"/> Binance/Trading Office REST · Yaklaşık 30 saniyede bir kontrol
    </p>
  </div>;
};
