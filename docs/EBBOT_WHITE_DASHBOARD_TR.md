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
