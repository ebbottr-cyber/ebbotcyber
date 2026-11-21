# EBBot — Türkçe yerelleştirme ve doğrulama durumu

Kaynak proje: [ZhuLinsen/daily_stock_analysis](https://github.com/ZhuLinsen/daily_stock_analysis). Lisans ve atıf korunmalıdır.

## Mevcut kapsam

- Arayüzde `tr` dil seçimi ve eksik alanlar için İngilizceye dönüş.
- Türkçe hisse raporlarında dil talimatları, bazı başlıklar ve etiketler.
- Nasdaq `AAPL` için çevrimdışı istek/simge yönlendirme regresyonları.
- ABD/HK/Japonya/Kore/Çin piyasa özeti şablonunda Türkçe istenince Çince şablona düşmeme kontrolü.
- `src/analyzer.py` Türkçe fiyat başlıkları ve `src/market_analyzer.py` Türkçe piyasa özeti başlığı.

## Açık doğrulama gereksinimleri

- Gerçek Yahoo AAPL tarihî fiyatı, gerçek bir LLM tarafından üretilen Türkçe açıklama ve kaydedilen raporun görsel denetimi henüz bu PR'da doğrulanmış değildir.
- Haberler, bildirimler, grafik etiketleri ve tüm ekran çevirilerinin Türkçe olması garanti edilmez.
- Fiyatı, tarihleri, sembolleri ve kaynak veriyi çeviri sırasında değiştirmeyin.
- BIST100, veri lisansı, Windows paketleme ve yayın yetkisi ayrıca incelenmelidir.

## Salt-okunur test

```sh
python -m pytest -q tests/test_turkish_market_recap_scaffold.py tests/test_turkish_text_leak_audit.py
python -m scripts.audit_turkish_text_leaks
python -m pytest -q tests/test_nasdaq_turkish_smoke.py tests/test_turkish_report_language.py tests/test_report_language.py tests/test_analyzer_prompt_language.py
```

İsteğe bağlı gerçek rapor denetimi: `python -m scripts.audit_turkish_text_leaks --report /path/to/turkish-report.json`.

Yerel API şeması örneği (gerçek analiz çağrısı değildir):

```json
{"stock_code":"AAPL","report_type":"detailed","report_language":"tr","notify":false,"async_mode":false}
```

Parola ve API anahtarı hiçbir zaman GitHub'a eklenmemeli. Devre dışı bırakılmış schedule/trade/workflow dosyaları değişmeden kalmalıdır.
