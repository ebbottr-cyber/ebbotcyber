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

## KAP Pazarlar tarihli envanterini fiyat üretmeden hazırlama

KAP'ın [resmî Pazarlar](https://www.kap.org.tr/tr/Pazarlar) sayfası KAP kodu ve şirket/fon adı sunar. Bu kodu veri sağlayıcı sembolü, ISIN veya aracı kurum emriyle otomatik eşleştirmek güvenli değildir. Bu yüzden yeni `scripts/audit_ebbot_kap_market_inventory.py` yalnızca bağımsız inceleme bekleyen **aday KAP kodlarını** sayar. Eski dört piyasa OHLCV raporunda BIST=0 kalır; yeni fiyat veya `.IS` sembolü türetilmez.

Operatör, KAP'taki pazar kayıtlarının orijinal hâlini ve indirme tarihini ayrıca saklayıp çalışma kopyasını UTF-8 CSV'ye dönüştürmelidir. Dosya şu sütunlara sahip olur: `pazar,kap_kodu,unvan,kaynak_tarihi,isin`. `isin` sütunu isteğe bağlıdır. Her satırın kaynak tarihi, verilen snapshot tarihiyle aynı olmalıdır.

Kabul edilen pazar değerleri: `YILDIZ PAZAR`, `ANA PAZAR`, `ALT PAZAR`, `YAKIN İZLEME PAZARI`, `PİYASA ÖNCESİ İŞLEM PLATFORMU`, `YAPILANDIRILMIŞ ÜRÜNLER VE FON PAZARI`. Ayrıca resmî Pay Piyasası altında listelenen `GİRİŞİM SERMAYESİ PAZARI` ve `EMTİA PAZARI` kayıtları yalnız **ayrı fon/emtia kanıtı** olarak alınır; hisse adayı sayısına katılmaz. Sekiz segmentten bazıları eksikse rapordaki `all_eight_pay_market_segments_present=false` değeri bunu açık gösterir. Bu alan da kaynak kanıtı veya veri lisansı onayı değildir. Son gruptaki fon/yapılandırılmış ürünler ayrı sayılır.

Dosya gerçek olarak mevcutsa, Windows PowerShell'de aşağıdaki dosya adını ve tarihi **kendi dosyanıza göre** değiştirerek çalıştırın:

```powershell
$dosya = 'C:\ApprovedMarketData\kap-pazarlar-2026-11-21.csv'
$ozet = (Get-FileHash -Path $dosya -Algorithm SHA256).Hash.ToLowerInvariant()
python -m scripts.audit_ebbot_kap_market_inventory --csv $dosya --sha256 $ozet --source-url 'https://www.kap.org.tr/tr/Pazarlar' --snapshot-date '2026-11-21' --report-json 'C:\ApprovedMarketData\kap-pazarlar-review.json' --strict
```

**Kanıt sınırı:** Verilen SHA, yalnızca normalleştirilmiş çalışma CSV'sinin ham bayt bütünlüğünü ispatlar; resmî KAP kaynağından geldiğini tek başına kanıtlamaz. `--source-url` yalnızca iddia edilen KAP kaynağının şeklini kontrol eder, ağdan indirme yapmaz. Asıl belgenin bağımsız kaynak/eşleme kontrolü şarttır.

Bu araç eski dosyanın üzerine yazmaz; ham bayt SHA, bozuk/gelecek/mükerrer kaynak, geçersiz ISIN biçimi ve farklı tarihler güvenli şekilde reddedilir. Asgari kanıt olmadan sonuç `REVIEW_ONLY_UNMAPPED_KAP_CODES`, eski tarihli kaynakta `BLOCKED_STALE_KAP_SNAPSHOT`; `--strict` her koşulda çıkış 2 ve yayın engeli verir. Çıkış 0 yalnızca CSV'nin **okunabildiği** anlamına gelir.

Tam JSON raporunda pazar bazında **bütün** KAP kodları tutulur, terminalde ilk 10 örnek gösterilir. Araç `verified_provider_symbols=0`, `approved_broker_symbols=0`, `verified_ohlcv_bars=0`, `network_requests=0`, `orders=0` tutar. Semboller `--stocks` üzerinden doğrulanmış fiyat envanterine otomatik aktarılmaz.

Çevrimdışı regresyon:

```powershell
python -m unittest discover -s tests -p 'test_ebbot_kap_market_inventory.py' -v
```

Resmî pay işlem sırası ve ISIN, sağlayıcı sembolü, broker sembolü ve gerçek lisanslı OHLCV hâlâ ayrı onay gerektirir. [İş takibi #197](https://github.com/ebbottr-cyber/ebbotcyber/issues/197).
## KAP şirket kodu → BIST işlem sırası / ISIN kaynak eşlemesi

KAP kaynak sınıflandırması tek başına `THYAO.IS` gibi fiyat sağlayıcısı sembolünü doğrulamaz. İkinci bağımsız, salt-okunur `scripts/audit_ebbot_kap_bist_crosswalk.py` aşaması **iki ayrı tarihli operatör girdisini** karşılaştırır. Resmî Borsa İstanbul'un [Pay Piyasası Verileri](https://www.borsaistanbul.com/veriler/pay-piyasasi-verileri) sayfası ve [gün sonu veri formatı](https://www.borsaistanbul.com/files/dosya-paylasim-prensipleriA5F9EE60FF8A64B34D9AABEE.pdf), kaynakların kod ve tarih bazında ayrılmasına dayanak sağlar. Kaynaktaki veri/haklar saklanmalı; CSV kökeni salt `source_url` metniyle ispatlanmış sayılmaz.

BIST kaynak veri kopyası operatör tarafından hak ve formatlar kontrol edilerek şu sütunlarda hazırlanır:

```csv
kap_kodu,bist_islem_kodu,pazar,isin,kaynak_tarihi
```

Bu satırlar **gerçek piyasa sembolleri yerine örnek şemadır; asıl eşleme eklenmeden fiyat adı üretmeyin.** KAP dosyası önceki `pazar,kap_kodu,unvan,kaynak_tarihi,isin` şemasında bulunmalıdır. ISIN boş kalabilir fakat `instruments_without_isin` olarak raporlanır; var olan KAP ve BIST ISIN değerleri çelişirse tüm denetim durur.

GitHub'da `BIST_CSV` veya fiyat eklenmemiştir; aşağıdaki örnek dosya yolunu, tarihi ve hesaplanan SHA değerini yerel **gerçek kaynağınıza göre** değiştirin:

```powershell
$kap = 'C:\ApprovedMarketData\kap-pazarlar-2026-11-21.csv'
$bist = 'C:\ApprovedMarketData\bist-pay-2026-11-21.csv'
$kapSha = (Get-FileHash -Algorithm SHA256 -Path $kap).Hash.ToLowerInvariant()
$bistSha = (Get-FileHash -Algorithm SHA256 -Path $bist).Hash.ToLowerInvariant()
python -m scripts.audit_ebbot_kap_bist_crosswalk --kap-csv $kap --kap-sha256 $kapSha --kap-date '2026-11-21' --bist-csv $bist --bist-sha256 $bistSha --bist-date '2026-11-21' --report-json 'C:\ApprovedMarketData\kap-bist-crosswalk.json' --strict
```

Dosyalar hazır değilse `--bist-csv`, `--bist-sha256` ve `--bist-date` parametrelerini birlikte çıkarın; raporda tüm KAP kodları `kap_codes_without_declared_instruments_full` altında bekleyen olarak görünür.

Kontroller: iki kaynağın ham bayt SHA-256'sı, geleceğe ait/eski/karışık kaynak tarihleri, pazar eşleşmesi, KAP envanterinde olmayan kod, fon/emtia kodunun hisse sayılması, başka şirkete atanmış aynı işlem kodu veya mükerrer ISIN, çok işlem sıralı şirketlerin ayrı bayraklanması ve 100'den fazla kodun kesilmeden raporlanması.

Bu çıktı her durumda `BLOCKED_UNVERIFIED_BIST_CROSSWALK` veya `BLOCKED_STALE_CROSSWALK` olur; **iki CSV'nin birbiriyle tutarlı olması bağımsız resmî kaynak doğrulaması değildir.** Çıkış 0 yalnız başarılı yerel denetimi, `--strict` çıkış 2 ise yayın ve trading engelini gösterir. ISIN, sağlayıcı sembolü, broker sembolü, lisans, OHLCV ve erişim hakkı doğrulama bayrakları `false` kalır. KAP ile BIST'teki bir şirketin birden fazla pay kodu olabilir; bunlar otomatik tekilleştirilmez.

Bir sonraki ayrı adım PR #199'daki genel `provider_symbol` + gerçek OHLCV/işlem seansı eşleme denetimidir; bu aşamaya sadece **bağımsız doğrulanmış BIST işlem kodları** aktarılmalıdır, otomatik API veya emir bağlantısı yoktur.

Çevrimdışı regresyon:

```powershell
python -m unittest discover -s tests -p 'test_ebbot_kap_bist_crosswalk.py' -v
```

Kaynaklar, tekilleştirme, gerçek işlem sırası ve ISIN bağımsız kontrolü tamamlanana kadar [BIST envanter işi #197](https://github.com/ebbottr-cyber/ebbotcyber/issues/197) açıktır; veri kapsamı hâlâ `BLOCKED_INCOMPLETE_EVIDENCE`.