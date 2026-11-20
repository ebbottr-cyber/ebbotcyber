# EBBot — GitHub'da gerçek Solana fiyat gözlemleri

Bu sürümün amacı, **aynı Solana coinlerinin** fiyatını üç ayrı anda kaydetmektir. GitHub'ın geçici runner'ı üzerinde yapılan tek seferlik, salt-okunur denemedir. **Cüzdan, gerçek emir, sanal emir, otomatik strateji öğrenmesi veya zamanlanmış iş yoktur.**

## Test nasıl yapılır?

GitHub → **Actions** → **Solana fixed-mint time-spaced observations (read only)** → **Run workflow** → **main**. İlk sürüm PR'ında bu workflow, yalnızca ilgili dosyaları doğrulamak için bir defalık PR tetiklemesiyle de çalışır.

- Başlangıçta GeckoTerminal (yeni havuz) ve DEX Screener (güncel token profilleri) ile en fazla **2 farklı Solana mint adresi** seçilir.
- Bu adresler test boyunca sabit kalır. 60 saniyelik aralıklarla 3 ayrı gözlem yapılır (2 dakika boyunca, dış API gecikmeleri hariç).
- Önce DEX Screener'dan aynı mint adresleri sorgulanır. İlk kez GeckoTerminal'de keşfedilmiş bir token DEX Screener'da henüz yoksa yalnızca **o tokenın ilk keşfedilen GeckoTerminal havuzu** sorgulanır. Havuz kimliği ve base mint tam eşleşmezse veri kabul edilmez. Her kayıtta keşif ve fiyat kaynağı ayrı yazılır; iki farklı havuz aynıymış gibi gösterilmez.
- Her gözlemde GoPlus risk kontrolü yeniden sorgulanır. Bilgi eksikse mevcut EBBot risk motoru sonucu engeller; güvenli kabul edilmez.
- Fiyat, likidite, hacim, beş dakikalık alım-satım sayıları, gözlem zaman damgası ve iki stratejinin izleme/engelleme nedeni kaydedilir.
- Başarısız veya eksik fiyatlar için uydurma 0 USD fiyat konmaz; `missing_price` olarak işaretlenir. Ağ hataları `degraded` sonucuna dönüşür.

## Sonuç nereye kaydediliyor?

GitHub Actions çalıştırmasının **Artifacts** bölümünde `solana-public-observations-not-paper-trades` isimli JSON arşivinde saklanır (**7 gün**). Veri tek çalıştırma içindir: GitHub Actions kendi başına kalıcı 7/24 veri toplayan bir sunucu değildir. Arşiv başka bir çalıştırmanın verisiyle otomatik birleştirilmez.

JSON açıkça şunları söyler:

- `data_origin=live_public_api_not_historical` — kamuya açık fiyat sorguları; doğrulanmış tarihsel OHLCV değildir.
- `performance_calculated=false` — başarı oranı veya kazanç kaybı hesaplanmadı.
- `trading_enabled=false`, `wallet_enabled=false`, `background_schedule_enabled=false` — alım-satım veya otomasyon yapılmadı.

Üç ayrı zaman örneği, likiditeyi veya gerçek fill fiyatını doğrulamak için yeterli değildir. Zaman damgası, API yanıtının alındığı zamandır; borsadaki işlemin tam gerçekleşme zamanı değildir. Gecikmeler, farklı havuzlar, GoPlus sınırlamaları ve API kotası sonuçları etkiler. Veriler GitHub runner'ın ağ bölgesinden alınır; Türkiye'de erişim garantisi değildir.

## Gelecek aşama

Yeterli süre ve sayıda gerçek fiyat/risk snapshot'ı olmadan herhangi bir gerçek piyasa kâr oranı, tarihsel başarı veya öğrenme iddiasında bulunulmamalıdır. İlk örnekler incelenip veri kalitesi doğrulanınca, ayrı bir güvenli offline gerçek-veri replay içe aktarma tasarlanabilir.

Komutlar:

```bash
python -m pytest -q tests/test_solana_observations.py
python -m scripts.collect_solana_observations --live --rounds 3 --interval 60 --limit 2
```

`--live` yoksa ağ bağlantısı ve veri toplama yapılmaz.
