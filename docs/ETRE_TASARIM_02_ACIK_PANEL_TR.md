# ETRE — Seçilen 2. Arayüz: Açık Renkli Modern Finans Paneli

## Tasarım kararı

Kullanıcı ETRE için 2. örneği seçti: beyaz/açık gri zemin, mavi vurgu,
geniş okunabilir navigasyon, canlı veri kartları, mum grafiği, hisse ve
kripto takip listeleri, son haberler ve teknik/AI açıklamaları.
Koyu tema seçeneği kaldırılmadı. Yeni kurulumlarda varsayılan açık.
Önceden kaydedilmiş koyu tema tercihi kullanıcının tercihi olarak korunur.

## Sayfa yolları

- `/` — yeni ETRE ana paneli (DashboardPage)
- `/analysis` — eski kapsamlı Daily hisse analizi (HomePage), değiştirilmedi.
- `/news` — Türkçe RSS haber kutusu, bildirimler, tekli/toplu okundu.
- `/data` — Türkiye/ABD/Almanya/Hong Kong veri durumu ve CoinGecko Top100.
- `/portfolio`, `/screening`, `/decision-signals` — önceki işlevler ve API'ler.

## Veri doğruluğu

ANA PANELDE ŞABLON FİYATI / SAHTE AI PUANI YOKTUR.
Türkiye/ABD/Almanya/Hong Kong kartları BIST100, S&P500, DAX ve
Hang Seng endeks fiyatı gibi sunulmaz. Bunlar sırasıyla THYAO.IS, AAPL,
SAP.DE ve 0700.HK **gösterge hisse** fiyatlarıdır. Her kart bu
ayrımı yazar. Fiyatlar mevcut `/api/v1/stocks/{code}/quote` üzerinden
alınır; veri yoksa `—` veya `Fiyat bekleniyor` gösterilir.

Merkezdeki grafik `/api/v1/stocks/{code}/history` yolundan gerçek
günlük OHLC veriyle oluşturulur, 30/90/180 günlük aralık seçilebilir.
MA5/MA10/MA20 çizgileri gerçek kapanışlardan hesaplanır.
Teknik 'eğilim' sadece MA sıralamasına dayalı basit gösterimdir;
gerçek Daily 100 puanlık skoruyla karıştırılmaz. AI paneli
geçerli rapor uydurmaz; eski analiz motoruna bağlantı verir.

Kripto kartı ve listesi mevcut CoinGecko Top100 servisinden gelir.
Yan haber akışı mevcut ücretsiz RSS haber servisinden okunur;
Türkçe AI çevirisi üretilmediyse tamamlanmış gibi sunulmaz.
Son dakika/önemli işaretleri haber servisi verisinden alınır.

## Erişilebilirlik

Responsive: masaüstünde 238px sol sidebar, tablette 2–3 kartlı
piyasa satırı, mobilde üst gezinme ve hisse kodu arama alanı.
Hem açık hem koyu mod, kontrast ve klavye ile link gezinmesi korunur.

## Yerel doğrulama (Windows PowerShell)

    cd C:\Users\Thebo\Projects\ebbotcyber-test
    git status --short
    git switch feat/turkish-ui-hk-latin-display
    git fetch origin refs/heads/feat/turkish-ui-hk-latin-display:refs/remotes/origin/feat/turkish-ui-hk-latin-display
    git merge --ff-only origin/feat/turkish-ui-hk-latin-display
    cd apps\dsa-web
    npm.cmd run test -- src/pages/DashboardPage.test.tsx
    npm.cmd run build
    npm.cmd run dev

Yeni görünüm: http://localhost:5173/
Eski hisse analizi: http://localhost:5173/analysis
Haberler: http://localhost:5173/news

Bu dosya ve testler kod incelemesi için eklendi; CI veya yerel tarayıcı
ile uçtan uca doğrulama bu geliştirici oturumunda çalıştırılamadı.
Git işlemi hızlı-ileri birleştirmeye izin vermezse yerel değişiklikleri
silmeyin ve `git reset --hard` uygulamayın.
