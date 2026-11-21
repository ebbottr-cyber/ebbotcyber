# EBBot — main ile Windows taslak PR zincirinin birleştirme öncesi provası

**Durum: yalnız denetim. Birleştirme/yayın/kurulum/emir YOK.**

## Neden ayrı dal?

21 Kasım 2026 kontrolünde `main` dalının başlangıç Windows release-candidate dalından ayrıldığı doğrulandı. Ana dala yeni gelen 5 commit, Solana kalite raporu alanındaki değişiklikleri ve EBBot kimliğini / otomatik güncellemenin kapalı olmasını içeriyor. Özellikle Windows PR #123'ün dokunduğu `main.js`, `package.json`, `package-lock.json`, yükleme ekranı ve bazı testler `main` tarafında da değiştirildi. Yalnızca `git compare` sonucu **olası** örtüşmeyi gösterir, gerçek satır çakışmasını kanıtlamaz.

Bu PR, `main` SHA `1b3a327c74f0484af9b942f098e370e6fb4f80ec` üzerinden açılan bağımsız bir *audit-only branch* içerir. Diğer 10 taslak PR'a dokunulmaz: `#117 → #123 → #125 → #127 → #131 → #132 → #134 → #135 → #136 → #139`.

## Gerçek üç yönlü karşılaştırma

`scripts/audit_ebbot_desktop_merge_tree.py` her ikisi de gerçekten fetch edilmiş iki Git ref'i için:

1. `git merge-base` ile ortak tabanı bulur.
2. Ortak tabandan itibaren **iki taraftaki değişmiş dosyaları ayrı ayrı** listeler; örtüşen dosyaları ve Windows dosya sistemi açısından harf büyüklüğü/küçüklüğüyle çakışabilecek isimleri kaydeder.
3. `git merge-tree --write-tree --messages <main> <PR139>` ile **dosya ağacında gerçek üç yönlü çatışmayı sadece hesaplar**. Git branch/ref/working tree değiştirilmez; hiçbir merge commit üretilmez ve GitHub PR'ı birleştirilmez.
4. `CLEAN_DRY_RUN` veya `REVIEW_REQUIRED_CONFLICTS` raporu üretir. Çakışma varsa iş akışı kırmızı kalır ve toplu entegrasyon testleri yapılmaz.
5. Çakışma yoksa merge-tree'nin ürettiği **geçici Git tree SHA'sını** runner'ın geçici dizinine `git archive` ile dosya kopyası olarak açar. Bu, bir Git merge/commit değildir. Yalnız bu geçici dosyalarda kaynak, imza-gate, SQLite WAL, Node/Electron testleri çalıştırılır.

## Güvenlik ve kanıt sınırları

- CI iş akışı yalnız `contents: read` iznine sahiptir; `persist-credentials: false` kullanılır.
- `main` ve son #139 branch'i kaynak olarak güncel bir şekilde çekilir. Report, o anda ölçülen SHA'ları kaydeder.
- Yalnız JSON raporu kısa süreli GitHub artifact olarak yüklenebilir. `stock_analysis.exe`, NSIS installer, `.env`, API anahtarı, canlı pazar verisi veya gerçek SQLite dosyası artifact değildir.
- `npm ci --ignore-scripts` ile yerel binary kurulum scriptleri engellenir; Electron uygulaması/Windows yükleyici çalıştırılmaz.
- Güncelleme `DESKTOP_UPDATES_ENABLED=false`, otomatik piyasa taraması/scheduler, gerçek ve paper emirler kapalı kalır. `release_status=BLOCKED` raporu **her zaman** korunur.
- Geçici birleşim testlerinin yeşil olması, real Windows kullanıcı cihazı kurulumunun, imza/SmartScreen'in, NTFS güç kesintisinde recovery'nin veya otomatik sürüm yükseltmesinin güvenliğini kanıtlamaz.
- Olası çakışmalar, `main` SHA'sındaki daha yeni commitler silinmeden, ayrıca incelenmelidir. Bu audit PR'ı **asla** Windows ürün kodunu `main` üzerine merge etmez.

## Kanıt zinciri

PR #139 gerçek Windows PyInstaller + NSIS `--publish never` koşusu [44819008515](https://github.com/ebbottr-cyber/ebbotcyber/actions/runs/44819008515) başarılıydı. Bu yeni prova ise `main` ile birleştirildiğinde değişen kodun tam olarak aynı olacağını **iddia etmez**; yeni karşılaştırmanın sonucu ayrıca ölçülecektir.

**Geri alma:** Denetim PR'ını kapatmak ve ayrı audit branch'ini silmek, ana dala ve önceki taslak Windows çalışmalarına dokunmaz.
