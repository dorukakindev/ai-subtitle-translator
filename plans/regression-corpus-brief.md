# Brief: Kalite regresyon corpus'u + runner (Sonnet 5)

Hazırlayan: **Opus 4.8** (Fable 5 önerisi #3/#4, 2026-07-10). Protokol: Opus planlar, Sonnet kurar.
Amaç: "1000 regex testi geçerken gerçek çeviri kalitesi gerileyebilir" riskini yakalamak — her kod
değişikliğinden sonra GERÇEK bozuk örnekler üzerinde otomatik denetim.

## Neden şimdi: altın veri zaten elimizde
Bu oturumda düzelttiğimiz her dosyanın üç sürümü var:
- **kaynak** (EN) — `E:\ALTYAZILAR\...` veya proje klasörü
- **`.bak`** — gpt-5.4-mini'nin ÜRETTİĞİ, tüm guard'lardan GEÇMİŞ bozuk çıktı
- **final** — elle doğrulanmış doğru çıktı

Yani her düzeltilmiş cue = `(source, buggy, corrected)` üçlüsü. Bilinen dosyalar/`.bak`'lar:
- John Dee (`...john-dee-...srt.bak`) — desync + leak
- Satan - Prince Of Darkness (`.bak`) — Satan/Jesus/#327 truncation
- Unearthed S08E09 Sumerian (`.bak`) — desync #603-606 + element leak
- Solve Et Coagula (`.bak`) — Polish garble (g geçtiğinde/dalı/Ulü) + element leak
- (Atlantis, Göbekli, Explorer — varsa `.bak`/plan kayıtları)

## Görev 1 — corpus'u üret (tek seferlik harvest script)
`tools/build_regression_corpus.py` (read-only): her `(kaynak, .bak, final)` üçlüsü için,
`.bak` ≠ final olan cue'ları çıkar ve `tests/regression_corpus/cases.jsonl` yaz. Her satır:
```json
{"file":"solve_et_coagula","cue":"442","source":"...","buggy":"g geçtiğinde",
 "corrected":"geçtiğinde","category":"polish_garble","note":"stray g introduced by polish"}
```
Kategoriler (bu oturumdan gerçek sınıflar): `desync`, `english_leak`, `element_leak`,
`polish_garble`, `truncation`, `term_inconsistency`, `mixed_term`, `negation`, `sov_falsepos`
(son biri: DEĞİŞMEMESİ gereken doğru SOV örnekleri — false-positive testi için).
Hedef v1: ~50-100 vaka. Elle küratörlük şart (her cue'yu doğru kategoriye koy).

## Görev 2 — runner: mevcut dedektörleri corpus'a karşı çalıştır
`tests/test_regression_corpus.py`: her vaka için `buggy` metnini mevcut deterministik
katmanlardan geçir ve YAKALANDI mı ölç:
- `ht.find_garble_tokens(buggy)` → boş değil mi? (`polish_garble`, `element_leak` beklenir)
- İngilizce-leak taraması (`english_leak`, `element_leak`)
- `gui.detect_alignment_issues` (dosya düzeyinde; `desync`/`adjacent_duplicate`)
- `ht.validate_polish_candidate(corrected, buggy, source)` → red mi? (polish-bozulmaları)
- `sov_falsepos` vakaları: `corrected` metni HİÇBİR guard'ı tetiklememeli (yanlış-pozitif regresyon).

Rapor:
```
Kategori           Yakalanan / Toplam
desync             6 / 8
element_leak       9 / 12   <-- 3 kaçak (ör. büyük-harf "Water" R2'ye takılmıyor)
polish_garble      2 / 5    <-- guard boşluğu
sov_falsepos       14 / 14  (hiçbiri yanlışlıkla flag'lenmedi ✓)
```
Bu test **başarısızlıkta düşmez** (çoğu vaka bilerek "henüz yakalanmıyor"); bunun yerine bir
**baseline sayısı** tutar. Kural: bir kod değişikliği baseline'ı DÜŞÜRÜRSE (daha az yakalama veya
yeni false-positive) uyarı ver. Böylece "regex ekledim, başka bir şeyi bozdum" görünür olur.

## Görev 3 (opsiyonel) — baseline kilidi
`tests/regression_corpus/baseline.json`'a kategori başına yakalama sayılarını yaz. Runner mevcut
sonucu baseline'la karşılaştırsın; herhangi bir kategori gerilerse `assertGreaterEqual` ile
FAIL etsin. İyileşme olursa baseline elle güncellensin (bilinçli).

## Değeri
- Yeni guard eklenince: gerçekten yeni vaka yakalıyor mu, eskiyi bozuyor mu — ölçülür.
- `sov_falsepos` vakaları: "doğru SOV'u yanlışlıkla bozma" regresyonunu yakalar (bu oturumda
  #563 "yaşamayı sürdürüyor" gibi tuzaklar).
- Grup-atomiklik / first_seen değişiklikleri sonrası: polish-garble vakalarının artık
  engellenip engellenmediği ölçülür.

## Doğrulama
1. `python tools/build_regression_corpus.py` → `cases.jsonl` üretir (cue sayısı raporlanır).
2. `python -m unittest tests.test_regression_corpus` → baseline raporu basar, yeşil geçer.
3. Tam paket bozulmamalı.

## Not
Bu bir INFRA görevi, kod-davranışı değiştirmez (read-only harvest + yeni test). Diğer iki
brief'ten (first_seen, grup-atomiklik) BAĞIMSIZ; onlardan ÖNCE kurulursa, onların etkisini de
ölçer (before/after).
