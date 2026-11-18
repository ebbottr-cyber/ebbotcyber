# EBBot all-market stock and crypto inventory

Bu geliştirme 3 hisse, 100 hisse veya 10 coin sınırı kullanmaz.
Repo stock index'indeki bütün etkin hisseleri sayar. Mevcut indeks snapshot'ı:
31.677 hisse ve 33 endeks; BIST, Almanya ve Tayvan TAM listesi bu dosyada yoktur.

Diğer borsaların tüm hisse listesi için CSV envanteri eklenebilir.
CSV alanları: market,symbol,source (isteğe bağlı kind ve active).
Coinlerin tamamını eklemek için her sağlayıcının eksiksiz anlık
envanterinin JSON veya JSONL dosyası gerekir. Coin alanları:
network,asset_id,symbol,source (isteğe bağlı active).
Aynı ağdaki aynı coin adresi veya aynı piyasadaki aynı hisse
tekilleştirilir; listedeki tüm benzersiz kayıtlar sayılır.

## V2: Kaynaklardan elle güncelleme, asla otomatik işlem değil

KAP'ın resmi BIST şirket dizininden hisse kodlarını, CoinPaprika'nın anahtarsız
GET /v1/coins kataloğundan kayıtları alacak sağlayıcılar eklendi. **Manuel**
--fetch parametresi olmadan ağ erişimi ve dosya yazımı yoktur.

    mkdir C:\EBBotPaperData
    python -m scripts.refresh_paper_universe_sources --output-dir C:\EBBotPaperData
    python -m scripts.refresh_paper_universe_sources --fetch --output-dir C:\EBBotPaperData
    python -m scripts.audit_paper_universe --stocks C:\EBBotPaperData\kap-bist-all.csv --coins C:\EBBotPaperData\coinpaprika-all.json
    python -m scripts.refresh_paper_universe_sources --fetch --replace --output-dir C:\EBBotPaperData

- --source kap veya --source coinpaprika ile her kaynak tek başına alınabilir.
- KAP'ın dizinindeki şirket kodları .IS biçimine dönüştürülmüş **adaylardır**:
  her şirket kodunun o tarihte borsada işleme açık olduğu veya hisse senedi
  olduğu bağımsız olarak doğrulanmış sayılmaz.
- CoinPaprika'nın listesi aktif ve pasif tüm **katalog kimliklerini** saklar.
  Pasifler envanterin aktif sayımından dışlanır. Bu liste Solana mint adresleri
  veya bütün DEX tokenlarının kaydı DEĞİLDİR! CoinPaprika kimlikleri bilinçli
  olarak "coinpaprika_catalog" ağ etiketiyle izole edilir.
- Her iki kaynak sunucusunun servis/hız/erişim ve ticari veri lisansı şartları
  gerçek ortamda ayrıca kontrol edilmelidir. KAP web sayfası yapısı değişirse
  alma işlemi bloklanır; sessizce 3-5 hisselik sonuç kaydedilmez.
- Dışa aktarımlar sadece belirtilen yerel dizine yazılır; her dosyanın SHA-256
  özeti kaydedilir, yeni çıktının eskisini değiştirmesi için --replace gerekir.
  Kaynak tarihi, fiyat verisi tarihi veya güvenilir kontrat kimliği değildir.
- Hiçbir otomatik scheduler, tarama/işlem görevi, fiyat sorgusu veya gerçek
  emir bağlanmamıştır. GitHub CI ağ gerektirmeyen sahte yanıtlarla test edilir.

## Salt-okunur kontrol

    python -m scripts.audit_paper_universe
    python -m unittest discover -s tests -p test_paper_universe_inventory.py -v
    python -m unittest discover -s tests -p test_paper_universe_sources.py -v

Çıktı INVENTORY_ONLY (yalnızca envanter) düzeyindedir, fiyat/performans
veya sanal işlem hazır demek değildir. Bir kaynağın tam veya güncel
olduğu henüz ispatlanmamıştır. BIST ve coin kaynakları eksikse
missing_source_inventories içinde görünür. Bu adım sadece desteklenen
tüm listelerin birleşik ve ölçeklenebilir kayıtlarını hazırlar.

Bir sonraki aşama: Tüm piyasalarda güncel/listeden kaldırılmış varlıkları
doğrulayan kaynak envanterleri, sembol/kontrat tekilliği, saat/kur,
fiyat tazeliği, token riskleri, rate-limit korumalı sayfalı read-only
kotasyon ve tarihli sanal defter adaptörleri. Bunlar ayrı onay olmadan
açılmayacak. Otomatik tarama, zamanlayıcı, gerçek emir ve paper fill kapalı.
PR #57 ile main dalı bu hazırlıktan etkilenmez.
