# EBBot — dört yeni Türkçe React ekranı, izole Windows CI

**Taslak ve yayın engelli.** Bu dal başarılı [PR #177](https://github.com/ebbottr-cyber/ebbotcyber/pull/177) üzerine eklenir; `main` veya eski taslak PR'ları değiştirmez.

## Kanıt
PR #177'nin [gerçek Windows push çalışması](https://github.com/ebbottr-cyber/ebbotcyber/actions/runs/44886889474) PyInstaller/NSIS, paketli Electron, `Hisse Analizi` doğru menü etiketi ve `Kullanım`/`Veri Merkezi` testlerinde **success**. Yeni dal aynı doğru `Hisse Analizi` koşulunu korur ve sadece dört ek NavLink rotası/başlığına `exit=42` kontrollü CI testini genişletir.

| Menü | Rota | Beklenen gerçek başlık |
| --- | --- | --- |
| Portföy | /portfolio | Portföy Yönetimi |
| AI Önerileri | /decision-signals | AI Önerileri |
| Hisse Tarama | /screening | Hisse Tarama |
| Ayarlar | /settings | Ayarlar |

`uiText.ts` sadece AI Önerileri ve Ayarlar başlıklarının dört Türkçe anahtarını güncel `main` değerleriyle eşitler. Hisse Tarama başlığı, zaten `L("选股")` ile Türkçe `Hisse Tarama` olarak çevrildiğinden aynı kalır. Kaynak sözlük/gerçek ekran etiketleri için Node testleri eklendi. `api/app.py` yalnız frozen GitHub Windows + `EBBOT_PACKAGED_REACT_PROBE=1` modunda sahte salt-okunur auth, paketli statik React ve güvenli `GET` gezinme yollarını sunar; `POST` ve gerçek piyasa/analiz/scheduler yolları yoktur.

## CI ve önemli sınırlar

Bu başlık için Windows `push` gerçek PyInstaller+NSIS `--publish never` / Türkçe Electron smoke; `pull_request` Node/SQLite/NSIS 14 kaynak testi çalıştırır. **Yeni workflow PASS alınana dek dört sayfa başarıyla doğrulandı denilemez.** Windows kaynak testlerinde 9 NSIS fail-closed denetimi, `/KEEP_APP_DATA` sözleşmesi, SQLite WAL/SHM no-clobber, SHA-512 ve Authenticode gözlemi korunur.

`main`, son aşamada `b31c8195bd9650af8c3faa5e3f88fd576c14ab21` SHA'ya ilerledi. Bu daha yeni `main` commit'inde dört sayfada **read-only kontrol smoke** davranışı eklenmiştir. Bu taslak PR **o sonraki commit'in içerildiğini iddia etmez** ve ana dala birleştirilmemelidir. Mevcut dört rota testinin sonucu kesinleşince bir sonraki entegrasyonda karşılaştırılmalı.

`release_status=BLOCKED`, `DESKTOP_UPDATES_ENABLED=false`; gerçek Windows installer çalıştırma, kullanıcı DB/.env, alım-satım, paper-trade, otomatik piyasa taraması, scheduler, imzalama, yayın ve merge yok.
