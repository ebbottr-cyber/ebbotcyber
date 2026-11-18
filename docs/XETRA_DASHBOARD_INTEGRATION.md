# EBBot Almanya/Xetra panel entegrasyonu (inceleme)

Bu çalışma, [PR #62](https://github.com/ebbottr-cyber/ebbotcyber/pull/62)
üzerine yığılmıştır. Otomatik birleştirme ve canlıya alma yoktur.

## Ekran

- Web/pano yan menüsünde **Almanya (Xetra)** bağlantısı: `/germany`.
- Ekran ilk açılışta yalnızca `GET /api/v1/xetra/inventory` çağırır.
  Yerel kayıt `data/market_snapshots/de/xetra-candidates.csv` içinden tüm
  1.749 kaynaklı hisse adayının sayısı, kaynak tarihi, sembol/ISIN araması gelir.
  Varsayılan 30 aday listelenir; API'de sayım kesilmez.
- Hisse listesi bir *piyasa referansı*, fiyat akışı veya emir listesi değildir.
  Kaynak 7 günden eskiyse açık uyarı görünür.
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
yalnızca sabit Yahoo Finance HTTPS GET uç noktası, her sembol için ağ zaman aşımı.
Sunucuda zamanlanmış tarama veya otomatik veri tabanı kaydı yapılmaz.
Panel fiyat kontrolü henüz 1.749 hisseye toplu veri sağlayıcısı veya
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
bağımlılıklar birleştirilmeden kullanıcıya yayınlanmış sayılamaz. Mevcut
kripto, meme, futures ve canlı/paper trade koduna dokunulmadı.
