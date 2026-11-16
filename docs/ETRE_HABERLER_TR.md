# ETRE Haberler — beş piyasa + kripto

## Özellikler

Yeni `/news` sayfası ve yan menüde okunmamış haber rozeti. Piyasa kategorileri:
Türkiye (BIST/TCMB), ABD (NASDAQ/Fed), Almanya (DAX/Xetra/ECB),
Hong Kong (Hang Seng/HKEX), Kripto (Bitcoin/Ethereum vb.).

Kaynak: Google Haberler'in herkese açık ve ücretsiz RSS arama akışı.
Ücretsiz kaynak API anahtarı yoktur; RSS akışı haberlerin tamamını veya
her son dakika olayını garanti etmez. Feed başlığı, yayıncı ve bağlantı
metadata'sı alınır. Telifli makalelerin tam metni indirilmez,
kopyalanmaz veya eksiksiz tercüme edilmiş gibi sunulmaz.

Sunucu açıkken yaklaşık beş dakikada bir haber kontrolü yapılır.
`NEWS_POLL_ENABLED=false` ile durdurulabilir. İnternet veya kaynak
sorunları diğer piyasa feeds'ini durdurmaz. Haberler
`data/cache/etre_news.sqlite` dosyasında kalıcı ve tekrarsız tutulur.
İlk çalıştırmada mevcut eski haberler okunmuş olarak eklenir
(ilk bağlantıda toplu bildirim yağmuru olmaz); sonraki yeniler okunmamıştır.

`POST /api/v1/news/{id}/read`: tek haber okundu.
`POST /api/v1/news/read-all`: mevcut tüm haberler okundu;
yeni gelenler yine okunmamış olur. `PUT /api/v1/news/notifications`
future bildirimlerini açar/kapatır; okundu durumu silinmez.
`GET /api/v1/news/status` okunmamış sayısını verir.
`GET /api/v1/news/items` filtreli kayıtları verir.
`POST /api/v1/news/refresh` elle RSS kontrol eder.

Tarayıcı masaüstü bildirimleri **ETRE açıkken**, tarayıcı izin verdiyse
ve haber bildirimleri açıksa görünür; kullanıcı bildirimden haber
sekmesine geçebilir. Sayfa kapalıyken veya telefon kilitliyken OS push,
SMS/Telegram/e-posta bildirimi bu sürümde uygulanmadı. Yan menü
okunmamış rozeti, uygulama açıkken bir dakikada bir yenilenir.

## Yapay zekâ ve Türkçe

Ücretsiz RSS haber başlıkları Türkçe olmak zorunda değildir. Mevcut
ETRE GeminiAnalyzer/generation backend ile kaynak başlığı
Türkçeye tercüme edilir; yalnız başlığa dayalı kısa Türkçe açıklama
ve ihtiyatlı piyasa etkisi değerlendirmesi üretilir. Başlık,
işlem yaptıran bir talimat olarak yorumlanmaz. Önem seviyesi (genel,
önemli, son dakika) başlıktan ve AI sınıflandırmasından gelir;
önem seviyesi bir finansal sonuç veya kesinlik garantisi değildir.

Bu AI çalışma yolu varsayılan olarak **kapalıdır**, çünkü model
API çağrıları ücretli olabilir. Kullanıcının önce ETRE'de gerçek
çalışan bir AI modelini yapılandırması, sonra FastAPI başlatılan
PowerShell oturumunda `$env:NEWS_AI_ENABLED='true'` demesi gerekir.
Yapılandırma yoksa İngilizce metin çevrilmiş gibi gösterilmez,
'Türkçe çeviri bekleniyor' etiketi görünür. Her kayıt AI kuyruğuna
eklenir ve etkin worker sırayla değerlendirir; sınırlı hızda
işler (bir dakikada en fazla beş model denemesi, işlemler
uzun sürüyorsa daha az). Bu ayrı AI değerlendirmesidir:
borsadaki hisse analizini baştan başlatmaz ve emir göndermez.

## Windows başlatma

Yerel branch'i koruyarak GitHub değişikliklerini indirin:

    cd C:\Users\Thebo\Projects\ebbotcyber-test
    git switch feat/turkish-ui-hk-latin-display
    git fetch origin refs/heads/feat/turkish-ui-hk-latin-display:refs/remotes/origin/feat/turkish-ui-hk-latin-display
    git merge --ff-only origin/feat/turkish-ui-hk-latin-display

Python testleri (gerçek RSS veya ücretli LLM çağrısı yok):

    .\.venv\Scripts\python.exe -m unittest discover -s tests -p 'test_news_hub.py'

PowerShell 1 / ETRE API:

    chcp 65001
    $env:PYTHONIOENCODING='utf-8'
    $env:PYTHONUTF8='1'
    $env:NEWS_POLL_ENABLED='true'
    # AI yapılandırılıp maliyet onaylandıysa:
    # $env:NEWS_AI_ENABLED='true'
    & .\.venv\Scripts\python.exe -X utf8 main.py --serve-only --host 127.0.0.1 --port 8000

PowerShell 2 / web:

    cd C:\Users\Thebo\Projects\ebbotcyber-test\apps\dsa-web
    npm.cmd run test -- src/pages/NewsPage.test.tsx
    npm.cmd run build
    npm.cmd run dev

Tarayıcı: http://localhost:5173/news

## Kalite sınırları

RSS gecikmeleri, rate-limit, kaynak güvenilirliği ve link erişimi
bağımsız test gerektirir. Canlı RSS ve AI entegrasyonu henüz
bu geliştirme ortamında uçtan uca çalıştırılmadı.
Yalnızca tek kullanıcıya yönelik sunucu tarafı global okundu durumu
vardır; birden fazla kullanıcı için ayrı haber kutuları yoktur.
