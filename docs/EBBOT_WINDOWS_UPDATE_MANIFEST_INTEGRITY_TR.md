# EBBot Windows güncelleme manifesti bütünlük kapısı

**Yayın durumu: BLOCKED.** Bu PR sadece yerel/CI tarafından oluşturulmuş `latest.yml` dosyasını kontrol eder. Ağdan güncelleme indirmez, Electron/NSIS kurucusunu çalıştırmaz, sertifika üretmez, Windows'a kurmaz veya uygulamada güncelleme özelliğini açmaz.

## Amaç

`scripts/audit_ebbot_desktop_package.py --strict-package` daha önce `latest.yml` dosyasındaki sürüm, URL ve SHA-512 alanlarının **varlığını** denetliyordu; dosya içeriği ile SHA-512 karşılaştırması yapmıyordu. Bu, bütünlük doğrulaması açısından eksikti.

Bu aşamada:
- `version`, `path`, `files[].url` ve NSIS dosya adı tekil ve EBBot'a ait olmalıdır.
- `files[].sha512` ve üst düzey `sha512` **gerçek NSIS kurulum dosyasının base64 SHA-512 değeriyle eşleşmelidir**.
- Varsa manifestteki `files[].size` gerçek installer boyutuyla eşleşmelidir.
- Eksik, birden çok, farklı veya dış bağlantıya işaret eden dosya kayıtları reddedilir.
- Kurulum dosyası değiştirilmiş, güncelleme metadata hash'i yanlış veya URL farklıysa CI hatalı çıkacaktır.
- Sonuçlarda yalnız dosya ismi ve özetler bulunur; kurulum dosyaları yüklenmez.
- `DESKTOP_UPDATES_ENABLED = false` ve `release_status: BLOCKED` değişmez.

## Ne kanıtlamaz?

Bu kontroller **dosyanın kim tarafından üretildiğini veya kod imzasının güvenilirliğini kanıtlamaz**. SHA-512 değeri, ele geçirilen bir yayın kaynağıyla beraber değiştirilebilir. Dağıtım için ayrıca Authenticode sertifika zinciri, kod imzası doğrulaması, SmartScreen değerlendirmesi, yayın kanalı ve gerçek Windows kullanıcı kurulum/güncelleme/veri koruma senaryoları gerekir.

**Sınırlar:** PR #117 ve PR #123 halen taslak. Bu PR onların üzerine eklenir; main'e merge, tag/release, installer dağıtımı, updater'ı açma, scheduler, gerçek veya paper trade yok.
