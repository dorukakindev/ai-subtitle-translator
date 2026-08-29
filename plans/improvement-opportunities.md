# Subtitle Batch Translator — Improvement Opportunities

Based on my code review, here are the suggested improvements organized by category.

---

## 1. Security Issues

### 1.1 API Keys Stored in Plain Text

**Problem:** [`_save_settings`](subtitle_translator_gui.py:547) writes API keys directly to [`.gui_settings.json`](.gui_settings.json) in plain text. If this file is shared or backed to cloud storage, credentials could be exposed.

**Suggested Fix:**
- Use a secure credential store like Windows Credential Manager or a keyring library
- At minimum, encrypt API keys before saving to disk
- Add a checkbox to "remember API keys" with opt-in storage rather than default

### 1.2 Hardcoded External Path

**Problem:** [`hybrid_translate.py:12`](hybrid_translate.py:12) has `SUBTITLE_PROJECT_PATH = r"<kardes-proje-yolu>"` hardcoded. This makes the code non-portable and breaks on different machines.

**Suggested Fix:**
- Make this configurable via settings or environment variable
- Add a UI field to specify the external project path
- Provide clear error message if the path doesn't exist

---

## 2. Code Quality

### 2.1 Duplicate SRT Parsing Code

**Problem:** [`parse_srt`](subtitle_translator_gui.py:42) and [`write_srt`](subtitle_translator_gui.py:53) are duplicated in both [`subtitle_translator_gui.py`](subtitle_translator_gui.py) and [`subtitle_batch_translate.py`](subtitle_batch_translate.py:26).

**Suggested Fix:**
- Extract to a shared module like `srt_utils.py`
- Import from the shared module in both files

### 2.2 Inconsistent Chunking Strategies

**Problem:**
- The GUI chunks 25 subtitle blocks per request ([`CHUNK = 25`](subtitle_translator_gui.py:37))
- The CLI `subtitle_batch_translate.py` sends one request per block
- This means the CLI is 25x slower and has no context awareness

**Suggested Fix:**
- Apply the same chunking strategy to the CLI
- Consider making chunk size configurable

### 2.3 No Unit Tests

**Problem:** The project lacks any test files. Critical functions like SRT parsing, response parsing, and result collection have no test coverage.

**Suggested Fix:**
- Add a `tests/` directory
- Test `parse_srt` with edge cases (empty files, malformed timestamps)
- Test `parse_response` with various response formats
- Add integration tests for batch submission

---

## 3. Error Handling & Resilience

### 3.1 No Retry Logic for Failed Batch Requests

**Problem:** When a batch request fails (shown in [`_show_errors`](subtitle_translator_gui.py:873)), it's just logged. There's no automatic retry or partial recovery.

**Suggested Fix:**
- Add a "Retry Failed" button
- Automatically retry individual failed chunks up to N times
- Allow resuming from partial results

### 3.2 Resume Function Assumes File Structure Unchanged

**Problem:** [`_resume_batches`](subtitle_translator_gui.py:773) and [`resume_batch.py`](resume_batch.py) rebuild `file_map` by scanning the input folder. If files were moved, renamed, or had blocks added, results will map incorrectly.

**Suggested Fix:**
- Include metadata in the JSONL (original filepath, block count)
- Validate that current file structure matches before resuming
- Warn user if discrepancies detected

### 3.3 Silent Failures in Settings

**Problem:** [`_load_settings`](subtitle_translator_gui.py:563) has a bare `except Exception: pass` that silently ignores all errors when loading settings.

**Suggested Fix:**
- Log or display specific errors
- Use default values for corrupted settings
- Create a backup of settings before writing

---

## 4. User Experience

### 4.1 No Log Persistence

**Problem:** Logs are only displayed in the GUI textbox. If the app crashes or is closed, the log history is lost. Debugging issues is difficult.

**Suggested Fix:**
- Add an option to save logs to a file
- Auto-rotate log files (e.g., `logs/translator_YYYYMMDD_HHMMSS.log`)
- Include log file path in error dialogs

### 4.2 No Progress for MiniMax Analysis

**Problem:** The MiniMax analysis in [`_run_hybrid`](subtitle_translator_gui.py:882) can take a long time for large files but only shows chunk progress, not per-line progress.

**Suggested Fix:**
- Show both chunk and line progress
- Add an estimated time remaining
- Allow skipping MiniMax analysis with a warning

### 4.3 No Preview of Translations

**Problem:** Users cannot preview a sample translation before committing to a full batch. This can lead to wasted API credits if the translation quality is poor.

**Suggested Fix:**
- Add a "Test Translate" button that processes first 10 blocks
- Show side-by-side comparison of original and translated
- Allow adjusting settings before full batch

---

## 5. Performance

### 5.1 Inefficient File Re-parsing

**Problem:** In [`_run_batch`](subtitle_translator_gui.py:715), [`parse_srt`](subtitle_translator_gui.py:42) is called multiple times on the same file (lines 729, 732).

**Suggested Fix:**
- Parse each file once and cache the blocks
- Reuse the cached blocks for all operations

### 5.2 Synchronous File I/O in ThreadPool

**Problem:** In [`_run_sync`](subtitle_translator_gui.py:647), results are written after all translations complete. For large projects, this delays any output.

**Suggested Fix:**
- Write results as each file completes
- Use a queue to collect completed files and write asynchronously

---

## 6. Features

### 6.1 No Support for Multiple Languages at Once

**Problem:** Users can only translate to one target language at a time. Translating to multiple languages requires running the process multiple times.

**Suggested Fix:**
- Add multi-language selection in the GUI
- Create separate output folders per target language
- Submit multiple batches in parallel

### 6.2 No Translation Memory

**Problem:** Previously translated content is not stored for reuse. Re-translating the same or similar content wastes API credits.

**Suggested Fix:**
- Store translations in a local database or cache
- Before API call, check cache for exact or similar matches
- Add a "Clear cache" option

### 6.3 No Support for Glossary in Non-Hybrid Mode

**Problem:** The glossary picker only works in hybrid mode. Sync and batch modes cannot use glossaries.

**Suggested Fix:**
- Add glossary support to the system prompt in sync/batch modes
- Allow loading glossaries in all modes

---

## 7. Configuration

### 7.1 Hardcoded Constants

**Problem:** Values like `CHUNK = 25`, `CONTEXT_LINES = 5`, `max_workers = 10` are hardcoded and cannot be adjusted without editing code.

**Suggested Fix:**
- Move to a configuration file
- Add advanced settings panel in the GUI

### 7.2 Limited Model Selection

**Problem:** The [`MODELS`](subtitle_translator_gui.py:27) list is hardcoded. New models require code changes.

**Suggested Fix:**
- Fetch available models from OpenAI API dynamically
- Allow custom model names to be entered

---

## Priority Matrix

| Improvement | Impact | Effort | Priority |
|-------------|--------|--------|----------|
| Secure API key storage | High | Medium | High |
| Duplicate SRT parsing | Medium | Low | High |
| No retry logic | High | Medium | High |
| Hardcoded external path | High | Low | High |
| No unit tests | High | High | Medium |
| Log persistence | Medium | Low | Medium |
| Translation preview | Medium | Medium | Medium |
| Multi-language support | Low | Medium | Low |
| Translation memory | Medium | High | Low |

Would you like me to create detailed implementation plans for any of these improvements?
