# EBBot — Windows Türkçe React smoke: menü etiket uyumsuzluğu düzeltmesi

**TASLAK — RELEASE BLOCKED.** PR #176'ya bağlı bu yama sadece paketli, CI'ya özgü Electron React smoke testini düzeltir. Uygulama menüsü, Türkçe çeviriler, gerçek API, kullanıcı dosyaları ve üretim başlangıç akışı değiştirilmez.

## Kanıt ve kök neden adayı

PR #176 Windows `push` çalışması [44885281323](https://github.com/ebbottr-cyber/ebbotcyber/actions/runs/44885281323) gerçek PyInstaller backend, NSIS `--publish never`, sentetik SQLite WAL snapshot, SHA-512 paketi, donmuş backend loopback ve Electron splash/preload testlerinden geçti. **Son Türkçe React Chromium navigasyon testi** `expected exit=42, actual=2` ve `Timed out while waiting for packaged React route` hatası verdi; Windows iş akışı **failure**. Diğer tam backend, React, PWA, TypeScript, Solana ve Node kaynak iş akışları aynı PR head'inde başarılıydı.

Sürümdeki `apps/dsa-desktop/ci-ui-smoke.js`, React navigasyonunu başlatmadan önce `a[aria-label="Ana Sayfa"]` arıyordu. Oysa **gerçek** `apps/dsa-web/src/components/layout/SidebarNav.tsx` masaüstü menüsünde `home` öğesi için Türkçede bilinçli olarak `language === 'tr' ? 'Hisse Analizi' : t(labelKey)` kullanıyor. Türkçe genel `layout.nav.home` çevirisi `Ana Sayfa` olsa bile masaüstünde o etiket kullanılmıyor. Bu nedenle ilk menü bekleme koşulu erişilemezdi. Hatanın tek nedeni olduğuna hükmetmek için yeni gerçek Windows CI sonucu beklenmelidir.

## Düzeltme

1. `ci-ui-smoke.js` ilk menü bekleme koşulu gerçek `Hisse Analizi` etiketine bağlandı; **`Kullanım` ve `Veri Merkezi` linkleri, Türkçe `document.lang`, `Token Kullanımı` ve `Veri merkezi` başlıkları kontrol edilmeye devam ediyor**. İstekler `127.0.0.1` dışına çıkamaz, üretim API kayıt edilmez, sahte auth ile yalnız read-only CI fixture başlatılır.
2. `waitUntil` hata çıktısı artık hangi aşamanın başarısız olduğunu (`Turkish navigation controls`, `usage page heading`, `data center heading`) belirtiyor. Eşik ve başlık/rota kontrolleri gevşetilmedi; yanlış başarılı sonucu önlemek için **React çıkış kodu 42** şartı korundu.
3. `apps/dsa-desktop/tests/ci-react-smoke.test.js` menü etiket kaynağıyla smoke'un uyuştuğunu kontrol ediyor; eski `Ana Sayfa` aranmasını regresyon hatası sayıyor.
4. Windows workflow sadece yeni izole dal için push tetiklemesi açar; aynı SQLite/no-clobber, NSIS 9 kontrol + 14 sentetik test, Electron, SHA-512, Authenticode ve release engelleri korunur.

## Çıkış engelleri

Yeni dalın Windows gerçek paketli React smoke **success** sonucu alınana dek iş tamamlandı denemez. CI yalnız sahte içerikli read-only testtir; gerçek Windows installer çalıştırma/yükseltme/kaldırma, kullanıcı `.env`/DB/WAL/SHM restore, gerçek piyasa API'si, gerçek/paper emir, scheduler, piyasa tarama, otomatik güncelleme, kod imzalama veya yayın yoktur.

`DESKTOP_UPDATES_ENABLED=false`, `release_status=BLOCKED`. Bu PR merge edilmemeli; önceki PR #176 ve `main` değişmez.
