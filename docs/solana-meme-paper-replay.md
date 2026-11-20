# Solana Meme Radar — Sanal İşlem Testi (Aşama 1)

Bu aşama **gerçek para veya gerçek emir kullanmaz**. GitHub Actions'da iki strateji için üretilmiş (**sentetik**, tarihsel olmayan) fiyat serileriyle muhasebe ve risk simülasyonu yapılır. Kod, EBBot'un mevcut `evaluate()` sinyallerini kullanır; GoPlus verileri örnek olarak tanımlanmıştır. İşlem kaydı, maliyet ve fiyat dizisi hayalî olduğu için **kârlılık başarısı veya piyasada doğrulanmış bir backtest değildir.**

## Simülasyon kuralları

- Başlangıç: **1.000 USD** hayalî bütçe.
- Tek coinde ve strateji başına **en fazla 1 sanal pozisyon**, nakdin **%10'u** büyüklüğünde.
- Her iki tarafta varsayımsal **%0,30 komisyon** (30 baz puan) ve **%0,75 fiyat kayması** (75 baz puan).
- Stop-loss: masraflar dahil yaklaşık **-%8**, hedef: **+%15**. Bir gözlemde oluşan sinyal, **bir sonraki gözlemin fiyatından** gerçekleşir; zararı tam stop noktasında durdurmayı garanti etmez.
- Güncel risk bayrakları eksikse veya `blocked` ise **alım yok**. Açık pozisyonun risk durumu bozulursa satış, bir sonraki fiyat gözleminde simüle edilir.
- Son gözlemde açık pozisyon otomatik satılmış gibi yazılmaz; sadece yaklaşık tasfiye değeriyle işaretlenir. Açık kâr/zarar **gerçekleşmiş P&L değildir**.
- İşleme giriş ve çıkış için gelecekteki fiyatlar sinyal anında kullanılmaz. Simülasyon; gerçek spread, fiyat etkisi, MEV, ağ arızaları, gas, cüzdan ücretleri, likidite kayması veya alım-satım olanaklarının tamamını modellemez.

## GitHub üzerinden test

GitHub → **Actions** → **Solana synthetic paper replay (no orders)** → **Run workflow** (`main`).

Bu elle tetiklenen iş akışı zamanlanmaz. PR'da ilgili test kodu değiştiğinde de bir kez doğrulama yapar. İki senaryoyu çalıştırır: yapay fiyat yükselişi ve sert düşüş. Her senaryo için iki strateji ayrı raporlanır. Test dosyaları:

- `tests/fixtures/solana_paper_synthetic_up.json`
- `tests/fixtures/solana_paper_synthetic_down.json`

Sonuçlar GitHub Actions içinden **solana-synthetic-paper-replay-only** adıyla 7 gün saklanan dosyalara kaydedilir. Rapor JSON'unda `data_origin=synthetic`, `trading_enabled=false` ve `external_network_requests=0` etiketleri bulunur. Çalıştırma için sunucu, VPS, borsa hesabı, cüzdan veya API anahtarı gerekmez.

Yerel eşdeğer komutlar:

```bash
python -m pytest -q tests/test_solana_paper_replay.py tests/test_solana_meme_paper_integration.py
python -m scripts.solana_meme_paper_replay --fixture tests/fixtures/solana_paper_synthetic_up.json
python -m scripts.solana_meme_paper_replay --fixture tests/fixtures/solana_paper_synthetic_down.json
```

## Gerçek performans için sonraki şartlar

Tek anlık gerçek Solana taraması tarihsel fiyat serisi değildir. Gerçek geçmişe dönük test yapabilmek için **zaman damgalı, kaynak bilgisi doğrulanabilir, ayrı zamanlarda alınmış fiyat ve risk snapshot'ları** gerekir. Ayrıca veri eksiklikleri, diğer masraflar, likidite ve işlem gerçekleşme olasılığı ölçülmelidir. Yeterli veri oluşmadan **başarı oranı, geçmiş getiri veya kendi kendine öğrenme** iddiasında bulunulmamalıdır.

Sanal/gerçek emir gönderme, cüzdan bağlama, zamanlı otomatik tarama ve gerçek işlem **kapalıdır**.
