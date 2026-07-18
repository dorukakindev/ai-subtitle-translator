# Brief: Kalite paketi 2. tur — review bulguları düzeltmesi (Sonnet 5)

Hazırlayan: **Fable 5** (harici code-review bulgularının kod-doğrulaması, 2026-07-10).
Protokol: analiz modeli doğrular + brief yazar, Sonnet uygular. Önceki üç brief'in
(quickwins / group-atomicity / regression-corpus) review'ünde 5 bulgu çıktı; hepsi koda
karşı doğrulandı. Kayıt için: #3 (rapor cümlesindeki "54 gerçek + 6 FP" ifadesi) kod değil
iletişim hatasıydı — corpus 54 TOPLAM vakadır (48 bozuk + 6 sov_falsepos). Kod işi yok.

---

## GÖREV A — Native `src_map` simetrisi (tek satır, kesin)
[subtitle_translator_gui.py:10773](subtitle_translator_gui.py:10773) `_write_results` içindeki
`ht.native_reader_pass(...)` çağrısı `src_map` almıyor. Diğer 4 call site'ın HEPSİ alıyor
(8442: `src_map=_src_map_from_cues(orig_cues) if orig_cues else None`, 9904, 10464, 11353).
`native_reader_pass` fragment etiketlerini yalnız src_map varsa kurar → bu akışta Native
cümle-parçalarını tanımıyor.

**Düzeltme:** çağrıya `src_map=src_blocks` ekle (scope'ta zaten mevcut; `_src_cues`'ten
türetilen `{idx: _clean_src(text)}`). `analysis_result=_analysis_result` satırının yanına:
```python
                        tgt_lang=_tgt_lang, log_fn=self._log,
                        analysis_result=_analysis_result,
                        src_map=src_blocks)
```

## GÖREV B — Grup atomikliği v2: tam-üyelik + birleşik-anlam doğrulaması
`apply_polish_group_atomic` ([hybrid_translate.py](hybrid_translate.py), `validate_polish_candidate`
sonrası) şu an yalnız "dönen ve değişen üyelerden biri reddedilirse grubu geri al" kuralını
uyguluyor. İki açık kaldı:
1. Model grubun yalnız BAZI üyelerini döndürür ve dönenler geçerse → kısmi uygulama (eski
   bug'ın yanıt-eksikliği üzerinden geri gelmesi).
2. Cue'lar tek tek geçse bile birleşik cümle anlamı doğrulanmıyor.

**Düzeltme — helper imzasını genişlet (geriye-uyumlu):**
```python
def apply_polish_group_atomic(proposals, original_by_id,
                              group_expected=None, src_map=None):
```
- `group_expected`: `{group_id: [sid, ...]}` — grubun BEKLENEN üyeleri, **cue sırasında** ve
  yalnız `original_by_id`'de olanlar ([HATA] cue'ları items'a girmiyor, beklenmemeli).
  `None` → v1 davranışı (mevcut testler bozulmaz).
- `src_map`: `{sid: kaynak}` — birleşik-anlam kontrolü için; `None` → kontrol atlanır.

Değişen önerisi olan her grup için kural sırası:
1. (mevcut) değişen üyelerden biri per-cue reddedildiyse → grubu geri al.
2. (YENİ) `group_expected` verildiyse ve grubun beklenen üyelerinden herhangi biri
   `proposals`'ta YOKSA → grubu geri al; reason `group_atomic:partial_response`.
   (Cümle bütünlüğü ancak grubun tamamı görülerek doğrulanabilir.)
3. (YENİ) birleşik doğrulama: beklenen üyeleri cue sırasında birleştir —
   ```python
   old_joined = "\n".join(original_by_id[s] for s in expected)
   new_joined = "\n".join(proposals[s][0] if s in proposals else original_by_id[s]
                          for s in expected)
   src_joined = " ".join((src_map or {}).get(s, "") for s in expected)
   ok, reason = validate_polish_candidate(old_joined, new_joined, source_text=src_joined)
   ```
   `ok` değilse → grubu geri al; reason `group_atomic_joined:<reason>`.
   (Not: kural 1 per-cue linebreak sayısını zaten koruduğundan joined linebreak sayıları
   eşleşir — `linebreak_count` FP üretmez. Grup-düzeyi `content_word_loss` burada gerçek
   değer katar: kelime cue'lar ARASINDA taşınırsa grup toplamında kayıp yok → geçer;
   kelime tamamen DÜŞERSE → yakalanır.)
4. Hepsi geçerse değişen üyeleri uygula (mevcut).

**Call-site (`_polish_pass`, [subtitle_translator_gui.py](subtitle_translator_gui.py)):** chunk
kurulurken beklenen-üyelik haritasını üret ve helper'a geçir:
```python
group_expected = {}
for _idx, _ts, _text in chunk:
    _sid = str(_idx)
    if _sid not in original_by_id:
        continue
    _gid = frag_group_ids.get(_idx, frag_group_ids.get(_sid))
    if _gid is not None:
        group_expected.setdefault(_gid, []).append(_sid)
...
chunk_result, chunk_rejected, chunk_reasons = ht.apply_polish_group_atomic(
    chunk_proposals, original_by_id,
    group_expected=group_expected, src_map=src_map)
```
(chunk zaten cue sırasında iterasyon — sıra korunur. Grup chunk sınırında bölünürse
`group_expected` yalnız chunk-içi üyeleri içerir; bu bilinen POLISH_CHUNK=150 sınır durumudur,
bu turda kabul edilebilir — nadiren tetiklenir ve yön konservatiftir.)

**Testler (`tests/test_polish_group_atomicity.py` güncelle/ekle):**
1. Mevcut 5 test `group_expected=None` ile AYNEN geçmeli (geriye uyumluluk).
2. `test_partial_response_all_pass_reverts`: 3-üyeli grup, model 2'sini döndürmüş, ikisi de
   geçiyor → `group_expected` verildiğinde HİÇBİRİ uygulanmaz (`group_atomic:partial_response`).
3. `test_full_response_all_pass_applies`: aynı grup, 3/3 dönmüş, hepsi geçiyor, joined da
   geçiyor → 3'ü de uygulanır.
4. `test_joined_meaning_failure_reverts`: per-cue hepsi geçen ama birleşikte kaynaktaki bir
   sayıyı/kelimeyi topyekûn düşüren senaryo → `group_atomic_joined:*` ile geri alınır.
   (Ör: kaynak "144,000 souls...", eski joined "144.000 ruhu ...", yeni joined sayıyı hiç
   içermiyor → `source_numbers`/`content_word_loss` tetiklenir.)
5. `test_redistribution_across_cues_passes_joined`: kelimenin cue-1'den cue-2'ye taşındığı
   meşru SOV yeniden-dağıtımı → joined kontrol GEÇMELİ (grup toplamında kayıp yok).

## GÖREV C — Corpus runner v2: id-bazlı baseline + genel temizlik kontrolü + baseline zorunluluğu
[tests/test_regression_corpus.py](tests/test_regression_corpus.py) üç zayıflık:
(a) kategori-TOPLAMI, "A vakası kaçtı ama B yakalandı" takasını gizler; (b) corrected-metin
temizliği yalnız `sov_falsepos`'ta denetleniyor; (c) baseline yoksa test onu sessizce oluşturup
geçiyor (yanlışlıkla silinirse bozuk durum yeni baseline olur).

**Düzeltme — baseline formatı v2 (id-bazlı):**
```json
{
  "caught_case_ids":  ["john_dee:71", "..."],
  "clean_corrected_ids": ["john_dee:71", "...", "sumerian_pyramid:563"]
}
```
- `caught_case_ids`: yakalanan bozuk vakalar (`file:cue`); sov_falsepos HARİÇ.
- `clean_corrected_ids`: corrected metni hiçbir guard'ı tetiklemeyen TÜM vakalar
  (sov_falsepos dahil — onların "corrected"ı zaten kendisi).
Regresyon tanımı: baseline'daki bir `caught` id artık yakalanmıyorsa VEYA baseline'daki bir
`clean_corrected` id artık flagleniyorsa → FAIL (hangi id'ler olduğu mesajda listelenir).
Yeni yakalamalar/temizlenmeler FAIL değildir; raporda "baseline'ı güncellemek için
REGEN_CORPUS_BASELINE=1 ile çalıştır" notu basılır.

**Baseline zorunluluğu:** `baseline.json` yoksa test `self.fail(...)` ile düşer (mesajda
oluşturma komutu). Oluşturma/güncelleme YALNIZ açık istekle:
```python
if os.environ.get("REGEN_CORPUS_BASELINE") == "1":
    ...yaz ve geç...
elif not BASELINE_PATH.exists():
    self.fail("baseline.json yok — REGEN_CORPUS_BASELINE=1 python -m unittest "
              "tests.test_regression_corpus ile bilinçli oluşturun")
```
Mevcut kategori-sayılı `baseline.json` v1 dosyası: format v2'ye geçerken
`REGEN_CORPUS_BASELINE=1` ile bir kez yeniden üret (eski dosya üzerine yazılır); rapor
çıktısındaki kategori özeti (insan için) aynen kalabilir.

**Dikkat:** corrected-temizlik kontrolüne `validate_polish_candidate` DAHİL DEĞİL (o
old→new karşılaştırmasıdır, tek-metin temizliği değildir) — yalnız `find_garble_tokens` +
`has_non_turkish_target_leak`. Bazı corrected metinlerin flaglenmesi olasıdır (ör. bilinçli
korunan Latin terimler); ilk REGEN çalıştırmasında flaglenen id'ler `clean_corrected_ids`
DIŞINDA kalır ve bu bilinen-FP seti baseline'da böylece dondurulmuş olur — ekstra iş gerekmez.

## Doğrulama
1. `python -m py_compile subtitle_translator_gui.py hybrid_translate.py`
2. `python -m unittest tests.test_polish_group_atomicity tests.test_regression_corpus -v`
   (corpus testini önce `REGEN_CORPUS_BASELINE=1` ile, sonra normal çalıştır — normal
   çalıştırma yeşil olmalı; baseline'ı silip normal çalıştırınca FAIL olmalı, geri koy.)
3. Tam paket + headless smoke.
4. Görev A sonrası: `_write_results`'teki 3 pass çağrısının üçü de artık `analysis_result`
   VE (native için) `src_map` içeriyor — diğer akışlarla simetrik olduğunu grep'le teyit et.
