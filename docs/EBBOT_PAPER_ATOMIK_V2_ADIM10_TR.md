# EBBot — Aşama 10: Trading Office Paper V2 atomik güvenlik yaması

Bu dosya **açık EBBot GitHub deposunda** yalnız entegrasyon durumunu
belgeler. Kullanıcının yüklediği **özel Trading Office kaynak kodu
ve kaynak kodu diff'i buraya kopyalanmaz**. Yama, kullanıcıya ayrı
\`EBBot_TradingOffice_PaperV2_SafePatch.zip\` dosyası olarak teslim
edilir. GitHub'daki bu belgede ZIP'in kendisi bulunmaz.

## Kaynak

Yama doğrudan kullanıcının yüklediği
\`ai-multi-market-trading-office-main.zip\` içindeki gerçek
\`backend/app/paper/ledger.py\`,
\`backend/app/paper/futures.py\`,
\`backend/app/paper/automation.py\`,
\`backend/app/api/routes.py\` ve
\`backend/app/main.py\` kaynakları üzerinde hazırlanmıştır.

## Önerilen V2 yapısı

- Eski \`/api/v1/paper/*\` **HTTP yazma** yolları varsayılan olarak
  kapalıdır; araştırma ve görüntüleme GET yolları korunur.
- Kaynakta \`GET /api/v1/paper/v2/capabilities\` ile salt-okunur
  durum bildirimi bulunur.
- Kaynakta \`POST /api/v1/paper/v2/execute\` protokolü vardır;
  **PAPER_V2_EXECUTION_ENABLED=false** varsayılandır.
- Kaynak ancak \`TRADING_ENABLED=false\`, güçlü ayrı admin/read
  anahtarları ve \`API_AUTH_ENABLED=true\` varken denemeye açılabilir.
  Bu koşulların sağlanması tek başına dağıtım izni değildir.
- Kaynak, öneri fiyatı veya bakiye yerine Binance kamuya açık
  doğrulanmış market verisi ile mevcut Spot/Futures SQLite defterlerini
  kullanır. Yeni bir EBBot cüzdanı oluşturmaz.
- \`BEGIN IMMEDIATE\` transaction'ı içinde güncel portföy yeniden
  okunur, deterministik risk kapısı çalışır ve ancak güvenli
  senaryoda mevcut Paper defterine kayıt yazılır.
- Tekil \`client_request_id\` sayesinde tekrar gönderim ikinci
  Paper emri açmaz. İşlem ve kayıt hatası rollback olur.
- Funding uygulayan eski yazma endpoint'leri kapatılır. Yeni
  funding tahakkuk ettirme yolu bu protokolün bu sürümünde açılmaz.
- Bu yapı **asla gerçek Binance emirleri, para yatırma/çekme,
  canlı bakiye veya transfer** API'lerini kullanmaz.

## EBBot uyumluluk durumu

Açık EBBot deposuna eklenen \`GET /api/v1/crypto-office/paper/capabilities\`
çağrısı ayrı Trading Office sunucusunun V2 protokol beyanını kontrol eder.
Bu bilgi **kaynağın kendi iddiasıdır**, bağımsız güvenlik attestation'ı
değildir. Kaynak V2 opt-in açık olduğunu bildirse bile:

- \`readiness_verified=false\`
- \`ebbot_paper_execution_permitted=false\`
- \`real_exchange_orders=false\`

olur. EBBot üzerinden Paper açma/kapatma POST yolu **eklenmedi**.
Yama kurulmamışsa kaynak kontrolü 503 dönebilir; bu durumda
özellik kapalı kalır. Gerekli yönetici oturumu, eski yazma yollarının
engellenmesi ve sunucuların ayrı yetki sınırları korunur.

## Denenmiş doğrulamalar

Kullanıcının yüklediği orijinal ZIP ayrı bir geçici Git deposuna
açıldı. \`git apply --check\` ve \`git apply\` başarıyla tamamlandı.

- Yeni \`tests/test_guarded_paper_v2.py\`: **11/11 geçti** (ek test: okuma anahtarının Paper yazma isteği için reddedilmesi).
- Eski \`test_paper_ledger.py\` ve \`test_portfolio_guard.py\`:
  toplam **24/24 geçti**.
- Daha geniş Futures testleriyle birlikte yamalı örnekte
  **99 geçti, 6 başarısız**.
- Aynı Futures/Paper/portföy testleri, **hiç değiştirilmemiş
  kaynakta 88 geçti, aynı 6 başarısız**. Mevcut başarısızlıklar:
  kaynak Futures işleminde diğer açık pozisyonlar için
  taze mark zorunluluğunu eski testlerin sağlamaması (2 test)
  ve test zamanının açılış/kapanış arasında ileri gitmemesi (4 test).
  Bu sonuçlar mevcut kaynak kaynaklı test uyumsuzluğudur;
  çözülmeden tüm geçmiş regresyon testleri yeşildir denemez.

Bunların dışında **canlı olmayan gerçek HTTP auth denetimi**,
rate-limit, farklı zamanlarda fiyat değişimi, staging dağıtımı,
idempotency arıza/yeniden başlatma testi, kaynak Futures kanonik
sembol göçü ve gerçek Binance public feed erişimi ayrıca
doğrulanmalıdır. HTTP uçtan uca testleri tamamlanmadan V2 açılmamalıdır.

## Elle güvenli uygulama

Kullanıcı ayrı olarak verilen ZIP'i yerel Trading Office Git
deposuna, ZIP içindeki PowerShell yardımcı betiğiyle uygular.
Kaynak ve patch sürümü uyuşmazsa betik devam etmez.

1. Trading Office kaynak Git çalışma ağacında commitlenmemiş
   değişiklik bulunmadığını doğrulayın ve yedek alın.
2. Betikte \`-RepoPath\` için gerçek Trading Office kaynak
   yolunu kullanın.
3. \`git apply --check\` başarılı olmadan yamayı uygulamayın.
4. \`backend\` dizininde
   \`python -m pytest -q tests/test_guarded_paper_v2.py\` çalıştırın.
5. Kaynağın diğer eski Futures testlerini düzeltin ve bağımsız
   staging/HTTP güvenlik testlerini tamamlayın.
6. \`TRADING_ENABLED=false\` ve
   \`PAPER_V2_EXECUTION_ENABLED=false\` değerlerini koruyun.
7. EBBot'ta işlem tuşlarını ancak kaynak tarafta yetkili dağıtım
   ve ayrı risk doğrulaması tamamlandıktan sonra ele alın.

**Durum: kaynak yama paketi hazır, kaynak GitHub deposuna
kurulmadı, EBBot işlem iletimi açılmadı.**
