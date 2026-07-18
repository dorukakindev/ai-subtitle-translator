# İki açık: sözlük gloss'ları + `half a hundred` yanlış ayrıştırması

**Analiz:** Opus 4.8, 2026-07-17 · **Uygulayacak:** Sonnet 5
**Taban:** 1417 test yeşil · **Dosya:** `hybrid_translate.py` (ikisi de)

İki bağımsız iş, aynı dosyada olduğu için tek brief. **Sırayla uygula**, ikisi arasında testleri çalıştır.

---

# BÖLÜM 1 — `half a hundred` doğru çeviriyi bayraklıyor (ÖNCELİK 1, bugün eklenen kodda regresyon)

## Ölçülen davranış

```python
ht._en_spelled_numbers('half a hundred')                    # → [100]   YANLIŞ (50 olmalı)
S = 'They are even as half a hundred moons\ncaught in a golden net.'
ht._spelled_number_mismatch(S, 'Altmış ay gibidir onlar,')  # → True    (hatalı çeviri, ama yanlış sebeple)
ht._spelled_number_mismatch(S, 'Elli ay gibidir onlar,')    # → True    ❌ DOĞRU ÇEVİRİYİ BAYRAKLIYOR
```

`half` tamamen yok sayılıyor, grup `hundred` = 100 diye çözülüyor.

**Bu yakalayamamaktan kötü:** Salome #921'in doğru düzeltmesi (`Elli ay`) şu an yanlış alarm üretiyor. Critic'e boşuna satır gidiyor ve validator'a güven aşınıyor.

Gerçek vaka: Salome #921 `They are even as half a hundred moons` — `half a hundred` = **50**. Çeviri `Altmış` (60) demişti, elle `Elli` yapıldı.

## Çözüm

`_en_spelled_numbers` / `_en_number_group_value` içinde `half`'ı ele al:

1. **`half a <çarpan>` → çarpan / 2.** `half a hundred` → 50, `half a thousand` → 500. Belirsizlik yok.
2. **Diğer her `half` kullanımı → o grubu ATLA (boş dön).** Tahmin yürütme:
   - `half the kingdom` → sayı sözcüğü yok, zaten `[]` (mevcut davranış doğru, koru)
   - `half a dozen`, `a score`, `two dozen` → `dozen`/`score` `_EN_NUMBER_WORDS`'te yok, `[]` dönüyor. **Böyle kalsın** — eklemek yeni risk açar, kazancı yok.
   - `one and a half hundred` gibi tuhaf yapılar → `[]`
3. Aynı mantığı `quarter` için **EKLEME** — gerçek vaka yok, kapsam dışı.

**Kritik:** Belirsizlikte `[]` dön. `_spelled_number_mismatch` kaynak boşsa hiç çalışmıyor, yani `[]` = "sessiz kal" = güvenli.

## Testler (`tests/test_spelled_numbers.py`'a ekle)

```
test_half_a_hundred                 'half a hundred' → [50]        ← ASIL REGRESYON
test_half_a_thousand                'half a thousand' → [500]
test_half_the_kingdom_ignored       'half the kingdom' → []
test_half_a_dozen_ignored           'half a dozen' → []            (dozen desteklenmiyor, kasıtlı)
test_921_correct_translation_passes S=#921 kaynağı / 'Elli ay gibidir onlar,'
                                    → mismatch False               ← ASIL REGRESYON
test_921_wrong_translation_caught   S=#921 kaynağı / 'Altmış ay gibidir onlar,'
                                    → mismatch True
```

## Doğrulama

1. `python -m unittest discover -s tests` → 1417 + yeni testler yeşil.
2. Yukarıdaki üç ölçüm satırını tekrar çalıştır: `[50]`, `True`, **`False`**.
3. **Salome tam dosya yanlış-pozitif taraması.** Düzeltilmiş dosyada `run_validators` ile `SPELLED_NUMBER_MISMATCH` alan cue'ları listele:
   - `C:\Users\K\Desktop\Salome.1972.ITALIAN.1080p.WEBRip.x264.AAC-[YTS.MX].srt` (kaynak, 983)
   - `C:\Users\K\Downloads\ÇIKTI\Salome.1972.ITALIAN.1080p.WEBRip.x264.AAC-[YTS.MX]\Salome.1972.ITALIAN.1080p.WEBRip.x264.AAC-[YTS.MX].srt` (düzeltilmiş, 983)
   - **Beklenen: 0 flag** (dosya artık doğru). Flag varsa listele — yanlış-pozitiftir.
4. Blood of Hussain regresyonu: `.srt` (385) vs kaynak (469). **Cue sayıları eşit değil** — SDH temizliği cue düşürdü. Naif index eşlemesi ANLAMSIZ sonuç verir; **zaman kodu tabanlı hizalama kullan** (önceki ajan bu yöntemi kurdu). #384 hâlâ yakalanmalı, yeni yanlış-pozitif olmamalı.

---

# BÖLÜM 2 — sözlük hedefinde gloss/talimat (ÖNCELİK 1)

## Ölçülen davranış

```python
ht.sanitize_glossary_for_turkish({
  'Caesar':        'Caesar (Sezar)',
  'Bembem':        'Bembem (özel ad, aynen korunacak)',
  'sister-in-law': 'görümce / yenge bağlama göre',
  'Tetrarch':      'Tetrarch (bölge hükümdarı)',
  'Armed Forces':  'Silahlı Kuvvetler',
})
# → 5 terimin 5'i de geçti. 0 elendi. ❌
```

Bugün eklenen q/w/x guard'ı bu sınıfı görmüyor (hiçbirinde q/w/x yok).

## Neden önemli — üç filmde üst üste çıktı

Analiz geçişi hedef alanına **çeviri değil, meta-yorum** yazıyor. Ana model bunu ya satıra basıyor ya da telafi etmeye çalışıyor:

| Film | Sözlük hedefi | Çıktıya etkisi |
|---|---|---|
| Ishanou | `Bembem (özel ad, aynen korunacak)` | basılmadı (şanslıyız), ama 4 cue'da başka gloss uydurdu |
| Ishanou | `görümce / yenge bağlama göre` | model "yenge"yi seçti (iyi çözdü) |
| **Salome** | (sözlük kayıp, çıktıdan çıkarsandı) | **15 cue'da gloss**: `Caesar'ın (Sezar)` ×6, Tetrarch için **üç ayrı** gloss |
| Blood of Hussain | `Qawweyaha Xoogga Dalka / ciidamada qalabka sida` | 3 cue'da birebir basıldı |

**Salome'deki `Caesar'ın (Sezar)` kalıbı kök nedeni ele veriyor:** sözlük modele "Caesar'ı çevirme" dedi, model uydu ama okuyucuya acıyıp Türkçesini parantezle ekledi — hem de tutarsız biçimde (bazı cue'larda `Caesar`, bazılarında `Sezar`, bazılarında ikisi).

> Blood of Hussain'in Somalice dizesi de aynı eğik çizgili "iki seçenek" kalıbındaydı. Muhtemelen üçü tek sınıf: **model hedef alanına karar veremediğinde oraya seçenek/açıklama yazıyor.**

## Çözüm: yapısal red

`sanitize_glossary_for_turkish` içine, mevcut kuralların yanına:

**Bir hedef şunlardan birini içeriyorsa o TERİM sözlükten atılır:**
1. Parantez: `(` veya `)`
2. Eğik çizgi ayırıcı: ` / ` (boşluklu — seçenek ayırıcısı)
3. Köşeli parantez: `[` veya `]`

**Politika farkı — DİKKAT:** Bu kural **yalnızca o terimi** atar, **tüm sözlüğü DEĞİL.** q/w/x kuralından farklı; orada tüm sözlük atılıyordu çünkü toplu dil çökmesiydi. Burada model Türkçe üretmiş, sadece karar verememiş — diğer terimler sağlam olabilir. Bu ayrımı koda yorum olarak yaz.

### Kurtarmaya ÇALIŞMA
`Caesar (Sezar)` → hedef "Caesar" mı "Sezar" mı? `görümce / yenge bağlama göre` → hangisi? **Belirsiz.** Terimi atmak güvenli: model serbest çevirir ve zaten doğrusunu yapar (Salome'de sözlüksüz cue'larda `Sezar` demiş). Yanlış sözlükten iyidir.

### Yanlış-pozitif riski
Meşru bir terim hedefinde parantez/eğik çizgi olması pratikte yok — terim karşılığı tek bir ifadedir. Yine de:
- Eğik çizgi kuralı **boşluklu** ` / ` olsun; `AC/DC`, `24/7` gibi bitişik kullanımlar elenmesin.
- **Kaynak** tarafındaki parantezlere dokunma; kural yalnızca **hedef** için.

### Log
Elenen terimi ve gerekçesini `warn` seviyesinde log'la — bugün eklenen sözlük log'lamasının yanına. Kullanıcı analiz bitince sözlüğü okuyor; ne elendiğini görmeli.

## Testler (`tests/test_glossary_language_guard.py`'a ekle)

```
test_paren_gloss_target_dropped        {'Caesar':'Caesar (Sezar)'} → terim atılır
test_instruction_target_dropped        {'Bembem':'Bembem (özel ad, aynen korunacak)'} → atılır
test_slash_options_target_dropped      {'sister-in-law':'görümce / yenge bağlama göre'} → atılır
test_bracket_target_dropped            {'X':'Y [açıklama]'} → atılır
test_clean_terms_survive_alongside     {'Caesar':'Caesar (Sezar)', 'Armed Forces':'Silahlı Kuvvetler'}
                                       → yalnız 'Armed Forces' kalır  ← POLİTİKA TESTİ (tüm sözlük atılmaz)
test_tight_slash_not_dropped           {'band':'AC/DC'} → KALIR (boşluksuz eğik çizgi)
test_wqx_still_drops_whole_glossary    Somalice terim → TÜM sözlük atılır (eski politika bozulmadı)
```

**En kritik ikisi:** `test_clean_terms_survive_alongside` (iki politikanın ayrıldığını kilitler) ve `test_wqx_still_drops_whole_glossary` (eski davranış korunuyor mu).

## Doğrulama

1. `python -m unittest discover -s tests` → yeşil.
2. Yukarıdaki 5 terimlik ölçümü tekrarla: 4 terim elenmeli, `Armed Forces → Silahlı Kuvvetler` kalmalı.
3. Somalice sözlük hâlâ **tamamen** atılmalı (politika ayrımı korunuyor mu):
```python
{'Armed Forces':'Qawweyaha Xoogga Dalka / ciidamada qalabka sida','President':'madaxweynaha','Karbala':'Kerbela'}
# → {} (boş)  — hem eğik çizgi hem q/w/x var; wqx politikası kazanmalı
```
4. Temiz sözlük dokunulmadan geçmeli: `{'Armed Forces':'Silahlı Kuvvetler','church':'kilise','Washington':'Washington'}`
5. Gerçek Ishanou önbelleğiyle test — sözlük diskte duruyor:
   `C:\Users\K\Desktop\.context_cache\Ishanou AKA The Chosen One (1990) (1080p BDRip x265 10bit EAC3 2.0 - timesuck).json`
   `recurring_terms` (28 terim) guard'dan geçir. **Beklenen: `Bembem`, `Tampha`, `Dhanabir` (üçü de "(özel ad, aynen korunacak)") ve `sister-in-law` elenir; kalan ~24 terim sağlam kalır.** Gerçek sayıyı raporla.

---

## Raporla

- Bölüm 1 ve 2 ayrı ayrı: uygulandı mı, atlandı mı, neden
- Test sayısı öncesi/sonrası (1417 → ?)
- **Bölüm 1 Doğrulama 2 ve 3'ün sonucu** (özellikle `Elli` artık False dönüyor mu, Salome'de 0 flag mi)
- **Bölüm 2 Doğrulama 5'in sonucu** (Ishanou'nun gerçek 28 terimlik sözlüğünden kaç terim elendi, hangileri)
- Belirsiz/çelişkili madde — **tahmin yürütme, raporla.** (Bugün üç kez bunu doğru yaptın; brief'imdeki apostrof açığını ve yanlış sayı tahminlerini sen buldun. Aynı şekilde devam et.)
