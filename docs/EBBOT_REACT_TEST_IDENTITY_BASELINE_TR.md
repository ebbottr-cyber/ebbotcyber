> **Güncel sürüm notu (21 Kasım 2026):** Aşağıdaki 1.409 testlik ilk kanıt tarihî kabul referansıdır. PR #188 üzerinde 1.530 geçerli JUnit kimliğine yükseltilen yeni *taslak* kabul referansı için [ayrıntılı fark ve bağımsız inceleme gereksinimlerini](EBBOT_REACT_1530_IDENTITY_REVIEW_20261121_TR.md) okuyun. Kod onayı ve main branch koruması hâlâ eksiktir.

# EBBot — React JUnit test kimliği kabul kapısı (salt-okunur CI)

## Kapsam ve kanıt

21 Kasım 2026'da PR #180, HEAD `b5b663a29463f9224f434d6647c5677254236638` için GitHub Actions #44888953684 React job'u 1.409 PASS, 0 skipped, 0 failed üretti.
Kaynak JUnit arşivi: `ebbot-combined-react-vitest-truth`, artifact ID `14701096921`, iç dosya `vitest-results.xml`.

Bu raporun `testcase` öğelerindeki `classname` ve `name` değerleri ikili diziler halinde okunur. İkili diziler sıralanır; **tekrarlanan adlar silinmez**. `json.dumps(sorted(identities), ensure_ascii=False, separators=(',', ':'))` sonucunun UTF-8 SHA-256 özeti `.github/ebbot-react-test-baseline-1409.sha256` dosyasında arşivlenen geçmiş değerdir. Güncel 1.530 testlik taslak değer `.github/ebbot-react-test-baseline.sha256` içindedir. Süre, olay sırası, çalışma zamanı ve sonuç raporundan diğer metadata özete girmez.

## Koruma

- `scripts/validate_vitest_junit.py` ve `.github/workflows/ebbot-final-acceptance.yml` aktif birleşik PR #188'de en az **1.530** JUnit `testcase` bekler.
- `skipped`, `failure` ve `error` içeren testler reddedilir.
- Eksik `classname` veya `name`, geçersiz SHA biçimi ve bilinen `testcase` kümesinden sapma reddedilir.
- Çalışma sırasının değişmesi sorun yaratmaz; **bir testin silinip yerine farklı bir test eklenmesi** eşit test sayısına rağmen SHA farkı üretir.
- Baseline kontrollü revizyonun bir parçasıdır: yeni veya yeniden adlandırılmış meşru bir React testi için JUnit raporu, test farkı ve baseline hash güncellemesi **bağımsız PR review** ile birlikte değerlendirilmelidir.

## Değişiklik yapıldığında doğrulama

1. Tam Vitest JUnit raporunu GitHub CI üzerinden üretin ve hiçbir testin atlanmadığını doğrulayın.
2. `testcase` kimlik listesinin hangi testler için değiştiğini gözden geçirin. Yalnız fark onaylandıktan sonra `.github/ebbot-react-test-baseline.sha256` güncellemesini inceleyin.
3. `tests/test_validate_vitest_junit.py` ve tam React CI, tüm backend/auth/Türkçe kapıları aynı HEAD üzerinde PASS olmalı.
4. `main` dalında aktif ruleset, bağımsız review ve zorunlu `EBBot required gate / all offline acceptance checks` durumunu uygulayın (Issue #183). **Bu SHA tek başına GitHub repo ayarlarını veya review zorunluluğunu etkinleştirmez.**

## Sınırlar

Bu kontrol yalnız JUnit isim/suite kimliklerini korur; testlerin içeriğinin, assertion gücünün veya test dışındaki kodun değişmediğini ispatlamaz. Kaynak dosyası ve kontrol betiği aynı PR'da değiştirilebildiği için güvenliği **bağımsız inceleme ve korunan ana dal** ile tamamlanmalıdır. Canlı/paper trade, otomatik analiz ve Windows yayınlaması kapalıdır.
