# EBBot Kripto — Aşama 6: Binance USD-M Futures (read-only)

Bu geliştirme yalnızca EBBot'un Kripto Trading bölümünü değiştirir.
Hisse modülleri, Solana hype sistemi, CoinGecko Top100 ve Haberler
modülü olduğu gibi bırakılmıştır.

## Gerçek kaynak kodundan doğrulanan entegrasyon

Yüklenen \`ai-multi-market-trading-office-main.zip\` içindeki:

- \`backend/app/api/routes.py\` (/markets/{market}/ticker, ohlcv,
  orderbook, /markets/futures/funding-rate)
- \`backend/app/market_data/binance.py\`
- \`backend/app/market_data/exchange.py\`

dosyaları temel alındı. Trading Office Binance USD-M Futures tarafında
\`ccxt.binanceusdm\` kullanır. Gerçek CCXT USD-M perpetual kimliği
\`BTC/USDT:USDT\` şeklindedir, Spot \`BTC/USDT\` ile **aynı değildir**.
EBBot arayüzünde sade \`BTC/USDT\` gösterilir fakat Trading Office'e
\`BTC/USDT:USDT\` gönderilir ve dönüş aynı kontrat kimliğiyle doğrulanır.

## EBBot API

Beş salt-okunur, admin oturumu gerektiren endpoint:

| EBBot endpoint'i | Kaynak |
| --- | --- |
| GET /api/v1/crypto-office/futures/ticker | Trading Office /markets/futures/ticker |
| GET /api/v1/crypto-office/futures/ohlcv | Trading Office /markets/futures/ohlcv |
| GET /api/v1/crypto-office/futures/orderbook | Trading Office /markets/futures/orderbook |
| GET /api/v1/crypto-office/futures/funding | Trading Office /markets/futures/funding-rate |
| GET /api/v1/crypto-office/futures/open-interest | Binance public GET https://fapi.binance.com/fapi/v1/openInterest |

Son endpoint Trading Office'de bulunmadığı için **doğrudan Binance'in
herkese açık ve API anahtarı gerektirmeyen resmi USD-M REST
endpoint'inden** alınır. Sabit HTTPS URL, sembol allowlist,
limitli cevap boyutu, timeout ve kaynak zaman damgası doğrulaması vardır.
\`TRADING_ENABLED=false\` kuralı bu endpoint için de zorunludur.

Binance public OI miktarı *kontrat baz varlık adedi* cinsindendir;
USDT notional hacim sanılmamalıdır. Binance Futures, ülkeye göre
erişim engeli uygulayabilir. Başarısızlık halinde \`Veri yok\` gösterilir.

## Veriye güven kontrolleri

- İşlem çifti \`BASE/USDT\` biçiminde olmalı; futures CCXT symbol
  \`BASE/USDT:USDT\` olarak tanımlanmalı
- Binance veri kaynağı, market='futures' ve geri dönen kontrat kimliği
  uyuşmalı; Spot verisini Futures gibi göstermek yasak
- Fiyat/mark > 0, OHLCV high/low tutarlı, son mum güncel,
  emir defteri çapraz değil ve miktarlar sonlu olmak zorunda
- Funding rate sonlu, aralık 1/2/4/8 saat; mark/index fiyatlar
  ayrı doğrulanıyor; settlement timestamp *gözlem zamanı sayılmıyor*
- Open Interest timestamp'i son 180 saniye içinde olmalı;
  yanlış Binance sembolü, negatif/NaN/sonsuz büyüklük reddedilir
- Kaynakta zaman damgası yoksa \`quality=unknown\` gösterilir,
  doğrulanmış 'canlı' fiyat olarak sunulmaz
- Bozuk/eskimiş değerler gizlenir; eski cache ile yeniymiş gibi
  gösterilmez
- Trading Office tarafında API key sunucuda kalır ve yalnız
  GET public market data yollarına erişilir
- Futures public OI için kısa in-memory TTL ve sınırlı başarısızlık
  backoff/circuit; REST ~30 saniye taranır
- Güncel bakiye için özel API, gerçek emir, çekme veya transfer
  endpoint'i oluşturulmadı

## Kullanıcı arayüzü

\`/crypto-trading\` → \`Futures Piyasası\`:

1. BTC/USDT, ETH/USDT, SOL/USDT vb. sembol filtreleri
2. Mum grafiği ve 6 zaman dilimi
3. Son fiyat ve mark/index fiyatları
4. Funding oranı, ödeme aralığı ve planlanan sonraki zaman
5. Open Interest ve 20 kademelik emir defteri
6. Long/Short varsayımsal kaldıraç risk senaryosu

Risk simülatörü margin × leverage üzerinden hesaplanan yalnızca
teorik fiyat hareketi PnL'sini gösterir. **Likidasyon hesaplamaz**,
gerçek borsa emirleri açmaz, komisyon/maintenance margin/stop/funding
risklerini kapsıyor gibi iddia etmez. Funding nakit akışı, mevcut
oranın bir funding periyodu boyunca aynı kaldığı varsayımına dayanır.
Bu model zorunlu merkezi risk motorunun yerine geçmez.

Paper Trading Futures defteri ayrı tutulur. Mevcut dashboard sözleşmesi
doğrulanmışsa yalnız salt-okunur Paper görüntüsü sunulur. Aksi durumda
özsermaye veya açık pozisyon sayısı uydurulmaz.

## Kurulum

Önce \`docs/EBBOT_KRIPTO_ILK_ENTEGRASYON_TR.md\` içindeki Trading
Office sunucusu, EBBot oturumu ve API anahtarı kurulumlarını yap.
Ayrı servis erişimi yoksa kaynak fiyatları gösterilmez.

Yerel testler:

\`\`\`powershell
cd C:\Users\Thebo\Projects\ebbotcyber-test
git switch feat/turkish-ui-hk-latin-display
git pull --ff-only origin feat/turkish-ui-hk-latin-display
python -m unittest discover -s tests -p "test_crypto_futures_bridge.py" -v
python -m unittest discover -s tests -p "test_crypto_spot_bridge.py" -v
cd apps\dsa-web
npm.cmd run test -- src/api/cryptoFutures.test.ts src/components/crypto/CryptoFuturesPanel.test.tsx
npm.cmd run build
\`\`\`

Yerel/CI testleri ve canlı Binance erişimi bu turda henüz
doğrulanmadı. Binance sözleşme kimlikleri ve Futures kaynağı
gerçek Trading Office ZIP'indeki kodla karşılaştırıldı.

## Sonraki aşama

Futures modülünün tamamı güvenli salt-okunur şekilde doğrulandıktan
sonra AI ajanları, strateji, sinyal doğrulama ve nihayetinde **bağlayıcı
risk motoru** geliştirilecek. Risk kapısı testlerden geçmeden Futures
Paper Trading işlem yürütmeye izin verilmeyecek.
