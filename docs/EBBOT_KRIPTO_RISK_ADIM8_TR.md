# EBBot Kripto — Aşama 8: Bağımsız Risk Motoru

Bu aşama yalnızca EBBot kripto modülünü değiştirir. Hisse piyasa
modülleri, Haberler, Solana hype ve CoinGecko Top100 uygulama mantığı
değiştirilmez. Proje adı **EBBot**.

## Kaynak karşılaştırması

Yüklenen \`ai-multi-market-trading-office-main.zip\` içindeki:

- \`backend/app/risk/engine.py\` / \`models.py\` — kural bazlı
  pozisyon büyüklüğü, stop yönü, risk limiti ve **paper review only**.
- \`backend/app/paper/portfolio_guard.py\` — toplam pozisyon
  maruziyeti, aynı yön yoğunluğu ve gerçekleşmiş/günlük zarar ile
  kademeli risk azaltma: normal 1, yükselmiş 0.75, kritik 0.5,
  bloke 0.
- \`backend/app/paper/futures.py\` — 5x kaldıraç, 200 USDT günlük
  zarar, tek sembolde %50, toplam %100, aynı yönde %70, yaklaşık
  likidasyon tamponu. Bu hesap **Binance'in gerçek likidasyon
  algoritması değildir**.
- \`backend/app/paper/ledger.py\` — kalıcı Spot sanal muhasebe;
  \`GET /paper/account\` günlük zarar için salt okunur kullanılır.
- \`backend/app/api/routes.py\` — mevcut \`/integration/dashboard\`,
  \`/paper/account\`, \`/risk/check\` ve risk raporu yolları.

Kaynakta \`/paper/portfolio-risk\` bir **gözlem raporudur** ve mevcut
giriş yollarını tek başına bloke etmez. EBBot bu yüzden ayrı, konservatif
bir risk motoru uygular; hiçbir eski raporu otomatik işlem yetkisi
olarak kabul etmez.

## EBBot'un yeni parçaları

Backend:

- \`src/services/crypto_risk_engine.py\`: bağımsız, deterministik,
  katı doğrulama ve pozisyon/bütçe/risk-getiri senaryosu.
- \`src/services/crypto_risk_gateway.py\`: doğrulanmış Trading Office
  Paper portföyünü ve Spot ledger'ını, Binance Spot/Futures fiyatı,
  emir defteri ve Futures funding verisini salt-okunur alır.
- \`src/services/crypto_risk_audit.py\`: risk incelemelerini
  ayrı kripto SQLite veritabanında kaydeder.
- \`api/v1/endpoints/crypto_risk.py\`: yönetici oturumlu risk API.

Frontend:

- \`apps/dsa-web/src/api/cryptoRisk.ts\`: tür ve yürütme güvenliği
  kontrolleri olan API istemcisi.
- \`apps/dsa-web/src/components/crypto/CryptoRiskPanel.tsx\`:
  mevcut açık renkli Kripto Trading → Risk Yönetimi görünümü.

Yeni, kimlik doğrulamalı uç noktalar:

| Yöntem | Yol | Etki |
|---|---|---|
| GET | /api/v1/crypto-office/risk/limits | Sabit risk sınırlarını okur |
| POST | /api/v1/crypto-office/risk/review | **Yalnız manuel** risk senaryosu |
| GET | /api/v1/crypto-office/risk/history | Kalıcı risk değerlendirme geçmişi |

**Her koşulda:** \`risk_approved=false\`,
\`paper_execution_permitted=false\`, \`real_exchange_orders=false\`,
\`execution=disabled\`. \`REVIEW_ONLY\` sadece bir hesaplama sonucu,
bir yetkilendirme işareti veya taşınabilir onay jetonu **değildir**.

## Güvenlik kuralları

- Kullanıcıdan hesap bakiyesi, günlük zarar, pozisyon listesi veya
  kaynak funding değeri alınmaz; bunlar backend'den doğrulanır.
- Eksik Spot ledger / güncel fiyat / emir defteri / risk durumu
  **sıfır kabul edilmez**; değerlendirme reddedilir.
- Sunucu Spot ledger'ını Trading Office'un sabit
  \`GET /api/v1/paper/account\` yolundan alır. Hesap nakdi ile
  ana dashboard'daki Spot nakdi uyuşmalıdır. Emir listesi ve sayısı,
  kayıt zamanı, ücret ve işlem türü doğrulanır.
- Spot günlük zarar tahmini, gün içi SELL gerçekleşmiş sonucu
  ile BUY ücretini toplar. BUY ücretinin daha sonra SELL maliyet
  bazında zaten yer alması durumunda **aynı ücret muhafazakâr
  biçimde iki kez sayılabilir**. Bu bir kesin finansal PnL raporu
  değil, yalnızca günlük risk **üstten korumalı kontrol** hesabıdır.
- Spot/Futures sanal hesapları birbirine karıştırılmaz; birleştirilmiş
  toplam özsermayenin iki hesabın özsermaye toplamına eşit olması
  zorunludur. USDT dışında para birimi dönüştürme yapılmaz.
- Mevcut Spot pozisyonu için %100 pazar değeri, Futures izole
  marjin pozisyonu için geriye kalan teminat bütçesi mevcut risk
  yerine kullanılan **muhafazakâr üst sınır proxy'sidir**.
  Kaynak Futures pozisyon defteri bağımsız stop emri saklamadığı için
  risk düşük gösterilmez.
- Bilinen Spread, emir defteri, kaynak güncelliği ve piyasa fiyatı
  karşılaştırılır (giriş referansı ≲ %0,5 fiyat farkı).
- Stop yanlış taraftaysa veya %10'dan uzaksa reddedilir.
- Risk başına bütçe en fazla %2.0; varsayılan %0.5; toplam
  mevcut+açılacak stop/pozisyon muhafazakâr risk üst sınırı %2.0.
- Futures kaldıraç 1–5x; Spot 1x ve yalnız yeni BUY araştırma
  önerisi. Spot SELL mevcut pozisyon çıkışıdır; bu aşamada
  ayrı bir yürütme yolu bulunmaz.
- Futures özsermaye: tek sembol %50, gross %100,
  aynı yön %70; Spot araştırma yoğunluğu %20.
- Günlük zarar üst sınırı min(200 USDT, Futures orijinal güncel
  limiti, hesabın %2'si); Spot için min(200 USDT, hesabın %2'si).
- Trading Office \`daily_guard\` üzerindeki 0.75/0.5 risk
  azaltma çarpanı bağlayıcıdır; kullanıcı/AI yükseltemez.
- Maliyet rezervi: her iki yönde %0,1 komisyon + %0,05 slippage
  varsayımı; Futures için **bir funding periyodunda mutlak oran**
  muhafazakâr gider rezervi. Bu değerler canlı Binance
  hesap ücretleri veya garantili gelecekteki funding değildir.
- Maliyet sonrası net risk/getiri en az 1,5:1 gerekir.
- Futures izole marjin likidasyon **yaklaşımı** yalnız stopa
  yakınlık uyarısı verir; gerçek Binance bakım marjı
  kademelerini içerdiği iddia edilmez.
- Bir işlem büyüklüğü, mevcut emir defteri tarafının azami %10
  görünen derinliğiyle sınırlandırılır; gerçek likidite/fill
  garantisi değildir.
- Eski, bozuk veya doğrulanmamış sonuçlar UI'da işlem
  onayıymış gibi gösterilmez; her manuel değerlendirme için
  kayıt zorunludur.

## Sonraki aşamada zorunlu entegrasyon

**Önemli:** Bu aşama henüz mevcut Trading Office'un kendi
\`POST /paper/orders\` veya Futures Paper emir API'sinin
sunucu içi işlem akışına doğrudan bağlanmadı.

EBBot bu iki API'yi **hiçbir şekilde dışarı açmıyor**.
Ancak Trading Office'un kendisine başka bir istemci erişirse
kaynak taraftaki işlemler bu yeni EBBot preflight'ını kullanmaz.
Dolayısıyla sistemi *küresel ölçekte bağlayıcı emir kapısı*
olarak adlandırmak henüz doğru olmaz.

Aşama 9'da her Paper emir işleminin **aynı sunucu transaction'ında**,
yeniden okunan güncel bakiye ve bağımsız risk kontrolleriyle
onaylanması sağlanacak. Şu andaki \`REVIEW_ONLY\` yanıtı bu
kontrol yerine geçmeyecek.

## Testler

\`tests/test_crypto_risk_engine.py\` ve
\`tests/test_crypto_risk_gateway.py\`:

- Veri eksikliği, imkânsız fiyat, günlük zarar limiti,
  stop/hedef yönü, düşük risk/getiri, kötü spread/derinlik.
- Mevcut risk, kaldıraç, Spot/Futures ayrımı, kademeli
  portföy risk çarpanı, bütünlük/uzlaşma kontrolü.
- Denetim veritabanının kapalı emir ve hatalı disk yazımı.

\`apps/dsa-web/src/api/cryptoRisk.test.ts\` ve
\`apps/dsa-web/src/components/crypto/CryptoRiskPanel.test.tsx\`:

- Güvenlik bayraklarının zorunluluğu, eski veri reddi,
  manuel buton, Spot/Futures ayrımı ve geçmiş.

Otomatik iş akışı: \`.github/workflows/crypto-risk-tests.yml\`
(\`EBBot Crypto Risk Offline Checks\`). Python offline testleri,
Vitest ve tüm React/TypeScript derlemesini kontrol eder.

Windows PowerShell:

\`\`\`powershell
cd C:\Users\Thebo\Projects\ebbotcyber-test
git switch feat/turkish-ui-hk-latin-display
git pull --ff-only origin feat/turkish-ui-hk-latin-display
python -m unittest discover -s tests -p "test_crypto_risk_*.py" -v
cd apps\dsa-web
npm.cmd run test -- src/api/cryptoRisk.test.ts src/components/crypto/CryptoRiskPanel.test.tsx
npm.cmd run build
\`\`\`

Bu belge kod davranışını tanımlar; canlı Binance/Paper bağlantısı ve
CI geçişi ayrıca doğrulanmadan **üretime hazır** denmemelidir.
