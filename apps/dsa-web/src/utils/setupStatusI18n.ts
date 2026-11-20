import type { UiLanguage } from '../i18n/uiText';
import type { SetupStatusCheck } from '../types/systemConfig';

/** Translate setup API display text without changing check status, key or requirements. */
export function localizeSetupCheck(check: SetupStatusCheck, language: UiLanguage): SetupStatusCheck {
  if (language === 'zh') return check;
  const text = (tr: string, en: string) => language === 'tr' ? tr : en;
  const names: Record<string, [string, string]> = {
    llm_primary: ['Ana Yapay Zekâ Modeli', 'Primary AI Model'],
    llm_agent: ['Agent Modeli', 'Agent Model'],
    stock_list: ['Takip Listesi', 'Watchlist'],
    notification: ['Bildirim Kanalı', 'Notification Channel'],
    storage: ['Veritabanı / Yerel Depolama', 'Database / Local Storage'],
  };
  const titlePair = names[check.key];
  if (!titlePair) return check;
  const title = language === 'tr' ? titlePair[0] : titlePair[1];
  const raw = check.message || '';
  let message = raw;
  let nextStep = check.nextStep || null;

  if (check.key === 'llm_primary') {
    const localBackend = raw.match(/^已启用 (.+) 本地生成 Backend/);
    const detected = raw.match(/^已检测到 (.+?): (.+)$/);
    if (localBackend) message = text(
      localBackend[1] + ' yerel model sistemi etkin (deneysel/sınırlı).',
      localBackend[1] + ' local model backend is enabled (experimental/limited).',
    );
    else if (detected) message = text(
      detected[1] + ' algılandı: ' + detected[2],
      'Detected ' + detected[1] + ': ' + detected[2],
    );
    else if (raw.includes('codex') && check.status === 'needs_action') message = text(
      'Codex CLI seçilmiş ancak sunucu codex çalıştırılabilir dosyasını PATH içinde bulamıyor.',
      'Codex CLI is selected, but the server cannot find the codex executable on PATH.',
    );
    else if (raw.includes('可执行文件') && check.status === 'needs_action') message = text(
      'Seçilen yerel model aracı sunucuda bulunamadı.',
      'The selected local model executable was not found on the server.',
    );
    else if (raw === '尚未检测到主模型配置') message = text(
      'Henüz ana model yapılandırması bulunamadı.',
      'No primary model configuration was detected.',
    );

    if (check.nextStep) nextStep = raw.includes('codex')
      ? text(
          'Codex CLI kurulumunu ve sunucu PATH ayarını denetleyin. Alternatif: GENERATION_BACKEND=litellm.',
          'Verify the Codex CLI installation and server PATH. Alternatively set GENERATION_BACKEND=litellm.',
        )
      : raw.includes('可执行文件')
        ? text(
            'İlgili CLI aracını kurup giriş yapın veya GENERATION_BACKEND=litellm seçin.',
            'Install and sign in to the CLI tool or set GENERATION_BACKEND=litellm.',
          )
        : text(
            'LITELLM_MODEL, LLM_CHANNELS, LITELLM_CONFIG veya sağlayıcı API anahtarı yapılandırın.',
            'Configure LITELLM_MODEL, LLM_CHANNELS, LITELLM_CONFIG or a provider API key.',
          );
  }

  if (check.key === 'llm_agent') {
    const explicitModel = raw.match(/^已配置 Agent 主模型: (.+)$/);
    const inheritedModel = raw.match(/LiteLLM 主模型: (.+)$/);
    if (check.status === 'inherited') message = text(
      'Agent için ayrı model seçilmedi; ana yapay zekâ modeli kullanılacak.',
      'No separate Agent model was selected; the primary AI model will be used.',
    );
    else if (inheritedModel) message = text(
      'Standart analiz Codex CLI kullanıyor; Agent araçları LiteLLM modelini kullanıyor: ' + inheritedModel[1],
      'Standard analysis uses Codex CLI; Agent tools use LiteLLM model: ' + inheritedModel[1],
    );
    else if (explicitModel) message = text(
      'Agent ana modeli yapılandırıldı: ' + explicitModel[1],
      'Agent primary model configured: ' + explicitModel[1],
    );
    else if (raw.includes('Hermes')) message = text(
      'Seçili Hermes modeli Agent araç çağrılarını desteklemiyor.',
      'The selected Hermes model does not support Agent tool calls.',
    );
    else if (raw.includes('text-only')) message = text(
      'Yalnızca metin üreten bu model sistemi Agent araç çağrılarını desteklemiyor.',
      'This text-only model backend does not support Agent tool calls.',
    );
    else if (raw.includes('缺少可用渠道') || raw.includes('未检测到可用 LiteLLM')) message = text(
      'Agent modelinin kullanılabilir kanalı veya gerekli API anahtarı bulunamadı.',
      'No usable channel or required API key was found for the Agent model.',
    );
    else if (raw.includes('LLM 主渠道尚不可用')) message = text(
      'Agent için ayrı model ayarlanmamış ve ana yapay zekâ modeli henüz kullanılabilir değil.',
      'The Agent has no separate model, and the primary AI model is not yet available.',
    );
    else if (raw.includes('需要 LiteLLM 模型')) message = text(
      'Agent araç çağrıları LiteLLM modeli gerektirir; yerel CLI modeli otomatik devralınmaz.',
      'Agent tool calls need a LiteLLM model; the local CLI model is not automatically inherited.',
    );
    if (check.nextStep) nextStep = raw.includes('Hermes')
      ? text(
          'Agent için Hermes olmayan bir model veya karma yönlendirme seçin.',
          'Choose a non-Hermes Agent model or a mixed route.',
        )
      : raw.includes('text-only')
        ? text(
            'AGENT_GENERATION_BACKEND değerini auto veya litellm yapıp LiteLLM kanalı ekleyin.',
            'Set AGENT_GENERATION_BACKEND to auto or litellm and configure a LiteLLM channel.',
          )
        : text(
            'Ana model ve Agent ayarlarını tamamlayın: AGENT_LITELLM_MODEL, LITELLM_MODEL, LLM_CHANNELS veya LITELLM_CONFIG.',
            'Complete the primary and Agent settings: AGENT_LITELLM_MODEL, LITELLM_MODEL, LLM_CHANNELS or LITELLM_CONFIG.',
          );
  }

  if (check.key === 'stock_list') {
    const count = raw.match(/^已配置 (\d+) 只股票/);
    message = count
      ? text('Takip listesinde ' + count[1] + ' hisse bulunuyor.', count[1] + ' stocks are configured in the watchlist.')
      : check.status === 'needs_action' ? text('STOCK_LIST şu anda boş.', 'STOCK_LIST is currently empty.') : raw;
    if (check.nextStep) nextStep = text(
      'İlk deneme için takip listesine en az 1 hisse ekleyin.',
      'Add at least one watchlist stock for the first smoke test.',
    );
  }

  if (check.key === 'notification') {
    message = check.status === 'configured'
      ? text('En az bir bildirim kanalı yapılandırılmış.', 'At least one notification channel is configured.')
      : text(
          'Bildirimler isteğe bağlıdır; ayarlanmamış olmaları ilk analizi engellemez.',
          'Notifications are optional; leaving them unconfigured does not block the first analysis.',
        );
    if (check.nextStep) nextStep = text(
      'Gerekirse daha sonra Telegram, e-posta veya başka bir bildirim kanalı ekleyebilirsiniz.',
      'Add Telegram, email or another notification channel later if needed.',
    );
  }

  if (check.key === 'storage') {
    const available = raw.match(/^数据库路径可用: (.+)$/);
    const creatable = raw.match(/^数据库上级目录可创建: (.+)$/);
    const invalid = raw.match(/^数据库路径父目录不可用: (.+)$/);
    const unwritable = raw.match(/^数据库路径上级目录不可写: (.+)$/);
    if (available) message = text('Veritabanı yolu kullanılabilir: ', 'Database path is available: ') + available[1];
    else if (creatable) message = text('Veritabanı üst klasörü oluşturulabilir: ', 'Database parent folder can be created: ') + creatable[1];
    else if (invalid) message = text('Veritabanının üst klasörü kullanılamıyor: ', 'Database parent folder is unavailable: ') + invalid[1];
    else if (unwritable) message = text('Veritabanı klasörüne yazılamıyor: ', 'Database folder is not writable: ') + unwritable[1];
    if (check.nextStep) nextStep = text(
      'DATABASE_PATH ayarını ve klasör izinlerini denetleyin.',
      'Check DATABASE_PATH and directory permissions.',
    );
  }
  // Keep original backend text for unknown cases: a false translation could hide a real setup problem.
  return { ...check, title, message, nextStep };
}
