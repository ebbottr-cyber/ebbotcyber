import type { UiLanguage } from '../i18n/uiText';

// Presentation-only localization of legacy portfolio controls. Source text
// stays available for Chinese UI, without changing persisted account, stock,
// broker, trade, currency or transaction values.
const TRANSLATIONS: Record<string, { tr: string; en: string }> = {
  "券商列表接口返回为空，已回退为内置券商列表（华泰/中信/招商）。": {
    "tr": "Aracı kurum listesi boş geldi; yerleşik kurum listesi kullanılıyor (Huatai/CITIC/China Merchants).",
    "en": "Broker list was empty; using built-in brokers."
  },
  "券商列表接口不可用，已回退为内置券商列表（华泰/中信/招商）。": {
    "tr": "Aracı kurum listesine ulaşılamadı; yerleşik kurum listesi kullanılıyor.",
    "en": "Broker list unavailable; using built-in brokers."
  },
  "风险数据获取失败，已降级为仅展示快照数据。": {
    "tr": "Risk verisi alınamadı; yalnızca portföy özeti gösteriliyor.",
    "en": "Risk data unavailable; showing the portfolio snapshot only."
  },
  "请先在右上角选择具体账户，再进行录入或导入提交。": {
    "tr": "İşlem eklemek veya içe aktarmak için sağ üstten bir hesap seçin.",
    "en": "Select an account in the upper right before adding or importing transactions."
  },
  "请先在右上角选择具体账户，再进行删除修正。": {
    "tr": "Bir işlemi düzeltmek veya silmek için sağ üstten hesap seçin.",
    "en": "Select an account in the upper right before correcting a transaction."
  },
  "请先选择具体账户，再删除持仓账户。": {
    "tr": "Silmeden önce bir hesap seçin.",
    "en": "Select an account before deleting it."
  },
  "账户名称不能为空。": {
    "tr": "Hesap adı boş olamaz.",
    "en": "Account name cannot be empty."
  },
  "账户创建成功，已自动切换到该账户。": {
    "tr": "Hesap oluşturuldu ve seçildi.",
    "en": "Account created and selected."
  },
  "创建账户失败，请稍后重试。": {
    "tr": "Hesap oluşturulamadı; sonra tekrar deneyin.",
    "en": "Account creation failed; try again later."
  },
  "新建账户": {
    "tr": "Yeni hesap",
    "en": "New account"
  },
  "收起": {
    "tr": "Daralt",
    "en": "Collapse"
  },
  "创建后自动切换到该账户": {
    "tr": "Oluşturulduğunda yeni hesap seçilir",
    "en": "The new account is selected automatically"
  },
  "创建账户失败": {
    "tr": "Hesap oluşturulamadı",
    "en": "Account creation failed"
  },
  "创建账户成功": {
    "tr": "Hesap oluşturuldu",
    "en": "Account created"
  },
  "账户名称（必填）": {
    "tr": "Hesap adı (zorunlu)",
    "en": "Account name (required)"
  },
  "券商（可选，如 Demo/华泰）": {
    "tr": "Aracı kurum (isteğe bağlı, ör. Demo/Huatai)",
    "en": "Broker (optional, e.g. Demo/Huatai)"
  },
  "基准币（如 CNY/USD/HKD）": {
    "tr": "Temel para birimi (ör. TRY/USD/HKD)",
    "en": "Base currency (e.g. TRY/USD/HKD)"
  },
  "市场：A 股（cn）": {
    "tr": "Piyasa: Çin A hisseleri (cn)",
    "en": "Market: China A-shares (cn)"
  },
  "市场：港股（hk）": {
    "tr": "Piyasa: Hong Kong (hk)",
    "en": "Market: Hong Kong (hk)"
  },
  "市场：美股（us）": {
    "tr": "Piyasa: ABD (us)",
    "en": "Market: USA (us)"
  },
  "市场：日股（jp）": {
    "tr": "Piyasa: Japonya (jp)",
    "en": "Market: Japan (jp)"
  },
  "市场：韩股（kr）": {
    "tr": "Piyasa: Güney Kore (kr)",
    "en": "Market: South Korea (kr)"
  },
  "市场：台股（tw）": {
    "tr": "Piyasa: Tayvan (tw)",
    "en": "Market: Taiwan (tw)"
  },
  "创建中...": {
    "tr": "Oluşturuluyor...",
    "en": "Creating..."
  },
  "创建账户": {
    "tr": "Hesap oluştur",
    "en": "Create account"
  },
  "手工录入：交易": {
    "tr": "Elle giriş: Alım/satım",
    "en": "Manual entry: Trade"
  },
  "股票代码（例如 600519）": {
    "tr": "Hisse kodu (ör. THYAO.IS)",
    "en": "Stock code (e.g. THYAO.IS)"
  },
  "股票代码": {
    "tr": "Hisse kodu",
    "en": "Stock code"
  },
  "买入": {
    "tr": "Alış",
    "en": "Buy"
  },
  "卖出": {
    "tr": "Satış",
    "en": "Sell"
  },
  "数量（必填）": {
    "tr": "Adet (zorunlu)",
    "en": "Quantity (required)"
  },
  "成交价（必填）": {
    "tr": "İşlem fiyatı (zorunlu)",
    "en": "Trade price (required)"
  },
  "手续费（可选）": {
    "tr": "Komisyon (isteğe bağlı)",
    "en": "Commission (optional)"
  },
  "税费（可选）": {
    "tr": "Vergi (isteğe bağlı)",
    "en": "Tax (optional)"
  },
  "手续费和税费可留空，系统将按 0 处理。": {
    "tr": "Komisyon ve vergiyi boş bırakırsanız 0 kabul edilir.",
    "en": "Blank commission and tax values are treated as zero."
  },
  "提交交易": {
    "tr": "Hisse işlemini kaydet",
    "en": "Save trade"
  },
  "手工录入：资金流水": {
    "tr": "Elle giriş: Nakit hareketi",
    "en": "Manual entry: Cash movement"
  },
  "流入": {
    "tr": "Para girişi",
    "en": "Cash in"
  },
  "流出": {
    "tr": "Para çıkışı",
    "en": "Cash out"
  },
  "金额": {
    "tr": "Tutar",
    "en": "Amount"
  },
  "账户基准币": {
    "tr": "Hesabın temel para birimi",
    "en": "Account base currency"
  },
  "提交资金流水": {
    "tr": "Nakit hareketini kaydet",
    "en": "Save cash movement"
  },
  "手工录入：公司行为": {
    "tr": "Elle giriş: Şirket işlemi",
    "en": "Manual entry: Corporate action"
  },
  "现金分红": {
    "tr": "Nakit temettü",
    "en": "Cash dividend"
  },
  "拆并股调整": {
    "tr": "Bölünme/birleşme düzeltmesi",
    "en": "Split/consolidation adjustment"
  },
  "每股分红": {
    "tr": "Hisse başına temettü",
    "en": "Dividend per share"
  },
  "拆并股比例": {
    "tr": "Bölünme/birleşme oranı",
    "en": "Split/consolidation ratio"
  },
  "提交企业行为": {
    "tr": "Şirket işlemini kaydet",
    "en": "Save corporate action"
  },
  "券商 CSV 导入": {
    "tr": "Aracı kurum CSV dosyasını içe aktar",
    "en": "Import broker CSV"
  },
  "选择 CSV": {
    "tr": "CSV dosyası seç",
    "en": "Select CSV"
  },
  "仅预演（不写入）": {
    "tr": "Yalnızca önizleme (kayıt yapılmaz)",
    "en": "Dry run (no writes)"
  },
  "解析中...": {
    "tr": "İşleniyor...",
    "en": "Parsing..."
  },
  "解析文件": {
    "tr": "Dosyayı çözümle",
    "en": "Parse file"
  },
  "提交中...": {
    "tr": "Gönderiliyor...",
    "en": "Submitting..."
  },
  "提交导入": {
    "tr": "İçe aktarmayı kaydet",
    "en": "Commit import"
  },
  "CSV 解析结果": {
    "tr": "CSV ayrıştırma sonuçları",
    "en": "CSV parse results"
  },
  "CSV 预演结果": {
    "tr": "CSV deneme sonuçları",
    "en": "CSV dry-run results"
  },
  "CSV 提交结果": {
    "tr": "CSV içe aktarma sonuçları",
    "en": "CSV import results"
  },
  "预演检查": {
    "tr": "Deneme kontrolü",
    "en": "Dry-run check"
  },
  "实际写入": {
    "tr": "Gerçek kayıt",
    "en": "Actual write"
  },
  "事件记录": {
    "tr": "İşlem geçmişi",
    "en": "Transaction history"
  },
  "交易流水": {
    "tr": "Hisse işlemleri",
    "en": "Trades"
  },
  "资金流水": {
    "tr": "Nakit hareketleri",
    "en": "Cash movements"
  },
  "公司行为": {
    "tr": "Şirket işlemleri",
    "en": "Corporate actions"
  },
  "加载中...": {
    "tr": "Yükleniyor...",
    "en": "Loading..."
  },
  "刷新流水": {
    "tr": "İşlemleri yenile",
    "en": "Refresh transactions"
  },
  "按股票代码筛选": {
    "tr": "Hisse koduna göre filtrele",
    "en": "Filter by stock code"
  },
  "全部买卖方向": {
    "tr": "Tüm alış/satış işlemleri",
    "en": "All buy/sell directions"
  },
  "全部资金方向": {
    "tr": "Tüm nakit hareketleri",
    "en": "All cash directions"
  },
  "全部公司行为": {
    "tr": "Tüm şirket işlemleri",
    "en": "All corporate actions"
  },
  "删除修正仅在单账户视图可用。请先选择具体账户后再删除错误流水。": {
    "tr": "Silme yalnızca tek hesap görünümünde yapılır. Önce bir hesap seçin.",
    "en": "Deletion is available only in single-account view. Select an account first."
  },
  "如有错误流水，可直接删除后重新录入。": {
    "tr": "Hatalı işlemi silip yeniden kaydedebilirsiniz.",
    "en": "Incorrect entries can be deleted and re-entered."
  },
  "删除": {
    "tr": "Sil",
    "en": "Delete"
  },
  "暂无流水": {
    "tr": "Henüz işlem kaydı yok",
    "en": "No transaction records"
  },
  "调整筛选条件或先录入一笔交易、资金流水或公司行为。": {
    "tr": "Filtreleri değiştirin veya önce bir işlem kaydedin.",
    "en": "Adjust filters or enter a transaction."
  },
  "上一页": {
    "tr": "Önceki",
    "en": "Previous"
  },
  "下一页": {
    "tr": "Sonraki",
    "en": "Next"
  },
  "删除错误流水": {
    "tr": "Hatalı işlemi sil",
    "en": "Delete incorrect transaction"
  },
  "确认删除这条流水吗？": {
    "tr": "Bu işlemi silmek istediğinizden emin misiniz?",
    "en": "Are you sure you want to delete this transaction?"
  },
  "删除中...": {
    "tr": "Siliniyor...",
    "en": "Deleting..."
  },
  "确认删除": {
    "tr": "Silmeyi onayla",
    "en": "Confirm deletion"
  },
  "取消": {
    "tr": "İptal",
    "en": "Cancel"
  }
};

export function portfolioCopy(sourceText: string, language: UiLanguage): string {
  if (language === 'zh') return sourceText;
  return TRANSLATIONS[sourceText]?.[language] ?? sourceText;
}
