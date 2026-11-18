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
