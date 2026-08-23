# Derin Bug Arama — 5 Ayrı Alan Prompt'u (2026-08-22)

Her bloğu **ayrı bir yapay zekâya** ver. Alanlar bilerek çakışmıyor; aynı bulguyu
iki kişiden almamak için her prompt kendi "KAPSAM DIŞI" listesini taşıyor.

Beşinin de başına aşağıdaki **ORTAK BAŞLIK**'ı yapıştır, sonra o ajana ait alan
bloğunu ekle.

---

## ORTAK BAŞLIK (hepsine yapıştır)

```
Sen deneyimli bir Python/masaüstü uygulama denetçisisin. Aşağıdaki projede DERİN
bir hata araması yapacaksın. Düzeltme YAPMA — yalnız bul, doğrula ve raporla.

## Proje

`D:\Openai Altyazı Çevirisi` — Windows masaüstü uygulaması (CustomTkinter, Türkçe
arayüz). Altyazı dosyalarını (.srt/.vtt/.ass) OpenAI API ile çeviriyor. Çeviri
hattı "bağlam farkındalığı" için ağır mühendislik taşıyor: model izole cue değil,
çevresindeki satırları, önceki çevirileri, dosya düzeyi analizi ve tür kurallarını
görüyor.

Önce `CLAUDE.md` dosyasını oku — mimari, akışlar ve konvansiyonlar orada.
`plans/architecture-overview.md` de yardımcı olur (`Architecture.md` ESKİ, koda
karşı doğrula).

Modüller ve boyutları:
    subtitle_translator_gui.py   40421 satır   (ana uygulama, tüm akışlar)
    hybrid_translate.py          14582 satır   (analiz + kalite geçişleri)
    subtitle_formats.py           1777 satır   (parse/yaz/temizle, paylaşılan leaf)
    provider_retry.py             1664 satır   (yeniden deneme, rota failover)
    sdh_cleaner.py                1533 satır   (SDH/konuşmacı etiketi temizliği)
    helper_models.py               760 satır
    translation_memory.py          677 satır   (SQLite TM)
    series_memory.py               652 satır   (dizi kanonu)
    subtitle_batch_translate.py    590 satır
    credential_store.py            384 satır
    video_subtitles.py             370 satır
    project_memory.py              338 satır
    repair_batches.py              317 satır
    prompt_constants.py            263 satır
    response_integrity.py          155 satır
    app_state.py                   155 satır
    request_cancellation.py        152 satır
    folder_picker.py               127 satır

## Dört çeviri akışı (hepsi subtitle_translator_gui.py içinde)

`_start()` mod × hybrid toggle'ına göre dağıtır:
  - `_run_sync`            — düz senkron, ThreadPoolExecutor, chunk başına bir istek
  - `_run_sync_hybrid`     — "Yardımcı Analiz" açık senkron (kullanıcının FİİLİ yolu)
  - `_run_batch` → `_wait_batch` → `_write_results`  — OpenAI Batch API
  - `_run_hybrid` → `_wait_batch_hybrid`             — analizli batch
Bir değişiklik genelde İLGİLİ TÜM AKIŞLARA uygulanmalıdır; ortak yardımcıları
paylaşırlar ama her birinin kendi yazma/TM/rapor bloğu vardır.

## Yöntem — bunlara uy

1. **Statik okuma + hedefli çalıştırma.** Bulduğun her maddeyi mümkünse küçük bir
   Python parçacığıyla ÇALIŞTIRARAK doğrula ve çıktısını rapora koy. Doğrulanmamış
   madde "şüphe" olarak ayrı başlıkta dursun.
2. **Test paketini çalıştırma konusunda DİKKAT.** Komut
   `python -m unittest discover -s tests` (4037 test, pytest yok). Ancak testler
   canlı uygulamayla proje kökünü paylaşıyor (`batch_id.txt`, `logs/`): TEK MODÜL
   çalıştırınca `tests/customtkinter.py` stub'ı devreye girmez, gerçek Tk penceresi
   açılır ve açılıştaki yarım-batch kontrolü kullanıcının EKRANINDA modal pencere
   açabilir — "Seçilenleri Sil" düğmesi parası ödenmiş bir batch'in kurtarma
   verisini siler. App oluşturan hiçbir testi tek başına çalıştırma; gerekirse
   `tests/_gui_app.py::make_app` kullan. Kullanıcı çeviri yapıyorsa hiç çalıştırma.
3. **Test bir tasarımı BELGELİYOR olabilir.** "Şu satırı değiştirsem test kırılıyor"
   demek çoğu zaman "bu bilinçli bir karar" demektir. Önerini yazmadan önce ilgili
   testi oku; testin adı ve docstring'i niyeti söyler. Bilinçli tasarımı bug diye
   raporlamak bu projede en sık yapılan hata.
4. **Dedektör/otomatik-düzeltme önerilerini GERÇEK dosyada ölç.** Depoda kullanıcının
   gerçek teslim ettiği yüzlerce `.srt` var:
   `HAZIR DİZİLER/`, `HAZIR FİLMLER/`, `DİZİLER/`, `FİLMLER/`.
   (Tararken `Raporlar/`, `Kaynak/`, `Ham/`, `Kurtarma/`, `Yedekler/`, `Arsiv/`
   klasörlerini ve `.ham.`/`.partial.`/`.bak.` adlarını ELE — onlar ara dosyalar.)
   Yeni bir kural öneriyorsan yanlış pozitif oranını bu külliyatta ölç ve rakamı
   rapora yaz. Ölçülmemiş kural bu projede güvenilmez sayılıyor: geçmişte önerilen
   4 kuralın yanlış-pozitif oranı %30-100 çıktı, biri çeviriyi bozuyordu.
   **Bu dosyaları yalnız OKU — hiçbirini değiştirme.**
5. **Hiçbir dosyayı, ayarı veya çalışan süreci değiştirme.** API çağrısı yapma.
   `python -m py_compile <dosya>` serbest.

## Zaten işlenmiş — TEKRAR RAPORLAMA

Bu raporların hepsi uygulandı; bulguları ve "bilinçli tasarım" kararları içinde:
  - `DERIN_BUG_DENETIMI_2026-08-20.md`            (48 madde)
  - `YENI_DERIN_BUGLAR_VE_DUZELTME_REHBERI.md`    (48 madde)
  - `HARIC_YENI_BUG_DENETIMI_2026-08-21.md`       (39 madde)
  - `HARIC_YENI_BUG_DENETIMI_DEVAM_2026-08-21.md` (6 madde)
  - `HARIC_YENI_BUG_DENETIMI_DEVAM_2_2026-08-22.md` (7 madde)
  - `.claude/worktrees/bug-search-report-b11b58/plans/bug-taramasi-2026-08-22.md`
    (41 madde — sonundaki "UYGULAMA DURUMU" bölümü hangi maddelerin BİLİNÇLİ
    tasarım olduğunu tek tek söylüyor)
Başlamadan önce en az son ikisini oku. Aynı maddeyi yeniden bulursan raporlama;
ama ESKİ DÜZELTMENİN YENİ BİR HATA ÜRETTİĞİNİ bulursan MUTLAKA raporla.

## Rapor formatı

Markdown, madde madde. Her madde için:

    ## N. ŞİDDET (YÜKSEK/ORTA/DÜŞÜK) — tek cümlelik başlık
    **Nerede:** dosya.py:satır (fonksiyon adı)
    **Ne oluyor:** mekanizma, kod alıntısıyla
    **Neden bug:** hangi sözleşme/beklenti ihlal ediliyor
    **Etki:** kullanıcı için somut sonuç (hangi dosya, hangi ayar, hangi akış)
    **Doğrulama:** çalıştırdığın parçacık + çıktısı (yoksa "yalnız kod okuması")
    **Öneri:** düzeltme yönü (kodu YAZMA, yönü tarif et)

Sonuna iki bölüm ekle:
  - "Bakıldı, temiz çıktı" — incelediğin ama sorun bulmadığın yerler (yanlış alarm
    üretmemek ve tekrar bakılmasını önlemek için)
  - "Şüpheli ama doğrulayamadım" — mekanizmayı kanıtlayamadıkların

Şiddeti abartma. "Kullanıcının teslim ettiği altyazıyı bozuyor mu?" sorusunun
cevabı YÜKSEK/ORTA/DÜŞÜK ayrımını belirlesin.
```

---

## ALAN A — Batch API hattı ve çökme kurtarma

```
## SENİN ALANIN: Batch API hattı, oturum durumu ve çökme kurtarma

Bu hat geçmişte İKİ KEZ bozuldu ve para kaybettirdi; en riskli alan burası.
OpenAI Batch işleri ÖN ÖDEMELİDİR — bağlantısı kopan bir batch, kullanıcının
ikinci kez ödemesi demek.

### İncele

subtitle_translator_gui.py:
  - `_run_batch` (36088), `_wait_batch` (37803), `_write_results` (37950)
  - `_resume_batches` (36787), `_wait_batch_hybrid` (37059), `_run_hybrid` (38884)
  - `_run_twowave_batches` (38774), `_split_waves` (8057), `_chain_waves` (8081)
  - `_check_pending_batches` (18096) ve bekleyen-batch diyaloğu
  - batch maliyet/token muhasebesi, `_verified_token_price`, kısmi çıktı yolu
hybrid_translate.py:
  - `create_batch_session` / `_create_batch_session_unlocked`,
    `update_batch_session`, `update_recovered_batch_session`,
    `_recover_submitted_batch_links`, `batch_session_summary`,
    `prune_batch_sessions`, `_batch_id_path`, `_batch_fmap_path`
  - `build_batch_requests` (yalnız batch'e özgü yanları)
app_state.py: `mutate_batch_ids`, `best_effort_cancel_remote_batch`,
  `is_safe_batch_id`, `_interprocess_lock`
Ayrıca: `repair_batches.py`, `resume_batch.py`, `subtitle_batch_translate.py`,
  `response_integrity.py` (batch yanıtı ayrıştırma tarafı)

### Özellikle ara

- Uzak batch ↔ yerel oturum SAHİPLİĞİ: yanlış dosyaya bağlanma, iki oturumun aynı
  batch'i sahiplenmesi, oturum dosyası bozulunca ne oluyor.
- Kısmi sonuç yolları: batch `completed` ama bazı chunk'lar eksik; `expired`,
  `cancelled`, `failed` durumları; yarıda durdurma.
- `batch_id.txt` + `batch_fmap_<id>.json` çifti tutarsızlaşırsa (biri var biri yok,
  biri eski) ne oluyor.
- İki-dalgalı batch (`twowave`, varsayılan KAPALI, gerçek dosyada hiç doğrulanmadı):
  dalga sınırında zincirleme bağlam, bir dalga başarısız olursa ne oluyor.
- Aynı anda iki uygulama örneği / iki koşu: kilitleme, atomik yazma, yarış durumu.
- Batch akışının post-processing'e girişi diğer üç akışla parite taşıyor mu
  (aynı geçişler, aynı sırayla, aynı toggle'lara bağlı mı).
- Maliyet/token raporlaması: batch %50 indirimi doğru yansıtılıyor mu, resmî
  olmayan sağlayıcı rotasında ne oluyor.

### KAPSAM DIŞI (başkası bakıyor)

Kalite geçişlerinin kendi mantığı (Critic/Polish/Native/QC/Condense/Backtrans/
Semantic), altyazı parse/yazma ve SDH katmanı, TM/ayar/kimlik kalıcılığı,
UI yaşam döngüsü ve provider_retry yeniden deneme mantığı.
```

---

## ALAN B — Kalite geçişleri ve doğrulayıcılar

```
## SENİN ALANIN: Çeviri sonrası kalite geçişleri ve güvenlik doğrulayıcıları

Bu geçişler ÇEVİRİ METNİNİ DEĞİŞTİRİYOR. Bir doğrulayıcıdaki boşluk doğrudan
teslim edilen altyazıyı bozar. Geçmişte Critic'in otomatik uyguladığı 1186
değişikliğin 4 sınıfta çeviriyi bozduğu ölçüldü (sözlük körlemesi, iyelik eki
düşmesi, çifte olumsuzlama, yazı→rakam sayı çevirimi) — o yüzden Critic artık
YALNIZ RAPOR modunda ve bu kod+testle kilitli.

### İncele

hybrid_translate.py:
  - `critic_pass_with_helper` (12912) ve Critic prompt'u
  - `native_reader_pass` (4210), `condense_fast_lines` (4730),
    `back_translation_check` (4947), `qc_auto_fix` (12547)
  - `semantic_reconciliation_pass` (8965) + `build_semantic_reconciliation_clusters`
    (8775), `_adaptive_semantic_suspects` (8690), `_semantic_cluster_batches` (8933)
  - DOĞRULAYICILAR: `validate_polish_candidate` (11802),
    `validate_condense_candidate` (12225),
    `validate_semantic_reconciliation_candidate` (12026),
    `is_safe_polish_edit`, `_has_content_word_drift`, `_has_content_word_loss`,
    `_has_medical_adjective_deletion`, `_has_word_merge`, `_has_char_deletion`,
    `_has_unanchored_negation_addition`, `find_garble_tokens`,
    `_condense_merges_speakers`, `_condense_drops_source_content`
  - `consistency_sweep` / `final_consistency_sweep`
subtitle_translator_gui.py:
  - `_run_post_process` (30866), `_run_quality_check_inline` (31299),
    `_run_final_semantic_checks` (29874)
  - Derin Teslim Anlam Taraması: `_deep_delivery_target_coverage` (29541),
    `_deep_delivery_segment_coverage` (15238), `_deep_delivery_risk_rows` (15275)
  - `_quality_pass_has_hard_failure`, `_REQUIRED_QUALITY_PASS_KEYS`, `pass_trace`
  - terim normalizasyonu ve `_normalize_mixed_terms`

### Özellikle ara

- Bir doğrulayıcının KAÇIRDIĞI bozma sınıfı: aday metin kabul ediliyor ama anlam,
  olumsuzluk, soru kipi, sayı, özel ad, iyelik eki ya da konuşmacı kaybı var.
- Bir doğrulayıcının GEREKSİZ reddi: meşru düzeltme sessizce çöpe gidiyor
  (log'a "değişiklik yok" yazılıyor) — sessiz kayıp en tehlikelisi.
- Geçişler arası SIRA bağımlılığı: A geçişinin çıktısı B'nin varsayımını bozuyor mu.
- Aynı geçişin dört akışta farklı parametre/toggle ile çağrılması.
- Kapsam bütçesi (Derin Tarama varsayılan %35): bütçe neye harcanıyor, öncelik
  listesi doğru mu, bütçe dolunca ne atlanıyor ve kullanıcı bunu görüyor mu.
- API hatası / kesik JSON / iptal durumunda geçişin kısmi sonucu uygulanıyor mu.
- `quality_report_only` (varsayılan AÇIK) hangi geçişi gerçekten durduruyor,
  hangisini durdurmuyor — ve UI metni bunu doğru anlatıyor mu.

### KAPSAM DIŞI (başkası bakıyor)

Batch API hattı ve oturum kurtarma, altyazı parse/yazma ve SDH temizliği,
TM/ayar/kimlik kalıcılığı, UI yaşam döngüsü ve raporlama.
```

---

## ALAN C — Altyazı G/Ç, biçim katmanı ve SDH

```
## SENİN ALANIN: Altyazı okuma/yazma, biçim dönüşümleri ve SDH temizliği

Bu katman teslim edilen DOSYAYI üretiyor. Buradaki bir hata her akışı aynı anda
vurur ve genelde sessizdir: cue kayar, etiket kaybolur, satır birleşir.

### İncele

subtitle_formats.py (TAMAMI — paylaşılan leaf modül):
  - `read_subtitle_text` (utf-8-sig → cp1254 → latin-1 sırası), `parse_vtt`,
    `parse_ass`, `write_srt`, `restore_format_tags`
  - `clean_translation_source_text`, `ends_sentence`, `visible_semantic_text`,
    `translation_failure_reason`, `normalize_subtitle_control_artifacts`
  - `decode_vtt_entities`, ASS yardımcıları (`parse_ass_timer_scale`,
    `parse_ass_invisible_styles`, `ass_visible_text`, `parse_ass_wrap_style`,
    `strip_ass_drawing_segments`), `normalize_srt_timestamp_separators`
  - `is_generated_subtitle_file` / `is_generated_subtitle_name`
sdh_cleaner.py (TAMAMI):
  - `is_sdh_descriptor`, `_bracket_shape_is_label` (2026-08-22'de eklendi, GERÇEK
    dosyada ölçüldü — regresyonuna dikkat), `strip_sdh_line`, `is_sdh_only`,
    `clean_sdh_blocks`, `strip_labels_by_source`, `normalize_speaker_labels`,
    `normalize_turkish_artifacts`, `src_is_sfx_only`
video_subtitles.py: ffprobe iz seçimi, `SubtitleStream`, `selection_rank`
subtitle_translator_gui.py (yalnız biçim tarafı):
  - `_prepare_upload_ready_blocks`, `_finalize_translation_blocks`,
    `_restore_tags_blocks`, `apply_line_breaks`, `_rebalance_line_breaks`,
    `rebalance_cue_fill_pairs` / `_cue_fill_move_plan`, `_maybe_merge_cues`,
    `_normalize_delivery_ids`, `_delivery_source_map`, `_resolve_output_path`,
    `_subtitle_delivery_audit`, `normalize_foreign_titles/exonyms`

### Özellikle ara

- Cue KAYBI veya KAYMASI: kaynak N cue, çıktı M cue — farkın açıklanamadığı yollar.
- Zaman damgası: taşma, negatif süre, çakışma, ondalık ayracı, ASS timer ölçeği,
  sıfır süreli cue.
- Encoding: Windows-1254 Türkçe dosya, BOM, karışık satır sonu, bozuk UTF-8.
- Etiket yaşam döngüsü: `_clean_src` neyi söküyor, `_restore_tags_blocks` neyi geri
  koyuyor — arada değişen cue metninde eşleşme bozuluyor mu; `{\an8}`, `<i>`,
  ASS çizim komutları, VTT ruby/konuşmacı etiketleri.
- SDH: yeni BİÇİM kuralının (`_bracket_shape_is_label`) kaçırdığı ya da fazladan
  sildiği sınıflar — GERÇEK teslim dosyalarında ölç, rakam ver.
- Satır kırma ve birleştirme: genişlik/CPS sınırları, çok satırlı cümle grupları,
  diyalog tiresi, sarkan bağlaç.
- `.srt` dışı hedef yok — ama `.vtt`/`.ass` KAYNAK okuma yolları eksiksiz mi.

### KAPSAM DIŞI (başkası bakıyor)

Batch API hattı, kalite geçişlerinin karar mantığı, TM/ayar/kimlik kalıcılığı,
UI yaşam döngüsü ve raporlama.
```

---

## ALAN D — Kalıcılık, durum bütünlüğü ve eşzamanlılık

```
## SENİN ALANIN: Disk durumu, veritabanı, önbellekler ve eşzamanlılık

Bu katmanın hataları KALICIDIR: bozuk bir TM satırı ya da bayat bir önbellek
sonraki bütün koşulara bulaşır. Geçmişte TM'de 659 bozuk satır gerçek veriye
yazılmıştı (temizlendi), analiz önbelleği sürümü 3 hafta boyunca kod değişse de
sabit kaldı.

### İncele

translation_memory.py (TAMAMI): şema, `store_batch`, tam eşleşme + bulanık
  eşleşme (`_fuzzy_semantically_compatible`, `_entry_shape`, `_punctuation_shape`,
  `_is_question`), `_is_safe_target`, `_context_key`, bağlam parmak izi
subtitle_translator_gui.py: `_tm_context_fingerprint`, `_tm_canonical_context`,
  `_store_tm_pairs` (DİKKAT: 130k mevcut satırı geçersiz kılacak her parmak izi
  değişikliği kırıcıdır — mevcut kod bunu bilerek koruyor)
app_state.py (TAMAMI): `atomic_write_text/bytes/json`, `_replace_with_retry`
  (Windows PermissionError geri çekilmesi), `_interprocess_lock` (msvcrt),
  `state_dir`/`state_path`, `SUBTITLE_TRANSLATOR_STATE_DIR`
credential_store.py (TAMAMI): keyring, obfuscated dosya yedeği,
  `migrate_from_settings`, anahtar sızıntısı
project_memory.py, season_canon yolu, `.context_cache/<stem>.json`,
  `.precontext.json`, `analysis_fingerprint` / `CONTEXT_ANALYSIS_CACHE_VER`,
  `.sync_checkpoint.json` / `.sync_stage_checkpoint.json` ve
  `save_sync_ckpt_entry_to_store` / `clear_sync_ckpt_entries_from_store`
`.gui_settings.json` yükleme/kaydetme: `_load_settings`, `_save_settings`,
  varsayılan-AÇIK (`if "key" in d:`) vs varsayılan-KAPALI (`if d.get("key"):`)
  kalıbının doğru uygulanıp uygulanmadığı

### Özellikle ara

- Yarım yazma / süreç çökmesi: hangi dosya bozuk kalabilir, kim onu okumaya
  çalışıyor, bozuk JSON'a dayanıklılık gerçekten var mı.
- İki süreç (uygulama + bir test koşusu, ya da iki uygulama) aynı dosyaya yazarsa.
- Thread güvenliği: worker thread'lerden yazılan paylaşılan sözlükler/sayaçlar,
  Tk değişkenlerine ana thread dışından erişim, `_post_ui` marshalling'in
  atlandığı yerler.
- Önbellek GEÇERSİZLEME: parmak izine girmeyen ama davranışı değiştiren şeyler
  (prompt metni, parser, sanitizer, şema, yardımcı model). Analiz, TM ve
  checkpoint için ayrı ayrı bak.
- TM'ye yazılmaması gereken çift: kaynak==çeviri, `[HATA]`, `[ÇEVİRİ EKSİK]`,
  belirsiz/çok anlamlı kaynak — guard'lar tam mı, bulanık eşleşme onları geri
  getirebiliyor mu.
- Ayar geçişleri: eski ayar dosyası, eksik anahtar, tip değişimi, silinmiş dosya.
- Log rotasyonu ve pid koruması: canlı bir koşunun log'unu silme riski.

### KAPSAM DIŞI (başkası bakıyor)

Batch API hattı ve oturum kurtarma, kalite geçişlerinin karar mantığı, altyazı
parse/yazma ve SDH, UI yerleşimi ve raporlama.
```

---

## ALAN E — UI, koşu yaşam döngüsü, iptal ve raporlama

```
## SENİN ALANIN: Arayüz, koşu yaşam döngüsü, durdurma/iptal, API bağlantı katmanı
ve raporlama

Buradaki hatalar "uygulama çökmüyor ama yanlış şey yapıyor" sınıfındadır:
durdurma tam durdurmuyor, ilerleme yalan söylüyor, rapor teslim edilen dosyayı
temsil etmiyor, bir ayar sessizce uygulanmıyor.

### İncele

subtitle_translator_gui.py:
  - `App.__init__`, `_build_ui`, `_load_settings`/`_save_settings` ÇAĞRI SIRASI,
    `_apply_startup_geometry`, `_set_running`, `_on_close`
  - `_start`, `_resume`, `_stop`, `_stop_flag`'in okunduğu her yer:
    durdurma isteğinden sonra hangi işler yine de çalışıyor, hangi dosya yazılıyor
  - `_post_ui` / `_drain_ui_queue` / UI dispatcher, worker→UI marshalling
  - ilerleme ve ETA: `_set_progress`, `completed` sayaçları, dosya durum kartları
    (`_record_file_status`), hazır-olma kartı, istatistik kartları
  - dosya/klasör seçimi ve tarama: `_selected_files`, `_output_selection_roots`,
    sürükle-bırak, `folder_picker.py`, üretilmiş dosyanın kaynak sanılması
  - çalışma profilleri (`WORKFLOW_PROFILES`, `_apply_workflow_profile`),
    `_take_run_snapshot` / `_snap_get` / `_run_setting` — bir ayarın koşu
    içinde nereden okunduğu (snapshot mı canlı Tk değişkeni mi) tutarlı mı
  - raporlama: `build_quality_report_text`, `delivery_scan_report_lines`,
    `_record_quality_issue`, `ceviri_raporu.txt`, işlem dökümü, `YÜKLEMEYE HAZIR.txt`
  - diyaloglar: bekleyen batch, kesintiye uğramış koşu, JSONL içe aktarma
provider_retry.py (TAMAMI): yeniden deneme düzeni, `chat_create_with_compat`,
  shuai rota failover, sağlık probu, bekleme iptali
request_cancellation.py (TAMAMI), helper_models.py (`resolve_helper_model`,
  rol başına anahtar/rota devralma)

### Özellikle ara

- DURDURMA sözleşmesi: kullanıcı "Durdur"a bastıktan sonra kaç saniye/kaç istek
  daha gidiyor, yarım çıktı diske yazılıyor mu, uzak batch iptal ediliyor mu,
  bir sonraki açılışta ne görünüyor.
- Bir toggle'ın UI'da göründüğü değer ile koşuda OKUNAN değerin ayrışması
  (snapshot vs canlı değişken; koşu ortasında değiştirilen ayar).
- Rapor ile TESLİM EDİLEN DOSYA arasındaki uyuşmazlık: rapordaki sayı hangi
  listeden geliyor, kullanıcı raporu okuyup "temiz" sanabilir mi.
- Sessiz yutulan istisna: `except Exception: pass` bloklarından kullanıcıyı
  ilgilendiren bir başarısızlığı gizleyenler.
- Tk özgü: `after` zamanlayıcılarının temizlenmemesi, kapanışta callback,
  ölçek değişiminde yeniden yerleşim, pencerenin ekran dışına düşmesi.
- Yeniden deneme/failover: aynı isteğin iki kez gönderilmesi, iptal sırasında
  bayrak sızıntısı, kullanıcıya yanlış "başarılı" bildirimi.
- Türkçe arayüz metinleri kodun gerçekte yaptığını anlatıyor mu (yanıltıcı
  etiket bu projede kabul edilen bir hata sınıfı).

### KAPSAM DIŞI (başkası bakıyor)

Batch API oturum kurtarma iç mantığı, kalite geçişlerinin karar mantığı,
altyazı parse/yazma ve SDH, TM/önbellek/kimlik kalıcılığının iç yapısı.
```

---

## Sonuçlar gelince

Beş raporu bana ver; her maddeyi kendi worktree'mde yeniden doğrulayıp
düzelteceğim. Geçmiş turlarda oran şöyleydi: 41 maddede 36 gerçek + 5 bilinçli
tasarım, 48 maddede 47 gerçek, 39 maddede 39 gerçek. Yani yanlış pozitif azdır
ama sıfır değildir — özellikle "test bunu kilitliyor" durumlarında.
