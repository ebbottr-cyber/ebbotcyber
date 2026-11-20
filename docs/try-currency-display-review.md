# EBBot TCMB kaynaklı tahmini TL görünümü (inceleme sürümü)

## Ne değişti?

Yalnızca portföy özetindeki **toplam özkaynak, toplam piyasa değeri ve nakit** alanları, doğrulanmış güncel TCMB gösterge döviz satış kuru varsa TRY olarak sunulur. Yanında özgün USD/EUR/CNY tutarı gösterilir. Geri kalan emir, fiyat, miktar, risk, kazanç/zarar, portföy muhasebesi, strateji ve rapor hesaplamaları **özgün para birimiyle** devam eder.

- Backend: `GET /api/v1/portfolio/fx/try-display` (salt okunur), `src/services/tcmb_try_display_service.py`.
- Frontend: `apps/dsa-web/src/api/portfolio.ts` ve `PortfolioPage.tsx`; `formatTryDisplay` güvenli son kontrolü uygular.
- Kaynak: `https://www.tcmb.gov.tr/kurlar/today.xml`. Bu feed **anlık alım-satım kotasyonu değildir**, TCMB günlük gösterge döviz satış kurudur. Bülten tarihi ayrıca görünür.
- Yeni bir emir tetikleyicisi, API anahtarı, otomasyon, scheduler, döviz muhasebe yazma fonksiyonu veya env ayarı eklenmedi.

## Güvenlik ve veri doğrulama

1. Backend yalnızca sabit `https://www.tcmb.gov.tr/kurlar/today.xml` adresine istek gönderir (5 saniye zaman aşımı, yönlendirme yok, maksimum 128 KiB, 10 dakika başarılı sonuç önbelleği). URL kullanıcı girdisi olamaz.
2. XML kökü `Tarih_Date` olmalı; `Tarih` bülten tarihi ayrıştırılır ve varsa `Date` ile eşleşmelidir. DTD/ENTITY reddedilir. `CurrencyCode`, `Kod`, `Unit` ve `ForexSelling` birlikte kontrol edilir. Kaynak birimi 1'e normalize edilir.
3. Sadece USD, EUR ve CNY → TRY geçerlidir. Kur pozitif, sonlu ve maksimum dört takvim günü eski olmalıdır (İstanbul takvimine göre). Gelecek tarih, mükerrer kod, geçersiz/eksik bülten, ağ kesintisi ve sahte değerler dönüşüm üretmez.
4. Endpoint doğrulanmış bülten yoksa HTTP 503 döndürür. Frontend hatayı sessizce TRY'ye dönüştürmez.
5. Portföy `fxStale` ise, hesaplarından biri `fxStale` ise veya özetin `dataQuality` alanı `partial` ise TL dönüşümü **engellenir**. Fiyat kalitesi ve kapsamı ayrıca gerçek cihazda incelenmelidir.
6. Envanterdeki herhangi bir para birimi orijinal veride USD/EUR/CNY dışında ise bu alanın dönüştürülmesi desteklenmez. Mevcut portföyün toplulaştırılmış para birimi değiştirilmez.

## Sınırlar / kabul koşulları

- Resmi TCMB kuru gün içinde bir kez yayımlanır; intraday veya işlem yapılabilir fiyat değildir.
- Hafta sonu veya uzun tatillerde dört günü geçen tarih yüzünden orijinal para birimi korunur.
- Gerçek TCMB ağından end-to-end erişim, veri lisansı/kullanım koşulları, tarayıcı ekran görüntüleri ve cihaz üstü Türkçe kontrolleri henüz onaylanmamıştır.
- Mevcut 359 geniş React test hatası bu çalışma tarafından çözüldü sayılmamalıdır. Taslak PR birleştirilmeye ve üretime yayına hazır değildir.
- Geri alma: yeni taslak PR'ı kapatmak veya bu PR'ın commit'lerini geri almak. Veritabanı geçişi yoktur.
