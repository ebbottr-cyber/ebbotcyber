# EBBot — 1.409 → 1.530 React test kimliği fark incelemesi (TASLAK)

Bu belge *otomatik test baselinena körü körüne güvenmeyen*, gerçek iki JUnit XML çıktısı karşılaştırılarak hazırlanan denetlenebilir geçiş raporudur. **Bağımsız insan kod incelemesi ve main dal koruması olmadan birleştirme/yayın onayı değildir.**

## Sabit GitHub CI kaynakları ve değişmez SHA-256

| Kaynak | Kanıt |
|---|---|
| Önceki #180 commit | `ef9a293921a32dd06b90d2a9d0ef6bdc239e4d07` |
| Önceki CI | [#44895100078](https://github.com/ebbottr-cyber/ebbotcyber/actions/runs/44895100078), JUnit artifact **14703209470** (`ebbot-combined-react-vitest-truth/vitest-results.xml`) |
| Eski JUnit | **1.409 test, 0 skip, 0 hata** |
| Eski kimlik SHA-256 | `dd129ec976c816d456e852aedb523e7894dd119f71ff169971b2832cde546f1c` |
| Yeni birleşik #188 commit | `b1b1867efba49fbfa688eaa4a1acd24205c3ae3f` |
| Yeni required-gate CI | [#44900003831](https://github.com/ebbottr-cyber/ebbotcyber/actions/runs/44900003831), JUnit artifact **14705458409** |
| Yeni JUnit | **1.530 test, 0 skip, 0 hata**; testler geçiyor, eski kimlik özetiyle doğrulama ise beklenen şekilde kırmızı |
| Yeni kimlik SHA-256 | `bf6be809ecd5e1e097a0bb53f9de7d531cd73ca11f13005d4d396bf2aaebe0d4` |

Her iki **gerçek JUnit XML** dosyası indirildi. Test kimlikleri `(classname, name)` çiftleriyle, **tekrarları koruyan** bir çoklu küme olarak karşılaştırıldı. Sıralanmış çiftlerin UTF-8 JSON'u üzerinden `sha256(json.dumps(sorted(identities), ensure_ascii=False, separators=(',', ':')))` yeniden hesaplandı. Önceki ve yeni SHA'lar ilgili CI loglarıyla **birebir eşleşti**.

**Tam fark: 125 eklenen, 4 çıkarılan/yeniden adlandırılan kimlik; net +121 test.** Her iki JUnit çıktısında da iki adet yinelenen test kimliği vardı; eşit sayı yanılgısına düşmemek için çoklu küme karşılaştırması yapıldı.

## Eksilen 4 kimliğin semantik incelemesi

1. **Eski tek hesap döviz görünümü** — `PortfolioPage FX refresh > converts single-account foreign-currency exposure values into the snapshot currency`. Eski test CNY toplamını doğrudan gösteriyordu. Yeni `keeps legacy single-account foreign exposure amounts hidden without verified TRY quotes`, `does not relabel single-account legacy CNY exposure as TRY without fresh FX quotes` ve `portfolioTryDisplay` doğrulanmış kur testleri, güvenilmeyen TRY gösterimini fail-closed yapıyor. **FX kaynak doğruluğu bağımsız değerlendirilmelidir.**
2. **Eski karma hesap döviz görünümü** — `PortfolioPage FX refresh > converts mixed CNY and USD accounts using per-account aggregate market values`. Yeni `preserves mixed-account aggregate exposure weights without inventing TRY quotes`, `hides mixed-currency exposure values until trustworthy TRY conversion is available` ve `sums account-native CNY and USD amounts in TRY, not the CNY aggregate` testleri, uydurma çapraz döviz toplamlarını engelliyor.
3. **Türkçe sağlayıcısız başlık** — `StockScreeningPage > renders a Turkish screening heading without a language provider`. Yeni `falls back to a Turkish screening heading without a language provider` testi, aynı **Hisse Tarama** başlığını ve Çince başlığın görünmemesini gerçekten test ediyor; ayrıca açıkça Türkçe seçili test var.
4. **Koyu tema varsayılanı** — `index.html theme bootstrap > preloads dark mode before React mounts and respects stored theme values`. Yeni `preloads the current light theme default before React and respects saved dark/light choices` testinde varsayılan açık tema; kayıtlı light/dark seçimi hâlâ korunuyor. **Ürün varsayılanının açık tema olmasına bağımsız inceleme/onay gereklidir.**

## Eklenen 125 kimlik — 21 kaynak dosyasının test sayıları

| Yeni test dosyası / ek senaryo alanı | Ek kimlik |
|---|---:|
| Solana Radar API namespace | 2 |
| Dashboard özet kartları | 9 |
| Mum grafiği ve doğrulanmış OHLC | 5 |
| Türkiye piyasa kartları | 6 |
| Sentetik strateji kanıtı | 6 |
| Sentetik strateji raporu | 11 |
| AI model kanalı Türkçesi | 2 |
| Strateji günlüğü | 4 |
| Alarm ekranı Türkçesi | 1 |
| Sohbet ekranı Türkçesi | 1 |
| MemeCoin ekranı / işlemsiz güvenlik | 28 |
| Portföy döviz güvenliği | 10 |
| Ayarlar ilk kurulum Türkçesi | 1 |
| Hisse tarama Türkçe senaryoları | 2 |
| Strateji Laboratuvarı | 5 |
| Portföy defteri Türkçesi | 4 |
| Gerçek TRY döviz dönüşümü kuralları | 12 |
| Kurulum metinlerinin yerelleştirilmesi | 6 |
| Sistem dili ve tarih metinleri | 3 |
| Teknik gösterge matematiği | 6 |
| Açık tema ve kayıtlı tercih | 1 |
| **Toplam** | **125** |

## Fail-closed kabul politikası

- **Eski baselinena dokunulmadan saklandı:** `.github/ebbot-react-test-baseline-1409.sha256` = `dd129ec976c816d456e852aedb523e7894dd119f71ff169971b2832cde546f1c`.
- Yeni taslak aktif referans `.github/ebbot-react-test-baseline.sha256` = `bf6be809ecd5e1e097a0bb53f9de7d531cd73ca11f13005d4d396bf2aaebe0d4`, yalnız *bu iki JUnit XML kanıtındaki* gerçek test kimliklerinden çıkarıldı.
- `.github/workflows/ebbot-final-acceptance.yml` artık **en az 1.530** test ister. Başarısız/atlanan/kimliği kaymış testler **kesin red**. Doğrulayıcı `scripts/validate_vitest_junit.py` değiştirilmedi veya gevşetilmedi.
- Her yeni test/değişiklikte aynı review+JUnit fingerprint prosedürü tekrarlanmalı.
- CI yeşile dönse bile **bağımsız review, 9 çatışmalı test dosyasının davranış incelemesi, GitHub [#183 main koruma ruleseti](https://github.com/ebbottr-cyber/ebbotcyber/issues/183), Windows gerçek cihaz kurulum/güncelleme, broker ve canlı fiyat doğrulaması** ayrı kapılardır. Bunlar olmadan main merge, release, scheduler, auto trading ve gerçek/sanal emir **YOK**.
