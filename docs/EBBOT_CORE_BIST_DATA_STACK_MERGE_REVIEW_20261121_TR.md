# EBBot — PR188 çekirdek + PR203 BIST paneli + PR201 güncel veri güvenliği entegrasyonu

## Yalnız taslak, main'e birleştirilmedi

21 Kasım 2026 entegrasyon dalı, üç ayrı dalın **mevcut güncel GitHub commitlerini** kaynak alır:

- Çekirdek/Windows/Türkçe/güvenlik ve 1.530 test kimliği: PR #188 `b0eb3405e42acb464a5b0d517f09d3b32e7856a7` (ana ebeveyn).
- BIST admin-only KAP/XIST rapor API ve Veri Merkezi React paneli: PR #203 `a630189a48f473e26684c1a577c2e6f984903905` (ikinci ebeveyn).
- Güncel KAP 8 pazar, KAP→BIST işlem kodu/ISIN, gerçek ham-bayt Xetra checksum ve provider/seans düzeltmeleri: PR #201 `ed0e067034dccf5b15ca285bfa713d5539a511d1` (üçüncü ebeveyn).

### Gerçek dosya birleştirme kararları

- `main` dalına karşı iki kaynak dalın değişen blob yolları eksiksiz Git tree envanterinden kontrol edildi; çakışan **tek** dosya `api/v1/endpoints/data.py` oldu.
- Bu dosyada çekirdeğin `GET /tr-market-overview` Türkçe gecikmeli piyasa özeti ve BIST taslağının **iki ayrı yönetici güvenliği şartlı**, `Cache-Control: no-store` taşıyan `GET /equity-coverage` ile `GET /bist-identity` uç noktaları korunmuştur. İsim/parametre veya rota çakışması yok; bağımsız auth davranışı için test zorunludur.
- #203 dalı, #201'in sonradan eklenen 11 dosyalık güvenlik yamasından **önce** ayrılmıştı. 11 değişen yol, #203'te eski #201 ile aynı blob olduğundan **en yeni #201 blobu** ile değiştirildi; bu seçim çakışma bastırması değildir.
- Diğer #203 veri paneli, yerel CSV staging, kimlik doğrulama ve veri hazırlık dosyaları kendi blob kimlikleriyle taşınmıştır.

### Kırmızıysa gevşetilmeyecek kapılar

- `EBBot required gate / all offline acceptance checks` dâhil tam backend + React 0 skip + TypeScript/Vite/ESLint + gerçek Windows PyInstaller/NSIS.
- **1.530 React exact testcase kimlik SHA** yeni React testleri nedeniyle değişirse, eski sabit hash otomatik gevşetilmez. CI JUnit artifact karşılaştırması, eklenen/çıkan test adlarının semantik incelemesi ve yeni kimliğin onayı gerekir.
- BIST/KAP/XIST köken, ISIN, fiyat sağlayıcı/broker sembolü, veri lisansı, OHLCV/seans ve gerçek Türkiye piyasa erişimi **doğrulanmadı**. Bir CSV dosyasında 'resmî' etiketi veya SHA bulunması gerçek kaynak doğrulaması değildir.
- `main` koruması (Issue #183), bağımsız reviewer (Issue #195), gerçek veri kaynağı (Issue #197) hâlâ zorunlu engellerdir.

**Her koşulda DRAFT / NO MAIN MERGE / NO RELEASE / NO INSTALLER RUN / NO SCHEDULER / NO AUTO TRADING / NO PAPER/LIVE BROKER ORDER.**

Bu belge CI sonucu değildir. Son HEAD CI sonuçları ayrıca kanıtlanıp kaydedilmelidir.