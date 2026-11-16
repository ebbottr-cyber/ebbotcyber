# ETRE — CoinGecko Top 100 entegrasyonu

## Kapsam

CoinGecko'nun /coins/markets verisi market_cap_desc, per_page=100, page=1
parametreleriyle alınır. Liste sabitlenmez ve CoinGecko sıralaması korunur.
Stablecoin ve wrapped varlıklar sıralamada varsa listelenir. Her varlık
sembolüyle değil, benzersiz CoinGecko id alanıyla tanımlanır.

- GET /api/v1/crypto/top100: günlük değil, 10 dakika önbellekli ilk 100.
- GET /api/v1/crypto/{coin_id}/technical: seçilen coin için mevcut Daily
  StockTrendAnalyzer teknik puanlama motorunu çalıştırır (15 dk önbellek).

Arayüz: Veri Merkezi > Kripto · CoinGecko Top 100.
Mevcut 4 hisse piyasası (Türkiye, ABD, Almanya, Hong Kong) ve 400 hisse
listesi değiştirilmez. STOCK_LIST, SQLite, alım-satım, bildirim,
portföy kaydı ve hisse sinyalleriyle entegre edilmez.

## Veri kalitesi ve sınırlamalar

CoinGecko 30 günlük OHLC verisini otomatik zaman çözünürlüğünde verir;
gerçek OHLC mumları, tamamlanmış UTC takvim günleri için birleştirilir.
Bu mumlara /market_chart kaynağından, ilgili günün sonundaki kayan 24
saatlik USD hacim verisi bağlanır. Bu hacim kesin günlük borsa hacmi
değildir. Eksik mum veya hacim uydurulmaz: 26 günden az veri varsa
puanlama yapılamaz. 60 günlük veri olmadığı için Daily motorundaki
MA60 -> MA20 yedekleme davranışı geçerlidir.

Kripto puanları aynı hisse stratejisi eşikleriyle hesaplanır, ancak bu
eşikler kripto için kalibre edilmemiştir. Geriye dönük test yoktur.
Yalnızca kullanıcı seçtiğinde tek coin incelenir; tüm ilk 100 coin
otomatik taranmaz ve yatırım emri gönderilmez.

Bir istek başarısız olursa önceki başarılı ilk 100 verisi en fazla 6
saat boyunca 'eski veri' etiketiyle gösterilebilir. API erişimi için
opsiyonel COINGECKO_DEMO_API_KEY değişkeni sunucuda ayarlanabilir.
Anahtarı GitHub'a veya web arayüzüne koymayın.

## Windows yerel kontrol

Proje ana dizininden:

    .\.venv\Scripts\python.exe -m pytest tests/test_coingecko_top100.py -q

Web arayüzü dizininden:

    npm.cmd run test -- src/api/coinGecko.test.ts
    npm.cmd run build

Sunucu yeni Python dosyalarını yüklemek için yeniden başlatılmalıdır.
Python sunucusu: main.py --serve-only --host 127.0.0.1 --port 8000
Web arayüzü: apps/dsa-web klasöründen npm.cmd run dev

Bu testler örnek/veri taklitleriyle çalışır. Canlı CoinGecko cevapları,
API kotası, gerçek kullanıcı arayüzü ve finansal doğruluk henüz
uçtan uca doğrulanmış sayılmaz.
