# EBBot — Dört borsa fiyat sağlayıcısı ve seans boşluğu denetimi

**Durum: Salt-okunur, ağ erişimi olmayan, işlem yapmayan taslak.** PR #194 → PR #196 → PR #198 üzerine yığılmıştır. Gerçek fiyat, borsa takvimi veya lisans verisi otomatik olarak üretilmez.

## Ne yapıyor?

1. Türkiye/BIST, ABD, Almanya/Xetra ve Hong Kong aday hisselerinin tümünü (100 ile sınırlamadan) toplar. Mevcut `stocks.index.json`, Xetra adayları ve ayrıca sağlanan tarihli KAP/manifests okunur.
2. Operatörün sağladığı **gerçek ve tarihli borsa seansları** CSV'sini okur. Takvim yoksa eksik seans sayısı **`null` (bilinmiyor)** kalır; hafta içi/tatil kuralları uydurulmaz.
3. Aynı kod için sağlanan `provider`, `provider_symbol` ve `source_as_of_date` alanlarını, gerçek günlük OHLCV dosyasındaki sağlayıcı metaverileriyle karşılaştırır. Hatalı veya çakışan eşleme reddedilir.
4. OHLCV'nin geçerli fiyatlar ve tekil işlem günleri içerdiğini mevcut denetimden tekrar doğrular. Takvim aralığı içinde beyan edilmeyen bir günde işlem mumu varsa, mumun veya takvimin hatalı olabileceğini belirterek tüm denetimi durdurur.
5. Son en çok **20 beyan edilmiş seansı** (ayarlanabilir 1–60) tarayıp her aday kod için **potansiyel** eksik günleri sayar. Halka arz, kotasyondan çıkış, işlem durdurma ve kurumsal olaylar nedeniyle eksiklikler kesin veri kaybı kanıtı değildir.
6. Terminal yalnızca her piyasa için özet ve ilk 10 örneği gösterir. `--report-json` bütün adayların eksik olabilecek seans listesini **yalnız yerel yeni bir dosyaya** yazar; mevcut dosyayı ezmez.

**Önemli:** Bir CSV'de `source=official` veya `provider=xyz` yazılması, gerçek borsa takvimi, sembol eşleşmesi, fiyat lisansı ya da Türkiye'de işlem izni olduğunu ispatlamaz. Tüm doğrulama bayrakları `false`, durum daima `BLOCKED_REQUIRES_INDEPENDENT_MARKET_DATA_VALIDATION` olur.

## Örnek giriş biçimleri (tamamen şematik, piyasa verisi değildir)

Borsa seansları CSV (`market,session,source,source_as_of_date`):

```csv
market,session,source,source_as_of_date
us,2026-11-20,operator_reviewed_calendar,2026-11-20
```

Sağlayıcı-sembol eşlemesi CSV (`market,symbol,provider,provider_symbol,source,source_as_of_date`):

```csv
market,symbol,provider,provider_symbol,source,source_as_of_date
us,AAPL,example_provider,AAPL,operator_reviewed_mapping,2026-11-20
```

Gerçek OHLCV dosyaları önceki denetimdeki alanları (`market,symbol,session,open,high,low,close,volume,source,currency`) taşımalı; isteğe bağlı `provider,provider_symbol` alanları eklendiğinde bunlar eşleme dosyasıyla çapraz kontrol edilir.

**Örnekler yalnız dosya başlıklarını/alanlarını anlatır, gerçek zamanlı seans listesi veya sağlayıcı lisansı değildir.**

## Windows PowerShell komutları

Depo kök dizininden sadece mevcut stok indeksini, takvim yokken denetlemek:

```powershell
python -m scripts.audit_ebbot_equity_session_gaps
```

Operatörün önceden doğrulanmış ve sahip olduğu gerçek kaynaklar varsa:

```powershell
python -m scripts.audit_ebbot_equity_session_gaps --stocks "$HOME\EBBotPaperData\kap-bist-all.csv" --calendar "C:\ApprovedMarketData\sessions-2026.csv" --mapping "C:\ApprovedMarketData\provider-symbols.csv" --bars "C:\ApprovedMarketData\real-daily-ohlcv.csv" --report-json "C:\ApprovedMarketData\ebbot-session-gaps.json"
```

Dosyalar operatör bilgisayarında bulunmalı. Bu komut hiç veri indirmez. `--report-json` yeni dosya bekler. Özel piyasa fiyatlarını, sözleşmeleri veya kişisel abonelik bilgilerini herkese açık GitHub deposuna **yüklemeyin**.

## İzin ve tamamlanma kontrolü

- Çıkış `0`: denetim çalıştı; **borsa verisi tamamlandı anlamına gelmez**.
- Çıkış `1`: geçersiz veri, çelişen eşleme, hatalı OHLCV, bozuk takvim veya dosya hatası nedeniyle güvenli şekilde durdu.
- İki durumda da gerçek/sanal alım-satım ve zamanlanmış otomatik veri çekme **kapalı**.
- Gerçek piyasa seans takvimini ve broker sağlayıcı kimliğini bağımsız doğrulamak; yeni/halt olmuş/delist hisseler için doğru seans beklemelerini çözmek; veri lisanslarını denetlemek ayrı aşamalardır.
- Genel backend/React/Windows regresyonu ve ana dal birleştirme kapısı ayrıca bekler.

**Yayın: BLOKE.** Bu araçta “eksik gün” ifadesi yalnız *beyan edilmiş takvim ile gözlenen fiyat tarihleri arasındaki potansiyel fark* anlamına gelir.

## Xetra kaynak bütünlüğü PR #194 ile eşitlendi

Seans boşluğu denetimi ve yerel OHLCV staging, Xetra aday dosyasının kimliğini artık dört-piyasa denetimiyle **aynı ham dosya baytlarından** SHA-256 hesaplayarak kontrol eder. UTF-8 BOM, LF/CRLF değişikliği veya symlink kaynak engellenir. Bu düzeltme bir finansal veri lisansı, fiyat geçmişi ya da veri sağlayıcısı sembolü doğrulaması değildir. Kaynak güvenlik kontrolleri eksikse denetim güvenli şekilde durur; emir, scheduler ve yayın hâlâ kapalıdır.
