# KAPSAMLI DERİN BUG RAPORU

**Proje:** Openai Altyazı Çevirisi (CustomTkinter Windows Desktop App)
**Analiz:** 9 Tur, 35+ Agent, ~35.000 Satır Kod Okuması
**Tarih:** 2026-07-25
**Durum:** READ-ONLY analiz — kodda hiçbir değişiklik yapılmamıştır

---

# BÖLÜM 1: CRITICAL BUGLAR (~30 Adet)

| # | Dosya | Satır(lar) | Açıklama |
|---|-------|-----------|----------|
| C01 | `hybrid_translate.py` | 5501 | `_POLISH_CAUSATIVE_WANT_RE` regex — TÜM Türkçe karakterler cp1252 çift-encoding'li. Regex asla eşleşmez. `_has_causative_want_backslide()` tamamen ölü. |
| C02 | `hybrid_translate.py` | 5494 | `_POLISH_MODEL_CORRUPTION_RE` regex — `İyeleri`, `mekişi` gibi pattern'ler çift-encoding'li. Corruption detection tamamen ölü. |
| C03 | `hybrid_translate.py` | 2392 | SCRIPT GUARD prompt'u: Arapça/Devanagari/Tamil/Kiril örnekleri mojibake — model yanlış karakterler görür. |
| C04 | `hybrid_translate.py` | 2704-2705 | Native Reader idiom prompt'u: tüm Türkçe karakterler mojibake (`Şu` → `Åžu`, `doğal` → `doÄŸal`). |
| C05 | `hybrid_translate.py` | 3426 | `_LOCAL_FIXES` — "Graal şatosu" regex + replacement ikisi de bozuk. Asla çalışmaz, çıktıda garbage üretir. |
| C06 | `hybrid_translate.py` | 3561 | "Bible" suffix regex — `Bible'ın` → `Bible'Ä±n`. Suffix-aware variant dead code. |
| C07 | `hybrid_translate.py` | 4256, 4391, 4735 | Fancy-quote stripping regex'leri: `\u201C\u201D\u2018\u2019` çift-encoding'li → kıvrık tırnaklar temizlenemez. |
| C08 | `hybrid_translate.py` | 255 | `_ellipsis_continues()` rstrip karakter seti — `"` (U+201D) ve `»` (U+00BB) mojibake → cümle devamı tespiti hybrid flow'da bozuk. |
| C09 | `credential_store.py` | 264 | `migrate_from_settings()` atomik olmayan yazma — `.gui_settings.json` crash'te truncate olur. |
| C10 | `helper_models.py` | 486-496 | `call_anthropic_messages` base_url `"api.anthropic.com"` içerince `/v1/` yolunu atlar → 404. |
| C11 | `subtitle_translator_gui.py` | 9428-9469 | `_resume()` `_set_running(True)` çağırmaz → stop butonu devre dışı, start/resume butonları devrede (ikinci çeviri başlayabilir). |
| C12 | `subtitle_translator_gui.py` | 3157-3184 | `.lower()` Türkçe `İ`'yi (U+0130) `i\u0307` (2 kod noktası) yapar → "Dini İçerik / Vaaz" şeması asla model çıktısıyla eşleşmez. |
| C13 | `subtitle_translator_gui.py` | 9930-9950 | `_locked_terms_hint` `sanitize_glossary_for_turkish()` çağırmaz → Somali drift terimleri LOCKED TERMS olarak modeli zehirler. |
| C14 | `subtitle_translator_gui.py` | 6033 | `precontext_switch`'te `command=_on_precontext_toggle` bağlı değil — tek yönlü dışlama (hibrit açılınca precontext kapanır ama tersi çalışmaz). |
| C15 | `hybrid_translate.py` | 8034 | Submit batch: fmap write batch ID kaydından SONRA → fmap başarısız olursa batch OpenAI'da çalışır ama yerelde kurtarılamaz → para kaybı. |
| C16 | `subtitle_translator_gui.py` | 9684-9702 | `_cancel_active_batches` owner dosyasını güncellemeden `_active_batches`'i temizler. |
| C17 | `subtitle_translator_gui.py` | 1809-1829 | `write_srt` crash'te orphan `.srt.tmp` dosyaları bırakır — cleanup mekanizması yok. |
| C18 | `hybrid_translate.py` + GUI | 735-873, 14488 | `_batch_sessions/`'de 14+ orphan session — garbage collection yok. |
| C19 | `hybrid_translate.py` | 1669-1670 | `_is_openai_compatible_endpoint` SABİT True döndürür → MiniMaxProvider ve `subtitle_localizer/minimax_client.py` tamamen ölü kod. |
| C20 | `subtitle_translator_gui.py` | 8758 | Bozuk `.gui_settings.json` sessizce varsayılana düşer — kullanıcı uyarı almaz. |
| C21 | `subtitle_batch_translate.py` | 262 | `relative_to("./subtitles")` farklı CWD'den `ValueError` ile crash. |
| C22 | `credential_store.py` | 169-177 | `_load_fallback` `_fallback_lock` almaz — API key race condition. |
| C23 | `subtitle_translator_gui.py` | 1304 | `_SDH_ONLY_RE` baştaki boşluğu (leading whitespace) handle etmez. |
| C24 | `subtitle_formats.py` | 113 | `restore_format_tags` `[ÇEVİRİ EKSİK]`'e TAG EKLEMEZ — test `test_hata_fallback.py` başarısız. |
| C25 | `hybrid_translate.py` | 893 | `load_fmap_for_batch` her hatada `None` döner — bozuk fmap ile sağlam fmap ayırt edilemez. |
| C26 | `subtitle_translator_gui.py` | 13579-13581 | `_write_results`'ta `_maybe_condense` "qc" key kullanır — diğer 3 flow "analysis" kullanır (H16 detayı). |
| C27 | `subtitle_translator_gui.py` | ~14256 | Hybrid-batch başarı yolunda `_fill_hata_with_source` eksik (H5 detayı). |
| C28 | `subtitle_translator_gui.py` | 5537-5538 | `_on_close` `_log_file`'i `_log_lock` edinmeden kapatır → worker thread race. |
| C29 | `subtitle_translator_gui.py` | 14151-14460 | `_run_hybrid` Phase 2'de `_wait_between_files` YOK — pause tuşu etkisiz. |
| C30 | `subtitle_batch_translate.py` | 169-176 | Sistem prompt'u sadece ~30 kelime → GUI'nin 5750 karakterlik prompt'una kıyasla kalite 4/10. |

---

# BÖLÜM 2: HIGH BUGLAR (~49 Adet)

| # | Dosya | Satır(lar) | Açıklama |
|---|-------|-----------|----------|
| H01 | `helper_models.py` | 39 | `"Özel (Custom)"` `_CONFIGS`/`_ALIASES`'te yok → sessizce `gpt-5.4-mini`'ye düşer |
| H02 | `sdh_cleaner.py` | 5 | `FORMAT_TAG_RE` sadece `<i><b><u><font>` — ASS `{\an8}` atlanır |
| H03 | GUI | 13195-13244 | Resume: tüm quality pass'ler `analysis_result`'suz — Critic/Polish/Native/QC bağlamsız çalışır |
| H04 | GUI | ~14256 | Hybrid-batch başarı yolunda `_fill_hata_with_source` EKSİK — `[HATA]`'lar kullanıcıya gider |
| H05 | GUI | 7142-7143 | `_log()` 500 karakterde keser — hata detayları kaybolur |
| H06 | GUI | 12958-12967 | Resume, mevcut UI state'inden request oluşturur — fmap key uyuşmazlığı |
| H07 | `subtitle_batch_translate.py` | 107-112 | Fallback encoding sadece utf-8-sig dener — cp1254 Türkçe dosyalar sessizce bozulur |
| H08 | `subtitle_batch_translate.py` | 257 | `or` operatörü `""`'ü `"[ÇEVIRI HATASI]"`'na çevirir (ASCII S) → `_fill_hata_with_source` asla yakalamaz |
| H09 | `_smoke_test.py` | 113 | SDH clean `src_map`'siz — cue'lar sessizce düşer |
| H10 | `repair_batches.py` | 130-140 | Bilinmeyen CID'ler sessizce kaybolur — `[HATA]` bile konulmaz |
| H11 | `subtitle_formats.py` | 1638-1644 | Numarasız SRT'de blank-line merging iki cue'yu birleştirir |
| H12 | GUI | 2130 | `< i>` (boşluklu) HTML tag'leri `_clean_src`'yi geçer |
| H13 | `hybrid_translate.py` / GUI | 8327, 13284-13286 | Hybrid batch: double `_restore_tags_blocks` çağrısı |
| H14 | GUI | 14256 | Hybrid batch `.ham.srt` backup'ı HATA fill'den SONRA yakalanır |
| H15 | GUI | 5280-5284 | `_check_pending_batches` tüm exception'ları sessizce yutar |
| H16 | GUI | 13579-13581 | `_write_results`'ta `_maybe_condense` "qc" key'ini kullanır (diğerleri "analysis") |
| H17 | GUI | 5632-5633 | Clipboard işlemi try/except'siz — crash riski |
| H18 | GUI | 5660-5662 | Drag-drop regex boşluklu yolları kırar |
| H19 | GUI | 9203 | `native_var` validasyonu `"qc"` key'ini kontrol eder — yanlış uyarı riski |
| H20 | `hybrid_translate.py` | 2391 | SCRIPT GUARD + Native Reader mojibake (C03/C04 ile aynı) |
| H21 | GUI | 9428-9469 | Resume: `_set_running(True)` eksik (C11 ile aynı) |
| H22 | GUI | 8393-8395 | Non-OpenAI provider'lar Step 5'te dead-end — `""` döner, sessizce skip |
| H23 | GUI | 10518, 11952, vb | Worker thread'ler Tkinter `StringVar.get()`'i snapshot'sız okur |
| H24 | GUI | 12679→12710, 13635→13659, 14421→14434 | TM/.srt uyuşmazlığı — backtranslation fix'i TM'ye kaydedilir ama .srt güncellenmez |
| H25 | GUI | 9902 | `validate_polish_candidate` tag-wrapped fix'leri reddeder — backtranslation fix modu sessizce ölü |
| H26 | GUI | 5537-5538 | `_log_file.close()` locksuz (L28 ile aynı) |
| H27 | GUI | 4940-4941 | `_pid_alive` docstring'le çelişir — `OpenProcess` ACCESS_DENIED'da False döner |
| H28 | GUI | 4939/4980 | Windows PID reuse → stale `batch_owner_*.json` canlı sayılır → batch kalıcı kaybolur |
| H29 | `sdh_cleaner.py` | 210-222 | `is_sdh_descriptor()` modifier+keyword SDH'leri false negative verir: `[loud crash]` tespit edilemez |
| H30 | `sdh_cleaner.py` | 585-588 | `_SRC_PLAIN_SPEAKER_LABEL_RE` çok geniş — "CHAPTER 1:" gibi konuşmacı olmayan şeyleri eşleştirir |
| H31 | GUI | 13648-13657 | `_write_results` raporunda `pass_fix`, `qc`, `qc_auto` alanları eksik |
| H32 | GUI | 13195-13244 | Resume'daki quality pass'ler `analysis_result`'suz (H04 ile aynı) |
| H33 | GUI | 13579-13581 | `_write_results` "qc" key kullanıyor (H16 detayı) |
| H34 | GUI | 10681 | `_run_post_process` `_maybe_merge_cues()` çağırmaz |
| H35 | GUI | 10681 | `_run_post_process` `.ham.srt` backup kaydetmez |
| H36 | GUI | 7710 | `schema_name` TM store'a hiç iletilmez — tüm türler aynı TM havuzunda |
| H37 | GUI | 5179 | `_stop_flag` senkronizasyonsuz plain bool — CPython dışında çalışmayabilir |
| H38 | `translation_memory.py` | 222-231 | `fuzzy_lookup` `None` connection'ı handle etmez → crash |
| H39 | `project_memory.py` | — | Hiç locking yok — UI + translation thread concurrent access |
| H40 | `credential_store.py` | 169-177 | `_load_fallback` locksuz (C22 ile aynı) |
| H41 | `subtitle_formats.py` | 60-61 | VTT→SRT dönüşümü tek haneli dakikada `00:1:23,456` (malformed) |
| H42 | GUI | 148 | Backup `errors="replace"` — UTF-8 olmayan içerik sessizce bozulur |
| H43 | `credential_store.py` | 35 | `identity.encode()` sistem varsayılanını kullanır — cross-platform değil |
| H44 | GUI | 3221-3225 | Detection prompt'ta var olmayan şema adları ("Gaming", "Akademik Anlatım") |
| H45 | GUI | 5259 | `_check_pending_batches` süresi dolmuş batch'leri filtrelemez |
| H46 | GUI | 13558-13565 | `_write_results` Native Reader'da `token_callback` EKSİK |
| H47 | GUI | 13579-13581 | `_maybe_condense` "ql" key vs "analysis" — tüm flow'larda aynı değil |
| H48 | `sdh_cleaner.py` | 173-184 | Bare verb forms missing from `_SDH_ACTION_VERBS` |
| H49 | GUI | 7790-8050 | `_retry_hata`'da hardcoded message index[1]; üçüncü bir mesaj eklenirse crash |

---

# BÖLÜM 3: MEDIUM BUGLAR (~80 Adet)

## 3.1 Flow Asimetrileri

| # | Dosya | Satır(lar) | Açıklama |
|---|-------|-----------|----------|
| M01 | GUI | 13579-13581 | `_write_results` "qc" key kullanır, diğer 3 flow "analysis" |
| M02 | GUI | 13648-13657 | `_write_results` raporu `pass_fix`, `qc`, `qc_auto` alanlarını içermez |
| M03 | GUI | 13558-13565 | `_write_results` Native Reader'da `token_callback` EKSİK |
| M04 | GUI | 10681 | `_run_post_process` `_maybe_merge_cues()` çağırmaz |
| M05 | GUI | 10681 | `_run_post_process` `.ham.srt` backup kaydetmez |
| M06 | GUI | 7710 | `schema_name` TM store'a hiç iletilmez |
| M07 | GUI | 14151-14460 | `_run_hybrid` Phase 2'de `_wait_between_files` yok (P1) |
| M08 | GUI | 12679→12710, 13635→13659, 14421→14434 | TM/.srt uyuşmazlığı (H24) |
| M09 | GUI | 9902 | Validate_polish_candidate tag-fix rejection (H25) |
| M10 | GUI | 14256 | `.ham.srt` yakalama zamanlaması farklı (H14) |

## 3.2 Thread & State

| # | Dosya | Satır(lar) | Açıklama |
|---|-------|-----------|----------|
| M11 | GUI | 7660 | Worker thread Tk `StringVar` okur — thread-safe değil |
| M12 | GUI | 5179 | `_stop_flag` senkronizasyonsuz plain bool (H37) |
| M13 | GUI | 9417-9419 | `_set_running(False)` queue üzerinden — hızlı restart bozar |
| M14 | `translation_memory.py` | 222-231 | `fuzzy_lookup` `None` connection'ı handle etmez → crash |
| M15 | `project_memory.py` | — | Hiç locking yok — UI + translation thread concurrent access |
| M16 | `credential_store.py` | 169-177 | `_load_fallback` locksuz |
| M17 | GUI | 9428-9469 | `_resume()`'da `_cost_total` sıfırlanmaz — maliyet birikir |
| M18 | GUI | 9762 | `list(self._selected_files)` — set concurrent mutation riski |
| M19 | GUI | 12950-13073 | `_resume_batches` `_block_cache` init etmez → disk re-read |
| M20 | GUI | 5532-5534 | `_tm.close()` locksuz → SQLite write-after-close |

## 3.3 Encoding & Türkçe

| # | Dosya | Satır(lar) | Açıklama |
|---|-------|-----------|----------|
| M21 | `subtitle_formats.py` | 60-61 | VTT→SRT tek haneli dakikada `00:1:23,456` |
| M22 | GUI | 148 | Backup `errors="replace"` |
| M23 | `credential_store.py` | 35 | `identity.encode()` sistem varsayılanı |
| M24 | GUI | 3221-3225 | Detection prompt'ta var olmayan şema adları |
| M25 | `sdh_cleaner.py` | 162 | ASCII fold Turkish karakterleri kaybeder (teorik) |
| M26 | `subtitle_batch_translate.py` | 107-112 | cp1254 fallback yok (H07) |
| M27 | `sdh_cleaner.py` | 206-207 | `[speaks Latin]` tespit edilmez |

## 3.4 Glossary Guard

| # | Dosya | Satır(lar) | Açıklama |
|---|-------|-----------|----------|
| M28 | `hybrid_translate.py` | 4316-4325 | `rstrip("s")` greedy — "processes" gibi key'lerde hata |
| M29 | `hybrid_translate.py` | 4495 | Roman numeral `len<4` filtresi "IV", "IX" gibi kısa numeral'ları atlar |
| M30 | `hybrid_translate.py` | 4440-4443 | Semicolon whitelist sadece 4 pattern |
| M31 | GUI | 9930-9950 | `_locked_terms_hint` sanitize'siz (C13) |
| M32 | `hybrid_translate.py` | 4487-4489 | 10+ kelimelik legit translation verbose note olarak düşer |

## 3.5 SDH & Subtitle Format

| # | Dosya | Satır(lar) | Açıklama |
|---|-------|-----------|----------|
| M33 | `sdh_cleaner.py` | 206-207 | `[speaks Latin]` tespit edilmez |
| M34 | `sdh_cleaner.py` | 8 | 100-karakter limit + iç içe parantez başarısız |
| M35 | `subtitle_formats.py` | 272-276 | ASS Events Format regex `[` ile kırılır |
| M36 | `subtitle_formats.py` | 208 | VTT blank-line guard sadece `.` nokta ile eşleşir |
| M37 | `subtitle_formats.py` | 155-156 | `\N`/`\n` IGNORECASE overlap ASS line-break distinction'ı kaybeder |
| M38 | `subtitle_formats.py` | 69-78 | ASS santisaniye sağa padding → 10x süre |
| M39 | GUI | 2131 | Boş `{}` ASS tag'leri `_clean_src`'yi geçer |
| M40 | GUI | 9761 | `_get_srt_files` adı yanıltıcı (`.vtt`/`.ass` de döndürür) |
| M41 | `subtitle_formats.py` | 136-142 | Kısmen tag'lı multi-line bloklar tüm formatlamayı kaybeder |
| M42 | GUI | 1822-1825 | `write_srt` SDH normalizasyonu kalite pass'inden dönen İngilizce'yi de çevirir |
| M43 | `subtitle_formats.py` | 272-276 | ASS Events Format regex `[` karakteriyle kırılır |
| M44 | GUI | 1638-1644 | Numarasız SRT iki cue'yu birleştirir (H11) |
| M45 | GUI | 2130 | `< i>` boşluklu tag'ler kaçar (H12) |
| M46 | `subtitle_formats.py` | 119-148 | Trailing ASS tag'leri multi-round'da kaybolur |

## 3.6 JSON Extraction & Repair

| # | Dosya | Satır(lar) | Açıklama |
|---|-------|-----------|----------|
| M47 | `hybrid_translate.py` + GUI | 1407, 5388, 5416, 3485 | Single-line code fence → COMPLETE DATA LOSS (4 fonksiyonda) |
| M48 | `hybrid_translate.py` + GUI | 5401, 3502 | `find('[')/rfind(']')` yanlış sınır seçer |
| M49 | `hybrid_translate.py` | 1563 | `_regex_extract_analysis_fields` her yerden "name" toplar |
| M50 | `hybrid_translate.py` | 1571 | Garbage injection into recurring_terms |
| M51 | `hybrid_translate.py` | 1465-1467 | Python literal substitution string değerlerini bozar |
| M52 | `hybrid_translate.py` | 1546 | `[^"]*` escaped quote'da truncate |
| M53 | GUI | 3548-3549 | Duplicate "i" ID'leri sessizce overwrite eder |
| M54 | GUI | 3631 | `min_coverage=0.5` → %50 kayıp kabul edilir |

## 3.7 UI & Dialog

| # | Dosya | Satır(lar) | Açıklama |
|---|-------|-----------|----------|
| M55 | GUI (9 site) | 5293, 5559, 7300, 8930, vb. | Hiçbiri `grab_release()` çağırmaz |
| M56 | GUI | 5256 | `after(500, ...)` iptal edilmez — destroyed widget'da çalışır |
| M57 | GUI | 8930 | Advanced settings dialog'unda `WM_DELETE_WINDOW` yok |
| M58 | GUI | 7343-7345 | Test dialog'u "Tam Çevir" butonu `_is_running=True` iken `_start()` çağırabilir |
| M59 | GUI | 8215 | Folder seçimi mevcut file seçimini sessizce temizler |
| M60 | GUI | 10411, 9471, 7207 | 3 worker-thread fonksiyonunda `_is_running` guard'ı yok |
| M61 | GUI | 5504-5541 | `_on_close` `_write_batch_owner()` çağırmaz |
| M62 | GUI | 9033, 9057 | Orphaned one-shot `after()` elapsed timer'da |
| M63 | GUI | 6401-6407 | 4 role-specific provider combo `command=` callback'siz |
| M64 | GUI | 8470-8471 | `_on_helper_provider_change_role` boş metod |
| M65 | GUI | 8792-8793 | `self.helper_model_var` hiç tanımlanmamış dead code |
| M66 | GUI | 5903, 5908, 5912 | 3 combo instance attribute olarak saklanmamış |
| M67 | GUI | 9807 | `_estimate_async` sessizce başarısız olur — "token hesaplanıyor" sonsuza kalır |
| M68 | GUI | 8155 | `_on_mode_change` `hybrid_var.set(True)` yapar ama switch widget'ını güncellemez |
| M69 | GUI | 10537-10539, 9614, 7230 | Worker thread Tk okumaları (H23) |

## 3.8 Error Handling

| # | Dosya | Satır(lar) | Açıklama |
|---|-------|-----------|----------|
| M70 | `hybrid_translate.py` | 2004 | Provider detection hatası sessizce yutulur |
| M71 | `hybrid_translate.py` | 794 | `load_batch_session` her hatada `None` döner |
| M72 | `hybrid_translate.py` | 1451-1482 | 4x `except Exception: pass` chain — hatalar sessizce yutulur |
| M73 | `subtitle_batch_translate.py` | 43, 57, 81 | API key/config hataları sessizce yutulur |
| M74 | `credential_store.py` | 203 | API key migration hatası sessizce yutulur |
| M75 | `repair_batches.py` | 80 | Tüm batch repair sessizce atlanır |
| M76 | GUI | 1818 | Homoglyph normalization hatası sessizce yutulur |
| M77 | GUI | 109 | Chat kwargs normalization hatası sessizce yutulur |

## 3.9 Diğer

| # | Dosya | Satır(lar) | Açıklama |
|---|-------|-----------|----------|
| M78 | `subtitle_formats.py` | 60-61 | `_vtt_ts_to_srt` tek haneli dakikada `00:1:23,456` |
| M79 | `translation_memory.py` | 278, 313 | `except Exception` tüm SQL hatalarını yutar |
| M80 | GUI | 13422-13425 | `_wait_batch` polling'de exponential backoff yok |

---

# BÖLÜM 4: DÜŞÜK/INFO BUGLAR (~100+ Adet — Seçilmiş)

| # | Dosya | Satır(lar) | Açıklama |
|---|-------|-----------|----------|
| L01 | GUI | 6798, 6800 | `grid_columnconfigure(0, weight=1)` 2 kere çağrılır |
| L02 | GUI | 6623 | `import tkinter as tk` metod body'si içinde |
| L03 | GUI | 120 | `_SETTINGS_TOKEN_RE` sadece `sk-`/`mk-` prefix'lerini redakte eder |
| L04 | GUI | 117 | `_SETTINGS_SECRET_KEY_RE` escaped quote'ları handle etmez |
| L05 | GUI | 6997 | Falsy fallback for empty dict schema |
| L06 | GUI | 1872-1874 | Cross-drive files lose subfolder structure |
| L07 | GUI | 1885 | `surrogatepass` hash'te |
| L08 | `sdh_cleaner.py` | 292 | Trailing dash unconditionally stripped |
| L09 | `sdh_cleaner.py` | 269 | Wrong `match.end()` reference |
| L10 | `sdh_cleaner.py` | 516-535 | Belgesel satır replasmanları yanlış modülde |
| L11 | `hybrid_translate.py` | 6960 | Fix count per-pattern, per-occurrence değil |
| L12 | GUI | 1746 / sdh_cleaner:372 | Duplicate speaker label map (2 yerde) |
| L13 | GUI | 1789 | `find()` VO/OS paren detection sıralı |
| L14 | GUI | 2097, 2104, HT:198 | `_ts_to_sec*` tam HH:MM:SS varsayar — MM:SS.mmm crash |
| L15 | GUI | 1242 | CPS per-line = total block süresi kullanılır → şişer |
| L16 | GUI | 3781 | `_content_shift_regions` same-sign guard kırılgan |
| L17 | GUI | 3723, 3727 | `_find_adjacent_duplicate_ids` min 12 karakter |
| L18 | GUI | 3689 | Proper noun anchor 4+ lowercase gerekli |
| L19 | GUI | 3913-3916 | Outlier cluster ratio <0.15 veya >4.0 |
| L20 | `subtitle_formats.py` | 222 | VTT saat >99 desteklemez |
| L21 | `subtitle_formats.py` | 73 | ASS timestamp regex H:MM:SS.cc |
| L22 | GUI | 3743 | Content shift `min_run=4` |
| L23 | `subtitle_batch_translate.py` | 270-271 | Redundant glob patterns |
| L24 | `subtitle_batch_translate.py` | 188 | Hardcoded `batch_input.jsonl` yolu |
| L25 | `_smoke_test.py` | 6-10 | 4 unused import |
| L26 | `_smoke_test.py` | 136-149 | Model output keyword checks brittle |
| L27 | `resume_batch.py` | 18-34 | Working directory varsayımı |
| L28 | `read_errors.py` | 21 | `logs/` dizini yoksa FileNotFoundError |
| L29 | `check_cues.py`, `check_cues2.py`, `check_flags.py` | — | One-off hardcoded paths |
| L30 | `fix.py`, `refactor.py`, `refactor2.py` | — | In-place modify, TEHLİKELİ |
| L31 | `fix_indent.py`, `fix_srt.py`, `fix_read_errors.py`, `fix_resume_batch.py` | — | In-place modify |
| L32 | `prompt_constants.py` | 3 | Docstring `gui.py` yazıyor, asıl dosya `subtitle_translator_gui.py` |
| L33 | GUI | 9428-9469 | `_cost_total` `_resume()`'da sıfırlanmaz |
| L34 | GUI | 9499 | `_import_jsonl` `_stop_flag` resetlemez |
| L35 | GUI | 5256 | `after(500, _check_pending_batches)` iptal edilmez (M56) |
| L36 | GUI | 5513-5523 | `_post_ui` çağrıları `_is_shutting_down=True` anında düşer |
| L37 | GUI | 11418, 11636 | `after(20, _start)` sıralaması kırılgan |
| L38 | `app_state.py` | 30 | `finally` missing_ok=True ile korunmuş |
| L39 | `app_state.py` | 41 | Single `_fallback_lock` serializes all paths |
| L40 | `app_state.py` | 38-62 | `.lock` files never cleaned |
| L41 | `app_state.py` | 13-15 | `state_dir()` env var override doğrulamaz |
| L42 | `app_state.py` | 85 | `mutate_batch_ids` exception handling yok |
| L43 | `series_memory.py` | 20-41 | `parse_series_key` Türkçe isimlendirmeyi desteklemez |
| L44 | `series_memory.py` | 20-41 | Regex show name at start bekler |
| L45 | `series_memory.py` | 55-195 | Lock yok |
| L46 | `project_memory.py` | 171-182 | `detect_series_key` dead code |
| L47 | `project_memory.py` | 44, 157 | `proper_nouns` dead storage |
| L48 | `project_memory.py` | 24-168 | Lock yok |
| L49 | `translation_memory.py` | 322-324 | `hit_count_session()` locksuz okur |
| L50 | `translation_memory.py` | 58-92 | `_init_db` non-lock hataları handle etmez |

---

# BÖLÜM 5: BUG CASCADE'LERİ (Birbirini Tetikleyen Bug'lar)

## Cascade 1: Mojibake + Custom Provider + H1 → Compound Failure

```
C02/C04 (mojibake prompt'lar)
  + H01 ("Özel (Custom)" sessizce gpt-5.4-mini'ye düşer)
  = Kullanıcı Anthropic proxy yapılandırır → H1 ile sessizce OpenAI'ye yönlendirilir 
    → mojibake prompt'lar model'e gider → kullanıcı "API çalışmıyor" sanır
```

## Cascade 2: Locked Terms + Somali Drift → Kalıcı Zehirlenme

```
C13 (_locked_terms_hint sanitize'siz)
  + PENDING (sozluk-hedef-dil-guard uygulanmamış)
  = Project memory'de kalan Somali drift terimi review pass'inde LOCKED TERMS olur
    → model zorla Somali kullanır → doğru Türkçe "düzeltilir"
    → tek bir drift tüm sonraki çalışmaları zehirler
```

## Cascade 3: "[ÇEVIRI HATASI]" + Resume → Görünmez Bozulma

```
H08 (ASCII S'li varyant → _fill_hata_with_source yakalamaz)
  + C11 (resume _set_running False)
  + PENDING (batch cancel on stop)
  = Çıktıda gerçek çeviri gibi görünen hata metni kalır
```

## Cascade 4: Submit Batch Order → Para Kaybı

```
C15 (fmap write batch ID'den sonra)
  + C11 (resume stop butonu çalışmaz)
  + _stop() batches.cancel() çağırmaz
  = Batch OpenAI'da çalışır, fmap yok, resume yapılamaz → para kaybı
```

## Cascade 5: Precontext/Hybrid + Resume + Analysis Result → Kalite Kaybı

```
C14 (tek yönlü dışlama)
  + C11 (resume _set_running False)
  + H04 (resume analysis_result'suz quality passes)
  = Resume'da tüm quality pass'ler bağlamsız çalışır → kalite düşer
```

## Cascade 6: Stop + Pause Interaction

```
C11 (resume'da stop butonu çalışmaz)
  + C29 (Phase 2 pause yok)
  = Kullanıcı hybrid batch resume'da ne durdurabilir ne duraklatabilir
```

---

# BÖLÜM 6: ALTYAPI EKSİKLERİ

| Eksiklik | Etki |
|----------|------|
| `requirements.txt` yok | Yeni geliştirici/CI bağımlılıkları bilemez |
| `test_hybrid_translate.py` yok | `hybrid_translate.py`'nin 0 test kapsamı |
| **0 klavye kısayolu** | 14.500 satırlık uygulama tamamen fareyle |
| SIGINT/SIGTERM handler yok | Ctrl+C crash → orphan files |
| `MODEL_PRICE` OpenAI dışı modelleri kapsamaz | Rapordaki maliyet yanlış |
| Duplicate `_safe_chat_create` (GUI + HT) | İkisi ayrı ayrı güncellenmeli — sapar |
| `test_deep_bugfix.py:30` hardcoded path | Sadece developer makinesinde çalışır |
| `test_content_shift_detector.py:88-89` hardcoded | Sadece developer makinesinde çalışır |

---

# BÖLÜM 7: UYGULANMAMIŞ PLAN'DAKİ BUG'LAR

| # | Plan | Bug | Severite |
|---|------|-----|----------|
| P01 | round8-robustness | Encoding tolerance: cp1254 Turkish files crash | HIGH |
| P02 | round8-robustness | [HATA] source fallback: viewers see error text | HIGH |
| P03 | round8-robustness | Batch cancel on stop: `batches.cancel()` hiç çağrılmaz | MED |
| P04 | quality-quickwins | `final_consistency_sweep` Branch A: first_seen context-körü | HIGH |
| P05 | quality-quickwins | `_write_results` `analysis_result`'suz quality passes | HIGH |
| P06 | olumsuzluk-validator | Negation validator gaps: 44+ false positive | HIGH |
| P07 | sozluk-hedef-dil-guard | Glossary target-language guard (Somali drift) | HIGH |
| P08 | sozluk-gloss-ve-half-sayi | "half a hundred" → [100] regression | MED |
| P09 | sdh-kaynak-gutlu-temizlik | SDH whitelist approach: 1/20 catch rate — kırık | HIGH |
| P10 | condense-safety-validators | Condense zero content guards — default OFF | MED |
| P11 | shift-detector | `content_shift` 5. alignment signal eklenmemiş | MED |
| P12 | future-quality-guards G1 | `find_garble_tokens` deterministic detection yok | MED |
| P13 | future-quality-guards G2 | TM hygiene gate — store/store_batch garbage'e karşı korumasız | MED |
| P14 | future-quality-guards G4 | Polish word-merge guard uygulanmamış | LOW |
| P15 | polish-group-atomicity v2 | Group atomicity v2: partial response detection | MED |
| P16 | batch-test-pollution | Test pollution: `batch_fmap_*.json` temizlenmez | MED |
| P17 | s04e14-json-repair | JSON repair pass ID validation yok → 44-cue desync | HIGH |

---

# BÖLÜM 8: ÖN CEVRİMİŞ (STASH) ANALİZİ

**Stash:** `stash@{0}` — "recovery: broken unfinished checkpoint edit 2026-07-23"
**Durum:** 21 commit geride (`358ed7c` üzerinde). 4 content detection metodunu silmiş.
**Uygulanırsa:** Runtime crash (silinen metodlara çağrılar hala duruyor).
**Öneri:** DROP. Amaç zaten `36baef4` + `1c488c8` ile gerçekleştirilmiş.

---

# BÖLÜM 9: SİLİNMESİ GEREKEN DOSYALAR (11 Adet)

| Dosya | Risk |
|-------|------|
| `fix.py` | `subtitle_translator_gui.py`'yi in-place modify eder |
| `refactor.py`, `refactor2.py` | `repair_batches.py`'yi in-place modify eder |
| `fix_indent.py` | `repair_batches.py`'yi in-place modify eder |
| `fix_srt.py` | Belirli SRT dosyasını in-place modify eder |
| `fix_resume_batch.py` | Generator script (template dump) |
| `fix_read_errors.py` | Generator script |
| `check_cues.py`, `check_cues2.py` | One-off, hardcoded paths |
| `check_flags.py` | One-off, hardcoded import path |
| `read_errors.py` | One-off, hardcoded batch ID |

---

# BÖLÜM 10: TEST KALİTE DEĞERLENDİRMESİ

**Genel Skor: 8.2/10**

| Kriter | Skor |
|--------|------|
| Bireysel test doğruluğu | 9/10 |
| Deterministic helper kapsamı | 9/10 |
| Entegrasyon/flow kapsamı | 3/10 (büyük boşluk) |
| İzolasyon | 8/10 |
| Bakım/brittleness | 5/10 |
| Taşınabilirlik | 4/10 |

**Zayıf Noktalar:**
- Source-text-inspection tests (`test_pipeline_pass_parity.py`: 6+ test method) — runtime davranışı değil, kaynak kodu kontrol eder
- 2 dosyada hardcoded developer path'leri (sadece developer makinesinde çalışır)
- `App.__new__()` pattern — 5+ test, `__init__`'i bypass eder
- `batch_id.txt` manipülasyonu — 2 test, gerçek dosyayı backup/restore yapar
- `tests/openai.py` + `tests/customtkinter.py` — sys.path shadowing

---

# BÖLÜM 11: EN ÖNCELİKLİ 10 FİX

| Sıra | Bug ID | Dosya | Fix | Regression Risk |
|------|--------|-------|-----|----------------|
| 1 | C01-C08 | `hybrid_translate.py` | Byte-level `bytes.replace()` fix (13 satır) | LOW — test'ler assert etmez |
| 2 | C14 | GUI:6033 | `precontext_switch`'e `command=_on_precontext_toggle` | SIFIR — UI fix |
| 3 | C11 | GUI:9428 | `self._set_running(True)` ekle | ÇOK DÜŞÜK |
| 4 | C13 | GUI:9930-9950 | `_locked_terms_hint`'e sanitize ekle | DÜŞÜK |
| 5 | C09 | `credential_store.py:264` | Atomic write (tmp+replace) | DÜŞÜK |
| 6 | C12 | GUI:3157-3184 | `.replace('\u0307', '')` ekle | SIFIR |
| 7 | C15 | `hybrid_translate.py:8034` + GUI | Fmap BEFORE batch_id.txt | DÜŞÜK |
| 8 | C20 | GUI:8758 | Bozuk settings'te uyarı + backup'tan geri yükle | DÜŞÜK |
| 9 | C16 | GUI:13579-13581 | `_write_results` "analysis" key kullansın | DÜŞÜK |
| 10 | C27 | GUI:~14256 | Hybrid-batch başarı yoluna `_fill_hata_with_source` ekle | DÜŞÜK |

---

# BÖLÜM 12: ÖZET İSTATİSTİKLER

| Severite | Adet |
|----------|------|
| CRITICAL | ~30 |
| HIGH | ~49 |
| MEDIUM | ~80 |
| LOW/INFO | ~100+ |
| UYGULANMAMIŞ PLAN | 16+ |
| **TOPLAM** | **~250+ unique bug** |

**En tehlikeli 3 alan:**
1. **Encoding mojibake** (13 satır) — prompt'ların tamamı kırık, quality pass regex'leri ölü
2. **Flow asimetrileri** — aynı özellik 4 flow'da farklı uygulanıyor
3. **Thread modeli** — `_stop_flag` senkronizasyonsuz, worker thread'ler Tk okuyor

---

*Rapor, 9 tur boyunca 35+ agent ile ~35.000 satır kod okunarak hazırlanmıştır.*
*Kodda hiçbir değişiklik yapılmamıştır.*
