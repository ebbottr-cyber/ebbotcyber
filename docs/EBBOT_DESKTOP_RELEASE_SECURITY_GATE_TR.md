# EBBot masaüstü sürüm ve güncelleme güvenliği — taslak

**Durum: YAYIN ENGELLİ (BLOCKED).** Bu değişiklik bir release, imzalı ürün, Windows cihazına kurulum, otomatik sanal işlem veya gerçek alım-satım izni değildir.

## CI kanıtı

PR #117 tabanındaki Windows 2022 push çalışması [44808217323](https://github.com/ebbottr-cyber/ebbotcyber/actions/runs/44808217323) gerçek PyInstaller backend ve NSIS kurulum dosyasını **yalnız CI çalışma alanında** başarıyla üretmiş, paket bütünlüğü/eksik .env kontrollerini geçmiştir. Bu, güvenli dağıtım veya kullanıcı cihazı kurulumu kanıtı değildir.

## Bu taslak değişiklik ne yapar?

- Electron `productName = EBBot`, `appId = com.ebbot.desktop`, `name = ebbot-desktop` olarak ayrılır. Kimlik, gelecekteki kararlı sürüm seçimi öncesinde öneridir; mevcut eski projeye ait veriler otomatik taşınmaz.
- NSIS dosya adı `EBBot-windows-installer-v<version>.exe` olarak değiştirilir; Windows kurulum algılayıcısı `Uninstall EBBot.exe` dosyasını arar.
- Electron build publish hedefi yalnız `ebbottr-cyber/ebbotcyber` adresini kullanır. Eski proje `ZhuLinsen/daily_stock_analysis` Electron paketine veya güncelleyici sabitlerine dahil edilmez.
- **Önemli:** `DESKTOP_UPDATES_ENABLED = false`. Hem otomatik başlangıç kontrolü hem de kullanıcı tarafından istenen masaüstü güncelleme kontrolü ağ isteği yapmadan engellenir. İndirme, yükleme ve yeniden başlatma da uygulama üzerinden çalışmaz; kullanıcı arayüzüne kapalı olma durumu döner.
- Kaynak denetimi yanlış sahip, eski hedef veya açılmış güncelleme kapısında hata verir. CI yalnız rapor JSON'u saklar; kurulum .exe'leri ve updater metadata dağıtılmaz.
- Daha önceki `3.21.0` sürüm numarası geçici olarak korunur; EBBot'a ait ilk sürüm numarası bu PR ile ilan edilmez.

## Yayın engelleri

1. Uygun Windows kod imzalama kimliği ve sertifika sahipliği doğrulanacak; sertifika/anahtar GitHub deposuna eklenmeyecek.
2. Bağımsız EBBot Release deposu, imzalı paket ve sağlam sürüm kanalı belirlenip güncelleme imzaları/kaynak izinleri güvenlik testinden geçirilecek. `DESKTOP_UPDATES_ENABLED` yalnız ayrı, gözden geçirilmiş PR ile değiştirilebilir.
3. Gerçek Windows cihazında kurulum, kaldırma, yükseltme, Windows SmartScreen/Defender ve hesap/veri koruma senaryoları kontrollü olarak doğrulanacak.
4. Paketli backend başlatma/sadece yerel sağlık kontrolü ayrı kontrollü testte doğrulanacak; hiçbir otomatik/paper/canlı emir açılmayacak.
5. Lisans, telif ve bağımlılık dağıtım incelemesi ile güvenli yayımlama onayı gereklidir.

**Mutlak sınır:** Herhangi bir CI başarısı dağıtım izni değildir. `main` ve mevcut PR #117 birleştirilmez. GitHub Releases, tag, installer upload, imzalama işlemi, gerçek/sanal alım-satım ve scheduler yapılmaz.
