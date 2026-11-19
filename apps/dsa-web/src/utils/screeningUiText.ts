import type { UiLanguage } from '../i18n/uiText';

/** Presentation-only screening translations. Never translate identifiers or source payloads. */
const LABELS: Record<string, { tr: string; en: string }> = {
  "选股": {
    "tr": "Hisse Tarama",
    "en": "Stock Screening"
  },
  "选股状态加载失败": {
    "tr": "Hisse tarama durumu yüklenemedi",
    "en": "Screening status failed to load"
  },
  "正在读取选股配置，请稍候。": {
    "tr": "Hisse tarama ayarları kontrol ediliyor.",
    "en": "Checking screening configuration."
  },
  "重试": {
    "tr": "Yeniden dene",
    "en": "Retry"
  },
  "选股未开启": {
    "tr": "Hisse tarama kapalı",
    "en": "Stock screening disabled"
  },
  "开启后即可运行选股策略。": {
    "tr": "Etkinleştirildiğinde hisse tarama stratejileri çalıştırılabilir.",
    "en": "Enable screening to run stock strategies."
  },
  "开启中...": {
    "tr": "Etkinleştiriliyor...",
    "en": "Enabling..."
  },
  "开启选股": {
    "tr": "Hisse Taramayı Aç",
    "en": "Enable Screening"
  },
  "选股功能不可用": {
    "tr": "Hisse tarama kullanılamıyor",
    "en": "Stock screening unavailable"
  },
  "请检查后端日志、策略文件和基础数据依赖后重启服务。": {
    "tr": "Sunucu günlüklerini, strateji dosyalarını ve veri bağlantılarını kontrol edin.",
    "en": "Check backend logs, strategy files and data dependencies."
  },
  "调用失败": {
    "tr": "İstek başarısız",
    "en": "Request failed"
  },
  "热点题材": {
    "tr": "Öne Çıkan Temalar",
    "en": "Trending Themes"
  },
  "收起热点题材": {
    "tr": "Temaları daralt",
    "en": "Collapse themes"
  },
  "展开热点题材": {
    "tr": "Temaları genişlet",
    "en": "Expand themes"
  },
  "刷新中...": {
    "tr": "Yenileniyor...",
    "en": "Refreshing..."
  },
  "刷新热点题材": {
    "tr": "Temaları yenile",
    "en": "Refresh themes"
  },
  "更新于": {
    "tr": "Güncelleme:",
    "en": "Updated:"
  },
  "暂无热点数据，点击“刷新热点题材”获取。": {
    "tr": "Henüz tema verisi yok. Getirmek için Temaları yenile'ye tıklayın.",
    "en": "No trending theme data yet. Click Refresh themes."
  },
  "涨跌幅": {
    "tr": "Fiyat değişimi",
    "en": "Price change"
  },
  "趋势": {
    "tr": "Trend",
    "en": "Trend"
  },
  "持续": {
    "tr": "Süreklilik",
    "en": "Persistence"
  },
  "龙头": {
    "tr": "Öncü hisseler",
    "en": "Leaders"
  },
  "正在读取发酵路线与概念股...": {
    "tr": "Tema gelişimi ve ilgili hisseler yükleniyor...",
    "en": "Loading theme trend and related stocks..."
  },
  "点击题材查看发酵路线与概念股。": {
    "tr": "Tema gelişimini ve ilgili hisseleri görmek için tema seçin.",
    "en": "Select a theme to view its evolution and related stocks."
  },
  "标准题材：": {
    "tr": "Ana tema: ",
    "en": "Canonical theme: "
  },
  "搜索中...": {
    "tr": "Aranıyor...",
    "en": "Searching..."
  },
  "搜索最新消息": {
    "tr": "Güncel haberleri ara",
    "en": "Search recent news"
  },
  "正在补充详情": {
    "tr": "Ayrıntılar yükleniyor",
    "en": "Loading details"
  },
  "质量": {
    "tr": "Kalite",
    "en": "Quality"
  },
  "概念股": {
    "tr": "İlgili hisseler",
    "en": "Related stocks"
  },
  "详情数据已降级，展开查看原因": {
    "tr": "Bazı veriler eksik; nedenini göster",
    "en": "Some detail data is degraded; show why"
  },
  "暂缺：": {
    "tr": "Eksik: ",
    "en": "Missing: "
  },
  "发酵时间线": {
    "tr": "Tema gelişim zaman çizelgesi",
    "en": "Theme evolution timeline"
  },
  "查看消息": {
    "tr": "Haberi görüntüle",
    "en": "View news"
  },
  "分析": {
    "tr": "Analiz et",
    "en": "Analyze"
  },
  "热度": {
    "tr": "İlgi puanı",
    "en": "Heat"
  },
  "运行选股": {
    "tr": "Hisse Taramasını Çalıştır",
    "en": "Run Screening"
  },
  "市场": {
    "tr": "Piyasa",
    "en": "Market"
  },
  "策略": {
    "tr": "Strateji",
    "en": "Strategy"
  },
  "自定义策略…": {
    "tr": "Özel strateji…",
    "en": "Custom strategy…"
  },
  "自定义策略 ID": {
    "tr": "Özel strateji kimliği",
    "en": "Custom strategy ID"
  },
  "输入策略 ID": {
    "tr": "Strateji kimliğini girin",
    "en": "Enter strategy ID"
  },
  "返回数量": {
    "tr": "Sonuç sayısı",
    "en": "Results limit"
  },
  "筛选中...": {
    "tr": "Taranıyor...",
    "en": "Screening..."
  },
  "策略会先执行硬过滤和因子评分，再进行风险与组合约束。": {
    "tr": "Strateji önce filtreleme ve faktör puanlaması, sonra risk ve portföy kısıtları uygular.",
    "en": "The strategy filters and scores factors before risk and portfolio constraints."
  },
  "选股运行中": {
    "tr": "Hisse tarama çalışıyor",
    "en": "Screening in progress"
  },
  "选股完成": {
    "tr": "Hisse tarama tamamlandı",
    "en": "Screening completed"
  },
  "正在执行选股": {
    "tr": "Hisseler taranıyor",
    "en": "Screening stocks"
  },
  "运行详情": {
    "tr": "Çalışma ayrıntıları",
    "en": "Run details"
  },
  "任务：": {
    "tr": "Görev: ",
    "en": "Task: "
  },
  "快照": {
    "tr": "Anlık görüntü",
    "en": "Snapshot"
  },
  "过滤后": {
    "tr": "Filtre sonrası",
    "en": "After filter"
  },
  "候选": {
    "tr": "Adaylar",
    "en": "Candidates"
  },
  "排序：": {
    "tr": "Sıralama: ",
    "en": "Ranking: "
  },
  "智能重排": {
    "tr": "Yapay zekâ sıralaması",
    "en": "AI reranking"
  },
  "确定性因子": {
    "tr": "Kural tabanlı faktörler",
    "en": "Deterministic factors"
  },
  "覆盖": {
    "tr": "Kapsam",
    "en": "Coverage"
  },
  "候选差异：近分池": {
    "tr": "Aday farkları / yakın puanlılar:",
    "en": "Candidate variation / close scores:"
  },
  "本次替换": {
    "tr": "Bu kez değiştirilen",
    "en": "Replaced this run"
  },
  "本次保持基准": {
    "tr": "Temel sıra korundu",
    "en": "Baseline maintained"
  },
  "深度补充：": {
    "tr": "Derinleştirilmiş veri: ",
    "en": "Enrichment: "
  },
  "当前使用因子排序": {
    "tr": "Faktör sıralaması kullanılıyor",
    "en": "Using factor ranking"
  },
  "选股提示": {
    "tr": "Tarama bilgilendirmesi",
    "en": "Screening notice"
  },
  "选股结果": {
    "tr": "Hisse Tarama Sonuçları",
    "en": "Stock Screening Results"
  },
  "条候选": {
    "tr": "aday hisse",
    "en": "candidates"
  },
  "暂无符合条件的候选": {
    "tr": "Koşullara uygun aday hisse yok",
    "en": "No candidates meet the conditions"
  },
  "代码": {
    "tr": "Kod",
    "en": "Code"
  },
  "名称": {
    "tr": "Ad",
    "en": "Name"
  },
  "行业": {
    "tr": "Sektör",
    "en": "Sector"
  },
  "价格": {
    "tr": "Fiyat",
    "en": "Price"
  },
  "评分": {
    "tr": "Puan",
    "en": "Score"
  },
  "排序依据": {
    "tr": "Sıralama ölçütü",
    "en": "Ranking basis"
  },
  "风险": {
    "tr": "Risk",
    "en": "Risk"
  },
  "详情": {
    "tr": "Ayrıntılar",
    "en": "Details"
  },
  "因子排序": {
    "tr": "Faktör sıralaması",
    "en": "Factor ranking"
  },
  "收起": {
    "tr": "Daralt",
    "en": "Collapse"
  },
  "展开查看": {
    "tr": "Ayrıntıları göster",
    "en": "Expand details"
  },
  "为什么入选": {
    "tr": "Neden seçildi?",
    "en": "Why selected?"
  },
  "暂无可验证的入选解释": {
    "tr": "Doğrulanabilir seçim açıklaması yok",
    "en": "No verifiable selection explanation"
  },
  "综合质量：": {
    "tr": "Genel veri kalitesi: ",
    "en": "Overall quality: "
  },
  "为什么现在": {
    "tr": "Neden şimdi?",
    "en": "Why now?"
  },
  "暂无带来源的价格、消息或事件证据": {
    "tr": "Kaynaklı fiyat, haber veya olay kanıtı yok",
    "en": "No sourced price, news or event evidence"
  },
  "摘要": {
    "tr": "Özet",
    "en": "Summary"
  },
  "操作信号": {
    "tr": "İşlem sinyali",
    "en": "Action signal"
  },
  "进一步深度分析": {
    "tr": "Derinlemesine analiz et",
    "en": "Run in-depth analysis"
  },
  "增强摘要": {
    "tr": "Genişletilmiş özet",
    "en": "Enriched summary"
  },
  "智能判断": {
    "tr": "Yapay zekâ değerlendirmesi",
    "en": "AI assessment"
  },
  "板块": {
    "tr": "Sektör",
    "en": "Sector"
  },
  "主题": {
    "tr": "Tema",
    "en": "Theme"
  },
  "置信度": {
    "tr": "Güven düzeyi",
    "en": "Confidence"
  },
  "风险标签": {
    "tr": "Risk etiketleri",
    "en": "Risk flags"
  },
  "无": {
    "tr": "Yok",
    "en": "None"
  },
  "风险摘要": {
    "tr": "Risk özeti",
    "en": "Risk summary"
  },
  "主要因子": {
    "tr": "Ana faktörler",
    "en": "Key factors"
  },
  "无因子明细": {
    "tr": "Faktör ayrıntısı yok",
    "en": "No factor details"
  },
  "成交额": {
    "tr": "İşlem hacmi (tutar)",
    "en": "Turnover"
  },
  "智能关注项": {
    "tr": "Yapay zekâ takip notları",
    "en": "AI watch items"
  },
  "催化因素": {
    "tr": "Tetikleyici gelişmeler",
    "en": "Catalysts"
  },
  "相关新闻": {
    "tr": "İlgili haberler",
    "en": "Related news"
  },
  "公告与事件": {
    "tr": "Duyurular ve olaylar",
    "en": "Announcements and events"
  },
  "数据补充提示": {
    "tr": "Veri tamamlama notları",
    "en": "Data enrichment notices"
  },
  "历史记录": {
    "tr": "Geçmiş Taramalar",
    "en": "Screening History"
  },
  "加载中...": {
    "tr": "Yükleniyor...",
    "en": "Loading..."
  },
  "刷新": {
    "tr": "Yenile",
    "en": "Refresh"
  },
  "正在加载历史记录...": {
    "tr": "Tarama geçmişi yükleniyor...",
    "en": "Loading screening history..."
  },
  "暂无历史选股记录": {
    "tr": "Henüz tarama geçmişi yok",
    "en": "No screening history"
  },
  "返回": {
    "tr": "Sonuç:",
    "en": "Returned"
  },
  "只": {
    "tr": "hisse",
    "en": "stocks"
  },
  "A 股": {
    "tr": "Çin A Hisseleri",
    "en": "China A-Shares"
  },
  "综合": {
    "tr": "Genel",
    "en": "General"
  },
  "收益": {
    "tr": "Getiri",
    "en": "Return"
  },
  "动量": {
    "tr": "Momentum",
    "en": "Momentum"
  },
  "反转": {
    "tr": "Tersine dönüş",
    "en": "Reversal"
  },
  "价值": {
    "tr": "Değer",
    "en": "Value"
  },
  "可用": {
    "tr": "Kullanılabilir",
    "en": "Available"
  },
  "不可用": {
    "tr": "Kullanılamıyor",
    "en": "Unavailable"
  },
  "部分可用": {
    "tr": "Kısmen kullanılabilir",
    "en": "Partially available"
  },
  "缓存": {
    "tr": "Önbellek",
    "en": "Cached"
  },
  "高": {
    "tr": "Yüksek",
    "en": "High"
  },
  "中": {
    "tr": "Orta",
    "en": "Medium"
  },
  "低": {
    "tr": "Düşük",
    "en": "Low"
  },
  "待评估": {
    "tr": "Değerlendirme bekleniyor",
    "en": "Pending assessment"
  },
  "未知策略": {
    "tr": "Bilinmeyen strateji",
    "en": "Unknown strategy"
  },
  "自定义": {
    "tr": "Özel",
    "en": "Custom"
  },
  "自定义策略": {
    "tr": "Özel strateji",
    "en": "Custom strategy"
  },
  "时间未知": {
    "tr": "Zaman bilinmiyor",
    "en": "Time unknown"
  },
  "正在恢复选股任务状态...": {
    "tr": "Tarama görevi geri yükleniyor...",
    "en": "Restoring screening task..."
  },
  "已加载历史选股结果": {
    "tr": "Geçmiş tarama sonuçları yüklendi",
    "en": "Historical screening results loaded"
  },
  "选股任务已完成，但服务端未返回候选结果。": {
    "tr": "Görev tamamlandı, ancak sunucu aday sonuçları döndürmedi.",
    "en": "Screening task completed without candidate results."
  },
  "选股任务提交失败，请稍后重试。": {
    "tr": "Tarama başlatılamadı. Yeniden deneyin.",
    "en": "Could not start screening. Try again."
  },
  "正在提交选股任务...": {
    "tr": "Tarama başlatılıyor...",
    "en": "Submitting screening task..."
  },
  "选股任务已提交": {
    "tr": "Tarama görevi gönderildi",
    "en": "Screening task submitted"
  },
  "历史记录加载失败": {
    "tr": "Geçmiş yüklenemedi",
    "en": "History failed to load"
  }
};

export function screeningUiText(chinese: string, language: UiLanguage): string {
  return language === 'zh' ? chinese : LABELS[chinese]?.[language] ?? chinese;
}
