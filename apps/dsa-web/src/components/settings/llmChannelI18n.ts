import type { UiLanguage } from '../../i18n/uiText';

/** Presentation-only translations. IDs, URLs, API keys and model names are never rewritten. */
const LABELS: Record<string, { tr: string; en: string }> = {
  "AI 模型配置": {
    "tr": "Yapay Zekâ Model Yapılandırması",
    "en": "AI Model Configuration"
  },
  "渠道管理": {
    "tr": "Kanal Yönetimi",
    "en": "Channel Management"
  },
  "添加服务商渠道后可自动获取模型列表并多选，也可继续手动填写。配置会自动同步到 .env 文件。": {
    "tr": "Sağlayıcı kanalı ekleyerek modelleri otomatik getirebilir veya elle girebilirsiniz. Ayarlar .env dosyasına kaydedilir.",
    "en": "Add a provider channel to discover models or enter them manually. Settings are saved to .env."
  },
  "▶ 展开": {
    "tr": "▶ Genişlet",
    "en": "▶ Expand"
  },
  "▼ 收起": {
    "tr": "▼ Daralt",
    "en": "▼ Collapse"
  },
  "快速添加渠道": {
    "tr": "Hızlı Kanal Ekle",
    "en": "Quick Add Channel"
  },
  "先选择预设服务商，再一键创建配置草稿。": {
    "tr": "Önce bir sağlayıcı seçin, ardından kanal taslağı oluşturun.",
    "en": "Choose a provider preset, then create a channel draft."
  },
  "+ 添加渠道": {
    "tr": "+ Kanal Ekle",
    "en": "+ Add Channel"
  },
  "选择服务商": {
    "tr": "Sağlayıcı seçin",
    "en": "Select provider"
  },
  "注册 Modelflare": {
    "tr": "Modelflare'a Kaydol",
    "en": "Register for Modelflare"
  },
  "渠道列表": {
    "tr": "Kanal Listesi",
    "en": "Channel List"
  },
  "还没有渠道": {
    "tr": "Henüz kanal eklenmedi",
    "en": "No channels yet"
  },
  "选择服务商预设后点击“添加渠道”即可开始配置。": {
    "tr": "Başlamak için bir sağlayıcı seçip Kanal Ekle'ye tıklayın.",
    "en": "Choose a provider and click Add Channel to start."
  },
  "运行时参数": {
    "tr": "Çalışma Ayarları",
    "en": "Runtime Settings"
  },
  "主模型、备选模型、Vision 与 Temperature 会直接写入运行时配置。": {
    "tr": "Ana model, yedek modeller, görüntü modeli ve sıcaklık ayarı çalışma yapılandırmasına kaydedilir.",
    "en": "Primary, fallback and vision models and temperature are written to runtime configuration."
  },
  "控制模型输出随机性，0 为确定性输出，2 为最大随机性，推荐 0.7。": {
    "tr": "Model yanıtlarının rastgeleliğini belirler. 0 en tutarlı, 2 en değişken; önerilen değer 0,7.",
    "en": "Controls model randomness. 0 is deterministic, 2 is maximum randomness; 0.7 is recommended."
  },
  "先添加至少一个已启用渠道并填写模型，下面的主模型 / 备选模型 / Vision 选项才会出现。": {
    "tr": "Model seçimlerinin görünmesi için en az bir etkin kanal ve model tanımlayın.",
    "en": "Add at least one enabled channel with models to display runtime model selections."
  },
  "主模型": {
    "tr": "Ana Model",
    "en": "Primary Model"
  },
  "Agent 主模型": {
    "tr": "Agent Ana Modeli",
    "en": "Agent Primary Model"
  },
  "备选模型": {
    "tr": "Yedek Modeller",
    "en": "Fallback Models"
  },
  "Vision 模型": {
    "tr": "Görüntü Modeli",
    "en": "Vision Model"
  },
  "备选模型只会在主模型失败时使用。主模型不会重复加入备选模型。": {
    "tr": "Yedek modeller yalnızca ana model başarısız olursa kullanılır. Ana model yedek listesine tekrar eklenmez.",
    "en": "Fallback models are used only if the primary model fails. The primary model is not duplicated in fallbacks."
  },
  "自动（使用第一个可用模型）": {
    "tr": "Otomatik (ilk kullanılabilir model)",
    "en": "Auto (first available model)"
  },
  "自动（继承普通分析主模型）": {
    "tr": "Otomatik (ana analiz modelini kullan)",
    "en": "Auto (inherit primary analysis model)"
  },
  "自动（跟随 Vision 默认逻辑）": {
    "tr": "Otomatik (varsayılan görüntü modeli)",
    "en": "Auto (default vision selection)"
  },
  "检测到已配置高级模型路由 YAML：此处仅管理渠道条目和基础连接信息。运行时主模型 / 备选模型 / Vision / Temperature 仍由下方通用字段决定；若 YAML 解析成功，则以其中的路由与可用模型声明为准，本配置不会覆盖 YAML 文件本身。": {
    "tr": "Gelişmiş YAML model yönlendirmesi bulundu. Burada yalnızca kanal ve bağlantı bilgileri düzenlenir. Çalışma modeli ayarları aşağıdaki genel alanlardan veya geçerli YAML yönlendirmesinden alınır; YAML dosyası değiştirilmez.",
    "en": "Advanced YAML model routing detected. Only channel entries and connection data are managed here. Runtime settings follow the fields below or the valid YAML routes; the YAML file is not overwritten."
  },
  "保存中...": {
    "tr": "Kaydediliyor...",
    "en": "Saving..."
  },
  "保存 AI 配置": {
    "tr": "Yapay Zekâ Ayarlarını Kaydet",
    "en": "Save AI Settings"
  },
  "保存渠道配置": {
    "tr": "Kanal Ayarlarını Kaydet",
    "en": "Save Channel Settings"
  },
  "当前没有未保存的改动": {
    "tr": "Kaydedilmemiş değişiklik yok",
    "en": "No unsaved changes"
  },
  "保存后提示": {
    "tr": "Kaydetme Uyarıları",
    "en": "Save Warnings"
  },
  "渠道名称": {
    "tr": "Kanal Adı",
    "en": "Channel Name"
  },
  "协议": {
    "tr": "Protokol",
    "en": "Protocol"
  },
  "选择协议": {
    "tr": "Protokol seçin",
    "en": "Select protocol"
  },
  "选择 API Surface": {
    "tr": "API türünü seçin",
    "en": "Select API Surface"
  },
  "官方接口可留空": {
    "tr": "Resmî API için boş bırakılabilir",
    "en": "Optional for official APIs"
  },
  "配置参考": {
    "tr": "Yapılandırma Bilgisi",
    "en": "Configuration Reference"
  },
  "官方来源：": {
    "tr": "Resmî kaynaklar:",
    "en": "Official sources:"
  },
  "能力标签仅用于配置参考，不代表运行时能力已验证通过。": {
    "tr": "Özellik etiketleri yalnızca bilgi amaçlıdır; çalıştıkları henüz doğrulanmadı.",
    "en": "Capability labels are informational; runtime support has not been verified."
  },
  "本地 Ollama 可留空": {
    "tr": "Yerel Ollama için boş bırakılabilir",
    "en": "Optional for local Ollama"
  },
  "支持多个 Key 逗号分隔": {
    "tr": "Birden fazla API anahtarı virgülle ayrılabilir",
    "en": "Separate multiple API keys with commas"
  },
  "获取中...": {
    "tr": "Getiriliyor...",
    "en": "Fetching..."
  },
  "获取模型": {
    "tr": "Modelleri Getir",
    "en": "Fetch Models"
  },
  "支持 `/models` 的 OpenAI Compatible 渠道可自动拉取模型。": {
    "tr": "/models uç noktasını destekleyen OpenAI uyumlu kanallar modelleri otomatik getirebilir.",
    "en": "OpenAI-compatible channels supporting /models can discover available models."
  },
  "可选模型（可多选）": {
    "tr": "Seçilebilir Modeller (çoklu seçim)",
    "en": "Available Models (multiple selection)"
  },
  "手动模型（逗号分隔）": {
    "tr": "Elle Eklenen Modeller (virgülle ayırın)",
    "en": "Manual Models (comma-separated)"
  },
  "模型（逗号分隔）": {
    "tr": "Modeller (virgülle ayırın)",
    "en": "Models (comma-separated)"
  },
  "如有自定义模型名未出现在列表中，可继续手动补充，保存格式仍为逗号分隔。": {
    "tr": "Listede olmayan model adlarını elle ekleyebilirsiniz; virgülle ayırın.",
    "en": "Add model names missing from the list manually, separated by commas."
  },
  "若渠道不支持自动发现或请求失败，可直接手动填写模型列表。": {
    "tr": "Otomatik arama desteklenmiyorsa modelleri elle girebilirsiniz.",
    "en": "If discovery is unavailable, enter models manually."
  },
  "测试中...": {
    "tr": "Test ediliyor...",
    "en": "Testing..."
  },
  "测试连接": {
    "tr": "Bağlantıyı Test Et",
    "en": "Test Connection"
  },
  "运行时能力检测（可选）": {
    "tr": "Model Özellik Testi (isteğe bağlı)",
    "en": "Model Capability Check (optional)"
  },
  "运行时能力检测": {
    "tr": "Model Özellik Testi",
    "en": "Model Capability Check"
  },
  "仅在手动触发时发起真实 LLM 请求；多选可能需要 20-40 秒。": {
    "tr": "Yalnızca test düğmesine basınca gerçek model isteği yapılır; birden fazla test zaman alabilir.",
    "en": "Real model requests are only made on demand; multiple checks can take time."
  },
  "检测中...": {
    "tr": "Kontrol ediliyor...",
    "en": "Checking..."
  },
  "检测能力": {
    "tr": "Özellikleri Test Et",
    "en": "Check Capabilities"
  },
  "连接正常": {
    "tr": "Bağlantı başarılı",
    "en": "Connected"
  },
  "连接失败": {
    "tr": "Bağlantı başarısız",
    "en": "Connection failed"
  },
  "测试中": {
    "tr": "Test ediliyor",
    "en": "Testing"
  },
  "未填 Key": {
    "tr": "API anahtarı yok",
    "en": "API key missing"
  },
  "删除渠道": {
    "tr": "Kanalı Sil",
    "en": "Remove channel"
  },
  "未配置模型": {
    "tr": "Henüz model yok",
    "en": "No models configured"
  },
  "无效配置：": {
    "tr": "Geçersiz yapılandırma: ",
    "en": "Invalid configuration: "
  },
  "额外手动模型：": {
    "tr": "Elle eklenen modeller: ",
    "en": "Additional manually added models: "
  },
  "基础连接测试默认使用模型列表首项：": {
    "tr": "Temel bağlantı testi ilk modeli kullanır: ",
    "en": "Basic connection test uses the first model: "
  },
  "（当前配置）": {
    "tr": " (mevcut seçim)",
    "en": " (current selection)"
  },
  "（默认）": {
    "tr": " (varsayılan)",
    "en": " (default)"
  },
  "通过": {
    "tr": "Başarılı",
    "en": "Passed"
  },
  "失败": {
    "tr": "Başarısız",
    "en": "Failed"
  },
  "跳过": {
    "tr": "Atlandı",
    "en": "Skipped"
  },
  "模型发现": {
    "tr": "Model keşfi",
    "en": "Model discovery"
  },
  "聊天调用": {
    "tr": "Sohbet isteği",
    "en": "Chat request"
  },
  "Responses 调用": {
    "tr": "Responses isteği",
    "en": "Responses request"
  },
  "响应解析": {
    "tr": "Yanıt çözümleme",
    "en": "Response parsing"
  },
  "JSON 能力": {
    "tr": "JSON desteği",
    "en": "JSON capability"
  },
  "Tools 能力": {
    "tr": "Araç çağrısı desteği",
    "en": "Tool calling"
  },
  "Stream 能力": {
    "tr": "Akış desteği",
    "en": "Streaming capability"
  },
  "Vision 能力": {
    "tr": "Görsel işleme desteği",
    "en": "Vision capability"
  },
  "鉴权失败": {
    "tr": "Kimlik doğrulama başarısız",
    "en": "Authentication failed"
  },
  "请求超时": {
    "tr": "İstek zaman aşımı",
    "en": "Request timeout"
  },
  "额度或限流": {
    "tr": "Kota veya hız sınırı",
    "en": "Quota or rate limit"
  },
  "模型不可用": {
    "tr": "Model kullanılamıyor",
    "en": "Model unavailable"
  },
  "请求被拦截": {
    "tr": "İstek engellendi",
    "en": "Request blocked"
  },
  "空响应": {
    "tr": "Boş yanıt",
    "en": "Empty response"
  },
  "格式异常": {
    "tr": "Geçersiz biçim",
    "en": "Invalid format"
  },
  "网络异常": {
    "tr": "Ağ hatası",
    "en": "Network error"
  },
  "配置无效": {
    "tr": "Geçersiz ayar",
    "en": "Invalid configuration"
  },
  "协议暂不支持": {
    "tr": "Desteklenmeyen protokol",
    "en": "Unsupported protocol"
  },
  "能力不支持": {
    "tr": "Özellik desteklenmiyor",
    "en": "Capability unsupported"
  },
  "已跳过": {
    "tr": "Atlandı",
    "en": "Skipped"
  },
  "连接测试": {
    "tr": "Bağlantı testi",
    "en": "Connection test"
  },
  "测试失败": {
    "tr": "Test başarısız",
    "en": "Test failed"
  },
  "能力检测失败": {
    "tr": "Özellik testi başarısız",
    "en": "Capability check failed"
  },
  "未返回能力检测结果": {
    "tr": "Özellik testi sonucu dönmedi",
    "en": "No capability results returned"
  },
  "正在检测运行时能力...": {
    "tr": "Model özellikleri kontrol ediliyor...",
    "en": "Checking model capabilities..."
  },
  "正在获取模型列表...": {
    "tr": "Model listesi getiriliyor...",
    "en": "Fetching model list..."
  },
  "获取模型失败": {
    "tr": "Modeller getirilemedi",
    "en": "Model discovery failed"
  },
  "渠道名称不能为空，且只能包含字母、数字或下划线。": {
    "tr": "Kanal adı boş olamaz; yalnızca harf, rakam ve alt çizgi kullanılabilir.",
    "en": "Channel name cannot be blank; use only letters, digits and underscores."
  },
  "Mixed Hermes/non-Hermes route 暂不支持作为主生成或备选模型，请选择纯 Hermes 或纯非 Hermes route。": {
    "tr": "Karma Hermes/non-Hermes yönlendirmesi ana veya yedek model olamaz. Tek tür yönlendirme seçin.",
    "en": "Mixed Hermes/non-Hermes routes cannot be primary or fallback models. Select a pure route."
  },
  "当前运行时模型使用非规范 route alias，请从下拉框重新选择规范模型。": {
    "tr": "Geçersiz model yönlendirme takma adı seçilmiş. Açılır listeden geçerli modeli seçin.",
    "en": "Invalid model route alias. Select a canonical model from the dropdown."
  },
  "当前主模型不在已启用渠道的模型列表中，请重新选择。": {
    "tr": "Ana model etkin kanalların model listesinde yok. Yeniden seçin.",
    "en": "Primary model is not in any enabled channel model list. Select another."
  },
  "当前 Agent 主模型没有 Agent-safe 非 Hermes deployment，请重新选择。": {
    "tr": "Agent ana modeli için güvenli, Hermes olmayan dağıtım bulunamadı. Yeniden seçin.",
    "en": "Agent primary model has no Agent-safe non-Hermes deployment. Select another."
  },
  "存在无效的备选模型，请重新选择。": {
    "tr": "Geçersiz yedek model var. Yeniden seçin.",
    "en": "Invalid fallback model. Select another."
  },
  "当前 Vision 模型不能包含 Hermes deployment，请重新选择纯非 Hermes route。": {
    "tr": "Görsel modelde Hermes dağıtımı kullanılamaz. Hermes olmayan bir model seçin.",
    "en": "Vision model cannot use Hermes deployment. Select a non-Hermes route."
  },
  "AI 配置已保存": {
    "tr": "Yapay zekâ ayarları kaydedildi",
    "en": "AI settings saved"
  },
  "渠道配置已保存": {
    "tr": "Kanal ayarları kaydedildi",
    "en": "Channel settings saved"
  },
  "连接成功": {
    "tr": "Bağlantı kuruldu",
    "en": "Connected"
  },
  "OpenAI 兼容": {
    "tr": "OpenAI uyumlu",
    "en": "OpenAI Compatible"
  },
  "聚合平台": {
    "tr": "Model toplayıcı",
    "en": "Model Aggregator"
  },
  "官方 API": {
    "tr": "Resmî API",
    "en": "Official API"
  },
  "可获取模型": {
    "tr": "Model listesi alınabilir",
    "en": "Model Discovery"
  },
  "Vision 提示": {
    "tr": "Görüntü modeline uygun olabilir",
    "en": "Vision Hint"
  },
  "本地运行": {
    "tr": "Yerel çalışma",
    "en": "Local Runtime"
  },
  "按 OpenAI-compatible endpoint 配置 Base URL，不额外拼接 /chat/completions。": {
    "tr": "Base URL'yi OpenAI uyumlu uç nokta olarak girin; /chat/completions eklemeyin.",
    "en": "Set an OpenAI-compatible Base URL; do not append /chat/completions."
  },
  "模型可见性、路由和价格可能随账号权限与平台策略变化。": {
    "tr": "Görünen modeller, yönlendirme ve fiyatlar hesap izinlerine göre değişebilir.",
    "en": "Available models, routing and pricing depend on account permissions."
  },
  "使用服务商官方协议或官方兼容入口。": {
    "tr": "Sağlayıcının resmî API'sini kullanın.",
    "en": "Use the provider's official protocol or compatible API."
  },
  "支持尝试通过 /models 获取模型列表；实际结果仍取决于账号权限和 API Key。": {
    "tr": "/models üzerinden modeller sorgulanabilir; sonuçlar hesap yetkilerine bağlıdır.",
    "en": "You can request models via /models, subject to account permissions."
  },
  "模板提示该 provider 常用于 Vision 场景；具体模型能力仍以账号和模型列表为准。": {
    "tr": "Bu sağlayıcı görsel işlemede kullanılabilir; gerçek özellikleri model ve hesaba bağlıdır.",
    "en": "The provider may support vision; actual capabilities depend on model and account."
  },
  "需要当前运行环境能访问对应本地服务。": {
    "tr": "Bu ortamdan yerel model servisine erişilebilmelidir.",
    "en": "The runtime must be able to reach the local model service."
  },
  "Modelflare（聚合平台）": {
    "tr": "Modelflare (model toplayıcı)",
    "en": "Modelflare (aggregator)"
  },
  "AIHubmix（聚合平台）": {
    "tr": "AIHubmix (model toplayıcı)",
    "en": "AIHubmix (aggregator)"
  },
  "DeepSeek 官方": {
    "tr": "DeepSeek Resmî",
    "en": "DeepSeek Official"
  },
  "通义千问（Dashscope）": {
    "tr": "Qwen (DashScope)",
    "en": "Qwen (DashScope)"
  },
  "智谱 GLM": {
    "tr": "Zhipu GLM",
    "en": "Zhipu GLM"
  },
  "Moonshot（月之暗面）": {
    "tr": "Moonshot (Kimi)",
    "en": "Moonshot (Kimi)"
  },
  "MiniMax 官方": {
    "tr": "MiniMax Resmî",
    "en": "MiniMax Official"
  },
  "火山方舟（豆包）": {
    "tr": "Volcengine Ark (Doubao)",
    "en": "Volcengine Ark (Doubao)"
  },
  "硅基流动（SiliconFlow）": {
    "tr": "SiliconFlow",
    "en": "SiliconFlow"
  },
  "Gemini 官方": {
    "tr": "Gemini Resmî",
    "en": "Gemini Official"
  },
  "Anthropic 官方": {
    "tr": "Anthropic Resmî",
    "en": "Anthropic Official"
  },
  "OpenAI 官方": {
    "tr": "OpenAI Resmî",
    "en": "OpenAI Official"
  },
  "Ollama（本地）": {
    "tr": "Ollama (yerel)",
    "en": "Ollama (local)"
  },
  "自定义渠道": {
    "tr": "Özel Kanal",
    "en": "Custom Channel"
  },
  "Modelflare 专属注册": {
    "tr": "Modelflare kayıt",
    "en": "Modelflare registration"
  },
  "API Key 的路由分组需支持所选模型；模型 ID 请以控制台或获取模型的结果为准。modelflare 渠道的 Base URL 留空时使用默认 /v1 地址，可按需覆盖，不额外拼接 /chat/completions。": {
    "tr": "API anahtarının seçilen model erişimine sahip olması gerekir. Model kimliğini panelden veya model keşfinden kontrol edin. Boş Base URL, varsayılan /v1 adresini kullanır; /chat/completions eklemeyin.",
    "en": "API key must permit the selected model. Verify model IDs in the console or discovery. Empty Base URL uses the default /v1 endpoint; do not append /chat/completions."
  },
  "模型列表和模型可见性依赖账号权限与 API Key。": {
    "tr": "Model listesi hesap izinlerine ve API anahtarına bağlıdır.",
    "en": "Model availability depends on account and API key permissions."
  },
  "模型列表和模型可见性依赖账号权限与 API Key；EU 区域可将 Base URL 改为 https://router.eu.requesty.ai/v1。": {
    "tr": "Modeller hesap izinlerine bağlıdır. Avrupa için https://router.eu.requesty.ai/v1 kullanılabilir.",
    "en": "Models depend on account permissions. EU users can use https://router.eu.requesty.ai/v1."
  },
  "确认在线推理 endpoint / region 与 Coding Plan 专用入口不要混用。": {
    "tr": "Normal API uç noktasını Coding Plan adresiyle karıştırmayın; bölgeyi kontrol edin.",
    "en": "Do not mix inference endpoint/region with the Coding Plan endpoint."
  },
  "需要本机、Docker 或 self-hosted runner 能访问 Ollama 服务。": {
    "tr": "Bilgisayarın veya Docker ortamının Ollama sunucusuna erişebilmesi gerekir.",
    "en": "Local machine, Docker or self-hosted runner must reach Ollama."
  },
  "同一 ANSPIRE_API_KEYS 可复用到搜索与 LLM 渠道。以下模型与网关为配置示例，实际可用性请以账号权限和控制台为准；建议先点“测试连接”确认。": {
    "tr": "ANSPIRE_API_KEYS hem arama hem model kanalında kullanılabilir. Örnek modellerin gerçek erişimini hesabınızdan ve bağlantı testinden doğrulayın.",
    "en": "ANSPIRE_API_KEYS may be reused for search and LLM. Verify sample model availability with your account and connection test."
  }
};

export function llmUiText(chinese: string, language: UiLanguage): string {
  return language === 'zh' ? chinese : LABELS[chinese]?.[language] ?? chinese;
}

export function llmUiParts(chinesePrefix: string, value: string, language: UiLanguage): string {
  return llmUiText(chinesePrefix, language) + value;
}
