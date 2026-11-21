# EBBot Beyaz Panel + Meme Coin V2 entegrasyonu

Bu dal `feat/ebbot-white-dashboard-v1` üzerine `feat/meme-coin-discovery-v2` kodlarını güvenli şekilde yerleştirir. Meme Coin kaynağı son aktarılan commit: `d1e698b6d349892689b2343bf44e0b5aaabd2ba7`. Bu bir **anlık görüntüdür**: diğer konuşmada Meme Coin kodu değişmeye devam ederse yeniden karşılaştırılmalıdır.

## Ekranlar

- `/overview`: beyaz piyasa özeti, hisse mum grafiği, teknik göstergeler, portföy, risk ve AI görevleri.
- `/`: eski ayrıntılı hisse analiz çalışma alanı **korunur**.
- `/meme-coins`: Solana **Yeni Coin Avcısı** (`new_launch`) ile **Momentum Avcısı** (`momentum`), iki bağımsız araştırma stratejisi.
- Masaüstü/çekmece menüsüne ve beyaz paneldeki mobil 5'li alt menüye Meme Coin bağlantısı eklendi. `/overview` için üst başlık Türkçeleştirildi.
- Mevcut `/portfolio`, `/alerts`, `/decision-signals`, `/data` ve diğer rotalar korunur.

## Veri ve işlem güvenliği

- Meme Coin API'si yalnızca `GET /api/v1/meme-coins/overview` ve `GET /api/v1/meme-coins/candidates?strategy=...` sağlar.
- Meme Coin keşfi **varsayılan kapalıdır** (`MEME_COIN_DISCOVERY_ENABLED=false`); açılırsa sadece araştırma amaçlı GeckoTerminal verisi okunur. Taramalar yalnızca butona basıldığında çalışır.
- Her aday `risk_status=unverified` ve `tradable=false`. Sözleşme/otorite, holder, satılabilirlik doğrulaması ve gerçek veya sanal emir motoru **yoktur**.
- Mevcut Solana Hype stratejisine, cüzdan erişimine, hisse yatırım motoruna veya emir API'lerine dokunulmadı.
- PWA yalnızca kamuya açık çevrimdışı ekranı önbelleğe alır; kimlik doğrulama ve finans verilerini saklamaz.
- Meme Coin için gerçek para ile işlem açılmaz; riski/performansı uyduran kart yoktur.
- **Yayına alınmadı**. Entegrasyon PR'ı sadece `feat/ebbot-white-dashboard-v1` dalını hedefler; PWA ve beyaz panel PR'ları ayrı taslaklardır.

## Birleştirme ön koşulları

1. Entegrasyon CI: React/Vite, PWA, Meme Coin paneli, API şeması ve mobil gezinme testleri.
2. Gerçek sunucuda yönetici oturumuyla erişim; `ADMIN_AUTH_ENABLED` ve yetkilendirme kontrolleri doğrulanmalı.
3. Tam backend test takımındaki önceki başarısızlıklar değerlendirilmeden üretim dağıtımı yapılmamalı.
4. Gerçek iPhone ve Android üzerinde HTTPS PWA kurulum testi.
5. Ayrı Meme Coin dalındaki yeni commit'ler gelirse güncel dosya farkı ve güvenlik incelemesi.

## PWA kurulumundan açılan ilk sayfa
PWA manifest `id` ve `scope` alanları `/` olarak korunur. `start_url`, yalnızca entegrasyon test dalında `/overview` olacak biçimde ayarlanmıştır; bu nedenle uygulama simgesi beyaz Piyasa Özeti'ni açar. Tarayıcıdaki `/` ayrıntılı hisse analiz ekranı aynı kalır. iOS/Android gerçek cihaz davranışı ayrıca doğrulanmalıdır.

## Türkçe rapor yayın engeli düzeltmesi
- `get_market_role` ve `get_market_guidelines` işlevlerinde Türkçe çıktı modu artık İngilizce finansal piyasa çerçevesi üzerinden çalışır. AAPL/ABD hissesine Çince pazar açıklaması eklenmez.
- Bildirim kaynak adlarında Türkçe/Korece için İngilizce kaynak etiketi kullanılır; `KeyError` ile rapor oluşturma kesilmez.
- Türkçe boş haber kanıtı uyarıları mevcut desteklenen dil test sözlüğüne eklendi ve gerçek şablon çıktıları denetlenir.
- Entegrasyon CI'ına ilgili iki Python regresyon testi eklendi. **Bu düzeltmeler genel backend testlerinin tamamının geçtiği anlamına gelmez.**
- Eski `.env.example`, `.github/workflows/ci.yml` ve `.github/workflows/00-daily-analysis.yml` yoklukları hâlâ yayın engelidir. Bu dosyalar gerçek üretim sözleşmeleri doğrulanmadan uydurma içerikle oluşturulmayacaktır.
