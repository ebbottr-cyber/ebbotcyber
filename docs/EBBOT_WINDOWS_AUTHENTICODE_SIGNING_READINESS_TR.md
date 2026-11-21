# EBBot — Windows Authenticode imzalama hazırlığı (yayımlama kapalı)

**Durum: YAYIN ENGELLİ (BLOCKED).** Bu aşama EBBot'un Windows kurulum dosyasını imzalamaz, kullanıcıya dağıtmaz, kurmaz, çalıştırmaz veya güncelleyiciyi açmaz.

## PR zinciri ve dayanak

- [PR #117](https://github.com/ebbottr-cyber/ebbotcyber/pull/117): Windows PyInstaller + NSIS derlemesi, paket yapısı
- [PR #123](https://github.com/ebbottr-cyber/ebbotcyber/pull/123): bağımsız EBBot kimliği, güncelleyici kilidi
- [PR #125](https://github.com/ebbottr-cyber/ebbotcyber/pull/125): `latest.yml` ile kurulum dosyasının SHA-512 bütünlük eşleşmesi

Bu taslak, üçüne bağımlı **yeni bir imzalama hazırlığı kontrolüdür**.

## Güvenlik denetimi

Windows 2022 CI'da yalnızca **lokal** olarak oluşturulmuş bu üç .exe dosyası `Get-AuthenticodeSignature` ile incelenir:

1. EBBot NSIS kurulum dosyası
2. Paket içindeki EBBot Electron uygulaması
3. Paket içindeki gerçek PyInstaller Python backend'i

`scripts/collect_ebbot_windows_signatures.ps1`, sadece dosyanın varlığını, Windows Authenticode `Status` bilgisini, imzalayan sertifikanın parmak izini ve geçerlilik tarihlerini yerel JSON rapora yazar. Dosyaları **çalıştırmaz**, herhangi bir sunucuya göndermez, anahtar/sertifika dosyası oluşturmaz veya güncellemeyi kontrol etmez.

`scripts/audit_ebbot_desktop_signing.py`, Windows `Valid` durumunu, sertifika tarihlerini ve bilinen yayıncı sertifikası parmak izi izin listesini birlikte denetler. **Varsayılan izin listesi boştur**. Bilinmeyen yayıncı, eksik dosya, eksik imza, süresi geçmiş sertifika veya politika sapması `signing_validation: BLOCKED` üretir.

Politika: `.github/ebbot-desktop-signing-policy.json`. Sertifika parmak izi, yayıncının kimliği ve sahipliği haricen doğrulanmadan politika güncellenmeyecek. Kullanıcının onayı ve yeni güvenlik PR incelemesi olmadan imzalama açılmayacak.

## Önemli sınırlar

- İmza kontrollerinin başarılı olması bile `release_status: BLOCKED` değerini **değiştirmez**.
- Hash doğrulaması veya Authenticode durumu tek başına Windows SmartScreen itibarı, güncelleme kaynağı güvenliği, sürüm geri alma güvenliği ya da gerçek kullanıcı kurulumu kanıtı değildir.
- Gerçek sertifika satın alma, özel anahtar, GitHub Actions secret, sertifika yükleme veya imzalama işlemi yapılmaz.
- Sadece masaüstü paket denetimi ve imza denetimi JSON'ları Actions artefaktı olarak kaydedilir; kurulum .exe'si, `latest.yml`, veri dosyaları veya özel bilgileri içeren örnekler yüklenmez.
- `DESKTOP_UPDATES_ENABLED = false`; Windows yayını, otomatik güncelleme, scheduler, gerçek ve sanal işlemler kapalı kalır.

## İleride yapılması gerekenler

Ayrı bir onaylı sürüm planında Windows kod imzalama kuruluş/kimlik tespiti, güvenli sertifika saklama veya güvenilir bulut imzalama, kararlı güncelleme kanalı, sürüm yükseltme/geri alma, Windows SmartScreen/Defender davranışı ve kullanıcı verisi koruma testleri yapılmalı. Bu PR yayın izni vermez.
