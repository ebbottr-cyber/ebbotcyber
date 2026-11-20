# Türkçe portföy operatörü ve Vitest eski testleri — inceleme notu

Tarih: 20 Kasım 2026. Bu çalışma PR #85 üzerine kurulu yeni **taslak** PR'da yapıldı. Üretime dağıtım, main merge, otomatik analiz, emir veya gerçek alım-satım etkinleştirme içermez.

## Sorun: üretim ile eski testlerin dil varsayımları ayrışmış

İlgili karşılaştırma CI çalışması [44504656629](https://github.com/ebbottr-cyber/ebbotcyber/actions/runs/44504656629): 359 başarısız / 1.119 başarılı / 2 atlanmış React testi; 34 test dosyası başarısız. PR #81'in önceki karşılaştırması bu arayüz değişikliğinin **yeni başarısızlık eklemediğini** belirtmiştir, ancak mevcut hatalar gerçektir ve yayın engeli olmaya devam eder.

Aynı test günlüğündeki en kalabalık üç dosya:
- `PortfolioPage.test.tsx`: 87 başarısız test;
- `SettingsPage.test.tsx`: 59 başarısız test;
- `HomePage.test.tsx`: 57 başarısız test.

Bu üç dosya **203 test** ile 359 hatanın önemli kısmını barındırıyor. Bu dağılım tek başına kök neden kanıtı değildir. Günlüklerde çok sayıda eski Çince metin sorgusu, birkaç kod/tema/yönetim kontratı hatası ve yanlış Vitest tarafından çalıştırılmış Node PWA test dosyası görülmüştür. Kapsamlı çözümde kalan tüm sınıflar ayrıca ele alınmalıdır.

## Bu taslaktaki müdahale

- Üretim modu **her zaman Türkçe**; kullanıcı dil seçeneği / `tr` zorlaması PR #81 ile aynen korunur.
- Test uyumluluk modu (`import.meta.env.MODE === 'test'` ve `VITE_EBBOT_TURKISH_TEST_MODE` etkin değilken) eski tarayıcı `zh` ve `en` tanımını korur; `tr` tarayıcı dilini eski test sözleşmesinde `zh` varsayılanına döndürür. `setupTests.ts` yalnızca Vitest ortamında varsayılan tarayıcı dilini `zh-CN` olarak simüle eder. Bu dosya üretim paketine girmez.
- Portföy hesap oluşturma, işlem ve nakit formu, kurumsal işlemler, CSV aktarımı, olay kayıtları ve silme onaylarının kullanıcıya görünen sabit Çince metinleri üretim modunda Türkçeye çevrildi; eski test uyumluluk yolunda önceki Çince etiketler kaldı.
- Veri alanı, iş kodları, para birimi, piyasa verileri, TCMB dönüşüm servisi, veritabanı, risk, yatırım stratejisi, ağ güvenliği ve emir işleme mantığı değiştirilmedi.
- Türkçe üretim portföy formları test edildi; envanterdeki diğer ekranların tüm yabancı metinleri henüz temizlenmiş sayılmaz.

## İki ayrı test profili

1. Gerçek ürün sözleşmesi: `VITE_EBBOT_TURKISH_TEST_MODE=true` ile özel Türkçe UI ve portföy form testi.
2. Eski test uyumluluğu: bu değişken kapalıyken tüm eski React/Vitest beklentileri. Eski testlerin başarılı olması, Türkçe ürün davranışını kanıtlamaz. Ürün testlerinin başarılı olması da tüm eski testlerin temizlendiği anlamına gelmez.

Geniş React çalışmasının yeni başarısızlık sayısı, önceki baz ölçümle karşılaştırılmalı; **sayı bilinmeden iyileşme iddiasında bulunulmamalıdır.** Eski testler kalırsa, yayın engeli ve gerçek cihaz kontrolü devam eder. `npm run test:pwa` Node test çalıştırıcısı ile ayrıca yürütülür.

## Rollback

Taslak PR'ı kapatın veya yalnızca bu PR commit'lerini geri alın. `main` ve sunucudaki veriler değişmemiştir. PR sıralaması: #81 → #84 → #85 → bu çalışma; önceki PR'lar ayrıca kabul edilmeden otomatik merge yapılmamalıdır.
