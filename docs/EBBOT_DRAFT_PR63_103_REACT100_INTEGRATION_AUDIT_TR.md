# EBBot — Birleştirme Öncesi Entegrasyon Denetimi (20 Kasım 2026)

**Kapsam:** PR #63, #86, #88, #90, #93, #95, #97, #101, #103 zinciri ve ayrı gelişen PR #100 React regresyon düzeltmeleri.

**Durum:** SADECE TASLAK ENTEGRASYON DENEMESİ. `main`, hiçbir mevcut PR dalı, canlı alım-satım, otomatik sanal emir ve zamanlayıcı değiştirilmez.

## 1. Bağımlılık ve çatışma analizi

- PR #63 (Türkçe arayüz + portföy güvenliği) -> #86 (bağımsız TL kurları) -> #88 (USD ara kurları) -> #90 (tarihî kur kaynağı) -> #93 (piyasa tatili kontrolü) -> #95 (kapanmamış gün çubuğu) -> #97 (hata/kur ekranı) -> #101 (Windows salt-okunur denetim) -> #103 (gerçek yerel Windows HTTP sunucu kontrolü) zincirini GitHub PR metadata ve karşılaştırma uç noktalarıyla doğruladık.
- Temel alınan dal **PR #103'ün son commit'idir**. Bu commit, önceki sekiz PR'ın tüm ardışık değişikliklerini zaten içerir; onları bir kez daha `merge` etmek gereksiz ve risklidir.
- PR #100'ün tabanı: `fix/portfolio-turkish-fx-test-contract-20261120` (SHA `802ec986...`). PR #103 ile Git ortak atası `37adb271...`; iki dal **diverged** durumunda. PR #100'ün tabanındaki bağımsız Xetra/Germany, Meme Coin, paper-market vb. değişikliklerin PR #103'e körlemesine alınması kapsam dışıdır.
- GitHub'ın PR #100 dosya listesinde **11 farklı dosya** vardı. 8 mevcut React dosyası için seçici entegrasyon yapıldı; PR #100'ün farklı bazından kaynaklanan bağımsız/uyuşmayan içerikler ayrıca ele alındı.

## 2. PR #100 aktarım tablosu

| Değişiklik | Durum | Çözüm |
| --- | --- | --- |
| DesktopUpdateIndicator + testi | Taşındı | `title` -> erişilebilir `aria-description` ve Tooltip, 42% indirme testi |
| UiLanguageToggle | Uyarlanarak taşındı | Mevcut Türkçe/İngilizce/Çince kısaltılmış bileşende yalnız native title kaldırıldı, PR100'ün farklı sayfa varyantı alınmadı |
| SidebarNav testi | Uyarlanarak taşındı | Chat'ten hemen sonra Screening korunur; /overview var, bağımsız /germany rotası zorunlu kılınmaz |
| NotificationTestPanel testi | Taşındı | Türkçe `E-posta` beklentisi; buna uygun **üretim etiketi de** yerel UI'da düzeltildi. İngilizce `Email` korunur |
| DecisionSignals testi | Çatışma çözüldü | PR #103'teki bugünün tarihli sinyal testi korundu; PR #100'ün 90 günü aşan tarihî örneği **ayrı** regresyon testi eklendi |
| index.html tema testi | Taşındı | Uygulamanın mevcut açık tema varsayılanı (light) doğrulanır |
| Vitest konfigürasyonu | Taşındı | Sadece Node native `tests/pwa-smoke.test.mjs` Vitest keşfinden dışlandı; Node PWA testleri ayrı ve zorunlu çalışır |
| MemeCoinsPage.test.tsx | **Taşınmadı** | Bu çalışma zincirinde `MemeCoinsPage.tsx` ve ilgili API bulunmuyor; PR #100'ün başka dal özelliklerini çekmek yanlıştır. Ayrı entegrasyon incelemesi gerektirir |
| PR100 React-only CI workflow | **Aynen taşınmadı** | Farklı bazdan gelen Meme/Germany/test varsayımlarını istemez. Yerine hem **tam backend** hem **tam frontend** ve portföy güvenliğini kapsayan yeni CI dosyası eklendi |
| PR100 kaynak değerlendirme dokümanı | **Aynen taşınmadı** | Başka dalın 1.490/7 sayımlarını bu dal için doğru kabul etmiyoruz; bu rapor ve yeni CI gerçek sonuçları kullanılır |

## 3. Zorunlu entegrasyon testleri

Yeni `.github/workflows/ebbot-draft-integration-full-regressions.yml` yalnız bu entegrasyon dalında veya bu dalın taslak PR'ında çalışır.

- **Tam backend:** `python -m pytest -q -m "not network"` (ağ işaretli testler bilinçli dışarıda), tekil test 120s sınırı, JUnit dosyası her durumda saklanır. Başarısız test **CI'yi kırar**, filtreyle gizlenmez.
- **Tam frontend:** Tüm Vitest testleri (`npm test -- --reporter=dot`), lint, gerçek production TypeScript/Vite build, ayrı Node native PWA smoke (`PWA_REQUIRE_BUILD=1 npm run test:pwa`). İş testleri gizlenmez.
- **Odaklı güvenlik:** Portföy servis/API/risk/tarihî kur regresyonları, 16 bağımsız fail-closed FX testi, Windows ön kontrol aracı güvenlik regresyonları.

## 4. Sınırlar / geçiş kriterleri

- Bu GitHub CI **gerçek cihazdaki Electron kurulumunun**, üretim veritabanının, broker API'lerinin ve piyasa sağlayıcısı lisans koşullarının yerine geçmez.
- Başarılı testler yalnızca entegrasyon dalının kalite kapılarından geçtiğini gösterir. İlgili PR'lar ve ana dal için merge veya deploy yetkisi vermez.
- Her yeni kusur veya baseline başarısızlığı ayrı ayrı incelenmeli; testte filtre/skip ekleyerek saklanmamalıdır.
- **Canlı alım-satım ve otomatik paper trading kapalı kalır.** Bu dal araştırma/inceleme amaçlıdır.
