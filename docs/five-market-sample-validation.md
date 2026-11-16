# ETRE — Dört piyasa, piyasa başına 100 hisse hedefi (taslak)

**Aktif yatırım/örnek veri kontrolü kapsamı:** 🇹🇷 Türkiye (BIST), 🇺🇸 ABD (NYSE/Nasdaq), 🇩🇪 Almanya (Xetra), 🇭🇰 Hong Kong (HKEX). **Japonya, Çin, Güney Kore ve Tayvan bu ETRE yatırım kapsamına dahil değildir.** Mevcut geçmiş veri ve eski arka uç testleri veri bütünlüğü için silinmez. Tekil şirketin aracı kurumda işlem izni ayrıca doğrulanmalıdır.

## Hedef, kapsam ve mevcut gerçek durum

| Piyasa | 100-hisse hedefi | Temel veri örneği | İkinci örnek | Para birimi |
|---|---:|---|---|---|
| Türkiye | 100 | \`THYAO.IS\` | \`ASELS.IS\` | TRY |
| ABD | 100 | \`AAPL\` | \`MSFT\` | USD |
| Almanya | 100 | \`SAP.DE\` | \`SIE.DE\` | EUR |
| Hong Kong | 100 | \`HK00700\` → \`0700.HK\` | \`HK01810\` → \`1810.HK\` | HKD |
| **Toplam** | **400** | 4 temel örnek | 4 ek örnek | |

**Önemli:** 100 x 4 şu anda **istenen tarama kapasitesi**, 400 hissenin mevcut/veri yönünden hazır olduğu iddiası değildir. Dört piyasanın her birinden 100 gerçek, o tarihte aktif ve uygun hisseden oluşan **güvenilir sembol listeleri** ayrıca içeri aktarılmalı ve veri kalitesi doğrulanmalıdır. Sahte sembol oluşturulmaz; sembol biçiminin doğruluğu kote olduğunun kanıtı değildir.

\`core\` modu her piyasadan 1 gerçek veri örneği (toplam 4); \`expanded\` modu her piyasadan 2 örnek (toplam 8) denetler. \`--symbols\` veya \`--symbols-file\` seçeneği, **tek piyasada en fazla 100**, toplam **en fazla 400** farklı hisse kodunu tamamen kontrol eder; 101'inci kod, yinelenen kod ve Japonya/Çin/Kore/Tayvan kodu ağ sorgusuna başlamadan reddedilir. Sonuçta \`target_symbols_per_market=100\`, \`target_symbols_total=400\`, \`remaining_to_target\`, \`checked_symbols\`, \`analyzed_symbols\`, \`markets_checked\` ve her piyasa için ayrı \`by_market\` sayaçları bulunur. **Bir hisse başarısızsa başarıya dahil edilmez.**

Kontroller Yahoo Finance günlük OHLCV tarihçesini, tamamlanan işlem gününü, fiyatın güncelliğini, gözlenen TRY/USD/EUR/HKD para birimini ve teknik analiz puanını kullanır. Geçmiş verinin başarılı kontrolü **anlık fiyat, 400 hisse tam kapsaması, AI yatırım tavsiyesi veya aracı kurum emir yetkisi** değildir.

## Windows PowerShell — yerel ve isteğe bağlı

Çalıştırmadan önce GitHub dalındaki değişiklikler yerel test kopyasına çekilmeli ve Python bağımlılıkları hazırlanmalıdır.

\`\`\`powershell
cd "$env:USERPROFILE\Projects\ebbotcyber-test"

# Küçük doğrulama
& ".\.venv\Scripts\python.exe" -m pytest -q tests/test_five_market_sample_validation.py tests/test_five_market_report_reader.py
& ".\.venv\Scripts\python.exe" -m src.services.five_market_sample_validation --sample-set core --as-of 2026-11-15 --output "$env:TEMP\etre-four-market-core.json"

# Kullanıcının seçtiği hisseler için (Japonya desteklenmez)
& ".\.venv\Scripts\python.exe" -m src.services.five_market_sample_validation --symbols "THYAO.IS,AAPL,SAP.DE,HK00700" --as-of 2026-11-15 --output "$env:TEMP\etre-four-market-selected.json"

# Tam liste bulunduğunda: UTF-8, satır veya virgül ayrılmış, piyasa başına en fazla 100 hisse
& ".\.venv\Scripts\python.exe" -m src.services.five_market_sample_validation --symbols-file "$env:USERPROFILE\Documents\etre-400-tickers.txt" --output "$env:TEMP\etre-four-market-400.json"
\`\`\`

**Not:** Eski dahili Python dosya adı \`five_market_sample_validation.py\` geriye dönük uyumluluk için korunmuştur; *aktif* \`FOCUS_MARKETS\` listesi 4 piyasadır. Raporun \`scope\` kimliği \`etre_four_market_...\` biçimine çevrilmiştir; eski beş-piyasa/Japonya raporları yeni arayüzce geçersiz sayılır.

## ETRE Veri Merkezi — salt okunur rapor görüntüleme

Taslak PR #11'de \`four-market-core-live-yahoo\` işi 4 örneği kontrol eder. Başarılı olduğunda \`etre-four-market-sample-<run_id>\` artifact'ındaki JSON raporu indirip Veri Merkezi → **Dört piyasa · 400 hisse hedefi** → JSON raporu seç menüsünden açabilirsiniz.

Sunucuda zaten üretilmiş ve doğrulanmış rapor bulunuyorsa, yönetici oturumuyla \`GET /api/v1/data/four-market/samples\` üzerinden otomatik görüntülenebilir. Bu erişim **varsayılan olarak kapalıdır**. Sunucu yöneticisi, yönetici oturum doğrulamasını etkinleştirip yalnızca kendi belirlediği **mutlak** rapor yolunu \`ETRE_FOUR_MARKET_REPORT_PATH\` değişkeniyle ayarlar. Sunucu URL'den dosya yolu kabul etmez, maksimum 2 MB JSON okur, 400 toplam/100 piyasa sınırlarını doğrular; yetki yoksa veya rapor geçersizse rapor sunmaz. Dosya seçimi tarayıcıda kalır ve sunucuya yüklenmez.

Gösterilen \`Hedefe kalan\` sayısı başarılı analiz sayısını değil **henüz kontrol edilmeyen hisse sayısını** ifade eder. Kontrol edilip veri hatası yaşayan hisseler ayrı olarak başarısız gösterilir. \`4/400\` yalnızca 4 örneğin kontrol edildiğini anlatır; tamamlanmış bir 400-hisse taraması değildir.

## Bilinçli olarak yapılmayanlar

Bu arayüz yeni veri taraması başlatmaz, kendi kendine 400 hissenin tam listesini oluşturmaz, SQLite'a yazmaz, gerçek emir vermez ve Midas/başka bir aracı kuruma bağlanmaz. Sonraki önemli geliştirme, her piyasanın resmi ve güncel 100-hisselik evrenini doğrulayarak tarama listelerini üretmek ve daha sonra güvenli, kademeli veri kontrolleri yapmaktır.
