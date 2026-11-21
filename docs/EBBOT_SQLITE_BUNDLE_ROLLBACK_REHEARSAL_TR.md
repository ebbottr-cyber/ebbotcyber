# EBBot — SQLite DB/WAL/SHM geri alma provası

**Statü: TASLAK / yayın ENGELLİ.** Bu protokol henüz gerçek Windows kullanıcı veritabanı veya Electron yükseltme rotasına bağlanmıyor. Yalnızca testler tarafından oluşturulan *sentetik Buffer* verileriyle işletilir. Kod imzalama, gerçek yükleyici kurulumu, SmartScreen ve kullanıcı verisi geçişi doğrulanmadığı için güncelleme açılamaz.

## Güvenlik amaçları

- Eski SQLite `stock_analysis.db`, `stock_analysis.db-wal`, `stock_analysis.db-shm` dosyaları **tek bir eski paket klasörü** olarak tutulur.
- Yeni `sqlite3.Connection.backup` snapshot'ı tek başına SQLite DB dosyasıdır; eski WAL/SHM dosyalarıyla **asla aynı aktif klasörde birleştirilmez**.
- Klasör adı değişikliği sırasında hata çıkarsa eski paket geri taşınır; geri taşıma da başarısızsa eski `previous/` klasörü kalır ve ayrı bir kurtarma denemesinde kullanılabilir.
- Başarılı prova yükseltmesinden sonra da eski paket `previous/` altında kalır. Yanlışlıkla silinmez.
- Onaylı rollback talebi `active/` içindeki yeni tek-dosya snapshot'ı `candidate-quarantine/` dizinine ayırır ve `previous/` içindeki eski DB/WAL/SHM üçlüsünü tek klasör olarak geri taşır.
- Çökme sonrası `active/` yok ve `previous/` mevcutsa eski paket geri alınır. Her ikisi mevcutsa **otomatik karar verilmez**: `REVIEW_REQUIRED`.
- Eksik eski DB, beklenmeyen başka dosya, snapshot'ta WAL/SHM bulunması ve sembolik bağlantı şüpheleri reddedilir.

## İzole test tasarımı

`apps/dsa-desktop/sqliteRollbackRehearsal.js`, `createSqliteBundleRehearsal()` ile yalnız `os.tmpdir()` altında benzersiz bir `ebbot-sqlite-rehearsal-*` klasörü açar. Girdiler **64 KiB üst sınırına sahip, sentetik Buffer verileridir**; gerçek veri dosyası yolu kabul etmez. Marker, klasör konumu ve symlink kontrolü sağlanmadan işlem çalışmaz.

`rehearseSqlitePromotion()`, `recoverInterruptedSqlitePromotion()`, `rollbackCompletedSqlitePromotion()` senaryoları `node --test tests/*.test.js` içerisinde çalışır. Başarı, yarıda kesilen iki rename, kilitli hedefi taklit eden hata, önceki dosyaları kurtarma, istenmeyen WAL/SHM'yi reddetme ve mevcut kullanıcı dosyalarına erişmeme durumları ayrı test edilir.

Windows kilitlenme sınırları için üç ek negatif test eklendi: ilk klasör taşıması `EBUSY` ile reddedildiğinde mevcut üçlünün yerinde kalması; ikinci taşıma ve eski klasörü geri alma işlemleri birlikte kilitlendiğinde eski üçlünün `previous/` altında korunması; yeniden başlatma kurtarmasında `EACCES` görülürse geri alma talebinin başarısız kalıp verileri silmemesi. Böylece toplam **13** sentetik Electron kurtarma senaryosu vardır.

Ayrıca Windows gerçek paketleme akışındaki imza kolektörü için önceki bir native komuttan kalan `$LASTEXITCODE` kontrolü kaldırıldı. Saf PowerShell kolektörünün hatası artık PowerShell'in sonlandırıcı exception'ı ve JSON çıktısının varlığı ile denetleniyor. Kaynak CI'da önce `cmd.exe` ile bilerek sıfır olmayan bir çıkış kodu oluşturup ardından üç **sentetik, imzasız** .exe üzerinde Authenticode kolektörünün çalışması ve yayın sonucunun `BLOCKED` olması doğrulanıyor.

**Gerçek kullanıcı dosyaları üzerinde bu yöntem denenmez ve mevcut yedek restore fonksiyonlarına dahil edilmez.**

## Ne kanıtlamaz?

Bu yalnız bir *prova*. Windows'ta birden fazla dosyanın değişimini transaction gibi atomik hale getirmez. Elektrik kesintisinde NTFS dayanıklılığını, SQLite dosya kilitlerini, gerçek NSIS uninstall/yükseltmeyi, Program Files kullanıcı izinlerini, antivirüs kilitlerini veya SQL backend bağlantı yaşam döngüsünü doğrulamaz. Prod'a geçiş için veri depolama yerinin uygun seçilmesi, ek yazma/okuma tutarlılığı, kurtarma state manifesti, cihaz testleri ve bağımsız güvenlik incelemesi gerekir.

## Geri alma ve yayın kapısı

PR #135 üzerine ayrı taslak branch'tir. Yeni helper ve testler kaldırılarak geri alınabilir; eski PR veya gerçek kullanıcı DB'sine dokunulmaz. `DESKTOP_UPDATES_ENABLED = false`, installer `--publish never`, `release_status: BLOCKED`, gerçek/paper trade ve scheduler kapalı.
