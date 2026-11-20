# EBBot — SQLite kurtarma için ayrı işlem çökme provası

**Durum:** Taslak, gerçek kullanıcı verisine erişim yok, yayın ve otomatik güncelleme engelli.

Bu aşama PR #136 içindeki normal JavaScript `throw` simülasyonlarını tamamlar. `apps/dsa-desktop/tests/sqliteRollbackCrash.test.js` gerçek bir **ayrı Node alt işlemi** çalıştırır. Alt işlem dosya sistemi `renameSync` adımlarından birini bitirdiği anda `process.exit` ile **normal kodun `catch/finally` temizliğini çalıştırmadan** kapanır. Kontrol ve kurtarma işlemleri ana test işleminde, diskte kalan klasörler üzerinden sınanır.

Üç doğrulama:

1. `active/` eski DB/WAL/SHM üçlüsü `previous/` olarak taşındıktan hemen sonra alt işlem kapanır. Kurtarma üçlüyü eksiksiz geri getirmelidir; yeni `candidate/` aynı kalmalıdır.
2. Yeni tek DB snapshot'ı `active/` konumuna geçtikten hemen sonra alt işlem kapanır. Açılış kontrolü **otomatik kabul/restore yapmadan** `REVIEW_REQUIRED` döndürmeli; açık geri alma üçlüyü geri getirmeli ve yeni DB'yi `candidate-quarantine/` altında tutmalıdır.
3. Rollback sırasında yeni `active/` `candidate-quarantine/` olarak ayrıldıktan sonra alt işlem kapanır. Yeniden başlatma kurtarması `previous/` altındaki eski DB/WAL/SHM'yi eski konumuna taşımalı, yeni kopyayı karantinada bırakmalıdır.

Tüm klasörler `os.tmpdir()` altındaki `ebbot-sqlite-rehearsal-*` adlarında, geçici markera sahip dizinlerdir. Dosyalar sentetik küçük `Buffer` değerleridir. Alt işlem sadece bu klasörü ve modülün test fonksiyonlarını alır; Electron, gerçek backend, kurulum dosyası, borsa taraması veya alım-satım başlatmaz.

**Kanıt sınırı:** `process.exit` ile süreç kapanışını taklit etmek gerçek elektrik kesintisini, NTFS journal dayanıklılığını, `TerminateProcess` semantiğini, Windows kullanıcı izinlerini, kilitli SQLite veritabanı davranışını veya gerçek NSIS yükseltmesini doğrulamaz. Kullanıcıya dağıtım izni değildir.

**Test komutu (CI):** `npm test` (Windows 2022 üzerinde). Gerçek PyInstaller/NSIS işleri ayrı `push` koşulu altında `--publish never` ile yapılır. Dağıtım/yükleme yapılmaz. Geri alma: PR'ı kapatmak yeterlidir; uygulamanın üretim yolu etkilenmez.

## Ek çapraz dil SQLite tutarlılık doğrulaması

`tests/test_ebbot_sqlite_recovery_roundtrip.py` iki gerçek **sentetik SQLite veritabanı** testi içerir. Python'un `sqlite3` modülüyle WAL modunda iki kayıt commit edilir; üçüncü kayıt commit edilmeden bekletilir. Canlı WAL/SHM'nin sentetik dosya baytları ile `sqlite3.Connection.backup` snapshot'ı üretilir. Bu baytlar yalnızca JSON/Base64 üzerinden ayrı Node işlemlerinin geçici çalışma klasörlerine aktarılır.

1. Yeni snapshot bir DB olarak aktive edildiğinde yalnız iki commit edilmiş kayıt görünür. Eski DB/WAL/SHM topluca `previous/` altında tutulur; geri alma sonrasında eski dosyalardan açılan veritabanının `PRAGMA integrity_check` ve iki commit edilmiş kaydı doğrulanır.
2. Eski DB/WAL/SHM klasör olarak ayrıldıktan sonra Node alt işlemi hiçbir `finally` çalıştırmadan çıkış kodu 71 ile sonlanır. Ayrı kurtarma işlemi eski üçlüyü geri getirir; hem eski DB hem yeni aday SQLite tarafından ayrı ayrı açılarak doğrulanır.

Bu testler, önceki 3 çökme provasından **ayrıdır**; artık toplam 5 yeni test bulunmaktadır (3 Node, 2 Python+Node). Bunlar gerçek Windows kullanıcı dosyası, NTFS güç kesintisi, imza veya installer testi değildir. CI üzerinde sadece sentetik geçici SQLite verileri kullanılır.

**Windows WAL kilit düzeltmesi:** İlk gerçek SQLite testi Windows CI'da açık yazıcı işlemi varken ham WAL/SHM dosyalarına erişmeye çalıştığı için `PermissionError` verdi. Test kurulumu güncellendi: ayrı bir Python yazıcı işlemi iki kaydı commit ettikten ve üçüncü kaydı açık transaction'da bıraktıktan sonra `os._exit(0)` ile ani kapanmayı taklit eder. İşlem sona erince Windows dosya kilitleri çözülür; eski DB/WAL/SHM baytları **ancak bundan sonra** toplanır. SQLite'ın `Connection.backup` API'si ayrı, kapalı durumdaki bu sentetik WAL veritabanından tutarlı snapshot üretir. Gerçek kullanıcı dosyası kullanılmaz. Bu revizyonun CI sonucu yeniden doğrulanmalıdır.
