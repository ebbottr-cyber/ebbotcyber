# EBBot — BIST KAP şirketleri, gerçek işlem kayıtları ve ISIN eşleştirme denetimi

**Durum: Salt-okunur, çevrimdışı, yayın onayı vermez.** 21 Kasım 2026 itibarıyla BIST'in işlem gören payları ile KAP'ın şirket üyeliği ayrı kaynaklardır. `KAP'ta var` demek bir hissenin anlık olarak `BIST'te aktif, işleme açık, fiyatlı ve Türkiye'deki aracı kurumdan alınabilir` olduğu anlamına gelmez.

## Kontrol edilen ayrımlar

- **KAP aday şirket kodları:** Önceki PR #58'in yerel `kap-bist-all.csv` çıktısı `market,symbol,source,kind,observed_at_utc` başlığını taşır. KAP dosyasındaki 803 aday geçmişte yerelde görülmüş; bu dosya GitHub ana dalında yok ve bugünkü sayıya ilişkin garanti değildir.
- **Borsa İstanbul XIST pay referansı:** Ayrı, gerçekten elde edilmiş ve operatörün tarihini/sözleşmesini kontrol ettiği işleme açık/pay kaydı CSV'si gerekir. `active`, `halted` ve `delisted` durumları ayrı sayılır. Bu dosya yokken borsanın kaç aktif hissesi olduğu **bilinmiyor**, sıfır değil.
- **ISIN:** 12 haneli ISO 6166 biçimi ve check-digit algoritması incelenir. Geçerli check-digit menkul kıymet kimliğinin doğruluğunu, lisansı veya işlem iznini kanıtlamaz. Aynı ISIN'in iki farklı pay sembolüne eşleşmesi güvenli şekilde reddedilir.
- **Sağlayıcı:** İsteğe bağlı `mapping.csv` ile `provider` ve `provider_symbol` karşılaştırılır. İsteğe bağlı gerçek OHLCV dosyasındaki sağlayıcı sembolü de kontrol edilir; metaveri yoksa belirsizlik raporlanır, hatalı sembol reddedilir.
- **Güncellik:** Girdiler tarihli olmalı; gelecekteki kayıtlar reddedilir, yedi günden eski kaynaklar eski olarak işaretlenir. İki listedeki farklar asla otomatik silinmez veya eksik fiyat uydurularak doldurulmaz.
- **Kapsam:** Yalnız `market=tr`, `.IS` ile normalize edilmiş 3–8 harf/rakam pay kodu ve `mic=XIST`. Yatırım fonları/varantlar/VİOP/başka MIC türleri için bu rapor tam piyasa envanteri değildir; 100 sembol sınırı bulunmaz.

## Resmî kaynaklar

- [KAP BIST şirketleri](https://www.kap.org.tr/tr/bist-sirketler) — şirket üyeliği/kodları.
- [Borsa İstanbul işlem gören şirketler](https://www.borsaistanbul.com/sirketler/islem-goren-sirketler) — pay şirketleri için resmî başvuru noktası.
- [Borsa İstanbul Pay Piyasası veri sayfası](https://www.borsaistanbul.com/en/data/equity-market-data) — isim/kod değişiklikleri ve kalıcı kotasyon çıkışları dahil referans bilgileri.
- [Borsa İstanbul DataStore tarihsel veri](https://www.borsaistanbul.com/veriler/gecmise-donuk-veri-satisi) — geçmiş fiyatlar için ayrı erişim/sözleşme süreci.

**Bu linklerden veri çekilip veri lisansı alınmış değildir.** Kullanılacak gerçek pay listesi ve fiyat geçmişi operatörün erişim hakkı olan kaynaktan temin edilmelidir. KAP kaynaklı adayları BIST işlem referansı gibi kopyalayarak sahte eşleştirme YAPMAYIN.

## CSV biçimleri

Yerel eski KAP dosyası (PR #58) satırları:

```csv
market,symbol,source,kind,observed_at_utc
```

Alternatif olarak tarih alanı `source_as_of_date` olabilir. İkisi varsa aynı UTC günü göstermelidir. Gerçek kodları bu belgede örnek olarak üretmiyoruz.

Operatör tarafından ayrı kaynaktan edinilen gerçek BIST pay referans CSV dosyası başlığı:

```csv
market,symbol,isin,mic,listing_status,source,source_as_of_date
```

Bu araç, resmî borsa pay kodlarını `.IS` son ekiyle **daha önce kontrollü olarak normalize ettiğiniz** bir CSV bekler. Resmî kaynaklar doğrudan `.IS` takısını kullanmak zorunda değildir; `borsa kodu → .IS` kuralı ve ISIN kimliği bağımsız teyit edilmelidir. `listing_status` yalnızca `active`, `halted`, `delisted` olabilir. Başlık dışındaki alanları tahmin etmez.

Opsiyonel fiyat sağlayıcı eşlemesi (`--mapping`) başlığı:

```csv
market,symbol,provider,provider_symbol,source,source_as_of_date
```

Opsiyonel gerçek, yerel OHLCV (`--bars`) başlığı:

```csv
market,symbol,session,open,high,low,close,volume,source,currency,provider,provider_symbol
```

OHLCV hesapları mevcut **fiyat girişi içinde** kaç aktif sembolde en az bir mum bulunduğunu sayar. Girdi yoksa rakam **bilinmiyor** gösterilir. `source`/`provider` metin alanları lisans veya kimlik belgesi yerine geçmez.

## PowerShell komutları (repo kökünden)

Kaynak dosyaları bilgisayarda yokken (CI'da da çalışır):

```powershell
python -m scripts.audit_ebbot_bist_reference_identity
```

Bu çağrı `BLOCKED_MISSING_BIST_SOURCE_FILES` döndürür; kullanıcıya sahte 0 BIST hisse sayısı vermez.

Gerçekten temin edilmiş, ayrı ve tarihli referanslar mevcut olduğunda:

```powershell
python -m scripts.audit_ebbot_bist_reference_identity --kap "$HOME\EBBotPaperData\kap-bist-all.csv" --exchange "C:\ApprovedMarketData\bist-xist-equities.csv" --mapping "C:\ApprovedMarketData\tr-provider-symbols.csv" --bars "C:\ApprovedMarketData\staged-tr-ohlcv.csv" --report-json "C:\ApprovedMarketData\bist-identity-audit.json"
```

`--mapping` ve `--bars` isteğe bağlıdır; yoksa fiyat erişimi veya sağlayıcı kimliği onayı varmış gibi davranılmaz. Her dosya gerçek hakları bulunan yetkili veri kaynağından gelmelidir. `--report-json` yalnızca **yeni** yerel dosyaya, tam fark listelerini yazar ve dosyayı ezmez.

**Çıkış 0:** Denetim çalıştı, borsa veya lisans onaylanmış değildir. **Çıkış 1:** Girdi hatası/çelişki güvenli şekilde reddedildi. ISIN biçimi, KAP/işlem farkı, eski kaynak ve bağlı fiyatların geçerliliği bağımsız inceleme gerektirir.

## Sonraki gerçek engeller

- Yetkili ve güncel bir XIST pay işlemi referans listesi (ISIN, durum, tarih).
- Operatörün daha önce kullandığı **yerel** 803 KAP kodu dosyası; GitHub'a gizli/lisanslı içerik yüklenmemeli.
- Türkiye'de kullanılabilecek, lisans/otomatik analiz ve saklama hakları netleşmiş gerçek veri sağlayıcısı.
- Gerçek, lisanslı ve güncel OHLCV geçmişleri; kurumsal aksiyonlar, sembol değişiklikleri ve işlem durdurma günleri ayrıca çözümlenmeli.
- PR zinciri test edilip `main`e birleştirilmeden ve Windows gerçek kurulum testinden geçmeden yayına alınamaz.

**Yayın kapalı. Sanal ve gerçek emir kapalı.** Bu denetim işlemsel piyasa doğruluğu iddia etmez.
