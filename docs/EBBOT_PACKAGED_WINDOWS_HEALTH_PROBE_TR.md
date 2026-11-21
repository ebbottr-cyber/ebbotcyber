# EBBot Windows: paketli backend için yalnızca yerel sağlık deneyi

**Durum: YAYIN ENGELLİ.** Bu PR; Windows gerçek PyInstaller/NSIS paketinin backend exe dosyasını sadece GitHub Windows 2022 runner'ında kısa süreli çalıştırarak **127.0.0.1 /api/health** yanıtını ölçer. Kurulum sihirbazı, Electron arayüzü, dağıtım, güncelleme, işlem ve piyasa taraması başlatılmaz.

## Neden ayrı bir tanılama modu?

Normal `main.py --serve-only` akışında varsayılan API yaşam döngüsü zamanlayıcı, arka planda hisse indeksi yenilemesi ve AkShare önbellek hazırlığı gibi yan etkiler içerebilir. Ayrıca GitHub Actions ortamında normal web server açılması mevcut kodda özellikle engellenmiştir. Sırf test için bu engeli genel olarak kaldırmak güvenli değildir.

Yeni `EBBOT_PACKAGED_HEALTH_PROBE=1` yalnızca **frozen Windows exe + `GITHUB_ACTIONS=true` + tam `--serve-only --host 127.0.0.1 --port <port>`** çağrısında geçerlidir. Sıradan sunucu çağrıları ile diğer argümanlar reddedilir.

Bu koşulda uygulama sadece `/api/health` uç noktasını kaydeder; `/api/v1/analysis/analyze`, diğer API yolları, Swagger ve OpenAPI yoktur. FastAPI yaşam döngüsü zamanlayıcıyı, indeks indirmeyi ve cache warmup işlerini çalıştırmaz; normal main akışındaki bot stream istemcileri atlanır. Dış veri, gerçek/paper emir, wallet veya otomatik öğrenme kullanılmaz.

`scripts/probe_ebbot_packaged_health.py` Windows runner'ında gerçek `win-unpacked/resources/backend/stock_analysis/stock_analysis.exe` dosyasını, ortam değişkenlerini izin listesiyle süzerek, yalnızca 127.0.0.1'e bağlayarak başlatır. Dinamik localhost portunda 200/JSON doğrular, analiz API'si için 404 bekler; süreç her sonuçta sonlandırılır. Başka ana makine adreslerine HTTP isteği yapmaz. Bu **tam ağ/işletim sistemi sandbox'ı değildir**; sadece uygulama kodundaki ağ/işlem yan etkilerinin tanılama modunda kapatılması ve izin listeli ortam ile sınırlandırılmasıdır.

## GitHub kanıtı

- PR genel CI ve özel Windows birim testleri; normal API davranışının değişmediği, CI modunun yalnızca izin verilen koşullarda aktif olduğu ve yan yolların saklandığı sözleşmelerini doğrular.
- Windows `push` job'u gerçek PyInstaller backend + React + NSIS'i `electron-builder --win nsis --publish never` ile üretir; tam paket denetiminden sonra kısa süreli sağlık deneyi yapar. Bir PR kontrolünde tam paket işi, önceki iş akışındaki güvenlik ayarı gereği atlanabilir; **push işi açıkça başarılı olmadıkça sağlık deneyi doğrulanmış sayılmaz**.
- `.exe`, `latest.yml`, `app.asar`, backend, kullanıcı `.env` dosyası **yüklenmez**. Yalnız paket denetim JSON'u kısa süreli saklanır.

## Açık engeller

Gerçek Windows kullanıcı cihazında EBBot Electron UI başlatma/kurulum/kaldırma, eski kurulum ve veri göçü, Windows imzası ve SmartScreen/Defender, üçüncü taraf lisans/atıflar, paket değişikliklerinin gerçek dünyadaki güvenliği ve manuel yayın onayı **ayrı kontrollerdir**. Bu PR hiçbir yayın veya işlem yetkisi vermez.
