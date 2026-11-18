# EBBot beyaz panel — ilk ekran

Bu aşamada mevcut `/` analiz çalışma alanına, `/overview` adresinden açılan duyarlı (mobil/masaüstü) beyaz finans özeti eklenir. Henüz varsayılan giriş ekranı değildir; karşılaştırma ve test amacıyla ayrı tutulur.

- Referans görseldeki beyaz/mavi stil: üst piyasa kartları, hisse analizi, portföy, risk, takip listesi, haberler, AI görev akışı ve uyarılar.
- Fiyatlar uydurulmaz. BIST/döviz/altın kartları yalnızca kayıtlı piyasa raporunun eşleşen veri alanlarını kullanır; aksi halde "—" gösterilir.
- Hisse fiyat geçmişi yalnızca kayıtlı analiz raporlarından çizilir; mum grafik ya da canlı veri iddiası yoktur.
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
