# Brief: CPS/condense pass'ine güvenlik doğrulaması ekle — Sonnet 5 için (KOD)

Hazırlayan: **Opus 4.8** (analiz + tasarım kararı, 2026-07-08). Protokol: Opus hangi
validator'ların uygun olduğuna karar verir; **Sonnet 5 kodu uygular**. Bkz.
[[fable5-planning-protocol]], [[mini-main-model-quality-2026-07]].

## Amaç ve bağlam

`condense_fast_lines` (hybrid_translate.py:2662) CPS sınırını (>21-24 kar/sn) aşan satırları
**mini ile kısaltır**. Özellik dört akışa da bağlı (`_maybe_condense`) ama **KAPALI**
(`condense_var = BooleanVar(value=False)`). Neden kapalı: kısaltma çıktısında **hiçbir
kalite guard'ı yok** — mini kısaltırken sessizce sızıntı/typo/anlam-kaybı/negasyon-ters-dönmesi/
sayı-düşürme üretebilir; critic/polish'in aksine `validate_polish_candidate`'ten geçmiyor.
Bu her episodda 25-40 satırı etkiliyor (Explorer 1: 40, Socrates: 29). Bu brief condense'i
**güvenli** hale getirir → kullanıcı gönül rahatlığıyla açabilir.

**Mevcut guard (yetersiz):** condense yalnızca mekanik kontrol yapıyor (satır 2755-2761):
kısaldı mı + yeni_cps < eski_cps + yeni_cps ≤ limit. İçerik/kalite kontrolü YOK.

## TASARIM KARARI (kritik) — hangi validator'lar?

`validate_polish_candidate` (hybrid_translate.py:5652) çok kapsamlı ama condense'e OLDUĞU GİBİ
uygulanamaz: içinde **kısaltmayla ÇATIŞAN** kontroller var — condense kelime atmayı ve
kısaltmayı KASITLI yapar:
- ❌ `_has_content_word_loss` — kelime düşürmeyi reddeder → condense'in tam işini engeller
- ❌ `_has_destructive_shorten` ("too_short") — <%45 kısaltmayı reddeder → agresif ama meşru kısaltmayı engeller
- ❌ `_has_short_source_overexpansion` — konuyla ilgisiz

Bu yüzden **yeni, dar bir `validate_condense_candidate`** yaz — yalnızca GÜVENLİK-KRİTİK,
kısaltmayla çatışmayan alt-küme. Hepsi zaten hybrid_translate.py'de modül-düzeyinde mevcut
(validate_polish_candidate onları çağırıyor):

**DAHİL et (kısaltma sırasında bunların HİÇBİRİ meşru değildir):**
| Kontrol | Fonksiyon | Neden |
|---|---|---|
| Yeni hedef-dil sızıntısı | `has_non_turkish_target_leak(new)` (eski'de yokken) | kısaltma sızıntı EKLEMEMELİ |
| Eklenen typo | `_has_introduced_typo(old, new)` | çift-harf/bozuk token |
| Yabancı alfabe | `_has_foreign_script_backslide(old, new)` | Kiril/Yunan vb. |
| Model bozulması | `_POLISH_MODEL_CORRUPTION_RE` (eski'de yokken new'de) | garble deseni |
| Sayı düşürme | `_POLISH_NUMBER_RE` — eski'deki sayı new'de yoksa | "150 dolar"→"dolar" olmamalı |
| Negasyon kaybı | `_source_negation_requires_turkish_negation(src) and not _has_turkish_negation(new)` | anlam ters döner |
| Format etiketi | `_POLISH_FORMAT_RE.findall(old) != ...(new)` | `<i>` korunmalı |
| Köşeli-parantez etiketi | `_POLISH_BRACKET_LABEL_RE.findall(old) != ...(new)` | `[SFX]` korunmalı |
| Konuşmacı tire | `old.lstrip().startswith(("-","–","—")) != new...` | diyalog tiresi |
| İngilizce geri-kayma | `_has_english_backslide(old,new)` / `_has_new_english_residue(old,new)` | İngilizce sızıntı |
| Yeni içerik kelimesi (drift) | `_has_content_word_drift(old, new, source_text=src)` | condense EKLEME yapmamalı; kelime EKLİYORSA yeniden-yazım/uydurma |

**HARİÇ tut (condense'in işi):** `_has_content_word_loss`, `_has_destructive_shorten`,
`_has_short_source_overexpansion`, ve `linebreak_count` (condense satır sayısını meşru
değiştirebilir; line-break pass zaten sonradan çalışıyor).

**Dürüstlük notu:** kelime-KAYBI guard'ını bilerek dışarıda bıraktığımız için, condense'in
"anlamı koruyarak kısalttım" iddiası tam garanti edilemez — ama (a) prompt zaten İngilizce
kaynağı ('en') anlam çıpası olarak veriyor, (b) negasyon + sayı guard'ları en sert anlam
sapmalarını yakalıyor, (c) drift guard'ı uydurma/yeniden-yazımı yakalıyor. Bu, "hiç guard yok"
durumundan ÇOK daha güvenli. Kalan risk: ince (kritik olmayan) bir ayrıntının düşmesi.

## UYGULAMA

### 1. Yeni fonksiyon (hybrid_translate.py, `validate_polish_candidate`'in hemen yakınına)
```python
def validate_condense_candidate(original_text: str, candidate_text: str,
                                source_text: str = "") -> tuple[bool, str]:
    """condense_fast_lines için DAR güvenlik doğrulaması. validate_polish_candidate'in
    yalnızca güvenlik-kritik, KISALTMAYLA ÇATIŞMAYAN alt-kümesi — kelime-kaybı/çok-kısa
    kontrolleri BİLEREK yok (condense kelime atmayı kasıtlı yapar). fail-closed:
    (True,"") kabul, (False,reason) reddet → çağıran orijinali korur."""
    old = "" if original_text is None else str(original_text)
    new = "" if candidate_text is None else str(candidate_text)
    src = "" if source_text is None else str(source_text)
    if not new.strip():
        return False, "empty"
    if _POLISH_FORMAT_RE.findall(old) != _POLISH_FORMAT_RE.findall(new):
        return False, "format_tags"
    if _POLISH_BRACKET_LABEL_RE.findall(old) != _POLISH_BRACKET_LABEL_RE.findall(new):
        return False, "bracket_labels"
    old_numbers = _POLISH_NUMBER_RE.findall(old)
    if old_numbers:
        new_numbers = _POLISH_NUMBER_RE.findall(new)
        if any(n not in new_numbers for n in old_numbers):
            return False, "numbers"
    if old.lstrip().startswith(("-", "–", "—")) != new.lstrip().startswith(("-", "–", "—")):
        return False, "speaker_dash"
    if _has_english_backslide(old, new):
        return False, "english_backslide"
    if _has_new_english_residue(old, new):
        return False, "english_residue"
    if not _POLISH_MODEL_CORRUPTION_RE.search(old) and _POLISH_MODEL_CORRUPTION_RE.search(new):
        return False, "model_corruption"
    if _has_introduced_typo(old, new):
        return False, "introduced_typo"
    if _has_foreign_script_backslide(old, new):
        return False, "foreign_script"
    if not has_non_turkish_target_leak(old) and has_non_turkish_target_leak(new):
        return False, "non_turkish_target"
    if src and _source_negation_requires_turkish_negation(src) and not _has_turkish_negation(new):
        return False, "source_negation"
    if _has_content_word_drift(old, new, source_text=src):
        return False, "content_word_drift"
    return True, ""
```

### 2. condense_fast_lines'a bağla (hybrid_translate.py ~2754-2762)
Mevcut kabul bloğu:
```python
                pos = idx_to_pos[fid]
                old_idx, old_ts, old_text = result[pos]
                # Yalnızca gerçekten kısaldıysa uygula — uzatma/aynı kalma engellenir
                if len(short.replace('\n', ' ')) < len(old_text.replace('\n', ' ')):
                    # CPS kontrolü: kısaltma sonrası hala limitin altında mı?
                    old_cps = cps(old_text, _block_duration(old_ts))
                    new_cps = cps(short, _block_duration(old_ts))
                    if new_cps < old_cps and new_cps <= max(cps_limit, CPS_WARN_LIMIT):
                        result[pos] = (old_idx, old_ts, short)
                        total += 1
```
`result[pos] = ...`'ten HEMEN ÖNCE güvenlik doğrulaması ekle (mekanik guard'lar geçtikten
sonra). `en` kaynağı: `src_map.get(fid, "")` (src_map verilmişse). Reddedilenleri say + logla
(polish'in `_reject_reasons` deseni gibi):
```python
                    if new_cps < old_cps and new_cps <= max(cps_limit, CPS_WARN_LIMIT):
                        en_src = src_map.get(fid, "") if src_map else ""
                        ok, reason = validate_condense_candidate(old_text, short, en_src)
                        if not ok:
                            reject_counts[reason] = reject_counts.get(reason, 0) + 1
                            continue
                        result[pos] = (old_idx, old_ts, short)
                        total += 1
```
- Döngü başında `reject_counts = {}` tanımla (fonksiyon başında, `total = 0` yanında).
- Fonksiyon sonundaki log bloğuna (satır ~2768) ekle: `if reject_counts:` → 
  `log_fn(f"Kısaltma: {sum(reject_counts.values())} öneri güvenlik filtresinden döndü "
   f"({', '.join(f'{k}:{v}' for k,v in sorted(reject_counts.items()))})", "warn")`.

### 3. Test (`tests/test_condense_validation.py` — yeni)
`validate_condense_candidate`'i doğrudan test et (API yok):
- Temiz kısaltma (kelime atılmış, sızıntı/typo yok) → `(True, "")` **kabul** (en önemli: meşru kısaltma REDDEDİLMEMELİ).
- Yeni sızıntı ("...bäýram...") → `non_turkish_target` reddet.
- Eklenen typo ("ttek") → `introduced_typo` reddet.
- Sayı düşürme (old "150 lira", new "lira") → `numbers` reddet.
- Negasyon kaybı (src "I do NOT agree", old "katılmıyorum", new "katılıyorum") → `source_negation` reddet.
- Yeni içerik kelimesi (old→new'de alakasız yeni kelimeler) → `content_word_drift` reddet.
- Format etiketi düşürme (old "<i>x</i>", new "x") → `format_tags` reddet.
- **Kelime-kaybı KABUL edilmeli**: old "çok uzun bir cümle, birçok gereksiz kelimeyle dolu",
  new "uzun bir cümle" (kelime düştü ama güvenli) → `(True, "")` — condense'in özü budur,
  loss guard'ı BİLEREK yok. (Bu test tasarım kararını kilitler.)

## Doğrulama (Sonnet)
1. `python -m py_compile hybrid_translate.py`
2. `python -m unittest tests.test_condense_validation`
3. Tam paket: `python -m unittest discover -s tests` (regresyon yok)
4. Headless smoke: `python -c "import subtitle_translator_gui as g; a=g.App(); a.update_idletasks(); a.destroy(); print('OK')"`

## KAPSAM DIŞI (dokunma)
- `condense_var` varsayılanını AÇMA — OFF kalsın. Bu brief condense'i GÜVENLİ yapar; açma
  kararı kullanıcının (önce bir gerçek dosyada test etmeli — validator'lar kaç öneri
  reddediyor logdan görülür). Kullanıcıya: "artık güvenli, /switch ile aç, bir dosyada dene".
- CPS eşiği (21/24) değişmez.
- `validate_polish_candidate`'e DOKUNMA (ağır kullanımda; ayrı fonksiyon yaz).
- Mevcut mekanik guard'ları (kısaldı-mı/cps) kaldırma — üstüne ekle.
