# ETRE — Beş piyasa için salt-okunur örnek veri kapsamı (taslak)

**Kullanıcıya görünen yatırım kapsamı:** Türkiye (BIST), ABD, Almanya (Xetra), Hong Kong, Japonya. Çin, Güney Kore ve Tayvan'ın eski veri/analiz kodları silinmeden yatırım görünümünden gizlenir.

Bu modül bir **örnek veri sağlığı kontrolüdür**, kapsamlı borsa tarayıcısı değildir. Gerçek para, aracı kurum hesabı, işlem emri, SQLite yazımı veya LLM kullanmaz.

## Çalışma kapsamı

| Piyasa | Temel örnek | İkinci örnek | Beklenen para birimi |
|---|---|---|---|
| Türkiye | `THYAO.IS` | `ASELS.IS` | TRY |
| ABD | `AAPL` | `MSFT` | USD |
| Almanya | `SAP.DE` | `SIE.DE` | EUR |
| Hong Kong | `HK00700` → `0700.HK` | `HK01810` → `1810.HK` | HKD |
| Japonya | `7203.T` | `6758.T` | JPY |

`core` = 5 piyasada birer hisse, `expanded` = 5 piyasada ikişer hisse (10 toplam). `--symbols` seçeneği, kullanıcının belirlediği **1–50 hisse koduyla** aynı güvenli kontrolü yapar. Girişte bütün kodlar önce doğrulanır; desteklenmeyen piyasa, endeks, boş/tekrar eden veya hatalı kod veri çekilmeden reddedilir. Girilmemiş piyasalar `not_requested` gösterilir. Alman SAP için `SAP.DE` gereklidir; çıplak `SAP` farklı bir ABD kodu olarak değerlendirilir. Fiyatlar Yahoo'dan alınır; her örnek için piyasa ve Yahoo kod eşleşmesi, en az 60 geçerli günlük OHLCV kaydı, son tamamlanan seans, para birimi ve mevcut teknik analiz puanı kontrol edilir. Bir hissede sorun çıkarsa durumu saklanmaz.

Rapor `checked_symbols`, `analyzed_symbols`, `markets_checked`, `results` ve `by_market` alanlarını içerir. Piyasa bazındaki `sample_status`, yalnızca seçilmiş **örneklerin** geçtiğini (`samples_passed`), kısmen geçtiğini (`partial`) veya hiçbirinin geçmediğini (`samples_failed`) gösterir; bütün borsa veya bütün hisseler hakkında kesin bir sağlık iddiası değildir.

## Çalıştırma (izole ve manuel)

```powershell
cd "$env:USERPROFILE\Projects\ebbotcyber-test"
& ".\.venv\Scripts\python.exe" -m pytest -q tests/test_five_market_sample_validation.py
& ".\.venv\Scripts\python.exe" -m src.services.five_market_sample_validation --sample-set core --as-of 2026-11-15 --output "$env:TEMP\etre-five-market-core.json"
# Daha geniş kontrol yalnızca gerektiğinde, salt-okunur:
& ".\.venv\Scripts\python.exe" -m src.services.five_market_sample_validation --sample-set expanded --as-of 2026-11-15 --output "$env:TEMP\etre-five-market-expanded.json"
# Özel 5-piyasa hisse listesi (yalnızca okuma)
& ".\.venv\Scripts\python.exe" -m src.services.five_market_sample_validation --symbols "THYAO.IS,AAPL,SAP.DE,HK00700,7203.T" --as-of 2026-11-15 --output "$env:TEMP\etre-custom-symbols.json"
```

GitHub'da taslak PR #11 için `five-market-core-live-yahoo` işi, başarılı Almanya 3-hisse testinden sonra çalışır ve geçici JSON artifact üretir. Ağ hataları veya geçici veri eksiklikleri başarısızlık olarak kaydedilir, gizlenmez.

**Henüz yapılmayanlar:** tüm borsa sembol evreninin içe aktarılması; otomatik düzenli 5-piyasa taraması; market-wide sıralama; veri kalitesinin ETRE panelinde kalıcı/doğrulanmış olarak gösterilmesi; Midas dahil aracı kurum bağlantısı, işlem izni, alım-satım ve emir gönderme. Bunlar ayrı geliştirme ve onay kapıları gerektirir.
