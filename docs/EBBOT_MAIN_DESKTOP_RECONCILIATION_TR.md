# EBBot — main + Windows taslak #139 ayrı entegrasyon adayı (YAYIN ENGELLİ)

**Entegrasyon kaynağı:** `main=85f35395922b10e47686315c3af1576f286e93b1`, `#139=0c0feb2d9eaca9ab9d3067d12e453a103fb8df35`. Bu belge yalnız bu iki sabit SHA için geçerlidir. Ana dal güncellenirse birleştirme adayı **yeniden gözden geçirilmelidir**. Bu commit izole `integration/` dalındadır; `main` dalı değiştirilmez.

## Dosya bazlı çözüm

Ortak Git tabanı `6262da4208f6f5b6eba8d7555db1bc6c3616071b`. `main` tarafında bu tabandan itibaren 26 dosya değişti; 10 tanesi taslak #139 ile örtüştü. **Örtüşmeyen 16 dosya `main` içeriğiyle korundu:** Solana kalite raporları, kalite kontrol scriptleri/testleri, `meme-radar-verify.yml`, ve yeni masaüstü kimliği ve offline main gate doküman/workflowları.

Çakışan 4 dosya için güvenli manuel inceleme başlangıç kararı:

- `.github/workflows/ebbot-electron-windows-offline-package.yml`: #139'daki daha kapsamlı gerçek PyInstaller + NSIS `--publish never`, Python WAL ve Authenticode kontrol adımları korundu. `integration/` dalı `push` tetikleyicisine, `main` ise PR hedef listesine **eklenerek** yerel CI uyumu sağlandı. `main` üzerindeki `ebbot-desktop-identity-main-gate.yml` ayrıca korundu.
- `apps/dsa-desktop/main.js`: #139'daki önceki kullanıcı DB/WAL/SHM dosyalarını güvenlik kapısıyla kontrol eden staged backup/restore ve kapalı `DESKTOP_UPDATES_ENABLED=false` sürümü seçildi. `main`'in daha basit özyinelemeli `copyRuntimeStatePathSync` ve `installDownloadedUpdate` akışındaki eski satırlar aynen alınmadı: bu davranışların yerini #139'da test edilen daha sıkı koruma alıyor. **Gerçek user-data restore doğrulanmış DEĞİL.**
- `scripts/audit_ebbot_desktop_package.py`: #139 sürümü seçildi çünkü gerçek NSIS SHA-512/byte-size denetimi, `latest.yml` tekrarlanan alan reddi ve SQLite offline köprü sözleşmeleri içeriyor. `main` sürümündeki yalnız metinsel `sha512` varlık kontrolü yeterli değil.
- `tests/test_ebbot_desktop_package_audit.py`: #139 sürümü seçildi çünkü paket hash sahteciliği/metadata reddi, kimlik ve offline köprü pozitif/negatif testlerini genişletiyor.

Diğer 6 örtüşme dosyası:
- `installer.nsh`, `package-lock.json`, `renderer/loading.html`, `tests/preload.test.js` hem `main` hem #139 üzerinde **birebir aynı Git blob**.
- `package.json` ve `tests/main.test.js` #139 tarafından genişletildi; `main` içeriğindeki anlamlı satırlar #139'da da bulundu. `package.json`'daki kapalı updater, EBBot uygulama kimliği ve yayın adresi korunuyor.

Bu çözüm GitHub Git Trees API ile `#139` kaynak ağacından, ilgili 16 `main` blob'u üzerine koyarak oluşturuldu. **Yeni commitin tek ebeveyni `main` commitidir**, fakat hiçbir geçmiş PR otomatik merge edilmedi; bu normal kaynak entegrasyon adayıdır. Diğer taslak PR zinciri orijinal haliyle korunmuştur.

## Yayın ve doğrulama kapıları

Önce gerçek `node --test`, Python WAL ve kaynak audit testleri; ardından yalnız GitHub Actions Windows 2022 üzerinde gerçek PyInstaller ve NSIS paketlemesi (`--publish never`).  Gerçek Windows kurulumu, gerçek kullanıcı SQLite taşınması/rollback, SmartScreen, kod imzalama, updater ve canlı/paper trade **yasak/engelli**.

**Kritik risk:** Uygulamanın normal `backupPackagedRuntimeState` / `restorePackagedRuntimeStateFromBackup` kodu halen WAL-tutarlı CLI snapshot + no-clobber rollback provasına bağlı değildir. Bu entegrasyon tek başına yayın adayı değildir.

Merge için ayrıca `main` HEAD yeniden denetimi, bağımsız kod incelemesi, test ve açık kullanıcı onayı gerekir. Geri dönüş: yalnız taslak entegrasyon PR'ı kapatılır; `main` ve #117…#139 taslak zinciri değişmez.
