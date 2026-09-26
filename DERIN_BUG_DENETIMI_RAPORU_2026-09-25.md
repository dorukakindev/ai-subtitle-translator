# Derin Bug Denetimi Raporu — 2026-09-25

## Kapsam ve Yöntem

Depo baştan sona tarandı (~79.000 satır Python; en büyük iki dosya:
`subtitle_translator_gui.py` ~48.000 satır, `hybrid_translate.py` ~16.000 satır).

Uygulanan teknikler:

- Tüm küçük/orta modüllerin tam satır-satır incelemesi (`app_state`,
  `credential_store`, `request_cancellation`, `response_integrity`,
  `saglayicilar`, `subtitle_formats`, `sdh_cleaner`, `series_memory`,
  `translation_memory`, `helper_models`, `provider_retry`, `kilavuz`,
  `kaynak_on_kontrol`, `project_memory`, `translation_review`,
  `video_subtitles`, `folder_picker`, `ui_localization`,
  `subtitle_batch_translate`, `resume_batch`, `repair_batches`,
  `read_errors`, `chunk_sorgu`, `translation_workbench`, `pilot_runner`,
  `_smoke_test`, `belge_uret`).
- Büyük iki dosyada AST tabanlı taramalar: `finally` içinde `return`,
  değişebilir varsayılan argümanlar, iptal istisnası yutma
  (`except Exception` içinde `RequestCancelled`), üretilen-dosya tanıma,
  çıktı yolu çözümleme, checkpoint/kurtarma akışları, batch yaşam döngüsü,
  TM kapsam parametreleri, encoding algılama.
- Tüm test süiti: **3548 geçti, 12 atlandı, 2 alt-test başarısız,
  2141 alt-test geçti** (2 başarısızlık aşağıda F-2 olarak raporlandı).
- `GENEL_PROGRAM_KAPSAMLI_BUG_AVI_2026-09-22.md` (23 canlı bulgu: B1–B11,
  A1–A12) ve `plans/` altındaki eski raporlar okundu; bulgular tekrarlanmadı.

Değerlendirme: Kod tabanı çok sayıda tarihli denetim turu geçirmiş
("denetim 2026-08-20/21, madde N" yorumları) ve genel olarak son derece
sertleştirilmiş durumda. Yeni doğrulanmış bulgu sayısı az; çoğu şüphe
incelendiğinde bilinçli tasarım çıktı.

---

## Doğrulanmış Bulgular

### F-1 — Standalone batch: `[ÇEVIRI HATASI]` işareti paylaşılan hata-işareti regex'iyle uyuşmuyor

- **Konum:** `subtitle_batch_translate.py:486`
- **Karşı referans:** `subtitle_formats.py:1841-1842`

```python
# subtitle_batch_translate.py:486
translated_text = source_text or "[ÇEVIRI HATASI]"

# subtitle_formats.py:1841
_TRANSLATION_FAILURE_MARKER_RE = re.compile(
    r"\[\s*(?:HATA|ÇEVİRİ\s+EKSİK)", re.IGNORECASE)
```

**Kanıt:** `[ÇEVIRI HATASI]` düz ASCII `I` içerir (`ÇEVIRI`, `HATASI`);
regex `İ` (U+0130) içeren `ÇEVİRİ` ve `[` sonrası doğrudan `HATA` ister.
Python `re.IGNORECASE` `İ`↔`I` eşleşmesi yapmaz → işaret
`translation_failure_reason()` tarafından tanınmaz.

**Ulaşılabilirlik:** `parse_srt` metni boş cue'ları korur
(`subtitle_batch_translate.py:133`), `create_batch_requests` boş metinli
cue'ları da file_map'e ekler (`:322-328`). Boş-metin cue + eksik/duplicate
yanıt → `[ÇEVIRI HATASI]` diske yazılır.

**Etki sınırlaması (önemli):** İşaret yalnız `.partial.srt` dosyasına girer;
dosya zaten `failed_ids`/`file_failed` ile ayrıca işaretlenir ve
`is_generated_subtitle_file`/discovery `.partial.srt`'i kaynak olarak
tekrar almaz. `resume_batch.py` kurtarmayı `failed_ids` üzerinden
korur — regex'e bağımlı değil. `repair_batches.py` doğru `[HATA]` biçimini
kullanır. Dolayısıyla bu bug'ın bugün bilinen hiçbir tüketicide aktif bir
teslim hatası üretmediği doğrulandı.

- **Önem:** DÜŞÜK (latent tutarsızlık)
- **Güven:** Yüksek (mekanik olarak doğrulandı)
- **Öneri:** İşareti `[HATA]` veya `[ÇEVİRİ EKSİK]` olarak birleştir —
  gelecekte `.partial` dosyalarını tarayan bir kod eklendiğinde sessiz
  kaçak oluşmasın.

---

### F-2 — `test_public_tree_excludes_internal_working_material` bakımcı ağacında her zaman başarısız; `plans/` .gitignore'da yok

- **Konum:** `tests/test_public_repository_docs.py:44-55`
- **Test sonucu:** `plans` ve `YENİDEN ÇEVRİLECEK` alt-testleri başarısız.

Test public-tree sözleşmesini çalışma ağacındaki `Path.exists()` ile
denetliyor; yani geliştiricinin yerel çalışma dizinleri (`plans/` —
denetim raporları; `YENİDEN ÇEVRİLECEK/` — kullanıcının yeniden çeviri
kuyruğu) mevcutsa test her zaman kırmızı. Bu iki dizin repoda tracked
değil (`git ls-files` boş).

Ek bulgu: `YENİDEN ÇEVRİLECEK/` `.gitignore`'da kapsanıyor
(`.gitignore:112`), fakat **`plans/` ignore edilmiyor** — `git status`
onu `??` listeliyor, yani `git add -A` iç denetim/yetim raporları depoya
sürükler. Test niyeti (iç malzemenin public tree'ye girmemesi) doğru ama
uygulama hem çalışma ağacını denetliyor hem de ignore koruması eksik.

- **Önem:** DÜŞÜK-ORTA (test sürekli kırmızı → gerçek regresyonlar
  gözden kaçar; ignore eksiği → iç belgeler yanlışlıkla publish edilebilir)
- **Güven:** Yüksek (reproducible: `pytest tests/test_public_repository_docs.py`)
- **Öneri:** Test tracked dosyalar üzerinden çalışsın (`git ls-files`)
  veya `plans/` `.gitignore`'a eklensin.

---

### F-3 — Anthropic adaptörü: `*/v1` ile biten her URL "native" sayılıp `x-api-key` gönderiliyor

- **Konum:** `helper_models.py:721-727`

```python
url_check = (base_url or "https://api.anthropic.com/v1").lower().rstrip("/")
is_anthropic_native = (url_check.endswith("/v1")
    or "api.anthropic.com" in url_check
    or url_check.endswith("/messages") or "opencode.ai" in url_check)
if is_anthropic_native:
    headers["x-api-key"] = api_key_str
else:
    headers["Authorization"] = f"Bearer {api_key_str}"
```

`endswith("/v1")` neredeyse tüm OpenAI/Anthropic-uyumlu relay adreslerini
"native" sınıfına sokar. Anthropic-tipli yardımcı model, Bearer bekleyen
bir proxy/relay'de (ör. `https://relay.example.com/v1`) yanlış auth
başlığıyla gider → HTTP 401. Kullanıcı tipik resmi Anthropic adresini
kullandığında sorun yok; kusur yalnız `/v1` ile biten üçüncü-parti
Anthropic-uyumlu uçlarda görünür.

- **Önem:** DÜŞÜK (egzotik kurulum gerektirir; hata görünür 401,
  sessiz veri bozulması değil)
- **Güven:** Orta (mantık kusuru net; etki daraltılmış çünkü adaptör
  yalnız anthropic-tipli sağlayıcıda çağrılır)
- **Öneri:** Karar `api.anthropic.com` ve bilinen relay hostlarına
  indirilsin; ya da iki başlık denemeli tek denemeli retry eklensin.

---

## İncelenip Reddedilen Yanlış Pozitifler

Aşağıdaki adaylar araştırıldı ve **bug olmadığı** doğrulandı:

| Aday | Sonuç |
|---|---|
| `finally` bloğunda `return` isabetleri | İç içe fonksiyonların return'ü; dış finally'yi etkilemiyor |
| `arabic_author_card`, `source_has_unverified_group` kullanılmayan değişkenler | Git geçmişi bilinçli refactor kalıntısı olduğunu gösteriyor (f58a5f7); davranış hatası değil |
| `except Exception` içinde `RequestCancelled` yutulması | Tüm geniş handler'lar iptali yeniden fırlatıyor (`raise_if_cancelled`/`is_cancelled` kontrolü ile re-raise); AST taraması temiz |
| `after_cancel` içeren try blokları | Tkinter zamanlayıcısı; `RequestCancelled` ile ilgisiz |
| Dict iterasyonu sırasında atama | Python'da mevcut anahtarın değerini güncellemek güvenli |
| `== 0` / `== 1` karşılaştırmaları | Sayısal karşılaştırma, bool karışıklığı yok |
| Değişebilir varsayılan argüman (`def f(x=[])`) | Tüm üretim dosyalarında AST taraması boş döndü |
| `ProjectMemory.detect_series_key` gevşek `[Ee][Pp]?(\d+)` regex | Yalnız kendi testi kullanıyor; üretim `series_memory.parse_series_key` (sıkı) kullanıyor |
| `folder_picker.py` COM vtable indeksleri | IFileOpenDialog/IShellItemArray/IShellItem indeksleri tek tek doğrulandı; Release/CoTaskMemFree/CoUninitialize dengeli |
| PowerShell bildirim komutu (27645) | Değerler uygulama içi; tırnak temizleniyor; kullanıcı girdisi taşımıyor |
| `read_errors.py` sabit batch_id | Tek seferlik debug aracı; üretim yolu değil |
| Batch `custom_id` çakışması | `stem + path-sha + block_no` + açık `ValueError` kontrolü var |
| TM `allow_contextless_final` tutarsızlığı | Tüm çağrı noktaları (`lookup`, `lookup_batch`, `fuzzy_lookup`) bağlam parmak izi koşulunu tutarlı uyguluyor |
| UTF-16/32 BOM'suz algılama yanlış pozitifi | Aday yalnız subtitle-vari çıktıda kabul ediliyor (`read_subtitle_text`) |
| `.partial.srt` → final sızıntısı | Discovery hariç tutuyor; recovery `failed_ids`'e bağlı; final yazımı yalnız tüm chunk'lar terminal + tam sonuç + kaynak hash eşleşmesiyle |
| WinError 32 log dosyası uyarısı | Test teardown artefaktı; uygulama akışında tekrarlanabilir etki gösterilemedi |
| `temperature`/`max_tokens` reasoning modellerinde | `_normalize_chat_create_kwargs` o1/o3/o4/gpt-5/codex için normalize ediyor, system→developer dönüşümü yapıyor |

## Test Durumu

```
3548 passed, 12 skipped, 2 failed, 2141 subtests passed
```

Başarısızlar: yalnız F-2'de belgelenen iki public-tree alt-testi.
Uygulama mantığına ilişkin test başarısızlığı yok.

## Sonuç

Bu turda doğrulanmış **3 yeni bulgu** vardır; ikisi düşük önemli
(F-1 latent işaret uyuşmazlığı, F-3 egzotik sağlayıcı auth-header
seçimi), biri düşük-orta repo/test hijyeni (F-2). Kritik veya yüksek
öncelikli yeni bulgu saptanmadı — önceki raporun 23 canlı bulgusuna ek
olarak teslim-engelleyici yeni bir kusur bulunamadı. Kod tabanında
kurtarma, checkpoint, batch yaşam döngüsü, teslim denetimi ve iptal
yolları yoğun biçimde korunmuş durumda.


---

## GÜNCEL DOĞRULAMA EKİ (2026-09-25)

Bu ek, rapordaki maddelerin güncel kod tabanına karşı yeniden doğrulanmasıyla eklendi. Etiketler: GERÇEK/CANLI = bug hâlâ mevcut; DÜZELTİLDİ = kod düzeltilmiş; YANLIŞ POZİTİF = iddia yanlış; KISMEN = kısmen doğru/kısmen giderildi; DOĞRULANAMADI = yeniden üretilemedi; TASARIM = bilinçli davranış.

- **F-1 `[ÇEVIRI HATASI]` işaret uyuşmazlığı → DÜZELTİLDİ.**
  `subtitle_batch_translate.py:486` artık `[HATA]` yazar; paylaşılan
  `_TRANSLATION_FAILURE_MARKER_RE` ve `translation_failure_reason()` ile
  doğrulandı (sonuç `hata_isareti`).
- **F-2 public-tree testi + `plans/` sızıntısı → DÜZELTİLDİ.**
  `plans/` `.gitignore`'a eklendi; test artık `git ls-files` ile tracked
  içeriği denetliyor (git yoksa `exists()` geri dönüşü). 6 test/39
  alt-test yeşil.
- **F-3 `/v1` auth-header heuristiği → DÜZELTİLDİ.**
  `helper_models.py:721-727`: `endswith('/v1')` koşulu kaldırıldı;
  `x-api-key` yalnız `api.anthropic.com`, bilinen relay ve açık
  `/messages` uçlarına gidiyor.
