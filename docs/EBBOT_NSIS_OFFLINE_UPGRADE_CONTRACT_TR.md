# EBBot — NSIS kurulum/yükseltme veri koruma sözleşmesi (yükleyici çalıştırılmadan)

**TASLAK · YAYIN ENGELLİ.** Temel PR: [#165](https://github.com/ebbottr-cyber/ebbotcyber/pull/165). Bu aşamada **gerçek NSIS kurulum paketi çalıştırılmadı**, Windows kayıt defteri veya kurulu EBBot uygulaması okunmadı/yazılmadı, hiçbir kullanıcının DB/WAL/SHM, `.env`, log veya diğer dosyası değiştirilmedi.

## Denetlenen kaynak kuralları

`scripts/audit_ebbot_nsis_upgrade_contract.py`, dört depodaki kaynağı **yalnız okur**: `apps/dsa-desktop/installer.nsh`, `package.json`, `main.js` ve `.github/workflows/ebbot-electron-windows-offline-package.yml`.

Denetim fail-closed şekilde şu dokuz sözleşmenin varlığını doğrular:

1. Per-user kurulum zorlaması; sistem-geneli kurulumdan kaçınma.
2. Program Files/Windows gibi korunan klasörler için kurulum dizini kısıtları.
3. Eski kaldırıcı hatalı/eksikse işlemden **başarılı çıkmama**, hata seviyesiyle durma.
4. Kurulum yolu boşluk içerdiğinde `"_?=$R8"` ve `/KEEP_APP_DATA` değerlerini iki retry denemesinde koruma.
5. Özel NSIS include içinde beklenmeyen `RMDir`, `Delete` ve `DeleteRegKey` gibi silme komutlarını reddetme.
6. Paket kimliği EBBot, NSIS per-user, yönetici yetkisi yükseltmesiz ve kurulum dizini seçilebilir kurallarını doğrulama.
7. `DESKTOP_UPDATES_ENABLED=false` değişmezini doğrulama.
8. GitHub Actions yalnız read-permission altında NSIS `--publish never` ve `release_status: BLOCKED` kurallarını koruma.
9. CI'nın NSIS yükleyiciyi kurmadığı/çalıştırmadığı kaynak sözleşmesini kontrol etme.

`tests/test_ebbot_nsis_upgrade_contract.py` gerçek kaynakta olumlu testi, bellek içi kopyalarda ise komut satırından `/KEEP_APP_DATA` kaybolması, tırnaksız `_?=`, sıfır yerine hata kodu, `Quit` kaldırılması, per-user kapısının kaldırılması, yeni silme komutları, korunan dizin denetiminin kaldırılması, yönetici yükseltmesi, yanlış uygulama kimliği, updater'ın açılması, `--publish always`, CI izin yükseltmesi gibi **olumsuz senaryoları** sınar. Bu mutasyonlar yalnız Python belleğindedir; CI gerçek dosyalara değişiklik uygulamaz.

Windows source CI job'unda bu testler ve CLI denetimi başka SQLite/kurtarma/Electron kontrolleriyle birlikte çalıştırılır. Ağ/piyasa/cüzdan/veritabanı işlemi başlatılmaz. Gerçek Windows paketleme job'u önceki gibi yalnız `--publish never` ile exe/NSIS üretir; **kurulum gerçekleştirmez**. `release_status=BLOCKED` kalır.

## Bu testlerin ispatlamadığı şeyler

Bu **NSIS sözdizimi ve uygulama politikası üzerinde kaynak seviyesi kontrollerdir**: Gerçek kullanıcı kurulumunda `Uninstall EBBot.exe` davranışı, registry değeri uyumu, Windows dosya kilitleri, per-user vs all-user migration, kullanıcı dosyalarının NSIS tarafından gerçekten korunması, yükseltme/kaldırma veya elektrik kesintisinde geri dönüş başarısı **kanıtlanmış değildir**. NSIS 3. parti/electron-builder template'in tamamını test etmez. Bu aşamalardan önce bağımsız ve açık onaylı, yalnız **izole sahte kullanıcı profili** kullanan kurulum provası gereklidir.

Bu PR `main`e birleştirilmez; otomatik güncelleme, scheduler, gerçek/sanal alım-satım ve yayın kapalı kalır.
