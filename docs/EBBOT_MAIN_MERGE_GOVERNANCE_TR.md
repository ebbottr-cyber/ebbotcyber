# EBBot — GitHub ana dal birleştirme ön denetimi

İş akışı: .github/workflows/ebbot-merge-governance-advisory.yml

Bu denetim, başarılı kod testlerinden bağımsız olarak main koruması ve bağımsız PR incelemesi olup olmadığını GET-only GitHub REST API ile kontrol eder.

- Main hedefli active ruleset, protected main dalı, zorunlu PR ve en az bir bağımsız onay.
- Son commit onayı veya eski onayların geçersiz kılınması, zorunlu güncel CI status check.
- Gerekli check tam olarak: EBBot required gate / all offline acceptance checks.
- Force-push, branch silme ve sınırsız bypass engelleri.
- PR açık, main hedefli, taslaktan çıkarılmış; insan reviewer PR sahibinden farklı ve onayı son commit SHA için geçerli.

Çıktı BLOCKED veya GOVERNANCE_PRECHECK_PASSED, JSON artifact ile kaydedilir. Bugün main.protected=false, rulesets boş, PR #188 draft ve bağımsız approval bulunmadığından RED/ BLOCKED beklenir. Bu kod testi başarısızlığı değil, açık idari güvenlik gereğidir.

Workflow salt okunur; API GET dışında erişim yapmaz. Kod testleri, mevcut EBBot required gate ve repo settings aynen bırakılır. Bu job kendi başına GitHub required check olmaz; yönetici ayrıca kuralları etkinleştirmelidir.

Yönetici ayarı: https://github.com/ebbottr-cyber/ebbotcyber/settings/rules

Bu iş yalnız pull_request olayında tetiklenir. Ruleset veya review değiştiğinde PR güncellemesi ya da GitHub Actions üzerinden yeniden çalıştırma gerekebilir.

Main merge, release, otomatik analiz, broker ve sanal/gerçek emir, installer yayını veya Windows üzerinde kurulum işlemleri burada yapılmaz.

Rapor denetim için yararlıdır ama kendi dalındaki kod PR sahibi tarafından değiştirilebildiğinden tek başına güvenlik sınırı değildir. Güvenlik GitHub main koruması ve bağımsız reviewer yetkisi ile uygulanmalıdır.