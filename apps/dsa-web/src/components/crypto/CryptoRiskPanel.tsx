import type React from 'react';
import { useEffect, useState } from 'react';
import { AlertTriangle, Calculator, CircleCheck, History, LockKeyhole, RefreshCw, ShieldAlert } from 'lucide-react';
import {
  cryptoRiskApi,
  type CryptoRiskHistory, type CryptoRiskLimits, type CryptoRiskMarket,
  type CryptoRiskReview, type CryptoRiskSide,
} from '../../api/cryptoRisk';

function display(value: number | null | undefined, digits = 4) {
  return typeof value === 'number' && Number.isFinite(value)
    ? new Intl.NumberFormat('tr-TR', { maximumFractionDigits: digits }).format(value)
    : '—';
}

function Stat({ name, value }: { name: string; value: string }) {
  return <div className="rounded-xl border border-border bg-card p-4">
    <p className="text-xs text-muted-text">{name}</p>
    <p className="mt-2 break-words text-lg font-bold tabular-nums text-foreground">{value}</p>
  </div>;
}

export const CryptoRiskPanel: React.FC = () => {
  const [market, setMarket] = useState<CryptoRiskMarket>('spot');
  const [symbol, setSymbol] = useState('BTC/USDT');
  const [side, setSide] = useState<CryptoRiskSide>('BUY');
  const [entry, setEntry] = useState('');
  const [stop, setStop] = useState('');
  const [target, setTarget] = useState('');
  const [riskPercent, setRiskPercent] = useState(0.5);
  const [leverage, setLeverage] = useState(1);
  const [limits, setLimits] = useState<CryptoRiskLimits | null>(null);
  const [history, setHistory] = useState<CryptoRiskHistory | null>(null);
  const [result, setResult] = useState<CryptoRiskReview | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [refresh, setRefresh] = useState(0);

  useEffect(() => {
    let alive = true;
    setHistory(null);
    setLimits(null);
    void Promise.allSettled([cryptoRiskApi.limits(), cryptoRiskApi.history()])
      .then(out => {
        if (!alive) return;
        setLimits(out[0].status === 'fulfilled' ? out[0].value : null);
        setHistory(out[1].status === 'fulfilled' ? out[1].value : null);
      });
    return () => { alive = false; };
  }, [refresh]);

  const invalidate = () => {
    setResult(null);
    setError('');
  };
  const changeMarket = (next: CryptoRiskMarket) => {
    setMarket(next);
    setSide('BUY');
    setLeverage(1);
    setEntry('');
    setStop('');
    setTarget('');
    invalidate();
  };

  const review = async (event: React.FormEvent) => {
    event.preventDefault();
    if (busy) return;
    setResult(null);
    setError('');
    setBusy(true);
    try {
      const response = await cryptoRiskApi.review({
        market, symbol: symbol.trim().toUpperCase(), side,
        entry_price: Number(entry), stop_price: Number(stop),
        take_profit_price: Number(target), risk_percent: riskPercent,
        leverage,
      });
      setResult(response);
      setRefresh(n => n + 1);
    } catch {
      setError('Risk değerlendirmesi engellendi. Piyasa verisi, Spot/Futures sanal hesapları, günlük zarar ve kayıt güvenilirliği doğrulanmalıdır.');
    } finally {
      setBusy(false);
    }
  };

  return <div className="space-y-4" data-testid="ebbot-crypto-risk">
    <section className="rounded-2xl border border-border bg-card p-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h3 className="flex items-center gap-2 font-bold">
            <ShieldAlert className="h-5 w-5 text-primary"/> Bağımsız Kripto Risk Motoru
          </h3>
          <p className="mt-2 text-xs leading-6 text-muted-text">
            Spot ve USD-M Futures için güvenilir Binance fiyatları, canlı emir defteri ve Trading Office
            sanal muhasebesi ile risk ön kontrolü. Bakiye ve günlük zarar kullanıcıdan alınmaz.
          </p>
        </div>
        <button type="button" onClick={() => setRefresh(n => n + 1)}
          className="inline-flex items-center gap-2 rounded-xl border border-border px-3 py-2 text-xs">
          <RefreshCw className="h-4 w-4"/> Risk kayıtlarını yenile
        </button>
      </div>
      <div className="mt-3 flex flex-wrap gap-2">
        <span className="rounded-lg bg-primary/10 px-2.5 py-2 text-xs font-semibold text-primary">
          <LockKeyhole className="mr-1 inline h-4 w-4"/> Gerçek emir ve Paper işlem yürütme kapalı
        </span>
        <span className="rounded-lg bg-surface px-2.5 py-2 text-xs text-secondary-text">
          Risk onayı yok · Sadece senaryo değerlendirmesi
        </span>
      </div>
    </section>

    <div className="grid gap-4 lg:grid-cols-[minmax(0,1.3fr)_minmax(260px,1fr)]">
      <form onSubmit={e => void review(e)} className="space-y-4 rounded-2xl border border-border bg-card p-4">
        <div className="flex items-center gap-2 font-bold"><Calculator className="h-4 w-4"/> Manuel risk senaryosu</div>
        <div className="grid gap-3 sm:grid-cols-2">
          <div>
            <label htmlFor="risk-market" className="text-xs font-semibold">Piyasa</label>
            <select id="risk-market" value={market} onChange={e => changeMarket(e.target.value as CryptoRiskMarket)}
              className="mt-1 w-full rounded-lg border border-border bg-background p-2.5 text-sm">
              <option value="spot">Binance Spot</option>
              <option value="futures">Binance USD-M Futures</option>
            </select>
          </div>
          <div>
            <label htmlFor="risk-symbol" className="text-xs font-semibold">İşlem çifti</label>
            <input id="risk-symbol" maxLength={26} value={symbol} onChange={e => { setSymbol(e.target.value); invalidate(); }}
              className="mt-1 w-full rounded-lg border border-border bg-background p-2.5 font-mono text-sm"/>
          </div>
          <div>
            <label htmlFor="risk-side" className="text-xs font-semibold">Yön</label>
            <select id="risk-side" value={side} onChange={e => { setSide(e.target.value as CryptoRiskSide); invalidate(); }}
              className="mt-1 w-full rounded-lg border border-border bg-background p-2.5 text-sm">
              <option value="BUY">{market === 'spot' ? 'Spot AL' : 'LONG'}</option>
              {market === 'futures' ? <option value="SELL">SHORT</option> : null}
            </select>
          </div>
          <div>
            <label htmlFor="risk-leverage" className="text-xs font-semibold">Kaldıraç</label>
            <select id="risk-leverage" value={leverage} disabled={market === 'spot'}
              onChange={e => { setLeverage(Number(e.target.value)); invalidate(); }}
              className="mt-1 w-full rounded-lg border border-border bg-background p-2.5 text-sm">
              {(market === 'spot' ? [1] : [1,2,3,4,5]).map(v => <option key={v} value={v}>{v}x</option>)}
            </select>
          </div>
          {([
            ['risk-entry', 'Giriş referansı (USDT)', entry, setEntry],
            ['risk-stop', 'Stop Loss (USDT)', stop, setStop],
            ['risk-target', 'Take Profit (USDT)', target, setTarget],
          ] as const).map(([id, label, value, setter]) => <div key={id}>
            <label htmlFor={id} className="text-xs font-semibold">{label}</label>
            <input id={id} type="number" min="0.000001" step="any" value={value} required
              onChange={e => { setter(e.target.value); invalidate(); }}
              placeholder="Piyasa fiyatını gir"
              className="mt-1 w-full rounded-lg border border-border bg-background p-2.5 text-sm"/>
          </div>)}
          <div>
            <label htmlFor="risk-percent" className="text-xs font-semibold">İşlem başı risk bütçesi</label>
            <select id="risk-percent" value={riskPercent} onChange={e => { setRiskPercent(Number(e.target.value)); invalidate(); }}
              className="mt-1 w-full rounded-lg border border-border bg-background p-2.5 text-sm">
              {[0.25,0.5,1,1.5,2].map(v => <option key={v} value={v}>%{v}</option>)}
            </select>
          </div>
        </div>
        <p className="text-xs leading-5 text-muted-text">
          Fiyatı sen girersin; sunucu Binance fiyatıyla karşılaştırır.
          Geçerli sanal özsermaye, açık pozisyonlar, günlük kayıp ve maliyetler yalnız sunucudan alınır.
        </p>
        <button type="submit" disabled={busy || !entry || !stop || !target}
          className="flex w-full items-center justify-center gap-2 rounded-xl bg-primary px-4 py-3 text-sm font-bold text-primary-foreground disabled:opacity-40">
          <ShieldAlert className="h-4 w-4"/> {busy ? 'Risk kontrol ediliyor…' : 'Risk ön kontrolünü çalıştır'}
        </button>
        {error ? <div role="alert" className="rounded-lg bg-surface p-3 text-xs text-danger">{error}</div> : null}
      </form>

      <div className="space-y-4">
        <section className="rounded-2xl border border-border bg-card p-4">
          <h4 className="font-bold">Zorunlu güvenlik sınırları</h4>
          {limits ? <div className="mt-3 space-y-2 text-xs text-secondary-text">
            <p>İşlem başına risk üst sınırı: <strong>%{display(limits.limits.max_risk_per_trade_pct, 2)}</strong></p>
            <p>Toplam risk üst sınırı: <strong>%{display(limits.limits.max_aggregate_risk_pct, 2)}</strong></p>
            <p>Futures kaldıraç: <strong>{display(limits.limits.max_leverage, 0)}x</strong></p>
            <p>Futures toplam notional: <strong>%{display(limits.limits.max_gross_futures_pct, 0)}</strong></p>
            <p>Aynı yön: <strong>%{display(limits.limits.max_directional_futures_pct, 0)}</strong></p>
            <p>Günlük zarar tavanı: <strong>{display(limits.limits.daily_loss_ceiling_usdt, 0)} USDT</strong></p>
          </div> : <p className="mt-3 text-xs text-muted-text">Risk limitleri sunucudan doğrulanamadı.</p>}
        </section>
        <section className="rounded-2xl border border-border bg-card p-4">
          <h4 className="font-bold">Kontrol kapsamı</h4>
          <p className="mt-2 text-xs leading-6 text-muted-text">
            Stop yönü ve uzaklığı, beklenen getiri/risk, ücret, kayma, Futures funding,
            tahmini likidasyon tamponu, mevcut sermaye, pozisyon yoğunluğu,
            günlük zarar, piyasa likiditesi ve kaydedilmiş risk geçmişi.
          </p>
          <p className="mt-3 text-xs text-muted-text">
            Stop gerçekleşmesi, gerçek borsa likidasyon formülü ve fill kalitesi garanti edilmez.
            Bir kontrolün geçmesi gerçek veya sanal işlem yetkisi vermez.
          </p>
        </section>
      </div>
    </div>

    {result ? <section className="space-y-4 rounded-2xl border border-border bg-card p-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h4 className="flex items-center gap-2 font-bold">
          {result.status === 'BLOCKED' ? <AlertTriangle className="h-5 w-5 text-danger"/> :
            <CircleCheck className="h-5 w-5 text-primary"/>}
          {result.status === 'BLOCKED' ? 'Risk kontrolü: ENGELLENDİ' : 'Risk ön kontrolü: incelemeye uygun'}
        </h4>
        <span className="text-xs text-muted-text">Denetim no: {result.audit_id}</span>
      </div>
      <p className="rounded-lg bg-surface p-3 text-xs font-semibold text-secondary-text">
        Risk onayı: YOK · Paper işlem izni: YOK · Gerçek emir: KAPALI
      </p>
      <div className="grid grid-cols-2 gap-3 xl:grid-cols-4">
        <Stat name="Sanal hesap özsermayesi" value={display(result.paper_account_equity, 2) + ' USDT'}/>
        <Stat name="İşlem risk bütçesi" value={display(result.risk_budget, 2) + ' USDT'}/>
        <Stat name="Araştırma pozisyon büyüklüğü" value={display(result.estimated_position_notional, 2) + ' USDT'}/>
        <Stat name="Tahmini stop zararı (maliyet dahil)" value={display(result.estimated_loss_with_costs, 2) + ' USDT'}/>
        <Stat name="Komisyon (iki yön)" value={display(result.estimated_round_trip_fee, 4) + ' USDT'}/>
        <Stat name="Kayma (iki yön)" value={display(result.estimated_round_trip_slippage, 4) + ' USDT'}/>
        <Stat name="Funding rezervi" value={display(result.estimated_one_period_funding_reserve, 4) + ' USDT'}/>
        <Stat name="Net risk/getiri" value={result.net_risk_reward == null ? 'Hesaplanamadı' : display(result.net_risk_reward, 2) + ':1'}/>
        <Stat name="Birleşik Spot+Futures tahmini risk" value={'%' + display(result.estimated_combined_risk_pct, 3)}/>
        <Stat name="Kaynak portföy risk çarpanı" value={display(result.upstream_risk_multiplier, 2) + 'x'}/>
      </div>
      <div className="text-xs leading-6 text-secondary-text">
        <strong>Karar gerekçeleri:</strong>
        <ul className="mt-2 list-disc pl-5">
          {result.reasons.map(reason => <li key={reason}>{reason}</li>)}
        </ul>
      </div>
    </section> : null}

    <section className="rounded-2xl border border-border bg-card p-4">
      <h4 className="flex items-center gap-2 font-bold"><History className="h-4 w-4"/> Kripto risk denetim geçmişi</h4>
      {history ? history.reviews.length ? <div className="mt-3 overflow-x-auto">
        <table className="w-full min-w-[540px] text-left text-xs">
          <thead className="text-muted-text"><tr><th className="px-2 py-2">No</th>
            <th className="px-2 py-2">Tarih</th><th className="px-2 py-2">Piyasa</th>
            <th className="px-2 py-2">Coin</th><th className="px-2 py-2">Durum</th></tr></thead>
          <tbody>{history.reviews.map(v => <tr key={v.id} className="border-t border-border">
            <td className="px-2 py-2">{v.id}</td>
            <td className="px-2 py-2">{new Date(v.created_at).toLocaleString('tr-TR')}</td>
            <td className="px-2 py-2">{v.market === 'spot' ? 'Spot' : 'Futures'}</td>
            <td className="px-2 py-2">{v.symbol}</td>
            <td className="px-2 py-2 font-semibold">{v.status === 'BLOCKED' ? 'Engellendi' : 'İnceleme'}</td>
          </tr>)}</tbody>
        </table>
      </div> : <p className="mt-3 text-xs text-muted-text">Henüz kaydedilmiş manuel risk değerlendirmesi yok.</p>
      : <p className="mt-3 text-xs text-muted-text">Risk geçmişi erişilebilir değil veya yükleniyor.</p>}
    </section>
  </div>;
};
