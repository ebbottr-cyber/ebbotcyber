# EBBot — Dört piyasa veri eksiksizliği denetimi

**Durum: İNCELEME / GERÇEK İŞLEM VE SANAL EMİR KAPALI.** Bu denetim borsadaki tüm hisselere ait güncel fiyatların hazır olduğunu iddia etmez; eksik kanıtları görünür yapar.

## Kapsam

- Yalnızca **Türkiye (TR), ABD (US), Almanya/Xetra (DE), Hong Kong (HK)** hisse adayları incelenir. Eski CN/JP/KR/BSE kayıtları silinmez, yalnız dört-piyasa toplamına katılmaz.
- Ana kaynak `apps/dsa-web/public/stocks.index.json`; oradaki büyük harfli `US`/`HK` etiketleri doğru eşlenir. Aktif hisseler ve ETF türleri ayrı sayılır, endeksler ve pasif kayıtlar dışlanır. **100 sembol sınırı yoktur.**
- 19 Kasım 2026 tarihli resmî Xetra kaynağından türetilmiş **1.750 aday** `data/market_snapshots/de/xetra-candidates.csv` üzerinden otomatik eklenir; dosyanın SHA-256 özeti sabittir. Özet ham dosya baytları üzerinden hesaplanır; UTF-8 BOM veya CRLF değişikliği, görünen CSV satırları aynı olsa da kaynağın checksum kimliğini bozar ve denetim reddeder. Bu kayıtların `.DE` fiyat sembolü, borsa üyeliğinin bugünkü hali veya Türkiye'de aracı kurum erişimi ayrıca doğrulanmamıştır.
- BIST'in daha önce Windows bilgisayarında alınan 803 KAP şirket adayı GitHub'a yüklenmediği için otomatik mevcut sayılmaz. `--stocks` ile yerel kaynak dosyası ayrıca eklenebilir. KAP şirket kodu, işleme açık BIST hissesi kanıtı değildir.
- Eski ABD/HK endeksleri güncel resmî borsa listeleriyle doğrulanmamıştır. Kayıt sayısı fiyat verisi sayısı değildir.

## Kanıt denetimi nasıl çalışır?

1. Kaynak dosyaları tarih, sembol, tür ve biçim açısından okur; mükerrer kayıtları raporlar ve çelişkili türü reddeder.
2. `--bars` ile eklenen **gerçek günlük OHLCV** dosyalarının tarihini, açılış/en yüksek/en düşük/kapanış/hacim değerlerini, tutarsız mumları, tekrar eden günleri, NaN/sonsuz/sıfır fiyatları ve geleceğe dönük kayıtları denetler.
3. Varsayılan eşik bir hisse için **250 gözlenen günlük mum** ve son mum için en fazla **7 takvim günü** yaştır. Tatil/seans takvimini doğrulamadığından bu eşik *gerçek geçmiş eksiksizliği sertifikası değildir*.
4. Varsayılan terminal raporu hata başına ilk 10 örneği gösterir; **bütün sembol sayıları eksiksiz hesaplanır**. `--report-json` verildiğinde bütün eksik, eski ve yetersiz geçmiş sembolleri tam liste halinde yeni JSON dosyasına yazılır. Mevcut dosyayı ezmez.
5. Dosya başına 64 MiB limit bulunur; büyük OHLCV arşivlerini birkaç dosyaya bölüp `--bars` seçeneğini tekrarlayın.

## PowerShell komutları (depo ana klasöründe)

```powershell
python -m scripts.audit_ebbot_market_data_coverage
```

Bilgisayarınızdaki tarihli KAP/Xetra aday dosyalarını da eklemek için:

```powershell
python -m scripts.audit_ebbot_market_data_coverage --stocks "$HOME\EBBotPaperData\kap-bist-all.csv" --stocks "$HOME\EBBotPaperData\xetra-candidates.csv"
```

Bu örnekler yerel dosya yollarıdır; dosyanın gerçekten bulunması gerekir. Depodaki sabit Xetra listesi ayrıca otomatik okunur, tekrar verilmesi gerekli değildir.

Gerçek fiyat geçmişi CSV başlığı şu şekilde olmalıdır:

```csv
market,symbol,session,open,high,low,close,volume,source,currency
tr,THYAO.IS,2026-11-20,300,305,295,303,123456,ornek_kaynak,TRY
```

**Önemli:** Yukarıdaki OHLCV satırı yalnızca biçimi göstermek için *uydurulmuş bir örnektir*; gerçek fiyat değildir ve rapor dosyası olarak kullanılmamalıdır. Yalnız hak sahibi olduğunuz, gerçek sağlayıcıdan doğrulanmış dosyaları kullanın. `source` etiketi kendiliğinden lisans kanıtı değildir.

Tam eksik-sembol raporu ve güvenli yayın engeli:

```powershell
python -m scripts.audit_ebbot_market_data_coverage --stocks "$HOME\EBBotPaperData\kap-bist-all.csv" --bars "C:\ApprovedMarketData\tr-daily-2026.csv" --report-json "C:\ApprovedMarketData\ebbot-coverage.json" --strict
```

- Çıkış `0`: denetim çalıştı; **veri eksiksiz demek değildir**.
- Çıkış `1`: bozuk/güvenli olmayan giriş veya dosya.
- Çıkış `2`: `--strict` modunda borsa üyeliği, lisans, takvim, aracı kurum ve sağlayıcı eşlemesi bağımsız onaylanmadığı için **yayın engelli**.

Çevrimdışı test:

```powershell
python -m unittest discover -s tests -p 'test_ebbot_market_data_coverage.py' -v
```

## Gerçekten tamamlanması gerekenler

- **BIST:** KAP şirketlerinden aktif işlem sembolüne kesin eşleme, güncel BIST100 üyeleri, lisanslı günlük veri ve işlem takvimi.
- **ABD/Hong Kong:** 23.357 ABD ve 2.739 Hong Kong eski kayıtlarının resmî güncel listelerle karşılaştırılması, delist/kurumsal işlem ve doğru veri sağlayıcısı sembolü.
- **Almanya:** 1.750 Xetra adayının fiyat sembolü ve ISIN eşlemesi, güncel kotasyon ve onaylı geçmiş.
- **Dört piyasa:** Gerçek, lisanslı OHLCV geçmişi ve eksik seans kontrolü; fiyat zaman damgası/para birimi; Türkiye'den aracı kurum erişimi ve sözleşmeler.
- **Kripto/Solana:** Binance Spot/Futures ve Solana izleme işi ayrı geliştirmelerde (özellikle taslak PR #58) bulunuyor; hisse fiyat kapsamına karıştırılmamalı.
- **Birleştirme:** PR #58/#59 ve bu PR bağımsız incelenip güncel `main` üzerinde tam backend/React/Windows testinden geçirilmeli. Otomatik birleşim, veri yayını ve emir hâlâ kapalı.

Resmî kaynak araştırması: [KAP şirket listesi](https://www.kap.org.tr/tr/bist-sirketler), [Borsa İstanbul veri sağlayıcıları](https://www.borsaistanbul.com/en/data/data-dissemination/data-vendors-directory), [HKEX menkul kıymet listesi](https://www.hkex.com.hk/Services/Trading/Securities/Securities-Lists?sc_lang=en), [NasdaqTrader sembol tanımları](https://nasdaqtrader.com/Trader.aspx?id=SymbolDirDefs). Bunların web üzerinden görülmesi lisanslı otomatik fiyat çekme hakkı vermez.

**Yayın durumu: BLOKE.** Denetim olumlu çalışsa bile gerçek/paper emir, otomatik fiyat tarama, fon yönetimi ve canlı dağıtım açılmaz.
