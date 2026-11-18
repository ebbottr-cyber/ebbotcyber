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

Kullanım (tamamı yalnızca yerel okuma, ağ erişimi ve işlem yok):

    python -m scripts.audit_paper_universe
    python -m scripts.audit_paper_universe --stocks C:\veriler\bist-all.csv --coins C:\veriler\solana-all.jsonl --coins C:\veriler\crypto-spot.json
    python -m unittest discover -s tests -p test_paper_universe_inventory.py -v

Çıktı IN​VENTORY_ONLY (yalnızca envanter) düzeyindedir, fiyat/performans
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
