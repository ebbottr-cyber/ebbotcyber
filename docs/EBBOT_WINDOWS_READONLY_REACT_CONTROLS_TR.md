# EBBot: Windows Electron React salt-okunur kontrolleri ve Türkçe tarama durumu

**YAYIN ENGELLİ / CI-ONLY.** PR #175'in doğruladığı Türkçe React paneline bir sonraki güvenli test katmanı eklenir. Bu test gerçek piyasa taraması, emir, analiz, zamanlayıcı veya ayar kaydetme işlemini başlatmaz.

## Gerçek Chromium renderer ile etkileşim sınaması

Sadece GitHub Windows runner, gerçek PyInstaller + NSIS `--publish never` çıktısı ve `EBBot.exe --ebbot-ci-ui-smoke` ile:

1. Gerçek Türkçe React kabuğu ve daha önce doğrulanan 6 rota test edilir.
2. `Kullanım` sayfasında başlangıçta `Ay` aralığı seçiliyken `Tümü` düğmesine tıklanır. React kontrolünden gelen `aria-pressed` değeri `Ay`: false, `Tümü`: true olmalıdır. Bu yalnızca gösterim dönemidir, GET dışında ağ işlemi yapılmaz.
3. `AI Önerileri` sayfasındaki **Eylem** (action) ve **Durum** (status) açılır menülerinin React kontrollü durumları, test amaçlı `buy` ve `expired` seçenekleriyle değiştirilir. İlk varsayılanlar `action=''` ve `status='active'` olmalıdır; ikinci değişiklik React render'ı tetikleyerek birincinin korunmasını da kontrol eder. **Filtrele/Gönder/Tarama/Emir düğmelerine basılmaz.**
4. Diğer Türkçe sayfa gezinmeleri ve başlık kontrolleri sürdürülür. İki etkileşim kontrolü hatalıysa Electron 42 koduyla çıkmaz, Python runner smoke testini başarısız sayar.

## Ağ ve API kilitleri

- Electron tanılamasında yalnız `GET` ve `HEAD` istekleri, `file:` veya tam `http://127.0.0.1:<port>` adresine izinlidir. `POST/PUT/PATCH/DELETE` yollarına Chromium seviyesinde izin verilmez.
- Frozen backend yalnız CI + açık test bayrakları ile paketli statik dosya, sahte GET auth durumunu ve GET `/api/health` servis eder. Gerçek portföy, config kaydetme, screening run ve alım-satım API rotaları yoktur.
- Test, dış ağdan gerçek veri çekmez; profil/veri dosyalarını düzenlemez, windows installer EXE dosyası Actions artefaktına yüklenmez. Sadece audit JSON.
- Otomatik güncelleme kapalıdır, gerçek ve sanal emirler **kapalıdır**.

## Kullanıcıya dönük küçük dil düzeltmeleri

- Hisse Tarama sayfasının **yükleme**, **etkin/kapalı/bilinmiyor**, **hata**, **tekrar dene** ve **etkinleştir** durum metinleri Türkçede gösterilir. Çince/İngilizce karşılıklar da çoklu dil sözlüğüne eklenerek mevcut dil seçenekleri korunur.
- Kullanım verisinde Türkçe sayı/tarih biçimlendirmesi `tr-TR` ile yapılır.
- Tüm ekranların tüm Çince/İngilizce metinlerinin çevrildiği iddia edilmez; yalnız belirtilen metinler düzeltilmiştir.

## Kabul kriterleri ve yayın blokajları

- [ ] GitHub Windows `push` gerçek paket job'unda ayrı `PASS: Usage period and AI signal dropdown filters updated...` kanıtı
- [ ] 56+ Electron unit / Windows source security ve ana backend/frontend regresyonu aynı commit SHA'sında tamamen başarılı
- [ ] CI dışında normal Electron başlangıç yolu değişmedi, herhangi bir `--publish` veya installer upload açılmadı
- [ ] Gerçek kullanıcı cihazı kurulum/kaldırma, veri göçü, kod imzalama, Defender/SmartScreen ve üretim API etkileşimleri ayrıca test edilecek

PR bu kanıtların tamamı görülmeden taslaktan çıkarılıp ana dala birleştirilmemelidir.
