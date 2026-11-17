# EBBot — Kripto Trading Merkezi, Aşama 4 / İlk güvenli entegrasyon

Bu modül yalnızca EBBot kripto alanını değiştirir. Dört hisse piyasası,
mevcut hisse analizleri ve Haberler sistemine ait servis mantığı korunur.

## Geliştirmeye alınan ilk parça

Özel `ai-multi-market-trading-office` ZIP'indeki
`integrations/daily_stock_analysis` paketi incelendi.
Doğrudan ZIP kopyalama yapılmadı: EBBot'a izole, küçük bir
salt-okunur bağlantı uygulandı.

- EBBot route: `GET /api/v1/crypto-office/dashboard`
- Kaynak route: `GET /api/v1/integration/dashboard`
- Beklenen sözleşme: `schema_version=1.1`, `mode=paper_only`
- Güvenlik bayrakları: `real_exchange_orders=false`, `live_trading_enabled=false`
- Zorunlu alanlar: application, portfolio, risk, performance, validation,
  agents, strategies, operations, safety
- 24 saatten eski veya 5 dakikadan fazla gelecek zaman damgalı veri reddedilir.
- Eksik toplam portföy fiyatında `valuation_complete=false` ve `equity=null`
  zorunludur; eksik fiyat sıfır görünmez.
- Gizli anahtar benzeri alan veya değer varsa rapor tamamen reddedilir.
- Maksimum upstream JSON 2 MB. Yanlış content-type, redirect, HTTP hatası
  ve bozuk JSON güvenli 502 hatası üretir.
- EBBot yöneticisi etkin değilse 403, geçerli oturum çerezi yoksa 401.
- Yalnız localhost/127.0.0.1/::1 üzerindeki sabit HTTP endpoint kabul edilir.
  Phase 1'de HTTP ile uzak ağ servisine proxy yapılmaz.
- Anahtar yalnız EBBot backend ortam değişkeninde; React bundle'ında yok.
- Yeni UI 15 bölümlü navigasyon taşır; doğrulanmamış işlemler kapalıdır.

## EBBot açılış ayarları (yerel Windows, ayrı iki servis)

1. Önce EBBot uygulamasında yönetici kimlik doğrulamasını etkinleştirin
   (`ADMIN_AUTH_ENABLED=true`) ve yönetici parolasını oluşturup giriş yapın.
   Güvenlik nedeniyle bu crypto endpoint'i auth kapalıyken çalışmaz.
2. Trading Office ZIP'ini güvenilir yerel klasöre çıkarın.
3. Trading Office backend'inde `backend/requirements.txt` bağımlılıklarını
   kurun. Bu ilk entegrasyon dış servis kodunu çalıştırmadan da dağıtılabilir;
   ancak gerçek veriler için Trading Office sunucusunun çalışması gerekir.
4. Trading Office için birbirinden FARKLI, 32+ karakterlik iki rastgele
   `READ_API_KEY` ve `ADMIN_API_KEY` oluşturun. Üçüncü tarafla paylaşmayın.
5. Trading Office backend sunucusu yerel 127.0.0.1:8001 portunda açılmalı.
   Ortam değişkenleri:

       APP_ENV=production
       API_AUTH_ENABLED=true
       TRADING_ENABLED=false
       READ_API_KEY=<secret-1>
       ADMIN_API_KEY=<secret-2>

   `backend` klasöründe örnek başlatma:

       python -m uvicorn app.main:app --host 127.0.0.1 --port 8001

6. EBBot FastAPI sunucusunun **kendi** ortamına:

       TRADING_ENABLED=false
       TRADING_OFFICE_URL=http://127.0.0.1:8001
       TRADING_OFFICE_READ_API_KEY=<ayni-secret-1>

   EBBot ve Trading Office için ayrı secret tutun. API anahtarı hiçbir
   kaynak dosyaya veya tarayıcı yerel depolamasına yazılmamalı.
7. EBBot sunucusunu yeniden başlatın ve oturum açın.
   Kripto ekranı: `http://localhost:5173/crypto-trading`.

**Not:** Docker kullanıyorsanız bu ilk sürüm sadece host loopback
adresini kabul eder. Ayrı container'lar arasındaki ağ bağlantısı için
TLS + açık allowlist + özel ağ denetimi sonraki aşamada hazırlanmalıdır.

## Bu aşamada çalışan ve çalışmayan alanlar

**Kod bağlantıları mevcut (canlı doğrulama bekliyor):** EBBot menüsünde
Kripto Trading, 15 başlıklı bölüm navigasyonu; birleşik Paper özsermaye,
ayrı Spot/Futures sanal hesaplarının salt-okunur durumu, açık pozisyonlar,
ajan ağırlıkları, risk, performans ve operasyon metrikleri.

**Henüz EBBot'a bağlanmadı:** Binance Spot/Futures canlı veri sekmeleri,
manuel AI sinyal feed'i, piyasa tarayıcı, işlem geçmişi, kripto backtest
başlatma, emir simülasyonu açma/kapatma, WebSocket doğrudan gösterimi.
Bu alanlar için UI gerçek olmayan veri veya sonuç üretmez.

## Kontroller

    cd C:\Users\Thebo\Projects\ebbotcyber-test
    git switch feat/turkish-ui-hk-latin-display
    git fetch origin
    git merge --ff-only origin/feat/turkish-ui-hk-latin-display
    & .\.venv\Scripts\python.exe -m unittest discover -s tests -p test_crypto_office_bridge.py -v

    cd apps\dsa-web
    npm.cmd run test -- src/api/cryptoOffice.test.ts src/pages/CryptoTradingPage.test.tsx
    npm.cmd run build

İkinci aşamaya geçmeden bu testlerin başarılı olması, canlı dashboard
sözleşme doğrulaması, kimlik doğrulama, gizli anahtar sızıntısı, kayıp
fiyat ve hisse regresyon testleri kontrol edilmelidir.

**Proje güvenliği:** Gerçek borsa emirleri, gerçek bakiye okuma, para transferi
ve çekme için hiçbir API yazılmadı. Paper işlem motoru bu aşamada salt okunurdur.
