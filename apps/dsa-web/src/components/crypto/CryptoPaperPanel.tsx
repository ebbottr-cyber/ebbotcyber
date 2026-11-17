import type React from 'react';
import { useEffect, useState } from 'react';
import { Activity, BookOpen, CircleAlert, History, LockKeyhole, RefreshCw, ShieldCheck, Wallet } from 'lucide-react';
import {
  cryptoPaperApi,
  type PaperAccount, type PaperEvent, type PaperHistory,
  type PaperMarket, type PaperPosition, type PaperSummary,
} from '../../api/cryptoPaper';

type PaperView = 'paper' | 'positions' | 'history';

function amount(v: number | null | undefined, decimals = 2) {
  return typeof v === 'number' && Number.isFinite(v)
    ? new Intl.NumberFormat('tr-TR', { maximumFractionDigits: decimals }).format(v)
    : 'Değerlenemiyor';
}
function when(v: string) {
  const d = new Date(v);
  return Number.isFinite(d.getTime()) ? d.toLocaleString('tr-TR') : 'Tarih yok';
}
function Card({ label, value, note }: { label: string; value: string; note?: string }) {
  return <div className="rounded-xl border border-border bg-card p-4">
    <p className="text-xs text-muted-text">{label}</p>
    <p className="mt-2 break-words text-lg font-bold tabular-nums">{value}</p>
    {note ? <p className="mt-1 text-[11px] text-muted-text">{note}</p> : null}
  </div>;
}
function PositionRows({ positions }: { positions: PaperPosition[] }) {
  if (!positions.length) return <p className="p-5 text-sm text-muted-text">
    Kaynak sanal defterde açık pozisyon bulunamadı.
  </p>;
  return <div className="overflow-x-auto">
    <table className="w-full min-w-[760px] text-left text-xs">
      <thead className="bg-surface text-muted-text"><tr>
        <th className="px-3 py-3">Piyasa</th>
        <th className="px-3 py-3">Sözleşme</th>
        <th className="px-3 py-3">Yön</th>
        <th className="px-3 py-3">Miktar</th>
        <th className="px-3 py-3">Giriş/ortalama</th>
        <th className="px-3 py-3">Mark fiyatı</th>
        <th className="px-3 py-3">Açık PnL</th>
        <th className="px-3 py-3">Marjin</th>
      </tr></thead>
      <tbody>{positions.map(p => <tr key={p.market + ':' + p.symbol} className="border-t border-border/70">
        <td className="px-3 py-3">{p.market === 'spot' ? 'Spot' : 'Futures'}</td>
        <td className="px-3 py-3 font-mono font-semibold">{p.symbol}</td>
        <td className="px-3 py-3">{p.side === 'BUY' ? 'Spot AL' : p.side}</td>
        <td className="px-3 py-3 font-mono">{amount(p.quantity, 8)}</td>
        <td className="px-3 py-3">{amount(p.market === 'spot' ? p.average_price : p.entry_price, 6)}</td>
        <td className="px-3 py-3">{amount(p.mark_price, 6)}</td>
        <td className="px-3 py-3 font-semibold">{amount(p.unrealized_pnl, 4)}</td>
        <td className="px-3 py-3">{p.market === 'futures'
          ? amount(p.margin, 4) + ' USDT (' + p.leverage + 'x)' : '—'}</td>
      </tr>)}</tbody>
    </table>
  </div>;
}
function PaperAccountView({ data }: { data: PaperAccount }) {
  const spot = data.market === 'spot';
  return <div className="space-y-3">
    <div className="grid grid-cols-2 gap-3 xl:grid-cols-4">
      <Card label={spot ? 'Spot sanal nakit' : 'Futures kullanılabilir cüzdan'}
        value={amount(spot ? data.cash : data.wallet_balance, 2) + ' USDT'} />
      <Card label="Hesap özsermayesi" value={data.valuation_complete
        ? amount(data.equity, 2) + ' USDT' : 'Değerlenemiyor'}
        note={data.valuation_complete ? 'Kaynak hesap raporu' : 'Piyasa fiyatı eksik'} />
      <Card label="Gerçekleşmiş PnL" value={amount(data.realized_pnl, 4) + ' USDT'} />
      <Card label="Gerçekleşmemiş PnL" value={amount(data.unrealized_pnl, 4) + (data.unrealized_pnl === null ? '' : ' USDT')} />
    </div>
    <div className="rounded-2xl border border-border bg-card">
      <div className="flex flex-wrap items-center justify-between gap-2 border-b border-border p-4">
        <h4 className="text-sm font-bold">{spot ? 'Spot' : 'USD-M Futures'} açık sanal pozisyonları</h4>
        <p className="text-xs text-muted-text">{data.positions.length} pozisyon · Salt okunur</p>
      </div>
      <PositionRows positions={data.positions} />
    </div>
    {!spot ? <div className="grid gap-3 sm:grid-cols-2">
      <Card label="Kullanılan izole marjin" value={amount(data.used_initial_margin, 2) + ' USDT'}/>
      <Card label="Futures funding / işlem olayı"
        value={String(data.trades?.length ?? 0)}
        note="En son 100 Futures defter işlemi" />
    </div> : null}
  </div>;
}
function EventTable({ events }: { events: PaperEvent[] }) {
  if (!events.length) return <p className="p-5 text-sm text-muted-text">
    Bu filtrede kayıtlı sanal işlem veya funding olayı yok.
  </p>;
  return <div className="overflow-x-auto">
    <table className="w-full min-w-[730px] text-left text-xs">
      <thead className="bg-surface text-muted-text"><tr>
        <th className="px-3 py-3">Zaman</th><th className="px-3 py-3">Piyasa</th>
        <th className="px-3 py-3">Sembol</th><th className="px-3 py-3">Olay</th>
        <th className="px-3 py-3">Fiyat</th><th className="px-3 py-3">Ücret</th>
        <th className="px-3 py-3">Olay PnL</th><th className="px-3 py-3">Kaynak</th>
      </tr></thead>
      <tbody>{events.map((event, index) => <tr key={event.market + ':' + event.source + ':' + event.id + ':' + index}
        className="border-t border-border/70">
        <td className="px-3 py-3">{when(event.created_at)}</td>
        <td className="px-3 py-3">{event.market === 'spot' ? 'Spot' : 'Futures'}</td>
        <td className="px-3 py-3 font-mono">{event.symbol}</td>
        <td className="px-3 py-3 font-semibold">{event.action === 'FUNDING' ? 'Funding' :
          event.action === 'LIQUIDATION' ? 'Sanal likidasyon' :
          event.action === 'OPEN' ? 'Pozisyon açılışı' :
          event.action === 'CLOSE' ? 'Pozisyon kapanışı' :
          event.action === 'BUY' ? 'Spot AL' : event.action === 'SELL' ? 'Spot SAT' : event.action}</td>
        <td className="px-3 py-3">{amount(event.price, 6)}</td>
        <td className="px-3 py-3">{amount(event.fee, 4)}</td>
        <td className="px-3 py-3 font-semibold">{amount(event.event_pnl, 4)}</td>
        <td className="px-3 py-3 text-muted-text">{event.source === 'trade_lifecycle'
          ? 'Strateji yaşam döngüsü' : event.source === 'futures_ledger'
            ? 'Futures defteri' : 'Spot defteri'}</td>
      </tr>)}</tbody>
    </table>
  </div>;
}

export const CryptoPaperPanel: React.FC<{
  view: PaperView;
  onOpenRisk: () => void;
}> = ({ view, onOpenRisk }) => {
  const [summary, setSummary] = useState<PaperSummary | null>(null);
  const [history, setHistory] = useState<PaperHistory | null>(null);
  const [selected, setSelected] = useState<PaperMarket>('spot');
  const [filter, setFilter] = useState<'all' | PaperMarket>('all');
  const [revision, setRevision] = useState(0);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    let alive = true;
    setSummary(null);
    setHistory(null);
    setLoading(true);
    setError('');
    const request = view === 'history'
      ? cryptoPaperApi.history(filter === 'all' ? null : filter)
      : cryptoPaperApi.summary();
    void request.then(result => {
      if (!alive) return;
      if (view === 'history') setHistory(result as PaperHistory);
      else setSummary(result as PaperSummary);
    }).catch(() => {
      if (alive) setError('Trading Office sanal defteri okunamadı veya tutarlılık doğrulamasını geçmedi. Eksik kayıtlar sıfır kabul edilmez.');
    }).finally(() => {
      if (alive) setLoading(false);
    });
    return () => { alive = false; };
  }, [view, filter, revision]);

  const positions = summary ? [...summary.spot.positions, ...summary.futures.positions] : [];

  return <div className="space-y-4" data-testid="ebbot-crypto-paper">
    <header className="rounded-2xl border border-border bg-card p-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h3 className="flex items-center gap-2 text-base font-bold">
            <Wallet className="h-5 w-5 text-primary"/>
            {view === 'paper' ? 'Spot ve Futures Paper Hesapları' :
              view === 'positions' ? 'Açık Sanal Pozisyonlar' : 'Sanal İşlem ve Funding Geçmişi'}
          </h3>
          <p className="mt-2 max-w-3xl text-xs leading-5 text-muted-text">
            Kaynak: Trading Office'un mevcut SQLite sanal defterleri.
            Yeni sanal bakiye oluşturulmaz; Spot ve Futures muhasebesi ayrı kalır.
          </p>
        </div>
        <button type="button" onClick={() => setRevision(n => n + 1)}
          className="flex items-center gap-2 rounded-lg border border-border px-3 py-2 text-xs">
          <RefreshCw className="h-4 w-4"/> Kayıtları yenile
        </button>
      </div>
      <div className="mt-4 flex flex-wrap items-center gap-2 text-xs text-muted-text">
        <LockKeyhole className="h-4 w-4 text-success"/>
        Gerçek emir kapalı · Paper emir açma/kapama bu bağlantıda kapalı
      </div>
      <p className="mt-2 text-xs leading-5 text-muted-text">
        Eski Trading Office işlem API'leri EBBot risk kontrolüne atomik bağlanana kadar
        emir butonu açılmaz. Hesap özeti tarihsel kayıtları gösterir; canlı broker bakiyesi değildir.
      </p>
      <button type="button" onClick={onOpenRisk}
        className="mt-3 rounded-lg border border-primary px-3 py-2 text-xs font-semibold text-primary">
        <ShieldCheck className="mr-1 inline h-4 w-4"/> Risk Yönetimini aç
      </button>
    </header>

    {loading ? <div role="status" className="rounded-xl bg-surface p-4 text-xs text-muted-text">
      Sanal hesap kayıtları doğrulanıyor…
    </div> : null}
    {error ? <div role="alert" className="rounded-xl border border-border bg-card p-4 text-xs text-danger">
      <CircleAlert className="mr-1 inline h-4 w-4"/>{error}
    </div> : null}

    {summary ? <>
      {view === 'paper' ? <>
        <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
          <Card label="Birleşik sanal özsermaye" value={summary.valuation_complete
            ? amount(summary.combined_equity, 2) + ' USDT' : 'Değerlenemiyor'} />
          <Card label="Bugünkü gerçekleşmiş PnL"
            value={amount(summary.performance.daily.realized_net_pnl, 4) + ' USDT'}
            note="Trading Office olay raporu; ayrı kaynak çift sayımları içeriyor olabilir"/>
          <Card label="Haftalık gerçekleşmiş PnL"
            value={amount(summary.performance.weekly.realized_net_pnl, 4) + ' USDT'}/>
          <Card label="Aylık gerçekleşmiş PnL"
            value={amount(summary.performance.monthly.realized_net_pnl, 4) + ' USDT'}/>
        </div>
        <div className="flex gap-2">
          {(['spot', 'futures'] as const).map(market => <button type="button" key={market}
            aria-pressed={selected === market} onClick={() => setSelected(market)}
            className={'rounded-lg border px-4 py-2 text-xs font-semibold ' +
              (selected === market ? 'border-primary bg-primary/10 text-primary' : 'border-border')}>
            {market === 'spot' ? 'Spot Sanal Hesabı' : 'Futures Sanal Hesabı'}
          </button>)}
        </div>
        <PaperAccountView data={summary[selected]}/>
      </> : <>
        <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
          <Card label="Spot açık pozisyon" value={String(summary.spot.positions.length)}/>
          <Card label="Futures açık pozisyon" value={String(summary.futures.positions.length)}/>
          <Card label="Toplam açık sanal pozisyon" value={String(positions.length)}/>
        </div>
        <section className="rounded-2xl border border-border bg-card">
          <h4 className="border-b border-border p-4 text-sm font-bold">
            Spot + Futures · Ayrı muhasebe kaynakları
          </h4>
          <PositionRows positions={positions}/>
        </section>
      </>}
      <div className="flex items-center gap-2 text-xs text-muted-text">
        <Activity className="h-4 w-4"/> İstek tamamlanma zamanı: {when(summary.checked_at)}.
        Bu zaman tek tek piyasa fiyatlarının kaynak güncelliğini garanti etmez.
      </div>
    </> : null}

    {view === 'history' ? <>
      <div className="flex flex-wrap items-center gap-2 rounded-xl border border-border bg-card p-3 text-xs">
        <BookOpen className="h-4 w-4 text-primary"/><strong>Geçmiş filtresi</strong>
        {(['all', 'spot', 'futures'] as const).map(value => <button type="button"
          key={value} aria-pressed={filter === value} onClick={() => setFilter(value)}
          className={'rounded-lg border px-3 py-2 ' +
            (value === filter ? 'border-primary bg-primary/10 font-semibold text-primary' : 'border-border')}>
          {value === 'all' ? 'Tümü' : value === 'spot' ? 'Spot' : 'Futures'}
        </button>)}
      </div>
      {history ? <section className="rounded-2xl border border-border bg-card">
        <div className="flex flex-wrap items-center justify-between gap-2 border-b border-border p-4">
          <h4 className="flex items-center gap-2 text-sm font-bold">
            <History className="h-4 w-4"/> İşlem / Funding olayları ({history.count})
          </h4>
          <span className="text-xs text-muted-text">Son 100 kaynak olayından seçilen filtre</span>
        </div>
        <EventTable events={history.events}/>
      </section> : null}
      <p className="text-xs leading-5 text-muted-text">
        Strateji yaşam döngüsü kayıtları ile Spot/Futures defter kayıtları ayrı kaynaklardır.
        Bu tabloyu toplayarak çift sayım içermeyen toplam PnL çıkarılmamalıdır.
      </p>
    </> : null}
  </div>;
};
