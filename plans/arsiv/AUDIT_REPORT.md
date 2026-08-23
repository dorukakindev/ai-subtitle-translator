# Comprehensive Audit Report: OpenAI Subtitle Translator

## Executive Summary

This audit examines the OpenAI Subtitle Translator (Windows desktop app, CustomTkinter + Turkish UI) — a desktop application for translating subtitle files (.srt, .vtt, .ass) via OpenAI API with sophisticated context-aware translation pipelines.

**Overall Assessment**: **Strong engineering foundation with sophisticated context-aware translation pipelines, but significant technical debt in code organization, testing coverage, and documentation currency.**

---

## Architecture Overview

### Three Translation Pipelines (all in `subtitle_translator_gui.py` ~6,400 lines)

| Pipeline | Entry Point | Key Characteristics |
|----------|-------------|---------------------|
| **Sync** | `_run_sync()` | `ThreadPoolExecutor`, one `chat.completions` call per chunk |
| **Batch** | `_run_batch()` → `_wait_batch()` → `_write_results()` | OpenAI Batch API (50% cheaper, async), crash recovery via `batch_id.txt` + `batch_fmap_<id>.json` |
| **Hybrid (Yardımcı Analiz)** | `_run_sync_hybrid()` / `_run_hybrid()` | Pre-pass analysis (characters, tone, terms, pronouns, emotions) → context-injected translation → multi-pass quality passes |

**Critical finding**: All three pipelines share helpers but **each has its own write/TM/report block**. A feature change often needs 3–6 touch points.

### Core Quality Machinery (the differentiator)

| Component | Location | Purpose |
|-----------|----------|---------|
| **Smart chunking** | `_make_smart_chunks*()` | Scene-aware, sentence-aware, fragment-aware chunking |
| **Context injection** | `_inject_prev_tr()`, `_chain_pairs_from_result()` | Injects prior translations as few-shot context ("Zincirleme Bağlam") |
| **Context chain** | `ContextChain` (ContextChain.py) | Maintains rolling context window across chunks |
| **Pre-pass analysis** | `hybrid_translate.analyze_file_*()` | Characters, tone, terminology, pronouns (sen/siz), scene emotions |
| **Quality passes** | `hybrid_translate._safe_chat_create()` wrappers | Consistency → Review → Critic → Polish → Native → Condense → SDH clean → Line-break → QC → `[HATA]` fill → Tag restore |

### Content Schemas (`CONTENT_SCHEMAS` dict ~line 180)

| Schema | Purpose |
|--------|---------|
| Belgesel, Dizi/Film, Anime, Çizgi Film, Belgesel/Doğa, Stand-up, Eğitim/Online Kurs, Haber/Spor, Çocuk/Öğrenci, FRP/RPG, Tiyatro/Sahne, Podcast/Röportaj, Reklam/Tanıtım, ASMR/Meditasyon, Kullanım Kılavuzu, Vlog/Günlük, Müzik/Şarkı Sözleri, Oyun/Yazılım Yerelleştirme, Gerçeklik/Şov, Bilim/Kurgu, Korku/Gerilim | Genre-specific translation rules (honorifics, tone, terminology, honorifics, cultural refs) |
| **Otomatik** | Auto-detects via `detect_content_type_with_ai()` → `_detect_categories()` (derived from schema keys) → `_match_category()` maps free-text LLM response back to schema key |

### Helper Model (`hybrid_translate.py` + `helper_models.py`)

| Role | Model (default) | Entry Point |
|------|-----------------|-------------|
| Critic, Polish, Native Reader, Condense, SDH Clean, Line-break, QC, Analysis | `gpt-5.4-mini` (OpenAI) | `hybrid_translate._safe_chat_create()` |

**Critical**: `_safe_chat_create()` strips `temperature` and maps `max_tokens` → `max_completion_tokens` for `gpt-5`/`o-series`. **Direct `client.chat.completions.create()` calls will error on these models.**

### Persistence & State

| Artifact | Purpose | Location |
|----------|---------|----------|
| `.gui_settings.json` | All UI state **except API keys** | Working dir |
| Windows Credential Manager / `keyring` (fallback: obfuscated file) | OpenAI API keys | OS credential store / `.api_keys.obf` |
| `translation_memory.db` (SQLite) | Exact + fuzzy TM (source≠target guard) | Working dir |
| `.context_cache/<stem>.json` | Cached per-file analysis (hybrid pre-pass) | Working dir |
| `.precontext.json` | Cross-file pre-context cache | Working dir |
| `logs/*.log` | Rotated logs (30 most recent kept) | `logs/` |
| `translation_memory.db` | SQLite TM (exact + fuzzy, source≠target guard) | Working dir |

### External Dependency

`hybrid_translate.py` imports from `subtitle_localizer.*` (ContextMemory, MiniMax models, SRT parsing) — resolved via `resolve_subtitle_project_path()` scanning `_KNOWN_SUBTITLE_PROJECT_PATHS` + `_SUBTITLE_PROJECT_PATH` env var + GUI field. **Hybrid mode requires this sibling project.**

---

## Code Quality Assessment

### Strengths

1. **Sophisticated context-aware pipeline** — Multi-layer context (prev lines, next lines, scene bridge, prior translations, glossary, fragment tags, full-file analysis) is genuinely sophisticated for subtitle translation.
2. **Three-pipeline architecture** correctly handles cost/quality/latency tradeoffs (sync/batch/hybrid).
3. **Smart chunking** respects scene boundaries, sentence boundaries, multi-line fragments — not naive fixed-size chunks.
4. **Context chain** (`ContextChain`) maintains rolling context window across chunks — rare in subtitle tools.
3. **Quality pipeline** (Consistency → Review → Critic → Polish → Native → Condense → SDH → Line-break → QC → HATA-fill → Tag restore) is thorough.
4. **Content schemas** (`CONTENT_SCHEMAS`) are extensible; auto-detect derives categories from schema keys automatically.
5. **Credential security**: OS credential store (Windows Credential Manager) with obfuscated-file fallback.
5. **TM with source≠target guard** prevents polluting TM with `[HATA]` fallbacks.
5. **Log rotation** (keeps 30), settings migration (legacy plaintext key migration), TM source≠target guard show production hardening.

### Critical Issues

| # | Issue | Location | Severity |
|---|-------|----------|----------|
| **C1** | **Monolithic GUI file** (~6,400 lines) — UI, business logic, 3 pipelines, prompts, helpers all in one file | `subtitle_translator_gui.py` | **Critical** |
| **C2** | **Three pipelines duplicate write/TM/report logic** — feature changes need 3–6 edits | `_run_sync`, `_run_batch`/`_write_results`, `_run_sync_hybrid`/`_run_hybrid` | **Critical** |
| **C3** | **Zero automated tests for core pipelines** — only `tests/` covers pure helpers (`ContextChain`, `inject_prev_tr`, format parsing) | `tests/` (7 test files, ~200 lines total) | **Critical** |
| **C4** | **No linting/type-checking configured** — `py_compile` only syntax check | N/A (no `ruff`, `mypy`, `pylint`) | **High** |
| **C5** | **`hybrid_translate.py` imports external sibling project** (`subtitle_localizer`) via filesystem search — fragile deployment | `hybrid_translate.py:25-45`, `resolve_subtitle_project_path()` | **High** |
| **C6** | **No type hints** in main file (~6,400 lines) | `subtitle_translator_gui.py` | **High** |
| **C6** | **God class `App`** — UI, settings, 3 pipelines, TM, logging, settings, TM, context cache, batch recovery, hybrid analysis, QC report generation all in one class | `subtitle_translator_gui.py:class App` | **High** |
| **C7** | **Legacy identifiers** (`minimax_*` → actually OpenAI helper config) — confusing | `helper_models.py`, GUI settings keys | Medium |

### Code Organization Issues

| Issue | Location | Impact |
|-------|----------|--------|
| Prompt templates as giant inline strings | `_build_sync_system_prompt()`, `ht.build_system_prompt()` | Hard to review diff, easy to drift between sync/hybrid prompts |
| Prompt building logic interleaved with API call logic | `_build_sync_system_prompt()`, `ht.build_batch_requests()` | Hard to test prompts in isolation |
| Quality passes inline in `_run_hybrid()` / `_run_sync_hybrid()` | ~200 lines each | Hard to test/extend passes independently |
| `CONTENT_SCHEMAS` dict ~400 lines inline | Top of GUI file | Hard to maintain/extend schemas |
| Settings keys as magic strings throughout | 100+ `self.vars["key"].get()` | Typos silent, no IDE support |

### Testing Gaps

| Area | Coverage | Gap |
|------|----------|-----|
| `ContextChain` | ✅ `tests/test_context_chain.py` | Good |
| `inject_prev_tr` / `_chain_pairs_from_result` | ✅ `tests/test_context_chain.py` | Good |
| Subtitle format parsing | ✅ `tests/test_subtitle_formats.py` | Good |
| Prompt building | ❌ | No tests for prompt construction |
| Chunking logic | ❌ | No tests for `_make_smart_chunks*` |
| Context injection (`_inject_prev_tr`, `_chain_pairs_from_result`) | ❌ | Only helper tests, not integration |
| Quality passes (critic/polish/native/etc.) | ❌ | Zero coverage |
| Batch pipeline (recovery, `_wait_batch`, `_write_results`) | ❌ | Zero coverage |
| Hybrid pre-pass analysis | ❌ | Zero coverage |
| TM exact/fuzzy lookup | ❌ | Zero coverage |
| Settings persistence/migration | ❌ | Zero coverage |
| Credential store (keyring/obfuscation) | ❌ | Zero coverage |
| Settings migration (legacy key migration) | ❌ | Zero coverage |

### Dependency & Deployment Risks

| Risk | Detail |
|------|--------|
| **Sibling project dependency** | `subtitle_localizer` resolved by filesystem search — breaks if folder moved/renamed; no `pip install -e` or package |
| **OpenAI model assumptions** | `_safe_chat_create()` assumes `gpt-5`/`o-series` need `max_completion_tokens` & no `temperature` — will break on new model families |
| **No pinned dependencies** | No `requirements.txt` / `pyproject.toml` / `uv.lock` / `poetry.lock` |
| **No CI/CD** | No GitHub Actions, no pre-commit, no automated test run |

### Documentation Gaps

| Doc | Status | Gap |
|-----|--------|-----|
| `AGENTS.md` | ✅ Exists, accurate | Good for agent onboarding |
| `Architecture.md` | ⚠️ Exists but **outdated** (pre-dates context chain, hybrid passes, content schemas) | Misleading if trusted |
| `AUDIT_FINDINGS.md` | ✅ This file | — |
| `README.md` / `README.md` | ❌ Missing | No user-facing docs |
| Inline docstrings | ⚠️ Sparse, mostly Turkish comments | Hard for contributors |

---

## Security Assessment

| Area | Status | Notes |
|------|--------|-------|
| API Key Storage | ✅ Good | Windows Credential Manager via `keyring`; obfuscated file fallback; legacy plaintext migration on load |
| Network Calls | ⚠️ Medium | Direct `openai` client calls; no request signing/audit log; helper model calls go through `_safe_chat_create()` but sync/batch use raw `client.chat.completions.create` |
| File I/O | ✅ Safe | Subtitle reads via `subtitle_formats.read_subtitle_text()` with encoding fallback; writes atomic-ish (write → replace) |
| Settings | ✅ Good | `.gui_settings.json` explicitly excludes API keys; legacy plaintext migration on load |
| TM Database | ✅ Safe | SQLite, parameterized queries, source≠target guard |
| Logs | ⚠️ Medium | Logs may contain source text snippets; rotated but not encrypted |

---

## Performance Characteristics

| Pipeline | Latency | Cost | Quality | Best For |
|----------|---------|------|---------|----------|
| Sync | High (sequential chunks, threaded) | Standard | Good (context chain) | Quick turnaround, small files |
| Batch | Low latency (async, 50% cost) | **50% cheaper** | Good (context chain) | Large volumes, cost-sensitive |
| Hybrid | Highest (pre-pass + multi-pass) | Highest | **Best** (full analysis + multi-pass) | High-stakes, quality-critical |

**Batch recovery**: `batch_id.txt` + `batch_fmap_<id>.json` enable crash recovery — well engineered.

---

## Refactoring Roadmap (Priority Order)

### Phase 1: Safety & Testability (Week 1–2)
1. **Add `pyproject.toml` with `ruff`, `mypy`, `pytest`** + GitHub Actions CI
2. **Extract pure functions** from `App` into testable modules:
   - `prompt_builder.py` (sync & hybrid system prompts)
   - `chunking.py` (`_make_smart_chunks*`)
   - `context_injection.py` (`_inject_prev_tr`, `_chain_pairs_from_result`, `ContextChain`)
   - `quality_passes.py` (critic/polish/native/condense/SDH/linebreak/QC)
   - `prompt_templates.py` (extract giant prompt strings)
   - `content_schemas.py` (`CONTENT_SCHEMAS` + `_detect_categories` + `_match_category`)
2. **Add tests** for each extracted module (target: 80%+ coverage on pure logic)
4. **Add type hints** to extracted modules; incrementally to `App`

### Phase 2: Pipeline Unification (Week 3–4)
5. **Extract common pipeline base class** with shared `write_results()`, `update_tm()`, `generate_report()` → 3 pipelines inherit/configure via strategy objects
6. **Extract `QualityPipeline` class** with configurable pass list (sync/hybrid both use it)
7. **Unify prompt building** — single source of truth for system prompt + chunk payload schema

### Phase 3: Architecture & Deployment (Week 5+)
8. **Extract `App` → `AppController` (pipelines, TM, settings, cache) + `MainWindow` (UI only)**
9. **Package `subtitle_localizer` as installable package** (`pip install -e ../subtitle_localizer`) or vendor it
10. **Add `pyproject.toml` with pinned deps**, `uv.lock`/`poetry.lock`
11. **Add GitHub Actions CI** (lint + typecheck + test)
12. **Write `README.md`** (install, run, configure, external project setup)

---

## Risk Register

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Sync/hybrid prompt drift | High | Quality regression | Phase 2: unify prompt builder |
| Batch pipeline bit-rot | Medium | Batch jobs silently fail | Phase 1: add batch pipeline tests |
| `subtitle_localizer` path breaks | High (if moved) | Hybrid mode broken | Phase 3: package/vendoring |
| OpenAI model API change breaks `_safe_chat_create` | Medium | Hybrid/critic passes fail | Add model capability detection; test new models |
| Settings key typo silent failure | High | Silent config bugs | Phase 1: settings dataclass with typed keys |
| TM corruption (source=target) | Low (guard exists) | Polluted TM | Guard exists; add test |

---

## Appendix: Key File Inventory

| File | Lines | Purpose |
|------|-------|---------|
| `subtitle_translator_gui.py` | ~6,400 | Main app: UI, 3 pipelines, prompts, chunking, context, TM, settings, logging, QC |
| `hybrid_translate.py` | ~1,200 | Hybrid pre-pass analysis, quality passes, `_safe_chat_create`, batch request builder |
| `subtitle_formats.py` | ~400 | SRT/VTT/ASS parsing, encoding detection (utf-8-sig → cp1254 → latin-1) |
| `translation_memory.py` | ~300 | SQLite TM (exact + fuzzy, source≠target guard) |
| `ContextChain.py` | ~200 | Rolling context window across chunks |
| `helper_models.py` | ~100 | Helper model resolution (`gpt-5.4-mini` default, alias migration) |
| `credential_store.py` | ~100 | Windows Credential Manager + obfuscated fallback |
| `subtitle_formats.py` | ~400 | SRT/VTT/ASS parse + encoding detection |
| `translation_memory.py` | ~300 | SQLite TM |
| `credential_store.py` | ~100 | Keyring + obfuscation |
| `context_cache.py` | ~100 | Per-file analysis cache |
| `hybrid_translate.py` | ~1,200 | Hybrid analysis + quality passes |
| `ContextChain.py` | ~200 | Rolling context window |
| `helper_models.py` | ~100 | Helper model resolution |
| `context_cache.py` | ~100 | Analysis cache |
| `credential_store.py` | ~100 | Credential store |
| `translation_memory.py` | ~300 | TM |
| `subtitle_formats.py` | ~400 | Format parsing |
| `hybrid_translate.py` | ~1,200 | Hybrid pipeline core |
| `ContextChain.py` | ~200 | Context chain |
| `tests/` | ~200 total | 7 test modules, pure helpers only |

---

## Conclusion

This is a **genuinely sophisticated translation tool** with context-aware pipelines that exceed most commercial subtitle tools. The engineering investment in context-aware chunking, pre-pass analysis, multi-pass quality, and batch cost optimization is substantial.

However, **the codebase has evolved beyond its architecture**: a 6,400-line God class with three duplicated pipelines, no tests on core logic, no linting/type-checking, and a fragile external dependency. The refactoring roadmap above addresses these systematically without rewriting the valuable translation logic.

**Recommended next step**: Start Phase 1 (linting, type-checking, test infrastructure, pure-function extraction) — this enables safe refactoring of the God class and pipeline unification.