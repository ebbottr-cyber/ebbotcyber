# Solana fiyat gözlemi kalite kontrolü — GitHub'da, işlem yapmadan

Bu özellik, **önceden toplanmış** EBBot Solana gözlem JSON arşivlerini GitHub'da kontrol eder. Yeni fiyat çekmez, düzenli/sürekli veri toplamaz, emir göndermez, sanal veya gerçek işlem açmaz. Birden çok GitHub çalışmasındaki kayıtların tutarlılığını ölçer.

## Nasıl çalıştırılır?

1. GitHub → Actions → **Solana fixed-mint time-spaced observations (read only)** bölümünden gerektiğinde ayrı ayrı elle veri toplayın. Bir çalışmada en fazla iki coin için 60 saniye arayla üç gözlem alınır.
2. İlgili GitHub çalışma numaralarını (run ID) not edin. İlk doğrulanmış veri toplama örneği: **44779967482**. Aynı çalışmayı birden fazla girmeyin.
3. Actions → **Solana manual market history quality review (no orders)** → Run workflow → main bölümünde **observation_run_ids** alanına 1–6 çalışma numarasını virgülle ayırarak girin. Örnek: 44779967482. İlgisiz workflow kayıtları reddedilir.
4. Sonuç JSON'u ilgili çalışmanın Artifacts bölümünde **solana-history-quality-no-performance** adıyla yedi gün saklanır.

## Hangi sorunları yakalar?

- Coin adresinin ve havuz kimliğinin doğru kaynakla eşleşmesini, her çalışmada coin listesinin sabit tutulmasını.
- Tekrarlanan, düzensiz, gerçek dışı sıklıktaki ya da eksik zaman damgalarını.
- Pozitif ve sonlu fiyatları; sıfır, negatif, NaN veya uydurma fiyatları.
- Fiyat kaydı olmadan alım-satım değerlendirmesi üretilmesini.
- GoPlus güvenlik kaydı yokken watch sonucu oluşturulmasını veya 10.000 USD altında likiditeye sahip bir varlığın risksiz sayılmasını.
- Bir çalışmanın sonuç özetinin gerçek kayıt sayılarıyla uyuşmamasını.
- Başka bir iş akışından gelmiş arşivleri ve aynı veri çalışmasının tekrar kullanılmasını.

Fiyat yoksa ancak eski kayıtta başarısız sorgulanan sağlayıcı açıkça yazıyorsa, bu bir eksik veri satırıdır ve **degraded** olarak raporlanır. Fiyat uydurulmaz veya otomatik olarak doldurulmaz.

## Doğrulanan gerçek arşivler

- **44779967482:** 2 coin, toplam 6 geçerli fiyat, 0 eksik, sağlayıcı hatası yok. Kontrol sonucu complete_captures.
- **44777830658:** 2 coin, 3 geçerli fiyat, 3 eksik fiyat. Kontrol sonucu degraded_capture_data. Bu çalışmanın ilk kayıt şeması da denetleyici tarafından kabul edilir fakat eksikliği saklanmaz.

Bu sonuçlar canlı geçmişten doğrulanan **gözlem kalitesi** sonuçlarıdır. Alım-satım performansı, işlem gerçekleşme olasılığı veya kârlılık sonucu değildir.

## Güvenlik ve sınırlar

- Sadece manual workflow_dispatch; zamanlanmış job, cüzdan veya emir yoktur.
- GitHub token izinleri actions:read ve contents:read ile sınırlıdır.
- En fazla 6 arşiv, dosya başına 2 MB veri ve çalıştırma başına 2 coin/4 gözlem turu kabul edilir.
- Yalnızca kısa, kişisel bilgi içermeyen bir kalite özeti arşivlenir; gerçek fiyat JSON'ları tekrar yayınlanmaz.
- Kaynak JSON üzerindeki etiket tek başına kriptografik ispat değildir. Yalnızca uygun isimli GitHub Actions çalışmasının arşivi okunur. Fiyatların zincir üstü işlem fiyatı olduğu iddia edilmez.
- Veri kaydı GitHub Actions'ta yedi gün tutulur; uzun süreli veri deposu değildir. Eski arşivler süre sonunda erişilemez hale gelir.

**ready_for_verified_paper_performance her zaman false kalır.** API'nin alındı zaman damgası, zincir üstü gerçek işlem zamanı değildir. Doğrulanmış emir fiyatı, spread, likidite derinliği, ağ masrafı ve yeterli süreklilik olmadığı için simülatör bu kısa kayıtlardan gerçek kâr hesabı çıkarmaz.

## Yerel denetleme (isteğe bağlı)

```bash
python -m pytest -q tests/test_solana_history_quality.py
python -m scripts.validate_solana_history --inputs observation-a.json observation-b.json
```
