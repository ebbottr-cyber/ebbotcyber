# EBBot Türkçe Dil ve Para Birimi Denetimi — 19.11.2026

## Kapsam ve yöntem
Kaynak dal: `fix/turkish-ui-chat-20261118` / PR #63. Frontend sayfaları, bileşenler, Türkçe çeviri sözlüğü, portföy API ve hesaplama servisi incelendi. Bu bir **kaynak kod denetimidir**; yerel Windows paneli, tüm dinamik backend yanıtları ve dış kaynak verileri henüz uçtan uca doğrulanmadı.

## Dil bulguları
- `apps/dsa-web/src/i18n/uiText.ts`: 990 İngilizce anahtarın 400'ünde açık Türkçe karşılık mevcut; **590 anahtar** `...en` devralması nedeniyle Türkçe görünümde İngilizce çıkabilir. Önemli eksik gruplar: karar sinyalleri (202), akış diyagramı (94), takip listesi (70), ana sayfa (52), kullanım (33), hisse trendi (29).
- `StockScreeningPage.tsx`: 300 civarında Çince karakter içeren kaynak satır; birçok başlık ve etiket doğrudan Çince yazılmıştır. **Birincil kalan çeviri açığı.**
- `AlertsPage.tsx`: 36 civarında sabit Çince satır (test sonucu, bildirim denemeleri vb.). `AlertTriggerHistory.tsx` ayrı kontrol edilmeli.
- `PortfolioPage.tsx`: 120'yi aşkın Çince karakter içeren satır; bazıları bilinçli `zh` sözlüğü, bazıları ise sabit formlar, iş akışı ve silme mesajları.
- `MemeCoinPage.tsx`: 182 Çince karakterli satırın çoğu `CONTENT.zh` çevirisinde; TR sözlüğü mevcut olduğu için bu **doğrudan Türkçe hatası olarak sayılmamalı**.
- `StrategyLabPage.tsx`, `PaperJournalPanel.tsx` ve `SyntheticReportPanel.tsx`: doğrulanması gereken bazı Çince metinler veya çok dilli sözlükler.
- Ayarlar ve Hisse Asistanı'nın önceki düzeltmeleri PR #63'te; çalışmakta olan Windows paneline henüz dağıtılmamıştır.
- Teknik alan adları, dosya uzantıları, resmî model kimlikleri, ticker kodları, para birimi kodları (API düzeyinde) ve kullanıcıdan gelen metinler tercüme edilmemelidir.

## Para birimi bulguları — KRİTİK
1. `src/services/portfolio_service.py` içinde toplam portföy para birimi **CNY** olarak sabitlenmişti: `aggregate_currency = "CNY"`.
2. Aynı servis `_convert_amount` içinde FX yokken `(amount, True, "fallback_1_to_1")` döndürüyor. Bu güvenilir döviz dönüşümü değildir ve eşdeğer TL tutarı olarak gösterilmemelidir.
3. `apps/dsa-web/src/utils/portfolioFormat.ts` `formatMoney` varsayılanını CNY ve `zh-CN` kullanıyor.
4. Hesap/işlem kayıtlarının **kaynak para birimi** (CNY, USD vb.) korunmalıdır. Bunları API veya veritabanında tümden TRY yapmak gerçek defter tutarlarını bozar.
5. CNY'den TRY'ye dönüşüm için sadece USD/TRY yeterli değildir: `CNY * (USDTRY / USDCNY)`. USD için `USD * USDTRY`.
6. Yahoo Finance `USDTRY=X` ve `USDCNY=X` intraday veri gecikmeli/erişilemez olabilir. Kaynak ve veri zamanı belirtilmeli, broker gerçek işlem kuru olarak sunulmamalıdır.

## Bu PR kapsamındaki düzeltme
- `src/services/portfolio_display_fx.py`: iki bağımsız indikatif forex fiyatını getirir; en fazla 30 dakika yaşa ve 15 dakika farkına izin verir. Eşleşme olmazsa herhangi bir tutar tahmin etmez; 60 sn sunucu önbelleği vardır.
- `GET /api/v1/portfolio/fx/display-rates`: yalnızca **görüntüleme** amaçlı, salt-okunur.
- `portfolioTryDisplay.ts`: para birimi ve saat bilgisi doğrulanmadan TL tutarı göstermez. Kaynak defter/işlemleri değiştirmez.
- `PortfolioPage.tsx`: ana TL toplamını hesapların gerçek baz para biriminden tek tek çevirerek oluşturur; sahte CNY toplamasını kullanmaz. Eski veya eksik kurda `—` gösterir.
- Şu an yalnızca TRY/USD/CNY kaynağı destekleniyor. HKD, EUR, JPY, KRW, TWD vb. için **doğrulanmış kurlar eklenmeden** TL dönüşümü yapılmaz.
- Risk motorunun kendi `fallback_1_to_1` ve CNY toplaması **henüz temizlenmedi**. Bu nedenle diğer hesaplamalar ve iç raporların tümünün TL/güvenli olduğu iddia edilemez. Risk/performans raporlarına dokunmadan ayrı teknik düzeltme ve regresyon testi gerekir.
- Kur servisi doğru kur verdiğinde bile test ortamında dış bağlantı ve gerçek veri zamanı doğrulanmalıdır. Canlı broker alım-satımı açılmaz.

## Sonraki iş sırası
1. Hisse Tarama sabit Çince metinlerini `useUiLanguage` ve TR/EN/ZH sözlüğüne taşı.
2. Uyarılar ve Portföy işlem formlarını/yazılarını Türkçeleştir.
3. Kalan 590 `uiText.ts` devralınmış İngilizce anahtarı çevirmeyi parçalara bölerek bitir; yeni anahtarların TR karşılığını CI'da zorunlu kıl.
4. Kaynak para birimleri ve çoklu hesaplı risk/performans hesaplarında 1:1 fallback'i kaldırıp eksik FX'i açıkça `unavailable` olarak modellendir; ayrıca desteklenen para birimlerini genişlet.
5. Windows üzerinde yeni dalı ayrı test klasöründe çalıştırıp tüm sayfaları ve kur kaynak zamanı/30 dakika kuralını denetle.
