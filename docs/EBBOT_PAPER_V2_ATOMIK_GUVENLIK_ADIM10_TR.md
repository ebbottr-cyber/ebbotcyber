# EBBot — 10. Aşama: Paper V2 atomik kapı ve güvenli kurulum kontrolü

**Durum:** EBBot tarafı salt okunur Paper V2 hazırlık denetimi eklendi.
Trading Office kaynak koduna yönelik uygulama yaması hazırlanıp temiz
kaynağa karşı \`git apply --check\` ile doğrulandı; **kaynak GitHub deposuna
otomatik uygulanmadı**. Her iki uygulamada da gerçek borsa emirleri kapalıdır.
EBBot'ta Spot/Futures Paper emir oluşturma veya pozisyon kapatma API'si **yok**.

## Kaynak ve elde bulunan yama

Kullanıcının yüklediği \`ai-multi-market-trading-office-main.zip\` temel alındı.
Bu ZIP'in SHA-256 özeti:

\`\`\`
b14019a9ce398b9eadea2157242c3ea8ded1b956b0ac5e087bbb662754ac84df
\`\`\`

Kaynağa özel \`EBBot_TradingOffice_PaperV2_SafePatch.zip\` dağıtım
paketinde \`TradingOffice_PaperV2.patch\`, \`README_TR.md\` ve
\`Uygula-PaperV2-Yama.ps1\` bulunur.

- Paket SHA-256: \`a2c3c358e3de277791981ae11841ec1a5d3d625d911cd235a39723e95f49ebc9\`
- Patch SHA-256: \`01478a3639d7e431bbd749fd6d98b094e6614126c7f8769c3b0eb1338166105a\`

Patch, kullanıcıda mevcut ama bağlı GitHub uygulamasında erişilemeyen
ayrı **Trading Office** deposuna uygulanmak üzere hazırlanmıştır.
Buradaki EBBot GitHub PR'ı, Trading Office dosyalarını yerinde güncellemez.

## Kaynak tarafındaki tasarlanan atomik protokol

- Önceki \`/api/v1/paper/*\` yazma yolları ve otomatik Futures Paper
  açma/kapatma varsayılan olarak engellenir.
- Yeni \`GET /api/v1/paper/v2/capabilities\` yalnız durum bildirir.
- Yeni \`POST /api/v1/paper/v2/execute\` ancak tüm ayrı güvenlik
  koşulları sağlanırsa çalışabilecek şekilde tasarlandı; paket
  varsayılanında kapalıdır.
- \`TRADING_ENABLED=false\` zorunludur. V2 ayrıca
  \`PAPER_V2_EXECUTION_ENABLED=true\`, kimlik doğrulaması etkin,
  farklı ve güçlü admin/read key şartlarını kontrol eder.
- Spot BUY/SELL, Futures LONG/SHORT ve tam Futures CLOSE yalnız
  sanal muhasebede ele alınır.
- Binance'in yalnız public piyasa verileri, aynı SQLite
  \`BEGIN IMMEDIATE\` transaction'ında güncel risk/pozisyon/marjin
  kontrolleri, kayıt, request-idempotency ve denetim günlüğü
  ile birlikte doğrulanır; başarısızlık rollback gerektirir.
- Aynı \`client_request_id\` başka emir çalıştırmaz.
- Funding uygulama mutasyonları bu protokolde açılmadı.
- Trading Office kaynak repo dağıtımı, HTTP admin kimlik
  doğrulaması, gerçek Binance public feed ve eşzamanlı süreç
  dağıtımı henüz uçtan uca doğrulanmadı. Bu koşullar sağlanmadan
  V2'yi etkinleştirmeyin.

## EBBot'taki güvenli durum denetimi

Mevcut yönetici oturumlu
\`GET /api/v1/crypto-office/paper/capabilities\`
isteği yalnız kaynak sunucunun
\`GET /api/v1/paper/v2/capabilities\` yolunu inceler.

Kontrolün güncel davranışı:

- Kaynakta V2 yoksa: \`503 / paper_v2_not_installed\`.
- Kaynak erişilemiyorsa: \`503 / paper_v2_unavailable\`.
- Protokol, kaynak, admin-auth, legacy-write kilidi veya
  gerçek emir bayrakları beklenenden farklıysa:
  \`503 / unsafe_v2_capability\`.
- Kaynak V2 kurulu ama kapalı olduğunu bildirirse:
  \`SOURCE_INSTALLED_DISABLED\`.
- Kaynak V2'yi açık olarak bildirse bile:
  \`SOURCE_FLAG_ON_UNVERIFIED\` — bu bir beyan, **test kanıtı değil**.

EBBot her başarılı yanıtında aşağıdakileri zorunlu döndürür:

\`\`\`json
{
  "readiness_verified": false,
  "ebbot_paper_execution_permitted": false,
  "real_exchange_orders": false,
  "execution": "disabled"
}
\`\`\`

Tarayıcıdan yalnızca durum okunur, herhangi bir Paper V2 yazma
endpoint'i, emir düğmesi veya canlı borsa erişimi açılmaz.
Gösterim ekranındaki durum kaynağın kendi beyanına dayanır.

## Güvenli kurulum sırası (ileride)

1. Trading Office deposunun değişikliklerini yedekleyin;
   \`git status\` temiz ve kod tabanı ZIP ile uyumlu olsun.
2. Bu sohbetten sağlanan kaynak yama paketini indirin ve
   README_TR talimatına göre \`git apply --check\` yapın.
   Eşleşmeyen sürüme \`--reject\` veya zorlayarak uygulama yapmayın.
3. Varsayılan ortamda \`TRADING_ENABLED=false\` ve
   \`PAPER_V2_EXECUTION_ENABLED=false\` tutun.
4. Kaynak tarafında \`pytest backend/tests/test_guarded_paper_v2.py\`
   ve mevcut tüm testleri çalıştırın. Ağ erişimi olmayan kaynak
   testlerinde **10/10** atomik risk/idempotency/rollback testi geçti.
5. Kaynak yönetici anahtarı, salt-okunur anahtar,
   kullanıcının EBBot admin oturumu ve gerçek HTTP rota testleri
   ayrıca doğrulanmalı.
6. EBBot Paper V2 hazırlık ekranı artık güvenli kaynak beyanını
   ayırt edebilir. Bu yalnız gözlem verir.
7. **EBBot sanal emir açma ancak ayrıca uygulanacak uçtan uca
   yazma sözleşmesi, CSRF/oturum doğrulaması, merkezi risk denetimi
   ve kurtarma/rollback testleri tamamlandıktan sonra** açılabilir.

## Otomatik doğrulama

- \`tests/test_crypto_paper_v2_status.py\`: sabit public-olmayan
  localhost GET, kaynak sözleşmesi, eksik veya hatalı durum,
  aşırı büyük/malformed yanıt ve fail-closed kontrolleri.
- \`tests/test_crypto_paper_v2_capabilities.py\`: eski izin veren
  varsayımları kaldırıp yeni katı sözleşmeye günceller.
- \`apps/dsa-web/src/api/cryptoPaper.test.ts\`: kaynak beyanından
  yürütme yetkisi üretmeyi reddeder.
- \`.github/workflows/crypto-paper-tests.yml\`: Python offline
  doğrulama, TypeScript test ve tüm frontend derlemesi.

**Bu aşamanın tamamlanan kapsamı kurulum hazırlığı ve veri güvenliğidir;
sanal emir akışını açma değil.**
