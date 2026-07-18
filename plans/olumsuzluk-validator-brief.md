# Olumsuzluk validator'ı: emir kipini ve `yok` koşacını göremiyor

**Analiz:** Opus 4.8, 2026-07-17 · **Uygulayacak:** Sonnet 5
**Taban:** 1391 test yeşil

## Olan olay

Salome (1972), 983 satır. Güvenlik filtresi **63 öneriyi** `source_negation` gerekçesiyle reddetti (Critic 33 + Polish 30) ve Polish yalnızca **14/983** satır değiştirebildi.

Ölçüm: dosyada **44 cue** yanlış alarm veriyor — kaynakta olumsuzluk var, çeviri de doğru şekilde olumsuz, ama `_has_turkish_negation` çeviriyi olumsuz saymıyor.

**Yön güvenli tarafta** (yanlış metin üretilmedi) ama **gerçek iyileştirmeler engellendi.** Bu dosyaya özgü değil — Türkçede olumsuz emir her metinde var.

## Kök neden: iki ayrı boşluk

### Boşluk 1 — çıplak olumsuz emir (44 vakanın ~35'i, ASIL KÜTLE)

`_TURKISH_NEGATION_SUFFIX_RE`:
```
(?:(?:ma|me)(?:m|n|z|d[ıiuüi]|t[ıiuüi]|mış|miş|muş|müş|dan|den|s[ıi]n|l[ıi]|y(?:acağ|...))|(?:mı|mi|mu|mü)yor)\w*$
```

`(?:ma|me)` her zaman **zorunlu** bir ek grubuyla devam ediyor. Yani:
- `bakmadım`, `bakmayacak`, `bakmıyor` ✅ tanınıyor
- **`bakma`** (çıplak emir) ❌ tanınmıyor

Gerçek vakalar:
| Cue | Kaynak | Çeviri | Sorun |
|---|---|---|---|
| #70 | `Do not look at her` | `Ona bakma.` | `bakma` görünmüyor |
| #222 | `Come not near the chosen of the Lord.` | `Rabbin seçtiği kişiye yaklaşma.` | `yaklaşma` |
| #57 | `Rejoice not, O land of Palestine` | `Sevinme, ey Filistin toprağı,` | `Sevinme` |
| #94 | `Do not listen to thy mother's voice.` | `Annenin sesine kulak verme.` | `verme` |

> Bu metin Wilde uyarlaması — "Do not look at her" resmen nakarat. En sık kullanılan olumsuzluk biçimi, tam da görülmeyen biçim.

### Boşluk 2 — `yok` + koşaç (44 vakanın 9'u)

`_TURKISH_NEGATION_WORD_RE`:
```
\b(?:değil\w*|yok|hayır|hiç|hiçbir|hiçbiri|hiçkimse|asla|sakın)\b|\bne\b.{0,80}\bne\b
```

**Asimetri:** `değil\w*` joker almış, `yok` **çıplak** bırakılmış. Ölçüldü:

| Biçim | Tanınıyor mu |
|---|---|
| `değil`, `değildir`, `değildi`, `değilim`, `değilsin` | ✅ hepsi |
| `yok` | ✅ |
| `yoktur`, `yoktu`, `yokmuş`, `yoksa`, `yokum`, `yoksun`, `yoktular` | ❌ **hiçbiri** |

Bu dosyada 9 cue: `yoktur` ×8, `yoksa` ×1 (edebi register, `#6` `Başka aşk yoktur...`).

---

## Uygulama

### Adım 1 — `yok` koşaç biçimleri

`_TURKISH_NEGATION_WORD_RE` içindeki çıplak `yok`'u **sınırlı bir alternasyonla** değiştir:

```
yok(?:tur|tu|muş|sa|sam|san|sak|sanız|salar|sun|sunuz|um|uz|lar|ken|tular|tuk|tun|tunuz|muşuz|muşsun)?
```

> **`yok\w*` KULLANMA.** Aşırı eşler: `yokuş` (uphill), `yoksul` (poor), `yoksulluk`, `yokluk` — hiçbiri olumsuzluk değil.
>
> Sınırlı alternasyon + `\b` bunları doğal olarak eliyor: `yokuş`ta `uş` alternasyonda yok → opsiyonel grup boş eşler → `yok` ile `uş` arasında `\b` tutmaz → eşleşme yok. Aynısı `yoksul` için (`sul` alternasyonda yok). **Bunu testle doğrula.**
>
> `yoksun` kabul ediliyor — "sen yoksun" (olumsuz) ile "yoksun bırakmak" (mahrum etmek) belirsizliği var ama risk düşük.

### Adım 2 — çıplak olumsuz emir (DİKKAT: tuzak var)

**Naif çözüm YANLIŞ.** `(?:ma|me)$` eklemek felaket olur:
`elma`, `sinema`, `tema`, `şema`, `krema`, `lokma`, `dogma`, `reklama` — hepsi `-ma/-me` ile bitiyor ve hiçbiri olumsuzluk değil.

**Doğru çözüm — Türkçenin SOV yapısını kullan:** olumsuz emir **tümce sonunda** durur, isim durmaz.

| Cümle | `-ma/-me` sözcüğü | Tümce sonu mu? | Karar |
|---|---|---|---|
| `Ona bakma.` | `bakma` | ✅ (nokta önü) | olumsuz ✅ |
| `Sevinme, ey Filistin toprağı,` | `Sevinme` | ✅ (virgül önü) | olumsuz ✅ |
| `Rabbin seçtiği kişiye yaklaşma.` | `yaklaşma` | ✅ | olumsuz ✅ |
| **`Elma ye.`** | `elma` | ❌ (`ye` var) | olumsuz DEĞİL ✅ |
| **`Kremayı getir.`** | — (`kremayı`, `-ma` ile bitmiyor) | — | olumsuz DEĞİL ✅ |

**Kural:** bir sözcük `-ma`/`-me` ile bitiyor **VE** hemen ardından noktalama (`.,!?;:…`) veya satır/dize sonu geliyorsa → olumsuzluk sinyali.

Uygulama notu: mevcut `_has_turkish_negation` sözcükleri `re.findall(r"[^\W\d_]+", ...)` ile ayırıp her birine SUFFIX_RE uyguluyor — bu **konum bilgisini kaybediyor**. Yeni kural için metni sözcüklere ayırmadan, konumu koruyan ayrı bir regex gerekir:
```
(?:\w*(?:ma|me))(?=[\s]*(?:[.,!?;:…"'’”)\]]|$))
```
Satır sonlarını da hesaba kat (`re.MULTILINE` veya `\n`).

> **Kalan risk (kabul edilebilir, ama not düş):** `Elma, güzel meyvedir.` → `Elma` virgül önünde, kural olumsuzluk sanır. AMA validator **yalnızca kaynakta olumsuzluk varsa** çalışıyor — böyle bir cümlenin kaynağı olumsuz olmaz, dolayısıyla kural hiç tetiklenmez. Kaynak-gütme bu riski pratikte kapatıyor.

### Adım 3 — `-siz` yoksunluk eki (OPSİYONEL, riskliyse ATLA)

Gerçek vaka #172: `If you want to live without cares` → `Dertsiz yaşamak istiyorsan`. Kaynakta `without` olumsuzluk sayılıyor, `-siz` eki tanınmıyor.

Eklenecekse: sözcük-sonu `-siz/-sız/-suz/-süz`, **sözcük uzunluğu > 4** (çıplak `siz` = "you", zamir; onu eleme).

> Bu ayrı bir kavramsal karar (yoksunluk = olumsuzluk mu?). Adım 1-2 zaten 44 vakanın 43'ünü çözüyor. **Riskliyse atla ve raporla.**

---

## Testler

### Yaşamaya devam etmeli
Tüm mevcut olumsuzluk testleri. `_has_turkish_negation`/`_source_negation_requires_turkish_negation` kullanan yerler: `hybrid_translate.py:4893`, `:6312-6313` (`validate_polish_candidate` → `source_negation`), `:6526` (`validate_condense_candidate`).

`tests/test_polish_safety.py` içinde `source_negation` reason'ını `assertEqual` ile kilitleyen testler var — **reason string'ini değiştirme**, sadece tespiti genişlet.

### Yeni testler (`tests/test_negation_forms.py`)

```
# Boşluk 1 — çıplak emir
test_bare_imperative_negation           "Ona bakma."        → olumsuz ✅
test_bare_imperative_before_comma       "Sevinme, ey ..."   → olumsuz ✅
test_bare_imperative_multiline          "Ona bakma,\nyalvarırım." → olumsuz ✅
test_noun_ending_in_ma_not_negation     "Elma ye."          → olumsuz DEĞİL  ← TUZAK TESTİ
test_noun_sinema_not_negation           "Sinema iyiydi."    → olumsuz DEĞİL  ← TUZAK TESTİ
test_krema_not_negation                 "Kremayı getir."    → olumsuz DEĞİL

# Boşluk 2 — yok koşacı
test_yoktur_is_negation                 "Başka aşk yoktur." → olumsuz ✅  ← ASIL REGRESYON
test_yoksa_is_negation                  "Yoksa gelme."      → olumsuz ✅
test_yokmus_is_negation                 "Kimse yokmuş."     → olumsuz ✅
test_yokus_not_negation                 "Yokuş çıktık."     → olumsuz DEĞİL ← TUZAK TESTİ
test_yoksul_not_negation                "Yoksul bir ülke."  → olumsuz DEĞİL ← TUZAK TESTİ
test_yokluk_not_negation                "Yokluğunda geldi." → olumsuz DEĞİL

# Uçtan uca — validator artık reddetmiyor
test_do_not_look_suggestion_accepted    src "Do not look at her." / new "Ona bakma."
                                        → validate_polish_candidate source_negation ile REDDETMEZ
test_genuine_negation_drop_still_caught  src "Do not look at her." / new "Ona bak."
                                        → HÂLÂ reddedilir  ← guard'ın işini yaptığını kilitler
```

**En kritik ikisi:** `test_noun_ending_in_ma_not_negation` (tuzak) ve `test_genuine_negation_drop_still_caught` (guard hâlâ çalışıyor mu).

---

## Doğrulama

1. `python -m unittest discover -s tests` → 1391 + yeni testler yeşil.
2. `python -m py_compile hybrid_translate.py`
3. **Gerçek dosya ölçümü — asıl kanıt.** Salome'de yanlış alarm sayısı **44 → 0'a yakın** düşmeli:
   - Kaynak: `C:\Users\K\Desktop\Salome.1972.ITALIAN.1080p.WEBRip.x264.AAC-[YTS.MX].srt`
   - Çeviri: `C:\Users\K\Downloads\ÇIKTI\Salome.1972.ITALIAN.1080p.WEBRip.x264.AAC-[YTS.MX]\Salome.1972.ITALIAN.1080p.WEBRip.x264.AAC-[YTS.MX].srt`
   - Ölç: `_source_negation_requires_turkish_negation(src[i])` **ve** `not _has_turkish_negation(tr[i])` olan cue sayısı.
   - Öncesi: 44. Sonrası: raporla. Kalan varsa **listele** — `-siz` sınıfı (#172) Adım 3 atlanırsa kalır, o beklenen.
4. **Yanlış-pozitif kontrolü (ters yön).** Aynı dosyada, kaynağı olumsuz OLMAYAN cue'larda yeni kuralın olumsuzluk uydurup uydurmadığına bak — `_has_turkish_negation` çağrısı validator dışında da kullanılıyor olabilir, sayıyı raporla.
5. Blood of Hussain dosyasında da ölç (`C:\Users\K\Downloads\ÇIKTI\The.Blood.Of.Hussain...\....srt`) — regresyon var mı.

## Raporla

- Hangi adımlar uygulandı/atlandı (Adım 3 atlanabilir)
- Test sayısı öncesi/sonrası
- **Doğrulama 3: Salome'de 44 → kaç?** Kalanların listesi.
- Doğrulama 4 ve 5'in sonuçları
- Belirsiz/çelişkili madde — **tahmin yürütme, raporla.**
