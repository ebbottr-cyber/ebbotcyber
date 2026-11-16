# ETRE — Dört piyasa × 100 hisse: kademeli ve salt-okunur tarama

Aktif kapsam TR/US/DE/HK = 400 hisse kodudur. Japonya, Çin, Güney Kore ve Tayvan bu yeni yatırım taramasında yoktur. Mevcut geçmiş arşivler ve regresyon testleri silinmez.

## Kaynak ve veri ayrımı

- Türkiye'nin tarihli 2026-Q4 BIST100 üyelik listesi kaynaklarla birlikte depoda bulunuyor.
- ABD, Almanya ve Hong Kong'un 100'er gerçek kodu, resmî ve güncel dosyaların kullanıcının bilgisayarına indirilip önceki içe aktarıcılarla hazırlanmasını gerektirir. Eksikler uydurulmaz.
- Listeyi hazırlamak ile Yahoo'dan geçmiş fiyatı kontrol etmek ve teknik analizi başarıyla tamamlamak ayrı aşamalardır.
- Tamamlanan kontrol sayısı = başarılı + başarısız hisse sonuçları. Henüz kontrol edilmemiş kodlar "başarılı" sayılmaz.

## 1. Kaynaklı 400 kodlu planı üretin

Aşağıdaki işlem ancak dört piyasanın her birinden 100 farklı, tarihli ve biçimce doğru hisse kodu varsa tamamlanır; aksi hâlde ihracı engeller. Windows PowerShell, yerel test kopyasında:

    & ".\.venv\Scripts\python.exe" -m src.services.four_market_universe_plan --us-roster "$env:USERPROFILE\Documents\us.json" --de-roster "$env:USERPROFILE\Documents\de.json" --hk-roster "$env:USERPROFILE\Documents\hk.json" --as-of 2026-11-16 --report "$env:USERPROFILE\Documents\etre-source-400-plan.json" --export-400 "$env:USERPROFILE\Downloads\etre-400-tickers.txt"

Yabancı piyasa dosyaları veya kaynak doğrulamaları henüz tamamlanmadan gerçek 400 hisse taraması yapılmaz. Kaynak URL'sinin JSON'da bulunması yayıncı tarafından doğrulama veya broker emir yetkisi garantisi değildir.

## 2. Hisseleri 10'arlı partilerde kontrol edin

Yeni modülün adı: src.services.four_market_batch_validation. Bir çalıştırmada yalnızca bir parti; varsayılan 10, en fazla 25 hisse kontrol edilir. Varsayılan olarak geçmiş fiyat sorguları arasında iki saniye bırakılır. Geçmiş OHLCV, para birimi, son tamamlanan seans ve teknik analiz puanı hisse bazında kontrol edilir.

İlk parti için:

    & ".\.venv\Scripts\python.exe" -m src.services.four_market_batch_validation --manifest "$env:USERPROFILE\Documents\etre-source-400-plan.json" --as-of 2026-11-16 --output-dir "$env:TEMP\etre-400-batches" --batch-index 0 --batch-size 10 --resume

Sonraki parti için --batch-index 1; toplam 0..39 indeksleri. Bir kontrol başarısız olduğunda da ayrıntılı JSON raporu tutulur ve başarı koduyla çıkılmaz. Yalnızca aynı tarih, aynı kaynak SHA-256 imzası ve aynı parti parametreleriyle oluşturulan sağlam JSON dosyası --resume ile tekrar sorgulamadan geçilir.

İsteğe bağlı sıralı PowerShell döngüsü (uzun sürebilir ve Yahoo istek kısıtlarına tabidir):

    0..39 | ForEach-Object {
      & ".\.venv\Scripts\python.exe" -m src.services.four_market_batch_validation --manifest "$env:USERPROFILE\Documents\etre-source-400-plan.json" --as-of 2026-11-16 --output-dir "$env:TEMP\etre-400-batches" --batch-index $_ --batch-size 10 --resume
      if ($LASTEXITCODE -ne 0) { Write-Warning "Parti $_: eksik veya hatalı veri; rapor dosyasını kontrol edin." }
    }

## 2a. Bir partide yalnızca başarısız hisseleri yeniden deneme

Bir partide Yahoo veri erişimi kesilmişse veya hisse bazında teknik kontrol başarısızsa, baştan 10–25 hisseyi tekrar sorgulamak gerekmez. Normal `--resume` yalnızca önceden doğrulanmış raporu **değiştirmeden** okur. Bunun yerine `--retry-failed` kullanın:

    & ".\.venv\Scripts\python.exe" -m src.services.four_market_batch_validation --manifest "$env:USERPROFILE\Documents\etre-source-400-plan.json" --as-of 2026-11-16 --output-dir "$env:TEMP\etre-400-batches" --batch-index 0 --batch-size 10 --retry-failed

Bu komut yalnızca mevcut partinin `analyzed` olmayan hisselerine yeniden Yahoo fiyatı ve teknik kontrol uygular; başarılı hisseleri yeniden sorgulamaz. Eski raporu `batch-001-of-040.before-retry-01.json` gibi ayrı bir **denetim yedeğinde** koruyup yeni sonuçları atomik olarak kaydeder. Aynı parti için en fazla 5 yeniden deneme mümkündür; sonrasında sorunlu semboller ve kaynak ayrıca incelenmelidir. Başarısızlık devam ederse status yine başarısız kalır, başarı uydurulmaz.

`--retry-failed` ile `--resume` aynı anda kullanılamaz; eski rapor yoksa, bozulmuşsa veya kaynak kimliği/seans tarihi uyuşmuyorsa yeniden sorgulama başlamadan reddedilir. Yedekler saklanmalıdır; otomatik silinmezler. Aynı partiyi eş zamanlı iki ayrı süreçte çalıştırmayın.

## 3. Hisse bazındaki kontrol sonuçlarını birleştirin

    & ".\.venv\Scripts\python.exe" -m src.services.four_market_batch_validation --manifest "$env:USERPROFILE\Documents\etre-source-400-plan.json" --as-of 2026-11-16 --output-dir "$env:TEMP\etre-400-batches" --batch-size 10 --combine --report "$env:USERPROFILE\Documents\etre-400-historical-report.json"

Birleştirme yeni Yahoo isteği yapmaz. Tamamlanmış partilerin gerçek tarihini, kaynak kimliğini, her hisseyi ve rapor sayılarını doğrular. Raporda checked_symbols, analyzed_symbols, pending_symbols, missing_batch_indices, checked_all ve all_analyzed ayrı görünür. Dört piyasanın hepsi tamamlanmadıysa 400/400 kontrol edildi gösterilmez. Veri hatası olan hisseler başarı sayılmaz.

Birleştirilmiş JSON, ETRE Veri Merkezi içindeki mevcut dört piyasa rapor görüntüleyicisiyle uyumludur. Rapor fiyat geçmişi testidir; canlı fiyat, yatırım tavsiyesi, aracı kurum erişimi veya gerçek işlem değildir.

## Güvenlik sınırları

İşlem emri, Midas hesabı erişimi, SQLite veri yazımı, gizli anahtar veya LLM çağrısı yoktur. Kaynaklar yokken veya ağ istekleri yetkisizken modül işletilmemelidir. Testlerde sentetik hisse kodları kullanılır; bunlar gerçek borsa listesi veya 400 başarılı Yahoo fiyat verisi kanıtı değildir. Resmî ham dosyaların lisans şartlarına uyun.
