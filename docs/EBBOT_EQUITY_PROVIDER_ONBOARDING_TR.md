# EBBot — Dört hisse piyasası için resmî fiyat kaynağı ve kullanım hakkı denetimi

**Durum: İNCELEME / KAYNAK BAĞLANMADI / İŞLEM KAPALI.** Bu geliştirme ürün seçeneklerini listeler ve operatör beyanını denetler. Veri lisansı satın almaz, sözleşmenin gerçekliğini doğrulayamaz, hiç fiyat indirmez. GitHub üzerinde API anahtarı, sözleşme veya fiyat geçmişi bulunmaz.

## Resmî kaynak seçenekleri (21 Kasım 2026 araştırması)

| Piyasa | Görüşülebilecek resmî ürün veya kanal | Sözleşme kontrolü |
|---|---|---|
| **Türkiye / BIST** | [Borsa İstanbul DataStore tarihsel veri](https://www.borsaistanbul.com/en/data/historical-data-sales), [lisanslı dağıtıcılar](https://borsaistanbul.com/en/data/data-dissemination/data-vendors-directory) | BIST şirket/hisse listesi, geçmiş gün sonu fiyatları, algoritmik analiz, saklama ve otomatik erişim hakkı ayrı sorulmalı |
| **ABD** | [Nasdaq Data Link Bars API](https://www.nasdaq.com/products/data/data-link/api), [NYSE Daily TAQ](https://www.nyse.com/data-products/catalog/daily-taq) | İlgili abonelikte Nasdaq+NYSE+diğer borsalar kapsamı; TAQ işlemlerinden OHLCV dönüştürme, kurumsal olay ve ticari kullanım koşulları doğrulanmalı |
| **Almanya / Xetra** | [Deutsche Börse Historical Data](https://www.mds.deutsche-boerse.com/mds-en/historical-data) | XETR işlem yeri ve ISIN/fiyat sembolü eşlemesi, tarihsel seri ve yerel saklama hakkı sorulmalı |
| **Hong Kong** | [HKEX Data Marketplace](https://www.hkex.com.hk/Services/Market-Data-Services/Historical-Data-Services/HKEX-Data-Marketplace?sc_lang=en) | Seçilen ürünün gerçek günlük OHLCV alanları, tüm işleme açık hisseler, takvim, otomatik kullanım ve yeniden dağıtım hakkı kontrol edilmeli |

**Bunlar onaylı/bağlanmış tedarikçi listesi değil, resmî ürün araştırma adaylarıdır.** Bir ürünün ilan edilmesi EBBot için sözleşme, otomatik algoritmik işlem hakkı veya API erişimi vermez. Fiyat, tarife veya erişim hakkı bu PR'da uydurulmadı.

## Kodun denetlediği kayıt

Operatör her piyasa için sözleşme incelemesini ve kullanım kapsamını **yerel, gizli olmayan** bir JSON dosyasında işaretleyebilir. Dosyada API anahtarı, hesap numarası, kimlik bilgisi, sözleşme PDF'si, kişisel veri veya fiyat bulunmamalıdır.

Başlangıçta `data/market_sources/operator_provider_review.sample.json` şu şekilde **boştur**:

```json
{"schema_version": 1, "markets": {}}
```

İncelenmekte olan **tek** piyasa için `markets` içine aşağıdaki şemayı ekleyin; aşağıdaki tüm `false` işaretleri kasıtlıdır:

```json
{
  "schema_version": 1,
  "markets": {
    "tr": {
      "provider_reference": "TBD-PROVIDER-01",
      "product_reference": "TBD-PRODUCT-01",
      "assessment_ticket": "INTERNAL-REVIEW-001",
      "reviewed_utc_date": "2026-11-21",
      "access_expires_utc_date": "2026-11-21",
      "rights_claimed": {
        "historical_daily_ohlcv": false,
        "non_display_internal_research": false,
        "local_caching_and_retention": false,
        "automated_algorithmic_analysis": false
      },
      "checks_claimed": {
        "contract_terms_reviewed_by_authorized_person": false,
        "sample_export_obtained_by_authorized_person": false,
        "exchange_ticker_mapping_reviewed": false,
        "exchange_session_calendar_reviewed": false
      }
    }
  }
}
```

**Dikkat:** `true` yazılması bile lisansı doğrulamaz. Bu yalnızca operatörün bir kontrolü yaptığını beyan eder. Gerçek sözleşme hükümlerini yetkili kişi ayrıca teyit etmelidir. Tarihleri gerçek inceleme ve erişim süresine göre girin. 30 günü aşan inceleme, süresi biten erişim, eksik hak ve yanlış kaynak biçimi uyarı veya güvenli ret oluşturur.

## Komutlar

GitHub'daki kaynak ürün adayları ve eksik kanıtlar:

```powershell
python -m scripts.audit_ebbot_equity_provider_readiness
```

Onay aşamasındaki yerel kayıtla:

```powershell
python -m scripts.audit_ebbot_equity_provider_readiness --review "C:\ApprovedMarketData\provider-review.json"
```

**Çıkış `0`:** rapor üretildi demektir; hiçbir piyasanın verisi veya hakkı onaylanmış değildir. `BLOCKED_NOT_APPROVED_FOR_DATA_INGESTION_OR_TRADING` durumu daima korunur. **Çıkış `1`:** şema veya kaynak denetimi reddedilmiştir. Kişisel yollar ve yerel referans kimlikleri terminalde gösterilmez.

## Gerçek OHLCV yüklemesi için eksik bağımlılıklar

1. Her piyasa için satın alma/erişim yöntemi ve ülkenizdeki sözleşme şartlarını yetkili kişiyle doğrulayın.
2. Sağlayıcının gerçekten günlük OHLCV, kapsamlı aktif hisse listesi, geçmiş kurumsal olaylar ve seans takvimi sağladığını örnek çıktıyla test edin.
3. BIST için KAP şirket kodlarından işleme açık sembollere kesin eşleme ve BIST fiyat verisi hakkını; Xetra için ISIN/XETR kodunu; ABD ve Hong Kong için çoklu piyasa/delist kimliklerini doğrulayın.
4. Sözleşmeye uygun veri örneğini **özel yerel bilgisayarda** hazırlayıp PR #200'deki SHA-256 korumalı `stage_ebbot_equity_ohlcv` aracından geçirin. Veri sağlayıcının gizli ham dosyalarını herkese açık GitHub'a yüklemeyin.
5. Bütün fiyatlar ve işlem günleri PR #194/#199 denetimlerinden geçtikten sonra Veri Merkezi'ne yalnız agregat, kısıtlı raporunu bağlayın.

**Dikkat:** Bu kaynak uygunluk kontrolü, işlem algoritmasını/veri çekme zamanlayıcısını/gerçek veya sanal emirleri açmaz. PR taslaktır, main'e birleştirilmedi ve dağıtım izni verilmedi.
