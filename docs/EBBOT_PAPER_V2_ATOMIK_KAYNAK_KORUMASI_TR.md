# EBBot Kripto — Paper V2 atomik kaynak koruması (Aşama 9b)

> **Durum (17 Kasım 2026):** Kodlar hazır; özel Trading Office
> deposuna ve gerçek çalışan servise henüz uygulanmadı.
> **TRADING_ENABLED=false ve EBBot Paper emir yetkisi kapalı kalıyor.**

## Kaynak kodu ve teslim

Kullanıcının yüklediği \`ai-multi-market-trading-office-main.zip\` kaynağı
üzerinde ayrı çalışıldı. Çünkü bağlı GitHub hesabı yalnız
\`ebbottr-cyber/ebbotcyber\` deposuna erişebiliyor; ayrı özel
Trading Office deposuna doğrudan commit yapma yetkisi yok.

Kullanıcıya \`EBBot_TradingOffice_PaperV2_SafePatch.zip\` dosyası
hazırlandı. Bu paketteki \`TradingOffice_PaperV2.patch\`,
\`Uygula-PaperV2-Yama.ps1\`, \`README_TR.md\`
şunları değiştirir:

| Kaynak dosyası | Değişiklik |
|---|---|
| \`backend/app/main.py\` | HTTP seviyesinde eski Paper yazma yollarını bloke etme |
| \`backend/app/paper/write_policy.py\` | Yeni/gelecekteki Paper yazma yollarını varsayılan reddetme |
| \`backend/app/paper/automation.py\` | Eski otomatik Futures işlem yolunu kapatma |
| \`backend/app/paper/ledger.py\` | Spot defterini dış SQLite transaction bağlantısıyla kullanabilme |
| \`backend/app/paper/futures.py\` | Futures açma/kapamayı dış transaction bağlantısıyla kullanabilme |
| \`backend/app/paper/guarded_v2.py\` | Spot/Futures atomik Paper risk, audit, idempotency işlemi |
| \`backend/app/api/routes.py\` | \`GET /paper/v2/capabilities\` ve opt-in \`POST /paper/v2/execute\` |
| \`backend/tests/test_guarded_paper_v2.py\` | İzole SQLite üzerinde 10 çevrimdışı güvenlik testi |

**Önemli:** Yama bir API veya Trading Office sürümünün resmî yükseltmesi
değildir. Kullanıcı özel depodaki gerçek sürüm ile birebir uyumu
\`git apply --check\` ile doğrulamalı; script eşleşmeyen
kaynak dosyalarını zorlayarak değiştirmez.

## Kaynak işlem güvenliği

- \`PAPER_V2_EXECUTION_ENABLED\` yoksa/false ise bütün V2 yazma kapalıdır.
- Ayrı admin/read anahtarları ve \`API_AUTH_ENABLED=true\` zorunludur.
- \`TRADING_ENABLED=false\` kalır. Borsa private API/çekme/gerçek emir
  fonksiyonu eklenmedi.
- HTTP eski \`POST/PUT/PATCH/DELETE /api/v1/paper/...\` yolları
  varsayılan engellenir; güvenli \`/paper/v2/execute\` ayrı protokoldür.
- V2 işlem fiyatı, işlem derinliği ve Futures funding yalnız Binance
  **herkese açık piyasa verisi** üzerinden sunucuda alınır.
- Ticker ve emir defteri kimliği ve gerçek zaman damgası zorunludur.
  Market verisi bayatsa, kimlik yanlışsa veya missing/null ise
  işlem simülasyonu yapılmaz.
- Spot, Futures ve birleşik portföy risk hesabı aynı
  SQLite \`BEGIN IMMEDIATE\` kilidinde mevcut kayıtlardan yeniden
  türetilir. Risk testi, pozisyon güncellemesi, kaynak defter işlemi
  ve idempotent audit eklemesi aynı transaction'dadır.
- İsteğe özgü \`client_request_id\` aynı yük ile tekrar gelirse
  kayıt ikinci kez uygulanmaz; farklı yükle tekrar kullanımı reddedilir.
- Futures Long/Short izole marjin ve stop tamponları vardır;
  likidasyon fiyatı Binance kademeli likidasyon formülü değildir.
- Funding kayıtları için legacy mutasyon kapalıdır; V2 şu an yeni
  funding tahakkuku gerçekleştirmiyor.
- Eski Futures sözleşmesi \`BTC/USDT\` ve yeni kanonik
  \`BTC/USDT:USDT\` kimliği mevcut aynı hesapta karışırsa,
  otomatik veri taşıması yapılmaz; önce kontrollü göç gereklidir.

## EBBot tarafına eklenen salt-okunur uyumluluk kontrolü

\`GET /api/v1/crypto-office/paper/capabilities\`:

- Trading Office'un \`GET /api/v1/paper/v2/capabilities\` yanıtını
  doğrular.
- \`upstream_v2_present\` ve \`upstream_v2_opted_in\` gösterir.
- Upstream protokol açık olsa bile:
  \`ebbot_paper_execution_permitted=false\`,
  \`real_exchange_orders=false\`, \`execution=disabled\`.
- Upstream 404, bozuk kontrat veya erişim hatası olursa
  \`upstream_v2_present=false\` gösterir.
- React Paper Trading ekranında yalnız kaynak protokol
  durumunu gösterir, **emir düğmesi açmaz**.

## Test ve sınırlar

**Kaynak ZIP kodu** (lokal çevrimdışı):

- Yeni Paper V2 senaryo testleri: **10/10 geçti**.
- Seçili geriye dönük Spot/Futures testleri ile birlikte: **39/39 geçti**.
- Daha geniş eski test grubu: **77 geçti, 5 başarısız**. Aynı 5
  başarısız test, yama uygulanmamış orijinal kaynak ZIP'inde
  de gözlendi. Bunlar bağımsız düzeltilmeden kaynak projenin
  bütün testleri yeşil kabul edilmez.
- \`git apply --check\` ve temiz ayrı kaynak kopyasına gerçek
  patch uygulama kontrolü geçti.
- HTTP üzerinden gerçek auth/end-to-end işlem ve Binance feed
  testi *çalıştırılmadı*.

**EBBot GitHub CI:** Kripto Paper read-only workflow ve Kripto
Risk workflow başarıyla çalıştı. Paper V2 protocol
handshake için özel testler eklendi.

## Açmadan önce zorunlu adımlar

1. Trading Office'un **asıl özel GitHub deposunda** yama sürümünü
   karşılaştırıp PR aç; mevcut dosyalar değişmişse kör overwrite yapma.
2. Eski kaynaktaki 5 başarısız testin nedenlerini değerlendir,
   gerekirse ayrı düzeltme yap.
3. Admin auth, protokol bayrağı, HTTP write lockdown, kaynak piyasa
   kimliği/timestamp, tekrar gönderim, rollback ve çakışan
   farklı işlemler için uçtan uca testler.
4. Spot/Futures mevcut pozisyon kimliği göçünün gerekli olup
   olmadığını kontrol et.
5. Kaynak servisinde **yalnız test ortamında** V2 opt-in
   ayarını kısa süreli açarak doğrula.
6. Risk motorunun para birimi, fiyat/yasal kontrat eşleşmesi,
   funding, komisyon, sürümlü protokol kimliği ve kill switch
   politikasını EBBot ile eşleştir.
7. En son EBBot sunucusuna ayrı, sürümlü **yalnız Paper**
   yazma API'si eklenebilir. Şimdilik eklenmedi.

**Bir başarılı risk ön kontrolü başka bir işlem için izin jetonu değildir.**
Bu değişikliklerin hiçbiri gerçek borsaya emir göndermeyi açmaz.
