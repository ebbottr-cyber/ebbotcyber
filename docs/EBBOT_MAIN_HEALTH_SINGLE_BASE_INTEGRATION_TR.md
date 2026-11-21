# EBBot — Güncel main ile tek tabanlı, yayın engelli entegrasyon adayı

**Durum: TASLAK / RELEASE BLOCKED.** Kod, `main=65b77f17085224a2f01dda3ee8d3807dbe789e10` ve taslak PR #155 head `dd2470b86cb389278da7a1fd93a2d0b88e53678a` kaynaklarından üretilmiştir. Sonradan değişen herhangi bir branch kendiliğinden bu adayın parçası **değildir**.

## Amaç

PR #151, `main` üzerine yeni frozen localhost health commit'i gelince GitHub'da `mergeable=false` oldu. PR #155, bu yeni commitin özelliklerini zaten test amaçlı koduna taşıdı ama kendi zinciri eski `main` ebeveynine bağlı kaldı. Bu nedenle **`main`'in en son commitini tek ebeveyn alan** bağımsız ve yeni bir entegrasyon adayı oluşturuldu. Eski #151 ve #155 PR'lar korunur, hiçbiri merge edilmez.

## Kaynak bütünlüğü

Bu adayın Git dosya ağacı, PR #155 head dosya ağacına dayanır. `main` içindeki **hiçbir dosya yolu kaybolmamıştır** (Git tree path denetimi). Özellikle `api/app.py`, `scripts/probe_ebbot_packaged_health.py`, `tests/test_ebbot_packaged_health_probe.py` ve sağlık belgesinin Git blob içerikleri `main` ile **birebir aynıdır**. `main.py` eski ana dalın localhost sağlık modunu **ve** önceki SQLite snapshot erken-çıkış CLI'sini birlikte içerir.

`main`'deki Solana kalite verisi, web kalite testleri, güncel desktop identity main-gate ve bütünlük/attribution dosyaları korunur. Sadece bağımsız `integration/` branch tetiklemesi Windows workflow'undaki push allowlist'e eklenmiştir; `main` workflow'u veya `main` refs'i değiştirilmedi.

## Güvenlik ve testler

- Windows 2022 GitHub Actions koşusunun **push** işinde `stock_analysis.exe` PyInstaller ile yerel üretilir, sentetik SQLite WAL snapshot smoke çalışır; NSIS `electron-builder --win nsis --publish never` derlenir; SHA-512/Authenticode gözlem ve yalnız `127.0.0.1` frozen health testi yapılır.
- FastAPI health modu yalnız frozen + GitHub Actions + tam `--serve-only --host 127.0.0.1 --port N` argümanlarıyla, genel route/scheduler/market refresh açılmadan çalışmalıdır. Dış API/real-paper emir, otomatik tarama, wallet ve updater **engellidir**.
- Windows **kurulum yükleyicisi çalıştırılmaz/yüklenmez**, EXE veya kullanıcı verisi artifact olarak saklanmaz; yalnız audit JSON'u olabilir. Gerçek kullanıcı SQLite backup/restore ve NSIS upgrade/uninstall ayrı izolasyon testleri gerektirir.
- PR kaynak kodunun test edilmesi, **gerçek install veya yayın yetkisi** vermez. Windows imzalama, SmartScreen/Defender, lisans/atıf ve cihaz bazlı veri koruma kontrolü beklenir. Yayın `BLOCKED`, updater hard-off kalır.
- Bu geçici branch/test sonucunda çatışma yok diye otomatik ana dal merge yapılmaz. İnsan incelemesi + CI + **ayrı kullanıcı onayı** zorunludur.

**Geri dönüş:** Bağımsız taslak PR'ı kapat; önceki kodlar, kullanıcı dosyaları ve `main` değişmez.
