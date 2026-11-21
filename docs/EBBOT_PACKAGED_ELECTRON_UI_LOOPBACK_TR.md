# EBBot Windows Electron — paketli pencere / backend bağlantısı için CI doğrulaması

**Durum: YAYIN ENGELLİ.** Bu çalışma [PR #148](https://github.com/ebbottr-cyber/ebbotcyber/pull/148) ile doğrulanan güvenli, sadece sağlık uç noktalı frozen Windows backend deneyi üzerine kurulur.

## Doğrulanan kapsam

Windows 2022 GitHub Actions testinde gerçek PyInstaller + NSIS paketi üretilir (`--publish never`). Installer **çalıştırılmaz, yüklenmez veya yayımlanmaz**. Bunun yerine `win-unpacked/EBBot.exe` kurulum yapılmadan, CI'ya özel `--ebbot-ci-ui-smoke` argümanı ve kısa ömürlü `127.0.0.1` sağlık backend'iyle başlatılır.

Bu mod yalnız paketlenmiş Windows Electron uygulaması, `GITHUB_ACTIONS=true`, `EBBOT_ELECTRON_UI_SMOKE=1`, geçerli loopback portu ve **tek, eksiksiz tanılama argümanı** koşullarında çalışır; aksi durumda normal uygulama çalışma yolu açılmadan hata verir. Test, normal `createWindow()` ve `startBackend()` yollarını çağırmaz.

Test, gerçek Electron `BrowserWindow` ile paket içindeki EBBot `renderer/loading.html` ekranını yükler; başlık, EBBot metni ve `preload.js` köprüsünü doğrular. Ardından penceredeki Chromium renderer içinden sadece localhost backend'in `/api/health` uç noktasına HTTP 200 + `{"status":"ok","probe":"offline-packaged"}` bekleyerek erişir. Analiz endpoint'i `/api/v1/analysis/analyze` için HTTP 404 doğrulanır.

Electron oturumunun ağ istekleri yalnız yerel `file:` ve tam `http://127.0.0.1:<port>` kaynaklarına izin verir; dış adresler reddedilir. Python probe, CI ortamından API anahtarlarını ve ilgili diğer sırları aktarmadan yalnız güvenli izin listeli ortam ile süreç başlatır ve zaman aşımı/başarısızlıkta sonlandırır.

**Bu bir tam React panel testi değildir.** Dashboard render'ı, ekran görüntüsü, gerçek cihaz kullanıcı kurulumu, yükseltme/kaldırma, veri göçü veya Defender/SmartScreen açısından başarı iddia edilmez. Windows hosted runner GUI açma yetkisi sınırlı olabilir; sonuç başarılı değilse bunu gerçek kullanıcı kurulumu başarısı gibi göstermeyin.

## GitHub kanıt kapıları

- Node testleri, CI talep koşullarının paketli Windows + GitHub + exact arg ile sınırlı kaldığını ve localhost dışı isteklerin reddedildiğini doğrular.
- Genel frontend/backend ve Windows sözleşme testleri başarılı olmalıdır.
- **Gerçek Windows `push` job'unda yeni Electron smoke adımının açıkça başarılı olması gerekir.** PR olayındaki ağır paket oluşturma işi güvenlik gereği `skipped` olabilir.
- Sadece `desktop-package-audit.json` kısa süreli Actions artefaktı olarak saklanır. NSIS installer, EXE, backend, `.env` ve updater metadata dışarı yüklenmez.

## Açık yayın engelleri

Elektron'da **gerçek React panelinin veri/etkileşim testi**, kod imzalama, Windows SmartScreen/Defender, gerçek cihazda kurulum/kaldırma, eski sürümden veri göçü ve lisans denetimleri sürmektedir. Test başarılı olsa bile **dağıtım izni yoktur**. Otomatik güncelleme, paper/gerçek emir, piyasa taramaları ve scheduler kapalıdır.
