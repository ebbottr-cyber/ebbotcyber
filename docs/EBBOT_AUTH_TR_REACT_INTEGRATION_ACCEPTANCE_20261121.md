# EBBot — 21.11.2026 birleşik güvenlik, Türkçe ve React kabul provası

## Kaynak ve sabitleme
- `main` tabanı: `65b77f17085224a2f01dda3ee8d3807dbe789e10` (Windows offline paketleme ve localhost sağlık kontrolleri dahil).
- Kaynak güvenlik/Türkçe PR: [#144](https://github.com/ebbottr-cyber/ebbotcyber/pull/144), head `81b2e3b2e36ce31484ac2e476ee680a0c18c9b85`.
- Kaynak UI zinciri: [#140](https://github.com/ebbottr-cyber/ebbotcyber/pull/140) → [#145](https://github.com/ebbottr-cyber/ebbotcyber/pull/145) → [#147](https://github.com/ebbottr-cyber/ebbotcyber/pull/147) → [#149](https://github.com/ebbottr-cyber/ebbotcyber/pull/149) → [#153](https://github.com/ebbottr-cyber/ebbotcyber/pull/153); son head `5c7467d3169c6ca17d70e7f04c26b45cabae651e`, diff tabanı [#138](https://github.com/ebbottr-cyber/ebbotcyber/pull/138) head `63efedb2dc9ce59ae62729add1c79bac7a7f9736`.
- Birleşim yöntemi: SHA'sı doğrulanmış 20 adet PR144 dosyası ve 36 adet UI bileşeni/test dosyası blob'u `main` üzerine **yeni dalda** uygulanır. UI zincirinin 5 geçici, başka dallara bağlı workflow'u taşınmaz.
- UI tarafında 34 React test dosyası + test amaçlı `renderLegacyChineseUi` + erişilebilir masaüstü güncelleme açıklaması için üretim `DesktopUpdateIndicator` düzenlemesi vardır.
- Eski ETRE belgesi kaldırılmıştır; ETRE entegrasyonu eklenmez.
- Kaynak PR'ların tek başına yeşil olması birleşik adayın yeşil olduğu anlamına gelmez.

## Bağımsız kabul kontrolleri
1. Tam backend pytest: `python -m pytest -q -m "not network"`.
2. Yönetici şifre değişimi/oturum iptali, Türkçe fiyat ve LLM şablonları, salt-okunur Han metni sızıntısı kontrolü.
3. Tam React Vitest: orijinal hata kodu, JUnit/XML ve log kaydı. İki önceden skip edilmiş test ayrı izlenir.
4. Bağımsız ESLint, TypeScript ve Vite üretim derlemesi.
5. Var olan `PR #1 Verification` kontrolü ve gerektiğinde kod/güvenlik incelemesi.

## Yayın engelleri
- `main` dalı koruması ve zorunlu GitHub test kapıları doğrulanmadan merge/deploy yapılamaz.
- BIST100 lisanslı veri erişimi, gerçek Yahoo/LLM Türkçe rapor kalitesi, Windows kurulum/kimlik/imza/yayın, canlı veri ve gerçek performans ayrı işlemlerdir.
- Bu dal sadece test; **otomatik analiz, schedule, Solana radar/ticaret, paper/live emir, broker, cüzdan ve dağıtım etkinleştirilmez**.
- PR taslak olmalı; `main` değişirse yeniden tam fark denetimi + CI gerekir.
