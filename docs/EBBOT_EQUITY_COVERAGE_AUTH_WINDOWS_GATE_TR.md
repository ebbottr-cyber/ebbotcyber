# EBBot — Veri Merkezi güvenli oturum ve Windows paket kontrolü (inceleme)

Bu değişiklik [PR #196](https://github.com/ebbottr-cyber/ebbotcyber/pull/196) üzerine eklenmiştir. **Taslak / hiçbir otomatik birleşim, dağıtım, paper veya canlı işlem yoktur.**

## Gerçek güvenlik açığı

Mevcut EBBot yönetici girişi opsiyoneldir: `ADMIN_AUTH_ENABLED=false` iken `/api/v1/*` oturum middleware'i istekleri geçirir. Yeni kapsam raporu ise operatörün cihazındaki bir JSON dosyasını kullanır. Bu nedenle rapor, yönetici kimlik doğrulaması kapalıyken **okunmamalıdır**.

- Bu PR, yalnızca `GET /api/v1/data/equity-coverage` endpoint'ine özel olarak yönetici kimlik doğrulaması kapalı ise raporun okunmasını engeller.
- Dönen durum `unavailable / administrator_auth_required` olur, piyasa sayısı `null`, liste boş kalır. React paneli Türkçe açık güvenlik açıklaması gösterir.
- Admin auth açıkken eksik/geçersiz çerez `401`; geçerli oturumda yalnız dört piyasanın toplulaştırılmış sayıları gelir. `Cache-Control: no-store` korunur.
- İstekte `path` veya başka bir dosya yolu gönderilmesi backend'in açıkça belirlediği `EBBOT_EQUITY_COVERAGE_REPORT_PATH` değişkenini değiştirmez. İstemci hisse kodları, tam fiyatlar veya yerel dosya yolunu okuyamaz.
- Yalnız `GET` kabul edilir; POST ile kapsam JSON'unun yazılması mümkün değildir.

## Windows kaynak sözleşmesi

`scripts/build-backend.ps1` artık PyInstaller için `api.v1.endpoints.data` ve `src.services.equity_data_coverage_reader` modüllerini açık gizli içe aktarma listesine ve paketlenmiş çalıştırılabilir dosyanın **yalnız import** kontrolüne ekler. Yalnız modülü import eder; rapor, API veya borsa erişimi başlatmaz.

CI-only frozen React health modu **gerçek API'yi kaydetmez** ve kapsam isteğinde `404` dönmeye devam etmelidir. Bu durum ayrı gerçek CI testine ve Windows kaynak sözleşmesine eklenmiştir.

## Otomatik test kapısı

- Gerçek FastAPI `TestClient` ve auth middleware'i üzerinden çerez, dosya yolu, kapalı-auth ve yalnız-okunur istek testleri
- Eski rapor okuyucusu testleri
- Frozen-health-only uygulama rotası `404` doğrulaması
- Windows Server 2022 üzerinde salt-okunur PyInstaller betik kontrolü (**gerçek NSIS kurulumu veya exe derlemesi değildir**)
- Türkçe React panel testleri, ESLint, TypeScript ve Vite üretim derlemesi

Gerçek PyInstaller / NSIS ve yüklenmiş gerçek kullanıcı cihazında test **ayrıca gereklidir**. Windows kaynak testlerinin yeşil olması bir kurulum paketinin gerçek Windows üzerinde çalıştığını kanıtlamaz.

Yönetici girişi EBBot'un mevcut güvenli yapılandırma talimatlarına göre açılmadan yerel veri kapsamı paneli kullanılamaz. Mevcut operasyonel kayıtların lisansı veya gerçek fiyat kaynağı bu PR ile sağlanmaz.

**Yayın, otomatik veri çekme, paper/live trading: KAPALI.**
