import type { UiLanguage } from '../i18n/uiText';

/** Display-only localization: rule identifiers, statuses and payloads stay unchanged. */
const LABELS: Record<string, { tr: string; en: string }> = {
  "告警中心": {
    "tr": "Uyarı Merkezi",
    "en": "Alert Center"
  },
  "告警中心 - DSA": {
    "tr": "Uyarı Merkezi - EBBot",
    "en": "Alert Center - EBBot"
  },
  "管理事件告警、日线技术指标、自选股、持仓/账户联动和大盘红绿灯规则，执行一次性测试，并查看后台评估任务记录的触发历史。": {
    "tr": "Olay, teknik gösterge, takip listesi ve portföy uyarılarını yönetin. Testleri ve geçmiş tetiklemeleri inceleyin.",
    "en": "Manage event, indicator, watchlist and portfolio alerts. Review tests and trigger history."
  },
  "创建成功": {
    "tr": "Oluşturuldu",
    "en": "Created"
  },
  "关闭": {
    "tr": "Kapat",
    "en": "Close"
  },
  "存在环境变量告警规则": {
    "tr": "Ortam değişkeniyle tanımlı uyarılar var",
    "en": "Environment-defined alert rules exist"
  },
  "测试结果": {
    "tr": "Test Sonuçları",
    "en": "Test Results"
  },
  "通知尝试记录": {
    "tr": "Bildirim Gönderim Denemeleri",
    "en": "Notification Attempts"
  },
  "通知结果": {
    "tr": "Bildirim Sonuçları",
    "en": "Notification Results"
  },
  "正在加载通知尝试记录": {
    "tr": "Bildirim denemeleri yükleniyor",
    "en": "Loading notification attempts"
  },
  "暂无通知尝试记录": {
    "tr": "Henüz bildirim denemesi yok",
    "en": "No notification attempts"
  },
  "当前没有可展示的通知尝试明细；告警触发仍会按已配置通知渠道发送。": {
    "tr": "Gösterilecek bildirim kaydı yok. Uyarılar yapılandırılmış kanallardan gönderilmeye devam edebilir.",
    "en": "No attempts to display. Alerts can still use configured notification channels."
  },
  "渠道": {
    "tr": "Kanal",
    "en": "Channel"
  },
  "状态": {
    "tr": "Durum",
    "en": "Status"
  },
  "错误码": {
    "tr": "Hata kodu",
    "en": "Error code"
  },
  "耗时": {
    "tr": "Süre",
    "en": "Latency"
  },
  "时间": {
    "tr": "Zaman",
    "en": "Time"
  },
  "诊断": {
    "tr": "Tanılama",
    "en": "Diagnostics"
  },
  "业务冷却": {
    "tr": "Bekleme süresi",
    "en": "Cooldown"
  },
  "冷却读取失败": {
    "tr": "Bekleme bilgisi alınamadı",
    "en": "Cooldown lookup failed"
  },
  "通知降噪": {
    "tr": "Bildirim azaltma",
    "en": "Notification noise suppression"
  },
  "无可用渠道": {
    "tr": "Uygun kanal yok",
    "en": "No available channel"
  },
  "通知调度": {
    "tr": "Bildirim yönlendirmesi",
    "en": "Notification dispatch"
  },
  "会话渠道": {
    "tr": "Sohbet kanalı",
    "en": "Context channel"
  },
  "成功": {
    "tr": "Başarılı",
    "en": "Succeeded"
  },
  "冷却抑制": {
    "tr": "Bekleme nedeniyle engellendi",
    "en": "Suppressed by cooldown"
  },
  "降噪抑制": {
    "tr": "Gereksiz bildirim engellendi",
    "en": "Suppressed by noise filter"
  },
  "无渠道": {
    "tr": "Kanal yok",
    "en": "No channel"
  },
  "失败": {
    "tr": "Başarısız",
    "en": "Failed"
  },
  " · 状态：": {
    "tr": " · Durum: ",
    "en": " · Status: "
  },
  " · 触发：": {
    "tr": " · Tetiklendi: ",
    "en": " · Triggered: "
  },
  " · 观察值：": {
    "tr": " · Ölçülen değer: ",
    "en": " · Observed value: "
  },
  "是": {
    "tr": "Evet",
    "en": "Yes"
  },
  "否": {
    "tr": "Hayır",
    "en": "No"
  },
  "评估": {
    "tr": "Değerlendirilen",
    "en": "Evaluated"
  },
  "触发": {
    "tr": "Tetiklenen",
    "en": "Triggered"
  },
  "降级": {
    "tr": "Kısıtlı",
    "en": "Degraded"
  },
  "跳过": {
    "tr": "Atlanan",
    "en": "Skipped"
  },
  "已创建告警规则": {
    "tr": "Uyarı kuralı oluşturuldu",
    "en": "Alert rule created"
  },
  "已触发": {
    "tr": "Tetiklendi",
    "en": "Triggered"
  },
  "已跳过": {
    "tr": "Atlandı",
    "en": "Skipped"
  },
  "触发历史": {
    "tr": "Tetikleme Geçmişi",
    "en": "Trigger History"
  },
  "评估记录": {
    "tr": "Değerlendirme Kayıtları",
    "en": "Evaluation Records"
  },
  "正在加载触发历史": {
    "tr": "Tetikleme geçmişi yükleniyor",
    "en": "Loading trigger history"
  },
  "暂无触发历史": {
    "tr": "Henüz tetikleme geçmişi yok",
    "en": "No trigger history"
  },
  "后台评估会记录 triggered、skipped、degraded 和 failed 状态；正常未触发不会写入历史。": {
    "tr": "Arka plan değerlendirmesi tetiklenen, atlanan, kısıtlı ve başarısız denemeleri kaydeder. Tetiklenmeyen kontroller geçmişe yazılmaz.",
    "en": "Background evaluations record triggered, skipped, degraded and failed states; untriggered checks are not logged."
  },
  "阶段 / 质量": {
    "tr": "Piyasa evresi / kalite",
    "en": "Phase / quality"
  },
  "目标": {
    "tr": "Hedef",
    "en": "Target"
  },
  "观察值": {
    "tr": "Ölçülen değer",
    "en": "Observed value"
  },
  "阈值": {
    "tr": "Eşik",
    "en": "Threshold"
  },
  "数据源": {
    "tr": "Veri kaynağı",
    "en": "Data source"
  },
  "数据时间": {
    "tr": "Veri zamanı",
    "en": "Data timestamp"
  },
  "原因": {
    "tr": "Gerekçe",
    "en": "Reason"
  },
  "质量：": {
    "tr": "Kalite: ",
    "en": "Quality: "
  }
};

export function alertUiText(chinese: string, language: UiLanguage): string {
  return language === 'zh' ? chinese : LABELS[chinese]?.[language] ?? chinese;
}
