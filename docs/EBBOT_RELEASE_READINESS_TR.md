# EBBot — Yayın Öncesi Denetim

18 Kasım 2026, taslak PR #35. Yalnızca GitHub kaynak kodları incelenmiştir; gerçek cihaz veya üretim sunucusunda test yapıldığı anlamına gelmez.

## Depoda doğrulananlar

- Beyaz panel /overview, eski hisse analiz /, Meme Coin /meme-coins rotaları korunur.
- PWA manifesti /overview ile açılır; service worker finans/API oturumlarını önbelleğe almaz.
- Meme Coin endpointleri GET-only ve tarayıcısı varsayılan kapalıdır. Gerçek emir/cüzdan/fill motoru bu entegrasyonda yoktur.
- Eski günlük analiz workflow'u workflows_disabled/00-daily-analysis.yml.disabled içinde arşivlenmiştir ve zamanlama içerir; aktif dizine geri taşınmaz.
- Eski ci.yml ve .env.example bulunmuyor. Dosya yollarının GitHub commit araması da sonuç döndürmedi.
- .gitignore içindeki .env.* örüntüsü gelecekte bir örnek ortam dosyasının eklenmesini ayrıca etkileyebilir.

## Önceki genel regresyon ve kalan engeller

Geçmiş kapsamlı pytest: 44 failed / 8565 passed / 2 skipped. Hataların çoğu artık aktif olmayan .github/workflows/ci.yml, .github/workflows/00-daily-analysis.yml ve .env.example sözleşmelerine bağlıydı. Ayrı Türkçe bildirim/prompt uyumluluk sorunları PR #35 üzerinde hedefli testlerle düzeltildi. Tam test takımının geçmesi henüz doğrulanmadı.

Eski günlük workflow'u yalnızca testi yeşil göstermek için geri yüklemek istenmeyen piyasa analizi zamanlamasını tetikleyebilir. Eksik CI dosyası yerine sahte workflow oluşturulmaz. Sözleşmeler mevcut modüllere göre yeniden değerlendirilmelidir.

## Otomatik, salt-okunur audit

Komutlar:

    python scripts/audit_ebbot_release.py --json
    python scripts/audit_ebbot_release.py --strict
    python -m unittest discover -s tests -p test_ebbot_release_audit.py -v

Normal mod JSON raporu üretir, teknik/manuel engelleri açıkça belirtir. Strict mod çözülmemiş engel veya insan doğrulaması varken kod 1 ile çıkar. GitHub CI raporu artifact olarak kaydeder; raporun oluşturulabilmesi üretime hazır demek değildir.

## Yayına alma ön koşulları

1. Genel backend regresyonunu geçerli sözleşmelere göre tamamlamak.
2. Gerçek iPhone ve Android HTTPS PWA kurulumu ve navigasyonu.
3. Üretim yönetici oturumları, API yetki kontrolü ve sızma testleri.
4. Finansal veri kullanım/lisans kontrolü; gecikmeli fiyatları doğru etiketleme.
5. Paralel Meme Coin dalını yeniden karşılaştırma; yazma/emir endpointleri için bağımsız onay.

Bu audit hiçbir zaman live trade, deploy veya GitHub PR merge işlemi başlatmaz.

## Devre dışı günlük analiz testlerinin göçü

Dört tarihsel test dosyası artık `workflows_disabled/00-daily-analysis.yml.disabled` içeriğindeki eski veri sağlayıcısı, model, bildirim ve SearXNG yapılandırmalarını okur. Amaç, eski örnek yapılandırmanın tutarlılığını korumaktır; bu testler **üretimde çalışacak zamanlanmış bir işin varlığını doğrulamaz**. Aktif `.github/workflows/00-daily-analysis.yml` bilinçli olarak oluşturulmadı. `audit_ebbot_release.py` eski workflow'un yanlışlıkla yeniden etkinleştirilmesini ayrıca engeller. Eksik `.env.example` ve eski `ci.yml` testleri çözülmediği sürece tam regresyon yayına izin vermez.


## Güvenli örnek ortam dosyası — V8

- `.env.example`, gerçek frontend sağlayıcı listesinden oluşturulmuş, **hiçbir API anahtarı içermeyen** açıklamalı bir şablondur. Her sağlayıcı örneği yorum satırındadır; otomatik olarak bir LLM, veri sağlayıcı, cüzdan veya işlem modu etkinleşmez.
- SearXNG public-instance keşfi varsayılan olarak `false`, timeout `10` saniye, self-host URL boş tutulur. Kaynak: mevcut `src/config.py`, `docs/full-guide_EN.md` ve LLM sağlayıcı şablonları.
- `.gitignore` yalnızca `.env.example` için istisna içerir; gerçek `.env` ve `.env.*` dosyaları gizli kalır.
- Eski `.github/workflows/ci.yml` **üretilmedi**; onun yapısına dair eski testler hâlâ kalan teknik borçtur.
- CI'a günlük arşiv workflow uyumluluğu ve güvenli örnek ortam dosyası için ayrı hedefli test görevi eklendi; gerçek tam test ve release blocked kontrolleri aynen kaldı.

## Pasif CI sözleşmelerinin taşınması — V9

- `.github/workflows/ci.yml` **yeniden etkinleştirilmedi**. Eski path-filter, üçlü shard, Futu SDK ve macOS paketleme sözleşmeleri yalnızca `workflows_disabled/ci.yml.disabled` ile diğer arşivlenmiş workflow'ların **tarihsel davranışını** test eder; bunlar şu anda çalışan CI işleri değildir.
- Aktif `.github/workflows/ebbot-integration.yml` için ayrı fail-closed sözleşme eklendi: tam backend regresyonu, salt-okunur Meme Coin varsayılanı, yayın yapmayan izinler ve arşivlenmiş günlük analizin aktif olmaması.
- `ci-and-packaging-contracts` adlı hedefli CI işi iki sözleşme grubunu koşar. Tam regresyon işi hâlâ bağımsız olarak **zorunlu** kalır.
- Futu masaüstü paketleme, Docker yayınlama, günlük analiz ve gerçek alım-satım bu PR'da etkinleştirilmez. Arşivdeki testlerin yeşile dönmesi bu işlerin güncel CI ile doğrulandığı veya yayına hazır olduğu anlamına gelmez.
- Tam backend sonucunun PR #35'in en son commit'i üzerinden doğrulanması beklenir; kaynak testleri gerçek cihaz/sunucu testlerinin yerini tutmaz.

## Sentetik paper preview — V10

- Yalnızca statik sayılarla çalışan `src/services/meme_coin_paper_preview.py` matematiksel senaryo modülü eklendi; dış servis, alım-satım, cüzdan, API, veritabanı veya zamanlayıcı içermez.
- Varsayımsal pozisyon büyüklüğü, havuz likiditesi, veri yaşı ve günlük zarar bütçesi sınırları `tests/test_meme_coin_paper_preview.py` ile doğrulanır; test aktif salt-okunur CI işinde çalışır.
- Modülün sunduğu hipotetik PnL **gerçek bir işlem sonucu değildir**; paneldeki performans metrikleri `null`, paper trading ve live trading kapalı kalır.
- Sınırlamalar ve gerçek paper trading için sonraki gereksinimler `docs/MEME_COIN_PAPER_PREVIEW_V1.md` içinde belgelenmiştir.

## Sentetik işlem kayıtları — V11

- Yeni Coin Avcısı ve Momentum Avcısı için API/sunucudan bağımsız, yalnızca bellekte yaşayan sentetik kayıt motoru eklendi.
- Aynı olayın iki kez hesaplanması engellenir; çelişkili olay ID'leri tüm hesaplamayı reddeder.
- Strateji günlük zarar bütçesi %2, stratejiler arası ortak günlük zarar bütçesi %3 ve manuel durdurma kontrolü uygulanır. Bu sınırlar varsayımsal matematiksel testtir, gerçek emir güvenliği veya gerçekleştirilmiş PnL değildir.
- Önceki `"0"` metin değerinin geçersiz sayılmasına neden olan sayısal ayrıştırma hatası giderildi.
- Bağımsız testler yeni modülle birlikte salt-okunur CI görevinde koşar; aktif paper emir motoru veya canlı işlem yaratılmadı.
- Detaylar `docs/MEME_COIN_SYNTHETIC_JOURNAL_V1.md` dosyasında.

## Kalıcı sentetik günlük — V12

- Yerel SQLite kayıt prototipi yalnızca manuel `enabled=True` ile açılır;
  hiçbir backend route veya zamanlayıcıya bağlanmaz.
- İşlem ID'si tekilliği, iki ayrı strateji günlüğü, atomik yazma, hash zinciri,
  tekrar başlatmada doğrulama, kalıcı kill switch ve stratejiler arası günlük
  zarar bütçesi testlerle denetlenir. Gerçek emir veya doldurulmuş işlem yoktur.
- `tests/test_meme_coin_persistent_journal.py` yeni salt-okunur CI hedefli
  testlerine dahil edildi (yalnızca geçici sentetik SQLite dosyaları kullanır).
- `docs/MEME_COIN_PERSISTENT_JOURNAL_V1.md` riskleri ve kullanım sınırlarını
  açıklar. Bu modül **production-grade** denetim günlüğü değildir.
