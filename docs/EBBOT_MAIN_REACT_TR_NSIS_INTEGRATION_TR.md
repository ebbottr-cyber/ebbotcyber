# EBBot — Güncel main üstünde Türkçe React / NSIS / SQLite taslak entegrasyonu

**TASLAK — RELEASE BLOCKED.** Bu kod ağacı yalnız `main=c95fb7f2ee63d5bee131bd59b25a38ae420d0546` ve `PR #174=6429c459a3cc71d9a4e9638559d3f49634eb157d` SHA çiftinden üretilmiştir. Farklı bir main commit'i gelirse yeniden incelemeden birleştirilemez.

## Uyum ve kaynak politikası

- Bu entegrasyon commitinin **tek ebeveyni** yukarıdaki `main` commitidir; önceki #117…#174 taslak PR'lar **merge edilmedi**, tarihçe otomatik taşınmadı. Bütünleşik kod ağacı PR #174'ten alınır, sadece güvenli `push` CI dal adı ve bu belge eklenir.
- Git tree karşılaştırması: main'in **1.284/1.284** normal dosya yolu korunuyor. Son main commitinin frozen/CI salt-okunur `api/app.py`, `ci-ui-smoke.js`, UI React testleri, Python probe ve Türkçe React dokümanının Git blob SHA'ları **birebir aynı**. `uiText.ts` ise önceki taslak geliştirmelerin daha geniş Türkçe sözlük kayıtlarıyla bilinçli olarak korunur.
- Önceki #161'in SQLite WAL/SHM bozuk symlink no-clobber düzeltmesi; #171'in **9 NSIS kontrolü + 14 Python mutasyon testi**; gerçek Windows NSIS `--publish never`, SHA-512/Authenticode ve asla yayınlamama kapıları aynı kaynak ağacında.
- Windows CI gerçek paketli `EBBot.exe` içinde Türkçe React ana menü, Kullanım ve Veri Merkezi gezintisini; yalnız frozen `127.0.0.1` sağlık backend'ine bağlı, gerçek API/trading yokken sınar.

## CI ve yayın sınırları

**Bu PR'ın kendine ait Windows `push`, full backend, React/TypeScript/PWA, Solana, NSIS source denetim sonuçları ayrı ayrı kontrol edilmelidir.** Eski SHA'lardaki başarı yeni PR'a otomatik taşınmaz. PR olayında Windows installer job'unun `skipped` olması normaldir; paketleme yalnız push'ta gerçekleşir.

Bu **gerçek kullanıcı Windows NSIS install/upgrade/uninstall testine eşdeğer değildir**. Normal React pazar API bağlantısı, aktif DB WAL kilitleri/güç kesintisi, gerçek kullanıcı `.env` ve dosya taşıma, kod imzası, SmartScreen/Defender, production auto-update ve performans henüz test edilmedi. `release_status=BLOCKED`, `DESKTOP_UPDATES_ENABLED=false`, gerçek/paper emir, scheduler, otomatik analiz/tarama kapalı kalır.

Geri alma: bu draft PR kapatılabilir, `main` ve önceki taslak PR'lar değiştirilmez. Bağımsız insan incelemesi ve ayrıca kullanıcı onayı olmadan merge/release yoktur.
