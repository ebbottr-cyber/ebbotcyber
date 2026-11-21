# EBBot — Türkçe React Windows CI smoke ve NSIS veri-koruma denetimleri entegrasyonu

**DURUM: TASLAK, RELEASE BLOCKED.** Kaynaklar: son NSIS kaynak güvenliği [PR #171](https://github.com/ebbottr-cyber/ebbotcyber/pull/171) head `effd7debec6c95013dfc7a144c92d731bd7ff806` ve güncel `main` React smoke commit `c95fb7f2ee63d5bee131bd59b25a38ae420d0546`. Kaynak PR'lar veya `main` değiştirilmez.

## Korunan iki ayrı güvenlik katmanı

1. **Windows NSIS sözleşmesi:** [PR #171](https://github.com/ebbottr-cyber/ebbotcyber/pull/171) içindeki `scripts/audit_ebbot_nsis_upgrade_contract.py` ve 14 mutasyon testi korunur. Gerçek kurulum/yükseltme/kaldırma çalıştırılmaz. Per-user NSIS, `/KEEP_APP_DATA`, tırnaklı `"_?=$R8"`, hata kodu, kod imzası ve `--publish never` fail-closed kontrolleri devam eder. SQLite WAL/SHM dangling symlink no-clobber, offline snapshot/rollback testleri de korunur.
2. **Gerçek paketli Electron içinde Türkçe React smoke:** Güncel `main` commitinin `api/app.py` sahte salt-okunur auth/asset rotaları, `ci-ui-smoke.js` navigasyon denetimi, `main.js` yalnız CI'da ayrı 42 çıkış kodu, Python `--react-ui` frozen backend+Electron probu ve ilgili yeni testler entegre edilir. **Normal Electron startup ve gerçek API/analiz/scheduler** bu smoketa açılmaz.

## Önemli Türkçe sözlük kararı

`main` commit'i `uiText.ts` içine `usage.eyebrow=Kullanım`, `usage.title=Token Kullanımı`, `usage.description=Model çağrılarını…` satırlarını ekledi. Ancak birleşim kaynak dalındaki Türkçe sözlükte **bu anahtarların tamamı zaten doğru ve daha kapsamlı Türkçe ifadelerle bulunuyor** (`usage.eyebrow=KULLANIM`, `usage.title=Token Kullanımı`). Bu nedenle ikinci bir sözlük girişi üretmedik; önceki Türkçe iyileştirmeler silinmedi.

## Windows CI kapsamı

Sırayla kaynak testleri, NSIS no-install mutation/audit, Python frozen React probe route izinleri, Electron Node UI testleri, PyInstaller backend, sentetik SQLite WAL snapshot, NSIS `--publish never` derleme, paket SHA-512 kontrolü, donmuş backend 127.0.0.1 sağlık testi, paketli Electron splash/preload, **Türkçe React Ana Sayfa → Kullanım → Veri Merkezi** menü geçişleri ve Authenticode *gözlemi*. Başarıda yalnız kısa süreli JSON audit tutulur; kurulum paketi veya kullanıcı dosyası yüklenmez.

Ağ kısıtı ve sahte React fixture **tam işletim sistemi sandbox'ı değildir**. Test React'in gerçek verilerle davranışını, gerçek Windows yükleyicisini, kullanıcı kurulum yükseltmesini, DB WAL güç kesintisini, imzalama/SmartScreen veya otomatik güncellemeyi ispatlamaz.

**Değişmeyen kısıtlar:** `DESKTOP_UPDATES_ENABLED=false`, `release_status=BLOCKED`, gerçek/paper emir, zamanlayıcı ve piyasa taraması kapalı. Merge, yayın, imzalama, gerçek kullanıcı profilinde NSIS çalıştırma ve otomatik güncelleme yoktur.
