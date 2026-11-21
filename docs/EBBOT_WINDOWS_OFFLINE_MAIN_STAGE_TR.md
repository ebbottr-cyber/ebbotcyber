# EBBot — Windows Electron çevrimdışı paketleme: PR #137 sonrası taslak

**Durum: YAYIN ENGELLİ.** Bu PR bir installer yayımlama/kurulum görevi değildir. Dağıtım ve gerçek/paper alım-satım kapalıdır.

## Bağımlılık düzeni

Bu çalışma yalnızca [PR #137](https://github.com/ebbottr-cyber/ebbotcyber/pull/137) dalını temel alır. PR #137, yanlış uygulama kimliği ve eski projenin güncelleme adresini düzeltiyor; `DESKTOP_UPDATES_ENABLED = false` kilidi içeriyor. PR #137 henüz main'e birleştirilmemişken bu paketleme PR'ı da main'e alınmamalı. Önce PR #137'nin genel CI sonuçları tamamlanmalı, sonra bu PR güncel main'e taşınıp CI yeniden değerlendirilmelidir.

## Çevrimdışı kanıt kapsamı

1. `windows-2022` çalıştırıcısında Node ana süreç/preload testleri, ürün kimliği ve `release_status: BLOCKED` denetimi.
2. `scripts/build-backend.ps1` ile **gerçek PyInstaller backend**. Sahte yer tutucu dosya kullanılmaz.
3. `npx electron-builder --win nsis --publish never` ile geçici NSIS paketi oluşturma. Güncellemeci, backend sunucusu, strateji, tarayıcı veya installer başlatılmaz.
4. `--strict-package` ile `EBBot-windows-installer-v3.21.0.exe`, ASAR, `stock_analysis.exe`, React statikleri, `latest.yml` ve pakette gerçek `.env` olmaması kontrol edilir.
5. Yalnızca güvenlik raporu JSON'u kısa süreli artefakt olarak saklanır; **.exe, installer, backend, latest.yml veya .env yüklenmez**. `contents: read` dışında izin yoktur.
6. Çevrimdışı doğrulama `push` üzerinde yapılır; PR ana dala hedeflendiğinde yalnız kaynak/birim sözleşmeleri test edilir, otomatik release yapılmaz.

Önceki taslak zincirdeki [Windows çalışması 44811245439](https://github.com/ebbottr-cyber/ebbotcyber/actions/runs/44811245439) paket üretiminde başarılıydı. Bu yeni dalda yeniden başarılı sonuç alınmadan önceki kanıtı aktarılmış bir başarı gibi göstermemek gerekir.

## Açık yayın engelleri

Kod imzası ve sertifika sahibi, SmartScreen/Defender, gerçek Windows cihazında kurulum ve kaldırma, kullanıcının eski sürümünden veri göçü, paketli backend başlatma/GET sağlık kontrolü, lisans ve üçüncü taraf bağımlılık incelemesi. Ana dal birleşimi bile **yayın izni değildir**.

**Güvenlik sınırı:** GitHub Release, tag, installer upload, gerçek emir, paper emir, otomatik piyasa taraması veya scheduler açılmayacaktır.
