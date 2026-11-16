# ETRE dört piyasa — gerçek 100'er hisse evreni hazırlama

Aktif yatırım kapsamı: Türkiye (BIST), ABD, Almanya (Xetra), Hong Kong (HKEX). Japonya/Çin/Güney Kore/Tayvan aktif yeni taramaya dahil değildir.

## Kaynak taraması — 16 Kasım 2026

- TR: Projede src/data/bist100_constituents_2026q4.json ve src/services/bist100_universe.py ile 01.10–31.12.2026 aralığında geçerli, kaynak karşılaştırması yapılmış 100 BIST100 üyesi vardır. Resmî duyuru + iki bağımsız tam liste kullanılır. Bu üyelik kanıtıdır, 100 Yahoo fiyat serisinin tamamı doğrulandı demek değildir.
- US: [S&P Dow Jones S&P 100](https://www.spglobal.com/spdji/en/indices/equity/sp-100/) büyük ABD şirketlerinin aday kaynağıdır. Her hisse sınıfı, kote pazar ve Yahoo kodu ayrı değerlendirilir. ADR/ETF/endeksler hisse listesine karıştırılmaz.
- DE: [ISS STOXX DAX/MDAX/SDAX değişiklikleri](https://www.iss-stoxx.com/press-releases/stoxx-announces-scheduled-adjustments-to-dax-blue-chip-indices-4/) ve [Deutsche Börse işlem gören kıymetler](https://www.cashmarket.deutsche-boerse.com/cash-de/Handel/Handelbare-Werte-Xetra/frankfurt) kaynak olabilir. DAX40 + MDAX50 + kaynaklı 10 farklı SDAX şirketi yalnızca aday seçim yöntemidir; Xetra işlem yeri ve Yahoo .DE kodları ayrı teyit edilmelidir.
- HK: [Hang Seng Composite HSCI](https://www.hsi.com.hk/en-hk/indexes/all-indexes/index-details/?seriesCode=hsci) yüzlerce hisse barındırır. Kasım 2026 Hang Seng Index HSI yaklaşık 95 bileşene sahip olduğundan, HSI tek başına 100 hisse gereksinimini garanti etmez. 100 ayrı HKEX hissesi HSCI veya resmî HKEX kayıtlarından teyit edilmelidir. HK00700 sembolü Yahoo'da 0700.HK olarak karşılanır.

Bunlar kaynak adaylarıdır; her pazarın 100 ayrı gerçek hissesinin tümü henüz otomatik çekilmiş ve teyit edilmiş değildir. Kaynak URL yazmak, kaynağın gerçekten doğrulandığının kriptografik kanıtı değildir. Endeks üyeliği ile aracı kurum işlem izni farklıdır.

## Yabancı piyasa için tarihli JSON

Her yabancı pazar için ayrı UTF-8 JSON dosyası gerekir. Şema örneği (bu iki kod 100 hisse yerine GEÇMEZ):

    {
      "market": "us",
      "as_of": "2026-11-16",
      "source_name": "S&P Dow Jones S&P 100 (operator verified)",
      "source_url": "https://www.spglobal.com/spdji/en/indices/equity/sp-100/",
      "symbols": ["AAPL", "MSFT"]
    }

Her piyasanın kendi dosyası olacak: us.json, de.json, hk.json. Her dosyada kaynakça doğrulanmış tam 100 benzersiz hisse bulunmalıdır. As-of tarihi gelecekte veya kontrol tarihinden 45 günden eski olamaz. Biçim denetimi, hisselerin gerçekten kote olduğunu veya Yahoo fiyat verisinin geldiğini kanıtlamaz.

## Windows PowerShell (yalnızca liste hazırlar)

Yerel kodun GitHub'dan çekilmiş olması gerekir.

    cd "$env:USERPROFILE\Projects\ebbotcyber-test"

    # Kaynaklı BIST100 listesini ayrı dışa aktar; 400 listesi yoksa üretme
    & ".\.venv\Scripts\python.exe" -m src.services.four_market_universe_plan --as-of 2026-11-16 --export-tr100 "$env:TEMP\etre-bist100.txt" --report "$env:TEMP\etre-four-market-readiness.json"

    # Kaynaklı üç yabancı 100-lük JSON dosyası tamamlandıktan sonra:
    & ".\.venv\Scripts\python.exe" -m src.services.four_market_universe_plan --as-of 2026-11-16 --us-roster "$env:USERPROFILE\Documents\us.json" --de-roster "$env:USERPROFILE\Documents\de.json" --hk-roster "$env:USERPROFILE\Documents\hk.json" --export-400 "$env:USERPROFILE\Downloads\etre-400-tickers.txt" --report "$env:TEMP\etre-four-market-readiness.json"

Yalnızca BIST100 mevcutken rapor 100/400 üyelik listesi hazır, 300 eksik şeklinde görünür. 400 kodluk dosya yabancı pazar listeleri sağlanmadan üretilmez. Dört pazarın tamamında üyelik/sözdizim/para birimi tarih denetimi geçse bile, Yahoo verisi ayrı kontrol edilir.

ETRE Veri Merkezi → Dört piyasa · 400 hisse listesi hazırla → Kaynaklı BIST100 listesini ekle düğmesi mevcut dönem tarihli TR100 listesini API'den getirir; ABD/DE/HK girdilerini değiştirmez. Dönem bitince eski Türkiye listesini başarı gibi sunmaz.

Bu özellik SQLite'a yazmaz, yeni canlı veri çekmez, gerçek emir göndermez. 400 hisse için gerçek günlük fiyat ve teknik analiz başarısı henüz gösterilmemiştir.
