# EBBot — Windows paketli backend sağlık denetiminin entegrasyonu

**TASLAK / RELEASE BLOCKED.** Bu çalışma #151 üzerine stack edilir. Kaynaklar: `#151=7228c6cd645a3ec59e0c52287ff0af03610096cc` ve bağımsız `main=65b77f17085224a2f01dda3ee8d3807dbe789e10` sağlık kontrolü commit'i. Hiçbir eski PR veya `main` değiştirilmez.

## Korunan iki güvenlik yolu

**1. Tek atımlık SQLite snapshot**: `main.py` başındaki `--ebbot-desktop-sqlite-snapshot` işlemi, backend modülleri yüklenmeden kısa devre yapmaya devam eder. `sqlite3.Connection.backup` tutarlılığı, SHA ve DB/WAL/SHM provası eski draft zincirindeki gibidir; uygulamanın otomatik restore/update yoluna dahil edilmemiştir.

**2. Kısıtlı Windows backend sağlık kontrolü**: `main` tarafındaki `EBBOT_PACKAGED_HEALTH_PROBE=1` sadece frozen PyInstaller executable, `GITHUB_ACTIONS=true`, `--serve-only --host 127.0.0.1 --port N` tam argüman dizisiyle etkinleşir. `api/app.py` sadece `GET /api/health` sunar; analiz API'sini, normal docs/SPA ve scheduler/remote index refresh başlatılmasını engeller. `scripts/probe_ebbot_packaged_health.py` yalnız Windows GitHub runner'da izin listeli ortam ile yerel portu yoklar, süreci sonlandırır. Normal backend/Electron başlatma değildir.

## Birleştirme ve CI öncesi kanıt

- `api/app.py` ve `main.py` sağlık değişiklikleri #151'in mevcut dosyaları üstüne bağlamsal satır eşleşmesiyle işlendi; her hunk yalnız 1 kez eşleşmek zorundaydı. `main.py` içindeki **offline SQLite CLI girişi korunur**.
- Bağımsız `main` sağlık probu script'i, Python testleri ve Türkçe sınırlama belgesi eksiksiz alındı.
- Windows offline workflow, sağlık Python kaynak testlerini mevcut SQLite/NSIS/Authenti­code testlerine **ekler**. Gerçek `stock_analysis.exe` yalnız GitHub Actions Windows runner'ında `127.0.0.1` için sınanır. `--publish never` korunur; exe, installer ve kullanıcı dosyaları artifact olarak yüklenmez.
- Yalnız CI başarılı olmadan "paket açılışı çalışıyor" denmeyecek. Sağlık probunun geçmesi, Electron UI, gerçek NSIS kurulumu, SmartScreen, user SQLite restore, gerçek/paper trade veya otomatik tarama geçerliliği anlamına gelmez.

## Korunan engeller

`DESKTOP_UPDATES_ENABLED = false`. Yazma/işlem API'leri, wallet, gerçek ve paper alım-satım, scheduler ve otomatik piyasa taraması kapalıdır. `release_status: BLOCKED`. Herhangi bir dağıtım veya `main` merge için ayrı insan incelemesi gereklidir.

**Geri alma:** Bu ayrı taslak PR kapatılır; #151 ve `main` etkilenmez. `main` yeniden ilerlerse önce SHA/diff kıyaslaması tekrarlanır.
