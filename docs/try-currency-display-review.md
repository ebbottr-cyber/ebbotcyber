# EBBot: Türkçe para görünümü için kur doğrulama sözleşmesi

## Kapsam

Bu PR yalnızca operatör arayüzündeki Türkçe metinleri düzeltir ve **kullanıma henüz bağlanmamış** `formatTryDisplay` yardımcı işlevini tanımlar. Portföy, emir, muhasebe, performans, PnL, piyasa verisi, API sözleşmesi ve strateji hesaplamaları mevcut özgün para birimleriyle çalışmaya devam eder. Kur indirme/servis sunma veya görünür TL dönüşümü henüz devreye alınmamıştır.

## Kur kaynağı ve tarih

Önerilen güvenilir veri kaynağı TCMB günlük **gösterge niteliğindeki** döviz kurlarıdır: https://www.tcmb.gov.tr/kurlar/today.xml

Bu kurlar canlı veya anlık işlem kotasyonu değildir. TCMB iş günlerinde gösterge kurlarını 15:30 civarında yayımlar; hafta sonu ve resmi tatillerde yeni günlük bülten olmayabilir. Görünür dönüşümlerde `TCMB · bülten tarihi YYYY-MM-DD · gösterge kuru` bilgisi birlikte verilmelidir. Arşivden veya günlük bültenden gelen gerçek yayın tarihini kullanın, sistemin fetch zamanını veya bilgisayar saatini bülten tarihi olarak atamayın.

## Güvenli kullanım sözleşmesi

- Döviz kuru yalnızca güvenilir backend servisi tarafından TCMB XML'den alınmalı, her bir `CurrencyCode` ve `Unit` alanı doğru ayrıştırılmalıdır. Bu frontend yardımcı işlevi URL çağrısı yapmaz.
- Sadece `USD`, `EUR` ve `CNY` → `TRY` için izin vardır. Her kayıtta `source: 'TCMB'`, `targetCurrency: 'TRY'`, `sourceUnit: 1`, `asOfDate` (gerçek bülten tarihi) ve sonlu, pozitif `tryPerUnit` olmalıdır.
- Kur tarihi İstanbul tarihinden ileride olamaz; dört takvim gününden daha eskiyse dönüşüm yapılamaz. Uzun tatillerde bu, orijinal para birimini gösteren güvenli bir düşüşe yol açabilir.
- Eşleşmeyen, eksik, tarih biçimi bozuk, güncel olmayan, sıfır/negatif veya sonlu olmayan kurlarda özgün tutar ve döviz kodu korunur. **Uydurma TL hesabı veya sessiz CNY→TRY etiket değişimi yasaktır.**
- `TRY` cinsinden özgün tutar doğrudan görünür; herhangi bir döviz kuru gerekli değildir.
- Fiyat, emir, risk, bakiye, FX exposure ve muhasebe veri katmanında bu dönüştürülmüş çıktı kullanılmaz. Sadece ekrandaki bilgilendirici gösterim alanlarında kullanılabilir.
- Kur hizmeti hazırlanıp gerçek kaynak-tarih/birim testi ile doğrulanana kadar `formatTryDisplay` hiçbir sayfaya bağlanmamalıdır.

## Doğrulama ve yayımlama engelleri

`apps/dsa-web/src/utils/__tests__/tryDisplayFx.test.ts` yok/eskimiş/gelecek tarihli ve eşleşmeyen kur senaryolarını kontrol eder. Geniş React testlerindeki eski başarısızlıklar bu PR ile giderilmiş sayılmaz; tam test ve gerçek cihaz denetimi ayrı gerekir. Canlı piyasada emir, otomatik görev, deploy veya `main` birleştirmesi bu çalışmanın parçası değildir.
