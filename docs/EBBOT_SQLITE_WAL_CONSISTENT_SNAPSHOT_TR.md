# EBBot — SQLite WAL tutarlı offline snapshot (deneysel, otomatik kullanılmaz)

**Durum:** Taslak ve `release_status: BLOCKED`. Bu çalışma, mevcut Windows yedekleme akışının yerini **henüz almamaktadır**. Sadece açıkça çağrılan bir SQLite yedekleme komutu ve sentetik testler eklenmiştir.

## Gerçek sorun

SQLite WAL modundayken `stock_analysis.db` ile `stock_analysis.db-wal` dosyasının ayrı dosya kopyaları birbirinden farklı işlem anlarını temsil edebilir. Yalnızca dosya boyutu ve zaman damgası karşılaştırmak, tutarlı bir veritabanı anlık görüntüsünü kanıtlamaz.

`scripts/ebbot_sqlite_snapshot.py` bu sorunu SQLite'ın yerleşik `sqlite3.Connection.backup` API'sini kullanarak ele alır:

- Kaynak SQLite veritabanını `mode=ro` olarak açar; kaynakta şema, işlem veya commit değiştirmez.
- Kaynağın WAL'deki **commit edilmiş** satırlarını tutarlı bir SQLite anlık görüntüsüne kopyalar; henüz commit edilmemiş işlemleri dışarıda bırakır.
- Sonuç veritabanını `PRAGMA integrity_check` ile kontrol eder, WAL'siz tek dosya biçimine (DELETE journal mode) çevirir ve kapalı dosyayı yeniden doğrular.
- Önce yeni ve özel izinli geçici dosya üretir; doğrulanmış dosyayı yalnızca **hedef daha önce mevcut değilse** aynı disk üzerinde hard-link ile yayımlar. Mevcut hedefe yazmaz. Dosya sistemi hard-link kabul etmiyorsa hata vererek durur.
- SHA-256, dosya uzunluğu ve durum döndürür; çıktı içinde kullanıcı dosya yolu, SQL sorgusu, satırlar veya API anahtarı yoktur.
- Kaynak eksik/bozuksa, hedef mevcutsa, sembolik bağlantıysa veya dosya sistemi işlemi başarısızsa `BLOCKED` ve sıfır çıkış kodu olmayan sonuçla durur.

## Güvenli ve açıkça çağrılan giriş

Kaynak kodu:

```text
python main.py --ebbot-desktop-sqlite-snapshot --source <test-db> --destination <new-snapshot-db>
```

Bu özel giriş, normal `main.py` yapılandırması, scheduler, analiz modülleri, borsa veri ağları, kullanıcı bildirimleri ve FastAPI başlamadan önce işlemi tamamlar.

Windows PyInstaller içine aynı giriş dâhil edilir; GitHub CI'da kurulum çalıştırılmadan **yalnızca sentetik test SQLite dosyaları üzerinde** dondurulmuş .exe komutu doğrulanır. Doğrulama dosyayı release veya kullanıcıya dağıtmaz.

## Testler

- WAL işlemleri devam ederken tamamlanmamış satırları dışarıda bırakmak; commit edilenleri doğrulamak
- Mevcut snapshot'ın üzerine yazmayı reddetmek
- Bozuk SQLite kaynağını ve izin verilmeyen symlink'i reddetmek
- Yayımlama aşaması bozulursa eksik dosya bırakmamak
- Normal `main.py` runtime başlatılmadan CLI çalışması ve başarısızlıkta güvenli sonuç
- Gerçek Windows PyInstaller backend'de bir kerelik CLI smoke ve WAL commit tutarlılığı

## Henüz çözülmemiş entegrasyon

**Electron'un `backupPackagedRuntimeState` yöntemi bu Python aracını henüz çağırmıyor.** Mevcut PR #132'deki korumalı dosya kopyalama yönteminde DB/WAL/SHM yedeğinin işlem seviyesinde tutarlı olduğu iddia edilmez. Yeni SQLite anlık görüntüsünün Electron geri yükleme mekanizmasına bağlanabilmesi için:

1. Komutu yalnızca tam ve doğrulanmış Windows paketinde, doğru yerel `stock_analysis.exe` yoluyla çalıştırmak
2. WAL/SHM'yi snapshot ile **birlikte restore etmemek** ve var olan hedef yan dosyalar için güvenli göç kuralları oluşturmak
3. Mevcut recovery manifestini, yanlış/eksik/çift snapshot koşullarını ve rollback'i doğrulamak
4. Gerçek Windows SQLite kilidi, uygulama yeniden açılışı, Program Files kullanıcı izinleri ve sürüm yükseltmesini yalıtılmış cihaz testlerinde sınamak

Bu nedenlerle henüz gerçek kullanıcı verisi ile yedekleme veya yükseltme yapılmaz. Güncelleyici derleme seviyesinde kapalı; masaüstü kurulumu, yayın, scheduler, paper/live emirler kapalıdır. Kod imzalama ve SmartScreen engelleri de sürer.
