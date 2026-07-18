# Sözlük hedef-dil guard'ı: denylist → sözlük-seviyesi reddi

**Analiz:** Opus 4.8, 2026-07-16 · **Uygulayacak:** Sonnet 5
**Taban:** 1354 test yeşil

## Olan olay

The Blood of Hussain (ana model gpt-5.4, yardımcı gpt-5.4-mini): analiz geçişinin ürettiği 13 terimlik sözlük **Somalice** çıktı.

| Kaynak | Sözlüğün verdiği | Doğrusu |
|---|---|---|
| Armed Forces | `Qawweyaha Xoogga Dalka / ciidamada qalabka sida` | Silahlı Kuvvetler |
| President | `madaxweynaha` | Başkan |
| World Bank | `Bangiga Adduunka` | Dünya Bankası |
| Muezzin | `mu'addinka` | Müezzin |
| martial law | `martial law` | sıkıyönetim |
| Caliph | `khalifa` | halife |

Ana model **suçsuz** — sözlüğe sadık kaldı, nesri baştan sona temizdi. `ht.build_system_prompt:2369-2375` zaten `## MANDATORY TERM TRANSLATIONS ... no substitutions allowed` diyor. Sözlük yanlıştı, model doğru davrandı.

**Parmak izi:** aynı yanlış dize üç ayrı chunk'ta byte-byte aynı. Cue-başına halüsinasyon böyle davranmaz.

## Kök neden: guard bir denylist

`non_turkish_leak_token` (`hybrid_translate.py:4105-4133`) üç kural işletiyor, üçü de Somalice'yi geçiriyor:

1. `_FOREIGN_SCRIPT_RE` (`:3772`) — yalnızca Kiril/Arap/Devanagari/Tamil/CJK. Somalice **saf Latin** → geçer.
2. `_TURKIC_DRIFT_RE` (`:3744-3756`) — elle yazılmış Türkmen/Özbek/Azeri **kelime listesi**. Somalice kelime yok → geçer.
3. Latin-extended diakritik taraması (`:4119`) — Somalice imlası **tamamen ASCII**, `_LATIN_EXTENDED_CHAR_RE` eşleşmez → `return None` ile **erken çıkar**.

> Guard "bilinen kötü dile benziyor mu?" diye soruyor. Sorması gereken: "Türkçe'ye benziyor mu?" Denylist olduğu için **listede olmayan her dil sızar** — Somalice, Endonezce, Svahili, Filipince…

## Tasarım kararı: sözlük-seviyesi reddi

**Terim-başına tespit yetmez.** Ölçüm: 4 Somalice terimden yalnızca 2'si w/q/x taşıyor (`madaxweynaha`, `Qawweyaha`); `Bangiga Adduunka` ve `mu'addinka` hiçbir deterministik kuralı tetiklemiyor.

**Ama hata tek terim hatası değildi — sözlüğün tamamı dil değiştirmişti.** Bu gözlem çözümü veriyor:

> **Sözlükteki HERHANGİ bir terim açıkça Türkçe değilse, SÖZLÜĞÜN TAMAMINI at.**

Gerekçe: yardımcı model terim çıkarımı alt-görevinde hedef-dil çıpasını topluca kaybediyor (liste-şeklinde çıktı, cümle bağlamı yok). Bir terim çöktüyse hepsi çökmüştür. Sözlüğü atmanın maliyeti **düşük** — model terimi serbest çevirir, ki "Armed Forces" için zaten "Silahlı Kuvvetler" der. Yanlış sözlükten iyidir.

---

## Uygulama

### Adım 1 — `hybrid_translate.py:4105` `non_turkish_leak_token`: pozitif sinyal ekle

Mevcut üç kuralı **koru** (mevcut testler yaşasın), dördüncüyü ekle:

**R_wqx:** Türk alfabesinde `q`, `w`, `x` **yoktur**. Hedef terim bu harfleri içeriyorsa Türkçe değildir.

Uyarılar:
- `find_garble_tokens` R2_wqx_token (`:3974-3981`) aynı fikri zaten uyguluyor ama `tok[:1].isupper()` (`:3979`) ile büyük harfle başlayanları **atlıyor** (özel isim varsayımı). `Qawweyaha` bu yüzden kaçtı.
- Sözlük **hedefleri** için bu atlama gevşetilmeli: **çok kelimeli** bir hedefte w/q/x varsa özel isim değil, yabancı dildir. Tek kelimeli + büyük harfli hedef (gerçek özel isim: `Washington`, `Xavier`) atlanmaya devam etsin.
- Meşru istisnalar: `taxi` yok (Türkçe "taksi"), ama marka/özel isimler (`WhatsApp`, `Xerox`) olabilir → tek-kelime+büyük-harf istisnası bunu karşılıyor.

### Adım 2 — `sanitize_glossary_for_turkish` (`:4141`): sözlük-seviyesi reddi

Şu an terim-başına eliyor. Yeni davranış:

```python
def sanitize_glossary_for_turkish(glossary, target_language="tr"):
    # 1) Hedef dil Türkçe değilse dokunma (guard Türkçe'ye özgü)
    # 2) Her terimi mevcut kurallardan geçir
    # 3) YENİ: şüpheli terim sayısı eşiği aşarsa TÜM sözlüğü at
```

Eşik: **≥1 terim açıkça yabancıysa (R_wqx) TÜM sözlüğü at.** Tek bir kesin sinyal yeterli — çünkü toplu çökme gözlendi ve atmanın maliyeti düşük.

Atarken **log'la** (Adım 4).

> `sanitize_glossary_for_turkish` şu an **`target_language` parametresi almıyor**, Türkçe hard-coded. İmzaya opsiyonel `target_language="tr"` ekle, varsayılan mevcut davranışı korusun. Çağrı yerleri: `:643`, `:1486`, `:1952`, `:2193`, `:2228`, `:2369`, `:3125`, `subtitle_translator_gui.py:2252`.

### Adım 3 — precontext yolunu kapat (KRİTİK BOŞLUK)

Keşif: **iki ayrı sözlük yolu var, biri hiç sanitize edilmiyor.**

| Yol | Fonksiyon | sanitize? |
|---|---|---|
| Hybrid (Yardımcı Analiz AÇIK) | `_analyze_context_openai_compatible` (`hybrid_translate.py:1836`) → `recurring_terms` | ✅ `:1952` |
| **Precontext** (Yardımcı Analiz KAPALI) | `analyze_file_precontext` (`subtitle_translator_gui.py:2723`) → `terms` | ❌ **hiç** |

Üç yer düzeltilecek:
1. `analyze_file_precontext` (`:2723`) — dönmeden önce `terms`'i sanitize et.
2. `build_precontext_hint` (`:2659-2664`) — `terms`'i **ham enjekte ediyor**; sanitize edilmiş hâli kullan.
3. `_update_series_memory_from_precontext` (`:9487`) — **sanitize etmeden series_memory'ye kalıcılaştırıyor.** En tehlikelisi bu: zehir diziler arası taşınır. Kalıcılaştırmadan önce sanitize et.

### Adım 4 — sözlüğü LOG'la (en ucuz, en değerli)

Şu an sadece sayı düşüyor (`subtitle_translator_gui.py:9471-9472`):
```python
self._log(f"[...] Ön-bağlam hazır — {n_char} karakter, {n_term} sabit terim", "ok")
```
İçerik **hiçbir yere** düşmüyor. Bu koşuda `.context_cache/` de boş kaldı → **sözlük sonradan incelenemedi**; teşhis ancak çıktıdaki tekrar eden dizeden çıkarsanabildi.

Ekle:
- Sözlük içeriğini log'la (13 terim = 1-2 satır, maliyet sıfır). Hem hybrid hem precontext yolunda.
- Guard bir terimi/sözlüğü **elediğinde** ne elendiğini `warn` seviyesinde log'la.

> Hybrid yolunda terim log'u **hiç yok** — ekle.

### Adım 5 — sessiz cache hatası

`.context_cache/` boş kalmasının sebebi: yazma **sessiz best-effort** (`subtitle_translator_gui.py:9461-9462`, `except Exception: pass`). Disk/izin hatası hiç görünmüyor.

`except Exception: pass` → `except Exception as e: self._log(..., "warn")`. Aynı deseni `save_context_cache` (`hybrid_translate.py:567`) için de kontrol et.

> Not: cache **kaynak dosyanın yanına** yazılıyor (`p.parent`), çıktı klasörüne değil — bu mevcut davranış, değiştirme.

---

## Testler

### Yaşamaya devam etmeli
- `tests/test_source_language_leftover.py:59` (Turkic drift), `:155` (`quality_glossary_for_source` kötü hedef filtresi) — **yeni guard için en yakın şablon, oku**
- `tests/test_glossary_matching.py:57, 90, 99`
- `tests/test_glossary_self_translation.py` — src==tgt koruması (özel isim geçişi meşru, bozma)
- `tests/test_garble_rules.py` — 6 kuralın tam kapsamı; R2'nin `isupper()` davranışını değiştirirsen **burası kırılabilir**, dikkat: `find_garble_tokens`'ı değil, sözlük guard'ını değiştir. İkisini ayrı tut.
- `test_analysis_depth.py:74`, `test_precontext_salvage.py`, `test_series_memory.py:95`

### Yeni testler (`tests/test_glossary_language_guard.py`)

```
test_wqx_target_rejected                    "Armed Forces"→"Qawweyaha Xoogga Dalka" elenir
test_lowercase_wqx_rejected                 "President"→"madaxweynaha" elenir
test_single_word_proper_noun_kept           "Washington"→"Washington" korunur (tek kelime+büyük harf)
test_whole_glossary_dropped_on_one_leak     1 Somalice terim → TÜM sözlük atılır
                                            (Bangiga Adduunka ve mu'addinka da gider — asıl kazanç)
test_clean_turkish_glossary_untouched       {"Armed Forces":"Silahlı Kuvvetler"} dokunulmaz
test_ascii_turkish_target_kept              "church"→"kilise" korunur (diakritiksiz Türkçe meşru)
test_precontext_terms_sanitized             precontext yolu artık sanitize ediyor
test_series_memory_not_poisoned             kirli terim series_memory'ye yazılmaz
test_non_turkish_target_language_skips_guard  target_language="de" → guard çalışmaz
```

**Asıl regresyon testi `test_whole_glossary_dropped_on_one_leak`** — tasarımın kalbi.

### Regresyon korpusu

`tests/regression_corpus/cases.jsonl` yapısı: `{file, cue, source, buggy, corrected, category, note}`.
Yeni kategori **`glossary_leak`** için 8 gerçek vaka hazır:

`C:\Users\K\AppData\Local\Temp\claude\D--Openai-Altyaz---evirisi\9748ef95-8539-4063-b343-cbf3bef12e58\scratchpad\bloodofhussain_cases.jsonl`

Bu dosyayı `cases.jsonl`'a **ekle** (üzerine yazma). İçindekiler: #36/#60/#377 (Armed Forces ×3), #83 (madaxweynaha), #65 (Bangiga Adduunka), #58 (martial law), #14 (khalifa) — `glossary_leak` ve `english_leak` kategorilerinde; #384 (`source_numbers`, ayrı brief'in konusu).

Sonra `baseline.json`'ı güncelle (`tools/build_regression_corpus.py`'a bak; `tests/test_regression_corpus.py:51, 65`). **Yeni vakalar yakalanmıyorsa baseline'a "yakalandı" diye YAZMA** — korpusun amacı gerçeği ölçmek. Yakalanmayanlar `caught_case_ids` dışında kalsın, rapor oranı düşsün.

---

## Doğrulama

1. `python -m unittest discover -s tests` → 1354 + yeni testler yeşil.
2. `python -m py_compile subtitle_translator_gui.py hybrid_translate.py`
3. Headless smoke: `python -c "import subtitle_translator_gui as g; a=g.App(); a.update_idletasks(); a.destroy(); print('OK')"`
4. **Gerçek sözlükle test:** aşağıdaki sözlüğü `sanitize_glossary_for_turkish`'e ver, **boş dönmeli** (tamamı atılmalı):
```python
{"Armed Forces": "Qawweyaha Xoogga Dalka / ciidamada qalabka sida",
 "President": "madaxweynaha", "World Bank": "Bangiga Adduunka",
 "Muezzin": "mu'addinka", "Karbala": "Kerbela"}
```
   Not: `Kerbela` temiz bir terim ama sözlük-seviyesi reddi onu da atar — **bu istenen davranış**, model onu zaten doğru çevirir.
5. Temiz sözlük dokunulmadan dönmeli:
```python
{"Armed Forces": "Silahlı Kuvvetler", "church": "kilise", "Washington": "Washington"}
```
6. Regresyon korpusu raporunda `glossary_leak` satırı görünmeli (oran ne çıkarsa çıksın, dürüst olsun).

## Raporla

- Hangi adımlar uygulandı/atlandı
- Test sayısı öncesi/sonrası
- Doğrulama 4 ve 5'in sonuçları
- Korpus raporunda `glossary_leak` kaç/kaç yakalandı
- Belirsiz/çelişkili madde — **tahmin yürütme, raporla.**
