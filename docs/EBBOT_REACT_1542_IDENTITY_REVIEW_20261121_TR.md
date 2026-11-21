# EBBot — 1.530 → 1.542 React JUnit kimlik geçişinin kanıta dayalı incelemesi

## Durum

Bu referans yalnız **taslak PR #205** için oluşturuldu, bağımsız insan incelemesi ve main branch koruması tamamlanmadan birleştirme/yayın izni vermez. Etkin test kapısı **zayıflatılmadı**: 0 fail / 0 skipped, exact testcase kimlik SHA-256 ve yeni `--min-tests 1542` zorunludur.

## Orijinal kanıt ve dosyalar

- **Eski PASS:** [PR #188 required gate run #44902552528](https://github.com/ebbottr-cyber/ebbotcyber/actions/runs/44902552528), commit `b0eb3405e42acb464a5b0d517f09d3b32e7856a7`, JUnit artifact ID `14706313441`. **1.530 PASS, 0 FAIL, 0 SKIP**, hash `bf6be809ecd5e1e097a0bb53f9de7d531cd73ca11f13005d4d396bf2aaebe0d4`.
- **Yeni PASS test sonucu:** [PR #205 required gate run #44910934656](https://github.com/ebbottr-cyber/ebbotcyber/actions/runs/44910934656), commit `fa737080ba224e21b31607b38ec718cd396d9362`, JUnit artifact ID `14710305317`. **1.542 PASS, 0 FAIL, 0 SKIP** ve `125/125` test dosyası, hash `2b2fc969f37bfbd85bf91aa681c66dc3db5577b398a8f560bb7d76319ffd4abb`.
- Bu yeni koşudaki **React job** yalnız eski identity hash'in değişmesi nedeniyle kırmızıydı. İş yapan testlerin tamamı yeşildi; sıfır hata/skip JUnit XML içinde doğrulandı. Yeni commitin tam required-gate / backend / Windows sonucu ayrıca doğrulanmalıdır.

## Matematiksel yöntem ve fark

Her JUnit `testcase` için `(classname, name)` okunur, tekrar eden kimlikler **silinmeden** sıralanır, `json.dumps(sorted(identities), ensure_ascii=False, separators=(',', ':'))` çıktısının UTF-8 SHA-256 özeti alınır. Her iki artifact ZIP'indeki gerçek `vitest-results.xml` dosyası ayrı okunup çoklu küme farkı hesaplandı.

**Sonuç: +12 yeni test, 0 silinen/yeniden adlandırılan test, 0 skip ve 0 başarısız.**

### Yedi yeni BIST kimlik paneli testi

1. `BistIdentityPanel > clearly blocks local report visibility while admin authentication is disabled`
2. `BistIdentityPanel > does not show optimistic data when API request fails`
3. `BistIdentityPanel > keeps source files missing status unknown`
4. `BistIdentityPanel > marks supplied source as stale instead of displaying it as verified`
5. `BistIdentityPanel > never invents zero stocks when local report is absent`
6. `BistIdentityPanel > shows KAP versus BIST differences separately and disclaims verification`
7. `BistIdentityPanel > shows unknown rather than zero OHLCV when no bars file was provided`

JUnit `classname` tümünde `src/components/data-center/BistIdentityPanel.test.tsx`.

### Beş yeni dört piyasa paneli testi

1. `EquityCoveragePanel > blocks operator market data display when administrator auth is disabled`
2. `EquityCoveragePanel > does not silently show zero market data when API fails`
3. `EquityCoveragePanel > shows a non-trading explanation when no local report is configured`
4. `EquityCoveragePanel > shows four markets and transparent counts from a non-verified report`
5. `EquityCoveragePanel > warns on stale audit evidence`

JUnit `classname` tümünde `src/components/data-center/EquityCoveragePanel.test.tsx`.

## Bağımsız inceleyicinin onaylaması gerekenler

- Kaynaktaki test adları gerçekten panelin auth-off gizlilik, bozuk/eksik fiyat, eski rapor ve yayınlanmaya hazır değil davranışlarını ölçüyor mu?
- PR #205'te `DataCenterPage.test.tsx` tarihî 4 testin mock'u yeni panel fonksiyonlarını **fail-closed Promise rejection** ile karşılıyor. Dört testin adı ve orijinal beklentileri korundu mu? JUnit farkında bu dört eski kimliğin hiçbiri silinmedi.
- Python'daki sibling test fixture importu paketli `tests.*` yoluyla düzeltilirken backend testleri atlanmadı mı?
- Yeni Windows PyInstaller/NSIS gerçek paketleme (publish ve installer execution yok), main protection ve independent review engelleri hâlâ açık mı?
- `.github/ebbot-react-test-baseline-1409.sha256` ve `.github/ebbot-react-test-baseline-1530.sha256` arşivli; yeni `.github/ebbot-react-test-baseline.sha256` yalnız kanıtlı 1.542 identity hash'i içeriyor mu?

**Önemli:** `0 skip` veya tüm testlerin yeşil olması piyasa lisansı, canlı fiyat, broker erişimi, otomatik trading, gerçek Windows kurulum/imzalama veya main birleştirme onayı anlamına gelmez.