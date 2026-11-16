import type React from 'react';
import type { ParsedApiError } from '../../api/error';
import { useUiLanguage } from '../../contexts/UiLanguageContext';

interface ApiErrorAlertProps {
  error: ParsedApiError;
  className?: string;
  actionLabel?: string;
  onAction?: () => void;
  dismissLabel?: string;
  onDismiss?: () => void;
}


const TURKISH_ERROR_TEXT: Record<string, string> = {
  '请求失败': 'İstek başarısız',
  '配置需要调整': 'Yapılandırma düzeltilmeli',
  '请检查渠道的 API Key、模型和运行参数后重试。': 'API anahtarını, modeli ve çalışma ayarlarını kontrol edip tekrar deneyin.',
  '问股后端已移除': 'Hisse asistanı altyapısı kaldırıldı',
  '会话已更新': 'Oturum güncellendi',
  '请刷新会话后重试。当前输入尚未被接受，请保留问题与选择。': 'Oturumu yenileyip tekrar deneyin. Mevcut girişiniz kabul edilmedi; metni ve seçimlerinizi koruyun.',
  'Agent 模式未开启': 'Agent modu etkin değil',
  '当前功能依赖 Agent 模式，请先开启后再重试。': 'Bu özellik Agent modunu gerektiriyor. Modu etkinleştirip tekrar deneyin.',
  '请求缺少必要参数': 'Gerekli bilgiler eksik',
  '请先补充股票代码或必要输入后再试。': 'Hisse kodunu ve gerekli bilgileri girip tekrar deneyin.',
  '卖出数量超过可用持仓': 'Satış miktarı mevcut pozisyonu aşıyor',
  '卖出数量超过当前可用持仓，请删除或修正对应卖出流水后重试。': 'Satış miktarı mevcut pozisyonu aşıyor. İlgili işlemi düzeltin.',
  '持仓账本正忙': 'Portföy kayıtları meşgul',
  '持仓账本正在处理另一笔变更，请稍后重试。': 'Portföyde başka bir işlem sürüyor. Biraz sonra tekrar deneyin.',
  '选股功能未就绪': 'Hisse tarama hazır değil',
  '选股功能暂不可用，请检查策略配置、数据依赖和服务日志。': 'Hisse tarama kullanılamıyor. Strateji ayarlarını, veri bağlantılarını ve sunucu günlüklerini kontrol edin.',
  '选股任务不可恢复': 'Hisse tarama görevi bulunamadı',
  '服务端没有找到这次选股任务，可能后端已重启或任务记录已清理，请重新运行选股。': 'Görev bulunamadı. Sunucu yeniden başlamış olabilir; taramayı yeniden çalıştırın.',
  '选股失败': 'Hisse taraması başarısız',
  '选股访问行情、快照或模型服务失败，请稍后重试，或检查网络与代理设置。': 'Piyasa verisi veya model servisine erişilemedi. Bağlantıyı kontrol edip tekrar deneyin.',
  '系统没有配置可用的 LLM 模型': 'Kullanılabilir yapay zekâ modeli ayarlanmamış',
  '请先在系统设置中配置主模型、可用渠道或相关 API Key 后再重试。': 'Önce Ayarlar bölümünden ana model, sağlayıcı veya API anahtarını yapılandırın.',
  '当前模型不兼容工具调用': 'Model araç çağrılarını desteklemiyor',
  '当前模型不适合 Agent / 工具调用场景，请更换支持工具调用的模型后重试。': 'Agent araçlarını destekleyen başka bir model seçin.',
  '上游模型返回的数据结构不完整': 'Model yanıtı eksik veya geçersiz',
  '上游模型返回的工具调用结构不符合要求，请更换模型或关闭相关推理模式后重试。': 'Modelin araç çağrısı yanıtı geçersiz. Modeli veya akıl yürütme ayarlarını kontrol edin.',
  '连接上游服务超时': 'Dış servise bağlantı zaman aşımına uğradı',
  '服务端访问外部依赖时超时，请稍后重试，或检查当前网络与代理设置。': 'Dış servise erişim zaman aşımına uğradı. İnternet ve proxy ayarlarını kontrol edin.',
  '服务端无法访问外部依赖': 'Sunucu dış servise erişemiyor',
  '页面已连接到本地服务，但本地服务访问外部模型或数据接口失败，请检查代理、DNS 或出网配置。': 'Yerel sunucu çalışıyor ancak dış veri veya model servisine bağlanamıyor. DNS ve proxy ayarlarını kontrol edin.',
  '上游模型接口拒绝了当前请求': 'Model servisi isteği reddetti',
  '本地服务正常，但上游模型接口拒绝了请求，请检查模型名称、参数格式或工具调用兼容性。': 'Model adını, parametreleri ve araç çağrısı uyumluluğunu kontrol edin.',
  '无法连接到本地服务': 'Yerel sunucuya bağlanılamıyor',
  '浏览器当前无法连接到本地 Web 服务，请检查服务是否启动、监听地址是否正确、端口是否开放。': 'Yerel sunucunun çalıştığını ve doğru portu kullandığınızı kontrol edin.',
  '请求未成功完成，请稍后重试。': 'İstek tamamlanamadı. Biraz sonra tekrar deneyin.',
};

function errorDisplayText(value: string, language: string): string {
  if (language !== 'tr') return value;
  const translated = TURKISH_ERROR_TEXT[value];
  if (translated) return translated;
  const httpFailure = /^请求未成功完成（HTTP (\d+)）。$/.exec(value);
  if (httpFailure) return `İstek tamamlanamadı (HTTP ${httpFailure[1]}).`;
  if (value.startsWith('请修正以下配置后重试：')) {
    return 'Yapılandırma hatası. Ayrıntılar bölümündeki teknik açıklamayı kontrol edin.';
  }
  // Preserve the original server payload in the expandable technical details.
  if (/[\u3400-\u9fff]/.test(value)) {
    return 'İşlem tamamlanamadı. Ayrıntılar bölümünde teknik hata mesajı bulunuyor.';
  }
  return value;
}

export const ApiErrorAlert: React.FC<ApiErrorAlertProps> = ({
  error,
  className = '',
  actionLabel,
  onAction,
  dismissLabel,
  onDismiss,
}) => {
  const { t, language } = useUiLanguage();
  const title = errorDisplayText(error.title, language);
  const message = errorDisplayText(error.message, language);
  const showDetails = Boolean(error.rawMessage.trim() && error.rawMessage.trim() !== message.trim());

  return (
    <div
      className={`rounded-xl border border-[hsl(var(--color-danger-alert-border)/0.3)] bg-[hsl(var(--color-danger-alert-bg)/0.1)] px-4 py-3 text-[hsl(var(--color-danger-alert-text))] ${className}`}
      role="alert"
    >
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="text-sm font-semibold">{title}</p>
          <p className="mt-1 whitespace-pre-line break-words text-xs opacity-90">{message}</p>
        </div>
        {onDismiss ? (
          <button
            type="button"
            className="shrink-0 rounded-md border border-[hsl(var(--color-danger-alert-border)/0.3)] bg-[hsl(var(--color-danger-alert-bg)/0.1)] px-2 py-1 text-[11px] text-[hsl(var(--color-danger-alert-text))] transition hover:bg-[hsl(var(--color-danger-alert-bg)/0.15)]"
            onClick={onDismiss}
          >
            {dismissLabel ?? t('common.close')}
          </button>
        ) : null}
      </div>
      {showDetails ? (
        <details className="mt-3 rounded-lg border border-subtle bg-surface-2 px-3 py-2">
          <summary className="cursor-pointer text-xs text-[hsl(var(--color-danger-alert-text))] opacity-90">{t('common.details')}</summary>
          <pre className="mt-2 whitespace-pre-wrap break-words text-[11px] leading-5 text-[hsl(var(--color-danger-alert-text))] opacity-85">
            {error.rawMessage}
          </pre>
        </details>
      ) : null}
      {actionLabel && onAction ? (
        <button
          type="button"
          className="mt-3 inline-flex items-center justify-center rounded-md border border-[hsl(var(--color-danger-alert-border)/0.3)] bg-[hsl(var(--color-danger-alert-bg)/0.1)] px-3 py-1.5 text-xs font-medium text-[hsl(var(--color-danger-alert-text))] transition hover:bg-[hsl(var(--color-danger-alert-bg)/0.15)]"
          onClick={onAction}
        >
          {actionLabel}
        </button>
      ) : null}
    </div>
  );
};
