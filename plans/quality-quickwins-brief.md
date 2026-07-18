# Brief: Kalite quick-wins — first_seen kaldırma + batch analiz simetrisi (Sonnet 5)

Hazırlayan: **Opus 4.8** (Fable 5 analizinin kod-doğrulaması + genişletme, 2026-07-10).
Protokol: Opus doğrular + brief yazar, Sonnet uygular. İki bağımsız, düşük-riskli düzeltme.

## Bağlam / dürüst kalibrasyon
Fable 5'in "tüm pass'lere ortak PassContext" önerisini koda karşı doğruladım. Bulgular:
- Kullanıcının GERÇEK akışı `_run_sync_hybrid` **zaten** `analysis_result` geçiriyor
  ([subtitle_translator_gui.py:9856](subtitle_translator_gui.py:9856), 9873, 9890). Hibrit-batch
  (`_run_hybrid` 11312) ve resume (`_wait_batch_hybrid` 10437) de geçiriyor.
- YALNIZCA **düz-batch** yolu `_write_results` (10736/10748/10758) geçirmiyor.
Yani "asimetri" gerçek ama kullanıcının kullandığı yolu ETKİLEMİYOR → Görev 2 düşük-değer,
yalnız düz-batch'i düzeltir; yine de ucuz ve doğru olduğu için ekliyorum.

**Asıl değerli olan Görev 1** (first_seen): kullanıcının akışında da çalışan
`final_consistency_sweep`'i etkiler.

---

## GÖREV 1 (ASIL) — `final_consistency_sweep`'ten `first_seen` fallback'ini kaldır
Dosya: [hybrid_translate.py:6055](hybrid_translate.py:6055) `final_consistency_sweep`.

**Sorun:** Fonksiyonun iki dalı var:
- **Branch B** (majority sweep fix buldu, satır 6093-6118): her değişikliği
  `validate_polish_candidate` ile yeniden doğrular — GÜVENLİ, KALIR.
- **Branch A** (`if not fixes:`, satır 6063-6092): majority sweep hiçbir şey bulamayınca
  **ilk görülen çeviriyi** sonraki tekrarların üzerine yazmayı dener. Bu bağlam-KÖRDÜR:
  ```
  "Come on." → "Hadi ama."  /  "Yapma şimdi."  /  "Hadi gidelim."
  ```
  aynı kaynak farklı sahnede farklı çevrilebilir; `validate_polish_candidate` gate'i bu anlam
  farkını göremez. Üstelik Branch A tam da majority'nin ANLAŞAMADIĞI (yani bağlam-bağımlılığın
  en olası olduğu) durumda tetikleniyor. (Not: "Come on." 2 kelime olduğundan `min_words=3`
  gate'iyle zaten atlanır; ama ≥3 kelimeli bağlam-bağımlı ifadeler için risk gerçek.)

**Düzeltme:** Branch A gövdesini (6063-6092, `if not fixes:` bloğu — first_seen sözlüğü,
döngü, `return result, accepted`) tek satırla değiştir:
```python
    swept, fixes = consistency_sweep(cues, tr_blocks, log_fn=None, min_words=min_words)
    if not fixes:
        return list(tr_blocks), 0          # first_seen fallback kaldırıldı — bağlam-kördü
    # (Branch B aynen kalır: majority değişikliklerini validate_polish_candidate ile yeniden doğrula)
    result = list(tr_blocks)
    ...
```
Böylece majority-bazlı güvenli normalizasyon korunur; agresif ilk-görülen davranışı gider.

**Test** (`tests/test_final_consistency_sweep.py` — YENİ):
1. `test_no_majority_leaves_unchanged`: aynı kaynak 3 farklı çeviriyle (majority yok) →
   `final_consistency_sweep` HİÇBİRİNİ değiştirmemeli (eskiden first_seen'i dayatırdı).
2. `test_majority_still_normalizes`: aynı kaynak 3× "A", 1× "B" (≥3 kelime) → "B" "A"ya
   normalize edilmeli (Branch B çalışır).
3. `test_short_source_never_touched`: <3 kelimeli kaynak hiç değişmez.
4. Mevcut `consistency_sweep` testleri bozulmamalı.

---

## GÖREV 2 (İKİNCİL, düşük-değer) — düz-batch `_write_results`'e analiz-cache simetrisi
Dosya: [subtitle_translator_gui.py:10689](subtitle_translator_gui.py:10689) `_write_results`.

`_wait_batch_hybrid` (10426) analizi cache'ten geri yüklüyor:
```python
_analysis_result = ht.load_context_cache(str(_src_path),
    expected_target=tgt, expected_analysis_depth=self.analysis_depth_var.get())
```
`_write_results` bunu yapmıyor. Simetri için, dosya döngüsünde (`_src_cues` parse edildikten
sonra, ~10711 civarı) ekle:
```python
    _analysis_result = None
    try:
        _analysis_result = ht.load_context_cache(
            fp, expected_target=_tgt_lang,
            expected_analysis_depth=self.analysis_depth_var.get())
    except Exception:
        _analysis_result = None
```
Sonra üç pass çağrısına `analysis_result=_analysis_result` ekle:
- Critic (10736): `... tgt_lang=_tgt_lang, log_fn=self._log, analysis_result=_analysis_result)`
- Polish (10748): `... src_map=src_blocks, analysis_result=_analysis_result)`
- Native (10758): `... tgt_lang=_tgt_lang, log_fn=self._log, analysis_result=_analysis_result)`

**Davranış:** Düz-batch dosyasının cache'lenmiş analizi yoksa `load_context_cache` None döner →
bugünküyle AYNI (no-op). Yalnız daha önce analiz edilmiş dosyada bağlam kazanır. Sıfır regresyon
riski. (Glossary bu kapsamda YOK — ayrı konu, dokunma.)

**Doğrulama:** smoke + tam test paketi; `_write_results` imzası/çağrıları None-güvenli olmalı
(critic/polish/native `analysis_result=None`'ı zaten kabul ediyor — sync yolu None geçebiliyor).

---

## Genel doğrulama
1. `python -m py_compile subtitle_translator_gui.py hybrid_translate.py`
2. `python -m unittest tests.test_final_consistency_sweep` + mevcut consistency testleri
3. Tam paket: `python -m unittest discover -s tests`
4. Smoke: `python -c "import subtitle_translator_gui as g; a=g.App(); a.update_idletasks(); a.destroy(); print('OK')"`

İki görev BAĞIMSIZ — biri uygulanıp diğeri ertelenebilir. Öncelik: Görev 1.
