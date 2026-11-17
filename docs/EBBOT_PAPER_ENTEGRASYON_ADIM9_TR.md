# EBBot — 9. Aşama: Mevcut Paper Trading Defterlerini Entegre Etme

**Durum:** Mevcut Trading Office Spot/Futures hesapları, açık pozisyonlar,
gerçekleşmiş/gerçekleşmemiş PnL, funding ve kaynak olay geçmişi EBBot'a
**salt-okunur** bağlandı. **Yeni sanal emir yürütme bu aşamada açılmadı.**
Bu sınır güvenlik ve veri doğruluğu gerekçesiyle bilinçli olarak korunur.

## İncelenen gerçek kaynak kodu

Yüklenen \`ai-multi-market-trading-office-main.zip\` içerisinde:

- \`backend/app/paper/ledger.py\`: \`snapshot\`, \`portfolio\`,
  \`place_order\` ve kalıcı \`orders / positions / account\` SQLite tabloları.
  Spot BUY/SELL muhasebesi ve simülasyon komisyonu \`0.001\`.
- \`backend/app/paper/futures.py\`: \`snapshot\`, \`open_position\`,
  \`close_position\`, \`apply_funding\`, izole marjin, kaldıraç ve
  \`futures_* \` tabloları. Futures 1-5x, funding olayları ve
  açık/kapalı pozisyon geçmişi kaynakta vardır. Tahmini likidasyon
  borsa formülü değildir.
- \`backend/app/paper/reporting.py\`: \`history\`, \`performance\`,
  üç kaynak (\`spot_ledger\`, \`futures_ledger\`, \`trade_lifecycle\`).
- \`backend/app/api/routes.py\`: aşağıdaki **GET** ve **POST**
  endpoint'leri ayrı tanımlanmıştır.

Mevcut EBBot'a eklenen yeni dosyalar:

- \`src/services/crypto_paper_bridge.py\`: sabit allowlist'li
  localhost GET, kaynak kimlik/muhasebe sözleşme doğrulaması.
- \`api/v1/endpoints/crypto_paper.py\`: yönetici oturumuyla korunan
  GET summary/history API.
- \`apps/dsa-web/src/api/cryptoPaper.ts\`: TypeScript veri sözleşmesi.
- \`apps/dsa-web/src/components/crypto/CryptoPaperPanel.tsx\`:
  **Paper Trading**, **Açık Pozisyonlar**, **İşlem Geçmişi** menüleri.

EBBot'un okuduğu Trading Office kaynak GET uç noktaları:

| Kaynak | Okuma amacı |
|---|---|
| \`/api/v1/paper/account\` | Spot bakiye, tüm simüle emirler, stoklar |
| \`/api/v1/paper/portfolio\` | Spot pozisyonları, mark, maliyet/PnL |
| \`/api/v1/paper/futures/account\` | Futures cüzdan, marjin, PnL, açık pozisyon, son 100 işlem |
| \`/api/v1/paper/performance\` | Günlük/haftalık/aylık kaynak raporu |
| \`/api/v1/paper/history?limit=100\` | Spot/Futures/funding/lifecycle olayları |

EBBot yeni GET uç noktaları:

- \`/api/v1/crypto-office/paper/summary\`
- \`/api/v1/crypto-office/paper/history?market=futures&limit=100\`

**İstemciye gerçek Binance özel API anahtarı gönderilmez.**
Trading Office bağlantısı \`TRADING_OFFICE_URL\` localhost kısıtını,
sunucuya özel \`TRADING_OFFICE_READ_API_KEY\` ve
\`TRADING_ENABLED=false\` kontrolünü kullanır.

## Güvenilirlik

- Spot ve Futures muhasebesi **asla birleştirilerek yazılmaz**.
- Spot defterindeki \`order_count\` tüm gelen kayıtlarla uyuşmalıdır.
- Spot cash ile bağımsız Spot portfolio cash ve pozisyon
  miktarları uyuşmalıdır. Uyuşmazlıkta API hata döner.
- Futures cüzdan + kullanılan izole marjin + unrealized PnL
  raporlanan equity ile uyuşmalıdır.
- Futures source \`LONG/SHORT\`, pozitif miktar/mark ve 1-5x
  kaldıraç doğrulanır; Spot source \`BUY/SELL\` olarak kalır.
- Eksik piyasa fiyatında \`valuation_complete=false\`,
  \`equity=null\`: boş/missing veri **0** yapılmaz.
- Geçmişteki \`FUNDING\` olayları gerçekleşmiş Futures kaynak
  kaydı olarak gösterilir; EBBot yeni funding ödemesi oluşturmaz.
- Kaynak \`trade_lifecycle\` raporları ile muhasebe olayları
  farklı kayıtlardır: geçmiş satırlarını toplayarak PnL
  raporu türetilmez, kaynak performansı ayrıca gösterilir.
- Aynı zamanlı kayıtlara bağlı ardışık GET'ler farklı SQLite
  anlarını görebilir. Bu yüzden bu API **işleme yetki vermez**
  ve \`checked_at\` yalnızca okumanın tamamlandığı zamandır.
- Mevcut sanal hesaplar sıfırlanmaz, taşınmaz ve ikinci bir
  EBBot Paper hesabı icat edilmez.

## Paper emirlerini güvenle açmak için blokör

Kaynak Trading Office'un mevcut **mutasyon** yolları:

- \`POST /api/v1/paper/orders\`
- \`POST /api/v1/paper/futures/positions\`
- \`POST /api/v1/paper/futures/close\`
- \`POST /api/v1/paper/futures/funding\`
- \`POST /api/v1/paper/futures/reset\`
- \`POST /api/v1/paper/reset\`
- \`POST /api/v1/paper/automation\`
- \`POST /api/v1/paper/futures/funding/apply-latest\`

Bunlar mevcut Trading Office kodunda var; EBBot'un 8. aşamadaki
bağımsız \`crypto_risk_engine.py\` motoru **bu kaynak sunucunun
SQLite işlemi içinde henüz çağrılmıyor**. EBBot kendi başına
HTTP üzerinden önce risk hesaplayıp sonra yukarıdaki POST
adreslerine çağrı yapsaydı iki servis arasında TOCTOU (kontrol
sonrası hesap değişmesi), yarış, tekrar gönderim ve risk
kontrolünü atlama riski doğardı. Böyle bir bağlantı **eklenmedi**.

Güvenli yürütme için Trading Office kaynak reposunda ayrıca
yapılması gerekenler:

1. Varsayılan olarak tüm eski yazma uç noktalarını **kapatan**
   ve yalnızca özel güvenli Paper API v2'ye izin veren
   bir sunucu değişikliği. Bu yeni yazma yetkisi hiçbir şekilde
   canlı borsaya emir vermeyecek; \`TRADING_ENABLED=false\` kalacak.
2. Spot ve Futures defterleri aynı SQLite dosyasını kullandığı
   için \`BEGIN IMMEDIATE\` altında hesap/pozisyon/açık risk/
   günlük zarar/mark/funding zaman damgası *yeniden* okunmalı.
   AI önerisi asla kontrolü atlayamamalı.
3. Bağımsız risk motoru aynı transaction içinde zorunlu
   çağrılmalı; izin verilmeyen Spot açma, Futures Long/Short,
   aşırı marjin, stop/target, günlük zarar ve toplam
   portföy riski reddedilmeli. Eski \`REVIEW_ONLY\` sonucunun
   işlem token'ı olarak kullanılması yasak.
4. İşlem isteklerine benzersiz idempotency key; aynı isteğin
   iki defa uygulanmaması. Kayıt, işlem, funding ve risk
   denetimi tutarlı aynı SQLite transaction'ında yazılmalı.
   Kayıt başarısızsa atomik rollback.
5. Spot mevcut envanteri satan çıkış ve Futures kapatma
   ayrı, risk azaltıcı işlemler olarak değerlendirilmeli;
   hiçbir durumda canlı borsaya emir çevrilmemeli.
6. Kurulan güvenli yürütme servisine canlı/gerçek Binance
   emir ve özel bakiye yetkisi kesinlikle eklenmemeli.
   Daha sonra EBBot yalnızca sürümlü, testli ve kimlikli
   Paper v2 API'yi kullanmalı.
7. Eşzamanlı emir, arıza sonrası yeniden oynatma, günlük
   zarar, Funding çift kayıt, stop/likidasyon, yanlış Spot/Futures
   sözleşmesi ve bozuk piyasa verisi testleri yeşil olmadan
   EBBot'ta işlem düğmesi açılmamalı.

**Kaynak repo EBBot GitHub bağlantısında bulunmadığından**
bu upstream değişiklikler kullanıcının Trading Office
kaynak koduna uygulanmış gibi gösterilmeyecek. İçerideki
\`ai-multi-market-trading-office-main.zip\` yalnızca
mimariyi ve doğru veri alanlarını doğrulamak için kullanıldı.

## Testler

- Python: \`tests/test_crypto_paper_bridge.py\`
- Vitest: \`apps/dsa-web/src/api/cryptoPaper.test.ts\`
  ve \`apps/dsa-web/src/components/crypto/CryptoPaperPanel.test.tsx\`
- CI: \`.github/workflows/crypto-paper-tests.yml\`.
- CI yalnız read-only endpoint içerdiğini ayrıca kontrol eder.

Windows PowerShell:

\`\`\`powershell
git switch feat/turkish-ui-hk-latin-display
git pull --ff-only origin feat/turkish-ui-hk-latin-display
python -m unittest discover -s tests -p "test_crypto_paper_*.py" -v
cd apps/dsa-web
npm.cmd run test -- src/api/cryptoPaper.test.ts src/components/crypto/CryptoPaperPanel.test.tsx
npm.cmd run build
\`\`\`

Bu etap **9. aşamanın okuma/gösterim kısmını** gerçekleştirir.
Emir açma/kapama kısmı, kaynak-tarafı atomik risk korumasına bağlıdır.
