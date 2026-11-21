# EBBot — Elle sağlanan fiyat geçmişini güvenli içeri alma (salt-okunur ön aşama)

**Yayın durumu: BLOKE.** Bu adım, kendi veri sağlayıcınızdan elde ettiğiniz ve kullanım hakkınızı ayrıca kontrol ettiğiniz günlük OHLCV CSV dışa aktarımını yerel alanda doğrulayıp denetim formatına dönüştürür. Bu komut **borsaya bağlanmaz**, abonelik satın almaz, gerçek lisansı doğrulamaz, API anahtarlarını kullanmaz, botu eğitmez, paper veya gerçek alım-satım açmaz.

## Yapılan kontrol

- **SHA-256:** Sağlayıcıdan gelen ham dosya, ayrı hazırlanan manifestteki özetle bit düzeyinde eşleşmeli.
- **Kaynak kaydı:** Piyasa, sağlayıcı kimliği, para birimi, kaynak etiketi, dışa aktarım tarihi ve operatörün kurum içi inceleme referansı açıkça tanımlı olmalı. Referans **lisansın gerçekliğinin kanıtı değildir**.
- **Hisse kodu:** Kayıt, seçilmiş dört piyasadan (`tr`, `us`, `de`, `hk`) birinde bulunmalı; ayrı `mapping.csv` içindeki gerçek sağlayıcı sembolüyle uyuşmalı.
- **Piyasa takvimi:** Ayrı `calendar.csv` içindeki beyan edilmiş seanslardan olmayan hiçbir fiyat tarihi kabul edilmez. Bu takvim dosyasının gerçek borsa takvimi olduğu ayrıca doğrulanmalıdır.
- **OHLCV kalitesi:** Açılış/en yüksek/en düşük/kapanış/hacim tutarlılığı, sıfır veya negatif fiyatlar, NaN/sonsuz değerler, tekrar eden kod-tarih ve geleceğe taşan kayıtlar reddedilir.
- **İzolasyon:** Girdi başına 64 MiB sınırı vardır; daha büyük arşivleri parçalara ayırıp tekrarlayın. Veriler botun canlı analizi, veritabanı veya işlem motoruna otomatik aktarılmaz. Her parça açıkça belirtilen, **henüz bulunmayan yerel** çıktı dosyasına yazılır.

## Üç dosya ve tek komut

1. Sağlayıcının gerçek günlük veri dışa aktarımını kendi Windows bilgisayarınızda saklayın. Gerekli CSV başlıkları:

```csv
market,symbol,session,open,high,low,close,volume,source,currency,provider,provider_symbol
```

**Gerçek fiyat satırları bu belgede bilerek yoktur.** Kaynak, sağlayıcı ve sözleşme koşullarını üçüncü kişilere açık GitHub deposuna koymayın.

2. Sağlayıcı kimliği ile sözleşme inceleme takip kodunu (sır veya API anahtarı değil) tanımlayan **yerel** `provider.json` hazırlayın:

```json
{
  "schema_version": 1,
  "market": "us",
  "provider": "your_vendor",
  "source": "approved_export",
  "currency": "USD",
  "source_as_of_date": "2026-11-21",
  "input_sha256": "REPLACE_WITH_ACTUAL_64_CHARACTER_LOWERCASE_SHA256",
  "license_review_reference": "INTERNAL-123"
}
```

Bu şema örneğidir. Kimlikleri ve gerçek tarihi değiştirin. `license_review_reference`, operatörün izlemesine yarayan **metin etiketidir**, sözleşme hakkı otomatik doğrulanmaz. `source_as_of_date` UTC ve CSV'deki tüm fiyat seanslarının sonrasında olmalıdır.

3. Hash'i PowerShell ile öğrenin:

```powershell
(Get-FileHash "C:\ApprovedMarketData\real-daily.csv" -Algorithm SHA256).Hash.ToLowerInvariant()
```

Bu değeri manifestteki `input_sha256` alanına girin. Daha sonra önceden gerçek kaynaklarla hazırlanmış `calendar.csv` ve `mapping.csv` dosyalarını da ekleyerek çalıştırın:

```powershell
python -m scripts.stage_ebbot_equity_ohlcv --input-csv "C:\ApprovedMarketData\real-daily.csv" --manifest "C:\ApprovedMarketData\provider.json" --mapping "C:\ApprovedMarketData\mapping.csv" --calendar "C:\ApprovedMarketData\calendar.csv" --output-csv "C:\ApprovedMarketData\staged-ohlcv-01.csv"
```

`mapping.csv` başlığı:

```csv
market,symbol,provider,provider_symbol,source,source_as_of_date
```

`calendar.csv` başlığı:

```csv
market,session,source,source_as_of_date
```

**Çıkış `0`** yalnız doğrulama kapılarından geçen yerel dosyanın hazırlandığını söyler. `license_verified=false` ve `full_exchange_coverage_verified=false` olarak kalır. **Çıkış `1`** güvenli ret veya dosya hatasıdır; fiyatlar ve kullanıcı yolları konsolda yayınlanmaz.

## Sonraki çevrimdışı kontroller

Onaylı, elle oluşturulan staged dosyalarını önceki denetimlere geçin:

```powershell
python -m scripts.audit_ebbot_market_data_coverage --bars "C:\ApprovedMarketData\staged-ohlcv-01.csv" --report-json "C:\ApprovedMarketData\coverage-new.json"
python -m scripts.audit_ebbot_equity_session_gaps --bars "C:\ApprovedMarketData\staged-ohlcv-01.csv" --calendar "C:\ApprovedMarketData\calendar.csv" --mapping "C:\ApprovedMarketData\mapping.csv"
```

Bu örnekler, yalnız veri içindeki hisse kodları zaten envanterde bulunuyorsa çalışır. BIST için ayrıca `--stocks "$HOME\EBBotPaperData\kap-bist-all.csv"` geçmeniz gerekebilir. Aynı gün için birden fazla veri dosyasında tekrar eden bar varsa sonraki denetim hata verir; veri değişikliği için kontrollü yeni bir sürüm oluşturun.

Panelin mevcut veri özeti, operatörün üretip tanımladığı `EBBOT_EQUITY_COVERAGE_REPORT_PATH` dosyasını okur; **fiyat geçmişini veya kaynak sözleşmelerini API üzerinden sunmaz**. Takvim/sağlayıcı kimliği boşluk raporunun panele bağlanması farklı bir inceleme adımıdır.

**İzin ve uyumluluk:** Buradaki `approved_export` veya `your_vendor` örnek adları herhangi bir veri firmasından satın alma/çekme hakkınız olduğunu göstermez. Güncel hizmet koşulları, tarihsel veri lisansı, aktarım/önbellekleme izni, Türkiye'de erişim, işlem saatleri ve sembol eşlemesini doğrudan sağlayıcıyla veya yetkili aracı kurumla doğrulamak gerekir.

**Emir ve otomatik veri indirme: Kapalı.** Taslak PR'lardan ana dal birleştirmesi ve Windows dağıtımı yapılmamıştır.
