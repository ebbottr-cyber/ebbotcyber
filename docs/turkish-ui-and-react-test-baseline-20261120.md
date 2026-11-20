# EBBot Türkçe arayüz taraması ve eski React başarısızlıkları

Tarih: 2026-11-20
Temel sürüm: taslak PR #85 (`feat/tcmb-try-display-review-20261120`)
Bu doküman bir **kaynak-kod taraması ve eski CI logu sınıflandırmasıdır**; canlı kullanıcı arayüzü ya da tam React testlerinin geçtiği anlamına gelmez.

## Uygulanan dar kapsamlı düzeltme

`apps/dsa-web/src/pages/PortfolioPage.tsx` içinde doğrudan Çince yazılmış kullanıcı metinleri, üretim arayüzünde Türkçeye dönüştürüldü: aracı kurum listesi uyarıları, risk mesajları, hesap oluşturma formu, işlem/nakit/şirket işlemi formları, CSV içe aktarma, olay geçmişi, silme uyarıları ve sayfalama. Eski multilingual Vitest davranışını korumak için sadece üretimde zorunlu Türkçe modunda `operatorText(tr, legacyZh)` kullanılır. Çince kaynak metinler test uyumluluğu için kodda kalır; görünen etiketleri kontrol eden testler ayrıca eklendi.

Portföyün **fonksiyonel alanları, backend, veri birimleri, alım-satım hesaplaması, CSV değerleri ve API kodları değişmedi.**

## 12 önemli sayfada kaynak taraması (Çince karakter içeren satır)

| Sayfa | Satır sayısı (tarama, yaklaşık) | Yorum |
|---|---:|---|
| PortfolioPage | 121 | Yeni üretim Türkçe koşullu metinlerinin içinde eski Çince test karşılıkları kalıyor; sadece karakter sayısına bakarak sorun denemez. |
| StockScreeningPage | 300 | Çok sayıda düz metin, öncelikli sonraki inceleme. |
| MemeCoinPage | 182 | Çoğu `zh` dil sözlüğünde; doğrudan ekrana basılıp basılmadığı ayrı doğrulanmalı. |
| ChatPage | 69 | Sohbet girişleri ve butonlarda düz metin örnekleri bulundu. |
| AlertsPage | 36 | Tablo başlıklarında ve kontrollerde düz metin örnekleri bulundu. |
| MemeCoinsPage | 22 | `zh` sözlüğü içinde. |
| BacktestPage | 2 | Dil girdi temizleme ifadeleri; görünür UI sanılmamalı. |
| SettingsPage | 1 | Mevcut dil koşulundaki Çince uyumluluk metni. |
| HomePage, DecisionSignalsPage, DashboardOverviewPage, DataCenterPage | 0 | Bu dosyalarda doğrudan Çince karakter görülmedi; alt bileşenler ayrı. |

**Not:** Satır sayıları kaynakta Çince içeren satırlardır; kullanıcıda fiilen Çince görünen ifade veya kusur adedi değildir. Türkçe sürümde `en`/`zh` locale sözlüklerini kaldırmak, test/veri sözleşmelerini bozabileceği için bu PR'da yapılmadı. İngilizce teknik terimler, para kodları, marka/sembol isimleri otomatik çevrilmemeli.

## Eski geniş React testleri — CI #44504656629

19 Kasım 2026 tarihli **değiştirilmemiş temel sürüm**: 359 başarısız / 1.119 başarılı / 2 atlanan. PR #81 için karşılaştırma CI #44504010151: 359 başarısız / 1.121 başarılı / 2 atlanan; burada **yeni başarısızlık artışı yok**.

En yoğun kümeler:

| Test dosyası | Başarısız |
|---|---:|
| PortfolioPage.test.tsx | 87 |
| SettingsPage.test.tsx | 59 |
| HomePage.test.tsx | 57 |
| ChatPage.test.tsx | 19 |
| Geri kalan 29 bileşen ve sayfa test dosyası | 137 |
| **Toplam** | **359** |

**İlk neden ayrıştırması (kesin teşhis değil):**

1. Çok sayıda Testing Library seçicisi eski metni veya artık mevcut olmayan öğeyi arıyor (`Unable to find`); yeni etiket/DOM ayrımı gerek.
2. `SettingsPage` test çalışmasında yoğun `act(...)` uyarısı var; asenkron güncellemeler ve test zamanlaması ayrıca incelenmeli.
3. `tests/ui_governance.test.ts` ve `tests/index.theme-bootstrap.test.ts` tekil yapısal koşullarda başarısız; bunlar sırf çeviri hatası diye kapatılamaz.
4. Portföy kayıt, analiz veya hesaplama testleri ancak ayrı davranış ve veri sözleşmesi kontrolünden sonra test beklentisi olarak güncellenebilir. Başarısızlıkları skip etmek, geniş CI'yı yeşil göstermez.

Bu PR'ın düzeltmesi **eski 359 başarısız testi giderilmiş sayılmaz**. Bir sonraki kapsam: Hisse Tarama/Sohbet/Uyarılar için doğrudan görünen metinler; ayrı adımda en yüksek öncelikli üç test dosyasındaki seçici ve gerçek davranış farklarının izlenmesi.

## Güvenlik ve dağıtım

Bu çalışma birleştirme, dağıtım, emir/strateji/scheduler etkinleştirme yapmaz. İstenen düzeltmeler yalnızca bağımsız bir taslak PR üzerinden yürür. Geri alma: PR'ı kapatmak veya bu dalın commit'lerini geri almak; veri göçü bulunmaz.
