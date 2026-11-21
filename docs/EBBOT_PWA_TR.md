# EBBot PWA — Test Dalı

Mevcut React/Vite tabanlı EBBot sitesine yüklenebilir uygulama kimliği ve simgeleri ekler. Bu ilk aşama anasayfa tasarımını yeniden çizmez.

## Yapılanlar
- Türkçe EBBot manifesti, iPhone Apple Touch Icon, 192/512 px Android ikonları ve maskable ikon.
- Açık (beyaz) tema yeni kullanıcıların varsayılanıdır; kayıtlı koyu tema tercihleri korunur.
- Üretimde, güvenli bağlamda HTTPS/localhost servis işçisi kaydı.
- Çevrimdışı durumda sadece herkese açık uyarı sayfası.
- Servis işçisi özel rapor, oturum, API, piyasa, portföy ve işlem verilerini kesinlikle önbelleğe almaz.
- Otomatik işlem / model değiştirme, mevcut API ve analiz motoru değiştirilmez.
- Bildirim gönderme altyapısı bu sürüme dahil değildir.

## Test
```bash
cd apps/dsa-web
npm ci
npm run test:pwa
npm run build
PWA_REQUIRE_BUILD=1 npm run test:pwa
```

iPhone: HTTPS adresi Safari'de aç > Paylaş > Ana Ekrana Ekle.
Android: HTTPS adresi Chrome'da aç > Uygulamayı yükle / Ana ekrana ekle.
Yerel LAN HTTP adresleri servis işçisi açısından güvenli bağlam değildir; localhost istisnadır.

**Önemli:** Bu daldaki dosyalar birleştirilip sunucuya alınmadıkça telefona kurulacak üretim sürümü hazır değildir. Anasayfanın seçilen beyaz referans görsele birebir uyarlanması sonraki ayrı UI çalışmasıdır.
