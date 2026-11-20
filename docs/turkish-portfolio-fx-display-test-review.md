# Portföy FX görsel sözleşmesi — Türkçe test uyarlaması

**20 Kasım 2026, PR #96 üzerine zincirlenen taslak.**

## Neden

[PR #96 GitHub Actions tam React testi](https://github.com/ebbottr-cyber/ebbotcyber/actions/runs/44775953350) 1.499 testten 1.478 başarılı, 19 başarısız, 2 atlanan sonucunu verdi. Bunun 12'si `PortfolioPage.test.tsx` içindeki döviz ve değerleme görünümüne ilişkindir.

Bu 12 testi gerçek çıktı ile karşılaştırınca ortak neden **eski test metinleri** çıktı: kaynak Türkçe `formatMoney()` fonksiyonu iki ondalığı `tr-TR` ile yazıyor (`CNY 700,00`; `HKD 4.200,00`), testler ise `CNY 700.00`, `HKD 4,200.00` bekliyordu. Aynı şekilde `buildFxRefreshFeedback()` ve `getPositionPriceLabel()` artık Türkçe; testler eski Çince bildirimleri bekliyordu. Değerleme matematiğini yanlış yaptığına dair bu hata kayıtlarında kanıt yoktur.

## Değişiklikler

**Yalnızca test dosyası** `apps/dsa-web/src/pages/__tests__/PortfolioPage.test.tsx` değişir:
- Farklı para birimli hesapların gösterilen tutarları `tr-TR` sayı biçimiyle sınanır. Gerçek dönüşüm beklentileri, semboller, toplamlar, oranlar ve hisse adetleri aynı kalır.
- Aynı hesapta gösterilen HKD değeri yanlışlıkla CNY sayılmasın diye ek bir negatif kontrol eklendi.
- Kur yenilemesinin başarılı / güncellenecek çift yok / devre dışı / eski kur / çevrimiçi hata ayrımları mevcut Türkçe bildirimlerle sınanır. Eski kur veya hata durumlarında başarı kabul edilmez.
- Eksik fiyat `Fiyat yok`, kapanış tarihi `Kapanış fiyatı` etiketleriyle kontrol edilir.

Özellikle **değişmeyenler:** `portfolioFormat.ts`, `PortfolioPage.tsx`, `tryDisplayFx.ts`, backend, kur kaynakları, muhasebe, risk, alım-satım ve emir süreçleri.

## Sınırlar

Bu PR, 12 yanlış çeviri/biçim beklentisini test karşılıklarıyla uzlaştırır. Yeni kur toplamaz, eksik kurdan 1:1 hesap yapmaz, gecikmiş TCMB kuru kabul etmez. Ayrı `TCMB TRY display` testleri geçmeye devam etmelidir.

Tam Vitest, derleme, PWA ve güvenlik denetimleri yeşil olmadan **merge/deploy yapılmaz**. Testler başarılı olsa bile gerçek API ile döviz doğruluğu ve farklı hesaplar için hesaplama kanıtı ayrıca incelenmelidir.
