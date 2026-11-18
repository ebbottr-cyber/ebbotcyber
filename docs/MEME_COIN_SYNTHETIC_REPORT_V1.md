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
