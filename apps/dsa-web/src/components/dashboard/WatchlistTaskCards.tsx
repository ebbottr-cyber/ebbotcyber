import { Activity, AlertCircle, CheckCircle2, Clock3, LoaderCircle, Search } from 'lucide-react';
import type { HistoryItem, TaskInfo } from '../../types/analysis';

const price = (value: number | null | undefined): string | null =>
  typeof value === 'number' && Number.isFinite(value) && value > 0
    ? new Intl.NumberFormat('tr-TR', { maximumFractionDigits: 2 }).format(value)
    : null;

export type WatchlistOverviewProps = {
  codes: string[];
  history: HistoryItem[];
  loading: boolean;
  currentCode: string;
  onSelect: (code: string) => void;
  onManage: () => void;
};

export function WatchlistOverviewContent({ codes, history, loading, currentCode, onSelect, onManage }: WatchlistOverviewProps) {
  return (
    <div data-testid="watchlist-overview-content" className="min-w-0">
      {codes.length > 0 ? (
        <div className="divide-y divide-[#eaf0f8]">
          {codes.slice(0, 7).map((code) => {
            const report = history.find((item) => item.stockCode === code);
            const last = price(report?.currentPrice);
            const chosen = currentCode === code;
            return (
              <button key={code} type="button" onClick={() => onSelect(code)}
                aria-pressed={chosen} aria-label={code + ' grafiğini göster'}
                className={'flex min-h-12 w-full min-w-0 items-center justify-between gap-2 rounded-lg px-2 py-2 text-left transition-colors hover:bg-[#f1f7ff] ' +
                  (chosen ? 'bg-[#eaf4ff]' : '')}>
                <div className="min-w-0">
                  <p className="truncate text-xs font-bold text-[#234a7e]">{code}</p>
                  <p className="text-[10px] text-[#94a6bd]">{report?.stockName || 'Takip edilen sembol'}</p>
                </div>
                <div className="shrink-0 text-right">
                  <span className="block text-xs font-bold tabular-nums text-[#234a7e]">{last ?? '—'}</span>
                  <span className="text-[10px] text-[#899bb1]">{last ? 'Son analiz fiyatı' : 'Analiz fiyatı yok'}</span>
                </div>
              </button>
            );
          })}
        </div>
      ) : (
        <p role="status" className="rounded-xl bg-[#f5f9ff] p-3 text-xs text-[#748aa5]">
          {loading ? 'Takip listesi yükleniyor…' : 'Takip listesine henüz hisse eklenmedi.'}
        </p>
      )}
      <button type="button" onClick={onManage}
        className="mt-3 flex min-h-10 w-full items-center justify-center gap-1 rounded-xl border border-[#d6e5f6] bg-[#f5f9ff] text-xs font-semibold text-[#2575ca] hover:bg-[#e8f3ff]">
        <Search className="h-3.5 w-3.5" /> Hisseleri yönet
      </button>
      <p className="mt-2 text-[10px] text-[#99a8b9]">Listelenen fiyatlar canlı kotasyon değildir.</p>
    </div>
  );
}

export type TaskFeedProps = {
  tasks: TaskInfo[];
  loading: boolean;
  failed: boolean;
  onOpen: () => void;
};

export function taskStatus(status: TaskInfo['status']): { label: string; style: string } {
  switch (status) {
    case 'processing': return { label: 'Çalışıyor', style: 'bg-[#e7f2ff] text-[#246fc2]' };
    case 'pending': return { label: 'Sırada', style: 'bg-[#f3f5fa] text-[#677b98]' };
    case 'completed': return { label: 'Tamamlandı', style: 'bg-[#e5f7ef] text-[#178459]' };
    case 'failed': return { label: 'Hata', style: 'bg-[#fff0ef] text-[#bd4d4b]' };
    case 'cancel_requested': return { label: 'İptal istenmiş', style: 'bg-[#fff6e7] text-[#946622]' };
    case 'cancelled': return { label: 'İptal edildi', style: 'bg-[#f3f5fa] text-[#677b98]' };
    default: return { label: 'Bilinmiyor', style: 'bg-[#f3f5fa] text-[#677b98]' };
  }
}

export function TaskFeedContent({ tasks, loading, failed, onOpen }: TaskFeedProps) {
  if (loading || failed) {
    return <p role="status" className="rounded-xl bg-[#f5f9ff] p-3 text-xs text-[#758ba7]">
      {loading ? 'AI analiz görevleri yükleniyor…' : 'Görev listesine erişilemedi.'}
    </p>;
  }
  return (
    <div data-testid="ai-task-feed" className="min-w-0">
      {tasks.length ? (
        <div className="space-y-2">
          {tasks.slice(0, 4).map((task) => {
            const progress = typeof task.progress === 'number' && Number.isFinite(task.progress)
              ? Math.min(100, Math.max(0, task.progress)) : null;
            const status = taskStatus(task.status);
            return (
              <div key={task.taskId} className="rounded-xl border border-[#e3ecf7] bg-[#fbfdff] p-3">
                <div className="flex min-w-0 items-start justify-between gap-2">
                  <div className="flex min-w-0 items-center gap-2">
                    {task.status === 'processing' ? <LoaderCircle className="h-4 w-4 shrink-0 text-[#287bd5]" />
                      : task.status === 'failed' ? <AlertCircle className="h-4 w-4 shrink-0 text-[#d65c5c]" />
                      : task.status === 'completed' ? <CheckCircle2 className="h-4 w-4 shrink-0 text-[#25a779]" />
                      : <Clock3 className="h-4 w-4 shrink-0 text-[#7896b6]" />}
                    <span className="truncate text-xs font-bold text-[#2b4c74]">{task.stockCode || 'Genel analiz'}</span>
                  </div>
                  <span className={'shrink-0 rounded-full px-2 py-1 text-[10px] font-bold ' + status.style}>{status.label}</span>
                </div>
                {task.status === 'processing' && progress !== null && (
                  <div className="mt-2">
                    <div role="progressbar" aria-label={task.stockCode + ' analiz ilerlemesi'} aria-valuemin={0} aria-valuemax={100} aria-valuenow={progress}
                      className="h-1.5 overflow-hidden rounded-full bg-[#e2edf9]">
                      <div className="h-full rounded-full bg-[#2d83d9]" style={{ width: progress + '%' }} />
                    </div>
                    <p className="mt-1 text-[10px] text-[#8198b4]">{progress}% tamamlandı</p>
                  </div>
                )}
                {task.status === 'failed' && task.error && <p className="mt-2 line-clamp-2 text-[11px] text-[#aa6565]">Analiz hatası: {task.error}</p>}
              </div>
            );
          })}
        </div>
      ) : (
        <p className="rounded-xl bg-[#f5f9ff] p-3 text-xs text-[#7187a4]">Henüz görüntülenecek analiz görevi yok.</p>
      )}
      <button type="button" onClick={onOpen}
        className="mt-3 flex min-h-9 w-full items-center justify-center rounded-lg border border-[#dce8f7] text-xs font-semibold text-[#2874c8] hover:bg-[#f2f8ff]">
        <Activity className="mr-1.5 h-3.5 w-3.5" /> Analiz ekranını aç
      </button>
    </div>
  );
}
