# EBBot — Tüm hisse ve Binance Spot coin envanterleri

Bu hazırlık 3 hisse veya sabit 100 coin sınırı kullanmaz.
Mevcut depoda 31.677 etkin hisse kaydı ve ayrı 33 endeks var.
BIST'in tam şirket listesi KAP kaynağından; Binance Spot coin listesi,
Binance'in resmi salt-okunur exchangeInfo API'sinden *elle* indirilebilir.

## Hangi borsa, hangi kapsam?

- **BIST:** KAP şirket dizini. Şirket kodu bir borsa sembol adayıdır;
  işlem izni, kotasyonun güncelliği veya lisans kanıtı değildir.
- **Kripto:** Binance GLOBAL **Spot** kataloğu.
  API: https://data-api.binance.vision/api/v3/exchangeInfo
  Binance TR, Binance Futures veya dünyadaki bütün tokenların listesi DEĞİLDİR.
  Coinlerin işlem çiftleri (baseAsset + quoteAsset) tekilleştirilip
  benzersiz Binance varlık listesi oluşturulur.
- Yalnızca isSpotTradingAllowed=true olan çiftlerden varlıklar alınır.
  status=TRADING olmayan çiftler envanterde pasif kalabilir; para ile
  işlem yapılabileceği, kullanıcı ülkesinde erişim olduğu iddia edilmez.
- Ticker'lar zincir kontrat adresleri değildir.
  Ağ etiketi "binance_spot_catalog" olduğundan Solana ve Robinhood
  Chain kontratlarıyla otomatik birleştirilmez.
- Solana yeni tokenlar, DEX coinleri ve Binance'de listeli olmayanlar
  için ayrıca güvenilir zincir kimliği ve keşif adaptörü gerekir.
- Almanya, Tayvan ve diğer tam olmayan borsalar da CSV kaynaklarıyla
  eklenebilir; var olmayan kaynağa "tam kapsama" denmez.

## Nasıl kullanılır? (PowerShell, isteğe bağlı)

  New-Item -ItemType Directory -Force "$HOME\EBBotPaperData"
  python -m scripts.refresh_paper_universe_sources --fetch --output-dir "$HOME\EBBotPaperData"
  python -m scripts.audit_paper_universe --stocks "$HOME\EBBotPaperData\kap-bist-all.csv" --coins "$HOME\EBBotPaperData\binance-spot-all.json"

Sadece Binance'i denemek için:
  python -m scripts.refresh_paper_universe_sources --fetch --source binance --output-dir "$HOME\EBBotPaperData"

Komut mevcut envanter dosyalarını varsayılan olarak ezmez.
Manuel güncellemek için --replace eklenir.
--fetch verilmezse **hiç ağ isteği / dosya yazımı yapılmaz**.

## Teknik doğrulama ve sonraki aşama

  python -m unittest discover -s tests -p test_paper_universe_inventory.py -v
  python -m unittest discover -s tests -p test_paper_universe_sources.py -v

GitHub CI sadece sahte/çevrimdışı yanıtlarla envanter kaynaklarını test eder;
gerçek Binance erişimi veya Binance'deki coin sayısı ayrıca kanıtlanmalıdır.
Cihaz/bölge engeli, veri sözleşmesi, delist, fiyat gecikmesi, API hız limiti ve
veri lisansı canlı kullanım öncesi incelenmelidir.

**INVENTORY_ONLY** modunda kalır: fiyat yüklemez, emir üretmez, otomatik
tarama başlatmaz, sanal fill veya PnL yazmaz, cüzdan kullanmaz.
İkinci adım güncel fiyat, risk ve zaman damgası denetimleri;
paper trading için ayrıca manuel izin gerekir.


## V4 — Binance Futures sözleşme envanteri

Spot'a ek olarak Binance Global'in iki ayrı Futures kataloğu:
- USDⓈ-M: https://fapi.binance.com/fapi/v1/exchangeInfo
- COIN-M: https://dapi.binance.com/dapi/v1/exchangeInfo

Yalnızca kamuya açık GET market data çağrısı yapılır. API anahtarı, cüzdan,
hesap, kaldıraç, emir, açığa satış veya sanal fill yoktur.

Mevcut Spot dosyasını koruyarak yalnızca Futures sözleşmelerini alma:

    python -m scripts.refresh_paper_universe_sources --fetch --source futures --output-dir C:\EBBotPaperData

Sadece tek tür: --source usdm veya --source coinm.
Hepsi: --source all (KAP + Spot + USDⓈ-M + COIN-M).
Mevcut --source both seçeneği eskisi gibi yalnızca KAP + Spot'tur.

Birleştirilmiş envanter raporu:

    python -m scripts.audit_paper_universe --coins C:\EBBotPaperData\binance-spot-all.json --contracts C:\EBBotPaperData\binance-usdm-futures.json --contracts C:\EBBotPaperData\binance-coinm-futures.json

Raporun coin_count ve futures_contract_count sayıları birbirinden ayrıdır.
Futures sözleşmeleri coin olarak sayılmaz. PERPETUAL ve vadeli teslim türleri
farklı kontratlar olarak tutulur; delist/settled kontratlar ayrı statüde kalır.
Aktiflik sadece API'deki TRADING durumudur; ülkenizde Futures işlem hakkı,
marjin, likidasyon, funding, risk ve PnL hesabı doğrulanmış sayılmaz.
Henüz bu kaynaktan gerçek sayılar indirilmedi; GitHub testleri sentetiktir.

## V4.1 — Futures sembol doğrulaması

Binance Futures sözleşme sembolleri dar ASCII hisse/sembol kalıbı
ile sınırlandırılmaz: kaynakta bulunan **görünür UTF-8 karakterler**
ve noktalama korunur. En fazla 128 karakter, boş olmayan,
kenarları boşluksuz ve kontrol karakteri içermeyen semboller kabul
edilir. Hatalı kayıt atlanıp eksik pazar oluşturulmaz; kaynak satır
numarası ve kısaltılmış hatalı değerle işlem BLOKLANIR.
Stok envanter kontrolü aynı kuralla uyumlu kalır.
Gerçek emir, sanal fill, cüzdan veya kaldıraç açılmaz.


## V5 — Fiyat kaynaklarını doğrulama (yalnızca araştırma)

Yeni modül, mevcut **tüm aktif Binance Spot çiftlerini** ve **tüm aktif USDⓈ-M / COIN-M sözleşmelerini** fiyat kaynaklarına karşı kontrol eder; 3, 50 veya 100 örnek varlık seçmez.

- Spot: Binance public Spot exchangeInfo ile /api/v3/ticker/24hr verilerini karşılaştırır. Son fiyatın pozitifliği denetlenir, kayıp/kötü veri sayılır. 24h ticker closeTime **son işlemin zamanı değildir**; bu nedenle Spot anlık işlem fiyatı doğrulanmış sayılmaz.
- Futures: /fapi/v1/premiumIndex ve /dapi/v1/premiumIndex işaret fiyatlarının pozitifliği, eksik kayıtlar ve kaynak time alanına göre 120 saniyelik eskime kontrolü yapılır. Mark fiyatları emir gerçekleşme fiyatı değildir. Funding, marjin, kaldıraç, likidasyon, kontrat büyüklüğü için iş modeli henüz doğrulanmadı.
- BIST: KAP şirket dizinindeki bütün semboller sayılır. KAP şirket kodu fiyat değildir. Lisanslı günlük kapanış dosyası verilmezse 803 BIST adayı için fiyat durumu **missing** kalır. İsteğe bağlı dosya: symbol,close,as_of,source,currency alanlı CSV. Tarih son 7 takvim günü içinde olsa da kesin işlem takvimi veya anlık işlem kotasyonu kanıtlanmaz.
- Çıktı, her piyasa için ayrıntılı **adetler ve hata/kapsam nedenleri** sunar; fiyatların kendisini, alım-satım talimatını ya da sanal PnL'yi oluşturmaz.

PowerShell (mevcut dört snapshot dosyası, public API için açık opt-in):

    python -m scripts.audit_paper_quote_sources --fetch --stocks "$HOME\\EBBotPaperData\\kap-bist-all.csv" --spot "$HOME\\EBBotPaperData\\binance-spot-all.json" --usdm "$HOME\\EBBotPaperData\\binance-usdm-futures.json" --coinm "$HOME\\EBBotPaperData\\binance-coinm-futures.json"

Yalnızca 4 sabit Binance public GET çağrısı vardır. API anahtarı, cüzdan, pozisyon, disk raporu veya zamanlayıcı yoktur. Testler sentetik fixture'larla internetsiz çalışır; gerçek kaynakların güncelliği bilgisayarda ayrıca doğrulanmalıdır.


## V5.1 — Spot 24 saat fiyat sorunlarının sınıflandırılması

Binance 24 saatlik ticker kaydındaki `count`, o kayan 24 saatlik
pencerenin işlem sayısıdır; **son işlem zamanının** kanıtı değildir.
Denetim artık her geçersiz Spot çifti için `invalid_price_reasons`
döndürür: sıfır/negatif fiyat, sayısal olmayan fiyat, boş fiyat,
son 24 saatte işlem olmamasıyla birlikte sıfır fiyat veya
geçersiz işlem sayısı. Ayrıca `zero_trades_24h_symbols` listesi,
**pozitif son fiyat olsa bile**, o dönemde 0 işlem bildiren çiftleri
gösterir. Tüm eşleşmeler taranır, Top-N veya sessiz ayıklama yoktur.
Bu uyarılar delist kararı değil, veri sağlayıcısının verdiği
24 saatlik özet istatistiklerin teşhisidir.

18 Kasım 2026 Windows denetiminde geçersiz fiyatla dönen 9 çift:
`ARBU`, `LTCUSD1`, `ORDIU`, `PLUMETHB`, `TRBJPY`,
`TRXUSD1`, `UIDR`, `WLDU`, `XLMUSD1`.
Sembol adları kullanıcı çıktısıdır; **kesin hata nedenleri**
bir sonraki gerçek API denetiminde `invalid_price_reasons`
alanından görülecek. `paper_ready=false` ve gerçek emirler kapalı.
