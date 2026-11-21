# EBBot Windows — SQLite ve yarıda kesilmiş yükseltme yedek güvenliği

**Yayın durumu: BLOCKED.** Bu adım yalnızca kaynak değişiklikleri ve CI üzerindeki sentetik dosyalarla sınanır. Gerçek kullanıcı makinesinde kurulum, yükseltme, SQLite canlı işlem veya alım-satım çalıştırılmaz. Güncelleyici kapalıdır.

## Neden bu değişiklik?

Önceki yedekleme yordamı SQLite `stock_analysis.db`, `-wal` ve `-shm` dosyalarını tek tek kopyalayıp, yedek manifestini en son yazıyordu. Dosyalardan biri kilitliyken veya kopyalama sırasında değişirken yarım bir yedek klasörü oluşabiliyordu. Üstelik başarısız bir NSIS yüklemesi sonrası installer kodu kurtarma yedeğini silebiliyordu.

## Değişiklikler

- EBBot'un kendi yönettiği Python backend işlemi çalışıyorsa SQLite dosyalarından yedek oluşturmayı reddet. Önce backend durmalıdır.
- Yedekleri kullanıcı verisi dizinindeki benzersiz bir `.ebbot-runtime-stage-* ` (geçici) klasöründe topla; veriler ve manifest tamamen yazılmadan **son yedek konumu** oluşturulmaz. Tamamlandıktan sonra tek bir yerel dizin rename işlemiyle sunulur.
- SQLite ana DB, WAL ve SHM'nin varlık/boyut/değiştirilme zamanları kopyalama öncesi ve sonrasında farklıysa yedeği reddet ve geçici çıktıyı sil. Bu kontrol hareketli dosyaları yakalamak içindir; **SQLite online backup API yerine geçmez, transaction düzeyinde snapshot garantisi vermez**.
- Kilitli WAL kopyalama hatası, yarıda kesilen stage->backup taşıması veya eksik dosya durumunda tamamlanmamış backup klasörünü sunma.
- `installDownloadedUpdate()`, önceden oluşmuş kurtarma yedeğini otomatik olarak temizlemez; bekleyen yedek varsa yüklemeyi durdurur. Yükleme başarısız olsa bile tamamlanmış yedek korunur.
- Electron masaüstü güncelleme anahtarı hâlâ derleme seviyesinde `false`.

## Çevrimdışı regresyon senaryoları

1. Yönetilen backend çalışıyorken yedek alma reddedilir.
2. Kilitli WAL (`EBUSY`) kopyalanamadığında DB/WAL/SHM ve mevcut dosyalar korunur; geçerli yedek ilan edilmez.
3. Yedek sırasında WAL değişimi algılanır ve stage reddedilir.
4. Yedek klasörünün son aşamada taşınması başarısız olursa tamamlanmamış manifesto yayılmaz.
5. Kapalı/stabil durumda ana SQLite, WAL ve SHM tek tamamlanmış manifestte birlikte bulunur.

Önceki taslak PR #131'deki geri yüklemenin staged-copy ile veri kaybını önlemesi, manifest allowlist ve eski recovery kopyasını koruması da aynen devam eder.

## Henüz çözülmeyen riskler

Bu bir canlı SQLite tutarlılığı kanıtı değildir. Program Files ve kullanıcı profili izinleri, gerçek SQLite transaction'ları, antivirüs tarafından kilitlenme, dosya sistemi güç kaybı/durability, Windows NSIS yükseltmesi/geri alma ve gerçek kullanıcı verisi migrasyonu ayrıca test edilmelidir. İleride güncelleme etkinleştirilecekse Python `sqlite3.Connection.backup` veya uygun SQLite checkpoint stratejisi gereklidir. Kod imzası, gerçek yayımlama ve SmartScreen kapıları da açık kalır.
