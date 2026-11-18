# EBBot beyaz panel — ilk ekran

Bu aşamada mevcut `/` analiz çalışma alanına, `/overview` adresinden açılan duyarlı (mobil/masaüstü) beyaz finans özeti eklenir. Henüz varsayılan giriş ekranı değildir; karşılaştırma ve test amacıyla ayrı tutulur.

- Referans görseldeki beyaz/mavi stil: üst piyasa kartları, hisse analizi, portföy, risk, takip listesi, haberler, AI görev akışı ve uyarılar.
- Fiyatlar uydurulmaz. Türkiye kartları yalnızca `/api/v1/data/tr-market-overview` kaynağından gelen doğrulanmış ve tarihli gecikmeli fiyatları kullanır; aksi halde "—" gösterilir.
- Hisse grafiği günlük OHLC verisi varsa gerçek mumları kullanır; kaynak yoksa etiketli analiz kayıtlarına döner. Canlı veri iddiası yoktur.
- Portföy ve risk alanları mevcut API'lerden, haberler analiz geçmişinden, uyarılar ve görevler mevcut endpoint'lerden beslenir.
- Tek panelde kısmi hata gösterimi ve manuel yenileme vardır.
- Mevcut analiz, risk, portföy, backend, otomatik işlem ve PWA güvenlik davranışı değiştirilmez.
- Mobilde yatay piyasa kartları ve alt hızlı gezinme bulunur.

## Doğrulama
```bash
cd apps/dsa-web
npm ci
npm run build
npm run test:pwa
```
Gerçek cihazda iPhone Safari ve Android Chrome üzerinden PWA ve responsive kontrolü ayrıca yapılmalıdır.

## Gerçek mum grafiği — V2
- Mevcut, salt-okunur \`GET /api/v1/stocks/{stock_code}/history\` API'sine bağlanan OHLC ve hacim grafiği eklendi.
- Yalnızca sunucunun desteklediği günlük dönem kullanılır. 1A / 3A / 6A / 1Y butonları sırasıyla 30 / 90 / 180 / 365 günlük sorgu yapar; gün içi veri uydurulmaz.
- Geri dönüşte fiyatlar ve OHLC tutarlılığı doğrulanır, tekrar eden günler ayıklanır; API başarısızsa mevcut rapor fiyat geçmişi açık etiketle gösterilir.
- Mobil grafikte yatay kaydırma, en yeni güne doğru başlangıç ve dokunma/klavye ile erişilebilen açıklamalar vardır.
- Eski analiz/portföy/risk motorları değiştirilmez; yeni UI hâlen \`/overview\` altındadır.
- Candlestick birim ve bileşen testleri CI'a eklendi. Gerçek cihaz ve servis verisi entegrasyon testi sonraki aşamadır.

## Türkiye piyasa kartları — V3
- BIST 100: `XU100.IS`; BIST 30: `XU030.IS`; USD/TRY: `TRY=X`; EUR/TRY: `EURTRY=X`. Kaynak: Yahoo Finance günlük fiyat serileri (gecikmeli, anlık kotasyon değil).
- Yeni salt-okunur endpoint: `GET /api/v1/data/tr-market-overview`. Sunucu tarafı 300 saniye önbellek, sembol listesini kullanıcı değiştiremez; dört fiyat sorgusu eşzamanlıdır.
- Piyasa kartlarında kaynağın veri günü gösterilir. Eski, negatif, sıfır, NaN, gelecekteki veya getirilemeyen fiyatlar **hiçbir koşulda gösterilmez**. USD/TRY ve EUR/TRY daha hassas dört ondalıkla görüntülenebilir.
- Gram altın (TRY/gram) için doğrulanmış spot/yerel veri kaynağı henüz bulunmadığından **fiyat boş tutulur**. Vadeli ons altınla uydurma TL/gram fiyat üretilmez.
- Piyasa raporu içindeki CN/HK/US endeksleri Türkiye verisi yerine kullanılamaz. Bu yanlış eşleştirme kaldırıldı.
- Mobilde piyasa kartları yatay kaydırılır; klavye ile de erişilebilir. Bileşen testleri bu davranışı ve boş durumları doğrular.
- Üretimde finansal verinin yeniden yayımlanması için Yahoo Finance ve/veya seçilen lisanslı veri sağlayıcısının kullanım koşulları ayrıca doğrulanmalıdır.
- API tarafı ek paket yüklemeden koşan izole Python offline güvenlik testlerine sahiptir.
- PR henüz **taslaktır** ve `main` dalına birleştirilmedi; gerçek veri sağlayıcı ve gerçek iPhone/Android kontrolleri henüz yapılmadı.


## Mobil tarayıcı kontrolleri — V4
- Tarayıcı otomasyonu için sahte/izole API yanıtları kullanılır; portföy, piyasa ve analiz test fiyatları kesinlikle canlı veriler değildir.
- Chromium mobil emülasyonunda 320, 390, 430, 768, 1440 px ekran genişliği kontrol edilir; sayfa yatay taşma, üst/alt gezinme, eksik veri, API hatası ve salt-okunur erişim doğrulanır.
- Uygulama içinde kaydedilmiş veriler yenileme sırasında güncelmiş gibi gösterilmez.
- Bu testler **gerçek iPhone Safari veya Android cihaz testi değildir**. Gerçek cihazlarda PWA kurulumu, ekran klavyesi, safe-area ve gezinme ayrıca denetlenmelidir.

## Teknik gösterge panosu — V5
- Kullanıcının referans görselindeki teknik analiz paneline benzer, mum grafiğinin yanındaki RSI(14), MACD(12/26/9), EMA(20) ve EMA(50) kartı hazırlandı.
- Göstergeler yalnızca **ekranda çizilen aynı günlük kapanış serisinden** hesaplanır; yeni veri isteği ve ek API ücreti yoktur.
- RSI için 15, MACD sinyali için 34, EMA20 için 20, EMA50 için 50 kapanış gerekir. Daha az veri varsa `—` gösterilir.
- Alım/satım kararı veya risk puanı uydurulmaz. Grafik hata verdiğinde teknik panel kapatılır.
- Testler düz fiyat, tek yönde fiyat, eksik/NaN fiyat ve kısa serileri kapsar. Mobil görünümde teknik panel grafik altına yerleşir.

## Beyaz panel özet kartları — V6
- Portföyde özsermaye, nakit, pozisyon değeri ve mümkün olduğunda nakit yüzdesi ayrı gösterilir; `fxStale` veya kısmi değerleme durumunda uyarı korunur.
- Risk özeti yalnızca API ölçümlerini gösterir. Eksik/NaN değerler sıfır risk gibi çizilmez ve genel güvenlik puanı icat edilmez.
- Takip listesinden seçilen sembol beyaz paneldeki grafiği değiştirir; analiz raporu yoksa hisse geçmişi API'si kullanılabilir, fiyat yoksa açık boş durum korunur. Takip listesi fiyatları yalnızca kayıtlı analiz değerleridir, canlı değildir.
- AI analiz görevleri durumu Türkçeye çevrilir; yüzde yalnızca çalışan görevlerde, 0–100 aralığında görüntülenir. Başarısız görevlere başarılı etiketi verilmez.
- Veri yenilenirken ve API başarısızlığında önceki portföy, risk veya görev bilgileri güncelmiş gibi gösterilmez.
- 9 birim testi ve mobil Chromium senaryosu eklendi. API tabanında yeni işlem/emir endpoint'i yoktur.
