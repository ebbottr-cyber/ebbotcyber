# EBBot Türkçe Uyarı / Sohbet / Tarama arayüzü — inceleme

**20 Kasım 2026.** Bu düzeltme taslağı, PR #87 üzerine zincirlenmiştir; merge, deploy, scheduler ve canlı alım-satım yoktur.

## Kapsam
- **Uyarı Merkezi:** uyarı/notification başlıkları, bildirim kanal/durum açıklamaları, test sonuçları, çevresel kuralların gizlenmeyen uyarıları, geçmiş tablo başlıkları ve piyasa evresi kalitesi (yalnızca metin).
- **Sohbet:** hızlı analiz örneklerinin kullanıcıya görünen Türkçe kopyası, liste / silme / dışa aktarma / gönderim / sıkıştırma / kopyalama, görünen durum metinleri ve mesaj giriş örneği. Hızlı soruların **sembol kodları** ve API'deki `stockContext` değişmedi; geçmiş/uzak sunucudan gelen Çince isim/veri henüz Türkçeleştirilmedi.
- **Hisse Tarama:** ana menü, strateji/işlem butonları, durum başlıkları, sonuç tablosu, temel faktör açıklamaları ve geçmişin ana etiketleri. İşlem kimlikleri, strateji adları, `cn` market anahtarı, sabitler, matematik, algoritma, fiyat ve veri saklama alanları değiştirilmedi. Ayrıntılı hata tanılamaları ve dış veri açıklamalarında başka yabancı metinler bulunabilir; tüm tarama modülünün uçtan uca Türkçe olduğu iddia edilmez.
- **404:** sayfa başlığı, yönlendirme ve açıklama Türkçe.

## Neden eski çeviriler kaynakta hâlâ var?
`operatorText(legacyText, turkishText)` sadece **metin sunumunda** kullanılır. Üretimde `shouldForceTurkishUi()` her zaman true olduğundan Türkçe metin seçilir. Eski Vitest uyumluluk modunda Çince sabitler korunur; bu durum eski kontrat testlerini Türkçe sürüme karşı yanlış başarısız göstermez. Üretim sözleşmesi için ayrıca `VITE_EBBOT_TURKISH_TEST_MODE=true` ile test edilir.

## Doğrulama
- `operatorText` kaynak güvenlik testi ve üç sayfanın Türkçe üretim görünümü testleri.
- Eski sayfa testlerinden seçilen senaryolar, TypeScript/üretim build, ESLint, PWA; tam React regresyon ayrı ve bırakılan yayımlama engeli olarak raporlanır.
- UI ekran görüntüleri ve gerçek cihaz doğrulaması henüz yoktur.
- PR #87 son geniş React bazında **358 başarısız / 1.132 başarılı / 2 atlanan** test bulunmuştur. Bu çalışma sonuçlar doğrulanmadan 358 testin çözüldüğünü iddia etmez.

Rollback: bu taslak PR'ın commit'lerini geri al veya PR'ı kapat; veritabanı geçişi ve işletim ayarı yoktur.
