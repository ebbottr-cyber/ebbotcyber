# BIST 100 / BIST 30 — bağımsız ikinci veri kaynağı uygunluk notu

Denetim tarihi: 2026-11-20. **Araştırma notu; veri lisansı, abonelik veya API erişimi alınmış değildir.** PR taslağında kaynak, portföy ya da strateji koduna yeni sağlayıcı bağlanmaz.

## Doğrulanabilen resmî çerçeve

Borsa İstanbul, piyasa verilerinin gerçek zamanlı, gecikmeli ve günsonu olarak **lisanslı veri dağıtıcıları** yoluyla sunulduğunu belirtiyor:

- https://www.borsaistanbul.com/en/data/data-dissemination
- https://www.borsaistanbul.com/en/data/data-dissemination/data-vendors-directory
- https://www.borsaistanbul.com/sss/veri-dagitim-ve-endeks-lisanslama

Önemli: Borsa İstanbul'un resmî lisanslama SSS'sine göre **gösterimsiz kullanım** (ör. otomatik algoritmalar, risk ve analiz sistemleri) için doğrudan Borsa İstanbul ile Veri Dağıtım Sözleşmesi gerekebilir. Bir tedarikçinin “BIST lisanslı dağıtıcısı” olması EBBot'a otomatik tüketim veya başkasına dağıtım izni vermez.

Borsa İstanbul tarihsel ve bazı referans veri ürünlerini **DataStore** üzerinden sunuyor; bu kaynak bir dakikalık veya anlık fiyat akışı olarak yorumlanmamalı:

- https://www.borsaistanbul.com/en/data/historical-data-sales

## İlk adaylar (hiçbiri entegre/etkin değil)

| Aday | Kamuya açık doğrulama | EBBot için henüz kanıtlanmayan koşul | Sonuç |
|---|---|---|---|
| Matriks | Borsa İstanbul lisanslı veri dağıtıcıları rehberinde yer alıyor | Endeks değerleri için API sözleşmesi, gösterimsiz kullanım hakkı, gecikme/yeniden dağıtım şartı, teknik örnekler | **İnceleme adayı, bağlantı yok** |
| Finnet | Aynı resmî rehberde yer alıyor | Endeks veri API'si ve bot araştırma amaçlı tüketim hakkı, veri kökeni/tarih damgası | **İnceleme adayı, bağlantı yok** |
| Borsa İstanbul DataStore | Borsanın resmî tarihsel veri satış sayfası | Endeks 100/30 tarihsel günlük değerleri için lisans ve teslimat biçimi; programatik indirmeye izin | **Yalnızca tarihsel veri adayı, bağlantı yok** |

Matriks/Finnet isimleri Borsa İstanbul listesinden alınmıştır; **API sundukları veya EBBot'a lisans verecekleri doğrulanmamıştır.** Aynı Borsa İstanbul kaynağını tekrar satan iki API de kaynak bağımsızlığı anlamında dikkatli değerlendirilmelidir. Yahoo günlük seri ile TCMB ForexSelling yalnızca döviz için *bağlamsal fark* sunar; BIST endeksi için ikinci teyit oluşturmaz.

## Bağlantı açılmadan önce gerekenler

1. BIST 100 (`XU100`) ve BIST 30 (`XU030`) endeks değerlerinin açıkça sözleşme kapsamına alınması.
2. Algoritmik/gösterimsiz kullanım, depolama, elde edilen raporları gösterme ve varsa dışa aktarmaya izin verildiğinin yazılı teyidi.
3. Veri tipi: gerçek-zamanlı / 15 dakika gecikmeli / günlük kapanış; borsa günü, saat dilimi ve **yayın/işlem zaman damgası** sözleşmesi.
4. Mevcut Yahoo serisinden bağımsız köken bilgisi; sembol eşleştirmesi, endeks hesaplama ve piyasa tatil takvimi.
5. İptal, kesinti, gecikme, yanlış/tekrarlı fiyat, sağlayıcı kapasite sınırı testleri; uygunsa sağlayıcı taraflı SLA.
6. Bot içinde sağlayıcı anahtarları yalnızca gizli yapılandırmadan; hiçbir sır veya token GitHub'a commit edilmez.
7. En az iki farklı **gerçek tarih** üzerinde salt-okunur sağlayıcı kıyası ve manuel gözden geçirme tamamlanana kadar `independent_bist_second_source_verified=false`.

## Kanıt sınırı ve sonraki operasyon

Mevcut PR #111 / #112 gerçek gözlemleri **20 Kasım 2026** tarihli; aynı gün birden fazla koşum olsa bile çok-gün sürekliliği kanıtlamaz. Yeni `audit_tr_fx_multiday_continuity.py` yalnızca açıkça kaydedilmiş gerçek JSON arşivlerinden farklı takvim günü sayar. **Saatlik/günlük otomatik tarama oluşturulmaz.** Başarılı “2 gün gözlendi” sonucu da piyasa kârlılığı, anlık yürütülebilir fiyat ya da uzun dönem tedarikçi sürekliliği kanıtı değildir.

**Dağıtım, merge, canlı/paper emir, otomatik fill, kaldıraç ve scheduler kapalı.**
