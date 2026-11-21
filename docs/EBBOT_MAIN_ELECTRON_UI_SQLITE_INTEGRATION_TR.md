# EBBot — Güncel main temelinde tek commit'lik Windows/SQLite/Electron UI entegrasyon adayı

**TASLAK; yayın onayı YOK.** Bu adayın tek ebeveyni `main=daad93eaab155509cef8fcf3906c2b354fee4fdf` ve bütünleşik kaynak adayı `PR #164=ebfc66b7711173b0a7eaa10d402846e99423795d`dir. Windows CI'nın **yalnızca bu branch için** de tetiklenmesi amacıyla workflow push allowlist'e bu branch eklenir. Diğer içerikler PR #164 Git tree'sinden alınır.

## Korunanlar

- `main` dalındaki **hiçbir dosya yolu kaybolmaz**. Özellikle `ci-ui-smoke.js`, `tests/ci-ui-smoke.test.js`, `scripts/probe_ebbot_packaged_health.py` ve `docs/EBBOT_PACKAGED_ELECTRON_UI_LOOPBACK_TR.md` **main Git blob SHA'sı ile birebir aynıdır**.
- `main.js` içinde normal Electron başlangıcı, EBBot kimliği, kapalı auto-updater ve önceki SQLite rollback/snapshot yardımcıları korunur. Paketli UI smoke yalnız GitHub Actions Windows 2022 özel modunda, frozen backend `127.0.0.1` sağlık uç noktasıyla çalışır.
- `sqliteSnapshotBridge.js` PR #161'deki bozuk WAL/SHM symlink no-clobber korumasını ve sentetik testlerini içerir. Eski DB/WAL/SHM kurtarma testleri de korunur.
- PyInstaller → sentetik WAL `sqlite3.Connection.backup` smoke → NSIS `--publish never` → SHA-512 audit → localhost backend health → CI Electron BrowserWindow/preload/renderer smoke → Authenticode gözlemi.
- Daha önce PR #158'de doğrulanan Solana/React/TypeScript/PWA/standalone backend e2e kaynakları korunur.

## Release kontrol listesi

CI sonucunu **bu head için yeniden** doğrula. Eski taslak PR testleri farklı SHA'lara aittir ve son çalışmanın yerini almaz. Üretim Electron+React açılışı, gerçek Windows NSIS install/upgrade/uninstall, gerçek kullanıcı SQLite taşınması ve kilitli DB recovery, kod imzası ve SmartScreen hâlâ doğrulanmamıştır. `DESKTOP_UPDATES_ENABLED=false`, gerçek/paper trade ve scheduler **kapalı**, `release_status=BLOCKED`.

Hiçbir eski PR veya `main` merge edilmedi. Bu PR'ın olması otomatik birleştirme veya yayın izni değildir. Geri dönüş: taslak PR'ı kapat.
