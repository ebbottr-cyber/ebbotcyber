# EBBot — Electron ile SQLite snapshot aktarımı için güvenli hazırlık (yayın kapalı)

**Durum: TASLAK.** `DESKTOP_UPDATES_ENABLED = false`; `release_status = BLOCKED`. Bu PR gerçek bir Windows yükseltmesi, kullanıcının dosyalarını geri yükleme veya sistemdeki SQLite dosyalarının üzerine yazma işlemi **yapmaz**.

## Geçmiş ve amaç

PR #134 ile Python'da geliştirilen WAL-tutarlı `sqlite3.Connection.backup` komutu, asıl analiz servisi başlamadan tek seferlik çağrılabilir hale getirildi. Bu PR, bu komutu Electron paketinde doğrulanmış ve dar kapsamlı bir köprüyle çağırabilmek için gereken yardımcı kodu ekler.

## Yeni köprü

`apps/dsa-desktop/sqliteSnapshotBridge.js`:

- Yalnız açıkça fonksiyon çağrıldığında, paketli `stock_analysis.exe` dosyasını `--ebbot-desktop-sqlite-snapshot` ile çalıştırabilecek bir yardımcı metot sağlar. **Uygulamanın açılışında veya güncelleyici akışında çağrılmaz.**
- Alt işleme yalnız gerekli Windows dosya yolu/çalışma ortamı değişkenleri aktarılır; broker ve AI API anahtarları aktarılmaz. Normal backend, web sunucu, scheduler ve alım-satım başlatılmaz.
- Dönüş JSON'u fail-closed değerlendirilir: `PASSED`, `sqlite3.Connection.backup`, `integrity_check = ok`, `release_status = BLOCKED`, güvenli kapalı bayrakları, SHA-256 ve dosya boyutu kontrol edilir. Snapshot dosyasının gerçek SHA-256'sı ve boyutu bağımsız olarak kontrol edilir.
- `stageSnapshotRestoreCandidate` **yalnız boş hedef dizindeki, adı önceden kullanılmamış hedef dosyaya** yeni bir kopya hazırlayabilir. Var olan DB veya `-wal`/`-shm` yan dosyaları varsa reddeder.
- Snapshot SHA-256 ve boyutu uyuşmuyorsa reddeder. Kopyayı önce rastgele bir geçici dosyada doğrular, sonra aynı dizinde bağlantı oluşturarak eski dosyanın üzerine yazmadan yayımlar; başarısızlıkta geçici kopyayı kaldırır. Dosya sistemi güvenli hard-link yayınını desteklemiyorsa hata verip durur.
- `main.js` bu modülü yalnız ilerideki açıkça onaylanmış entegrasyon ve izole testler için dışa sunar. Web/Electron IPC veya otomatik update rotası açılmaz.

`package.json` dosya listesi ve `scripts/audit_ebbot_desktop_package.py` kaynak sözleşmesi, köprünün Electron ASAR'a eklenmesini zorunlu kılar.

## Çevrimdışı testler

- Sentetik `stock_analysis.exe` yerine verilen denetimli runner, hangi argümanlarla çağrıldığını doğrular; gerçek executable çalıştırmaz.
- Hatalı JSON, uyumsuz digest, mevcut hedef DB, aktif/eski WAL ve SHM, sembolik bağlantı reddedilir.
- Kullanıcıya ait mevcut hedef korunur. Yarış sırasında hard-link yayınlama engellenirse nihai dosya ve yarım geçici kopya oluşturulmaz.
- Orijinal kaynak veritabanı bu köprüyle hiçbir zaman değiştirilmez.
- PR #134'teki gerçek PyInstaller frozen snapshot smoke testi ayrıca CI'da yürütülmeye devam eder.

## Sınırlar

Bu köprü **güncel `backupPackagedRuntimeState` / `restorePackagedRuntimeStateFromBackup` akışına henüz bağlanmamıştır**. Bunun nedeni SQLite snapshot'ını eski DB/WAL/SHM üçlüsüyle değiştirmenin çökme/yarıda kesilme durumunda bütünlük riski oluşturmasıdır. Üretim bağlantısı için rollback journal, aynı anda açık backend bağlantılarının yönetimi, güvenli klasör izinleri ve test edilmiş Windows NSIS yükseltme/geri alma prosedürü gereklidir.

Hash uyuşması ve CLI JSON raporu, yürütülen backend'in orijinalliğini veya Windows Authenticode imzasını tek başına kanıtlamaz. PR #127'deki sertifika/yayın engeli yürürlükte kalır.

**No release, no install, no update, no live/paper trading, no scheduled scans.** Bu PR'ı kapatmak/branch'i silmek önceki test edilmiş taslaklara dokunmaz.
