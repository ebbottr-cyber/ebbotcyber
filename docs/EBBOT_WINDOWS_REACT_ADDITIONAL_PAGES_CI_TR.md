# EBBot Windows: dört ek React ekranının güvenli gezinme deneyi

**Durum: CI denetimi, yayın engelli.** Ön koşul: PR #163 ile doğrulanmış olan Windows paketli Electron + Türkçe React kabuğu, localhost sağlık kontrolü ve sahte salt-okunur oturum durumu.

## Denenen sayfalar

Gerçek PyInstaller + NSIS (`--publish never`) çıktısındaki `EBBot.exe` açılır; normal uygulama başlatma yolu değil, sadece frozen Windows/GitHub Actions'a ve loopback porta kilitli `--ebbot-ci-ui-smoke` kullanılır. Gerçek Türkçe React üretim dosyaları Chromium'da yüklenir. Önce Ana menü, Kullanım ve Veri Merkezi; sonra yalnız **NavLink tıklayarak** şu dört sayfa kontrol edilir:

| Menü | SPA yolu | Beklenen gerçek `main h1` başlığı |
|---|---|---|
| Portföy | `/portfolio` | `Portföy Yönetimi` |
| AI Önerileri | `/decision-signals` | `AI Önerileri` |
| Hisse Tarama | `/screening` | `Hisse Tarama` |
| Ayarlar | `/settings` | `Ayarlar` |

Sıra bilinçli olarak Ayarlar'ı sona koyar. Ekrandaki form, emir, rapor oluşturma, takvim, tarama veya ayar kaydetme butonları **tıklanmaz**. Bu sadece **gerçek React sayfa/başlık/menü navigasyonu**, işlev doğrulaması değil.

## Teste özel API ve ağ koruması

- Backend yalnız frozen exe, `GITHUB_ACTIONS=true`, tam `--serve-only --host 127.0.0.1 --port N`, `EBBOT_PACKAGED_HEALTH_PROBE=1` ve `EBBOT_PACKAGED_REACT_PROBE=1` ile React test moduna geçebilir.
- Test backend'i yalnız `GET /api/health`, **sahte ve yalnız GET** `/api/v1/auth/status`, gerçek paketli statik `/assets/*`, ve SPA `GET /`, `/usage`, `/data`, `/portfolio`, `/decision-signals`, `/screening`, `/settings` yollarına erişir.
- Production router yüklenmediğinden `/api/v1/analysis/analyze`, `/api/v1/screening/run`, portföy/API işlem uç noktaları, login veya ayar yazma yolları kaydedilmez. Testlerde 404/405 beklenir; gerçek/paper trade, bot stream, zamanlayıcı, piyasa taraması ve veri yenilemesi yoktur.
- Electron webRequest yalnız tam `http://127.0.0.1:<port>` ve `file:` URI'lerine izin verir. Bu işletim sistemi düzeyinde tam ağ sandbox'ı değildir.
- React smoke başarısı için tüm belirtilen sayfaların *gerçek* başlığının gelmesi gerekir. Standart splash başarı kodu 0'dır; React navigasyonu başarılıysa ayrı **42** kodu kullanılır, Python runner doğru kodu ve çıkış durumunu denetler. `PASS: packaged Turkish React Usage/Data, Portfolio, AI Signals, Screening and Settings navigation verified in Electron (CI-only, read-only).` satırı ayrıca loglanır.

## Küçük üretim dili düzeltmeleri

- Hisse Tarama üst başlığındaki sabit Çince metin `t('layout.nav.screening')` kullanır.
- AI Önerileri ve Ayarlar üst başlıklarının Türkçe karşılıkları i18n sözlüğüne eklenir. Bu sayfaların **tüm içeriği** henüz çevrilmiş kabul edilmez.

## Kabul kriterleri / açık yayın engelleri

- [ ] Yeni branch'te gerçek Windows paketleme, paket audit, Electron unit, yeni salt-okunur API sözleşmeleri ve gerçek renderer gezinmesi yeşil.
- [ ] Aynı branch head SHA'sında genel frontend lint/TypeScript/Vite ve backend regresyonu yeşil.
- [ ] Windows installer/EXE, updater, `.env` veya private kullanıcı verisi yayımlanmadı. Sadece paket audit JSON'u.
- [ ] Üretim veri API'leri, form etkileşimleri, gerçek Windows kurulum/upgrade/kaldırma, SmartScreen/Defender, kod imzası, üçüncü taraf lisanslar ve veri göçü **hala ayrı engeller**. Bu PR yayın veya gerçek/sanal emir açma yetkisi vermez.
