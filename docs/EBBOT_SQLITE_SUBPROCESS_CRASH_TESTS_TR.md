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
