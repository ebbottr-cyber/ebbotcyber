# EBBot Veri Merkezi — KAP / BIST (XIST) kimlik ve fiyat dosyası eksikliği

**Durum:** Salt-okunur taslak. Gerçek/sanal emir, otomatik piyasa veri indirme ve yayın kapalı. Bu özellik gerçek BIST kotasyonu veya veri lisansı doğrulaması değildir.

## Panel

Veri Merkezi'ndeki dört piyasa envanterinin altına **BIST · KAP ve işlem kaydı eşleştirmesi** bölümü eklenir. Bu bölüm yalnızca, PR #202'nin operatör bilgisayarında önceden oluşturduğu BIST kimlik denetim JSON raporunun güvenli özetini gösterir.

Görüntülenen alanlar: KAP şirket adayı, ayrı BIST XIST referansı, aktif olarak beyan edilmiş kayıt, işlem durdurulmuş/kotasyondan çıkarılmış kayıt, KAP ile eşleşen aktif, iki liste arasındaki farklar, aktif ama fiyat sağlayıcısı kodu eşleşmemiş, **yalnız denetime verilen dosyada** OHLCV bulunan ve bulunmayan kayıt.

**Kritik:** KAP veya gerçek BIST referans dosyası mevcut değilse hiçbir hisse sayısı **0 olarak uydurulmaz**. Panel 'bilinmiyor' gösterir. Fiyat dosyası verilmediyse fiyat bulunan/eksik sayıları boş (`—`) gösterilir. Çelişkili, bozuk, sahte olumlu bayrak taşıyan veya 7 günü aşmış raporlar geçersiz/eskimiş olarak işaretlenir.

## Yerel kullanım

1. PR #202'de belgelenen gerçek, ayrı kaynaktan elde edilmiş KAP ve BIST XIST referanslarını hazırlayın. Sağlayıcı ile OHLCV dosyaları isteğe bağlıdır. **KAP listesini BIST işlem kaydı olarak kopyalamayın.**
2. EBBot repo kökünden yerel, henüz bulunmayan bir JSON rapor dosyası üretin:

```powershell
python -m scripts.audit_ebbot_bist_reference_identity --kap "$HOME\EBBotPaperData\kap-bist-all.csv" --exchange "C:\ApprovedMarketData\bist-xist-equities.csv" --mapping "C:\ApprovedMarketData\tr-provider-symbols.csv" --bars "C:\ApprovedMarketData\staged-tr-ohlcv.csv" --report-json "C:\ApprovedMarketData\bist-identity-summary.json"
```

3. Sadece BIST denetiminin API tarafından okunmasını istediğiniz yerel backend terminaline sabit dosya konumunu tanıtın:

```powershell
$env:EBBOT_BIST_IDENTITY_REPORT_PATH="C:\ApprovedMarketData\bist-identity-summary.json"
```

4. EBBot backend'i bu ayarla başlatın ve **yönetici kimlik doğrulamasını açık tutun**. Veri Merkezi sayfasında BIST panelini açın.

`GET /api/v1/data/bist-identity` isteği, istemciden **dosya yolu veya fiyat kaynağı parametresi kabul etmez**. Yanıt yalnızca sınırlı sayısal toplamlar, tarih ve 'eksik/eskimiş' durumu içerir. Rapordaki kodlar, ISIN'ler, fiyat değerleri ve yerel dosya yolu gönderilmez. `Cache-Control: no-store` kullanılır. Admin auth kapalıysa yerel dosya hiç okunmaz ve veri kapalı tutulur. Yetkisiz oturum HTTP 401 alır.

## Sınırlar

- `active` durumu operatörün dışarıdan sağladığı ayrı listedeki **beyan edilmiş** durumdur; canlı borsa eşleştirmesi değildir. Geçerli ISIN checksum'ı menkul kıymet kimliği sertifikası değildir.
- Ham BIST/KAP referansları, sözleşme belgeleri ve lisanslı OHLCV dosyaları herkese açık GitHub'a yüklenmemelidir. Bu PR gerçek kullanıcı dosyasını, aboneliğini veya fiyatını sağlamaz.
- Rapor 4 MiB sınırında, mutlak yerel dosya yolunda ve sembol listesi sayılarıyla tutarlı olmalıdır. Eski/tutarsız kayıtlar güvenli kapanır.
- **İki panelin sayıları birebir aynı olmak zorunda değildir:** dört piyasa paneli eski envanter adaylarını sayar; BIST kimlik paneli ise ayrıca temin edilen gerçek tarihli KAP ve XIST referanslarını karşılaştırır.
- Gerçek lisans, borsa aktiflik durumu, kurumsal aksiyon, fiyat sembolü, seans takvimi, Türkiye'deki aracı kurum hakkı ve Windows dağıtımı ayrı onay gerektirir.
- Bu PR önceki taslaklar üzerine kuruludur, `main`e birleştirilmedi. Gerçek ve sanal emirler kapalıdır.

## Testler

```powershell
python -m unittest discover -s tests -p test_bist_identity_report_reader.py -v
python -m unittest discover -s tests -p test_bist_identity_api_auth.py -v
cd apps/dsa-web
npm run test -- src/components/data-center/BistIdentityPanel.test.tsx
npm run lint
npm run build
```

**Yayın durumu: BLOKE.** Bu ekran yalnız kanıtların izlenmesini sağlar, kaynağın tamamlandığını veya canlı işlem yapılabileceğini iddia etmez.
