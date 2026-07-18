# Yazıyla yazılmış sayılar: tespit yolunu açmak

**Analiz:** Opus 4.8, 2026-07-16 · **Uygulayacak:** Sonnet 5
**Taban:** 1354 test yeşil

## Olan olay

The Blood of Hussain #384:

| | |
|---|---|
| Kaynak | `The true revolution happened\nfourteen hundred years ago` |
| Çeviri | `Gerçek devrim, on dört yüz yıl önce` |
| Doğrusu | `Gerçek devrim, bin dört yüz yıl önce` |

`on dört yüz` Türkçede anlamsız bir birebir kopya (1400 = "bin dört yüz").

## Kök neden — iki katman, ikisi de önemli

### Katman 1: hata öneri filtresinde DEĞİL, tespit yolunda

İki ayrı sistem var, karıştırılmamalı:

| Sistem | Ne yapar |
|---|---|
| `validate_polish_candidate` (`hybrid_translate.py:5973`) | **Öneri filtresi.** Kalite geçişinin önerdiği değişikliği kabul/ret eder. Ham çeviriye asla bakmaz. Log'daki "güvenlik filtresinden döndü" hep bundan. |
| `run_validators` (`hybrid_translate.py:4489`) | **Ham çeviri tarayıcısı.** Blokları gezip şüpheli satırları işaretler. Critic Pass girişinde çağrılır (`:6661`). |

**#384'ün akışı:** kaynak `"fourteen hundred years ago"` → `run_validators:4617` `_numeric_token_mismatch` çağırır → `src_nums == []` → `False` → `NUMBER_MISMATCH` eklenmez → satır şüpheli listesine **girmez** → **Critic Pass o satırı hiç görmez** → düzeltme önerisi üretilmez.

> Log'daki `source_numbers:1` sayacı **başka bir satıra** ait, #384 ile ilgisi yok. Öneri filtresine guard eklemek #384'ü ÇÖZMEZ. Asıl eksik `run_validators:4617` tarafındaki tespit.

### Katman 2: mevcut mantık korunma kontrolü, doğruluk kontrolü değil

```python
# hybrid_translate.py:4058
_NUMERIC_TOKEN_RE = re.compile(r"(?<![\w])[-+]?\d+(?:[.,:/-]\d+)*(?![\w])")

# hybrid_translate.py:4421-4431
def _numeric_token_mismatch(src_text, tr_text):
    src_nums = _normalized_numeric_tokens(src_text)
    if not src_nums:
        return False              # <-- #384 BURADA ÖLÜYOR
    ...  # multiset içerme: kaynaktaki her token çeviride de olmalı
```

`\d+` yalnızca **rakam** eşler. Ayrıca mantık "kaynaktaki token çeviride var mı" — yani kaynakta `1400`, çeviride `1400` olsa **geçerdi**. `on dört yüz` → `bin dört yüz` bu validator'ın kavram uzayında yok; yazıyla yazılmış sayı için **değer hesaplayan hiçbir şey yok** (Keşif 7: ne İngilizce ne Türkçe sayı sözcük listesi kodda mevcut).

---

## Tasarım: triyaj, düzeltme değil

Validator'ın işi **düzeltmek değil, satırı Critic'e yönlendirmek.** Yeni kural yalnızca `run_validators`'a bir `reason` ekler; LLM karar verir. Bu, yanlış-pozitif riskini minimuma indirir — kötü ihtimalde bir satır boşuna incelenir.

### TUZAK: "yüz" hem 100 hem *face*

Projede zaten bu yüzden `_has_head_to_face_regression` var (`hybrid_translate.py:5482`). Bu dosyada #6 `yüzünü yaralamış` geçiyor — naif bir Türkçe sayı-sözcüğü tarayıcısı orada yanlış alarm verir.

**Çözüm — kontrolü kaynağa gütle:** yeni kontrol **yalnızca kaynakta yazıyla sayı varsa** çalışsın.
- #6 kaynağı: `The sword of Yazid has scarred your face.` → yazıyla sayı yok → **kontrol hiç çalışmaz** → `yüzünü` incelenmez ✅
- #384 kaynağı: `fourteen hundred years ago` → yazıyla sayı var → kontrol çalışır ✅

Aynı tuzağın Türkçe akrabaları: `bir` (1 / "a"), `tek` (1 / "single"), `iki` … Kaynak-gütme bunları da büyük ölçüde susturur, çünkü `bir` neredeyse her cümlede geçer ama kaynağında `one` olması gerekir.

---

## Uygulama

### Adım 1 — İngilizce yazıyla-sayı çözümleyicisi

`hybrid_translate.py`'de `_NUMERIC_TOKEN_RE` (`:4058`) civarına:

```python
_EN_NUMBER_WORDS = {"zero":0,"one":1,...,"twenty":20,"thirty":30,...,
                    "hundred":100,"thousand":1000,"million":10**6,"billion":10**9}
# ayrıca: "a hundred", "a thousand"

def _en_spelled_numbers(text) -> list[int]:
    """Ardışık sayı sözcüklerini gruplayıp değere çevirir.
    'fourteen hundred' → [1400]; 'thirteen wounds' → [13];
    'twenty-five' → [25]; sayı sözcüğü yoksa []."""
```

Kurallar:
- Ardışık sayı sözcükleri **tek grup** sayılır, tire de birleştirir (`twenty-five`).
- Çarpan mantığı: `fourteen hundred` = 14×100. `two thousand` = 2×1000.
- Toplama: `one hundred twenty` = 100+20.
- `one`/`a` belirteç olarak da geçer (`one of them`) — **tek başına `one` grubu güvenilmez.** Yalnızca çarpan (`hundred`/`thousand`/…) içeren VEYA ≥2 sözcüklü VEYA >12 değerli grupları raporla; gerisini atla. Muhafazakâr davran.

### Adım 2 — Türkçe yazıyla-sayı çözümleyicisi

```python
_TR_NUMBER_WORDS = {"sıfır":0,"bir":1,...,"yirmi":20,...,
                    "yüz":100,"bin":1000,"milyon":10**6,"milyar":10**9}

def _tr_spelled_numbers(text) -> list[int]:
    """Aynı mantık. 'bin dört yüz' → [1400]; 'on dört yüz' → [1400] (14×100)
    veya çözümlenemezse [] — ikisi de #384'ü yakalar."""
```

> `on dört yüz` ne dönerse dönsün önemli değil: 1400 dönerse değer eşleşir ama **ifade yanlış** — bu yüzden Adım 3'te ayrıca *kanonik ifade* kontrolü var. `[]` dönerse zaten eşleşmez.

Ek: `yüz` sözcüğü **ek almışsa** (`yüzünü`, `yüzüne`, `yüzden`) sayı değildir → yalnızca tam sözcük eşle (`\byüz\b`). Aynısı `bir`/`bin` için.

### Adım 3 — `run_validators`'a yeni reason

`hybrid_translate.py:4617` civarında, mevcut `NUMBER_MISMATCH`'in **yanına** (üzerine değil):

```python
if _spelled_number_mismatch(orig_clean, text):
    reasons.append("SPELLED_NUMBER_MISMATCH")
```

`_spelled_number_mismatch(src, tr)`:
1. `src_vals = _en_spelled_numbers(src)`; boşsa → `False` (**kaynak-gütme, tuzak koruması**).
2. `tr_vals = _tr_spelled_numbers(tr)` + `tr` içindeki rakam token'ları.
3. `src_vals`'taki her değer `tr_vals`'ta yoksa → `True`.
4. **Kanonik ifade kontrolü:** değer eşleşse bile, Türkçe ifade kanonik değilse (`on dört yüz` ≠ `bin dört yüz`) → `True`. Kanonik üreteci: `_tr_number_to_words(1400)` → `"bin dört yüz"`; çeviride bu dizi geçmiyorsa flag.

> Adım 4 (kanonik kontrol) riskliyse **atla ve raporla** — Adım 1-3 tek başına #384'ü zaten yakalar (çünkü `_tr_spelled_numbers("on dört yüz")` ya `[]` ya da 14/100 ayrı değerler döner, 1400 gelmez).

### Adım 4 — `validate_polish_candidate`'a DOKUNMA (sıralama tuzağı)

`tests/test_polish_safety.py:160-167` reason string'ini `assertEqual` ile kilitliyor (`"source_numbers"`). `validate_polish_candidate` içine `source_numbers`'tan **önce** yeni guard eklersen bu test kırılır.

Bu brief `validate_polish_candidate`'a **hiç dokunmuyor** — yalnızca `run_validators` tespit yolunu açıyor. Öyle kalsın.

---

## Testler

### Yaşamaya devam etmeli
- `tests/test_polish_safety.py:160-167` — `source_numbers` reason'ı, rakamlı kaynak
- `tests/test_polish_safety.py:48` — ayrı `numbers` reason'ı (eski→yeni kaybı)
- `tests/test_source_language_leftover.py:397-404` — `run_validators` → `NUMBER_MISMATCH`, rakamlı

**Hiçbiri değişmemeli.** Yeni reason ayrı isimde (`SPELLED_NUMBER_MISMATCH`), mevcutların yanına ekleniyor.

### Yeni testler (`tests/test_spelled_numbers.py`)

```
test_en_parser_multiplier            "fourteen hundred" → [1400]
test_en_parser_simple                "thirteen wounds" → [13]
test_en_parser_hyphen                "twenty-five" → [25]
test_en_parser_no_numbers            "scarred your face" → []
test_en_parser_bare_one_skipped      "one of them" → [] (muhafazakâr)
test_tr_parser_canonical             "bin dört yüz" → [1400]
test_tr_parser_suffixed_yuz_ignored  "yüzünü yaralamış" → [] (TUZAK)
test_tr_parser_suffixed_bir_ignored  "birini gördüm" → []
test_384_regression                  "fourteen hundred years ago" / "on dört yüz yıl önce"
                                     → SPELLED_NUMBER_MISMATCH   ← ASIL TEST
test_384_corrected_passes            "fourteen hundred years ago" / "bin dört yüz yıl önce"
                                     → flag YOK
test_source_gated_no_false_positive  kaynakta sayı yok + çeviride "yüz" → flag YOK
test_digit_translation_accepted      "fourteen hundred" / "1400 yıl önce" → flag YOK
```

**Asıl regresyon testi `test_384_regression`.**

### Regresyon korpusu

`bloodofhussain_cases.jsonl` (scratchpad'de, sözlük brief'i ekliyor) içinde #384 vakası `source_numbers` kategorisiyle var. Sözlük brief'i önce uygulanıyorsa vaka zaten eklenmiş olur — **tekrar ekleme**, sadece `baseline.json`'ı güncelle.

---

## Doğrulama

1. `python -m unittest discover -s tests` → 1354 + yeni testler yeşil.
2. `python -m py_compile hybrid_translate.py`
3. **#384 gerçek vakası:**
```python
_spelled_number_mismatch("The true revolution happened\nfourteen hundred years ago",
                         "Gerçek devrim, on dört yüz yıl önce")   # True olmalı
_spelled_number_mismatch("The true revolution happened\nfourteen hundred years ago",
                         "Gerçek devrim, bin dört yüz yıl önce")  # False olmalı
```
4. **Tuzak vakası (yanlış-pozitif olmamalı):**
```python
_spelled_number_mismatch("The sword of Yazid\nhas scarred your face.",
                         "Yezid'in kılıcı\nyüzünü yaralamış.")    # False olmalı
```
5. **Yanlış-pozitif taraması — en önemlisi.** Gerçek dosyanın 469 cue'sunu tara ve kaç satırın `SPELLED_NUMBER_MISMATCH` aldığını raporla:
   - Kaynak: `C:\Users\K\Downloads\Yeni klasör (4)\The.Blood.Of.Hussain.English-WWW.MY-SUBS.CO.srt`
   - Çeviri: `C:\Users\K\Downloads\ÇIKTI\The.Blood.Of.Hussain.English-WWW.MY-SUBS.CO\The.Blood.Of.Hussain.English-WWW.MY-SUBS.CO.srt.bak` (hatalı hâl, #384 içinde)
   - **Beklenen: #384 flag'lenir.** Kaynakta yazıyla sayı geçen diğer cue'lar: #137 `thirteen wounds`, #139 `seventh day`, #140/#150 `tenth day`, #162 `thirteen wounds`, #71/#72 `ten years`/`twenty`, #384 `fourteen hundred`.
   - Bunlardan **#384 dışında flag alan varsa yanlış-pozitiftir** → sayısını ve satırlarını raporla. 2'den fazlaysa DUR, tasarımı gözden geçirmem gerekir.

> `seventh`/`tenth` **sıra sayıları** — Adım 1'in kapsamında değil (kardinal sayı çözümleyicisi). `_EN_NUMBER_WORDS`'e sıra sayısı EKLEME; kapsam dışı bırak, `run_validators` onları görmesin.

## Raporla

- Hangi adımlar uygulandı/atlandı (Adım 3.4 kanonik kontrol riskliyse atlanabilir)
- Test sayısı öncesi/sonrası
- Doğrulama 3, 4, 5'in sonuçları — **özellikle 5'teki yanlış-pozitif sayısı**
- Belirsiz/çelişkili madde — **tahmin yürütme, raporla.**
