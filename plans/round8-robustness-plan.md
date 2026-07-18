# Round 8 — Sağlamlık Paketi (Opus 4.8 uygulama brief'i)

> Bu brief kendi içinde eksiksizdir; konuşma geçmişine ihtiyaç yoktur.
> Uygulama sırası: A → B → C. Her adımdan sonra `python -m py_compile` + tam test paketi
> (`python -m unittest discover -s tests`, şu an 122 test, hepsi yeşil olmalı).
> GUI duman testi: `App()` aç/kapat (tests klasöründeki mevcut kalıplara bak).

## Bağlam
Proje: CustomTkinter tabanlı altyazı çeviri uygulaması. Ana dosyalar:
`subtitle_translator_gui.py` (~6400 satır), `hybrid_translate.py`, `subtitle_formats.py`.
Üç çeviri akışı: düz sync (`_run_sync`), düz batch (`_run_batch` → `_write_results`),
hybrid sync (`_run_sync_hybrid`), hybrid batch (`_run_hybrid` → `ht.save_results`).

---

## A. Toleranslı encoding çözümleme (BUG)

**Sorun:** Altyazı dosyaları katı `utf-8-sig` ile açılıyor; Windows-1254/cp1252 kodlu
dosyalar (Türkçe altyazılarda çok yaygın) `UnicodeDecodeError` fırlatır.

**Mevcut açılış noktaları (hepsi düzeltilecek):**
- `subtitle_translator_gui.py:747-750` — `parse_srt`: `open(..., encoding="utf-8-sig")` (katı)
- `subtitle_formats.py:123` — `parse_vtt`: `encoding='utf-8-sig'` (katı)
- `subtitle_formats.py:189` — `parse_ass`: `errors='replace'` var (kayıplı ama patlamaz) — yine de ortak yardımcıya geçir
- `hybrid_translate.py:212` — `load_srt`: encoding kullanımını DOĞRULA ve aynı yardımcıya geçir

**Çözüm:** `subtitle_formats.py`'a ortak yardımcı ekle:
```python
def read_subtitle_text(filepath) -> str:
    """Altyazı dosyasını toleranslı çözümler: utf-8-sig → cp1254 → latin-1(replace).
    cp1254 denemesi 'şğıİ' içeren Türkçe dosyaları doğru açar."""
    raw = Path(filepath).read_bytes()
    for enc in ("utf-8-sig", "cp1254"):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    return raw.decode("latin-1", errors="replace")
```
Dikkat: cp1254 hemen her bayt dizisini kabul eder, bu yüzden SIRA önemli — önce utf-8
denenmeli (utf-8 geçerliyse o doğrudur). Dört açılış noktasını bu yardımcıyı kullanacak
şekilde değiştir (`f.read()` yerine `read_subtitle_text(filepath)` üzerinden satırlara böl).
`subtitle_translator_gui.py` zaten `from subtitle_formats import ...` yapıyor — import'a ekle.
`hybrid_translate.py` için `from subtitle_formats import read_subtitle_text` güvenli
(subtitle_formats hiçbir yerel modülü import etmiyor, döngü oluşmaz).

**Test (tests/test_encoding.py):** geçici dosyaya cp1254 ile 'Şöyle ığdır çiçeği'
içeren SRT yaz → `parse_subtitle` UnicodeDecodeError fırlatmadan doğru Türkçe karakterleri
okumalı. UTF-8 BOM'lu dosya da regresyonsuz okunmalı.

---

## B. [HATA] satırlarına kaynak-metin fallback'i

**Sorun:** Retry'lar sonrası hâlâ çevrilemeyen satırlar çıktı SRT'sine literal
`[HATA]` yazılıyor → izleyici ekranda "[HATA]" görüyor.

**Çözüm:** Yazımdan hemen önce `[HATA*]` satırlarını HAM kaynak metinle doldur
(etiketleriyle — italik vb. korunur). `subtitle_translator_gui.py`'a modül-seviyesi:
```python
def _fill_hata_with_source(blocks: list, raw_src_map: dict, log_fn=None) -> list:
    """[HATA*] satırlarını orijinal kaynak metinle değiştirir (son çare).
    raw_src_map: {idx_str: ham kaynak metin} — _raw_src_map_from_cues üretir."""
```
Sayaç tut, `log_fn` varsa "%d çevrilemeyen satır kaynak metinle dolduruldu" uyarısı yaz.

**Bağlanacak yerler** (hepsi `_restore_tags_blocks` çağrısının HEMEN ÖNCESİ — fallback
metni zaten etiketli olduğundan restore idempotent guard'ı ('<' in out) onu atlar):
1. `_write_results` — "Kaynaktaki biçim etiketlerini ... geri uygula" bloğu (~gui:5670),
   `_raw_cues` zaten orada hesaplanıyor; aynı raw map'i kullan.
2. `_run_sync_hybrid` — restore bloğu (~gui:5300), `cues` mevcut.
3. `_wait_batch_hybrid` post-process — restore bloğu (~gui:5535), `_orig_cues` mevcut (boş olabilir — boşsa dokunma).
4. `_run_hybrid` post-process — restore bloğu (~gui:6325), `cues` mevcut.
5. `hybrid_translate.save_results` (~ht:2906) — `src_cues` parametresi zaten var;
   restore bloğunun önüne aynı doldurma mantığını ekle (oradaki `raw_map` zaten kurulu).

**KRİTİK — TM koruması:** Doldurulmuş satırlar kaynak==çeviri olur; TM'e yazılırsa
çöp girer. İki TM kayıt noktasında (`_write_results` ~gui:5690 `tm_pairs` ve
`_run_sync_hybrid` ~gui:5320 `_tm_pairs`) mevcut `[HATA` filtresine ek olarak şu
guard'ı ekle: `_clean_src(tr_text).strip().lower() != src_clean.strip().lower()`.
(Not: scan_translation_quality bu satırları "çevrilmemiş" diye sayacak — bu DOĞRU
davranış, rapor gerçeği yansıtmalı.)

**Rapor:** `_count_hata_cps` artık 0 [HATA] sayar (dolduruldu). Rapor satırına gerçeği
taşımak için doldurma sayısını kullan: doldurma fonksiyonunun döndürdüğü sayıyı
(`blocks, n_filled` döndür) rapor row'unda `hata` alanına yaz (üç akışta da).

**Test:** blocks içinde `[HATA]` + `[HATA: timeout]` satırları → doldurma sonrası
kaynak metin; kaynak yoksa satır olduğu gibi kalır; sayaç doğru.

---

## C. Durdururken uzak batch iptali (maliyet)

**Sorun:** "Durdur" (`_stop`, gui:~3560) sadece `self._stop_flag = True` yapar.
OpenAI'daki batch çalışmaya ve faturalanmaya devam eder. Kodda hiç `batches.cancel` yok.

**Tasarım:**
1. `App.__init__`'e `self._active_batches = {}` ekle — {batch_id: api_key}.
2. Kayıt noktaları (create/submit sonrası ekle, tamamlanınca/başarısız olunca çıkar):
   - `_run_batch`: `client.batches.create(...)` sonrası (~gui:5360) ekle;
     `_wait_batch` dönüşünde (completed/failed/expired dallarında) çıkar.
   - `_run_hybrid`: `ht.submit_batch(...)` dönüşü `batch_id` (~gui:6200) ekle;
     Faz-2'de `wait_for_batch` sonuçlanınca çıkar.
   - `_resume_batches`: beklemeye alınan her bid'i ekle, sonuçlanınca çıkar.
   Temizlik `finally` mantığıyla güvenceye alınmalı (exception'da sızmasın).
3. `_stop` metodunu genişlet: `self._active_batches` boş değilse
   `messagebox.askyesno("Durdur", "OpenAI'daki N batch de iptal edilsin mi?\n"
   "İptal etmezseniz daha sonra '↺ Batch'i Devam Ettir' ile sonuçları alabilirsiniz.")`
   — Evet ise arka plan thread'inde her id için `OpenAI(api_key=...).batches.cancel(bid)`
   (try/except'li, sonucu logla). `_stop` UI thread'inde çalışır; cancel çağrılarını
   `threading.Thread(daemon=True)` ile yap, UI'ı bloklama.
4. İptal edilen id'lerin `batch_fmap_<id>.json` dosyalarını da sil ve `batch_id.txt`'den çıkar.

**Test:** ağ çağrısı test edilmez; `_active_batches` ekle/çıkar muhasebesini doğrulayan
birim test yeterli (kayıt fonksiyonlarını küçük yardımcılara çıkar:
`_register_batch(bid, key)` / `_unregister_batch(bid)` — saf, test edilebilir).

---

## Kabul kriterleri
- 122 mevcut test + yeni testler yeşil; `py_compile` üç dosyada temiz.
- cp1254 SRT dosyası GUI'de hatasız parse ediliyor.
- Çıktı SRT'lerinde hiçbir koşulda literal "[HATA]" kalmıyor; raporda doldurma sayısı görünüyor.
- TM'e kaynak==çeviri çifti girmiyor.
- Durdur → onayla → uzak batch'ler iptal; onaylamazsa resume akışı bozulmuyor.
