# EBBot — 53. aşama: Yerel sentetik araştırma raporu

Bu özellik mevcut güvenli, salt-okunur Meme Coin paneline **yalnızca yerel
JSON dosyası** üzerinden bir sentetik araştırma özet kartı ekler. API
yönlendiricisi, ana panel performans metrikleri veya canlı veri akışına
bağlanmaz.

## Rapor oluşturma (geliştirici / yerel test)

Önce 52. aşamadaki açıkça seçilmiş .sqlite3 test günlüğü mevcut olmalıdır.
Aynı sanal başlangıç sermayesini kullanın:

```bash
python -m scripts.export_meme_coin_synthetic_report --database ./local/research.sqlite3 --equity 1000 --output ./local/report.json --confirm-synthetic-only
```

- Komut varsayılan olarak kapalıdır; `--confirm-synthetic-only` gerekir.
- Mevcut SQLite zinciri önce doğrulanır; tutarsız, değişmiş veya bozulmuş
  günlükler rapora çevrilmez.
- Hedef dosya zaten varsa üzerine yazılmaz. Kayıtlar varsayılan herhangi
  bir uzak servise gönderilmez.
- Rapor, `ebbot-synthetic-report-v1` sürümlü biçim, sentetik özetler, iki
  stratejinin ayrılmış varsayımsal metrikleri ve açık kapalı güvenlik bayrakları
  içerir.
- Hiçbir JSON alanı gerçek kazanç, işlem veya bağımsız doğrulanmış fiyat
  anlamına gelmez. Dosya biçimi kendi başına kriptografik kimlik doğrulaması
  sunmaz.

## Panel

`/meme-coins` sayfasındaki **Yerel sentetik test raporu** bölümünden
`report.json` dosyasını seçin. Dosya yalnızca tarayıcı belleğinde okunur;
sunucuya yükleme, fetch isteği, localStorage veya veri tabanı yazma
gerçekleşmez. Sayfa yenilenince rapor yeniden seçilmelidir.

İçerik bilinçli olarak yalnızca agregalara indirgenir; JSON içindeki
işlem kayıtları veya kullanıcı tanımlı HTML ekrana basılmaz. Desteklenmeyen,
değiştirilmiş, büyük (256 KiB üzeri) veya tehlikeli durum işaretleri olan
raporlar reddedilir. "Raporu kaldır" düğmesi geçerli görüntüyü temizler.

Görünen net PnL tamamen **sentetik**, gerçek cüzdan/gerçek piyasa sonuçları
ile kıyaslanmamalıdır.

## Testler

```bash
python -m pytest -q tests/test_meme_coin_report_export.py
cd apps/dsa-web
npm test -- syntheticReport.test.ts
npm run build
```

Bu iş kalıcı paper broker başlatmaz; gerçek piyasa kaynakları, saklama
servisleri, finansal hareket veya yayına alma halen bloke.

## 54. aşama: Görüntüleyici veri mutabakatı

- İçe aktarılan her sentetik işlem kaydı beklenen şemaya ve `trade_executed=false`, `realized_performance=false` işaretlerine uymalıdır.
- Tekil olay ID'leri, tarih geçerliliği, strateji izolasyonu, kayıt/başarı/kayıp sayıları ve günlük brüt kayıp toplamları birbirleriyle tutarlı olmalıdır.
- Parasal tutarlar JavaScript kayan noktalı aritmetiği yerine tam sent değerinde `BigInt` ile karşılaştırılır. İki stratejinin PnL toplamı hesap PnL'sine; başlangıç bakiyesi + PnL bitiş bakiyesine eşit değilse dosya reddedilir.
- Panelde iki ayrı stratejinin sentetik kazanma oranı, yalnızca doğrulanmış yerel dosyadaki işaretli senaryolar üzerinden hesaplanır. Gerçek başarı oranı, gerçek işlem kalitesi veya tahmini fiyat başarısı değildir.
- Raporun kaynak kimliği ve değiştirilmezliği yine **kanıtlanmaz**: kullanıcı kontrolündeki bir JSON dosyası bilinçli olarak sahte, kendi içinde tutarlı sayılarla hazırlanabilir. Zincir/özetin doğruluğu için güvenilir, bağımsız imzalı provenance gerekir.

## 55. aşama: Zaman içinde sentetik strateji karşılaştırması

- Her iki stratejinin yerel ve doğrulanmış **sentetik** kayıtları yalnızca tarih bazında toplanır; gün içi mark-to-market veya gerçek piyasaya ait mum/fiyat akışı **yoktur**.
- Her günün sentetik net PnL'si, birikimli PnL'si ve örnek kapatılmış senaryo adedi bellekte hesaplanır. Sadece kayıt bulunan günler listelenir; tarih boşlukları işlem yok olarak geçer.
- Günlük kapanış bazlı **varsayımsal maksimum düşüş** (önceki birikimli PnL zirvesi ile sonradan gelen en düşük PnL arasındaki USD farkı) Yeni Coin Avcısı, Momentum Avcısı ve ortak görünüm için ayrı hesaplanır. Bu rakam *gerçek drawdown, risk/sermaye yeterliliği ölçümü veya geleceğe dönük tahmin değildir*.
- Bütün tutarlar `BigInt` ile kuruş hassasiyetinde hesaplanır. Ham işlem kaydı, coin adresi, cüzdan adresi veya API verisi arayüze taşınmaz. Varsayımsal bir stratejinin üstünlüğünü veya kazanç garantisini çıkarmaz.
- Örnek sayısı sıfırsa çizelge boş, sentetik kazanma oranı belirsiz kalır. Tüm veri tarayıcı oturumunda yalnızca açık dosya seçiminden sonra görünür; API, canlı emir, otomatik sorgu ve tarayıcı deposuna yazma eklenmez.
