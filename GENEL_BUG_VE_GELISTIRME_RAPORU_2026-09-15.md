# Genel Bug ve Geliştirme Raporu — 2026-09-15

Bu rapor, "kod değiştirmeden önce raporla" talimatıyla hazırlanmış salt-okuma
bir denetimdir. **Hiçbir kaynak dosya değiştirilmedi.** Bulgular üçe ayrılır:

1. **Bu turda bulunan yeni bulgular** (güncel kodda satır satır doğrulandı)
2. **Önceki raporlardan güncel kodda hâlâ açık olanlar** (bu turda yeniden doğrulandı)
3. **Düzeltilmiş veya geçersiz çıkan eski iddialar** (durum güncellemesi)

Önceki raporlar: `DERIN_DETAYLI_BUG_RAPORU_2026-09-02.md`,
`DERIN_DETAYLI_BUG_RAPORU_2026-09-04.md` (Tur 1 + Tur 2),
`YENI_BUG_BULGULARI_RAPORU_2026-09-11.md`, `plans/YENI_MODULLER_*` serisi,
`plans/BROWSER_*` serisi.

Başlangıç durumu: `master` @ `5a7cda9`, çalışma ağacında yalnız önceki
oturumlardan kalan untracked rapor/plan dosyaları var.

---

## BÖLÜM 1 — BU TURDA BULUNAN YENİ BULGULAR

### B1 — `okuma_yuzeyi`: Ctrl+P / Ctrl+N kısayolları engelleniyor (modifier guard yok)

**Şiddet: orta (tarayıcı işlevi kaybı)** · `okuma_yuzeyi.py:118-127`

```javascript
document.addEventListener('keydown',function(e){
 if(e.target.tagName==='INPUT')return;
 if(e.key==='n'){git(1);e.preventDefault();}
 if(e.key==='p'){git(-1);e.preventDefault();}});
```

`e.key` kontrolü modifier'lara bakmıyor. **Ctrl+P** (yazdır) ve **Ctrl+N**
(yeni pencere) basıldığında `git()` çalışır ve `preventDefault()` tarayıcının
kendi işlevini iptal eder. Üretilen HTML'de "yazdır" tamamen ölür — okuma
yüzeyi çıktı almak için tasarlanmış bir belge.

Ayrıca Caps Lock açıkken `e.key` `'N'`/`'P'` döner ve kısayol sessizce
çalışmaz (tutarsız davranış).

**Düzeltme önerisi:**

```javascript
if(e.ctrlKey||e.altKey||e.metaKey)return;
if(e.key.toLowerCase()==='n'){...}
```

**Test önerisi:** JS birim testi yerine `_JS` sabitinde `ctrlKey` guard'ının
varlığını doğrulayan string testi.

---

### B2 — `satirlari_esle`: numara-fallback, zaman damgası eşleşmesini çalıyor

**Şiddet: orta (yanlış satır eşleşmesi, sıraya bağımlı)** · `okuma_yuzeyi.py:64-78`

Eşleştirme TEK geçişte yapılıyor: her teslim cue'su için önce zaman damgası
havuzu, eşleşme yoksa **hemen** cue numarası fallback'i deneniyor. Sıraya
bağımlı bir yanlışlık var:

```
Kaynak:  S1(no=1, ts=00:01)  S2(no=2, ts=00:02)
Teslim:  D1(no=1, ts=00:09 ←bozuk)   D2(no=7, ts=00:01)
```

- D1 işlenir: ts `00:09` havuzda yok → numara fallback → **S1'i kapar**.
- D2 işlenir: ts `00:01` havuzundaki tek aday S1 ama `kullanilan`'da →
  numara fallback `7` de yok → **D2 eşleşmeden kalır**, S2 artakalana düşer.

Doğru sonuç: D2↔S1 (tam ts eşleşmesi) + D1 eşleşmesiz. Kesin bilgi (ts),
yedeğin (numara) önüne geçemiyor.

**Düzeltme önerisi:** iki geçiş — önce tüm teslim cue'ları ts ile eşleşir,
eşleşmeyenler ikinci turda numara fallback'i dener. Değişiklik ~15 satır.

**Test önerisi:** yukarıdaki senaryoyu kuran ve D2↔S1 eşleşmesini bekleyen
`satirlari_esle` birim testi.

---

### B3 — `chunk_sorgu gecmis --dosya`: filtre chunk kayıtlarına uygulanmıyor

**Şiddet: düşük-orta (yanıltıcı teşhis çıktısı)** · `chunk_gunlugu.py:309-328`,
`chunk_sorgu.py:253-284`

`cue_gecmisi` içinde `dosya` filtresi yalnız **pass** kayıtlarına uygulanıyor;
`cue_ara` ile gelen chunk kayıtları dosyaya bakılmadan listeye ekleniyor.
Cue numarası her dosyada tekrar ettiği için `--dosya film.srt` verilse bile
başka dosyaların chunk'ları sonuca karışır. `komut_bul`'da aynı filtre
chunk'lara da uygulanıyor (satır 110-111) — iki komut tutarsız.

**Düzeltme önerisi:** `cue_ara`'ya `dosya` parametresi ekle veya
`cue_gecmisi` içinde chunk sonuçlarını da aynı süzgeçten geçir.

---

### B4 — `replay_govdesi`: gövdede `model` yoksa kayıt değeri kullanılmıyor

**Şiddet: düşük (replay çağrısı eksik parametreyle patlar)** ·
`chunk_gunlugu.py:221-236`

`istek_ayarlari` = `body - messages`. `build_requests` her zaman `model`
yazdığı için ana akışta sorun yok; ama gövdesi `model` taşımayan bir kayıt
(elle/üçüncü akışla yazılmış) replay edilirse `create(**govde)` model
parametresi olmadan gider ve API hatası döner. Oysa `kayit["model"]` alanı
her zaman dolduruluyor (satır 131).

**Düzeltme önerisi:** `govde.setdefault("model", kayit.get("model") or "")`.

İlişkili ikinci nokta: sistem isteminin **rolü** (`system`/`developer`)
günlüğe yazılmıyor; replay rolü `model.startswith(...)` kuralıyla yeniden
türetiyor. Bu kural `build_requests`'tekini bugün birebir yansıtıyor ama
kayıtta rol durmadığı için kural kayarsa replay "orijinalin aynısı" vaadini
sessizce bozar. `kayit_olustur`'a `istem_rol` alanı eklenmesi önerilir.

---

### B5 — `chunk_gunlugu.budan`: `sinir=0` en yeni günlüğü de siler

**Şiddet: düşük (kenar durum; docstring ihlali)** · `chunk_gunlugu.py:345-381`

Docstring: *"En yeni günlük hiçbir koşulda silinmez."* Ama
`silinecek = yollar[max(int(sinir or 0), 0):]` — `sinir=0` verilirse
`kalanlar` boşalır, bayt döngüsü hiç çalışmaz ve **tüm günlükler silinir**.
GUI hep varsayılanı (20) geçtiği için bugün tetiklenmiyor; fonksiyon genel
bir API olarak bu vaadi taşımıyor.

**Düzeltme önerisi:** `kalanlar = yollar[:max(int(sinir or 0), 1)]` ya da
`sinir < 1` için erken dönüş.

---

### B6 — `translation_memory.fuzzy_lookup`: model kapsamı exact lookup ile asimetrik

**Şiddet: düşük-orta (çağırana bağlı, sessiz çapraz-model TM isabeti)** ·
`translation_memory.py` `fuzzy_lookup` (~satır 520-560)

Exact `lookup` ayar parmak izine (model + profanity + şema + bağlam) bağlı
hash üzerinden kapsamlanır — `model=""` ile yalnız model-agnostik satırlar
bulunur. `fuzzy_lookup` ise SQL'e `LOWER(model) = ?` koşulunu **yalnız model
boş değilken** ekliyor; `model=""` geçilirse tüm modellerin satırları aday
havuzuna girer. Çağıran iki API'ye farklı model değeri verirse (biri `""`),
fuzzy yolu başka bir modelin ürettiği çeviriyi döndürebilir — tam da
parmak izi tasarımının önlemek istediği şey.

**Düzeltme önerisi:** ya fuzzy'de de `model=""` iken `model = ''` satırlarına
kısıtlan (exact ile hizala), ya da çapraz-model eşleşme bilinçli tercihse
çağıran sözleşmesine belgele.

İlişkili küçük noktalar:
- `fuzzy_lookup` `LIMIT 500` — büyük DB'lerde uzunluk-süzülmüş aday kümesi
  500'ü aşarsa en iyi eşleşme kesilebilir (sıralama SQL'de yok; Python'da
  ratio hesaplanıyor ama yalnız ilk 500 adaya).
- `_init_db`/`_ensure_schema`: iki süreç aynı anda `ALTER TABLE` koşarsa
  ikincisi `OperationalError: duplicate column` alır → `_unavailable=True`
  → TM o oturum boyunca sessizce ölü (şema aslında doğru). `duplicate
  column` metni `unable to open` filtresini geçemiyor.

---

### B7 — `.okuma.html` üretiliyor ama kullanıcıya hiç gösterilmiyor

**Şiddet: orta (özellik görünürlüğü — üretilen değer çöpe gidiyor)** ·
`subtitle_translator_gui.py` `_write_reading_surface` (~19887), kalite raporu
diyaloğu (~39384-39422)

Teslim denetimi her dosya için `.okuma.html` üretip `audit["reading_surface_path"]`
içine yazıyor; ama bu yol `report_paths`'e girmiyor ve kalite raporu
diyaloğunda yalnız "Klasörde Göster" / "Kapat" düğmeleri var. Kullanıcı
dosyanın varlığını ancak rapor klasörünü gezerek öğreniyor — `webbrowser`
çağrısı depoda hiç yok.

**Düzeltme önerisi:** diyaloğa "Okuma Yüzeyini Aç" düğmesi
(`webbrowser.open(path.as_uri())`) + `report_paths` içine kayıt.

---

### B8 — `ht._ts_to_sec` hâlâ katı; `_ts_field_seconds` iki-parçalı damgada çöker

**Şiddet: düşük (gizli kırılganlık; mevcut çağıranlar normalize veri geçiyor)** ·
`hybrid_translate.py:344-348`, `subtitle_translator_gui.py:9493-9505`

Üç ayrı zaman-ayrıştırıcı var ve sağlamlıkları farklı:

- `ht._ts_to_sec`: `h, m, s = ts.split(':')` — zaman alanının sonunda
  koordinat/stil metadatası varsa (`00:01:20,000 X1:100`) 4 parça üretir →
  `ValueError`. GUI tarafı `_ts_field_seconds` ile bu durum için
  güçlendirildi (yorumunda açıkça yazıyor) ama ht versiyonu dokunulmadı;
  15+ çağrı noktası normalize `cue.start/end` geçtiği için bugün patlamıyor
  — yeni bir çağıran ham satır geçirirse patlar.
- `_ts_field_seconds`: `text.split(":")[:3]` fazla parçayı keser ama
  `MM:SS.mmm` (2 parça) gelirse unpack hâlâ `ValueError` verir.

**Düzeltme önerisi:** tek paylaşılan sağlam ayrıştırıcı
(`subtitle_formats`'a taşınabilir), üç çağrı ailesi ona bağlansın.

---

### B9 — `okuma_yuzeyi`: yinelenen cue numaraları geçersiz `id` üretiyor

**Şiddet: düşük** · `okuma_yuzeyi.py:163-166`

Satır kimliği `id="c<no>"` cue numarasından geliyor. Teslimde yinelenen cue
numarası varsa (denetim bunu ayrıca bulgu olarak raporluyor) üretilen
HTML'de aynı `id` birden çok `tr`'de görünür — geçersiz HTML ve
`location.hash=m[i].id` navigasyonu ilk eşleşmeye gider; ikinci işaretli
satıra `n` ile atlandığında hash yanlış yeri gösterir.

**Düzeltme önerisi:** `id`'yi satır sırasıyla tekilleştir (`c%d` → döngü
indeksi), görünen numara metni ayrı kalsın.

---

### B10 — `chunk_sorgu replay`: `_safe_chat_create` kullanmıyor, retry yok

**Şiddet: düşük (teşhis aracı sağlamlığı)** · `chunk_sorgu.py:226-233`

`istemci.chat.completions.create(**govde)` doğrudan çağrılıyor. Uygulamanın
kendisi tüm çağrıları `provider_retry`/`_safe_chat_create` üzerinden geçirir;
replay'de rate-limit/429 yeniden denemesi yok, tek denemede patlar. Kayıt
eski bir istekten geldiyse saklanan `istek_ayarlari` (ör. `temperature`)
sağlayıcının o modelde artık reddettiği parametre içerebilir — replay
"orijinalin aynısı" olmalı ama hata mesajı anlaşılır olmalı.

**Düzeltme önerisi:** bilinçli olarak ham istek korunmalı (doğru tasarım),
ama hata durumunda "parametre reddedildi — istek X tarihinden kalma"
açıklaması basılmalı.

---

### B11 — `subtitle_batch_translate.parse_srt`: index satırı varsayımı kırılgan

**Şiddet: düşük** · `subtitle_batch_translate.py:126-134`

`idx = lines[ts_pos - 1]` — `-->` satırından hemen önceki satır index
sayılıyor. Blok başında birden çok başlık/comment satırı varsa (ör.
NOTE-benzeri içerik ya da çift numaralı bozuk blok) son başlık satırı index
olur — index gerçek cue numarasından farklılaşır, `file_map` eşleşmesi
kayar. Ana `parse_any` zinciriyle ayrışma kuralları diverge ediyor (iki ayrı
SRT parser'ı var; uzun vadeli birleştirme önerisi).

---

## BÖLÜM 2 — ÖNCEKİ RAPORLARDAN, GÜNCEL KODDA HÂLÂ AÇIK OLANLAR

Bu turda her madde güncel kaynakta tekrar doğrulandı.

| # | Bulgu | Kaynak | Durum kanıtı |
|---|-------|--------|--------------|
| A1 | `is_sdh_descriptor` "sound noun ending" dalı sıradan diyalogu SDH-only sanıyor ("Paul's found the ring", "we heard a distant crash"). Zamir koruması çekimli `'s` biçimlerini görmüyor; `bare_text` yolunda da çalışıyor. Etki: `strip_sdh_line` satırı siliyor, boş-çeviri koruması cue'yu düşürüyor, standalone batch cue'yu hiç yazmıyor. | 2026-09-11 BULGU 1 | `sdh_cleaner.py:860-863` — dal değişmeden duruyor |
| A2 | `read_errors.py`: `logs/` dizinini oluşturmadan `logs/batch_errors.txt` yazıyor (fresh clone'da FileNotFoundError) + sabit kodlanmış tarihsel batch id. | 2026-09-11 BULGU 2 | `read_errors.py:12,18` — değişmemiş |
| A3 | `process_results`'ın ölü `srt_files` parametresi; `resume_batch.py` hâlâ `list(record["source_hashes"])` geçiriyor — yanıltıcı imza. | Tur 2, BUG 2.7 | `subtitle_batch_translate.py:402`, `resume_batch.py:35` |
| A4 | `_fuzzy_semantic_anchors` ölü kod — hiçbir çağıranı yok. | Tur 2, BUG 2.8 | `translation_memory.py:44`, tek referans tanımın kendisi |
| A5 | `transliteration_guard_rule` her hedef dilde Türkçe küfür tablosu dayatıyor ("ass → göt, kıç"). Türkçe dışı hedeflerde prompt'u kirletiyor. | Tur 2, BUG 2.6 | `prompt_constants.py:71-86` — değişmemiş |
| A6 | `series_memory`: `if season_pos:` falsy-0 tuzağı — sezon dizini ortak kökün hemen altındaysa (`season_pos==0`) dizi hafızası kökü bulunamıyor. | Tur 2, BUG 2.5 | `series_memory.py:213` — değişmemiş |
| A7 | `is_anthropic_native = url_check.endswith("/v1") or ...` — `/v1` ile biten HER özel proxy Anthropic-native sanılıp `x-api-key` başlığı alıyor (Bearer yerine). | Tur 2, BUG 2.4 | `helper_models.py:722-723` — değişmemiş |
| A8 | `_rebalanced_two_lines` etiket-bilinçsiz `split()`: kesim noktası `<font color="…">` içine düşebilir → kapanmamış tag üretme riski. | Tur 2, BUG 2.3 | `subtitle_translator_gui.py:3454-3480` — tag guard yok |
| A9 | `_strip_srt_unsafe_ass_overrides` `{\an8}` konum etiketini SRT çıktısından koşulsuz siliyor (`_SRT_SAFE_ASS_OVERRIDE_RE` yalnız `[ibus]` kabul ediyor) — `restore_format_tags`'in geri koyduğu konum bilgisi kayboluyor. | Tur 2, BUG 2.1 | `subtitle_formats.py:1079-1091` — değişmemiş |
| A10 | `okuma_yuzeyi`: eşleşmeyen kaynak cue'ları (`artakalan`) kronolojik yerine sayfa SONUNA yığılıyor — ortadaki kayıp en sonda görünüyor, bağlam kopuyor. | 0902, BUG 11 | `okuma_yuzeyi.py:81-83` — değişmemiş |
| A11 | `mutate_batch_ids` dosyayı `utf-8` ile okuyor; BOM'lu `batch_id.txt`'nin ilk satırı `\ufeffbatch_…` olur → `is_safe_batch_id` reddeder → ilk batch id sessizce düşer. | 0902, BUG 21 | `app_state.py:116` — `utf-8-sig` değil |
| A12 | `okuma_yuzeyi._TS_RE` tek haneli saat/saatsiz VTT damgasını hiç tanımıyor. Parser (`parse_vtt`→`_vtt_ts_to_srt`) normalize ettiği için ana akışta hafifletildi; ama fonksiyon başka cue kaynağından beslenirse ts eşleşmesi tamamen numaraya düşer. | 0902, BUG 20 | `okuma_yuzeyi.py:28` — regex değişmemiş, parser normalizasyonu hafifletiyor |

Önceki raporlardaki ve bu turda teyit edilemeyen diğer maddeler (ör. Tur 1'deki
24 madde, `YENI_MODULLER_*` serileri) için ayrı doğrulama turu gerekir;
"doğrulanamadı" diye işaretlenmeden kapatılmış sayılmamalı.

---

## BÖLÜM 3 — DÜZELTİLMİŞ / GEÇERSİZ ÇIKAN İDDİALAR

| İddia | Kaynak | Güncel durum |
|-------|--------|--------------|
| `_load_settings` yakalanmayan `ValueError` ile tüm ayar yüklemesini iptal ediyor | Tur 1, BUG 5 | **Düzeltilmiş** — `subtitle_translator_gui.py:32982-32991` geniş `except` + sanitize edilmiş yedek + warn log |
| GUI zaman ayrıştırması koordinat metadatasında çöküyor | 0902, BUG 1 | **Kısmen düzeltilmiş** — `_ts_field_seconds` (`:9493`) metadata'yı yok sayıyor; ht versiyonu hâlâ katı (B8) |
| Browser raporundaki arama kutusu reflow'u, `localStorage` yazımı, video drag-drop, buton-odak kilitlenmesi | `BROWSER_*_2026-09-04` serisi | **Geçersiz/eski** — mevcut `okuma_yuzeyi.py`'de arama, video, localStorage, drag-drop ve buton YOK; dosya yalnız tablo + `n`/`p` gezintisi üretiyor. Bu maddeler mevcut kodun bug'ı değil, olmayan bir arayüzün hayali analizi — geliştirme önerisi olarak yeniden sınıflandırılmalı |

---

## BÖLÜM 4 — GELİŞTİRME ÖNERİLERİ (öncelik sıralı)

### Yüksek değer / düşük maliyet

1. **Okuma yüzeyine "Tarayıcıda Aç" düğmesi** (B7) — tek `webbrowser.open`
   çağrısı; üretilen özelliği görünür kılar.
2. **`n`/`p` kısayollarına modifier guard** (B1) — 1 satır.
3. **İki geçişli eşleştirme** (B2) — ts önce, numara sonra; ~15 satır +
   1 test.
4. **`--dosya` filtresini chunk kayıtlarına da uygula** (B3) — tutarlılık.
5. **`budan` `sinir<1` koruması** (B5) — 1 satır.
6. **`replay_govdesi` `setdefault("model")`** (B4) — 1 satır.
7. **`read_errors.py` `os.makedirs("logs", exist_ok=True)` + arg'lı batch id**
   (A2) — ya da `plans/arsiv/`e taşı.
8. **Satır `id` tekilleştirme** (B9) — döngü indeksi.

### Orta değer

9. **`is_sdh_descriptor` iki koruma** (A1) — `'s` eki soyma + `bare_text`
   yolunda isim-tamlaması reddi. 2026-09-11 raporundaki öneri aynen geçerli;
   regresyon testleri de orada yazılı.
10. **`artakalan` cue'ları kronolojik konuma yerleştir** (A10) — kayıp satır
    olması gereken yerde görünsün.
11. **`is_anthropic_native` daralt** (A7) — `/v1` son eki yerine gerçek
    anthropic domain kontrolü.
12. **`transliteration_guard_rule` hedef dile göre** (A5) — Türkçe dışında
    kuralı üretme veya dile özgü tablo.
13. **Zaman ayrıştırıcılarını birleştir** (B8) — `ht._ts_to_sec`,
    `_ts_field_seconds`, `_ts_to_sec_gui` → tek sağlam fonksiyon.
14. **TM fuzzy/exact kapsam hizalaması + `duplicate column` ALTER yarışını
    `duplicate column` metniyle yakala** (B6).
15. **`season_pos==0` düzeltmesi** (A6) — falsy-0 yerine `is not None`.
16. **`mutate_batch_ids` `utf-8-sig`** (A11) — tek kelime.
17. **`_rebalanced_two_lines` tag-bilinçli kesim** (A8) — kesim noktalarını
    görünür-sözcük sınırlarına kısıtla.
18. **`_ts_to_sec`/`_ts_field_seconds` 2-parçalı damga** (B8).

### Mimari / özellik önerileri (eski browser raporlarından süzülen, bug değil)

19. Okuma yüzeyinde istem-tarafı **arama** (kendi `<input>`'u; Ctrl+F
    yeterliyken opsiyonel) — eklendiğinde keydown guard `INPUT`+`TEXTAREA`
    +`SELECT` genişletilmeli.
20. Chunk günlüğüne `istem_rol` alanı + replay'de `_safe_chat_create`'e
    benzer parametre uyarlama uyarısı (B4/B10).
21. İki SRT parser'ının birleştirilmesi (`subtitle_batch_translate.parse_srt`
    vs `parse_any` zinciri) — diverge riskini kapatır (B11).
22. `reading_surface_path`'in `report_paths`'e ve özet rapora eklenmesi (B7).

---

## BÖLÜM 5 — REGRESYON TESTİ ÖNERİLERİ

```
tests/test_okuma_yuzeyi.py:
  - iki-geçişli eşleştirme: ts eşleşmesi numara fallback'inden önce gelir (B2)
  - artakalan cue kronolojik konumda (A10)
  - yinelenen cue numarası → tekil tr id'leri (B9)
  - _JS'te ctrlKey/altKey/metaKey guard'ı var (B1)

tests/test_chunk_gunlugu.py (yeni):
  - cue_gecmisi(dosya=...) chunk kayıtlarını da süzer (B3)
  - replay_govdesi model'siz kayıtta kayıt modelini enjekte eder (B4)
  - budan(sinir=0) en yeni dosyayı korur (B5)

tests/test_translation_memory.py:
  - fuzzy_lookup(model="") çapraz-model satır döndürmez (B6) — ya da bilinçli
    davranış belgelenir
  - _ensure_schema 'duplicate column' hatasında _unavailable olmaz (B6)

tests/test_sdh_cleaner.py:
  - is_sdh_only("she's got the ring") == False (A1)
  - is_sdh_only("we heard a distant crash") == False (A1)
  - strip_sdh_line("be offering to buy the ring") metni korur (A1)
  - is_sdh_only("[phone ring]") == True (A1, pozitif tutma)

tests/test_app_state.py:
  - BOM'lu batch_id.txt ilk id'yi kaybetmez (A11)
```

---

## BÖLÜM 6 — KAPSAM VE DÜRÜSTLÜK KAYDI

- `subtitle_translator_gui.py` (~44k satır) ve `hybrid_translate.py` (~15k
  satır) bu turda satır satır okunmadı; hedefli bölgeler (ayar yükleme,
  chunk günlüğü entegrasyonu, okuma yüzeyi yazımı, zaman ayrıştırma, satır
  dengeleme) incelendi.
- Bu turda test süiti ÇALIŞTIRILMADI; önceki turda (2026-09-11) 5431 test
  OK'du. Yukarıdaki bulguların çoğu statik kanıta dayanıyor; A1 için
  2026-09-11 raporundaki gerçek-veri ölçümü hâlâ geçerli.
- `BROWSER_*` raporlarındaki arama/video/localStorage iddiaları mevcut
  `okuma_yuzeyi.py` ile uyuşmuyor — başka bir implementasyonu tarif ediyor
  olabilirler; "bug" değil "özellik önerisi" olarak ele alınmalı.
- API anahtarı, log içeriği ve kişisel veri bu rapora taşınmadı.
