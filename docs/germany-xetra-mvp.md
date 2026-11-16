# Almanya (Xetra) — ETRE beşinci piyasa, taslak entegrasyon

**Kapsam:** Kullanıcının seçtiği beş yatırım odaklı piyasa Türkiye (BIST), ABD, Almanya (Xetra), Hong Kong ve Japonya'dır. Bu bir **ETRE görünüm/analiz kapsamı** değişikliğidir; Midas veya başka bir aracı kurum üzerinden gerçek emir gönderme entegrasyonu değildir.

## Kaynak ve kod kuralları

- Midas, Almanya Xetra erişimini resmi yatırım rehberinde listeliyor: https://www.getmidas.com/destek/midas-ile-yatirima-baslarken/midas-ile-neler-yapabilirim/midas-yatirim-hesabin-ile-hangi-yatirimlari-yapabilirsin/
- Yahoo Finance listesinde Deutsche Boerse XETRA = **.DE** ve gecikmeli fiyat bilgisi: https://uk.help.yahoo.com/kb/exchanges-markets-covered-yahoo-finance-sln2310.html
- Hisse girişleri açık `TICKER.DE` biçimindedir: `SAP.DE`, `BMW.DE`, `VOW3.DE`. **SAP** gibi çıplak kısaltmalar Almanya olarak otomatik yorumlanmaz. Endeksler veya belirsiz kodlar için bu hisse yolu kullanılmaz.
- Bölge `de`, temel fiyat para birimi **EUR**, IANA saat dilimi **Europe/Berlin** ve `exchange_calendars` takvimi **XETR**'dir.
- `YfinanceFetcher`, ilk taslakta günlük fiyat için tek yetkili kaynak olarak kullanılır; Çin/Hong Kong/ABD üzerinden yanlış kaynak devri yapılmaz. Para birimi, fiyatların tamlığı ve güncelliği bağımsız canlı test olmadan doğrulanmış sayılamaz.
- Veri Merkezi'nde kaynak uygunluğu görünür, **canlı Xetra fiyatı, bütün hisse evreni, aracı kurum yetkisi veya otomatik alım-satım doğrulanmış sayılmaz**.
- ETRE hisse aramasına eklenen kısa Xetra listesi yalnızca **örnek arama rehberidir**; tüm Xetra listesi veya Midas'ta bu kodların tek tek işlem açılabildiği taahhüdü değildir.

## Bilinçli olarak dışarıda tutulanlar

- Almanya'nın piyasa toplu değerlendirme seçicisine eklenmesi: mevcut `MarketReviewRegion` backend sözleşmesi `de` kabul etmiyor; desteklenmeyen toplu analiz düğmesi gösterilmeyecek. Tekil .DE hisseleri için analiz yolu ayrı.
- Gerçek Midas emir bağlantısı, hesaba özel pazar izinleri, emir gönderme, canlı portföy, komisyon ve vergi hesapları.
- Almanya temel verileri ve gerçek zamanlı piyasa kapsamı için ayrı doğrulama gereklidir. Desteklenmeyen temel veri için Çin A hissesi verisine sessiz geçiş yapılmaz.
- Çin, Kore ve Tayvan yatırım görünümünde gizli kalır; eski kodlar, geçmiş veriler ve regresyon testleri silinmez.


## Üç Alman hissesi için ayrı canlı test kapısı

İlk kontrol `SAP.DE` ile **252 günlük OHLCV kaydı**, **EUR** ve **2026-11-13** son tamamlanan Xetra seansı üzerinden başarıyla çalıştı (2026-11-16, [GitHub Actions #43843905485](https://github.com/ebbottr-cyber/ebbotcyber/actions/runs/43843905485)). Bu yalnızca bir hisse için geçmiş fiyat ve teknik analiz doğrulamasıdır; alış/satış sinyali veya Midas işlem izni değildir.

İkinci kontrol `src.services.germany_xetra_basket_smoke` ile **SAP.DE**, **SIE.DE** ve **BMW.DE** örneklerini **tek tek** kontrol eder. Her hisse için geçerli OHLCV, en az 60 gün fiyat, EUR kur etiketi, son Xetra işlem gününe kadar güncellik, doğru `de` kod yönlendirmesi ve teknik puan ayrı ayrı gereklidir. Bir hisse başarısızsa tüm kapı başarısız olur; başarılı iki hisse üçüncünün eksiğini gizleyemez. Dış servis hataları JSON'da hisse bazında bırakılır.

GitHub'daki `germany-xetra-basket-live-yahoo` işi, temel `germany-xetra-live-yahoo` başarılı olduktan sonra çalışır; raporlar geçici Actions artifact'ı olarak saklanır. Bu işlem **yalnızca salt-okunur** bir kontrol olup SQLite'a yazmaz, API anahtarı istemez ve gerçek işlem yapmaz.

Çalıştırma örneği (Python ortamı yapılandırılmışsa):

```bash
python -m src.services.germany_xetra_basket_smoke --as-of 2026-11-15 --output xetra-basket.json
```

Üç hisseyle başarıya ulaşmak bile bütün Xetra evreninin, anlık veri lisansının, aracı kurum alım-satım izninin veya ETRE içinden emir gönderme işlevinin tamamlandığını kanıtlamaz.

## Yerel kabul kriterleri

1. GitHub frontend/backend/Windows SQLite testleri başarılı ve Draft PR yerinde kalır.
2. `SAP.DE` / `BMW.DE` ayrıştırıcı, saat dilimi ve Yahoo günlük yönlendirmesi yalnızca Almanya seçer; yanlış/eksik `.DE` kodları güvenle reddedilir.
3. ETRE Veri Merkezi beş ülkeyi gösterir; Japonya, Hong Kong, ABD ve Türkiye paneli korunur.
4. ETRE hisse araması `SAP.DE` gibi örnekleri Latin şirket adlarıyla gösterir; **SAP = Alman şirketi** diye otomatik yeniden yorumlanmaz.
5. Yerel Windows bilgisayarda yeni dal çekilir ve web `npm.cmd run build` ile yeniden derlenir. Yalnızca izole test API'si üzerinden açılır; henüz üretime dağıtılmaz.

**Not:** Liste yukarıdaki dört piyasa + Almanya için beşli **ETRE yatırım odağı**dır. Backend'deki daha geniş geçmiş piyasa sınıflandırması, analitik uyumluluk için silinmemiştir.
