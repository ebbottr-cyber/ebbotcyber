# EBBot — Kalıcı sentetik senaryo günlüğü (52. aşama)

Bu modül **yalnızca araştırma/test** içindir. Gerçek coin adresi, mum verisi,
cüzdan, emir, API endpoint, scheduler veya gerçek borsa bağlantısı içermez.
Önceki `src/services/meme_coin_synthetic_journal.py` modülündeki örnek
verileri, açıkça etkinleştirilmiş ve yolu kullanıcı tarafından seçilmiş bir
SQLite `.sqlite3` dosyasında tutar.

## Güvenlik sınırları

- Her API için `enabled=False` varsayılan. Etkin değilken dosya oluşturmaz.
- Dosya yolu açıkça verilmek zorunda; uygulama varsayılan kayıt dizini yoktur.
- SQLite `BEGIN IMMEDIATE` ile farklı yazıcılar sıralanır, **tek transaction**
  içinde ekleme yapılır ve `synchronous=FULL` kullanılır.
- Her `event_id` tekildir: aynı içerik tekrar gelirse sayılmaz; aynı kimlikte
  değişmiş içerik reddedilir. Toplam 200 örnek olay sınırı vardır.
- Her kayıt önceki SHA-256 özetiyle bağlıdır. Başlatıldığında her kayıt ve
  kurallar yeniden doğrulanır. Zincir, rastgele veri bozulmasını saptamaya
  yardımcı olur, fakat **kötü niyetli değişikliklere karşı imzalı/ağır
  güvenlikli denetim kaydı değildir**.
- İki strateji tek DB içinde ayrı günlüklerdir; toplam zarar bütçesi
  stratejiler arasında ortaktır.
- Manuel durdurma anahtarı dosyaya yazılarak kalıcı hale getirilir. Bu
  prototipte programatik tekrar açma yoktur; yeni test için yeni dosya gerekir.
- Sentetik PnL asla gerçek alım-satım performansı veya hesap bakiyesi değildir.
  Panelin mevcut canlı verilerini ve eski Solana Hype modülünü değiştirmez.

## Geliştirici testi

```bash
python -m pytest -q tests/test_meme_coin_persistent_journal.py
```

Temel fonksiyonlar:

- `append_synthetic_scenario(database_path=..., starting_equity_usd=...,
  event=..., enabled=True)`
- `read_synthetic_scenarios(database_path=..., starting_equity_usd=...,
  enabled=True)`
- `latch_synthetic_kill_switch(database_path=..., starting_equity_usd=...,
  enabled=True)`

Bu fonksiyonlar uygulamanın API yönlendiricisine bağlanmamıştır. Hiçbir
sunucu veya zamanlanmış iş tarafından otomatik çağrılmaz. SQLite yazımı
yalnızca yerel testlerde `tmp_path` altındadır.

## Sonraki yayın engelleri

Ağ kaynaklarından gelen verinin bağımsız doğrulanması, yetkilendirme, gerçek
P&L mutabakatı, çökme/sunucu kesintisi kurtarma, imzalı/kopyalı denetim
kayıtları, yedeklemeler, veri lisansları ve cihaz üstü testler tamamlanmadan
gerçek paper broker veya canlı emir motoru etkinleştirilmez.
