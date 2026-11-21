# EBBot — SQLite WAL/SHM dangling symlink koruması

**TASLAK · YAYIN ENGELLİ.** Bu PR, [#158](https://github.com/ebbottr-cyber/ebbotcyber/pull/158) üzerine yalnız **offline SQLite snapshot ve staging köprüsü** için eklenir. Gerçek kullanıcı SQLite dosyası, installer veya runtime güncelleme/geri alma yolu kullanılmaz.

## Hata ve düzeltme

`apps/dsa-desktop/sqliteSnapshotBridge.js` önceki sürümde hedef veritabanı dosyasını `fs.lstatSync(destination)` ile koruyordu; fakat `destination-wal` / `destination-shm` kontrolünde `fs.existsSync()` kullanıyordu. **Boşa düşen sembolik bağlantı** (dangling symlink) için `existsSync() = false` olmasına rağmen dizinde mevcut bir ad/bağlantı bulunabilir. Böyle bir durumda snapshot veya restore staging aşaması yanlış biçimde güvenli hedef varsayabilirdi.

Yeni koruma `-wal` ve `-shm` için `fs.lstatSync(path, {throwIfNoEntry:false})` ile **var olan her dosya sistemi girişini**, kırık symlink dâhil, reddeder. Köprü daha önce olduğu gibi yeni bir staged destination dışında hiçbir DB, WAL veya SHM üzerine yazmaz. Otomatik güncelleme/restore fonksiyonu devreye alınmamıştır.

## Regresyon testleri

- `apps/dsa-desktop/tests/sqliteSnapshotBridge.test.js` dosyasına **iki yeni senaryo** eklendi:
  1. Hem WAL hem SHM için Windows'ta gerçek symlink izni gerektirmeyen taklit `lstatSync` sonucu döndürülür. Hem `stageSnapshotRestoreCandidate` hem `createFrozenSnapshotCandidate` reddetmeli; frozen child runner **hiç çağrılmamalı**, kaynak snapshot ve hedef dizin korunmalı.
  2. İşletim sistemi izin verirse gerçek boşa düşen WAL sembolik bağlantısı oluşturulur. Restore bunun üzerine yazmadan fail-closed reddeder. Windows CI symlink yetkisi yoksa bu ek fiziksel senaryo atlanabilir; deterministic sahte `lstatSync` senaryosu **atlamaz**.
- GitHub Windows 2022 desktop source/Node/SQLite testleri üzerinden doğrulanır. NSIS/PyInstaller job sadece `push` ile `--publish never` geçer; hiçbir gerçek kurulum, EXE yayınlama veya satış/emir işlemi yok.

## Açık sınırlar

Bu kontrol yalnız **bozuk son-bileşen sidecar bağlantıları** için. Windows junction, ara klasör symlink'leri, NTFS güç kaybı, anti-virüs kilidi veya aktif gerçek kullanıcı veritabanının WAL transaction bütünlüğü için genel test/yetki değildir. Bu modül kullanıcı verisini otomatik restore etmiyor; `DESKTOP_UPDATES_ENABLED=false`, `release_status=BLOCKED`, cüzdan/gerçek-pap­er işlem ve scheduler kapalı kalıyor.

**Geri alma:** Taslak PR'ı kapat. `main`, PR #158, gerçek kullanıcı dosyaları ve yayın durumu değişmez.
