# Brief: Kayma dedektörü (5. sinyal) + Polish tek-karakter-silme garble guard'ı (Sonnet 5)

Hazırlayan: **Opus 4.8** (kod-doğrulaması + tasarım, 2026-07-10). Protokol: Opus tasarlar +
brief, Sonnet uygular. İki BAĞIMSIZ görev; ikisi de bu oturumun A/B'sinin ve Solve/Sun Kings
koşularının ortaya çıkardığı iki gerçek hata sınıfını hedefler. Görev 1 (kayma dedektörü) yüksek
değerli ama FP-riski var → eşikler konservatif + zorunlu negatif testler. Görev 2 (garble guard)
düşük risk ama KISMİ kapsam (dürüst gerekçe içeride).

---

## GÖREV 1 — Kayma dedektörü: `detect_alignment_issues`'a 5. sinyal `content_shift`
Dosya: [subtitle_translator_gui.py:3132](subtitle_translator_gui.py:3132) `detect_alignment_issues`.

**Neden:** Mevcut 4 sinyal, Sun Kings mini koşusundaki **31-cue saf-kayma** desync'inin yalnız
duplikasyon KUYRUĞUNU (#504/#508 adjacent_duplicate) yakaladı; **26-cue akıcı-ama-kaymış gövdeyi
(#480-506) kaçırdı** — çünkü saf kayma ne sayı-kaybı ne uzunluk-aykırılığı ne duplikasyon üretir,
sadece içerik id-ızgarasına göre N cue ötelenmiştir. Bu, dedektörün en büyük kör noktası.

**Fikir (sözlük gerektirmez):** Kaynak ve çeviride ORTAK kalan iki anchor türü var —
**sayılar** (`\d{2,}`) ve **özel isimler** (çeviride de büyük harfle korunan: Ptahshepses,
Niuserre, Khamerernebty, Abusir; Giza↔Gize gibi transliterasyon-yakını dahil). Her çeviri
cue'sundaki anchor'ları, aynı anchor'ı içeren EN YAKIN kaynak cue'suyla eşleştir → `offset =
src_pos - tr_pos`. Temiz/SOV dosyada offset ≈ 0 (±1) salınır; GERÇEK kayma bir pencere boyunca
**sürekli |offset| ≥ 2 (aynı işaret)** gösterir. Sun Kings #480-510'da anchor'lar yoğun
(Ptahshepses/Niuserre/Khamerernebty/Giza/Abusir + sayılar) → +2/+3 sabit offset net görünür.

**Uygulama (yeni saf helper + 5. finding bloğu):**
```python
_ALIGN_PROPER_RE = re.compile(r'(?<![.!?]\s)(?<!^)\b[A-ZÇĞİÖŞÜ][a-zçğıöşü]{3,}\b')
# (cümle-başı büyük-harf'i dışla — yalnız cümle-İÇİ özel isimler güvenilir anchor)

def _content_shift_regions(seq, src_map, window=6, min_offset=2, min_run=4):
    """seq: [(id_str, tr_visible)]; src_map: {id: kaynak}. Sürekli içerik ötelemesi
    olan bölgeleri döndürür — sayı+özel-isim anchor'ları üzerinden. Saf helper (test)."""
    # 1) Her kaynak cue'su için anchor kümesi (sayı + cümle-içi özel isim, casefold).
    def _anchors(text):
        nums = set(_ALIGN_NUMBER_RE.findall(text or ""))
        props = {m.casefold() for m in _ALIGN_PROPER_RE.findall(text or "")}
        return nums, props
    src_anchor = {}          # pos -> (nums, props)   (seq pozisyonuyla hizalı değil!)
    # src_map id-anahtarlı; seq ile aynı id sırasını kullan:
    id_to_pos = {sid: p for p, (sid, _tr) in enumerate(seq)}
    src_by_pos = {}
    for p, (sid, _tr) in enumerate(seq):
        src_by_pos[p] = _anchors(src_map.get(sid, "") or src_map.get(int(sid) if sid.isdigit() else sid, ""))
    # 2) Her çeviri cue'su için offset (aynı anchor'ı içeren en yakın kaynak pozisyonu).
    offsets = {}             # tr_pos -> signed offset (yalnız anchor eşleşen cue'lar)
    for i, (sid, tr) in enumerate(seq):
        t_nums, t_props = _anchors(tr)
        if not t_nums and not t_props:
            continue
        best = None
        for j in range(max(0, i - window), min(len(seq), i + window + 1)):
            s_nums, s_props = src_by_pos[j]
            if (t_nums & s_nums) or (t_props & s_props):
                if best is None or abs(j - i) < abs(best - i):
                    best = j
        if best is not None and best != i:
            offsets[i] = best - i
        elif best == i:
            offsets[i] = 0
    # 3) Sürekli |offset|>=min_offset, aynı işaret, >=min_run anchor'lı cue olan run'ları bul.
    flagged = set()
    anchored_positions = sorted(offsets)
    run = []
    for p in anchored_positions:
        o = offsets[p]
        if abs(o) >= min_offset and (not run or (o > 0) == (offsets[run[0]] > 0)):
            run.append(p)
        else:
            if len(run) >= min_run:
                flagged.update(range(run[0], run[-1] + 1))
            run = [p] if abs(o) >= min_offset else []
    if len(run) >= min_run:
        flagged.update(range(run[0], run[-1] + 1))
    return sorted({seq[p][0] for p in flagged}, key=lambda i: (0, int(i)) if str(i).isdigit() else (1, i))
```
Sonra `detect_alignment_issues` sonuna (adjacent_duplicate bloğundan sonra) ekle:
```python
    shift_ids = _content_shift_regions(seq, src_map, window=window)
    if shift_ids:
        findings.append({"type": "content_shift", "ids": shift_ids,
                         "detail": f"{len(shift_ids)} cue kaynağa göre sürekli kaymış (id↔içerik ötelemesi)"})
```
Ve `scan_translation_quality`'nin 🚨 mesajına `content_shift` type'ını da dahil et (mevcut
adjacent_duplicate/outlier'ı listeleyen yere ekle — grep'le bul).

**KONSERVATİF eşikler (FP kritik):** `min_offset=2` (±1 SOV'u ele), `min_run=4` (izole
eşleşmeyi ele), `window=6`. Tekrarlı isim (Ptahshepses ×20) sorunu **en-yakın-eşleştirme** ile
çözülür (offset her cue'da en yakın kaynak occurrence'ına göre; kaymış bölgede tutarlı çıkar).

**ZORUNLU testler (`tests/test_content_shift_detector.py` — YENİ):**
1. `test_sustained_shift_flagged`: sentetik — 12 cue, çeviri içeriği kaynağa göre +3 ötelenmiş,
   her cue'da bir özel isim/sayı anchor → `content_shift` bulgusu, doğru id aralığı.
2. `test_clean_1to1_not_flagged`: anchor'lar offset 0'da → bulgu YOK.
3. `test_sov_pm1_not_flagged`: anchor bir cue kaymış (±1, meşru SOV) ama sürekli değil → bulgu YOK.
4. `test_isolated_anchor_match_not_flagged`: yalnız 2-3 kaymış anchor (min_run altı) → YOK.
5. **GERÇEK-DOSYA negatif (kritik):** temiz gpt-5.4 Sun Kings çıktısı
   (`scratchpad/sunkings_gpt54.srt` mevcut) kaynağına karşı → `content_shift` bulgusu **OLMAMALI**
   (bu dosya temiz; #386 zaten benign SOV number_shift). Bu, FP-yok kanıtı.
6. **GERÇEK-DOSYA pozitif:** Sumerian `.bak` (#603-606 gerçek desync, regression corpus'ta) VEYA
   sentetik Sun Kings #480-510 eşlemesi → bölge flaglenir.

---

## GÖREV 2 — Polish tek-karakter-SİLME garble guard'ı (`_has_char_deletion`)
Dosya: [hybrid_translate.py:5839](hybrid_translate.py:5839) `_has_introduced_typo` yanına yeni
guard; [hybrid_translate.py:5982](hybrid_translate.py:5982) `validate_polish_candidate` içine wire.

**Neden + DÜRÜST kapsam:** Polish 3 dosyada tek-cue garble üretti — nihai→**ihai** (harf silme),
ahşap→**ohşap** (harf değişimi), sarayında→**sarasında** (orta-harf değişimi). `find_garble_tokens`
hiçbirini yakalamıyor; `_has_introduced_typo` yalnız İKİZLEME (tek→ttek) yakalıyor. **Kritik
tasarım kısıtı: Türkçe kelime listesi YOK** (projede yok, doğruladım). Sözlük olmadan DEĞİŞİM
(ahşap→ohşap) SİMETRİKtir — "ohşap→ahşap" meşru bir düzeltme mi yoksa "ahşap→ohşap" bozma mı
ayırt EDİLEMEZ (batdığını→battığını gibi gerçek polish-düzeltmelerini yanlışlıkla reddederiz).
Bu yüzden bu guard yalnız **ASİMETRİK, düşük-FP alt-sınıfı — tek-karakter SİLME** kapsar: polish
bir kelimeyi bir harf düşürerek KISALTIP korunmayan bir token'a çevirmişse reddet. (nihai→ihai
yakalanır; ahşap→ohşap ve sarasında YAKALANMAZ — bkz. §Kapsam-dışı.)

```python
def _has_char_deletion(old: str, new: str) -> bool:
    """new'de old'da olmayan, len>=4 bir token varsa VE bu token, old'daki bir
    token'dan TEK karakter silinerek elde ediliyorsa (nihai->ihai) reddet.
    ASİMETRİK: yalnız KISALMA yönünü yakalar — meşru düzeltmeler (kelimeye harf
    ekleme/orta düzeltme: batdığını->battığını) bu desene UYMAZ, FP üretmez."""
    if not old or not new:
        return False
    old_tokens = set(re.findall(r"[a-zçğıöşü]+", old.lower()))
    new_tokens = re.findall(r"[a-zçğıöşü]+", new.lower())
    for nt in new_tokens:
        if len(nt) < 4 or nt in old_tokens:
            continue
        # nt, bir old token'dan tek karakter silinerek mi oluşuyor?
        for ot in old_tokens:
            if len(ot) != len(nt) + 1:
                continue
            # ot'tan bir karakter silince nt olur mu? (tek-silme kontrolü)
            for k in range(len(ot)):
                if ot[:k] + ot[k+1:] == nt:
                    return True
    return False
```
`validate_polish_candidate` içinde `_has_introduced_typo` çağrısının hemen ardına
([hybrid_translate.py:5982-5984](hybrid_translate.py:5982) civarı, `_has_word_merge`'in yanına):
```python
    if _has_char_deletion(old, new):
        return False, "char_deletion"
```

**Testler (`tests/test_polish_char_deletion_guard.py` — YENİ):**
1. `test_first_char_deletion_rejected`: old "nihai statüsünü", new "ihai statüsünü" → reddedilir,
   reason "char_deletion".
2. `test_mid_char_deletion_rejected`: old "battığını", new "batığını" (orta 't' düştü) → reddedilir.
3. `test_legit_typo_fix_not_rejected`: old "batdığını", new "battığını" (harf EKLENDİ, kısalma yok)
   → GEÇER (bu guard'a takılmaz).
4. `test_normal_polish_not_rejected`: old "araştırıyor", new "inceliyor" (tamamen farklı kelime,
   silme deseni değil) → GEÇER.
5. `test_short_token_ignored`: 3 harfli token'lar (len<4 tabanı) tetiklemez.
6. `test_deletion_but_token_preserved_elsewhere_ok`: nt aynı zamanda old'da başka yerde varsa
   (nt in old_tokens) → GEÇER (gerçek kelime, tesadüf değil).

**Doğrulama:** `python -m unittest tests.test_polish_char_deletion_guard tests.test_polish_safety
tests.test_polish_conservative_mode` (mevcut polish testleri bozulmamalı — özellikle
batdığını→battığını gibi meşru düzeltmelerin hâlâ geçtiğini teyit et).

## §Kapsam-dışı (bilinçli, ayrı tur adayı)
- **Değişim garble'ı (ahşap→ohşap, sarasında)**: sözlük olmadan güvenli yakalanamaz (simetri
  sorunu). Gerçek çözüm: küçük bir **Türkçe kelime-sıklık listesi** paketleyip polish-değişen
  token'ları geçerliliğe karşı kontrol etmek — ayrı, daha büyük iş (yeni veri bağımlılığı). Bu
  brief bunu YAPMAZ; whack-a-mole kelime-listesi guard'ı da (memory'nin kaçınma tavsiyesi) EKLEME.
- ahşap→ohşap gibi vakalar şimdilik yalnız Görev 1'in kayma dedektörüyle DOLAYLI değil — onlar
  tek-cue, kayma değil; bilinçli olarak açık bırakılıyor.

## Genel doğrulama (her iki görev)
1. `python -m py_compile subtitle_translator_gui.py hybrid_translate.py`
2. İki yeni test dosyası + `tests.test_alignment_detector` + polish testleri yeşil.
3. Tam paket + headless smoke.
4. Regression corpus: `python -m unittest tests.test_regression_corpus` — `polish_garble`
   kategorisinde baseline DÜŞMEMELİ (ideali: char_deletion ekiyle `nihai/ihai` vakası artık
   yakalanıp sayı ARTAR — o zaman `REGEN_CORPUS_BASELINE=1` ile baseline'ı bilinçli güncelle).
