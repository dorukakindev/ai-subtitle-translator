# Memory/Cache/Persistence Audit Findings

## 1. Translation Memory (`translation_memory.py` - 15,091 bytes)

### SQLite Schema & WAL Mode
- **Schema**: `translations` table with columns `id`, `source_text`, `target_text`, `source_lang`, `target_lang`, `context_hash`, `quality_score`, `usage_count`, `created_at`, `updated_at`, `source_hash`, `target_hash`
- **Indexes**: `idx_source_hash`, `idx_source_lang_target_lang`, `idx_context_hash`, `idx_quality_score`
- **WAL mode enabled**: `PRAGMA journal_mode=WAL` - good for concurrent reads
- **Connection pooling**: Uses `threading.local()` with `RLock` per thread - **THREAD-SAFE** with `check_same_thread=False` + `RLock`

### Connection Pooling / Thread Safety
```python
_local = threading.local()
_lock = threading.RLock()

def _get_conn():
    if not hasattr(_local, 'conn') or _local.conn is None:
        with _lock:
            # double-checked locking pattern - but _local is thread-local so inner lock redundant
            _local.conn = sqlite3.connect(DB_PATH, check_same_thread=False)
            _local.conn.execute("PRAGMA journal_mode=WAL")
            _local.conn.execute("PRAGMA busy_timeout=5000")
    return _local.conn
```
**FINDING**: The `_lock` inside `_get_conn()` is **redundant but harmless** - `threading.local()` already isolates per-thread. However, `_lock` is also used in `_execute()` for write serialization across threads - **THIS IS CORRECT** for WAL mode write serialization.

### Fuzzy Matching Algorithm
```python
def _levenshtein_ratio(a: str, b: str) -> float:
    # Standard Levenshtein with early exit if ratio < threshold
    # O(n*m) - no optimization for long strings
    
def _token_overlap(a: str, b: str) -> float:
    # Jaccard on whitespace tokens - fast but naive
```
**FINDING**: `_levenshtein_ratio` is O(n*m) with no length cap - **potential DoS on very long subtitle lines** (e.g., malformed 10k-char lines). No length cap or early-exit threshold parameter.

### `store()` - `_is_safe_target` Guard
```python
def _is_safe_target(source: str, target: str) -> bool:
    if source.strip() == target.strip():  # Exact match guard
        return False
    if target.strip().upper() == "[HATA]":  # Error marker guard
        return False
    if len(target.strip()) < 2:  # Too short
        return False
    # Token overlap check - prevents near-duplicate storage
    if _token_overlap(source, target) > 0.9:
        return False
    return True
```
**FINDING**: 
- ✅ Guards against `[HATA]` pollution - GOOD
- ✅ Token overlap >0.9 guard prevents near-duplicate pollution - GOOD
- ⚠️ **NO TTL/TTL-BASED EVICTION** - DB grows unbounded
- ⚠️ **NO CACHE INVALIDATION** - Stale translations persist forever
- ⚠️ **NO MAX SIZE LIMIT** - Unbounded growth

### `lookup()` - Exact + Fuzzy
```python
def lookup(source: str, source_lang: str, target_lang: str, 
           context_hash: str = "", fuzzy_threshold: float = 0.85) -> Optional[str]:
    # 1. Exact match on source_hash + context_hash + langs
    # 2. Fuzzy fallback on source_text similarity + context_hash match
```
**FINDING**: Fuzzy threshold hardcoded at 0.85 - no config. Fuzzy scans full table (no index on source_text) - **O(n) scan on full table**.

### DB Corruption Handling
```python
def _get_conn():
    try:
        conn = sqlite3.connect(...)
    except sqlite3.DatabaseError:
        # Try to recover from .bak
        if os.path.exists(DB_PATH + ".bak"):
            shutil.copy2(DB_PATH + ".bak", DB_PATH)
            conn = sqlite3.connect(...)
```
**FINDING**: 
- ✅ Has `.bak` recovery attempt
- ⚠️ **No WAL corruption detection** - WAL corruption can silently corrupt data
- ⚠️ **No integrity check** (`PRAGMA integrity_check`) on startup
- ⚠️ **No vacuum schedule** - WAL files grow unbounded

### Backup Files Strategy
- `translation_memory.db` - main
- `translation_memory.db-shm` / `-wal` - WAL files (auto-managed by SQLite)
- `translation_memory.db.bak` - **Created ONLY on corruption recovery**, not periodic
- **NO PERIODIC BACKUP SCHEDULE** - only creates backup on corruption recovery attempt
- **NO VACUUM SCHEDULE** - WAL files grow unbounded

---

## 2. Series Memory (`series_memory.py` - 8,344 bytes)

### Storage Format
```json
{
  "series_name": {
    "characters": ["char1", "char2"],
    "terms": {"term1": "translation1", "term2": "translation2"},
    "context_notes": "context notes...",
    "episodes": {
      "ep1": {"characters": [...], "terms": {...}, "context": "..."},
      "ep2": {...}
    },
    "updated_at": "2024-01-01T00:00:00"
  }
}
```
**Format**: JSON file at `series_memory.json` (single file, no SQLite)

### Concurrency Safety
```python
_lock = threading.RLock()

def _load():
    with _lock:
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)

def _save(data):
    with _lock:
        atomic_write_json(path, data)  # atomic_write_json uses .tmp + replace
```
**FINDING**: 
- ✅ `RLock` + atomic write (`.tmp` + `os.replace`) - **THREAD-SAFE for single process**
- ⚠️ **NO INTER-PROCESS LOCKING** - Multiple GUI instances will corrupt JSON
- ⚠️ **NO FILE LOCKING (fcntl/flock)** - Multi-process unsafe

### Cross-Episode Contamination
```python
def get_series_context(series_name: str) -> dict:
    data = _load()
    series = data.get(series_name, {})
    # Returns MERGED characters + terms from ALL episodes
    return {
        "characters": series.get("characters", []),
        "terms": series.get("terms", {}),
        "context_notes": series.get("context_notes", "")
    }
```
**FINDING**: 
- ✅ Episode-specific data stored under `episodes[ep_name]`
- ⚠️ **`get_series_context()` MERGES all episodes** - Character names/terms from Ep 1 leak into Ep 10 context
- ⚠️ **NO EPISODE ISOLATION OPTION** - No way to get "only Ep 10 context"
- ⚠️ **NO EPISODE ORDERING** - Episodes stored as dict, no season/episode ordering

### Unbounded Growth
```python
def update_series(series_name: str, episode: str, characters: list, terms: dict, context: str):
    data = _load()
    series = data.setdefault(series_name, {"characters": [], "terms": {}, "episodes": {}})
    # Appends to characters list (no dedup beyond set conversion at read time)
    # Merges terms dict (new overwrites old)
    # Stores full episode copy under episodes[episode]
```
**FINDING**:
- ⚠️ **NO MAX EPISODES LIMIT** - Grows unbounded per series
- ⚠️ **NO TTL/EXPIRY** - Old seasons never expire
- ⚠️ **TERMS DICT GROWS UNBOUNDED** - New terms only added, never removed
- ⚠️ **CHARACTERS LIST GROWS** - Deduped at read time but stored with duplicates

---

## 3. Project Memory (`project_memory.py` - 7,946 bytes)

### Storage Format
```json
{
  "projects": {
    "project_name": {
      "glossary": {"term": "translation"},
      "style_guide": "style guide text",
      "characters": ["char1", "char2"],
      "context_notes": "notes",
      "updated_at": "2024-01-01T00:00:00"
    }
  }
}
```
**Format**: JSON file at `project_memory.json` (single file)

### Interaction with Series Memory
```python
# In subtitle_translator_gui.py:
def _get_merged_context(self, series_name: str = "", project_name: str = "") -> dict:
    ctx = {}
    if series_name:
        ctx.update(series_memory.get_series_context(series_name))
    if project_name:
        ctx.update(project_memory.get_project_context(project_name))
    # Project terms OVERRIDE series terms (project wins)
    return ctx
```
**FINDING**: 
- ✅ Project terms override series terms - intentional precedence
- ⚠️ **NO NAMESPACING** - Project "character" and Series "character" merge into same `characters` list
- ⚠️ **NO CONFLICT DETECTION** - Conflicting translations silently overwritten (project wins silently)

### Concurrency
- Same pattern as series_memory: `RLock` + atomic write
- **SAME MULTI-PROCESS UNSAFE ISSUE**

### Unbounded Growth
- Same issues as series_memory: no TTL, no max entries, no cleanup

---

## 4. Context Cache (`.context_cache/<stem>.json`)

### Location in Code
```python
# subtitle_translator_gui.py
CONTEXT_CACHE_DIR = Path(".context_cache")
CONTEXT_CACHE_DIR.mkdir(exist_ok=True)

def _get_context_cache_path(self, stem: str) -> Path:
    return CONTEXT_CACHE_DIR / f"{stem}.json"

def _save_context_cache(self, stem: str, data: dict):
    path = self._get_context_cache_path(stem)
    atomic_write_json(path, data)

def _load_context_cache(self, stem: str) -> Optional[dict]:
    path = self._get_context_cache_path(stem)
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
```

### Cache Key Derivation
```python
stem = Path(subtitle_path).stem  # e.g., "Show.S01E01.1080p"
cache_path = .context_cache / f"{stem}.json"
```
**FINDING**: 
- ⚠️ **STEM ONLY** - `Show.S01E01.1080p.srt` and `Show.S01E01.720p.srt` share cache
- ⚠️ **NO CONTENT HASH** - If subtitle file content changes but name stays same, **STALE CACHE SERVED**
- ⚠️ **NO CONTENT HASH IN CACHE** - Cache doesn't store source hash for validation

### Cache Invalidation
```python
def _load_context_cache(self, stem: str) -> Optional[dict]:
    path = self._get_context_cache_path(stem)
    if path.exists():
        data = json.loads(path.read_text(encoding="utf-8"))
        # NO VALIDATION - returns stale data blindly
        return data
    return None
```
**FINDING**: 
- ❌ **NO INVALIDATION** - No TTL, no content hash check, no mtime check
- ❌ **STALE DATA SERVED INDEFINITELY** - If subtitle file changes, stale context used

### Cache Poisoning via Malicious Subtitle Files
```python
def _analyze_file_with_ai(self, subtitle_path: Path, ...) -> dict:
    stem = subtitle_path.stem
    cached = self._load_context_cache(stem)
    if cached:
        return cached  # Returns cached analysis WITHOUT VALIDATION
    
    # ... AI analysis ...
    self._save_context_cache(stem, analysis)
```
**FINDING**:
- ❌ **CACHE POISONING POSSIBLE** - Malicious `.srt` with same stem but malicious content poisons cache for all future files with same stem
- ❌ **NO SOURCE HASH VALIDATION** - Cache doesn't store source file hash
- ❌ **NO SIZE/TIMESTAMP VALIDATION**

---

## 5. Precontext Cache (`.precontext.json`)

### Location in Code
```python
PRECONTEXT_FILE = Path(".precontext.json")

def _save_precontext(self, data: dict):
    atomic_write_json(PRECONTEXT_FILE, data)

def _load_precontext(self) -> dict:
    if PRECONTEXT_FILE.exists():
        return json.loads(PRECONTEXT_FILE.read_text(encoding="utf-8"))
    return {}
```

### Structure
```json
{
  "Show.S01E01": {
    "prev_scene_end": "Last line of previous scene",
    "prev_translations": ["prev translated line 1", "prev translated line 2"],
    "episode": 1,
    "season": 1
  }
}
```

### Cache Key
```python
key = f"{series_name}.S{season:02d}E{episode:02d}"  # Parsed from filename
```

### Cache Invalidation
```python
def _load_precontext(self) -> dict:
    if PRECONTEXT_FILE.exists():
        return json.loads(PRECONTEXT_FILE.read_text(encoding="utf-8"))
    return {}
```
**FINDING**:
- ❌ **NO INVALIDATION** - No TTL, no episode versioning
- ⚠️ **KEY FROM FILENAME PARSING** - If filename parsing fails or changes, wrong precontext used
- ⚠️ **NO SOURCE VALIDATION** - No hash of previous episode's last cues
- ⚠️ **SINGLE FILE** - All series/episodes in one JSON - grows unbounded
- ⚠️ **NO SIZE LIMIT**

### Cross-Contamination Risk
```python
def _get_prev_context(self, series_name, season, episode):
    key = f"{series_name}.S{season:02d}E{episode:02d}"
    return self._precontext.get(key, {})
```
- ⚠️ If two series have same S##E## pattern (e.g., "Show.S01E01" and "Show.S01E01.720p"), **KEY COLLISION**

---

## 6. Settings Persistence (`.gui_settings.json`)

### Atomic Write
```python
# app_state.py
def atomic_write_json(path: Path, data: dict):
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(tmp, path)  # Atomic on POSIX, near-atomic on Windows
```
**FINDING**: ✅ Atomic write pattern - GOOD

### API Key Exclusions
```python
# subtitle_translator_gui.py _save_settings()
excluded_keys = {
    "api_key", "api_key_helper", "openai_api_key", "minimax_api_key",
    "minimax_group_id", "openrouter_api_key"
}
settings_to_save = {k: v for k, v in self._settings.items() if k not in excluded_keys}
```
**FINDING**: 
- ✅ API keys excluded from JSON - GOOD
- ✅ Keys stored in OS credential store via `credential_store.py`
- ⚠️ **KEY LIST HARDCODED** - New key fields must be manually added to exclusion list

### Migration from Old Format
```python
def migrate_from_settings(old_settings: dict) -> dict:
    # Maps old keys to new keys
    mapping = {
        "api_key": "api_key",  # Now stored in credential store
        "model": "model",
        # ... mappings
    }
    new_settings = {}
    for old_key, new_key in mapping.items():
        if old_key in old_settings:
            new_settings[new_key] = old_settings[old_key]
    return new_settings
```
**FINDING**: 
- ✅ Migration logic exists
- ⚠️ **ONE-WAY MIGRATION** - Old keys removed from JSON but credential store migration is separate
- ⚠️ **NO VERSION FIELD** - No settings schema version for future migrations

### Schema Evolution
- ❌ **NO SCHEMA VERSION** - No version field in settings JSON
- ❌ **NO MIGRATION FRAMEWORK** - Ad-hoc migration only
- ❌ **NO SCHEMA VALIDATION** - Invalid keys silently ignored

### Boolean Toggle Defaults
```python
# Loading defaults
defaults = {
    "chain_context": True,      # Default ON
    "context_review": True,     # Default ON
    "critic_pass": False,       # Default OFF
    # ...
}

# Loading pattern for default-ON:
if "chain_context" in loaded:  # Key exists = user explicitly set it
    self.chain_context_var.set(loaded["chain_context"])
else:
    self.chain_context_var.set(True)  # Default ON

# Loading pattern for default-OFF:
if loaded.get("critic_pass"):
    self.critic_pass_var.set(True)
```
**FINDING**: 
- ✅ Correct pattern for default-ON (key presence check)
- ✅ Correct pattern for default-OFF (`.get()` truthiness)
- ⚠️ **FRAGILE** - If user explicitly sets default-ON to false, saves `false`, then deletes key from JSON manually, it reverts to TRUE (unexpected)

---

## 7. Batch Recovery State

### Files
- `batch_id.txt` - Single line with batch ID
- `batch_fmap_<batch_id>.json` - File mapping: `{"batch_id": {"file1.srt": "file1.ham.srt", ...}}`

### Recovery Logic (`_resume_batches`)
```python
def _resume_batches(self):
    batch_id_file = Path("batch_id.txt")
    if not batch_id_file.exists():
        return
    
    batch_id = batch_id_file.read_text().strip()
    fmap_file = Path(f"batch_fmap_{batch_id}.json")
    if not fmap_file.exists():
        return
    
    fmap = json.loads(fmap_file.read_text())
    # Resumes batch polling for this batch_id
```

### Orphaned Batch Detection
```python
# NO ORPHANED BATCH DETECTION
# batch_id.txt persists until _resume_batches succeeds
# If app crashes AFTER batch completes but BEFORE cleanup, batch_id.txt remains
# Next run: _resume_batches polls completed batch -> harmless but wasteful
```

### State Corruption Handling
```python
# NO CORRUPTION HANDLING
# If batch_fmap_<id>.json is corrupt JSON -> json.JSONDecodeError crashes _resume_batches
# If batch_id.txt contains garbage -> requests.get fails silently -> silent failure
```
**FINDING**:
- ❌ **NO JSON PARSE ERROR HANDLING** in `_resume_batches`
- ❌ **NO ORPHAN CLEANUP** - Stale batch_id.txt persists
- ❌ **NO BATCH STATE VALIDATION** - Doesn't verify batch still exists on OpenAI side before resuming
- ⚠️ **SINGLE BATCH ID** - Only tracks one batch at a time (overwrites batch_id.txt)

---

## 8. Sync Checkpoint (`.sync_checkpoint.jsonl`)

### Format
```jsonl
{"index": 0, "status": "done", "translation": "translated line", "ham_path": "file.ham.srt"}
{"index": 1, "status": "done", "translation": "translated line 2", "ham_path": "file.ham.srt"}
{"index": 2, "status": "pending"}
```

### Recovery Logic (`_run_sync`)
```python
def _run_sync(self):
    checkpoint_file = Path(".sync_checkpoint.jsonl")
    completed = set()
    if checkpoint_file.exists():
        for line in checkpoint_file.read_text().splitlines():
            try:
                rec = json.loads(line)
                if rec.get("status") == "done":
                    completed.add(rec["index"])
            except json.JSONDecodeError:
                pass  # Silently skip corrupt lines
    
    # Resume from first non-completed index
    for i, chunk in enumerate(chunks):
        if i in completed:
            continue
        # ... process chunk ...
        # Append to checkpoint after each chunk
        with open(checkpoint_file, "a", encoding="utf-8") as f:
            f.write(json.dumps({"index": i, "status": "done", ...}) + "\n")
```

### Concurrent Write Safety
```python
# NO FILE LOCKING
# Multiple processes writing to .sync_checkpoint.jsonl = CORRUPTION
# Single process: append is atomic on POSIX for small writes, NOT on Windows
```
**FINDING**:
- ⚠️ **NO FILE LOCKING** - Multi-process unsafe
- ⚠️ **WINDOWS APPEND NOT ATOMIC** - `open(..., "a")` + `write()` can interleave on Windows
- ✅ **CORRUPT LINE SKIP** - JSON decode errors skipped silently (resilient)
- ❌ **NO CHECKPOINT COMPACTION** - File grows unbounded (one line per chunk)
- ❌ **NO CHECKPOINT VALIDATION** - Doesn't verify `.ham.srt` files still exist/match

---

## 9. Log Rotation (`logs/*.log`)

### Rotation Logic
```python
def rotate_logs(log_dir: Path = Path("logs"), keep: int = 30):
    logs = sorted(log_dir.glob("*.log"), key=lambda p: p.stat().st_mtime, reverse=True)
    for old_log in logs[keep:]:
        try:
            old_log.unlink()
        except PermissionError:
            pass  # Skip locked files
```

### PID Protection (`test_log_rotation_pid_protection.py`)
```python
def rotate_logs_with_pid_protection(log_dir: Path, keep: int = 30):
    current_pid = os.getpid()
    logs = sorted(log_dir.glob("*.log"), key=lambda p: p.stat().st_mtime, reverse=True)
    for old_log in logs[keep:]:
        try:
            # Check if another process has it open (Windows)
            with open(old_log, 'a'):
                pass  # If we can open, no other process has it locked exclusively
            old_log.unlink()
        except (PermissionError, OSError):
            pass
```
**FINDING**:
- ✅ **PID PROTECTION EXISTS** - Test file shows PID protection logic
- ⚠️ **BUT NOT USED IN MAIN CODE** - `rotate_logs()` in `app_state.py` doesn't use PID check
- ⚠️ **WINDOWS FILE LOCKING** - `PermissionError` catch handles it but silently skips
- ⚠️ **NO MAX LOG SIZE** - Single log file can grow unbounded during single run
- ⚠️ **NO LOG COMPRESSION** - Old logs deleted, not compressed

---

## 10. Credential Store (`credential_store.py`)

### Keyring → File Fallback
```python
def get_credential(service: str, username: str) -> Optional[str]:
    try:
        return keyring.get_password(service, username)
    except Exception:
        pass
    # Fallback to file
    path = _get_credential_file(service, username)
    if path.exists():
        return _decrypt(path.read_bytes())
    return None

def set_credential(service: str, username: str, password: str):
    try:
        keyring.set_password(service, username, password)
        return
    except Exception:
        pass
    # Fallback: encrypt + atomic write
    path = _get_credential_file(service, username)
    tmp = path.with_suffix(".tmp")
    tmp.write_bytes(_encrypt(password))
    os.replace(tmp, path)
```

### Encryption
```python
def _encrypt(data: str) -> bytes:
    key = _get_or_create_key()
    f = Fernet(key)
    return f.encrypt(data.encode())

def _get_or_create_key() -> bytes:
    key_file = Path("credential.key")
    if key_file.exists():
        return key_file.read_bytes()
    key = Fernet.generate_key()
    key_file.write_bytes(key)
    return key
```
**FINDING**:
- ✅ **Fernet encryption** - GOOD
- ✅ **Atomic write** (`.tmp` + `os.replace`) - GOOD
- ⚠️ **KEY FILE UNPROTECTED** - `credential.key` stored in plaintext in repo folder
- ⚠️ **NO KEY ROTATION** - Key never rotated
- ⚠️ **KEYRING EXCEPTIONS SWALLOWED** - Falls back silently, user unaware keyring failed

---

## SUMMARY: CRITICAL FINDINGS

### 🔴 CRITICAL (Data Corruption / Security)
1. **Context Cache Poisoning** - No content hash validation, malicious subtitle with same stem poisons cache
2. **Precontext Cache Poisoning** - Same stem collision, no validation
3. **Series/Project Memory Multi-Process Corruption** - No file locking, JSON corruption on multi-process
4. **Sync Checkpoint Windows Corruption** - Non-atomic append on Windows
5. **Credential Key in Plaintext** - `credential.key` stored unprotected

### 🟠 HIGH (Data Loss / Stale Data)
6. **Context Cache No Invalidation** - Stale cache served indefinitely
3. **Precontext Cache No Invalidation** - Stale precontext served indefinitely
8. **Translation Memory No Invalidation/TTL** - Stale translations served forever
9. **Translation Memory Unbounded Growth** - No vacuum, no size limit, no TTL
10. **Series/Project Memory Unbounded Growth** - No TTL, no max entries
11. **Sync Checkpoint Unbounded Growth** - JSONL grows forever, no compaction
12. **Log Files Unbounded During Run** - No size-based rotation during single run

### 🟡 MEDIUM (Reliability / Correctness)
13. **Batch Recovery No Corruption Handling** - JSON decode error crashes resume
14. **Batch Recovery No Orphan Cleanup** - Stale batch_id.txt persists
15. **Translation Memory Fuzzy O(n) Scan** - No index on source_text for fuzzy
16. **Levenshtein O(n*m) No Length Cap** - DoS potential on long lines
17. **Settings No Schema Version** - Future migrations will be ad-hoc
18. **Credential Keyring Failure Silent** - User unaware keyring failed
19. **Log Rotation PID Protection Not Used in Main Code** - Test has it, main doesn't

### 🟢 LOW (Maintainability)
20. **Translation Memory Redundant Lock** - Thread-local makes inner lock redundant
21. **Series/Project Memory Key Collision Risk** - Filename parsing for keys
22. **Settings Boolean Default Pattern Fragile** - Manual JSON edit breaks defaults
23. **Credential Key No Rotation** - Long-term key exposure