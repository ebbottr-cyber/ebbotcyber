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