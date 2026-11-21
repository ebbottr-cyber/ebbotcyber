# EBBot — birleşik nihai kabul adayı (2026-11-21)

## İncelenen kaynaklar ve GitHub kanıtları
- Güncel `main`: `daad93eaab155509cef8fcf3906c2b354fee4fdf`; Windows paketleme, localhost health ve paketli Electron UI loopback değişiklikleri korunuyor.
- Birleşik güvenlik/Türkçe/React [PR #159](https://github.com/ebbottr-cyber/ebbotcyber/pull/159), head `dd13bf23fb2a6f34e72558f2c5c322b0bb92b7ce`: [GitHub CI run 44877921855](https://github.com/ebbottr-cyber/ebbotcyber/actions/runs/44877921855) — **8.787 backend passed, 4 network deselected**, **1.406 React passed, 2 skipped**, 157 hedefli Python PASS ve bağımsız lint/typecheck/build PASS.
- Shell son test düzeltmesi [PR #162](https://github.com/ebbottr-cyber/ebbotcyber/pull/162), head `113b97615a5259114bd431f56d85cfb3cd3792a1`: [GitHub CI run 44878515632](https://github.com/ebbottr-cyber/ebbotcyber/actions/runs/44878515632) — **1.408 React passed, 0 skipped**, Shell + SidebarNav + ThemeToggle 16/16, bağımsız lint/build PASS.
- Son `main` değişikliği `65b77f17 → daad93ea` yalnız Windows/Electron paketli uygulamanın smoke/probe dosyalarındaydı; taslak PR #162'nin değiştirdiği 59 yolla **çakışma yok**.

## Nasıl oluşturuldu
- 2026-11-21 tarihinde yeni `main` üzerine kaynak commit `113b97615a5259114bd431f56d85cfb3cd3792a1` değişen dosyaları SHA karşılaştırmasıyla yeniden konumlandırıldı; proje kaynakları bozulmadı.
- Kaynak branch'e özgü `ebbot-shell-unskip-review.yml` ve `ebbot-combined-auth-tr-react-offline.yml` dosyaları **taşınmadı**. Bunun yerine bu PR'da `ebbot-final-acceptance.yml` yalnız `main`e açılan PR'larda çalışan birleşik backend/auth/Türkçe/React kontrolüdür.
- Eski geçici kabul notunun yerini bu belge alır. ETRE belgesi temizlenmiş kalır, Türkçe varsayılan korunur.

## Kabul ölçütleri — bu PR head'inde yeniden doğrulanmalı
1. Tam çevrimdışı backend pytest `python -m pytest -q -m "not network"`: 0 failure (canlı sağlayıcı ağına bağımlı 4 test hariç).
2. Hedefli auth, parola değiştirme fail-closed, Türkçe piyasa raporu, Han sızıntısı denetimi: 0 failure.
3. Tam React Vitest: tüm dosyalar başarılı, **0 failure / 0 skipped**, JUnit artefaktı tutulur.
4. Bağımsız ESLint / TypeScript / Vite üretim derlemesi başarılı.
5. Mevcut PR workflow'ları ve Windows smoke testleri ayrıca değerlendirilmeli; gerçek paket, imzalama ve güncelleme kaynağı hâlâ yayın engeli olabilir.
6. GitHub `main.protected=false`, rulesets boş. Repo yöneticisi PR review ve required-checks olmadan main'e merge yapılmasını engellemelidir.

**Bu test raporu üretim garantisi değildir.** Gerçek Yahoo/LLM çıktısı, BIST100 veri lisansı, yayın kimliği ve canlı/sanal alım-satım onayı ayrıca ele alınmalıdır. **Deploy, cron, paper/live emir, cüzdan, broker, main merge ve otomatik analiz YOK.**
