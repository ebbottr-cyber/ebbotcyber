# EBBot — Türkçe raporda Çince metin denetimi

`scripts/audit_turkish_text_leaks.py` salt-okunur çalışır. Türkçe şablon seçimindeki bilinen sapmaları denetler; tüm kaynak kodu ve raporlar için eksiksiz bir dil güvenliği garantisi vermez.

```sh
python -m scripts.audit_turkish_text_leaks
python -m scripts.audit_turkish_text_leaks --include-candidates
python -m scripts.audit_turkish_text_leaks --report /path/to/turkish-report.json
python -m pytest -q tests/test_turkish_text_leak_audit.py
```

Çince dil sözlüğü, iç kod anahtarları, özgün şirket isimleri ve ham sağlayıcı verileri korunmalıdır. Türkçe olarak işaretlenmiş raporda kullanıcıya görünen alanlardaki Han karakterleri ayrıca gözden geçirilir. Kaynak envanteri tek başına bugünkü provider erişimini, model çıktısının Türkçeliğini veya raporun kârlılığını kanıtlamaz.
