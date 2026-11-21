# EBBot PR #180 + PR #188 birleşik taslak (21 Kasım 2026)

Bu belge **yayın veya main birleştirme onayı değildir**.

## Kaynak commitler

- Windows / SQLite / strateji ve 1.529 React testli PR #188: `eed661f457855176d7b8b9bfd7bcbd0470da7c86` (birinci ebeveyn).
- Backend auth, Türkçe rapor, required gate, 1.409 test kimlik kontrolü, Pandas uyarı azaltma PR #180: `ef9a293921a32dd06b90d2a9d0ef6bdc239e4d07` (ikinci ebeveyn).
- Ortak eski main: `b31c8195bd9650af8c3faa5e3f88fd576c14ab21`.

## Birleştirme yöntemi

1. PR #188'in tüm ağacı korunur. PR #180'in main'e göre değişmiş ve PR #188'de dokunulmamış **30 yolu** tam Git blob SHA'larıyla taşınır (bir eski İngilizce ETRE belgesinin silinmesi dahil).
2. 37 ortak değiştirilmiş yoldan **25'i birebir aynı Git blobu**. Geriye kalan **12 farklı dosya yalnızca React testleridir**. Gerçek `git merge-tree` bunların dokuzunda içerik çakışması bulmuştu; ilk taslakta 12 dosyanın da PR #188 test sürümleri korunur. Bu **nihai semantik test uzlaştırması değildir**. Eski test kimliklerini / güvenlik gereksinimlerini eksiltme ihtimali ayrıca denetlenecektir.
3. Geçici Git worktree provası, üretim koduna dokunmadan dokuz çatışmalı testte #188 tarafını seçti ve [CI #44899516690](https://github.com/ebbottr-cyber/ebbotcyber/actions/runs/44899516690) içinde **1.530 React PASS, 0 skip, 0 fail, lint/build PASS** verdi. Bu sonuç yalnızca geçici ağaca aittir; yeni commitin CI sonucuna otomatik aktarılmaz.
4. Bu kalıcı taslağın Git ağacı, gerçek merge-tree ile **tam eşdeğer olmayabilir**: özellikle otomatik birleşmiş üç farklı test dosyası ve `PortfolioPage` FX güvenliği ayrıca incelemeye açıktır. Bu nedenle aynı SHA'da tam CI ve bağımsız review zorunludur.

## Açık güvenlik kapısı

- `.github/ebbot-react-test-baseline.sha256` orijinal **1.409 test kimliğine** ait. Birleşimde 1.530+ test beklenir. Fingerprint geçmezse **fail-closed** kalmalı; gerçek JUnit isimlerinin bağımsız incelemesi ve onayı olmadan baseline otomatik yenilenmemeli. Test kimliğinin bilinçli değişmesi ayrıca açıklanmalı.
- Tam backend (4 canlı ağ testi ayrı), auth/Türkçe, React/JUnit, ESLint/TS/Vite, Windows PyInstaller/NSIS/SQLite kontrolleri **bu yeni commit üzerinde** yeniden çalışmalıdır.
- Portföyde kaynak/tarih doğrulanmadan sahte TRY/FX toplamı gösterilmez; Türkçe varsayılan ve yanlış dilli veriler güvenli biçimde korunmalı.
- Main dalında aktif koruma ruleset'i yok (`main.protected=false`). [Issue #183](https://github.com/ebbottr-cyber/ebbotcyber/issues/183) ve bağımsız onay tamamlanmadan draft kaldırılmaz, main merge/deploy/release yapılmaz.

**Otomatik scheduler/analiz, otomatik güncelleme, installer yayını ve gerçek/sanal broker alım-satım kapalı kalır.**
