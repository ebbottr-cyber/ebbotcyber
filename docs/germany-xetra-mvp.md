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

## Yerel kabul kriterleri

1. GitHub frontend/backend/Windows SQLite testleri başarılı ve Draft PR yerinde kalır.
2. `SAP.DE` / `BMW.DE` ayrıştırıcı, saat dilimi ve Yahoo günlük yönlendirmesi yalnızca Almanya seçer; yanlış/eksik `.DE` kodları güvenle reddedilir.
3. ETRE Veri Merkezi beş ülkeyi gösterir; Japonya, Hong Kong, ABD ve Türkiye paneli korunur.
4. ETRE hisse araması `SAP.DE` gibi örnekleri Latin şirket adlarıyla gösterir; **SAP = Alman şirketi** diye otomatik yeniden yorumlanmaz.
5. Yerel Windows bilgisayarda yeni dal çekilir ve web `npm.cmd run build` ile yeniden derlenir. Yalnızca izole test API'si üzerinden açılır; henüz üretime dağıtılmaz.

**Not:** Liste yukarıdaki dört piyasa + Almanya için beşli **ETRE yatırım odağı**dır. Backend'deki daha geniş geçmiş piyasa sınıflandırması, analitik uyumluluk için silinmemiştir.
