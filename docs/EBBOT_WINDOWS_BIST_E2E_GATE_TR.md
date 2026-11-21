# EBBot — Windows uçtan uca BIST veri kanıtı testi (dağıtım değil)

**Güvenlik:** Bu PR yalnız **sentetik örnek verilerle** Windows'ta CLI → doğrulanan CSV → 4-piyasa kapsam denetimi → BIST kimlik denetimi → Veri Merkezi rapor okuyucusu zincirini test eder. Gerçek KAP/BIST güncel verisi, canlı OHLCV, broker hesabı, API anahtarı, lisans, otomatik emir veya yüklenebilir Windows kurulum paketi sağlamaz. PR taslaktır ve `main`e birleştirilmez.

## Bu PR neden gerekli?

Önceki PR #203'ün `src/services/bist_identity_report_reader.py` modülü, `scripts/build-backend.ps1` içindeki PyInstaller zorunlu import/probe listesinde yoktu. Python testleri geçse bile bu modülün `.exe` içinde bulunduğu garanti değildi. Bu PR modülü hem `hiddenImports` hem gerçek paket oluşturma sonrası çalıştırılan `DSA_PACKAGED_IMPORT_PROBE` listesine ekler.

**Önemli ayrım:** Yeni CI, modülün paketleme betiğinde listelendiğini **kaynak kod seviyesinde** kontrol eder. Gerçek PyInstaller exe'sini üretmez, imzalamaz veya kurmaz. Gerçek frozen dosyanın import doğrulaması yalnız ayrı, izinli Windows build işleminde doğrulanabilir; bu PR bunu yayın onayı saymaz.

## Windows CI'da denetlenen uçtan uca senaryo

1. Test geçici Windows klasöründe, yalnız sentetik `KAP` şekliyle hazırlanmış şirket listesi, ayrı sentetik `XIST` referansı/ISO 6166 check-digit, sağlayıcı eşlemesi, manuel seans takvimi ve **uydurma test mumu** üretir. Bunlar gerçek piyasa kayıtları değildir.
2. `python -m scripts.stage_ebbot_equity_ohlcv` çağrısı SHA-256, CSV, sembol, para birimi, sağlayıcı ve gün kontrolünden sonra yalnız yerel yeni CSV çıktısı oluşturur; hiçbir fiyat servisine bağlanmaz.
3. `python -m scripts.audit_ebbot_market_data_coverage` ve `python -m scripts.audit_ebbot_bist_reference_identity` komutları çalışır. Dört piyasa ile BIST rapor okuyucuları ham sembol/ISIN/fiyatı **yanıta koymadan** özetleri kabul eder.
4. `python -m scripts.audit_ebbot_equity_session_gaps` sağlanan takvimleri karşılaştırır; diğer piyasalarda takvim yoksa **bilinmiyor** durumunu kullanır.
5. Sağlayıcı hakları denetimi her kaynakta `BLOCKED_NOT_APPROVED_FOR_DATA_INGESTION_OR_TRADING` kalır.
6. CSV sonradan değiştirilirse SHA-256 reddeder; yanlış ISIN'i borsa kimlik denetimi reddeder; yanlış fiyat sağlayıcısı sembolü reddedilir; mevcut çıktı dosyasını ezme reddedilir; XIST dosyası yoksa aktif pay sayısı **null** olur.
7. PyInstaller import listesi ve frozen sağlık probunun BIST API'sini gizlediği denetlenir; Windows React testleri/ESLint/TypeScript/Vite derlemesi ayrıca koşar.
8. Linux'taki gerçek FastAPI auth/oturum testi, iki özel rapor API'sinin yetkisiz erişimden korunmasını ve frozen React sağlık probunun gizli API'leri açmamasını sınar.

## PowerShell ile kendi PC'nizde güvenli test

EBBot deposunun ana klasöründe:

```powershell
python -m unittest discover -s tests -p test_ebbot_windows_equity_e2e.py -v
python -m unittest discover -s tests -p test_ebbot_windows_bist_packaging.py -v
python -m unittest discover -s tests -p test_equity_coverage_windows_packaging.py -v
```

Bu komutlar **sadece geçici test dosyaları** oluşturur, önceden var olan kullanıcı fiyat dosyalarını değiştirmez.

React tarafında:

```powershell
cd apps\dsa-web
npm ci
npm run test -- src/components/data-center/BistIdentityPanel.test.tsx src/components/data-center/EquityCoveragePanel.test.tsx
npm run lint
npm run build
```

## Gerçek kullanıcı dosyalarıyla yapılması gerekenler

- **Kaynaklar:** Yetkili ve güncel KAP şirket listesi ile gerçekten ayrı kaynaktan gelmiş tarihli BIST XIST pay referansı gerekir. Önceki Windows bilgisayarındaki 803 KAP adayının dosyası GitHub'da mevcut değildir.
- **Lisans:** Operatör, gerçek OHLCV sağlayıcısının geçmiş veri saklama/algoritmik analiz kullanım hakkını ve Türkiye'den erişimi doğrulamalıdır. BIST `source` CSV etiketinin `official` olması bunu kanıtlamaz.
- **Üretim:** Gerçek dosyalar bilgisayarda mevcutsa önce PR #202 ve #200 kılavuzlarına göre yerel raporları üretin; `EBBOT_BIST_IDENTITY_REPORT_PATH` ve `EBBOT_EQUITY_COVERAGE_REPORT_PATH` üzerinden yalnız özetleri panelde gösterin.
- **Windows:** Ayrı onaylı PyInstaller ve Electron paketleme işinde gerçek `.exe` içinde yeni modül importunu, kurulum yolunu, güncelleme kimliğini ve imzayı doğrulayın. Bu CI, kurulum paketi üretmediği için Windows dağıtımına izin vermez.
- **GitHub:** PR #194, #196, #198, #199, #200, #201, #202, #203 ve bu PR birbirine yığılmış **taslaklar**. Güncel main üzerinde tam regresyon ve bağımlılık sırası incelenmeden hiçbirini otomatik birleştirmeyin.

**Durum: NO MERGE / NO DEPLOY / NO PAPER / NO LIVE TRADING.** CI sonucu yalnız sentetik veride kodun beklendiği gibi davrandığının kanıtıdır.
