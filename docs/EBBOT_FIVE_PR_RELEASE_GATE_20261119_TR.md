# EBBot — 19 Kasım 2026, beş PR entegrasyonu yayın öncesi inceleme

**Karar: PRODUCTION / MAIN YAYINI ONAYLANMADI.**
Bu dosya yalnızca bir kod ve CI değerlendirmesi. Gerçek emir, sanal fill,
zamanlayıcı, piyasa verisi API'sine toplu sorgu, sunucu dağıtımı veya `main`
birleştirmesi başlatılmaz.

## 1. Beklenen ve henüz birleştirilmemiş taslak zincir

| Sıra | PR | Branch | Denetlenen head |
| --- | --- | --- | --- |
| 1 | #57 | `review/ebbot-3lu-entegrasyon-20261118` | `61ff4630e63941acd3b75ce5350eac81f8530f53` |
| 2 | #58 | `feat/all-markets-paper-universe-v1` | `f943f02403c010a156dd0d26438e783e07b5fd32` |
| 3 | #59 | `feat/four-market-equity-audit-v1` | `89ad671fe686ab5ae084745fd5d8af26a96bc02c` |
| 4 | #62 | `feat/xetra-quote-guard-v1` | `da5b666cefa538c9c8f6d734158a387aae126cc2` |
| 5 | #64 | `feat/xetra-dashboard-readonly-v1` | `212516234bd5c2bb8ccc48caa58b17b388a691e8` |

Anlık `main`: `2aade1eb43489483f3e18c1e04cb8d0849cf4900`.
Değişirse bu rapordaki topoloji kontrolü yeniden çalıştırılmalı.
Her PR kendi güncel üst dalından sıfır commit geridedir ve GitHub
`mergeable=true` bildirmiştir. Bu yalnızca birleştirme çatışması yok demektir,
**yayın yetkisi veya kod güvenlik onayı değildir**.

**Önerilen yayın yöntemi:** İşlevsel değişikliklerin tamamı üst dal
geçmişini zaten içeren PR #64'ün head dalında da bulunur. Tek bir birleşik
inceleme ve deploy stratejisi seçilmeli; tüm PR'ları gelişigüzel ayrı ayrı
`main` içine merge edip aynı değişiklikleri iki kez taşımamak gerekir.
`main` için son fark ve risk listesi tekrar incelenmeli, sürüm sabitlenmeli,
yedek/geri dönüş ve geçiş planı hazırlanmalı; kullanıcı ve repo yöneticisi
onay vermeden hiçbir `main` merge yapılmamalı.

## 2. Kod ve geçmiş testlerde doğrulananlar

- PR #57'de iki ayrı Solana ekranı korundu:
  `/meme-coins` stratejiler, `/meme-radar` salt-okunur radar.
  Bilgisayardaki yerel dağıtım bu GitHub PR'larından otomatik güncellenmez.
- PR #58 envanter/spot/futures modülleri **araştırma** amaçlıdır;
  fiyat, broker izni, gerçek veya sanal emir oluşturma kanıtı değildir.
- PR #59'da kaynak 19 Kasım 2026 tarihli, **1.750** Xetra
  ortak-hisse **adayı**; 18 Kasım'daki 1.749 adaya `1ANT.DE`
  (`US03703U1079`) eklenmiştir. Bu sayılar lisanslı gerçek zamanlı
  fiyat veya ISIN/provider eşleşme sayısı değildir.
- PR #62'de manuel Yahoo quote metadata denetimi varsayılan kapalı;
  eski/gelecek tarihli kaynak, yanlış borsa, yanlış döviz, yanlış sembol
  ve sağlayıcı hatası fail-closed reddedilir.
- PR #64'ün `/germany` ekranı GET ile envanter okur. En çok 5 sembol
  ile **yalnızca kullanıcı tıklayınca** quote metadata kontrolüne gider.
  `ADMIN_AUTH_ENABLED=true` ve
  `EBBOT_XETRA_QUOTES_UI_ENABLED=true` olmadan bu API aktif değildir.
  Tek süreç içinde 30 saniye cooldown uygulanır; dağıtık rate-limit yoktur.
- PR64 kalıcı CI: 36 backend testi, 8 frontend testi ve üretim build
  başarılıydı. Bu raporda daha geniş suite ayrıca çalıştırılır.

## 3. Üretim ve kullanıcı deneyimi engelleri

- **Üretim yönetici erişimi ve HTTPS:** `src/auth.py` dosyasında
  `.env` yoksa admin koruması etkin sayılmaz. Gerçek internete açık
  sunucuda erişim, ters proxy, oturumlar ve yetki denetimi ayrı doğrulanmalı.
  Uygulama sadece yerel `127.0.0.1` bağında tutulmalı; internet erişimi
  açılmadan güvenlik denetimi istenir.
- **Gerçek cihaz:** iOS ve Android PWA kurulumları, servis çalışanı
  cache/auth/çıkış davranışı, üretim URL'si, mobil navigasyon ve
  yetkisiz erişim cihaz üzerinde doğrulanmadı.
- **Veri hakları ve doğruluğu:** KAP/BIST envanteri gerektiğinde manuel
  sağlanmalı; Xetra adayları Yahoo doğrulanmış semboller değildir;
  lisans, güncellik, fiyat tarihleri ve Türkiye'de broker erişimi
  varsayılamaz. Xetra kaynağı yedi gün içinde eskimiş sayılabilir;
  otomatik yenileme bu incelemede açılmaz.
- **Çince / İngilizce arayüz:** Mevcut `GermanyMarketPage.tsx` içinde
  `zh`/English çeviri anahtarları duruyor ve tüm ürün arayüzünün
  Türkçe-only olacağı denetlenmiş değil. Kullanıcının çeviri
  hedefi için ayrı kapsamlı tarama gerekir; kod/sözleşme testlerinin
  geçmesi dil kalitesi onayı sayılmaz.
- **Para birimi:** Almanya fiyat örnekleri tasarım gereği
  `EUR` olarak gösterilir. Kullanıcının TL beklentisi için ayrı
  güvenilir EUR/TRY kur kaynağı, güncellik ve `as_of` göstergesi
  tasarlanmalıdır; geçerli kur yoksa TL değer tahmin edilmemelidir.
  Sadece fiyat birimi çevirmek alım-satım yetkisi sağlamaz.
- **Piyasa riskleri:** Paper/journal prototipleri, simülasyon denetimleri,
  gerçek para emir sistemi ve anahtar saklama testleri aynı şey değildir.
  Gerçek ve sanal işlemlere ayrı yetki verilmelidir.
- **Geniş regresyon:** Bütün 5 PR kodları aynı anda lint, backend,
  frontend, PWA ve gerçek cihaz denetiminden geçmeden yayın uygun
  sayılamaz. Ağ işaretli testler otomatik offline suite dışında tutulur;
  sağlayıcı bağlantısı ayrıca test edilmelidir.
- **Mevcut release denetleyicisi:** `scripts/audit_ebbot_release.py`
  manuel onayları `status=blocked` olarak verir. Böyle kalması
  bir CI hatası değil; release-gate politikasının beklenen sonucudur.

## 4. Bu audit PR'sinin sağladığı denetim

`.github/workflows/ebbot-five-pr-release-preflight.yml`:
- GitHub `main` ve 5 PR branch tipini anlık kontrol eder;
  altı SHA'nın birbirinin atası olduğunu kanıtlar.
- Mevcut audit'i *bilerek blocked* durumda tutar; raporu artifact yapar.
- `pytest -m 'not network'` ile tam çevrimdışı backend suite'i çalıştırır.
- Frontend lint + PWA + seçilmiş iki Meme Coin ekranı / Almanya paneli
  testleri + TypeScript build + çıktı PWA kontrat testini çalıştırır.
- Çevrimiçi araştırma veya gerçek API çağrısı, deploy, emir, cron,
  GitHub write izni, merge veya `main` değişikliği YAPMAZ.

## 5. Yayın kararı

Bu denetimin yeşil olması *tek başına* üretime geçiş kararı değildir.
Bekleyen manuel erişim, dil/kur, veri lisansı, gerçek cihaz ve yayın/geri
dönüş planı çözülene dek **YAYIN ENGELLİ**. Nihai karar için
kullanıcının açık yayın onayı ayrıca gereklidir.
