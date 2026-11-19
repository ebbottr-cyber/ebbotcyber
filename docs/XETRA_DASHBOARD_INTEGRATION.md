# EBBot Almanya/Xetra panel entegrasyonu (inceleme)

Bu çalışma, [PR #62](https://github.com/ebbottr-cyber/ebbotcyber/pull/62)
üzerine yığılmıştır. Otomatik birleştirme ve canlıya alma yoktur.

## Ekran

- Web/pano yan menüsünde **Almanya (Xetra)** bağlantısı: `/germany`.
- Ekran ilk açılışta yalnızca `GET /api/v1/xetra/inventory` çağırır.
  Yerel kayıt `data/market_snapshots/de/xetra-candidates.csv` içinden tüm
  1.750 kaynaklı hisse adayının sayısı, kaynak tarihi, sembol/ISIN araması gelir.
  Varsayılan 30 aday listelenir; API'de sayım kesilmez.
- Hisse listesi bir *piyasa referansı*, fiyat akışı veya emir listesi değildir.
  Kaynak 7 günden eski veya geleceğe tarihlenmişse açık uyarı görünür ve manuel sorgu kapatılır.
- Kullanıcı seçtiği en fazla 5 sembol için **Fiyatları kontrol et** düğmesine
  basınca `POST /api/v1/xetra/quote-check` çağrılır.
- Hatalı, eski, yanlış sembol/borsa/döviz sonucu fiyat olarak gösterilmez.
  Doğrulanan fiyat *gecikmeli olabilen* Yahoo/EUR örneği olarak tarih
  bilgisiyle gösterilir. Gerçek zamanlı değil, işlem sinyali değil.

## Ağ geçidi ve yetki

Varsayılan: yeni Xetra fiyat endpoint'i **kapalıdır**. Envanter okuması çalışır.

Etkinleştirmek için sunucunun `.env` dosyasında mevcut yönetici
kimlik doğrulaması açılmış (`ADMIN_AUTH_ENABLED=true`) olmalı; oturum
açıldıktan sonra sunucunun işletim ortamında:

```dotenv
EBBOT_XETRA_QUOTES_UI_ENABLED=true
```

olmalıdır. İstemci tarafından bu bayrak değiştirilemez. Yetkilendirme
middleware'i yönetici oturumu ister. Yönetici kimlik doğrulaması kapalıysa,
bayrak açık olsa dahi sunucu 403 döner. Web paneli bunu açıkça gösterir.
Açılmadığında URL fiyat çağrısı yapmaz; hesap anahtarına veya broker'a erişmez.

Sınırlamalar: Sorgu başına 5 kaynakta kayıtlı sembol, kullanıcı isteği,
aynı işlemde eşzamanlı fiyat sorgusuna izin vermeyen kilit ve başlatılan
manuel sorgular arasında 30 saniyelik bekleme kuralı (**yalnızca süreç
içinde**); küresel/birden fazla çalışanı kapsayan dağıtık limit değildir.
Gerçek çok-çalışanlı sunucu ortamlarında ters proxy üzerinden ayrıca
istek sınırı konulmalıdır. Kaynak tarihi tek ve en fazla 7 günlük değilse
fiyat endpoint'i 409/503 yanıtlar ve sağlayıcı sorgulanmaz. Sorgu geçidi
kapalıysa HTTP 403, limit doluysa HTTP 429 döner.

yalnızca sabit Yahoo Finance HTTPS GET uç noktası, her sembol için ağ zaman aşımı.
Sunucuda zamanlanmış tarama veya otomatik veri tabanı kaydı yapılmaz.
Panel fiyat kontrolü henüz 1.750 hisseye toplu veri sağlayıcısı veya
analiz/backtest stratejisi bağlantısı değildir. Güncel fiyat hizmeti için
veri lisansı ve ISIN eşleştirmesi ayrıca doğrulanmalıdır.

## Doğrulama

```powershell
python -m unittest discover -s tests -p "test_xetra_dashboard_api.py" -v
python -m unittest discover -s tests -p "test_xetra_quote_guard.py" -v
cd apps/dsa-web
npm ci
npm test -- src/pages/__tests__/GermanyMarketPage.test.tsx
npm run build
```

Yeni ekran ve API PR inceleme dalındadır; PR #57, #58, #59, #62 zincirindeki
bağımlılıklar birleştirilmeden kullanıcıya yayınlanmış sayılamaz.
19 Kasım 2026'da PR #57'nin ana dal çatışmaları giderildi ve
PR #58, #59, #62 güncel tabanlarına senkronlandı; bu PR'lar hâlâ taslak
ve ana dala alınmış değiller. PR #59'daki resmî kaynak listesi 19 Kasım
tarihli, **1.750 benzersiz Xetra ortak hisse adayı** içerir; önceki
18 Kasım listesindeki 1.749 kayda `1ANT.DE` eklendi. Liste fiyat/ISIN
eşleşmesi, lisans veya broker erişimi kanıtı değildir. PR #64 bu yeni
tabanda yalnızca read-only testlerle incelenir; ana sürüme doğrudan
birleştirilmez. Gerçek ve sanal işlemler kapalıdır.
