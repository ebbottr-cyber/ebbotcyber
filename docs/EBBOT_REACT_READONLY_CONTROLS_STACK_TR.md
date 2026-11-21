# EBBot — Türkçe React GET/HEAD-only kontrol testleri, güvenli katman

**TASLAK — RELEASE BLOCKED.** Kaynak: `main=b31c8195bd9650af8c3faa5e3f88fd576c14ab21` içindeki salt-okunur React kontrol CI gereksinimleri; öncül taslak [#184](https://github.com/ebbottr-cyber/ebbotcyber/pull/184) başı `e40b8a22642fe81bdd65fd767a6fa8c76d2a75c4`.

## Amaç ve birleştirme kararı

Bu dal, paketli Windows CI-only `EBBot.exe --ebbot-ci-ui-smoke` modunda 6 Türkçe React rotasını ve **iki gerçek React state etkileşimini** gözlemler. İlk menü bağını önceki gerçek Windows yeşil PR #177'de doğrulanan `Hisse Analizi` olarak bırakır; `Ana Sayfa` aria-label'i yanlış kabul edilir. `waitUntil` aşama bazlı hata, `exit=42`, 45 saniyelik zaman aşımı, `GITHUB_ACTIONS=true`, yalnız frozen Windows paket ve `127.0.0.1` port gereksinimleri korunur.

### İki interaktif ama veri yazmayan kontrol

1. `TokenUsagePage.tsx`: `data-testid=usage-period-month/all`, `aria-pressed` ve `tr-TR` formatı eklenir. Gerçek Chromium, varsayılan `Ay` seçimini `Tümü`ne çevirir; **her iki** düğmenin React state'i değişmelidir. Bu dönem filtresidir, analiz veya emir değildir.
2. `DecisionSignalsPage.tsx`: `decision-signals-action-filter` ve `decision-signals-status-filter` data-testid eklenir. Ön koşullar `action=''`, `status='active'`; sentetik DOM `change` olayları ile `buy` ve `expired` seçilir. İkinci React render'dan sonra **iki değer de** korunmazsa test başarısızdır. `Apply`, `Save`, `Reassess`, emir, analiz veya screening-run düğmelerine dokunulmaz.
3. `ci-ui-smoke.js`: `onBeforeRequest`, artık dış host/port erişimini zaten engellemesine ilave olarak **yalnız GET/HEAD** methoduna izin verir. `POST/PUT/PATCH/DELETE/OPTIONS` ayrıca Node testinde reddedilir; `file:` URI de yazma metodu ile reddedilir. Bu tarayıcı ağı için koruma olup tüm Windows işletim sisteminin network sandbox'ı değildir.

### Türkçe Hisse Tarama ekranı

Yeni `main` bazı status anahtarlarını `uiText.ts` içine ekliyor, ancak öncül taslakta `screeningUiText.ts` zaten bunları daha kapsamlı olarak Türkçe/İngilizce çeviriyor. Çakışma yaratacak ikinci sözlük grubu üretmek yerine `StockScreeningPage.tsx` içindeki `statusText` `L('...')` kullanmaya dönüştürüldü. Mevcut `L("选股")` ana başlığı ve tarama izin kuralları korunur.

## Kanıt ve tehlike sınırları

CI kaynak Node testleri gerçek React dönem düğmeleri, filtre selector'ları ve `Hisse Analizi` etiketini denetler. Gerçek Windows `push` workflow'u PyInstaller+NSIS `--publish never`, sentetik SQLite DB/WAL/SHM ve rollback, 9 NSIS fail-closed kaynak kuralı + 14 mutasyon testi, SHA-512/Authenticode, backend loopback ve paketli Electron React smoke'u yürütmelidir. **Bu head için yeşil olmadan test tamamlandı denilemez.**

Normal Electron/React işleyişi veya gerçek kullanıcının `DB`, `.env`, kurulu uygulama, Windows registry ve ayarları test edilmiyor; bu bir gerçek yükleyici çalıştırma/yükseltme/kaldırma deneyi değildir. Kod imzası, SmartScreen, kullanıcı veri göçü ve reel analiz hâlâ kontrol dışı. `DESKTOP_UPDATES_ENABLED=false`, `release_status=BLOCKED`, otomatik tarama, scheduler, gerçek/paper emir ve yayın kapalıdır.

**Geri alma:** Taslak PR'ı kapatmak yeterli; `main` ve #184 değiştirilmedi.
