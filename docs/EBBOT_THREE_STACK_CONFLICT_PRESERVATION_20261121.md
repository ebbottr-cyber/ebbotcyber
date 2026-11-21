# EBBot — Main + React + Windows/SQLite üçlü çakışma koruma kararı

**TASLAK: yayımlama/birleştirme izni vermez.** Kaynaklar ve SHA'lar sabittir:
- `main`: `daad93eaab155509cef8fcf3906c2b354fee4fdf`
- React düzeltmelerinin uç noktası PR #154: `61cda4b7024ff4f6d39b4c20887814ca882ade72`
- Windows/SQLite/localhost uç noktası PR #155: `dd2470b86cb389278da7a1fd93a2d0b88e53678a`

[PR #160 üçlü merge-tree çalışması](https://github.com/ebbottr-cyber/ebbotcyber/actions/runs/44878464794) **18 gerçek çakışma** bulmuştur: 16 React test dosyası, 1 Windows workflow, 1 paketlenmiş sağlık kontrolü betiği. Backend ve frontend mevcut parçaların ayrı ayrı yeşil olması, bu üçlü kaynağın birlikte geçtiğini kanıtlamaz. `main` koruması da kapalıdır.

## Gerçek test korunumu: neden bir tarafı komple seçmiyoruz?

Aynı test adlarını taşıyan dosyalarda bile test hazırlığı, açık `zh` seçimi, eski `en` seçimi sonrası localStorage temizliği ve varsayılan `tr` sınırları farklı olabilir. Dolayısıyla test adlarının eşitliği tek başına güvenli merge demek değildir.

Özellikle iki ayrı taraftaki ilaveler **birbirinin yerine geçmez**:

- **React tarafındaki 2 benzersiz portföy testi:** yabancı para maruziyetini snapshot para birimine çevirme, CNY/USD karma hesap agregasyonu.
- **Windows tarafındaki 8 benzersiz portföy testi:** TRY karşılıklarının sahte sayı üretmeden gizlenmesi, FX veri sağlayıcı outage/stale/503, gerçek HKD zaman damgası, Türkçe manuel defter ve broker etiketleri.
- **Windows tarafındaki ek Türkçe testleri:** AlertsPage Türkçe uyarı paneli, LLMChannelEditor Türkçe model kimliği ve auth hataları, NotificationTestPanel Türkçe kanal adları.
- 15 dosyada iki taraftaki temel test adları büyük ölçüde aynı olabilir, fakat farklı render sarmalayıcıları/localStorage/ek assertion'lar **hunk bazında incelenmelidir**. İki eski Shell `it.skip` durumu ayrıca PR #162 üzerinden inceleniyor.

## Üretim ve yayın sınırları

- `.github/workflows/ebbot-electron-windows-offline-package.yml`: güncel `main` Electron splash/renderer localhost testi ile Windows PR #155 gerçek PyInstaller/NSIS `--publish never`, SHA-512, Authenticode, frozen backend, SQLite WAL/snapshot kontrolleri birlikte korunmalı. Otomatik bir tarafı tercih etme.
- `scripts/probe_ebbot_packaged_health.py`: her iki kolda aynı adla eklenmiş ama farklı içerikli (`add/add`) kaynak; açık ve yalnızca `127.0.0.1` trafiği, CI-only flag, analiz/emir endpointleri kapalı davranışları birlikte doğrulanmalı.
- Bunlara dokunan uzlaştırma kullanıcı SQLite dosyasında, gerçek installer'ında veya gerçek brokerage hesabında çalıştırılmaz.

## Bu taslak PR ne sağlar?

`scripts/audit_ebbot_conflict_test_preservation.py` yalnız Git dosyalarını okur ve 16 test dosyasındaki **React-only / Windows-only adlandırılmış testleri** JSON'da çıkarır; adları henüz birleştirmez. Sabit SHA değişirse FAIL olur. Parçalar arası sınıflandırmayı saf Python unittest sınar. Denetim raporu workflow artifact'ıdır ve **gate açıkça FAIL** kalarak henüz çözülmemiş 18 çatışmayı gizlemez.

### Sonraki kaynak kod uzlaştırma sırası

1. Aynı senaryolu 15 React test dosyasının hazırlık/çeviri/harness farklarını birleştir, özel TR testlerini koru.
2. PortfolioPage'in 2+8 benzersiz testini ve TRY/CNY para birimi güvenliğini **davranışları ezmeden** uyumlu hâle getir. Değişmesi gerekiyorsa ayrı test kanıtı.
3. Windows workflow ve packaged health betiğini güncel `main` + PR #155 kontrollü olarak birleştir; yeni Electron smoke ve frozen sadece localhost şartlarını koru.
4. Geçici birleşik ağacı tam frontend **0 fail / 0 yeni skip**, backend `pytest -m 'not network'`, Windows/SQLite/frozen smoke ile denetle.
5. **Daha sonra** ayrı bağımsız güvenlik incelemesi ve gerçek `main` branch protection. Bu taslak `main`e asla merge edilmez.

Sürekli kapalı olanlar: live/paper trading, scheduler, auto-update, GitHub release, Windows installer dağıtımı, real API/keys, remote brokerage işlemleri.
