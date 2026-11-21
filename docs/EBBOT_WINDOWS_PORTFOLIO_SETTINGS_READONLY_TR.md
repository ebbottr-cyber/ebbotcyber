# EBBot — Windows portföy ve Ayarlar salt-okunur etkileşim denetimi

**Yayın kapalı / yalnız CI.** PR #179 sonrasındaki doğrulama katmanı; gerçek hesap, piyasa, pozisyon, kullanıcı ayarı veya kimlik bilgisi yüklenmez veya saklanmaz.

## Kanıt kapsamı

- Windows 2022 runner: gerçek PyInstaller backend ve yerel NSIS Electron paketleme (--publish never).
- Paketli EBBot.exe içinde Türkçe React paneli ve önceki Kullanım/AI filtre kontrolleri.
- Portföy: CI örnek hesabı yalnızca GET ile döner; FIFO -> AVG seçimi ve React ekranındaki AVG değeri doğrulanır.
- Ayarlar: yalnız base ve data_source şeması GET ile gelir; sekmeler arasında gidip dönülür, aria-current değerleri React tarafından güncellenir.
- Hiçbir hesap oluşturma, içe aktarma, ayar kaydetme, analiz, strateji tarama, emir veya scheduler eylemi yapılmaz.

## Ağ ve veri engelleri

- Sentetik GET yanıtları sadece frozen backend, GitHub Actions, açık paket sağlık probe ve React probe koşulları altında vardır.
- CI Örnek Hesap (sanal) gerçek finansal hesap değildir; gizli anahtar, pozisyon veya saklama alanı yoktur.
- Sentetik iki Ayarlar alanının isEditable değeri false; yalnız /api/v1/system/config ve /api/v1/portfolio/accounts GET örneklenir.
- Gerçek /api/v1/portfolio/snapshot, /api/v1/portfolio/risk, /api/v1/analysis/analyze ve üretim işlem yolları probe'da kayıtlı değildir.
- Chromium renderer yalnız file: ve http://127.0.0.1:<port> GET/HEAD isteklerini kabul eder; POST/PUT/PATCH/DELETE bloke edilir.
- Otomatik güncelleme, installer yayınlama, canlı/sanal işlemler, scheduler ve tarama kapalıdır. Installer veya özel .env artefakta yüklenmez.

## Birleştirme ve yayın engelleri

PR taslak kalır. Gerçek Windows paket/React etkileşim logları, Electron güvenlik denetimi, tam backend regresyonu ve frontend lint/TypeScript/build başarılı olmadan main ile birleştirilmez.

Bu kontrol gerçek kullanıcı PC kurulumu, gerçek hesap API entegrasyonu, veri göçü, kod imzalama, Defender veya SmartScreen testi yerine geçmez.
