# Solana kalite paneli — incelenmiş, salt okunur rapor dosyası

## Kaynak ve sınır

Meme Coin ekranındaki **Solana arşiv veri kalitesi** bölümü, `apps/dsa-web/public/solana-quality-reviewed.json` adlı **aynı kaynak deposunda kod incelemesinden geçmiş** dosyayı görüntüler. Dosya ham fiyat geçmişi, token seçimi veya ticaret önerisi içermez. Tarayıcı yalnızca uygulama sunucusundaki JSON dosyasına GET isteği gönderir; GitHub kimlik bilgileri, ayrı bir API anahtarı, piyasa verisi sorgusu veya arka plan taraması gerektirmez.

20 Kasım 2026 tarihli başlangıç kaydı, gerçek GitHub Actions denetiminden (`44791912581`) gelir: ilk arşiv `44779967482` için 6/6, eski arşiv `44777830658` için 3/6 geçerli fiyat; birleşik 9 geçerli, 3 eksik, 18 engellenmiş strateji değerlendirmesi, 0 izleme onayı. Doğrulanmış sanal işlem kârı **yoktur**.

Bu, **canlı GitHub senkronizasyonu değildir**. Kullanıcı arayüzü yeni kalite sonuçlarını otomatik aramaz; başka tarihli sonuçlar yalnızca yeni bir kaynak denetimi ve gözden geçirilmiş PR üzerinden JSON dosyası güncellenip yeni web sürümü yayımlandığında görünür. GitHub Actions kaynak artifact'leri 7 gün içinde silinebilir; yayımlanmış bu kısa sayı özeti ise kaynak deposunun sürüm geçmişindedir. JSON içindeki metadata tek başına kriptografik kaynak doğrulaması sağlamaz; kaynak bağlantıları ve manuel kod incelemesi gereklidir.

## Yeni rapor ekleme (manuel)

1. Gerçek gözlem iş akışındaki arşiv ID'lerini kaydedin; tam kimlik ve maliyet/performans sınırlamalarını [Solana geçmiş kalite dokümanında](solana-market-history-quality.md) inceleyin.
2. `scripts.validate_solana_history` ile kaynağı offline doğrulayın ve GitHub Actions denetimi tamamlanmış bir rapor alın. Eksik veri, kimlik uyuşmazlığı veya şüpheli raporda **başarılı** yazmayın.
3. Sadece doğrulanmış sayıları, ilgili GitHub çalışma ID'lerini ve UTC denetim tarihini JSON dosyasına aktarın. Ham fiyat, özel anahtar veya cüzdan bilgisi eklemeyin.
4. Ayrı bir PR açın; dosya değişikliklerini denetleyin. Otomatik kaynak yenileme, doğrudan arşiv ZIP'inden tarayıcıda okuma ve çalışma izni verme özellikleri eklemeyin.
5. PR'da tip/test ve görünüm doğrulaması yeşil olmadan `main` dalına birleştirmeyin.

## Bozuk veya bulunamayan rapor

Rapor yüklenemezse, şema geçersizse, çalışmanın ID'si yinelenirse, ham gözlem sayıları uyuşmazsa, kaynak durumları tutarsızsa veya cüzdan / gerçek işlem / kârlılık hesaplama bayrağı `true` olursa panel **hiçbir sayaç göstermez**. Yeni bir rapor devreye alınsa bile önceki sayılara sessizce geri dönmez.

Kaynak dosyanın varlığı emir, otomatik tarama, izleme izinleri veya kendiliğinden öğrenmeyi etkinleştirmez. `watch` sayısı olsa da bu gerçek veya sanal işlem izni değildir.
