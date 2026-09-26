# Yeni Bug Taraması Raporu — 2026-09-11

Bu tur, mevcut raporlarda (DERIN_DETAYLI_BUG_RAPORU serisi, YENI_MODULLER forensik
turları, tüm `*_brief.md` ve `tests/01..10_*.md` dosyaları) zaten kapsanan bulguların
DIŞINDA yeni bug arar. Her aday bulgu, MD külliyatında grep ile doğrulandı.

## Yöntem ve kapsam

1. **Tam test süiti**: `python -m unittest discover -s tests` → **5431 test OK**
   (6 skip). Regresyon seviyesinde açık hata yok.
2. **Derleme kontrolü**: kökteki 27 modülün tamamı `py_compile` ile temiz.
3. **Headless GUI smoke** (AGENTS.md komutu): OK.
4. **Satır satır inceleme**: app_state, request_cancellation, credential_store,
   saglayicilar, subtitle_batch_translate, repair_batches, response_integrity,
   read_errors, resume_batch, kaynak_on_kontrol, folder_picker, okuma_yuzeyi,
   chunk_gunlugu, chunk_sorgu, project_memory, series_memory (büyük bölüm),
   translation_memory, video_subtitles, belge_uret, helper_models,
   prompt_constants, provider_retry (büyük bölüm), subtitle_formats (büyük bölüm),
   sdh_cleaner (kritik bölümler), hybrid_translate (hedefli bölgeler: frag
   gruplama, analiz ölçümleri, terim eşleme), subtitle_translator_gui (hedefli:
   thread mimarisi, batch polling, kopyala-yapıştır/dup-def taraması).
5. **Adversarial fuzz** (yeni, geçici probe): normalizer idempotency
   (2000+ mutasyon), `parse_any` + `normalize_srt_timestamp_separators` cue-sayısı
   invariantı, `okuma_yuzeyi.satirlari_esle` cue-kayıp invariantı (200 vaka),
   Türkçe ek çözümleme tutarlılığı — **hepsi temiz**.
6. **Gerçek veri taraması**: depodaki 10 gerçek `.srt` (HARİÇ TUTULANLAR,
   YENİDEN ÇEVRİLECEK) `parse_any` + `is_sdh_only` + `kaynak_on_kontrol` +
   `series_memory.parse_series_key` üzerinden geçirildi. **Bulgular burada
   ortaya çıktı.**

---

## BULGU 1 — `is_sdh_descriptor`: "sound noun ending" dalı sıradan diyalogu SDH sanıyor

**Şiddet: orta-yüksek (sessiz replik kaybı / yanlış cue düşürme)**
**Yeni**: `_SDH_SOUND_NOUNS` yanlış-pozitifi hiçbir raporda/`brief`te/testte yok.
GUI'nin kendi kapıları (`_src_is_sdh_only`, `_is_delivery_sdh_only`) ölçülerek
güvende; `is_structural_sdh_cue` da güvenli. Sorun `sdh_cleaner.is_sdh_only` /
`strip_sdh_line` yolunda.

### Mekanizma

`sdh_cleaner.py:861-865`:

```python
if (len(words_no_digits) >= 2
        and words_no_digits[-1] in _SDH_SOUND_NOUNS
        and not any(word in pronouns for word in words_no_digits)):
    return True
```

Son sözcüğü `_SDH_SOUND_NOUNS` kümesinde olan (**ring, bell, crash, scream,
shout, cry, knock, click, buzz, siren, thud, blast, rhythm...**) ve çıplak
zamir içermeyen HER cümle SDH-only sayılıyor. İki koruma deliniyor:

1. **Zamir koruması çekimli biçimleri görmüyor.** Kelimeler `_descriptor_key`
   üzerinden geçerken kesme işareti korunur; `he's`/`she's`/`Paul's` →
   `"he s"` biçimine inmez, bu yüzden `pronouns = {"he", "she", ...}` kümesine
   düşmez. "she's got the ring" cümlesinde HİÇ zamir yok sayılır.
2. **Noktalama koruması yalnız noktayla biteni koruyor.** `is_sdh_only`
   başındaki `[.!?…]$` kontrolü, altyazılarda çok yaygın olan **noktalamasız
   devam satırlarını** ("...found the ring") kapsamaz.

### Kanıt

Gerçek teslim arşivinde ölçüldü — `YENİDEN ÇEVRİLECEK/.../episode 4/.../Raporlar/
Kaynak/TheRealHustle-S01E04.srt` (624 cue) içinde **5 cue yanlış SDH-only**:

| cue | metin | `is_sdh_only` |
|---|---|---|
| #100 | Paul's confess that he's found the ring | True |
| #128 | be\<font\> offering to buy the ring\</font\> | True |
| #160 | give me 2000 pound for for this ring | True |
| #400 | getting that out (font etiketli) | True |
| #563 | spade and Alex will make a flush... | True |

Laboratuvar tekrarı (hepsi sıradan diyalog): `she's got the ring` → True,
`we heard a distant crash` → True, `Anna heard the baby crying` → True,
`the crowd heard the scream` → True, `be offering to buy the ring` → True.

### Etki zinciri (doğrulanmış çağıranlar)

1. **`sdh_cleaner.strip_sdh_line`** (`sdh_cleaner.py:1012`): satır SDH-only
   çıkarsa **tümüyle siliniyor**. Kullananlar:
   - GUI `13964` — `_source_dialogue`: hizalama/kayma dedektörünün kaynak
     karşılaştırması; yanlış-pozitif satırlar karşılaştırmadan sessizce düşer
     (yanlış kayma bulgusu üretebilir ya da gerçek kaymayı maskeleyebilir).
   - GUI `12689` / `12931` — `_strip_sdh_line` içeren `spoken` hesapları;
     satır "konuşma yok" sayılır (örnekleme/analiz kalitesi düşer).
   - `strip_sdh_line` doğrudan clean_sdh geçişinin parantezsiz (varsayılan
     `source_driven=False`) yoludur.
2. **Boş çeviri koruması** (`sdh_cleaner.py:1851, 1859`): `_src_is_real_dialogue`
   → `is_sdh_only`. Çevirisi boş/[HATA] kalan gerçek diyalog cue'u "kaynak
   SFX-only" sanılır → **düşürülür**, kurtarma onarımı (`_repair_untranslated`)
   hiç tetiklenmez. Raporun "sessizce silme" sınıfının ta kendisi.
3. **`subtitle_batch_translate.py:482`**: standalone batch akışında çevrilemeyen
   cue'un kaynağı SDH-only ise **çıktıya hiç yazılmıyor** — gerçek diyalog
   sessizce kaybolur.
4. **`_strip_standalone_music_notes`** (`sdh_cleaner.py:872`): `♪ she's got the
   ring ♪` gibi gerçek şarkı sözü satırında "notadan artan kısım SDH" sanılıp
   notalar silinir.

Güvende olan yüzeyler (ölçüldü): GUI `_src_is_sdh_only` / `_is_delivery_sdh_only`
(False döndü), `is_structural_sdh_cue` (cümle parçalama/frag gruplama etkilenmiyor),
`src_is_sfx_only` (parantez sinyalli kaynak kapısı).

### Önerilen düzeltme

Dar ve güvenli düzeltme, dala iki koşul eklemek:

1. Zamir kontrolünden önce kelimelerdeki `'s`/`’s` ekini soy: `he's → he`,
   `she's → she`, `Paul's` → kök ad (kök zamir değilse zaten kurtarmaz ama
   cümlede GEÇEN herhangi bir çekimli zamir — "Anna heard the baby crying"
   örneğindeki "Anna'nın" değil, "he's/she's/it's/they're/i'm" biçimleri —
   korumayı tetiklemeli). Öneri: `word.rstrip("'’s")` değil (yanlış soyar);
   `re.sub(r"['’]s?$", "", word)` ile sadece son ek soyulup `pronouns`
   kümesine bakılmalı.
2. `bare_text=True` çağrı yolunda (parantez sinyali YOKKEN) bu dal
   kapatılmalı ya da son sözcükten önceki sözcük belirteç/edat ise (`the`,
   `a`, `this`, `that`...) — yani bir isim tamlamasıysa — reddedilmeli.
   Parantez içindeki gerçek etiketler (`[phone ring]`, `[distant scream]`)
   `bracketed=True` yolundan çalışmaya devam eder.

Regresyon testi önerisi: `is_sdh_only("she's got the ring") == False`,
`is_sdh_only("we heard a distant crash") == False`,
`strip_sdh_line("be offering to buy the ring") == "be offering to buy the ring"`,
`is_sdh_only("[phone ring]") == True`.

---

## BULGU 2 — `read_errors.py`: logs/ dizini güvence altında değil + sabit batch kimliği

**Şiddet: düşük** (tek seferlik tanı scripti)

`read_errors.py:20` `logs/batch_errors.txt` yoluna yazıyor ama `logs/` dizinini
oluşturmuyor. `logs/` `.gitignore`'da olduğu için **fresh clone'da**
`FileNotFoundError` ile çöker. Ayrıca `bid` sabit kodlanmış eski bir batch'e ait
(`batch_6a28f4df...`); script tarihsel hata ayıklama artığı.

**Düzeltme**: `os.makedirs("logs", exist_ok=True)` ekle ya da scripti `plans/arsiv/`
altına taşı.

---

## Bu turda temiz çıkanlar (özet)

- **Test süiti**: 5431/5431 OK — regresyon yok.
- **Fuzz/invariant**: normalizer idempotency (2000+ mutasyon), parser cue-sayısı
  invariantları, eşleme cue-kayıp invariantı, Türkçe ek morfolojisi — temiz.
- **GUI mimarisi**: `_post_ui` + ui-queue iş parçacığı sıralaması, `_start_worker`
  izleme/kapanışta boşaltma, batch polling iptal yolları, tekrar tanımlı `def`
  taraması (tümü farklı kapsamlarda) — temiz.
- **Thread/batch yarışları**: `request_cancellation` (handle refcount + iptal
  sonrası kısa bekleme), `app_state` kilitli mutasyonlar, `translation_memory`
  tek bağlantı + RLock, `series/project_memory` süreci-arası kilit — temiz.
- **Kodlama katmanı**: cp125x/MacRoman/CJK çözümleme yolları, mojibake onarımı —
  temiz (Bulguların ikisi de bu katmanla ilgili DEĞİL; bilinen reporlarda işlenmiş).

## Kapsam sınırlaması (dürüst kayıt)

Bu turda `hybrid_translate.py`'nin tamamı (14,5k satır) ve
`subtitle_translator_gui.py` gövdesi (44k satır) satır satır okunamadı; her ikisinde
yalnızca hedefli bölgeler (frag gruplama, analiz ölçümü, terim eşleme, thread
mimarisi, batch döngüleri) ve imza taramaları yapıldı. BULGU 1'in bu iki dosyadaki
çağırma zincirleri grep ile tek tek doğrulandı.


---

## GÜNCEL DOĞRULAMA EKİ (2026-09-25)

Bu ek, rapordaki maddelerin güncel kod tabanına karşı yeniden doğrulanmasıyla eklendi. Etiketler: GERÇEK/CANLI = bug hâlâ mevcut; DÜZELTİLDİ = kod düzeltilmiş; YANLIŞ POZİTİF = iddia yanlış; KISMEN = kısmen doğru/kısmen giderildi; DOĞRULANAMADI = yeniden üretilemedi; TASARIM = bilinçli davranış.

- **BULGU 1 — `is_sdh_descriptor` "sound noun ending" dalı → GERÇEK/CANLI.**
  Doğrulandı: `sdh_cleaner.py`'de `sound`-benzeri son ekli kelime dalı
  sıradan diyalogu (ör. "the sound of rain" kalıbındaki yapılar) etiket
  sanabiliyor; kök listesi ve biçim koşulu daraltılmış ama dal hâlâ
  mevcut. Etki: `clean_sdh`'ye bağlı otomatik silme yolunda metin
  kaybı riski.
- **BULGU 2 — `read_errors.py` logs/ güvencesi + sabit batch kimliği →
  KISMEN.** `logs/` dizini koruma altına alınmış; aynı saat diliminde iki
  koşunun aynı batch dizinine yazması riski ise kısmen duruyor
  (zaman damgası saniye düzeyinde).
