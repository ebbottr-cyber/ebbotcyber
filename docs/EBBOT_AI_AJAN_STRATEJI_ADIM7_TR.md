# EBBot Kripto — 7. Aşama: Çoklu Ajan, Strateji ve Sinyal Günlüğü

> Durum: Kodları GitHub geliştirme dalına kaydedildi; derleme/çalışan
> Trading Office uçtan uca doğrulaması **henüz yapılmadı**.
> Bu modül yalnızca EBBot kripto tarafını etkiler.

## Kaynak koduna dayalı mimari

Yüklenen özel Trading Office ZIP'indeki gerçek kaynaklar:

- \`backend/app/agents/ensemble.py\`: 7 strateji ajanı + hacim + emir
  defteri = **9 kural tabanlı araştırma ajanı**.
- \`backend/app/agents/regime.py\`: oynaklık ve trende göre
  araştırma ağırlıkları.
- \`backend/app/agents/performance.py\`: kapanmış sinyal sonuçlarından
  örneklem eşiği ve daraltma kullanarak sınırlı ajan ağırlıkları;
  \`signals.sqlite3\` sinyal günlüğü.
- \`backend/app/strategies/engine.py\`: scalping, intraday, swing,
  trend_following, mean_reversion, momentum, breakout.
- \`backend/app/api/routes.py\`: /agents/analyze, /agents/signals,
  /agents/weights, /strategies, /strategies/{strategy}/signal.

**Ajanlar LLM değildir.** Bu aşamada kaynak Trading Office'un deterministik
strateji değerlendiricileri kullanılır. Ağırlıklar model eğitimi yapmaz.
Gelecekte bir LLM değerlendirmesi eklenecekse ayrı sürümlü bir hizmet
olarak ve merkezi risk sınırının *gerisinde* uygulanmalıdır.

## EBBot'a eklenen API

| Yöntem | EBBot endpoint'i | Kaynak |
|---|---|---|
| GET | /api/v1/crypto-office/research/strategies | Trading Office /strategies |
| GET | /api/v1/crypto-office/research/signals?market=spot | /agents/signals |
| GET | /api/v1/crypto-office/research/weights | /agents/weights |
| GET | /api/v1/crypto-office/research/decisions | EBBot salt-okunur SQLite audit |
| POST | /api/v1/crypto-office/research/analyze | Upstream GET /agents/analyze |
| POST | /api/v1/crypto-office/research/strategy | Upstream GET /strategies/{id}/signal |

Tüm EBBot endpoint'leri **yönetici oturumu** ister; merkezi auth kapalıysa
403 döner. Ticaret, para transferi, bakiye okuma, paper emir açma
uç noktaları oluşturulmadı. API anahtarı yalnız sunucuda bulunur ve
upstream yalnız sabit, izinli GET yolları üzerinden çağrılır.

\`POST /research/analyze\` tasarımı bilinçlidir. Trading Office'un
\`GET /agents/analyze\` endpoint'i sunucuda **kalıcı sinyal günlüğü
kaydı yazar**; dolayısıyla EBBot bunu zamanlayıcıdan, sayfa yüklenirken,
haberden veya otomatik yenilemeden tetiklemez. Yalnız kullanıcının
"9 Ajanı Çalıştır" seçimiyle başlatılır. BUY/SELL/HOLD birer görüş,
gerçek veya sanal emir değildir.

## Güvenlik ve veri kalitesi

- Market kimliği \`spot\` veya \`futures\`; futures simgesi upstream'e
  \`BTC/USDT:USDT\` şeklinde iletilir. Spot simgesiyle karıştırılmaz.
- Gerekli 250 OHLCV mumu EBBot'un daha önce eklenen Binance
  köprüsünden önceden doğrulanır; eski/eksik mumda analiz engellenir.
- Gelen ajan analizinde market, sembol, zaman dilimi, veri kaynağı,
  son mumun **zamanı ve kapanış fiyatı** ön kontrolle uyuşmalıdır.
- Dokuz benzersiz ajan, toplam dokuz oy, sonlu 0–1 güven/uyum,
  \`mode=research_only\`, \`execution=disabled\`,
  \`performance_weighting.training=false\` zorunludur.
- \`GET /strategies/{strategy}/signal\` için aynı mumun kapanış
  referansı ve zaman damgası da kontrol edilir.
- Hatalı yanıt geldiğinde yeni sonuç göstermeyiz, fiyat veya
  sinyal uydurmayız.
- Araştırma API'sinin sabit upstream GET allowlist'i
  \`/paper/orders\`, \`/agents/trade-plan\`, \`/risk/check\` gibi
  mutasyon veya yürütme yollarını içermez.
- Sinyal günlüğü \`mode=journal_only\` ve
  \`orders_placed=false\` sağlamalıdır.
- Her başarılı ensemble/strateji kararında, **HOLD dahil**,
  ayrı EBBot audit kaydı zorunludur; audit başarısızsa sonuç
  API'den başarıyla dönmez.
- Birinci aşamada herhangi bir risk motoru onayı verilmez:
  \`risk_approved=false\`, \`orders_placed=false\`.

Kaynakta \`/agents/analyze\` çağrısı yukarıdaki EBBot yanıt
doğrulamasından önce yönlü sinyal satırı yazabilir. Kaynak ile EBBot
arasında atomik işlem bulunmadığından, sonraki entegrasyon aşamasında
iki günlük için korelasyon kimliği ve idempotent doğrulama geliştirilmeli;
şimdiki ön doğrulama bu riski azaltır ancak tamamen ortadan kaldırmaz.

## Kalıcı denetim günlüğü

\`data/cache/ebbot_crypto_research_audit.sqlite3\`

Burada **bütün başarılı manuel ajan ve strateji kararları**, BEKLE
(HOLD) dahil, onaysız araştırma olarak saklanır. Karar türü, piyasa,
sembol, zaman dilimi, güven puanı, mum zamanı, doğrulanmış rapor JSON'u
ve SHA256 özeti bulunur. Bu SQLite veritabanı hisse/portföy
veritabanından ayrıdır.

Audit veritabanının yedekleme, erişim izni ve bütünlük kontrollerini
11. operasyonel güvenlik aşamasında güçlendireceğiz.

## EBBot arayüzü

\`http://localhost:5173/crypto-trading\`:

- AI Analiz Merkezi: Market/çift/zaman seçimi; yalnız tıklamayla
  dokuz ajanın kararı, ağırlıkları, oyları, piyasa rejimi ve haber
  risk özeti; yedi manuel strateji değerlendirmesi.
- AI Sinyalleri: Trading Office'un kalıcı yönlü sinyal günlüğü +
  EBBot'un BEKLE dahil bütün manuel kararlarının ayrı audit görünümü.
- Çoklu Ajan Merkezi: Kapalı araştırma sinyallerinden hesaplanan
  performans ağırlıkları; yetersiz örneklem durumunda varsayılan 1.0.

Üretilen açıklamalar Trading Office'un kaynak kodundan gelen
**İngilizce gerekçelerdir**. Türkçe arayüz etiketleri eklenmiştir,
ancak çevrilmediği hâlde kaynak açıklamasının Türkçeye çevrildiği
iddia edilmez.

## Offline testler / doğrulama

\`\`\`powershell
cd C:\Users\Thebo\Projects\ebbotcyber-test
git switch feat/turkish-ui-hk-latin-display
git pull --ff-only origin feat/turkish-ui-hk-latin-display
python -m unittest discover -s tests -p "test_crypto_research_bridge.py" -v
python -m unittest discover -s tests -p "test_crypto_research_audit.py" -v
cd apps\dsa-web
npm.cmd run test -- src/api/cryptoResearch.test.ts src/components/crypto/CryptoResearchPanel.test.tsx
npm.cmd run build
\`\`\`

Bu testler yanlış kontrat/piyasa, yeni olmayan mum, farklı kapanış
fiyatı, eksik ajan, bozuk oy, canlı yürütme bayrağı, audit diski
hatası ve HOLD kararını kayıt altına alma vakalarını kapsar.
Kodlar ve testler GitHub'dadır; GitHub Actions sonucu veya canlı
entegrasyon sonucu şu an mevcut değildir.

## Sonraki aşama

**8. aşama: zorunlu, AI'dan bağımsız risk motoru.** Motorun
giriş doğrulaması, pozisyon risk sınırı ve muhasebe korumaları
tamamlanmadan Spot/Futures Paper Trading emir simülasyonu açılmaz.
