# EBBot — dört piyasa ve BIST bütünleşik inceleme / birleştirme kapısı

**21 Kasım 2026.** Bu dal, yayın veya canlı işlem onayı değildir. `main` değişmez. Veri lisansı, gerçek borsa geçmişi, Windows kurulum paketi ve Türkiye'deki aracı kurum yetkisi bu PR ile sağlanmaz.

## Neden ayrı entegrasyon dalı?

PR #194 → #196 → #198 → #199 → #200 → #201 → #202 → #203 → #204 taslak bir zincirdir. Sonraki güncellemeler eski dalları geride bıraktı: #196'nın dalında #194'ün 5 yeni commit'i ve #202'nin dalında #201'in 6 yeni commit'i yoktu. Bunun sonucunda son #204 dalında aşağıdaki sonradan geliştirilen KAP/BIST kaynak ve test değişiklikleri bulunmuyordu.

**Birleştirme yaklaşımı:** Son test edilmiş Windows dalı #204'ün commit'i `9d6964b0eab6517899c2557ca9026962ca213e8e` temel alındı. PR #201'in güncel `ed0e067034dccf5b15ca285bfa713d5539a511d1` ve PR #194'ün güncel `c235044b4e841cc5a473f9a44322b095b7b519a0` kayıtları ayrıca merge parent olarak işaretlendi. Sadece kaynakları farklılaşmış **11 dosya** dosya SHA kimliğiyle birleştirilerek ilk entegrasyon commit'i `5bf02943d235ef4963b0c712d71c5ceb91c6ac9e` oluşturuldu. Diğer mevcut PR #204 dosyalarına dokunulmadı.

Entegrasyona eklenen/yenilenen içerik:

- `scripts/audit_ebbot_kap_market_inventory.py` + testleri: KAP pazarları, aday şirket envanteri ve kaynak bütünlüğü; otomatik aktif borsa hisse/ISIN/fiyat çıkarımı YOK.
- `scripts/audit_ebbot_kap_bist_crosswalk.py` + testleri: operatörün sunduğu KAP/BIST kod kimlikleri için çevrimdışı denetim; bağımsız resmi yetki kanıtı YOK.
- Güncel `audit_ebbot_market_data_coverage.py`: resmi kaynak aday Xetra dosyası için **ham bayt SHA-256**; aynı dosya Windows/Linux'ta byte hash ile değerlendirilir. Windows satır sonu hatasına geri düşmez.
- Güncel seans boşlukları, Xetra, KAP, piyasa veri bütünlüğü, Türkçe belgeler ve regresyon testleri. Taslak #204'teki Windows sentetik OHLCV zinciri ve API yetki testleri korunur.

## Bütünleşik test: `.github/workflows/ebbot-equity-integration-regression.yml`

| İş | Ne doğrular? | Onaylamadığı konular |
|---|---|---|
| `integrated-offline-backend` | Tüm backend testlerini `pytest -m 'not network'` ile çalıştırır; bilinmeyen/eksik hisse verisinin sıfır olarak uydurulmamasını yeniden sınar | Dış ağ gerektiren testleri, veri lisansını, broker erişimini |
| `windows-bist-kap-and-ohlcv` | Windows 2022 üzerinde KAP & XIST kurgusal dosyaları, gerçek CLI girişleri, SHA-256, İSİN, günlük fiyat, seans, dört piyasa raporu ve PyInstaller kaynak sözleşmesini kontrol eder | İmzalı gerçek `.exe`, gerçek lisanslı fiyatlar, kurulum |
| `integrated-admin-api` | İki veri API endpoint'inin oturum korumasını, ham sembol/ISIN/fiyat/yol sızdırmamasını ve salt-okunurluğu kontrol eder | Üretim ağ yapılandırmasını |
| `integrated-full-react` | React'taki **tüm** Vitest dosyalarını, ESLint'i, TypeScript'i ve üretim Vite derlemesini çalıştırır | Elektron Windows paketi ve yayın izni |

Testlerdeki fiyatlar/sözde KAP kayıtları **sentetik**. `SCHEDULE_ENABLED=false` ve canlı kripto radar devre dışı; gerçek veri çekme, alım-satım, paper fill, veritabanına fiyat yazma veya otomatik strateji aktivasyonu yoktur.

## Birleştirme koşulları

1. GitHub Actions birleşik dört işin tamamı başarılı olmalı. `network` işaretli ve atlanan testlerin sayısı açıkça incelenmeli; testte atlama başarılı uygulama kanıtı olarak sayılmamalı.
2. Geride kalan eski PR dallarına force-push yapılmamalı. Entegrasyon dalının güncel `main` üzerinde merge-base'i, eklenen/kaldırılan dosyaları, ek güvenlik ve otomatik işlem bayrakları inceleme sırasında kontrol edilmeli.
3. `main` dalı branch protection veya eşdeğer required-status check kuralları, en az bir bağımsız inceleme ve yönetici güvenliği korunmadan merge yapılmamalı.
4. Windows üzerinde gerçek PyInstaller backend binary'si oluşturulup `DSA_PACKAGED_IMPORT_PROBE` ile BIST ve dört piyasa rapor okuyucuları gerçekten import edilebilmeli; Electron isim/kimlik/imza/güncelleme adresi ayrıca doğrulanmalı.
5. Yasal erişimi ve kullanım/saklama hakkı doğrulanmış gerçek KAP/BIST işlem listeleri, ISIN eşlemesi ve OHLCV kayıtları **yerel, özel dosyada** test edilmeli. Bunların hiçbiri ana repo veya PR'a yüklenmemeli.
6. Canlı işlem/sanal işlem, ayrı risk ve fill denetimleri tamamlanıp açık bir işlem devreye alma izni alınmadan **kapalı** kalmalı.

## Sonuç ve kapsam

**Entegrasyon dalının oluşturulması, eksik gerçek borsa fiyatlarının tamamlandığını göstermez.** Mevcut dört piyasa panelinde gerçek veriler olmadan bilinmeyen kapsam korunur. Yeni çalışma, daha önce gelişmiş fakat eski stack'e girmemiş KAP/BIST kod dosyalarını tek inceleme adımına getirir.

**Taslak / NO MERGE / NO RELEASE / NO PAPER / NO LIVE TRADING.**
