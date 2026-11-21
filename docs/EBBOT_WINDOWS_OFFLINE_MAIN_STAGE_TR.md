# EBBot — Windows Electron çevrimdışı paketleme: PR #137 sonrası taslak

**Durum: YAYIN ENGELLİ.** Bu PR bir installer yayımlama/kurulum görevi değildir. Dağıtım ve gerçek/paper alım-satım kapalıdır.

## Bağımlılık düzeni

Bu çalışma artık doğrudan `main` dalını temel alır. [PR #137](https://github.com/ebbottr-cyber/ebbotcyber/pull/137) başarılı genel backend/frontend ve 51 Electron testi sonrasında `1b3a327c74f0484af9b942f098e370e6fb4f80ec` commit'iyle main'e birleştirildi. Böylece EBBot ürün kimliği güncellendi ve `DESKTOP_UPDATES_ENABLED = false` güvenlik kilidi korundu. PR #142, squash birleşimi sonrası eski PR geçmişini tekrar içermeyecek şekilde main üzerine **yalnız dört denetim dosyası** ile yeniden oluşturuldu. Yeni commit'teki Windows ve genel GitHub testleri ayrıca doğrulanmadan bu PR main'e alınmaz.

## Çevrimdışı kanıt kapsamı

1. `windows-2022` çalıştırıcısında Node ana süreç/preload testleri, ürün kimliği ve `release_status: BLOCKED` denetimi.
2. `scripts/build-backend.ps1` ile **gerçek PyInstaller backend**. Sahte yer tutucu dosya kullanılmaz.
3. `npx electron-builder --win nsis --publish never` ile geçici NSIS paketi oluşturma. Güncellemeci, backend sunucusu, strateji, tarayıcı veya installer başlatılmaz.
4. `--strict-package` ile `EBBot-windows-installer-v3.21.0.exe`, ASAR, `stock_analysis.exe`, React statikleri, `latest.yml` ve pakette gerçek `.env` olmaması kontrol edilir.
5. Yalnızca güvenlik raporu JSON'u kısa süreli artefakt olarak saklanır; **.exe, installer, backend, latest.yml veya .env yüklenmez**. `contents: read` dışında izin yoktur.
6. Çevrimdışı doğrulama `push` üzerinde yapılır; PR ana dala hedeflendiğinde yalnız kaynak/birim sözleşmeleri test edilir, otomatik release yapılmaz.

Önceki taslak zincirdeki [Windows çalışması 44811245439](https://github.com/ebbottr-cyber/ebbotcyber/actions/runs/44811245439) paket üretiminde başarılıydı. Yeni `main` tabanlı commit'in [Windows çalışma kayıtları](https://github.com/ebbottr-cyber/ebbotcyber/actions/workflows/ebbot-electron-windows-offline-package.yml) doğrulanmadan önceki kanıtı aktarılmış bir başarı gibi göstermemek gerekir.

## Açık yayın engelleri

Kod imzası ve sertifika sahibi, SmartScreen/Defender, gerçek Windows cihazında kurulum ve kaldırma, kullanıcının eski sürümünden veri göçü, paketli backend başlatma/GET sağlık kontrolü, lisans ve üçüncü taraf bağımlılık incelemesi. Ana dal birleşimi bile **yayın izni değildir**.

**Güvenlik sınırı:** GitHub Release, tag, installer upload, gerçek emir, paper emir, otomatik piyasa taraması veya scheduler açılmayacaktır.
