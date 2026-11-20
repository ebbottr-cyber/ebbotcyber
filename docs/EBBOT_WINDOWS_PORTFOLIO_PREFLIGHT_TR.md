# EBBot — Windows Portföy Ön Kontrolü (Salt Okunur)

Bu kontrol, PR #97 üzerine hazırlanmış ayrı bir taslak geliştirme dalındaki kodlar içindir. **Kurulum, işlem, sanal emir, zamanlayıcı veya canlı yayın başlatmaz.** GitHub Actions Windows koşumu gerçek kullanıcının bilgisayarındaki masaüstü uygulamasını doğrulamaz.

## Neyi sınar?

- Kaynak hazırlığı: Python 3.10+, Node.js 20.19+ ve portföy/API/Electron kaynaklarının varlığı.
- Desktop modunda derlenmiş static/index.html dosyası ile /assets JS/CSS dosyalarının fiziksel varlığı.
- Yalnızca kullanıcının açıkça belirttiği http://127.0.0.1:8000–:8100 veya http://localhost:PORT adresinde GET /api/health ve GET /.
- İsteğe bağlı olarak GET /api/v1/portfolio/fx/display-rates: altı bağımsız döviz çiftinin durumunu, fiyat geçerliliğini ve 30 dakikalık kaynak zamanını kontrol eder. Bu uç nokta Yahoo Finance ile iletişime geçebilir. Kapalı piyasada kur çıkmaması normaldir ama doğrulanmış sonuç **sayılmaz**.
- PASSED_READ_ONLY, NOT_VERIFIED veya BLOCKED sonucunu verir. **Hiçbiri gerçek/sanal otomatik alım-satım izni değildir.**

Kontrol aracı **asla** .env, API anahtarı, cüzdan, SQLite işlem geçmişi veya logs/desktop.log dosyasını okumaz. POST/DELETE atmaz; dış IP'lere ve rastgele portlara bağlanmaz, HTTP yönlendirmelerini ve ortam vekil sunucularını kullanmaz. JSON çıktısında gizli yapılandırma bulunmaz.

## 1. Windows PowerShell — kurulum yapmadan kaynak kontrolü

Kodların bu PR dalında veya birleşik yerel çalışma ağacında olması gerekir. Kaynağın üst klasöründe:

    python .\scripts\ebbot_windows_portfolio_preflight.py --mode source

PASSED_READ_ONLY, yalnızca **kaynak ve çalışma zamanı önkoşulları**nın geçtiği anlamına gelir.

## 2. Derlenmiş arayüz ve çalışan masaüstünü kontrol etme (isteğe bağlı)

Kullanıcı masaüstü uygulamasını **kendi kararıyla** başlattıktan sonra, uygulamanın konsolunda seçtiği 127.0.0.1 portunu kullanın. Electron arka uç için 8000–8100 arasında boş bir port seçer; 8000'in her zaman doğru olduğunu varsaymayın.

Arayüz daha önce derlenmediyse, bunu ayrı ve açık kullanıcı adımı olarak yapabilirsiniz:

    cd apps\dsa-web
    npm ci
    npm run build
    cd ..\..

İlk komut ağdan bağımlılık indirebilir, ikincisi static/ çıktısını üretir. **Ön kontrol komutu bunları kendisi çalıştırmaz.**

Örnek, gerçek seçilen portun 8007 olduğunu **varsayarak**:

    python .\scripts\ebbot_windows_portfolio_preflight.py --mode desktop --origin http://127.0.0.1:8007 --check-display-fx

Yalnızca HTTP/arayüz erişimi kontrol edilecekse --check-display-fx olmadan çalıştırın. Makine internete çıkmıyorsa veya Yahoo veri sağlayıcısı kapalıysa, FX kontrolü NOT_VERIFIED verebilir; bu, fiyatı **güncel sanmak için bir gerekçe değildir**.

Komutun makineye okunur özel bilgi almadan çıktısı gerekiyorsa:

    python .\scripts\ebbot_windows_portfolio_preflight.py --mode desktop --origin http://127.0.0.1:8007 --json

--json, sağlık ve kaynak kontrollerini özetler; özel hesap değerlerini veya gizli anahtarları içermez. Konsol çıktısını paylaşmadan önce yine gözden geçirin.

## Hata yorumlama

| Sonuç | Anlamı / sonraki adım |
| --- | --- |
| BLOCKED / source_files | Doğru EBBot dalı kontrol edilmelidir |
| BLOCKED / node | Node.js 20.19+ kurulumu kullanıcı tarafından yapılmalıdır |
| BLOCKED / built_frontend | Arayüz derlenmemiş veya JS/CSS eksik; npm run build manuel gerekir |
| BLOCKED / backend_health | Masaüstü backend'i çalışmıyor, farklı portta veya geçersiz cevap veriyor |
| BLOCKED / frontend_http | Sağlıklı API olsa bile React UI henüz servis edilmiyor |
| NOT_VERIFIED / display_fx | En az bir kur eksik/eski; TL gösterimini kesin değer saymayın |
| PASSED_READ_ONLY | Yalnızca sınanan yerel koşullar olumlu; gerçek emir/dağıtım açılmaz |

## Test ve yayın sınırları

Windows GitHub Actions koşumu kaynak denetimini ve yerel uç nokta taklitlerini test eder; gerçek Windows kullanıcı cihazındaki kurulu Electron, güvenlik duvarı, dosya izinleri, çalışma veritabanı, kur lisansı veya piyasa emri entegrasyonunu doğrulamaz. PR hâlâ **taslak** tutulmalıdır. Gerçek cihaz doğrulaması yapıldıktan sonra bile **ayrı inceleme ve kullanıcının açık izni olmadan** merge/deploy, zamanlayıcı, gerçek emir ve otomatik sanal emir etkinleştirilmez.
