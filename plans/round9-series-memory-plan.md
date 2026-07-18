# Round 9 — Dizi Hafızası (Opus 4.8 uygulama brief'i)

> Bu brief kendi içinde eksiksizdir. Round 8'den bağımsız uygulanabilir.
> Her adımdan sonra `py_compile` + tam test paketi.

## Hedef
Aynı dizinin bölümleri arasında terim, karakter ve sen/siz kararlarının taşınması.
Bugün S01E05 çevrilirken E01-E04'ün kararlarından hiçbir şey aktarılmıyor (TM yalnız
birebir aynı satırları yakalar). Dizi hafızası: dosya adından dizi+bölüm tespiti →
dizi başına kalıcı JSON → sonraki bölümlerin system prompt'una enjeksiyon.

## Bağlam (mevcut yapı)
- `subtitle_translator_gui.py`: `build_requests(..., file_hints=...)` dosya başına
  prompt eki destekliyor (ön-bağlam analizi bunu kullanıyor; `_get_precontext_hints`
  metoduna bak). Hybrid yolunda prompt `ht.build_system_prompt(...)` ile dosya başına
  kuruluyor (`_run_sync_hybrid` ~5050 ve `_run_hybrid` ~6175).
- Hybrid analizi `context.recurring_terms`, `context.characters`, `pronoun_map` üretir
  (`ht.analyze_with_minimax` dönüşü, `_run_sync_hybrid` ~4990'da unpack ediliyor).
- Ön-bağlam analizi `analyze_file_precontext` JSON döndürür: summary/tone/characters/
  address_map/terms (modül seviyesinde, gui ~1150).
- `project_memory.py` klasör bazlı genel hafıza — dizi bazlı DEĞİL; ona dokunma,
  yeni bağımsız modül yaz.

## Tasarım

### 1. Yeni modül: `series_memory.py`
```python
SERIES_RE = re.compile(
    r'^(?P<show>.+?)[ ._-]+[Ss](?P<season>\d{1,2})[ ._-]?[Ee](?P<ep>\d{1,3})', )

def parse_series_key(filename: str):
    """'Show.Name.S01E05.720p.srt' → ('show-name', 1, 5) | None (dizi değilse).
    Ayrıca '1x05' kalıbını da destekle: r'(?P<season>\d{1,2})x(?P<ep>\d{2,3})'."""

class SeriesMemory:
    """<input_dir>/.series_memory/<show-slug>.json
    Şema: {"version": 1, "show": str, "updated_eps": ["s01e01", ...],
           "terms": {src: tgt}, "characters": {name: {"style": str}},
           "address_map": [{"a","b","register"}]}"""
    def load(input_dir, show_slug) -> SeriesMemory
    def merge_terms(self, terms: dict)          # mevcut karar ÖNCELİKLİDİR (ilk karar kazanır)
    def merge_characters(self, chars)           # list[dict] veya {name: style}
    def merge_address_map(self, pairs)
    def mark_episode(self, season, ep)
    def save(self)
    def build_hint(self) -> str
        # "## SERIES MEMORY (decisions from earlier episodes — follow strictly)" bloğu;
        # gui'deki build_precontext_hint formatına benzer; boşsa "" döner.
        # Sınırlar: max 40 terim, 15 karakter, 12 hitap çifti (prompt şişmesin).
```
Çakışma kuralı: var olan terim ASLA ezilmez (ilk bölümdeki karar kanon olur) —
tutarlılığın bütün amacı bu.

### 2. Enjeksiyon noktaları
- **Düz sync/batch:** `_run_sync` ve `_run_batch` içinde `_file_hints` kurulduktan sonra
  (`self._get_precontext_hints(...)` çağrısının hemen ardından): her dosya için
  `parse_series_key` → hafıza varsa `hints[fp] = hints.get(fp, "") + sm.build_hint()`.
- **Hybrid sync (`_run_sync_hybrid`):** `ht.build_system_prompt(...)` dönüşüne ekle:
  `system_prompt += sm.build_hint()` (dosya döngüsü içinde, ~5050).
- **Hybrid batch (`_run_hybrid`):** aynı şekilde (~6175 `build_system_prompt` sonrası).

### 3. Güncelleme noktaları (çeviri/analiz sonrası hafızaya yazım)
- **Hybrid analiz sonrası** (`_run_sync_hybrid` ~5000 ve `_run_hybrid` Faz-1 analiz
  bloğu): `sm.merge_terms(dict(context.recurring_terms))`,
  `sm.merge_characters(context.characters)` (name+speaking_style),
  `pronoun_map` → `merge_address_map`. `mark_episode` + `save`.
- **Ön-bağlam analizi sonrası** (`_get_precontext_hints` içinde, data elde edilince):
  data["terms"] / data["characters"] / data["address_map"] merge + save.
- Sıralama uyarısı: aynı koşuda çok bölüm çevriliyorsa dosyaları
  `parse_series_key`'e göre SIRALA (sezon, bölüm) — `_get_srt_files` dönüşünü
  sıralayan küçük bir yardımcı (`sort_files_by_episode`) ekle ve dört akışın dosya
  listesi kurulduğu yerde uygula. Hybrid sync sıralı işlediği için aynı koşu içinde
  bile E01 kararları E02'ye akar. Düz sync/batch'te istekler baştan kurulduğundan
  aynı koşu içinde akış sınırlıdır (bir sonraki koşuda devreye girer) — bu kabul
  edilen bir sınırlamadır, log'a bilgi satırı yaz.

### 4. UI + ayar
- KALİTE bölümüne switch: `series_memory_var` — "Dizi Hafızası" (varsayılan AÇIK).
  Açıklama: "Aynı dizinin bölümleri arasında terim, karakter ve sen/siz kararlarını taşır."
- Ayar kalıcılığı: `"series_memory"` anahtarı, default-True kalıbıyla
  (`if "series_memory" in d:` — _save_settings/_load_settings'teki chain_ctx örneğine bak).
- Sidebar'a buton GEREKMEZ; hafıza dosyası kullanıcı tarafından `.series_memory/`
  klasöründen elle düzenlenebilir (build_hint bozuk JSON'a dayanıklı olmalı).

### 5. Testler (`tests/test_series_memory.py`)
- `parse_series_key`: 'Show.Name.S01E05.720p.srt', 'show_s1e5.srt', 'Show 1x05.srt',
  'Movie.2024.srt' (None), Türkçe karakterli adlar.
- merge: ilk karar kazanır; tekrar merge idempotent.
- build_hint: boş hafıza "" döner; dolu hafıza başlık + sınırlar (40 terim kesimi).
- sort_files_by_episode: karışık liste doğru sıraya girer; dizi-olmayanlar sona, ada göre.
- Kalıcılık: save → load round-trip.

## Kabul kriterleri
- Tüm testler yeşil; GUI duman testi geçer (yeni switch görünür, ayar persist).
- İki bölümlü sahte akışta: E01 analizinden üretilen terim, E02'nin system prompt'unda
  "SERIES MEMORY" bloğu içinde görünür (birim test: hints sözlüğü üzerinden doğrula).
- Dizi olmayan dosyalarda davranış değişmez (hint eklenmez, hafıza dosyası oluşmaz).
