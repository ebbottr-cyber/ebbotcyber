# ETRE Türkçe arayüz ve Hong Kong Latin yazımı

## Amaç ve sınırlar

Bu değişiklik yalnızca ETRE uygulamasının **kullanıcıya görünen arayüz metinlerini** Türkçeleştirir. Piyasa kapsamı, hisse kodları, şirket kayıtları, değerleme kuralları, fiyat verileri, API alan adları, işlem yetkileri ve analiz hesaplamaları olduğu gibi kalır. Kod içindeki değişken adları, Çince veri ayrıştırma anahtarları ve diğer dil seçenekleri çevrilmez; bunlar veri uyumluluğunun parçasıdır.

## Kullanıcı arayüzündeki değişiklikler

- Türkçe ayarlarda 174 yapılandırma alanı için yerelleştirilmiş başlıklar, 14 seçenek grubu için Türkçe gösterim metinleri bulunur. Kaydedilen değerler aynı kalır.
- Mevcut 125 ayar-yardım anahtarına Türkçe **kısa açıklama** sağlanır. Bunlar ayrıntılı İngilizce/Çince kılavuzun birebir tam çevirisi değildir.
- Ayarların hata durumları, model kanalı bağlantı testi ve model keşfi mesajları, hisse arama yer tutucuları, uyarı merkezi, sohbet, tarama ekranı ve bulunamayan sayfa metinleri Türkçe gösterilir.
- Farklı dillere ait mevcut çeviri kaynağı, teknik hata kodları ve veri kaynaklarının orijinal işaretleri korunur.

## Hisse adları

- Hisse sembolü hiçbir zaman değiştirilmez: örneğin `AAPL`, `THYAO.IS`, `SAP.DE`, `HK00700` veya `0700.HK`.
- Şirket isimleri Türkçe kelime çevirisine uğramaz. Bilinen markalar aynı adla gösterilir.
- Hong Kong hissesinin kaynakta Latin harfli şirket adı varsa arayüzde öncelikle bu ad gösterilir. Kaynakta yalnızca Çince ad varsa mevcut, kodla ilişkili güvenilir Latin ad veya varsa pinyin adı gösterilir. Güvenilir Latin ad bulunamazsa **hisse kodu** gösterilir; uydurma çeviri yapılmaz.
- Bu dönüşüm yalnızca `getStockDisplayName` üzerinden **gösterim katmanında** uygulanır. Hisse ve portföy kayıtları, arama anahtarları, API istekleri ve veritabanı değerleri değiştirilmez.

## Doğrulama

Arayüz ve yardımcı işlev değişiklikleri ilgili Vitest testleriyle; derleme ve lint işlemleri ön uç CI işiyle doğrulanmalıdır. Yeni değişiklikler birleştirilmeden önce Türkçe ayarlarda, Hong Kong hisse aramasında, uyarılarda, sohbet ekranında ve tarama ekranında görsel kontrol yapılmalıdır.

### Kapsam dışı

Bu çalışma tüm geliştirici kaynak kodunu Türkçeye çevirmeyi amaçlamaz. Teknik değişkenler, sağlayıcı hata anahtarları, resmî şirket adları ve yabancı dilde yazılmış tarihî belgeler değiştirilmez. Türkçe açıklaması bulunmayan yeni alanlar daha sonra kendi yerelleştirme girdileriyle tamamlanmalıdır.
