# EBBot — Electron açılış smoke + SQLite WAL/SHM koruması, birleşmesiz entegrasyon

**Durum: TASLAK — RELEASE BLOCKED.** Bu dal PR #161 üzerine hazırlanmıştır. Entegre edilen yeni `main` commit'i: `daad93eaab155509cef8fcf3906c2b354fee4fdf`. Kaynak #161: `0f0936a8490ea7fc55ba0ed4d5fbf8441dbf5c2b`.

## Dosya çatışmalarının bilinçli çözümü

- `apps/dsa-desktop/main.js`: `main`in `ci-ui-smoke.js` girişini uygulamanın sonunda ekledik; **önceden var olan** `sqliteSnapshotBridge` + `sqliteRollbackRehearsal` importlarını, üretim başlangıcının ayrı `createWindow` yolunu, kullanıcı verisi koruma adımlarını ve **`DESKTOP_UPDATES_ENABLED=false`** kapısını kaldırmadık. Sadece Windows + GitHub Actions + packaged + tam argüman uyumu olan `--ebbot-ci-ui-smoke` çağrısı, normal çalışma yoluna gitmeden çıkış yapar.
- `apps/dsa-desktop/package.json`: önceki `main.js`, `preload.js`, `sqliteSnapshotBridge.js`, `sqliteRollbackRehearsal.js`, `renderer/**/*` paket dosyaları korunarak `ci-ui-smoke.js` eklenir. Windows NSIS hâlâ `--publish never`.
- `scripts/probe_ebbot_packaged_health.py`: yeni `--electron-exe` argümanı ve tek proseslik paketli Electron testi, mevcut yalnız `127.0.0.1` PyInstaller health probe üzerine eklenir. Script, yalnız Windows GitHub Actions sanal makinesinde çalışabilir ve dış URL/kimlik bilgisi mirasını yasaklar.
- `.github/workflows/ebbot-electron-windows-offline-package.yml`: gerçek Windows PyInstaller → sentetik SQLite WAL snapshot → NSIS → SHA512/paket denetimi → backend loopback smoke → **paketli Electron splash/preload/renderer smoke** → Authenticode gözlemi → sadece JSON audit adımları birlikte korunur. `release_status=BLOCKED`. `push` çalışma kolu listesine bu taslak kol eklendi.
- `apps/dsa-desktop/ci-ui-smoke.js`, `apps/dsa-desktop/tests/ci-ui-smoke.test.js` ve `docs/EBBOT_PACKAGED_ELECTRON_UI_LOOPBACK_TR.md`: `main` commitinden birebir alındı; testler Windows/frozen/CI argüman kısıtlarını ve localhost dışı ağ engelini ölçer.
- PR #161'in `sqliteSnapshotBridge.js` WAL/SHM **boşa düşen sembolik bağlantı reddi** ve yeni regresyon testleri aynen tutuldu.

## Kanıt sınırları

CI sonucunu bekle: PR olayında gerçek paketleme job'u **bilinçli olarak atlanır**, gerçek Windows derlemesi yalnız bu branch'in `push` koşusunda çalışır. Testler **gerçek Windows kullanıcısına kurulum değildir**; packaged Electron yalnız CI'da özel smoke argümanıyla açılır. Normal React panel açılışı, installer çalıştırma/yükseltme/kaldırma, NTFS güç kesintisi ve kullanıcı dosyası taşıma kontrolü değildir.

**Güvenlik:** Gerçek/paper emir, otomatik analiz/scheduler, otomatik güncelleme, kod imzalama, yayın ve `main` merge edilmez. Yeni `main` commit'i gelirse bu dalların uyumu yeniden değerlendirilmelidir.

**Geri dönüş:** PR'ı kapat; #161, #158 ve `main` değişmez.
