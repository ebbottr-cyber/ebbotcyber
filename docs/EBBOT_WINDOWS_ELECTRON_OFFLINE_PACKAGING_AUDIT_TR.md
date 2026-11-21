# EBBot — Windows Electron paketleme ve yayın emniyeti (PR #113 üstüne)

**İnceleme tarihi:** 20 Kasım 2026. Bu bir **yayın onayı değildir**. Windows CI'da hazırlanabilecek dosyalar GitHub Releases'a veya kullanıcının bilgisayarına gönderilmez.

## Kaynakta doğrulanan mevcut kimlik ve güncelleyici riski

`apps/dsa-desktop/package.json` şu an:
- `version: 3.21.0` ve `productName: Daily Stock Analysis`
- `appId: com.daily-stock-analysis.desktop`
- `build.win.publish` adresi `ZhuLinsen/daily_stock_analysis`

`apps/dsa-desktop/main.js` dosyasındaki güncelleme kontrolü de aynı **başka proje** adresini kullanır. EBBot olarak paketlenip kullanıcıya ulaştırılmadan önce **ürün kimliği**, yeni/ayrı otomatik güncelleme kanalı, indirme bütünlüğü, mevcut kurulu kullanıcı verisinin korunması ve güvenilir imzalama ayrıca ele alınmalıdır. Bu taslakta keyfî EBBot sürüm numarası, kod imzalama sertifikası veya yayın deposu **uydurulmadı**. Orijinal uygulama adı üzerinden gerçek dağıtım **yapılmayacak**.

## GitHub test yaklaşımı

`.github/workflows/ebbot-electron-windows-offline-package.yml`:

1. Windows 2022 üzerinde gerçek Electron `main.js` / `preload.js` Node testleri ve masaüstü kurulum sözleşmeleri.
2. Gerçek React `npm ci`, `scripts/build-backend.ps1` aracılığıyla Windows PyInstaller backend'i + paket içi modül/kalendar/strateji kontrolleri.
3. `electron-builder --win nsis --publish never` ile **yalnız CI çalışma klasöründe** NSIS çıktısı üretme denemesi. Hiçbir Electron penceresi, backend sunucusu, otomatik işlem, kurulum sihirbazı veya güncelleyici başlatılmaz.
4. `scripts/audit_ebbot_desktop_package.py --strict-package` ile `stock_analysis.exe`, `app.asar`, web statikleri, NSIS yükleyicisi, blockmap, `latest.yml` sürüm/eşleştirme ve gerçek `.env` dosyasının pakette bulunmaması denetlenir. Paketli çıktı varsa yalnızca **dosya adları ve SHA-256 özetleri** denetim JSON'unda tutulur.
5. Yalnızca `desktop-package-audit.json` kısa süreli Actions artefaktı olarak yüklenir. **Exe/installer/backend/latest.yml/blockmap dosyaları asla yüklenmez**, GitHub Release/tag oluşturulmaz, `contents: read` sınırı korunur.
6. Kaynak denetimi `release_status: BLOCKED` üretir. Windows paketinin yapısal olarak başarılı olması `release_status` değerini değiştirmez.

Mevcut `workflows_disabled/desktop-release.yml.disabled` içinde gerçek yayınlama akışı arşivlidir; **etkinleştirilmez**.

## Teknik olarak başarılı olmanın anlamı

- **Windows CI kaynak testi:** JavaScript/installer sözleşmeleri çalışıyor; gerçek kullanıcı kurulumu hakkında kanıt değildir.
- **NSIS çıktı testi:** Gerçek Windows CI dosyaları üretilebildi ve paket içindeki veriler var; bu **imzalı** veya **kullanıcı cihazında denenmiş** anlamına gelmez.
- **Manuel adımlar (henüz yapılmadı):** Kurulum/kaldırma/yükseltme, cüzdan veya hesap bilgisi olmadan yerel backend başlatma, sınırlı GET sağlık kontrolü, veri saklama izinleri, API kimlik doğrulaması, Windows Defender/SmartScreen, lisans ve açık kaynak dağıtım incelemesi.

Herhangi bir CI başarısızlığında veya eksik/yanlış metadata durumunda paket testini **başarısız** kabul edin; bunları atlayarak veya sahte bir backend koyarak yeşil sonuç üretmeyin.

## Açık sınırlar

`main`, PR #113 ve diğer taslaklar değiştirilmedi. Gerçek/paper emir, scheduler, canlı market taraması, yetkili oturum, deployment, tag/release, paket dağıtımı yapılmadı. **Birleştirme ve yayın ayrı açık kullanıcı onayı gerektirir.**
