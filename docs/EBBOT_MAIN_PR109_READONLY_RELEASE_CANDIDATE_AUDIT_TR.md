# EBBot — main + PR #107/#109: ayrı, işlemsiz sürüm adayı

Tarih: **20 Kasım 2026**. Bu dosya `main` için birleşme emri değildir.

## Doğrulanan kaynaklar

- `main`: `d8d4a6ea6bb618e8ff0a568c2ffbd558016860a1` (PR #105 dahil)
- PR #107: `70964f0c1f47912765cee0376c7974828a353e13`, tam backend 9.079 test başarılı.
- PR #109: `e777d28d20ca59cfaabf99ba58c73b9d5e7a5830`, tam frontend 1.499 test + PWA 9 test başarılı.
- Ortak Git atası: `6be70ec2ed5cc29a3612646b9d5eda370cc3c49b`.
- Son karşılaştırmada `main` dalında **8 ayrı commit**, 61 değişmiş dosya; PR #109'da 521 ayrı commit / 287 değişmiş dosya bulunuyordu.
- 61 main dosyasının **50'si** değişiklik içermeyen veya yalnız main tarafında değişmiş olduğu için Git blob SHA'larıyla sürüm adayı ağacına taşındı; **2 dosya zaten birebir aynıydı**; **9 gerçek çakışma** elle değerlendirildi.

## 9 çakışma ve çözüm

| Dosya | Karar |
| --- | --- |
| `.env.example` | main'in 1095 satırlık örnek ayar envanteri tutuldu; PR #109'daki ek ModelFlare notları kaybedilmedi; `MEME_RADAR_LIVE_ENABLED=false` ve `MEME_COIN_DISCOVERY_ENABLED=false` açıkça eklendi. Varsayılan zamanlayıcı kapalı kaldı. |
| `api/v1/router.py` | Kapsamı farklı iki Solana servisi tek yolda çakışıyordu. PR #109'un `/api/v1/meme-coins` araştırma API'si korundu; main'in ayrı salt-okunur gözlem servisi `/api/v1/meme-radar` altına alındı. |
| `apps/dsa-web/src/App.tsx` | PR #109'un kapsamlı `MemeCoinPage` sayfası `/meme-coins` altında kaldı; main'in manuel gözlem `MemeCoinsPage` sayfası `/meme-radar` oldu. |
| `apps/dsa-web/src/components/layout/SidebarNav.tsx` | İki bağımsız sayfa için farklı menü öğesi. Hisse asistanı/eleme sırası değiştirilmedi. |
| `apps/dsa-web/src/components/run-flow/utils.ts` | PR #109 içinde `zh-CN`, `en-US` ve `tr-TR` zaten destekleniyor; main'in eşdeğer değişimi tekrar uygulanmadı. |
| `apps/dsa-web/src/components/settings/NotificationTestPanel.tsx` | PR #109'daki Türkçe `E-posta` korundu; main'in Türkçe `Özel Webhook` etiketi eklendi. |
| `apps/dsa-web/src/i18n/uiText.ts` | Mevcut `layout.nav.memeCoin` metinleri korunarak üç dilde yeni `layout.nav.memeRadar` anahtarı tanımlandı. |
| `apps/dsa-web/src/utils/systemConfigI18n.ts` | PR #109'daki ayrıntılı Türkçe ayar başlıkları main'in karşılıklarını zaten kapsıyor; var olan çeviriler korunuyor. |
| `docs/CHANGELOG.md` | main'de ayrı gelişen 14 Solana gözlem/geçmiş kalite değişikliği maddesi, PR zincirinin değişiklik kaydı korunarak eklendi. |

Main'deki 50 değişikliğe veri kaynakları, salt-okunur Solana testleri, gözlem betikleri ve eski kapalı iş akışlarının denetimi dahildir. Kaynak kodun bu dalda bulunması **ağ veya bot çalıştırıldığı anlamına gelmez**.

## Sürüm adayı sınırları

- Gerçek emir, cüzdan, canlı işlem ve otomatik sanal alım-satım **açılmadı**.
- `main`, PR #107 ve PR #109'un başı **değiştirilmedi**. Sadece `release-candidate/ebbot-main-pr109-offline-20261120` test dalı değiştirildi.
- Radarı kapalı hâlde açmak için `GET /api/v1/meme-radar/status`; veri taraması yalnız `MEME_RADAR_LIVE_ENABLED=true` **açıkça** ayarlanırsa ve kullanıcı ayrıca `POST /scan` gönderirse gerçekleşebilir. Bu sürüm adayı bunları **yapmaz**.
- Yeni `tests/test_release_candidate_main_pr109_routes.py`, iki bağımsız URL, aynı yolda iki router olmaması, kapalı varsayılan taramalar ve şifresiz örnek ayarları denetler.
- GitHub Actions **tam backend** (ağ işaretli testler hariç), **tam frontend** (test/lint/TypeScript/Vite/PWA), ayrı **Solana fail-closed/Windows** koşumlarını raporlar. Başarısızlık varsa taslak blokeli kalır.
- Github üzerindeki Windows ön kontrolü gerçek kullanıcının bilgisayarındaki Electron kurulumunun yerini tutmaz.

## Birleşme eşiği

Tam backend ve frontend testleri, Radar/strateji ayrımı, FX güvenliği ve kapalı iş akışı kontrollerinin hepsi geçse bile otomatik merge/deploy veya emir izni **yoktur**. Güvenlik ve finansal veri lisansları için ayrıca kullanıcı onayı gerekir.
