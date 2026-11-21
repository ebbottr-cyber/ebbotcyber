# EBBot — Veri Merkezi Hisse Veri Kapsamı (taslak)

Bu entegrasyon piyasalardan otomatik fiyat indirmez, botu canlıya çıkarmaz ve emir açmaz. Önceki dört-piyasa eksiklik denetiminin (PR #194) hazırladığı yerel JSON raporunu Veri Merkezi ekranında özetler.

## Nerede görünür?

Paneldeki Veri Merkezi sayfasına **Hisse veri eksiksizliği** bölümü eklendi. BIST, ABD, Xetra ve Hong Kong için ayrı satırlarda aday envanter, OHLCV kanıtı bulunan kayıt, yetersiz geçmiş, OHLCV eksikliği ve eski fiyat mumu sayıları gösterilir. Panel rapor yoksa **0 yazmak yerine rapor bulunmadığını** söyler. Yedi günden eski rapor için açık uyarı verir.

## Yerel kurulum

1. Önce gerçek, kaynak ve kullanım izni denetlenmiş OHLCV CSV dosyalarını ayrı denetime sunun. Sahte fiyat üretmeyin.
2. Önceki PR'ın denetim komutuyla eksik veri JSON raporunu yeni bir dosya olarak üretin:

```powershell
python -m scripts.audit_ebbot_market_data_coverage --report-json "$HOME\EBBotPaperData\ebbot-coverage.json"
```

3. Aynı bilgisayarda backend'i başlatan terminale geçerli dosya yolunu tanımlayın:

```powershell
$env:EBBOT_EQUITY_COVERAGE_REPORT_PATH="$HOME\EBBotPaperData\ebbot-coverage.json"
```

4. Backend'i bu ayar ile başlatın, Veri Merkezi'ni açın. API `GET /api/v1/data/equity-coverage` yalnızca sunucuda operatörün yapılandırdığı bu dosyayı okur. Kullanıcı istek üzerinden dosya yolu veremez.

Dosya mevcut değilse, bozuksa, güvenli olmayan bir yoldaysa, 8 MiB sınırını aşıyorsa veya sayılar tutarsızsa, servis bilinmeyen değerleri sıfır olarak tahmin etmeden `unavailable` durumu üretir.

API dışarıya tam hisse kodlarını, fiyatları veya dosya yolunu göndermez: yalnız dört piyasaya ait sayımlar ve tarih döner. Mevcut yönetici oturum koruması etkinleştirilmişse `/api/v1/` altında bu endpoint de korunur.

## Sınırlar ve birleştirme

- Bu PR, PR #194 üzerine yığılmış **taslak**; doğrudan `main`e birleştirilemez.
- `listing_completeness_verified=false` ve `licensed_ohlcv_verified=false` sabittir. Gerçek veya sanal işlemler kapalı.
- CSV'deki `source` etiketi lisans veya borsa üyelik onayı değildir.
- Binance, Solana, Futures fiyatları bu hisse raporundan ayrı kalır.
- Windows paketlemesi, gerçek operatör verisiyle uçtan uca test, auth zorlamalı API testi ve bütün React/backend regresyonu ayrıca doğrulanmadan dağıtım yapılmaz.

## Salt-okunur test

```powershell
python -m unittest discover -s tests -p test_equity_data_coverage_reader.py -v
cd apps/dsa-web
npm ci
npm run test -- src/components/data-center/EquityCoveragePanel.test.tsx
npm run lint
npm run build
```

**Yayın: BLOKE.** Bu panel veri kanıtı gösterir, alım-satım yetkisi veya tam piyasa kapsama sertifikası vermez.
