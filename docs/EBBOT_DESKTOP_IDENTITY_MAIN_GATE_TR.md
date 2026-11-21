# EBBot masaüstü kimliği — main tabanlı güvenlik önerisi

**Durum: YAYIN ENGELLİ.** Bu PR yalnız masaüstü uygulama kimliğini ayırır ve yanlış GitHub deposundan otomatik güncelleme indirilmesini kapatır. Kurulum, dağıtım, gerçek emir, sanal strateji yürütme veya release izni vermez.

## Bağımlılık ayrımı

Kaynak [PR #123](https://github.com/ebbottr-cyber/ebbotcyber/pull/123), [PR #117](https://github.com/ebbottr-cyber/ebbotcyber/pull/117) test dalını; #117 de bir diğer taslak release-candidate dalını temel alır. Bu yüzden PR #123 doğrudan main'e birleştirilmez. Burada **sadece** main ile aynı tabana sahip yedi Electron kimlik/güncelleme dosyasının içerikleri, kaynak PR'da Windows testinden geçmiş blob sürümleri ile birebir aktarılmıştır.

## Koruma

- Masaüstü adı `EBBot`, paket adı `ebbot-desktop`, `appId = com.ebbot.desktop`.
- Electron güncelleme hedefi ve GitHub kod sabitleri sadece `ebbottr-cyber/ebbotcyber` adresindedir.
- `DESKTOP_UPDATES_ENABLED = false`: başlangıç kontrolü, elle güncelleme kontrolü ve otomatik kurulum fonksiyonları güvenlik incelemesi tamamlanana kadar bloke edilir. Kontrolü açmak için ayrıca gözden geçirilmiş kod değişikliği gerekir.
- Eski uygulama kimliğinden veri/kurulum göçü **bu PR'da yapılmaz**. Mevcut NSIS ve kod imzalama riski ayrı tutulur.
- PR CI, kimlik sözleşmesini ve Electron Node birim testlerini doğrular. Testleri geçmesi dağıtım izni değildir.

## Önceki Windows kanıtı ve kalan engeller

[44811245439](https://github.com/ebbottr-cyber/ebbotcyber/actions/runs/44811245439) numaralı **bağımlı PR #123 dalı** Windows testinde gerçek PyInstaller ve EBBot adlı NSIS dosyası oluşturmuş; `--publish never` ile yayımlamamıştır. Bu, burada main tabanında yeniden Windows paketi üretildiği veya Windows üzerinde kurulup çalıştırıldığı anlamına gelmez.

Kalan: PR #117 paket denetiminin bağımsız main entegrasyonu, imza/sertifika, eski sürümden göç, Windows yükleme-kaldırma/gerçek cihaz deneyi, veri güvenliği, MIT lisansı/atıf ve manuel yayın onayı. **Güncelleme ve release engeli açık kalmalıdır.**
