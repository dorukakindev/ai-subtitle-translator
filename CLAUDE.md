# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Yeni oturumda çalışma düzeni ve kullanıcı yetkisi

- Sohbet geçmişi olmadan başlıyorsan önce bu dosyayı, [yeni kurulum ve çalışma rehberini](docs/YENI-KURULUM-VE-CALISMA.md), `DEVIR-NOTU.md` indeksini ve son tarihli notu oku. Bu depodaki kullanıcı tercihleri oturum sıfırlansa da geçerlidir; daha yeni açık kullanıcı talimatı varsa onu izle.
- Kullanıcı, bu proje için gerekli geliştirme araçlarını ve bağımlılıkları indirip kurmana izin verdi. Eksik Python/Git, proje paketleri ve gerekli test araçları için tekrar genel izin isteme; güvenilir/resmî kaynakları kullan, önce mevcut kurulumu denetle, Python paketlerini `.venv` içine kur ve yaptıklarını devir notuna yaz. Bu yetki ücretli API çağrısı, satın alma, format atma, kullanıcı dosyası silme veya hesap güvenliğini değiştirme yetkisi değildir.
- Kullanıcının düzeltme/geliştirme isteğini uygula; yalnız plan verip bırakma. Türkçe iletişim kur, ilgili akışları ve regresyonları kontrol et, geri alınabilir olağan adımlarda gereksiz tekrar onayı isteme.
- Her tamamlanan mantıksal düzeltme/geliştirme sonrası: ilgili testler → yalnız kendi dosyalarını stage et → kod/değişiklik commit'i → yeni tarihli devir notu ve indeks → not commit'i → mevcut ilgili dala normal push → uzak commit doğrulaması. Kullanıcı commit/push yapma derse veya hedef dalı açıkça değiştirirse o talimatı uygula.
- `git status`, dal, HEAD ve remote'u başta kaydet. Kullanıcının mevcut değişikliklerini koru; `git add -A`, `reset --hard`, `clean -fd` ve force push ile işi kolaylaştırma. Uzak dal ilerlediyse farkı incele, çalışmalarını kaybetmeden bütünleştir; hatayı aşmak için uzaktaki geçmişi ezme.
- Yeni bilgisayarda yol, Git oturumu, API kimlik bilgileri, kardeş proje ve yerel verilerin mevcut olduğunu varsayma. Gereken hesap girişini kullanıcı kendi güvenli arayüzünde yapar; sohbetten anahtar/şifre isteme. Kimlik doğrulama engelinde notu ve yerel commit'i hazır tut, push yapılmadığını açıkça söyle.


## Proje özeti

A Windows desktop app (CustomTkinter, Turkish UI) that translates subtitle files (`.srt`/`.vtt`/`.ass`) via the OpenAI API. The translation pipeline is heavily engineered for **context-aware quality**: the model sees surrounding lines, prior translations, file-level analysis, and content-genre rules — not just isolated cues.

## Commands

```powershell
# Run the app
python subtitle_translator_gui.py          # or: .\Başlat.bat

# Full test suite (unittest, no pytest)
python -m unittest discover -s tests

# Single test module / class / method
python -m unittest tests.test_context_chain
python -m unittest tests.test_context_chain.InjectPrevTrTest
python -m unittest tests.test_context_chain.InjectPrevTrTest.test_injects_prev_tr_when_ctx_present

# Compile-check after edits (there is no linter configured)
python -m py_compile subtitle_translator_gui.py hybrid_translate.py subtitle_formats.py
```

After any GUI change, do a headless smoke test — `App()` constructs the whole UI and runs `_load_settings()`:
```powershell
python -c "import subtitle_translator_gui as g; a=g.App(); a.update_idletasks(); a.destroy(); print('OK')"
```
(Tkinter emits harmless `invalid command name ... after script` lines on destroy — ignore them.)

## Architecture

### Four translation flows (all in `subtitle_translator_gui.py`, ~43k lines)
`_start()` dispatches by mode × hybrid toggle:
- **`_run_sync`** — plain sync: `ThreadPoolExecutor`, one `chat.completions` call per chunk.
- **`_run_batch` → `_wait_batch` → `_write_results`** — OpenAI Batch API (50% cheaper, async). `_resume_batches` recovers a crashed batch run from `batch_id.txt` + `batch_fmap_<id>.json`.
- **`_run_sync_hybrid` / `_run_hybrid`** — "Yardımcı Analiz" on (`_run_sync_hybrid` is the flow the project owner actually runs): a pre-pass analyzes the whole file (characters, tone, terms, pronoun/sen-siz map, scene emotions) and injects that into the translation prompt; quality passes run after.

When extending, **a change usually has to be applied to all relevant flows** — they share helpers but each has its own write/TM/report block. Grep for the existing feature's call site to find every flow.

### Request building & context (the core quality machinery)
`build_requests()` (sync/batch) and `ht.build_batch_requests()` (hybrid) build chunked JSON payloads. Each chunk's payload may carry:
- `ctx` (preceding lines), `next_ctx` (read-ahead), `prev_scene` (bridge after a scene cut), `prev_tr` (how earlier lines were *already translated* — injected via `_inject_prev_tr`/`_chain_pairs_from_result` when "Zincirleme Bağlam" is on), `glossary`, `frag` tags for multi-line sentences.
- Chunk boundaries (`_make_smart_chunks*`) prefer scene gaps, then sentence ends, and never split a multi-line-sentence fragment group.
- **Both system prompts (sync in `_build_sync_system_prompt`, hybrid in `ht.build_system_prompt`) must stay semantically aligned** — when you add a payload key or rule, update both.

### Content schemas (`CONTENT_SCHEMAS`, ~top of GUI file)
Genre-specific translation rule sets (Belgesel, Anime, FRP, etc.). The "Otomatik" option auto-detects via `detect_content_type_with_ai`, whose candidate list is **derived from `CONTENT_SCHEMAS` via `_detect_categories()`** — add a schema and detection + the UI combobox both pick it up automatically. `_match_category` maps the model's free-text answer back to a schema name.

### Post-translation passes (gated by sidebar toggles)
Consistency sweep (always) → Bağlam İncelemesi/review pass (batch only) → Critic → Polish → Native Reader → condense → SDH clean → line-break → QC. Then **always, last**: `_fill_hata_with_source` (marks any remaining `[HATA]` as `[ÇEVİRİ EKSİK]` — despite the name it no longer writes source text into the target; a cue whose source is SDH-only is dropped and counted instead) → `_restore_tags_blocks` (re-apply `<i>`/`{\an8}` etc. that `_clean_src` stripped before translation). A per-file row feeds `build_quality_report_text` → `ceviri_raporu.txt`.

### Helper / "Yardımcı" model
Critic/Polish/Native/QC/condense/analysis run through a configurable helper model resolved in `helper_models.py` (`resolve_helper_model`). Default and effective standard is **OpenAI `gpt-5.4-mini`** (MiniMax was removed; old MiniMax settings auto-migrate via `_ALIASES`). All helper calls go through `hybrid_translate._safe_chat_create`, which strips `temperature`/maps `max_tokens` for gpt-5/o-series models — **use it, not `client.chat.completions.create` directly**, or those models will error.

### External dependency
`hybrid_translate.py` imports `subtitle_localizer.*` (ContextMemory, MiniMax models, SRT parsing) from a **sibling project** resolved by `resolve_subtitle_project_path()` (`_SUBTITLE_PROJECT_PATH` / `_KNOWN_SUBTITLE_PROJECT_PATHS`, also a GUI "External Project Path" field). Hybrid mode needs it; plain sync/batch does not.

### State & persistence
- `.gui_settings.json` — all UI state **except API keys**. Keys live in the OS credential store (`credential_store.py`, Windows Credential Manager via `keyring`; obfuscated-file fallback). `_load_settings` migrates legacy plaintext keys out of the JSON on first run.
- `translation_memory.db` (SQLite, `translation_memory.py`) — exact + fuzzy TM. **Never store source==translation pairs** (the `[HATA]`-filled lines guard against this).
- `.context_cache/<stem>.json` / `.precontext.json` — cached per-file analysis so re-translation skips it.
- `logs/*.log` — auto-rotated to newest 30 at startup (`rotate_logs`).
- Boolean toggles default-ON use the `if "key" in d:` load pattern (so a saved `false` sticks); default-OFF use `if d.get("key"):`.

### File encoding
All subtitle reads go through `subtitle_formats.read_subtitle_text` (utf-8-sig → cp1254 → latin-1, then `\r\n` normalized). Don't `open(..., encoding="utf-8-sig")` directly — Windows-1254 Turkish files would crash.

## Conventions
- Tests are plain `unittest`; pure module-level helpers are extracted specifically to be testable without constructing `App` or hitting the network. Prefer adding logic as a pure function + a thin App method over inline code in a flow.
- UI strings, log messages, and comments are Turkish; code identifiers are English. Internal names like `minimax_*` are legacy (now carry the OpenAI helper config) — renaming them is out of scope, they're just identifiers.
- `plans/` holds implementation briefs; `Architecture.md` is an older overview (predates rounds of context-aware work — verify against code).

## Zorunlu devir notu

- Bu projedeki her çalışma için `docs/devir/YYYY-MM-DD-HHMM.md` oluştur; tarih/saat Europe/Istanbul olsun. Aynı adlı kayıt varsa üzerine yazma, benzersiz yeni ad seç.
- Önceki notları silme veya değiştirme. Kökteki `DEVIR-NOTU.md` dosyasını son nota bağlantı veren ve eski kayıtları koruyan bir indeks olarak güncelle.
- Notta repo, dal, başlangıç ve bitiş kod commit kimlikleri; değişen dosyalar ve amaçları; hata/kök neden/doğrulama kanıtı; özellikler ve kullanım; test komutları ve sonuçları; çalıştırılmayan kontroller; bağımlılıklar, kurulum, ayar/şema değişiklikleri; açık işler ve sonraki adımlar bulunmalı.
- Commit veya push dışında kalan değişiklikleri açıkça belirt. Önceden mevcut kullanıcı değişikliklerini kendi çalışmana katma.
- API anahtarı, erişim tokenı, şifre veya kişisel veri ekleme; makineye özgü kişisel yolları ve ham logları yayımlama. Doğrulanmamış işi tamamlanmış gösterme.
- Kod değişikliklerini commit ederek bitiş kod kimliğini belirle, sonra devir notu/indeks commit'ini oluştur ve ilgili GitHub deposuna push et. Kod değişikliği yoksa başlangıç ve bitiş kod kimlikleri aynı olabilir. Bir commit'in kendi kimliğini kendi içeriğine yazmaya çalışma.
- Push başarısını ve uzak dal kimliğini doğrulamadan “GitHub’a yüklendi” deme. Son yanıtta repo bağlantısını, tarihli devir notunun doğrudan GitHub bağlantısını ve push edilen son commit kimliğini ver. Push engellenirse bunu ve kalan yerel commit'leri açıkça bildir; force push kullanma.
