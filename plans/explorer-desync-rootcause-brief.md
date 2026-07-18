# Brief: Cue-desync kök nedeni + dedektör açığı — Sonnet 5 için (KOD düzeltmesi)

Hazırlayan: **Opus 4.8** (kök-neden analizi, 2026-07-08). Protokol: Opus analiz eder + brief
yazar; **Sonnet 5 kodu uygular**. Bkz. [[fable5-planning-protocol]], [[mini-main-model-quality-2026-07]],
[[json-repair-cue-shift-2026-07]].

Tetikleyen olay: Explorer 1 & 2 (Discovering Peru) çevirisi. F2 için 🚨 cue-hizalama uyarısı
çıktı, F1 için ÇIKMADI — ama her iki dosya da sistemik "cue-içerik kayması + tekrar" desync'i
içeriyor. İnceleme her şeyi kaynak VTT + final SRT'yi **timestamp** ile hizalayarak doğruladı
(timestamp'ler korunuyor → kesin kanıt).

---

## 1. İKİ KÖK NEDEN (özet)

**A. Dedektör açığı** — `detect_alignment_issues` (subtitle_translator_gui.py:3075) üç sinyale
sahip (number_shift, missing_dialogue, outlier_cluster). Baskın desync sınıfını —
**"komşu cue tekrarı"** (içerik öne kayıp yeniden hizalanırken bir satırı iki id'e yazma) —
HİÇBİRİ görmüyor: tüm id'ler mevcut, cue silinmiyor, sayı yer değiştirmiyor, uzunluk normal.
→ F1'in 6 desync bölgesi **sessizce** geçti (`detect_alignment_issues` F1'de **0 bulgu**).
Hatta düzelttiğimiz **Göbekli 2'de bile 3-4 desync bu yüzden kaçmıştı** (elle QA + eski dedektör).

**B. Üretim (mini kapasitesi + prompt izni)** — Model çeviriyi indeks-anahtarlı döndürüyor
(`[{"i":N,"t":...}]`, JSON_INSTRUCTION son satırı) ve uygulama modelin `i→t` eşlemesine
**körü körüne güveniyor** (her id'nin çevirisinin o id'nin KAYNAĞINA karşılık geldiğini
doğrulamıyor). Prompt, fragment-grup içinde "Türkçe'yi item id'lerine yeniden dağıt / yeniden
sırala" izni veriyor. Yoğun çok-cue'lu cümle + araya serpilmiş `[MUSIC PLAYING]` SDH cue'ları
(belgesel anlatımı) olduğunda mini: bir cümleyi daha AZ id'e sıkıştırıyor → "same count" için
boşalan id'leri SONRAKİ cümleyle dolduruyor (öne kayma) → yeniden hizalandığı yerde içeriği
**tekrarlıyor**. Ham yedekte de var → çeviri-aşaması hatası (polish/critic değil).
Explorer >> Göbekli çünkü belgesel = daha yoğun çok-cue cümle + daha çok SDH.

**Kanıt (F2 #451-484, en büyük):** timestamp'ler src=fin olduğu hâlde 00:28:25'te ekranda
"1586 raporu" yazıyor; o an sesde başka cümle var — o satır aslında 00:28:50'ye (kaynak #470)
ait. ~25 sn / 8 cue kalıcı desync; #485'te düzeliyor ve kuyruk (#477-484) #485-492'yi **ikinci
kez** çeviriyor.

---

## 2. FIX A (BİRİNCİL) — Dedektöre "komşu tekrar" sinyali ekle

**Neden birincil:** düşük risk, yüksek değer. 🚨'ı güvenilir yapar → bundan sonra F1-tipi
dosyalar sessizce geçmez; kullanıcı hangi bölgeleri elle düzelteceğini bilir.

**Dosya:** `subtitle_translator_gui.py`

1. En üste `import difflib` ekle (henüz yok — mevcut importlar: json, copy, math, re, time…).

2. `_align_visible` (satır ~3044) yakınına iki modül-düzeyi yardımcı ekle:
```python
def _align_ratio(a: str, b: str) -> float:
    return difflib.SequenceMatcher(None, a, b).ratio()

def _align_lcs_len(a: str, b: str) -> int:
    """En uzun bitişik ortak alt-dizi uzunluğu (kaynak-tekrarı guard'ı için)."""
    if not a or not b:
        return 0
    return difflib.SequenceMatcher(None, a, b).find_longest_match(0, len(a), 0, len(b)).size
```

3. `detect_alignment_issues` içinde, 3. sinyalden (outlier_cluster) SONRA, `return findings`'ten
ÖNCE 4. sinyali ekle. `seq` zaten `[(idx, _align_visible(tr))]` (satır 3092); `_key` zaten
tanımlı:
```python
    # 4) adjacent_duplicate — bir cue çevirisi yakın (±win) başka bir cue çevirisine ÇOK
    # benziyor AMA kaynakları benzemiyorsa: içerik 'öne kaymış' ve yeniden hizalanırken
    # tekrarlanmış (redistribution-desync imzası). number/length/missing sinyallerinin
    # GÖREMEDİĞİ sınıf — Explorer 1'in 6 bölgesi + Göbekli 2'nin 3-4 bölgesi bu yüzden
    # sessizceydi. Guard: kaynak da benziyorsa (refrain) ya da uzun ortak ifade
    # paylaşıyorsa ('within sight of Gobekli Tepe' gibi) TETİKLEME (yanlış-pozitif önler).
    _DUP_WIN, _DUP_TR, _DUP_SRC, _DUP_LCS = 8, 0.75, 0.60, 15
    dup_ids = []
    for _a in range(len(seq)):
        _ta = seq[_a][1]
        if len(_ta) < 12:
            continue
        for _b in range(_a + 1, min(_a + 1 + _DUP_WIN, len(seq))):
            _tb = seq[_b][1]
            if len(_tb) < 12:
                continue
            if _align_ratio(_ta.lower(), _tb.lower()) < _DUP_TR:
                continue
            _sa = _align_visible(src_map.get(seq[_a][0], "")).lower()
            _sb = _align_visible(src_map.get(seq[_b][0], "")).lower()
            if _sa and _sb and _align_ratio(_sa, _sb) >= _DUP_SRC:
                continue  # kaynak da tekrar → meşru
            if _align_lcs_len(_sa, _sb) >= _DUP_LCS:
                continue  # kaynaklar uzun ortak ifade paylaşıyor → meşru
            dup_ids.append(seq[_a][0]); dup_ids.append(seq[_b][0])
    if dup_ids:
        ids = sorted(set(dup_ids), key=_key)
        findings.append({"type": "adjacent_duplicate", "ids": ids,
                         "detail": f"{len(ids)} cue komşusuyla neredeyse aynı (içerik kayması/tekrar)"})
```

**Entegrasyon otomatik:** `scan_translation_quality` (satır ~3267) bulgu tiplerini ve id'leri
zaten generic topluyor (`types = sorted({f["type"]...})`, `all_ids.extend(f.get("ids", []))`),
o yüzden 🚨 mesajına yeni tip kendiliğinden akar — orada değişiklik GEREKMEZ.

**Ölçülen sonuçlar (bu ayarlarla, doğrulandı):** `scratchpad/test_dup_signal.py` çıktısı —
- Explorer 1: **5** bölge yakalandı (#136~137, #171~172, #208~213, #227~228, #669~670)
- Explorer 2: **7** (#262~270, #385~386, #397~398, #477~485, #478~486, #479~487, #683~684 — büyük desync kuyruğu dahil)
- Göbekli 2: **6** (#687~689, #688~690, #761~762/763, #889~890)
- **Göbekli 1 (düzeltilmiş, temiz): 0 yanlış-pozitif** ✓ (LCS guard olmadan #558~566 FP veriyordu; guard elediler)
- Not: nadir sınırda FP olabilir (kaynağın kendisi kısa kekelerse, örn. Göbekli2 #889/890
  "passed it on, passed it on?"). Warn-seviyesi "elle karşılaştır" bayrağı için kabul edilebilir.

**Test ekle** (`tests/test_alignment_detector.py`'ye — mevcut dosya):
- Sentetik: iki komşu cue AYNI TR, FARKLI kaynak → `adjacent_duplicate` bulgusu döner.
- Guard: iki komşu cue aynı TR, kaynak da aynı/çok-benzer → bulgu DÖNMEZ (refrain).
- Guard: kaynaklar uzun ortak ifade paylaşır (LCS≥15) → bulgu DÖNMEZ.
- Regresyon: temiz bir blok listesinde 0 bulgu.

---

## 3. FIX B (UCUZ ÖNLEME) — Prompt'a ID-bütünlüğü kuralı

**Dosya:** `prompt_constants.py`, `JSON_INSTRUCTION` (satır ~49). "DIALOGUE DASHES" kuralının
hemen ÖNÜNE veya sonrasına ekle:
```
"ID INTEGRITY: The translation at each \"i\" MUST be the translation of THAT id's own source "
"text \"t\". Do NOT shift a line's content onto a neighbouring id to fill space, and do NOT run "
"ahead by translating a later sentence early. NEVER output the same or near-identical Turkish "
"sentence for two different ids — if you catch yourself repeating a line, you have mis-aligned: "
"re-map each id to its own source. If one source sentence spans several ids, split the Turkish "
"across EXACTLY those ids, in order.\n"
```
**Not (CLAUDE.md kuralı):** sync ve hybrid sistem promptları hizalı kalmalı. `JSON_INSTRUCTION`
her iki akışta da kullanılıyorsa tek düzenleme yeter; DEĞİLSE (sync akışı kendi çıktı-format
talimatını üretiyorsa — `build_requests` / `_build_sync_system_prompt`'u kontrol et) aynı kuralı
oraya da ekle. Uygulamadan önce grep ile doğrula.

**Beklenti:** bu tek başına mini'yi tam durdurmaz (kapasite tavanı — whack-a-mole geçmişi),
ama öne-kayma/tekrar eğilimini azaltır. Asıl güvence Fix A (tespit) + Fix C (öz-onarım).

---

## 4. FIX C (SAĞLAM, TAKİP) — Öz-onarım: chunk-düzeyi tekrar-retry

**Fikir (hafızadaki ertelenen "self-healing detector"):** bir chunk çevrilip döndükten SONRA,
o chunk'ın KENDİ çıktısında Fix A'daki komşu-tekrar sinyalini çalıştır; tetiklerse chunk'ı
yeniden çevir (daha katı prompt ile veya daha küçük alt-parçaya bölerek). Böylece desync
yazılmadan önce onarılır.

**Nereye:** mevcut `_retry_hata` altyapısı (chunk'ları `has_non_turkish_target_leak` ile yeniden
deniyor) aynı kalıp — oraya "chunk içi komşu-tekrar" tetikleyicisi eklenebilir. Bu daha büyük/
riskli bir değişiklik; Fix A+B'den SONRA, ayrı bir turda ele alınmalı. Bu brief'te SADECE
tasarım notu; kod istenirse ayrı brief.

**Alternatif/ek (yapısal, orta risk):** `[MUSIC PLAYING]`/SDH cue'larını modele göndermeden ÖNCE
ayır (yalnız gerçek diyalogu çevir, SDH'yi sonradan yerine koy) — SDH cue'ları "yeniden dağıtım
boşluğu" olmaktan çıkar. Chunk yapısı/id sürekliliğini etkiler; dikkatli test ister. Opsiyonel.

---

## 5. DÜRÜSTLÜK NOTU — mevcut çıktılar hâlâ bozuk (kod düzeltmesinden AYRI)

- Bu brief **geleceği** düzeltir (tespit + önleme). **Explorer 1 & 2'nin mevcut çıktıları** hâlâ
  ~11 desync bölgesi içeriyor (ayrı karar bekliyor: elle düzelt / güçlü modelle yeniden çevir).
- **Göbekli 2** — "tamamlandı" sanılan dosyada elle QA'nın KAÇIRDIĞI desync'ler var (dedektör
  sinyali ortaya çıkardı): **#685-690** (NOORY/COLLINS değişimi 2 cue erken tekrar), **#760-763**
  (#761/762 tekrar). Kaynak (Portal .vtt) ile:
  - #686 "Birçok kişi 'Contact' filmini hatırlar." → kaynak #688; #687 "Neredeyse bir kod gibi"
    (kaynak #689) → #689'da TEKRAR; #688 "Evet, tam da olan bu" (kaynak #690) → #690'da TEKRAR.
    Doğru sıra: #685-690'ı kaynağa göre yeniden hizala.
  - #761 "Şey, bunu aslında pratikte denemeye çalışıyorum." → #762'de TEKRAR (kaynak #762-763'ün
    ayrı içeriği). 
  Bunları Fix A'lı dedektörü Göbekli 2 üzerinde çalıştırıp elle düzeltmek gerekir (ayrı iş).

---

## 6. UYGULAMA SIRASI (Sonnet)
1. **Fix A** (dedektör sinyali) + testler — birincil, düşük risk.
2. `python -m py_compile subtitle_translator_gui.py` + `python -m unittest tests.test_alignment_detector`.
3. Headless smoke: `python -c "import subtitle_translator_gui as g; a=g.App(); a.update_idletasks(); a.destroy(); print('OK')"`.
4. **Fix B** (prompt kuralı) — JSON_INSTRUCTION + sync akışı grep-doğrulaması.
5. Fix A'lı dedektörü Explorer 1/2 + Göbekli 2 final'leri üzerinde çalıştır; §2'deki id'lerin
   çıktığını doğrula (`scratchpad/run_detector.py` + `test_dup_signal.py` referans).
6. Fix C: bu turda UYGULAMA — yalnız tasarım notu bırak.

## 7. KAPSAM DIŞI (dokunma)
- Timecode / sıra numarası / credential dosyaları.
- Mevcut Explorer/Göbekli SRT içerik düzeltmeleri (bu brief KOD; içerik düzeltmesi ayrı karar).
- `_make_smart_chunks` chunk-boyutu değişiklikleri (risk yüksek, kanıt yok).
