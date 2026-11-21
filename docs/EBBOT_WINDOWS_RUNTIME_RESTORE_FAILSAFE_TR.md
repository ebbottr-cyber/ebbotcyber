# EBBot Windows veri geri yükleme güvenliği — çevrimdışı test

**PR kapsamı:** Tamamen kaynak kodu ve geçici klasörlerle çalışan testler. Gerçek NSIS kurulumunu çalıştırmaz, gerçek kullanıcı verisi taşımaz ve masaüstü otomatik güncelleyicisini açmaz.

## Bulunan riskler

Önceki `copyRuntimeStatePathSync` uygulaması hedef dosya veya klasörü önce `fs.rmSync(target)` ile siliyor, sonra yedeği kopyalıyordu. Kopyalama hata verirse hedefteki mevcut kullanıcı verisi kaybedilebilirdi. İkinci risk: `runtime-state.json` içindeki beklenmeyen dosya yolları hedef uygulama klasöründen dışarı çıkabilecek biçimde kabul ediliyordu.

## Uygulanan önlemler

- Yedek, **önce hedefe komşu yeni bir geçici dizin/dosyaya eksiksiz kopyalanır**. Ancak kopyalama başarılı olursa eski hedef ayrı bir adla geçici olarak saklanıp yenisi yerleştirilir.
- Yeni dosyanın yerine taşınması başarısızsa önceki hedef geri alınır. Kopyalama/yerleştirme başarısızlığında geçici dosyalar temizlenir, yedek manifesti ve veri saklanır.
- Manifestte yalnız `DESKTOP_UPDATE_RUNTIME_RELATIVE_FILES` içindeki onaylı yollar kabul edilir. Eksik, boş, bozuk, mutlak veya göreli dizin dışına çıkan yol içeren liste **tamamen reddedilir**. Kısmi, tehlikeli bir restore yapılmaz.
- Dosya ve klasör kopyalanırken sembolik bağlantılar reddedilir; başka konumdaki verilerin yanlışlıkla içeri alınması önlenir.
- Geçici yedekler kullanıcıya ait gerçek uygulama klasöründe değil, yalnızca testte oluşturulan sentetik dizinler üzerinde çalıştırılır.

## Eklenen negatif testler

1. Veritabanı kopyası bozulduğunda mevcut veritabanı ve yeniden deneme yedeğinin korunması.
2. Tarama önbelleği içindeki bir alt dosyanın kopyası başarısız olduğunda mevcut klasörün korunması.
3. Yedek manifestinin `..` ile dizin dışına çıkmasının reddedilmesi, hiçbir dosyanın değiştirilmemesi.
4. Yedekte sembolik bağlantı görüldüğünde hedef ayarların korunması.

Önceden mevcut .env, hotspot geçmişi, WAL/SHM, kısmi retry, aynı-sürüm iptali testleri de çalışmaya devam etmelidir.

**Kalan açık konular:** Program Files yazma izinleri, gerçek kullanıcı verisi göçü, kurulum/yükseltme/geri alma/NSIS kaldırma, kilitli SQLite dosyası ve Windows cihaz testleri yapılmadı. Kod imzalama, SmartScreen ve otomatik güncelleme hâlâ engelli. Geliştirme bir yayın izni değildir.
