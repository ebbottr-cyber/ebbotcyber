# EBBot Kripto — Aşama 5: Binance Spot Piyasa Verileri

Bu aşama yalnızca EBBot'un Kripto Trading bölümünü değiştirir.
Mevcut hisse sistemi, Haberler, CoinGecko Top 100 ve Futures/Paper
muhasebesine yazma veya otomatik işlem özelliği eklenmedi.

## Uygulanan bileşenler

Trading Office ZIP'i esas alındı: mevcut sunucu şu API yollarını
sunuyor ve Binance public market data/CCXT üzerinden okuyor:

- `GET /api/v1/markets/spot/ticker?symbol=BTC/USDT`
- `GET /api/v1/markets/spot/ohlcv?symbol=BTC/USDT&timeframe=1h&limit=100`
- `GET /api/v1/markets/spot/orderbook?symbol=BTC/USDT&limit=20`

EBBot bunları ayrı sunucu-side read-only uç noktalarından sunar:

- `GET /api/v1/crypto-office/spot/ticker`
- `GET /api/v1/crypto-office/spot/ohlcv`
- `GET /api/v1/crypto-office/spot/orderbook`

Üç EBBot API yolu da etkin yönetici kimlik doğrulaması ve geçerli
oturum çerezi gerektirir. API anahtarı yalnız backend ortamında
tutulur. İstekler EBBot'un önceki localhost-only bağlantı kısıtı
içinden geçer; redirect ve ortam HTTP proxy'si kullanılmaz.
Gerçek emir, borsa bakiyesi, secret, para transferi endpoint'i yoktur.

## Piyasa veri doğrulaması

- İşlem çiftleri biçimsel olarak doğrulanır (`BTC/USDT`, `ETH/USDT` vb.).
  Sembol Binance'de gerçekten işlem görüyorsa Trading Office bunu ayrıca
  `exchange.markets` üzerinde doğrular. CoinGecko sembolünden otomatik
  Binance eşleştirmesi YAPILMADI; farklı kimlikler karıştırılmaz.
- Ticker last > 0; sayılar sonlu ve bid <= ask.
- Kaynak ticker timestamp'i varsa 180 saniyeden eski fiyat reddedilir;
  timestamp yoksa `quality=unknown` ile uyarılır, 'güncel' denmez.
- OHLCV mumlarının zaman damgaları artan, high/low tutarlı ve volume
  >=0 olmalıdır. Son mum 3 zaman aralığı + 180 saniyeden eskiyse
  veri kullanılmaz. 1m,5m,15m,1h,4h,1d desteklenir.
- Emir defteri seviyeleri geçerli ve doğru sıralı olmalı; bid/ask
  birbirini kesmemeli. 60 saniyeden eski kaynak zaman damgası
  varsa veri reddedilir. Timestamp yoksa kalite bilinmiyor.
- Bozuk veya eski veri `502/503` olarak reddedilir; fiyat sıfır
  uydurulmaz ve cached veri hata durumunda 'stale' olarak sunulmaz.
- En fazla 350 KB cevap gövdesi, timeout, hatalı içerik türü kontrolü.
- Trading Office tarafındaki ExchangeService retry/rate-limit,
  shared TTL cache, per-market circuit breaker sürdürülür.
- EBBot yerel TTL: ticker 6 sn, orderbook 5 sn, OHLCV 30 sn.

## EBBot arayüzü

`http://localhost:5173/crypto-trading` altında `Spot Piyasası`.
İlk sürüm gerçek Binance Spot fiyatı, 24 saatlik hacim, mum grafiği
ve ilk 20 emir defteri seviyesini gösterir. Popüler çift düğmeleri,
manuel çift girişi ve çoklu zaman dilimi vardır.
REST yaklaşık 30 saniyede bir yenilenir. WebSocket, Futures,
Spot Paper emir yürütme, CoinGecko Top100 eşleştirme ve
AI kararları sonraki ayrı aşamalarda kalır.

## Kurulum

Önce `docs/EBBOT_KRIPTO_ILK_ENTEGRASYON_TR.md` içindeki yerel
Trading Office/EBBot sunucu bağlantısını kur. `TRADING_ENABLED=false`
kalmalıdır. EBBot yönetici girişi için `ADMIN_AUTH_ENABLED=true`
ayarını EBBot .env dosyasında yap; backend bu anahtarı .env'den okur.

Yerel testler (gerçek Binance/gerçek emir erişimi gerektirmez):

    cd C:\Users\Thebo\Projects\ebbotcyber-test
    git fetch origin
    git switch feat/turkish-ui-hk-latin-display
    git merge --ff-only origin/feat/turkish-ui-hk-latin-display
    & .\.venv\Scripts\python.exe -m unittest discover -s tests -p test_crypto_spot_bridge.py -v
    cd apps\dsa-web
    npm.cmd run test -- src/api/cryptoSpot.test.ts src/components/crypto/CryptoSpotPanel.test.tsx
    npm.cmd run build

## Doğrulama durumu

API ve UI kodları ve offline test dosyaları GitHub'da var.
GitHub Actions ve canlı Trading Office/Binance bağlantısı bu
değişiklik turunda çalıştırılmadı. Başarılı canlı veri/kapsam
iddiası ancak test sonuçlarıyla yapılabilir.
