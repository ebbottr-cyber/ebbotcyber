# EBBot — Windows CI'da paketli Türkçe React paneli (salt-okunur)

**Durum: YAYIN ENGELLİ.** Bu kontrol normal EBBot backend'ini/stratejilerini açmaz; gerçek/paper emir, piyasa taraması, scheduler, bildirim, API anahtarları, otomatik güncelleme, installer çalıştırma veya yayınlama yoktur.

## Tam olarak neyi kontrol ediyoruz?

[PR #157](https://github.com/ebbottr-cyber/ebbotcyber/pull/157), paketlenmiş `EBBot.exe` içinde Electron splash/preload ve renderer → 127.0.0.1 sağlık bağlantısını geçti. Bu PR, **gerçek `apps/dsa-web` React üretim derlemesinin** aynı CI Windows/NSIS paketine dahil edilip edilmediğini ve Chromium penceresinde gerçekten render edilip edilmediğini ölçer.

Yeni `--react-ui` Python flag'i yalnız existing Windows runner probe'u içindedir. Şu bağımsız güvenlik koşulları birlikte gereklidir: `GITHUB_ACTIONS=true`, frozen PyInstaller exe, `EBBOT_PACKAGED_HEALTH_PROBE=1`, `EBBOT_PACKAGED_REACT_PROBE=1`, tam `--serve-only --host 127.0.0.1 --port <num>` komutu. Normal backend API/schedule yolu çağrılmaz. Electron tarafında ayrıca Windows paketli `EBBot.exe`, CI ve exact `--ebbot-ci-ui-smoke` argümanı gerekir; React test opt-in'i `EBBOT_ELECTRON_REACT_SMOKE=1`.

Test API modu yalnızca **GET** `/api/health`, **GET** `/api/v1/auth/status` (tamamen **sahte** `authEnabled:false` yanıtı), statik `/`, `/usage`, `/data` ve paketlenmiş `/assets/*` yollarını sunar. Production analiz, portföy emirleri, backtest, screening, auth login, OpenAPI, başka API ve veri mutasyon yolları **kayıt edilmez; 404/405 döner**. Test kimlik doğrulamayı veya gerçek kullanıcı oturumunu doğrulamış olmaz. AkShare önbellek ısınması, indeks yenileme, runtime scheduler, bot stream istemcileri atlanır.

GitHub Windows runner'ın tarayıcı dili İngilizce olabileceğinden, **yalnız CI'daki geçici Chromium oturumunun** `dsa.uiLanguage` anahtarı `tr` yapılır ve gerçek React sayfası tekrar yüklenir. Bu işlem uygulamanın varsayılan dil ayarını veya kullanıcı dosyalarını değiştirmez.

Windows paketli `EBBot.exe` Chromium renderer testinin bekledikleri:
1. Özgün EBBot splash sayfası ve preload köprüsü, gerçek frozen localhost health 200, analiz API 404.
2. Üretim `static/index.html` ve gerçek Vite JS/CSS assetlerinin localhost üzerinden yüklenmesi.
3. `document.documentElement.lang === 'tr'`, gerçek React `#root` ve `Ana menü` navigasyonunun render edilmesi.
4. Yan etkisiz gezinme bağlantıları `Kullanım` → `/usage` ve `Veri Merkezi` → `/data` tıklanınca **ilgili Türkçe sayfa başlıklarının** görünmesi. Türkçe sözlükte eksik `Token usage` başlığı `Token Kullanımı` olarak düzeltildi.

Electron oturumundaki istekler `file:` veya tam `http://127.0.0.1:<seçili port>` ile sınırlandırılır. Bu, ağ seviyesinde tam OS sandbox değildir; test kodunun ve Electron oturumunun isteklere koyduğu bir bariyerdir. Sahte auth yanıtı production API çalıştırmıyor.

## Kabul kriterleri ve açık noktalar

- [ ] Yeni `main` tabanlı PR head SHA'sında genel frontend/backend CI başarılı
- [ ] Yeni Windows push job'u: 54+ Electron unit, PyInstaller/NSIS `--publish never`, audit, React smoke **tamamı yeşil**
- [ ] Logda `PASS: packaged Turkish React shell and usage/data navigation` mevcut
- [ ] Installer, EXE, kullanıcı `.env`, güncelleme metadata hiçbir yere yüklenmiyor; yalnız JSON audit tutuluyor

Bu test **gerçek piyasa verisi, gerçek API etkileşimleri, Türkçeleştirilmiş bütün metinler, kullanıcı giriş, gerçek cihaz kurulumu, imzalama/Defender/SmartScreen, yükseltme veya veri göçü** için onay sayılmaz. Bunlar bağımsız yayın engelleridir; önceki MIT lisansı ve upstream atıfları korunur.
