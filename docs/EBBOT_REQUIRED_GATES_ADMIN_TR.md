# EBBot — `main` için GitHub zorunlu kabul kapısı (yönetici adımları)

Bu belge yalnız test ve repo yönetimi hazırlığıdır; herhangi bir PR'ı birleştirmez veya işlem başlatmaz.

## 1. GitHub CI kapsamı

`.github/workflows/ebbot-final-acceptance.yml`, `main` hedefli PR'larda şu dört bağımsız işi çalıştırır:

1. `Complete offline backend pytest (no live providers)`: `pytest -q -m "not network"`. Bilerek kapsam dışı bırakılan 4 gerçek ağ testi, canlı veri doğrulaması yerine geçmez.
2. `Dedicated auth, Turkish reporting and Chinese leak checks`: oturum ve parola iptal güvenliği, Türkçe rapor, Han metni denetimi, ayrıca JUnit validator birim testleri.
3. `Complete React Vitest (preserve all failures)`: tüm testlerin gerçek çıkış kodu korunur. `scripts/validate_vitest_junit.py` ile XML'deki **en az 1.408 testcase, sıfır skipped, sıfır failure/error** zorunludur. Test silmek veya `it.skip` eklemek yeşil sonuç üretemez.
4. `Independent ESLint, TypeScript and production Vite build`: frontend kalite/derleme kontrolleri.

Son iş: **`EBBot required gate / all offline acceptance checks`**. Dört bağımlılığın her biri `success` değilse bu iş başarısız olur. Workflow salt-okunurdur, `main` üzerinde otomatik işlem oluşturmaz.

## 2. GitHub yöneticisinin yapması gerekenler

- Repo: `ebbottr-cyber/ebbotcyber` → **Settings → Rules → Rulesets** (hesap arayüzüne göre Settings → Branches).
- `main` dalını hedefleyen **aktif branch ruleset** oluştur.
- **Require a pull request before merging** ve **en az bir bağımsız approving review**, uygun yetki varsa **dismiss stale approvals** ve **require conversation resolution** etkinleştir.
- **Require status checks to pass before merging** seç; yeni PR'da check adı listelendikten sonra **`EBBot required gate / all offline acceptance checks`** kontrolünü zorunlu yap. Mevcut, her PR'da çalışan `frontend` ve `backend` kontrolleri de incelenerek zorunlu yapılabilir. Sadece belirli path'lerde çalışan kontrolleri tüm PR'lara şart koşma; aksi halde beklemede kalırlar.
- **Require branches to be up to date before merging** veya merge queue stratejisini ekip politikasıyla uyumlu ayarla. Merge queue kullanılacaksa `merge_group` için ayrı CI tetikleyicisi de test edilmelidir.
- **Block force pushes** ve **block deletions**; uygunsa bypass listesini sınırla.
- `main.protected=true` ve required check'lerin gerçekten zorunlu olduğunu repo yönetici hesabından doğrula. Şu anda bu sohbetteki GitHub bağlantısı koruma API'sini değiştiremiyor: `403 Resource not accessible by integration`.

## 3. Yayın yetkisi değildir

Bu kontroller yalnız **offline backend + React ve seçili auth/Türkçe sözleşmelerine** aittir. Gerçek Yahoo/LLM rapor kalite doğrulaması, Windows paket/imza/güncelleme kaynakları, BIST veri erişim lisansı ve canlı/paper işlem yetkisi ayrıca gereklidir.

`main`e birleştirme, otomatik analiz, scheduler, cüzdan, broker, gerçek/sanal emir, deploy veya release bu PR kapsamında **yoktur**.
