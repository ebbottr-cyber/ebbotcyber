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
