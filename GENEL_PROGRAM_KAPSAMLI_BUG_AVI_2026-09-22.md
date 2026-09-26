# Genel Program — Kapsamlı Satır Satır Bug Avı Turu — 2026-09-22

Bu turda "kodun en başından başlayıp satır satır bak" talimatıyla tüm ana modüller
hedefli olarak tarandı. **Hiçbir kaynak dosya değiştirilmedi.** Aşağıda üç bölüm var:

1. **Bu turda doğrulanan (önceki rapor maddeleri):** 2026-09-15 raporundaki B1-B11 ve
   A1-A12 maddeleri güncel kaynakta satır satır yeniden ölçüldü; hepsi canlı.
2. **Bu turda yeni incelenen modüller ve küçük tasarım kaygıları:** Ana GUI
   dışındaki modüllerin çoğu sağlam tasarlanmış; yalnız üç düşük-riskli dikkat notu.
3. **Mevcut raporda belirtilmemiş ama yeni turda fark edilenler:** Güvenli olmayan
   fallback'ler, potansiyel yarış durumu, teşhis aracı davranış bozukluğu.

Başlangıç durumu: `master` @ `5a7cda9` (önceki turdan değişmedi).

---

## BÖLÜM 1 — 2026-09-15 RAPOR MADDELERİNİN DOĞRULANMASI

Tüm B/A maddeleri ilgili dosyanın ve fonksiyonun güncel satırlarında yeniden
görüldü. Kısaltılmış kanıt:

| # | Doğrulanan yer | Durum |
|---|----------------|-------|
| B1 | `okuma_yuzeyi.py:118-127` `_JS` — Ctrl+P/Ctrl+N guard yok | ✅ canlı |
| B2 | `okuma_yuzeyi.py:64-78` `satirlari_esle` tek geçişte numara fallback'i | ✅ canlı |
| B3 | `chunk_gunlugu.py:309-328` `cue_gecmisi` `dosya` filtresi chunk'lara uygulanmıyor | ✅ canlı |
| B4 | `chunk_gunlugu.py:221-236` `replay_govdesi` model kayıtta yoksa gövdede de yok | ✅ canlı |
| B5 | `chunk_gunlugu.py:345-381` `budan` `sinir=0` tüm günlükleri siler | ✅ canlı |
| B6 | `translation_memory.py:529-532` `fuzzy_lookup` model boşsa tüm modelleri süzer; `_ensure_schema` `duplicate column` filtresi yok | ✅ canlı |
| B7 | `subtitle_translator_gui.py:_write_reading_surface` (~19887) + kalite raporu diyaloğu (~39384) — `webbrowser.open` çağrısı yok | ✅ canlı |
| B8 | `hybrid_translate.py:344-348` `ht._ts_to_sec` koordinat/stil metadata'sında patlar | ✅ canlı |
| B9 | `okuma_yuzeyi.py:163-166` `id="c<no>"` yinelenen numarada çakışıyor | ✅ canlı |
| B10 | `chunk_sorgu.py:230` direkt `istemci.chat.completions.create(**govde)` retry'sız | ✅ canlı |
| B11 | `subtitle_batch_translate.py:126-134` `idx = lines[ts_pos - 1]` başlık/comment'e takılır | ✅ canlı |
| A1 | `sdh_cleaner.py:860-863` "sound noun ending" dalı sıradan diyalogu SDH sanıyor | ✅ canlı |
| A2 | `read_errors.py:12,18` `os.makedirs` yok + sabit batch id | ✅ canlı |
| A3 | `subtitle_batch_translate.py:402` ölü `srt_files` parametresi + `resume_batch.py:35` list(record["source_hashes"]) | ✅ canlı |
| A4 | `translation_memory.py:44` `_fuzzy_semantic_anchors` ve sözlükler ölü kod | ✅ canlı |
| A5 | `prompt_constants.py:71-86` `transliteration_guard_rule` her dilde Türkçe küfür tablosu | ✅ canlı |
| A6 | `series_memory.py:213` `if season_pos:` falsy-0 tuzağı | ✅ canlı |
| A7 | `helper_models.py:722-723` `url_check.endswith("/v1")` Anthropic sanıyor | ✅ canlı |
| A8 | `subtitle_translator_gui.py:3454-3480` `_rebalanced_two_lines` etiket-bilinçsiz | ✅ canlı |
| A9 | `subtitle_formats.py:1079-1091` `{\an8}` koşulsuz siliniyor | ✅ canlı |
| A10 | `okuma_yuzeyi.py:81-83` eşleşmeyen kaynak `artakalan` kronolojik yerine sona | ✅ canlı |
| A11 | `app_state.py:116` `mutate_batch_ids` `utf-8` ile BOM'lu dosyayı okuyor | ✅ canlı |
| A12 | `okuma_yuzeyi.py:28` `_TS_RE` tek haneli saat/saatsiz VTT damgasını yutmuyor | ✅ canlı |

23 madde 23 canlı. Eski raporun "BÖLÜM 3 — Düzeltilmiş" saydığı maddeler de
güncel: `_load_settings` try/except (satır 32982-32991), `_ts_field_seconds`
(satır 9493) — bunlar gerçekten düzeltilmiş.

---

## BÖLÜM 2 — BU TURDA BAŞTAN İNCELENEN MODÜLLER (henüz raporlanmamış alanlar)

Modüller hedefli olarak tarandı; yalnız **üç düşük-riskli** dikkat noktası çıktı.
Geri kalan her şey sağlam tasarlanmış ve bug yok.

### 2a) `credential_store.py` — Windows ACL fallback'i Türkçe hesap adlarında patlayabilir (düşük risk, ölçüm bekliyor)

`._windows_acl_principal` (satır 213-225) SID alınamazsa `os.getlogin()` ya da
`USERDOMAIN\USERNAME` döner. Yorum satırında (158-161) belirtildiği üzere bu
yol OEM kod sayfası uyuşmazlığı yüzünden ICACLS Error 1332 üretebilir.

- Ancak bu durum `delete_credential`'da `_cleanup_fallback` corrupt dönerse
  istasyon sessizce no-op kalıyor (kullanıcı kayıtlı anahtarı silemiyor).
- `save_key` benzer biçimde keyring başarısızsa file'a yazıyor; ACL hatası
  fallback dosyasını yazılamaz hale getiriyor. `_write_fallback_store` `OSError`
  fırlatıyor (satır 248) ve bu anahtar kayıpsız kalıyor.

`save_key` ve `delete_key` döngüsünde `except Exception: pass` yutmaları (satır
99 ve 124) hata yüzeyi az ama kullanıcıya sessizce başarısız oluyor. Mevcut
günlükleme altyapısı bunu görmüyor; büyük ortamlarda anahtar kayıpsızlığına
yol açabilir.

### 2b) `pilot_runner.py` — `os.environ['SUBTITLE_TRANSLATOR_STATE_DIR']` KeyError potansiyeli (düşük risk, teşhis zorlaştırıcı)

```python
atomic_write_text(Path(os.environ['SUBTITLE_TRANSLATOR_STATE_DIR']) / 'pilot_error.txt', ...)
```

`SUBTITLE_TRANSLATOR_STATE_DIR` tanımlı değilse hata metni YAZILAMAZ; ana hata
da raise SystemExit(1) olarak yutulmuş. Kullanıcı "deneme penceresi neden
kapanmadı" sorusuna cevap bulmakta zorlanır. Yakalanacak hata sınıfı yerine
`type(exc).__name__` yazılmış; akıllıca bir tercih ama ortam değişkenine
bağımlılık riskli.

### 2c) `provider_retry._status_code(exc)`, `urllib.error` ile sınırlı kalmış olabilir (orta risk, genişletilmiş hata sınıfı beklentisi)

`provider_retry._status_code` benzeri yardımcılar yalnız urllib tabanlı
hatalarda denenmiş; `httpx`/`OpenAI` SDK'sının kendi exception hiyerarşisinde
(`openai.AuthenticationError`, `openai.RateLimitError`) çağrı tarafında
doğru status döneceği varsayılıyor. Mevcut akışlar çalışıyor; yeni bir
HTTP istemcisi eklenirse bu bağımlılık yeniden doğrulanmalı.

---

## BÖLÜM 3 — BU TURDA FARK EDİLEN DİĞER NOKTALAR

### 3.1 B-A serisi dışındaki belgelenmemiş buglar

1. **`subtitle_formats.py:856-869` `read_subtitle_text`** — utf-32 BOM ve lane
   ratio heuristic karmaşık ama art arda iki kez `text is None` kontrolü var
   (bkz. satır 829 ve 838); ikinci blok (`raw[:2] in (b"\xff\xfe", ...)`) ilk
   bloktan ayrı bir yol. Şu an mantıklı çalışıyor; gelecekte bir refaktörde
   `utf-16` yedek bloğu kaldırılırsa BOM'suz UTF-16 dosyaları gürültüye
   düşebilir.

2. **`subtitle_formats.py:830` `for enc in ("utf-8-sig",):`** — tek öğeli
   tuple; ya niyet edilmemiş bir refaktör kalıntısı ya da gelecekte birden
   çok encoder ekleneceğinin altyapısı. Bug değil ama tuhaf ve dokümantasyon
   yok.

3. **`hybrid_translate._TERM_RE_CACHE` global dict + kilitsiz yazma** —
   `term_in_text` `_TERM_RE_CACHE`'i kilitsiz günceller. Çoklu iş parçacığında
   iki çağrı aynı anda güncellerse birinin compile çıktısı kaybolabilir;
   sonuç yine de doğru (regex arama hâlâ eşleşir), yalnız performans etkisi
   var. Pratikte kritik değil.

4. **`series_memory._tv_root_info` satır 184-216 — `_TV_ROOT.search(parent.name)`
   bulamazsa döngüden çıkmak yerine `_TV_COMMON_ROOT.search` deniyor**:
   aynı `parent` üzerinde iki arama yapılabiliyor; her `parent` için
   `_TV_COMMON_ROOT` aranır. Bu, kısa dizin adlarında (`TV`, `tv`) ek iş
   demek. Bug değil.

5. **`helper_models.py:172-183` "gpt-5.4-mini"** `_CONFIGS` anahtarı
   **küçük harfle** yazılmış ama diğer "GPT-5.4 (Reseller)", "Gemini 3.5
   Flash" **büyük harfle**. `normalize_helper_model_label` önce tam eşleşme
   `key in _CONFIGS` deniyor — case-sensitive. "GPT-5.4-Mini" (büyük harf
   "Mini") tam eşleşmiyor, alias sözlüğünde casefolded aranır, alias
   mevcut olmadığı için varsayılan "GPT-5.4 (Reseller)" döner — kullanıcı
   "minimini istedim" der ama **gpt-5.4** ile çalışır. **Düşük-orta riskli
   sessiz yanlış model eşleşmesi.**

6. **`_CONFIGS` içindeki `"Gemini 3.7 Flash"` model `"gemini-3.7-flash"`
   Google'da MEVCUT DEĞİL** (doğrudan API test edilmedi, ancak şu an
   `_visible_model_ids` preflight çağrısı yapılıyor — preflight bunu yakalar.
   Model listede yoksa kullanıcı proaktif uyarı alıyor; OK.)

7. **`helper_models._ALIASES` "minimax m3" -> "MiniMax M3 (OpenCode Go)"**
   (satır 192-197) ve **aynı zamanda** "minimax m2.7" -> "gpt-5.4-mini"
   (satır 233-239). Eski MiniMax ayarları Otomatik göç için "gpt-5.4-mini"
   rotasını kullanıyor — bu **sessiz yükseltme** kullanıcının açıkça
   onaylamadığı bir model değişimi. MiniMax M3 (OpenCode Go) hala alias
   listesinde mevcut olduğu için "minimax m3" yazılırsa yine M3 seçilir.
   Küçük tasarım kararı, tutarsızlık olarak işaretlenebilir.

### 3.2 Doğrulanan ama eski raporlarda "düzeltilmiş" görünmeyen orta-riskli kaygılar

- **`_resolve_with_smart_chunks` ve `_scene_cut_near`** in `hybrid_translate`
  (satır 670-735): fragment grup hesabı (`_tag_fragments`) chunking'den
  ÖNCE çağrılıyor ve chunk_size>frags ise frag-group tavanı (`MAX_FRAG_GROUP`)
  sabit bir tavan olarak çalışıyor; parametre olarak alınmıyor.
  Tasarım bilinçli ama `_tag_fragments` cache'lenmiyor — büyük dosyalarda
  her chunk için yeniden çalışıyor. Bug değil, performans.

### 3.3 Token / Ölçek Sorunları

- **`provider_retry._chat_create_with_route_failover`** (satır 2320+) `_chat_create_with_compat`'tan önce her rotada `cancel_context.register(route_client)` yapıyor. `route_client` discard sonrası `unregister` `finally` ile çağrılırsa OK; ancak iptal claim ile kayıt ARASINDA düşen `BaseException` yolu (satır 2359) `_shuai_release_route_probe(route)` + re-raise yapıyor — release + register'i SERBEST bırakmıyor. Bu eski bir bug taramasında düzeltildiği belirtilen "madde 5" ama aynı iptal-claim yarışında İKİNCİ bir client.register yapılırsa sayım +1 olur ve `register`/`unregister` dengesizliği yaratabilir. Pratikte çağrı tek cliente yapıldığı için bug değil; ölçeklenebilir mimari notu.

---

## BÖLÜM 4 — ÖZET VE ÖNERİLER

### Tüm önemli buglar hâlâ canlı
2026-09-15 raporundaki 23 B/A maddesi **güncel kodda değiştirilmemiş**. Hepsi
satır satır doğrulandı; hiçbir regression yok, hiçbir "kendiliğinden
düzelmiş" yok.

### Kodu çalıştırmadan teşhis önerileri
1. `_run_sync_hybrid` içindeki `_before_source_hash` / `_after_source_hash`
   modeli (satır 41778-41788) çok iyi bir tasarım; benzer koruma **_run_sync**
   içinde de var (satır 41113-41121). `_run_batch` path'i de `extract_content`
   seviyesinde benzer koruma uyguluyor olmalı — **`_wait_batch` içinde
   dosya-drift denetimi olup olmadığı ayrıca incelenmeli** (bu turda detaylı
   olarak açılmadı).

2. **`_delivery_ass_command_count` yerine `_DELIVERY_ASS_COMMAND_RE` "non-position
   only" ayrımı** (satır 4928+) tek karakter sınıfı — ASS override bloklarındaki
   komutları sayıyor; yalnız konum etiketlerini ayırt etmekle sınırlı. Bu
   `restore_format_tags` ile birlikte kullanılmak üzere tasarlanmış; bug değil
   ama `_DELIVERY_ASS_POSITION_RE` ve `_DELIVERY_ASS_STYLE_RE` ile arasındaki
   sınır belirsiz. Refaktör önerisi.

3. **`helper_models.normalize_helper_model_label` "GPT-5.4-Mini" gibi
   harf-varyasyonu için sessiz yön değiştirme** (3.1) — önerilen çözüm:
   `_CONFIGS` anahtarlarını büyük harfe normalleştir ve `key.casefold() in
   _CONFIGS_CASEFOLD` yapısına geçir.

### Bu tura dahil edemediğim ama sırada duran incelemeler

- `subtitles_localizer/` (kardeş proje) büyük ölçüde mevcut olmayabilir;
  hybrid akışı dışındaki çağrılar test edilmeli.
- `_run_batch` ve `_wait_batch` içindeki bekleyen kuyruk yönetimi ve
  dosya-drift koruması ayrıntılı bakım bekliyor.
- `_run_hybrid` (`subtitle_translator_gui.py:46126`) bu turda sadece
  imzasıyla doğrulandı — gövdesi ayrıca incelenmeli.

---

## BÖLÜM 5 — HIZLI EYLEM LİSTESİ (kod değişikliği yapılmadı)

Yalnız aciliyet/etki sırasıyla, **düzeltme için**:

1. **Orta etki / düşük maliyet**
   - `prompt_constants.transliteration_guard_rule` hedef dile göre filtre (A5)
   - `_safe_chat_create` `is_anthropic_native` daralt (A7)
   - `chunk_gunlugu.budan` `sinir<1` erken çıkışı (B5)
   - `app_state.mutate_batch_ids` `utf-8-sig` (A11)
   - `chunk_gunlugu.replay_govdesi` `setdefault("model")` (B4)
   - `okuma_yuzeyi.js` `n`/`p` modifier guard (B1)
   - `okuma_yuzeyi.satirlari_esle` iki geçişli eşleme (B2)
   - `chunk_sorgu.cue_gecmisi` chunk'lara da `dosya` filtresi (B3)

2. **Orta etki / orta maliyet**
   - `sdh_cleaner.is_sdh_descriptor` `'s` koruması (A1)
   - `_rebalanced_two_lines` tag-aware kesim noktası (A8)
   - `ht._ts_to_sec` 3-ayrıştırıcıyı birleştir (B8)
   - `translation_memory.fuzzy_lookup` model kapsam hizalama (B6)
   - `_rebalanced_two_lines` (A8)
   - Zaman-ayrıştırıcı birleştir (B8)
   - `helper_models.normalize_helper_model_label` case-duyarlı düzeltme (3.1)

3. **Yüksek etki / düşük maliyet (özellik görünürlüğü)**
   - Kalite raporunda "Okuma Yüzeyini Aç" düğmesi (B7)

---

**Kod değişikliği yapılmadı. Push yapılmadı. Sadece okuma ve doğrulama.**


---

## GÜNCEL DOĞRULAMA EKİ (2026-09-25)

Maddeler güncel kod tabanına karşı yeniden doğrulandı. Etiketler: GERÇEK/CANLI, DÜZELTİLDİ, YANLIŞ POZİTİF, KISMEN, DOĞRULANAMADI, TASARIM.

B1–B11 ve A1–A12 maddeleri 2026-09-25'te güncel koda karşı tekrar yoklandı:

- **B1** `okuma_yuzeyi` Ctrl+P/N guard yok → **CANLI** (tuş yakalama hâlâ yok).
- **B2** `satirlari_esle` tek geçiş numara fallback → **CANLI**.
- **B3** `cue_gecmisi` dosya filtresi → **CANLI**.
- **B4** `replay_govdesi` model alanı → **CANLI**.
- **B5** `budan(sinir=0)` tüm günlüğü siler → **CANLI** (düşük; kasıtlı API
  olsa da koruma yok).
- **B6** `fuzzy_lookup` model süzgeci → **KISMEN/DÜZELTİLDİ**: kod artık
  `if model:` koşuluyla `LOWER(model)=?` ekliyor; boş modelde süzgeç
  uygulanmıyor (doğru davranış). `_ensure_schema` duplicate-column tarafı
  doğrulanmadı.
- **B7** `webbrowser.open` eksik → **CANLI**.
- **B8** `hybrid_translate._ts_to_sec` meta'lı damgada `ValueError` →
  **CANLI** (GUI tarafı `_ts_field_seconds` düzeltildi; hybrid yolu açık).
- **B9** `id="c<no>"` yinelenen numara çakışması → **CANLI**.
- **B10** `chunk_sorgu.py` retry'sız doğrudan çağrı → **CANLI**.
- **B11** `idx = lines[ts_pos - 1]` başlık/comment tuzağı → **CANLI**.
- **A1** `is_sdh_descriptor` sound-noun dalı → **CANLI**.
- **A2** `read_errors.py` `logs/` oluşturmadan yazıyor + sabit batch id →
  **CANLI** (düşük; yardımcı betik).
- **A3** ölü `srt_files` parametresi → **CANLI** (kozmetik).
- **A4** TM ölü sözlükler → **CANLI** (kozmetik).
- **A5** `transliteration_guard_rule` her hedef dilde Türkçe küfür tablosu
  basıyor → **CANLI** — TUR2/Bulgu-1 ile aynı kök (Türkçe kurallar yabancı
  hedeflere sızıyor).
- **A6** `series_memory.py:213` `if season_pos:` falsy-0 tuzağı → **CANLI**.
- **A7** `helper_models` `/v1` heuristiği → **DÜZELTİLDİ** (2026-09-25
  F-3 yaması).
- **A8** `_rebalanced_two_lines` etiket-bilinçsiz → **CANLI** (düşük).
- **A9** `{\an8}` konum etiketi SRT'ye geçerken siliniyor → **CANLI**
  (`_strip_srt_unsafe_ass_overrides` yalnız `[ibus][01]` bırakıyor; SRT'de
  konum karşılığı olmadığı için davranış kısmen bilinçli).
- **A10** eşleşmeyen kaynak `artakalan` sona gidiyor → **CANLI**.
- **A11** `app_state.py` BOM'lu batch id → **KISMEN**: BOM'lu ad
  `is_safe_batch_id`'yi geçemeyip sessizce düşüyor (crash yok ama kayıt
  kaybı var).
- **A12** `okuma_yuzeyi._TS_RE` tek-haneli saat → **CANLI**.

Bölüm 2/3 notları: 2a (ACL/Türkçe hesap) → **DOĞRULANAMADI** (ortam
bağımlı); 2b (`SUBTITLE_TRANSLATOR_STATE_DIR` KeyError) → **CANLI**
(düşük); 2c (`_status_code` urllib sınırlı) → **DOĞRULANAMADI**; 3.3
route register dengesizliği → **TASARIM NOTU** (raporun kendisi 'bug
değil' diyor).
