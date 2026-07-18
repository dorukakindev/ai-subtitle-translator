# SDH temizliği: beyaz liste → kaynak-güdümlü yapısal tespit

**Analiz:** Opus 4.8, 2026-07-16 · **Uygulayacak:** Sonnet 5
**Taban:** 1354 test yeşil (`python -m unittest discover -s tests`)

## Sorun

`sdh_cleaner.py` içindeki `_SDH_KEYWORDS` (`:11`) elle yazılmış, İngilizce-öncelikli bir **kelime beyaz listesi**. Ama `clean_sdh` **çeviriden sonra** çalışıyor, yani artık Türkçeleşmiş etiketlere bakıyor. Sonuç: etiketlerin çoğu sağ kalıyor.

Gerçek ölçüm (The Blood of Hussain, 20 etiket): **yalnızca 1'i tanındı.** `[KALABALIK TEZAHÜRATI]` silindi (çünkü "kalabalik" listede), ama `[ÇAN SESLERİ]`, `[İNLEME]`, `[KİŞNEME]`, `[FERYAT]`, `(Urduca konuşur)`, `[RADYO]` sağ kaldı.

Listeye kelime eklemek **yanlış çözüm** — her yeni dosya yeni sözcük üretir. Üstelik `write_srt:1664` her akışta `normalize_sdh_descriptors` çalıştırıp İngilizce etiketleri Türkçeleştiriyor, yani sistem beyaz listenin göremediği etiketleri bizzat üretiyor.

## Çözüm: kaynağa sor

Kodda zaten doğru mekanizma var ama yanlış tarafta: **`_SDH_ONLY_SRC_RE`** (`subtitle_translator_gui.py:2429`) *yapısal* bir regex — beyaz liste kullanmaz, parantezin kendisine bakar — ve kaynak tarafında çalışır (`_src_is_sdh_only:2437`, `_is_untranslated:2451`, `_repair_untranslated_sync:2518`).

Asimetri: **kaynak tarafı yapısal, çeviri tarafı beyaz listeli.** `[ÇAN SESLERİ]` onarım geçişince SFX olarak doğru tanınıyor ama `clean_sdh`'ce tanınmıyor.

### Yeni kural (üç satır)

Her cue için, **İngilizce kaynağa** bakarak:

1. Kaynak cue'su **tamamen** parantez/köşeli/♪ ise (`_SDH_ONLY_SRC_RE`) → **çeviri cue'sunu sil.**
2. Kaynak satırında parantez/köşeli grup **varsa** → çeviri satırındaki parantez/köşeli grupları **sök** (kalan repliği bırak).
3. Kaynak satırında parantez **yoksa** → **dokunma.** (Çevirinin parantezi gerçek nesirdir.)

Beyaz liste bu yolda hiç sorgulanmaz.

### Neden bu tasarım yanlış-pozitif üretmez

| Vaka | Kaynak | Kural | Sonuç |
|---|---|---|---|
| Ses etiketi | `(Bells jingling)` | 1 → sil | ✅ istenen |
| Satıriçi dil etiketi | `(Speaks Urdu) Get out of the way!` | 2 → sök | ✅ `Yoldan çekilin!` |
| Konuşmacı etiketi | `(Captain) 'The airport is...` | 2 → sök | ✅ |
| **Şarkı sözü** | `♪ I love you ♪` | parantez yok → 3 | ✅ **korunur** (♪ parantez değil) |
| **Parantezli nesir** | kaynakta parantez yok | 3 → dokunma | ✅ korunur |
| Parantezli ağıt etiketi | `(♪ Punjabi lament)` | 1 → sil | ✅ (parantez var, ayırt edici bu) |

**Ayırt edici işaret parantezin kendisi, içindeki kelimeler değil.** `♪` tek başına şarkı sözüdür; parantez içine alınmışsa etikettir.

---

## Uygulama

### Adım 1 — `sdh_cleaner.py`: yapısal mod ekle

Mevcut beyaz liste yolunu **silme**, yanına yapısal yol ekle (geri uyumluluk; mevcut testler yaşamalı).

```python
# Kaynak-güdümlü yapısal SFX tespiti — beyaz liste sorgulamaz.
SFX_ONLY_STRUCTURAL_RE = re.compile(r'^(?:\([^)]*\)|\[[^\]]*\]|[♪_\s]+)+$')

def src_is_sfx_only(src_text: str) -> bool:
    """Kaynak cue'su tamamen parantez/köşeli/nota mı?"""
    ...

def strip_labels_by_source(tr_line: str, src_line: str) -> str:
    """Kaynak satırında parantez varsa çeviri satırındakileri sök.
    Kaynakta parantez yoksa çeviriye DOKUNMA."""
    ...
```

`strip_labels_by_source` ayrıntıları:
- Kaynakta bracket grubu yoksa → `tr_line` aynen dön.
- Varsa → `BRACKET_OR_PAREN_RE` ile çeviri satırındaki tüm grupları sil.
- Artıkları temizle: baş/son boşluk, çift boşluk → tek boşluk.
- **`- ` diyalog tiresi korunur.** Etiket silinince satırda yalnız `-`/`- ` kalıyorsa satır boş sayılır.
- **`<i>`/`<b>` biçim etiketlerine DOKUNMA** — `strip_format_tags=False` davranışı. (Bunlar `<>` içinde, `BRACKET_OR_PAREN_RE` zaten eşlemiyor, ama `strip_sdh_line`'ın aksine format tag sökme adımını hiç çalıştırma.)

### Adım 2 — `clean_sdh_blocks`: yeni parametre

```python
def clean_sdh_blocks(blocks, src_map=None, source_driven=False):
```

`source_driven=True` ve `src_map` verilmişse:
- `src_is_sfx_only(src_map[idx])` → cue'yu düşür
- değilse her satır için `strip_labels_by_source(line, src_line)`
- tüm satırlar boşaldıysa cue'yu düşür

`source_driven=False` → **mevcut davranış aynen** (mevcut testler geçmeye devam eder).

> **KRİTİK:** `src_map` YOKSA `source_driven` çalışamaz. Aşağıdaki Adım 3'e bak.

### Adım 3 — `src_map` boşluğunu kapat (ÖN KOŞUL)

Keşif şunu buldu: **`_write_results` (`subtitle_translator_gui.py:11145`) `clean_sdh`'ye `src_map` GEÇMİYOR.** Bu akış `_run_sync` (`:9874`) ve `_run_batch` (`:10564`, `:10650`) tarafından kullanılıyor — yani sync ve batch akışlarının ikisi de kaynaksız.

Diğer akışlar geçiyor:
| Akış | `clean_sdh` satırı | `src_map` |
|---|---|---|
| `_run_sync_hybrid` | `:10250` | ✅ `_src_map_for_condense` |
| `_wait_batch_hybrid` | `:10801` | ✅ `_src_map_from_cues(_orig_cues)` |
| `_run_hybrid` | `:11716` | ✅ `_src_map_from_cues(cues)` |
| **`_write_results`** | `:11145` | ❌ **yok** |
| `_import_jsonl` | `:7767` | ❌ |
| `_run_post_process` | `:8773` | ❌ |

`_write_results`'a `src_map` ekle (`_src_map_from_cues` ile, diğer akışlardaki gibi). Bu ayrıca **bağımsız bir hata düzeltmesi**: `src_map` olmadan `clean_sdh_blocks` eski "tüm boş cue'ları düşür" dalına giriyor (`sdh_cleaner.py:505`) — `tests/test_silent_empty_cue_loss.py`'nin başka yerde önlemek için yazıldığı davranışın ta kendisi.

`_import_jsonl` ve `_run_post_process` için kaynak elde yoksa `source_driven` çalıştırma; eski davranışta kalsınlar (regresyon yok).

### Adım 4 — UI toggle

Mevcut: `self.clean_sdh_var` (`:4760`, **varsayılan OFF**), etiket "SDH Temizle", ayar anahtarı `"clean_sdh"` (`:6751` kaydet, `:7064` yükle).

Toggle'ı **ikiye ayırma** — mevcut `clean_sdh` toggle'ı açıkken **kaynak-güdümlü mod** kullanılsın. Yani `clean_sdh=True` artık "gerçekten temizle" demek.

Gerekçe: kullanıcı SDH istemiyor; iki toggle karmaşa yaratır. Mevcut beyaz liste yolu yalnızca `src_map`'siz akışlar (`_import_jsonl`, `_run_post_process`) için geri düşüş olarak kalır.

CLAUDE.md: varsayılan-OFF toggle'lar `if d.get("key"):` yükleme kalıbı kullanır — mevcut hâli koru, varsayılanı değiştirme.

### Adım 5 — sıralama tutarsızlığını düzelt (keşif bulgusu)

Hibrit akışlar: condense → **SDH** → linebreak → QC
`_write_results`: QC → **SDH** → linebreak (`:11140` → `:11143`)

Yani sync/batch'te QC çıktısı SDH-temizli, hibritte değil. `_write_results`'ı diğerlerine hizala (SDH'yi QC'den önce çalıştır).

> Bu ayrı bir davranış değişikliği — ayrı commit yap, testleri ayrı doğrula. Riskliyse ATLA ve raporla.

### Adım 6 — `write_srt` geri sızıntısı

`write_srt:1664-1666` her akışta koşulsuz `normalize_sdh_descriptors` çalıştırıyor — `clean_sdh`'den SONRA. Bu fonksiyon **silmiyor, çeviriyor** (`sdh_cleaner.py:274`), yani `clean_sdh` bir etiketi kaçırdıysa write_srt onu Türkçeleştirip kalıcılaştırıyor.

Kaynak-güdümlü mod doğru çalışırsa etiket zaten silinmiş olur ve bu fonksiyon boşa çalışır — **dokunma.** Ama doğrulamada bunu teyit et (aşağıda 4. madde).

> `write_srt:1668-1669` boş cue'yu `[ÇEVİRİ EKSİK]`e çeviriyor — bu yüzden silme write_srt'te DEĞİL, `clean_sdh`'de yapılmalı. Zaten öyle.

---

## Testler

### Yaşamaya devam etmeli (mevcut davranış, `source_driven=False`)
- `tests/test_sdh_cleaner_extended.py:65-75` — `normalize_sdh_descriptors` çevirir, silmez
- `tests/test_write_srt_output.py:76-78` — `(The audience loved it)` değişmeden döner
- `tests/test_write_srt_output.py:79-82` — `♪ Seni seviyorum ♪` sağlam kalır
- `tests/test_write_srt_output.py:85-87` — descriptor korunup çevrilir
- `tests/test_speaker_labels.py:29-43` — `[NARRATOR]: Hello` → `[ANLATICI]: Hello`
- `tests/test_merge_cues.py:25-30` — `_is_sdh_only("Konuşma [gülüyor]")` False
- `tests/test_silent_empty_cue_loss.py` — `src_map` boş-cue sözleşmesi

**Bu testlerin HİÇBİRİ değişmemeli.** Yeni yol ayrı parametre arkasında.

### Yeni testler (`tests/test_sdh_source_driven.py`)

```
test_src_sfx_only_cue_dropped              (Bells jingling) → cue silinir
test_inline_label_stripped_by_source       (Speaks Urdu) X! → X!
test_speaker_label_stripped                (Captain) 'The airport → 'The airport
test_turkish_label_stripped_despite_whitelist   [ÇAN SESLERİ] silinir (BEYAZ LİSTEDE YOK — asıl regresyon)
test_lyric_with_notes_preserved            ♪ I love you ♪ → çeviri korunur
test_prose_paren_in_translation_preserved  kaynakta parantez yok → çeviriye dokunulmaz
test_dialogue_dash_preserved               - (Speaks Punjabi) Ne oldu? → - Ne oldu?
test_dash_only_line_dropped                - [KIKIRDAR] tek satırsa düşer, "-" kalmaz
test_format_tags_preserved                 <i>Selamünaleyküm.</i> korunur
test_double_space_collapsed                etiket sökülünce çift boşluk kalmaz
test_no_src_map_falls_back_to_legacy       src_map yoksa eski davranış
```

**Asıl regresyon testi `test_turkish_label_stripped_despite_whitelist`** — bugünkü hatayı kilitler.

### Regresyon korpusu

`tests/regression_corpus/cases.jsonl` yapısı: `{file, cue, source, buggy, corrected, category, note}`.
Bu değişiklik korpusa yeni vaka **eklemiyor** (korpus çeviri hatalarını izliyor, SDH'yi değil). Dokunma.

---

## Doğrulama

1. `python -m unittest discover -s tests` → **1354 test hâlâ yeşil** + yeni testler.
2. Headless smoke: `python -c "import subtitle_translator_gui as g; a=g.App(); a.update_idletasks(); a.destroy(); print('OK')"`
3. `python -m py_compile subtitle_translator_gui.py hybrid_translate.py sdh_cleaner.py`
4. **Gerçek dosya testi** — en önemlisi. Elde hem hatalı hem düzeltilmiş gerçek veri var:
   - Girdi kaynağı: `C:\Users\K\Downloads\Yeni klasör (4)\The.Blood.Of.Hussain.English-WWW.MY-SUBS.CO.srt` (469 cue)
   - Etiketli çeviri: `...\ÇIKTI\The.Blood.Of.Hussain...\....srt.bak` (440 cue, etiketler duruyor)
   - Beklenen sonuç: `clean_sdh_blocks(bak_blokları, src_map, source_driven=True)` → **385 cue**, hiç `[...]`/`(...)` etiketi kalmamalı, `<i>` korunmalı, `- ` tireleri korunmalı.
   - Bu, elle yapılan 3. turun sonucuyla birebir eşleşmeli: `...\....srt` (385 cue).
   **Bu testi çalıştır ve sonucu raporla.** Eşleşmiyorsa fark listesini ver.
5. `_write_results`'a eklenen `src_map` başka bir şeyi bozmadı mı — sync ve batch akış testleri.

## Raporla

- Hangi adımlar uygulandı, hangileri atlandı (Adım 5 riskliyse atlanabilir)
- Test sayısı öncesi/sonrası
- Doğrulama 4'ün sonucu: 385 cue eşleşti mi?
- Belirsiz/çelişkili bulduğun madde — **tahmin yürütme, raporla.**
