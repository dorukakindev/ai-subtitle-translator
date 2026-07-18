# Brief: Çıktı klasörü kuralları — alt-klasör yönlendirme (Sonnet 5)

Hazırlayan: **Opus 4.8** (kullanıcı isteği + çıktı-yolu kodunun haritalanması, 2026-07-10).
Protokol: Opus tasarlar + brief, Sonnet uygular.

> **DURUM: UYGULANDI (Opus, 2026-07-10).** Kullanıcı "yap" dedi → doğrudan uygulandı.
> `_paths_equal` + `_resolve_output_path` + `_resolve_report_dir` eklendi; 4 out_path çağrısı
> + rapor yolu (`_save/_open_quality_report`) bağlandı. EK: `get_subtitle_files`'a base-göreli
> `ÇIKTI` dizin dışlaması + `.ham.srt` yedek dışlaması (Kural 1 footgun'u: yeniden çalıştırmada
> `<girdi>/ÇIKTI` kendini çevirmesin). Testler: `tests/test_output_path_rules.py` (14) +
> `tests/test_subtitle_formats.py` (+4). Tam paket 1334 (yalnız bilinen flaky mtime testi kırmızı).

## Kullanıcının isteği — YORUMUM (uygulamadan ÖNCE onay bekliyor)
İki deterministik kural:
1. **Girdi klasörü == Çıktı klasörü ise** → girdinin içinde `ÇIKTI/` alt-klasörü oluştur, çeviriyi
   ORAYA koy (kaynak dosyaların yanına yazma). Ör: girdi=çıktı=`D:\subs` → `D:\subs\ÇIKTI\film.srt`.
2. **Çıktı ayrı bir klasörse** (ör. `C:\Users\K\Downloads\ÇIKTI`) → o klasörün içinde **dosya
   adıyla** bir alt-klasör oluştur, çıktıyı ORAYA koy. Ör: çıktı=`Downloads\ÇIKTI`,
   dosya=`Olous.srt` → `Downloads\ÇIKTI\Olous\Olous.srt`. (Her dosya kendi klasöründe → ortak
   çıktı klasörü karışmaz.)

**Boş çıktı klasörü** = girdiyle aynı sayılır (Kural 1). Karşılaştırma normalize edilmiş yolla
(`Path(...).resolve()`, büyük/küçük harf Windows'ta önemsiz).

## Mevcut kod (haritalandı)
Çıktı yolu 4 yerde AYNI kalıpla hesaplanıyor:
```python
try: rel = Path(filepath).relative_to(input_dir)
except ValueError: rel = Path(filepath).name
out_path = Path(output_dir) / rel
```
Yerler: `_run_sync_hybrid` (~9676), sync repair-save (~10090), `_write_results` (~10916),
`_run_hybrid` (~11257, `.with_suffix(".srt")` ile). **Resume otomatik uyumlu**: `_run_hybrid`
out_path'i fmap'e saklıyor ([~11264](subtitle_translator_gui.py:11264)), resume onu okuyor
([~10361](subtitle_translator_gui.py:10361)) — submit anında doğru hesaplanırsa resume da doğru.

## Uygulama — merkezi helper
Modül düzeyine (out_path kalıbının yakınına) ekle:
```python
def _resolve_output_path(input_dir: str, output_dir: str, filepath: str) -> Path:
    """Çıktı .srt yolunu iki kurala göre çözer (bkz. plans/output-folder-rules-brief.md).
    Kural 1: çıktı==girdi (veya çıktı boş) → <girdi>/ÇIKTI/<göreli-yol>.srt
    Kural 2: çıktı ayrı klasör       → <çıktı>/<dosya-adı-uzantısız>/<dosya-adı>.srt
    Yol her zaman .srt uzantılı (çıktı SRT)."""
    src = Path(filepath)
    in_dir = (input_dir or "").strip()
    out_dir = (output_dir or "").strip()

    def _same(a, b):
        try:
            return a and b and Path(a).resolve() == Path(b).resolve()
        except Exception:
            return (a or "").rstrip("\\/").lower() == (b or "").rstrip("\\/").lower()

    if not out_dir or _same(in_dir, out_dir):
        # Kural 1 — girdinin içinde ÇIKTI alt-klasörü, göreli substructure korunur
        base = Path(in_dir) if in_dir else src.parent
        try:
            rel = src.relative_to(base)
        except (ValueError, Exception):
            rel = Path(src.name)
        return (base / "ÇIKTI" / rel).with_suffix(".srt")
    # Kural 2 — ayrı çıktı klasörü içinde dosya-adı alt-klasörü
    return (Path(out_dir) / src.stem / src.name).with_suffix(".srt")
```
4 çağrı yerini bununla değiştir:
```python
out_path = _resolve_output_path(input_dir, output_dir, filepath)
```
(sync akışlarında `Path` döner; `_run_hybrid` `str(out_path)` bekliyorsa `str(...)` ile sar.
Mevcut `.with_suffix(".srt")` helper içinde olduğundan çağrı yerlerinden kaldırılabilir.)

**`_maybe_merge_cues`/`write_srt`/`_save_raw_backup`** out_path'ten türediği için `.ham.srt` ve
`.bak` otomatik olarak aynı alt-klasöre gider (istenen — dosya artefaktları bir arada).
**Klasör oluşturma:** `write_srt` zaten `out_path.parent`'ı yaratıyorsa ek iş yok; yaratmıyorsa
`out_path.parent.mkdir(parents=True, exist_ok=True)` ekle (write_srt'ü kontrol et).

## Alt-kararlar (varsayılan — kullanıcı aksini isterse değiştir)
- **`ceviri_raporu.txt`** ([~8886/8895](subtitle_translator_gui.py:8886)): per-run toplu rapor.
  Kural 2'de çıktı KÖKÜNDE kalır (alt-klasörlerin üstünde, `Downloads\ÇIKTI\ceviri_raporu.txt`).
  Kural 1'de `<girdi>/ÇIKTI/` içine gider (kaynak klasörünü kirletmesin). → rapor yolunu da
  aynı "efektif çıktı tabanı" mantığıyla hesapla (Kural 1 için `in/ÇIKTI`, Kural 2 için `out` kökü).
- **Recursive girdi + Kural 2**: dosya-adı alt-klasörü göreli substructure'ı DÜZLEŞTİRİR
  (`out/<stem>/<name>` — parent klasörler taşınmaz). Kullanıcının kullanımı düz (tek/az dosya);
  kabul edilebilir. Kural 1 substructure'ı korur.
- **Aynı dosya yeniden çevrilirse**: alt-klasör varsa içine yazılır (üzerine). Sorun yok.

## Testler (`tests/test_output_path_rules.py` — YENİ, saf helper)
1. `test_same_in_out_makes_cikti_subfolder`: in==out=`/x` → `/x/ÇIKTI/f.srt`.
2. `test_empty_output_treated_as_same`: out="" → Kural 1.
3. `test_separate_output_makes_named_subfolder`: in=`/a`, out=`/b`, f=`/a/Film.srt` →
   `/b/Film/Film.srt`.
4. `test_extension_normalized_to_srt`: girdi `.vtt`/`.ass` → çıktı `.srt`.
5. `test_recursive_input_preserves_substructure_rule1`: in=`/x`, f=`/x/sub/f.srt` →
   `/x/ÇIKTI/sub/f.srt`.
6. `test_case_insensitive_same_dir` (Windows): `/X` vs `/x` → aynı sayılır → Kural 1.
7. `test_filepath_outside_input_dir_fallback`: relative_to başarısız → dosya adına düşer.

## Doğrulama
1. `python -m py_compile subtitle_translator_gui.py`
2. `python -m unittest tests.test_output_path_rules` + tam paket + smoke.
3. Elle: 4 çağrı yeri + rapor yolu grep'le teyit; resume yolu değişmedi (fmap'ten okunuyor).

## ÖNEMLİ — uygulamadan önce
Yukarıdaki YORUM doğru mu? Özellikle: Kural 2 "ayrı çıktı klasörü seçtiğim HER zaman" (deterministik)
mü, yoksa yalnız belirli "ortak" klasörlerde mi isteniyor? Deterministik ("her ayrı klasör")
varsaydım — kullanıcı "her zaman" dediği için. Farklıysa (ör. toggle isteniyorsa) söylenmeli.
