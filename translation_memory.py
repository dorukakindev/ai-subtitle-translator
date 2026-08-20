"""
Translation Memory — SQLite tabanlı çeviri önbelleği.
Aynı kaynak metni tekrar API'ye göndermez, token tasarrufu sağlar.
Fuzzy eşleştirme: %85+ benzerlik için SequenceMatcher kullanır.
"""
import sqlite3
import hashlib
import re
import sys
import threading
import time
from difflib import SequenceMatcher
from pathlib import Path

FUZZY_THRESHOLD = 0.85  # minimum benzerlik oranı
_TM_GUARD_AVAILABLE = True
_TM_GUARD_WARNING_EMITTED = False
_TM_GUARD_LOCK = threading.Lock()

_SEMANTIC_TOKEN_RE = re.compile(r"[^\W_]+(?:['’][^\W_]+)?", re.UNICODE)
_NEGATION_TOKENS = frozenset({
    "not", "no", "never", "neither", "nor", "without",
    "isn't", "aren't", "wasn't", "weren't", "don't", "doesn't", "didn't",
    "won't", "wouldn't", "can't", "cannot", "couldn't", "shouldn't",
    "mustn't", "hasn't", "haven't", "hadn't",
})
_MODAL_TOKENS = frozenset({
    "can", "could", "may", "might", "must", "shall", "should", "will", "would",
})
_PRONOUN_TOKENS = frozenset({
    "i", "you", "he", "she", "it", "we", "they",
    "me", "him", "her", "us", "them", "my", "your", "his", "its", "our",
    "their", "mine", "yours", "hers", "ours", "theirs",
})
_NUMBER_WORDS = frozenset({
    "zero", "one", "two", "three", "four", "five", "six", "seven", "eight",
    "nine", "ten", "eleven", "twelve", "thirteen", "fourteen", "fifteen",
    "sixteen", "seventeen", "eighteen", "nineteen", "twenty", "thirty",
    "forty", "fifty", "sixty", "seventy", "eighty", "ninety", "hundred",
    "thousand", "million", "billion",
})


def _fuzzy_semantic_anchors(text: str) -> tuple:
    raw_tokens = _SEMANTIC_TOKEN_RE.findall(str(text or ""))
    tokens = [token.replace("’", "'").casefold() for token in raw_tokens]
    digits = tuple(re.findall(r"(?<!\w)[+-]?\d+(?:[.,:/-]\d+)*(?!\w)", str(text or "")))
    proper = tuple(
        token.casefold() for token in raw_tokens
        if token[:1].isupper() and token.casefold() != "i"
    )
    return (
        frozenset(token for token in tokens if token in _NEGATION_TOKENS),
        frozenset(token for token in tokens if token in _MODAL_TOKENS),
        frozenset(token for token in tokens if token in _PRONOUN_TOKENS),
        tuple(token for token in tokens if token in _NUMBER_WORDS),
        digits,
        proper,
    )


def _normalized_semantic_tokens(text: str) -> tuple:
    """Kesme işaretini (düz, eğik ve mojibake) tek biçime indirger."""
    return tuple(
        token.replace("â€™", "'").replace("’", "'").casefold()
        for token in _SEMANTIC_TOKEN_RE.findall(str(text or ""))
    )


def _fuzzy_semantically_compatible(source: str, candidate: str) -> bool:
    """Bulanık TM adayı kaynakla aynı şeyi mi söylüyor?

    Jeton dizisinin BİREBİR aynı olması KASITLIDIR: tek bir içerik kelimesi
    farklıysa ('gear' → 'bear') benzerlik oranı %95'i geçse bile çeviri yanlış
    olur ve çapa karşılaştırması bunu yakalayamaz. Gevşetme denemesi
    `test_fuzzy_rejects_content_tense_and_person_drift` ile geri döner.
    Yalnız kesme işareti biçimi (düz/eğik/mojibake) normalize edilir."""
    source_tokens = _normalized_semantic_tokens(source)
    candidate_tokens = _normalized_semantic_tokens(candidate)
    return bool(source_tokens) and source_tokens == candidate_tokens


def _context_key(context_fingerprint: str = "") -> str:
    raw = str(context_fingerprint or "").strip()
    if not raw:
        return ""
    return hashlib.sha256(raw.encode("utf-8", "replace")).hexdigest()[:24]


def _is_missing_translation(target: str) -> bool:
    text = str(target or "").strip()
    return text.startswith("[HATA") or text == "[ÇEVİRİ EKSİK]"


_TURKISH_TARGET_KEYS = frozenset({"tr", "tur", "turkish", "türkçe", "turkce"})


def _is_turkish_target(tgt_lang: str) -> bool:
    return str(tgt_lang or "tr").strip().casefold() in _TURKISH_TARGET_KEYS


def _is_safe_target(target: str, source_text: str = "", tgt_lang: str = "tr") -> bool:
    """Hedef metin sızıntı/bozuk-token içeriyorsa False — TM'ye KAYDETME (bkz.
    plans/future-quality-guards-brief.md Görev 2: geçmişte DB'ye giren hatalı bir
    çeviri, fuzzy/exact eşleşmeyle GELECEK bölümlere geri taşınır — guard'ları
    by-pass eden tek yol). hybrid_translate döngüsel import riskine karşı
    fonksiyon-içi lazy-import edilir. Guard çalışmazsa yalnız TM kaydı kapatılır;
    lookup ve altyazı yazımı devam eder.

    Türkçeye özgü denetimler yalnız Türkçe hedefte çalışır: Almanca/Fransızca
    çeviriler `has_non_turkish_target_leak` için tanım gereği "sızıntı"dır ve o
    dillerde TM'ye tek bir satır bile yazılamıyordu."""
    global _TM_GUARD_AVAILABLE, _TM_GUARD_WARNING_EMITTED
    if not _TM_GUARD_AVAILABLE:
        return False
    turkish_target = _is_turkish_target(tgt_lang)
    try:
        import hybrid_translate as ht
        if turkish_target and ht.has_non_turkish_target_leak(
                target, source_text=source_text):
            return False
        if ht.find_garble_tokens(target, source_text=source_text):
            return False
        if turkish_target and ht.find_translatable_english_residue(source_text, target):
            return False
    except Exception as exc:
        with _TM_GUARD_LOCK:
            _TM_GUARD_AVAILABLE = False
            if not _TM_GUARD_WARNING_EMITTED:
                print(
                    f"[TM] Güvenlik kontrolü çalışmadı; bu oturumda TM kaydı kapatıldı: {exc}",
                    file=sys.stderr,
                )
                _TM_GUARD_WARNING_EMITTED = True
        return False
    return True


class TranslationMemory:
    def __init__(self, db_path=None):
        if db_path is None:
            db_path = Path(__file__).parent / "translation_memory.db"
        self.db_path = Path(db_path)
        self._conn: sqlite3.Connection | None = None
        # Tek bağlantı çok thread'den paylaşılıyor (check_same_thread=False); yazımları
        # serileştir (eşzamanlı INSERT/commit aynı bağlantıda bozulmaya yol açabilir).
        self._lock = threading.RLock()
        self._closed = False
        self._unavailable = False
        self._init_db()

    # ── Bağlantı ──────────────────────────────────────────────────────────────

    def _get_conn(self) -> sqlite3.Connection | None:
        with self._lock:
            if self._closed:
                raise RuntimeError("TranslationMemory is closed")
            if self._unavailable:
                return None
            if self._conn is None:
                conn = sqlite3.connect(str(self.db_path), check_same_thread=False, timeout=30)
                try:
                    conn.execute("PRAGMA journal_mode=WAL")
                    self._ensure_schema(conn)
                except Exception:
                    conn.close()
                    raise
                self._conn = conn
            return self._conn

    def _init_db(self):
        try:
            self._get_conn()
        except sqlite3.DatabaseError as e:
            if (isinstance(e, sqlite3.OperationalError)
                    and ("locked" in str(e).lower() or "unable" in str(e).lower())):
                self._conn = None
                print(
                    f"[TM] DB geçici olarak kullanılamıyor; sonraki işlemde tekrar denenecek: {e}",
                    file=sys.stderr,
                )
                return
            self._unavailable = True
            print(
                f"[TM] DB bozuk; bu oturumda TM arama ve kayıt kapatıldı: {e}",
                file=sys.stderr,
            )

    def _ensure_schema(self, conn):
        conn.execute("""
            CREATE TABLE IF NOT EXISTS tm (
                hash    TEXT PRIMARY KEY,
                source  TEXT NOT NULL,
                target  TEXT NOT NULL,
                model   TEXT DEFAULT '',
                ts      REAL DEFAULT 0,
                tgt_lang TEXT DEFAULT '',
                profanity TEXT DEFAULT '',
                schema_name TEXT DEFAULT '',
                src_lang TEXT DEFAULT '',
                context_key TEXT DEFAULT ''
            )
        """)
        # Migrasyon: eski DB'lerde ek kolonlar yoksa ekle
        cursor = conn.execute("PRAGMA table_info(tm)")
        columns = {row[1] for row in cursor.fetchall()}
        required_columns = {"schema_name": " TEXT DEFAULT ''", "profanity": " TEXT DEFAULT ''",
                            "tgt_lang": " TEXT DEFAULT ''", "src_lang": " TEXT DEFAULT ''",
                            "context_key": " TEXT DEFAULT ''"}
        for col_name, col_def in required_columns.items():
            if col_name not in columns:
                conn.execute(f"ALTER TABLE tm ADD COLUMN {col_name}{col_def}")
        columns = {row[1] for row in conn.execute("PRAGMA table_info(tm)").fetchall()}
        missing_columns = set(required_columns) - columns
        if missing_columns:
            raise sqlite3.OperationalError(
                f"TM schema migration failed; missing columns: {', '.join(sorted(missing_columns))}"
            )
        conn.execute("CREATE INDEX IF NOT EXISTS idx_tgt_lang_len ON tm(tgt_lang, LENGTH(source))")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_tm_langs_len ON tm(tgt_lang, src_lang, LENGTH(source))")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_tm_context_len ON tm(tgt_lang, src_lang, context_key, LENGTH(source))")
        conn.commit()

    # ── Hash ──────────────────────────────────────────────────────────────────

    @staticmethod
    def _settings_fingerprint(model: str = "", profanity: str = "", schema_name: str = "",
                              source_language: str = "", context_fingerprint: str = "") -> str:
        """Ayarların özetini döndürür — farklı model/profanity/schema_name/kaynak dil farklı TM girişi demektir."""
        parts = []
        model_short = (model or "").strip().lower().replace(" ", "-")
        if model_short:
            parts.append(f"m:{model_short}")
        prof = (profanity or "").strip().lower()
        if prof:
            parts.append(f"p:{prof}")
        sch = (schema_name or "").strip().lower()
        if sch:
            parts.append(f"s:{sch}")
        src = (source_language or "").strip().lower()
        if src:
            parts.append(f"l:{src}")
        context_key = _context_key(context_fingerprint)
        if context_key:
            parts.append(f"c:{context_key}")
        return "|".join(parts)

    @staticmethod
    def _hash(text: str, tgt_lang: str = "", fingerprint: str = "") -> str:
        """Kaynak metni + hedef dili + ayar parmak izini normalize edip MD5 hash döner.
        tgt_lang dahil edildiğinde EN→TR ve EN→DE ayrı kaydedilir."""
        normalized = " ".join(text.strip().lower().split())
        if tgt_lang:
            normalized = f"{tgt_lang.strip().lower()}:{normalized}"
        if fingerprint:
            normalized = f"{fingerprint}:{normalized}"
        return hashlib.md5(normalized.encode("utf-8")).hexdigest()

    # ── Arama ─────────────────────────────────────────────────────────────────

    def lookup(self, source: str, tgt_lang: str = "", model: str = "", profanity: str = "",
               schema_name: str = "", source_language: str = "",
               context_fingerprint: str = "") -> str | None:
        """Kaynak metni TM'de ara. Bulursa hedef metni döner, yoksa None.
        model ve profanity aynı ayarlarla kaydedilmiş girişleri bulmak için kullanılır."""
        if not source or not source.strip():
            return None
        fingerprint = self._settings_fingerprint(
            model, profanity, schema_name, source_language, context_fingerprint)
        h = self._hash(source, tgt_lang, fingerprint)
        try:
            with self._lock:
                conn = self._get_conn()
                if conn is None:
                    return None
                row = conn.execute(
                    "SELECT target FROM tm WHERE hash=?", (h,)
                ).fetchone()
        except Exception:
            return None
        # Fallback: settings-aware olmayan eski girişleri dene (yalnızca schema_name BOŞ ise)
        if (row is None and fingerprint and not schema_name and not source_language
                and not context_fingerprint):
            try:
                old_h = self._hash(source, tgt_lang, "")
                with self._lock:
                    conn = self._get_conn()
                    if conn is None:
                        return None
                    row = conn.execute(
                        "SELECT target FROM tm WHERE hash=?", (old_h,)
                    ).fetchone()
            except Exception:
                return None
        try:
            return row[0] if row else None
        except Exception:
            return None

    def lookup_batch(self, sources: list, tgt_lang: str = "", model: str = "", profanity: str = "",
                     schema_name: str = "", source_language: str = "",
                     context_fingerprint: str = "",
                     allow_contextless_final: bool = True) -> dict:
        """Birden çok kaynak metni TEK sorguda arar.

        Bu API nihai altyazı satırını doğrudan ikame eder. Sen/siz, sözlük ve
        proje/dizi kararları bilinmiyorsa eski bir TM kaydını final sonuç yapmak
        güvenli değildir; çağıran taraf bir bağlam imzası vermelidir.
        ``allow_contextless_final`` yalnız açıkça seçilmiş eski araçlar içindir.
        """
        if not context_fingerprint and not allow_contextless_final:
            return {}
        fingerprint = self._settings_fingerprint(
            model, profanity, schema_name, source_language, context_fingerprint)
        # `_hash` metni küçük harfe indirger: "Thank you." ve "THANK YOU." aynı
        # hash'e düşer. Tek değer tutulursa ilk varyasyon eziliyor ve TM'de olduğu
        # hâlde bulunamamış sayılıp API'ye gönderiliyordu — her varyasyonu sakla.
        uniq: dict[str, list] = {}
        for s in sources:
            if s and s.strip():
                uniq.setdefault(self._hash(s, tgt_lang, fingerprint), []).append(s)
        if not uniq:
            return {}
        result = {}
        hashes = list(uniq.keys())
        # SQLite değişken limiti (~999) — parça parça sorgula
        try:
            with self._lock:
                conn = self._get_conn()
                if conn is None:
                    return {}
                for i in range(0, len(hashes), 900):
                    batch = hashes[i:i + 900]
                    ph = ",".join("?" * len(batch))
                    for h, target in conn.execute(
                            f"SELECT hash, target FROM tm WHERE hash IN ({ph})", batch):
                        for src in uniq.get(h, ()):
                            result[src] = target
        except Exception:
            return {}
        # Fallback: YALNIZCA schema_name BOŞ ise ve henüz bulunamamış kaynaklar varsa eski şemasız girişleri dene
        missing_sources = [s for s in sources if s and s.strip() and s not in result]
        if (missing_sources and fingerprint and not schema_name and not source_language
                and not context_fingerprint):
            try:
                with self._lock:
                    conn = self._get_conn()
                    if conn is None:
                        return result
                    uniq2: dict[str, list] = {}
                    for s in missing_sources:
                        uniq2.setdefault(self._hash(s, tgt_lang, ""), []).append(s)
                    hashes2 = list(uniq2.keys())
                    for i in range(0, len(hashes2), 900):
                        batch = hashes2[i:i + 900]
                        ph = ",".join("?" * len(batch))
                        for h, target in conn.execute(
                                f"SELECT hash, target FROM tm WHERE hash IN ({ph})", batch):
                            for src in uniq2.get(h, ()):
                                result[src] = target
            except Exception:
                return result
        return result

    def fuzzy_lookup(self, source: str, threshold: float = FUZZY_THRESHOLD,
                      tgt_lang: str = "", model: str = "", profanity: str = "",
                      schema_name: str = "", source_language: str = "",
                      context_fingerprint: str = "",
                      allow_contextless_final: bool = True) -> tuple[str, float] | None:
        """Fuzzy eşleştirme: %threshold+ benzerlik varsa (çeviri, oran) döner.
        Tam eşleşme varsa önce onu döner. Yoksa kısa adaylara (±40% uzunluk) bakar.
        Pahalı DB taramasını kısaltmak için uzunluk filtrelemesi yapar.
        """
        if not source or not source.strip():
            return None
        if not context_fingerprint and not allow_contextless_final:
            return None
        # Önce tam eşleşme dene (hızlı yol)
        exact = self.lookup(
            source, tgt_lang=tgt_lang, model=model, profanity=profanity,
            schema_name=schema_name, source_language=source_language,
            context_fingerprint=context_fingerprint)
        if exact is not None:
            return (exact, 1.0)

        src_norm = " ".join(source.strip().lower().split())
        src_len  = len(src_norm)
        if src_len < 6:
            return None  # çok kısa metinlerde fuzzy anlamsız

        # DB'den uzunluk filtreli ve hedef dile/şemaya göre adaylar çek (±40% uzunluk)
        lo = int(src_len * 0.6)
        hi = int(src_len * 1.4)
        lang = tgt_lang.strip().lower()
        sch = schema_name.strip().lower() if schema_name else ""
        src_lang = source_language.strip().lower() if source_language else ""
        ctx_key = _context_key(context_fingerprint)
        clauses = ["LENGTH(source) BETWEEN ? AND ?", "schema_name = ?", "src_lang = ?", "context_key = ?"]
        params = [lo, hi, sch, src_lang, ctx_key]
        if lang:
            clauses.append("tgt_lang = ?")
            params.append(lang)
        if model:
            clauses.append("LOWER(model) = ?")
            params.append(model.strip().casefold())
        if profanity:
            clauses.append("profanity = ?")
            params.append(profanity.strip().lower())
        sql = ("SELECT source, target FROM tm WHERE "
               + " AND ".join(clauses) + " LIMIT 500")
        try:
            with self._lock:
                conn = self._get_conn()
                if conn is None:
                    return None
                rows = conn.execute(sql, params).fetchall()
        except Exception:
            return None

        best_target = None
        best_ratio  = 0.0
        matcher = SequenceMatcher(isjunk=None, autojunk=False)
        matcher.set_seq2(src_norm)
        for db_src, db_tgt in rows:
            candidate_norm = " ".join(db_src.strip().lower().split())
            if not _fuzzy_semantically_compatible(source, db_src):
                continue
            matcher.set_seq1(candidate_norm)
            ratio = matcher.ratio()
            if ratio > best_ratio:
                best_ratio  = ratio
                best_target = db_tgt

        if best_ratio >= threshold and best_target is not None:
            return (best_target, best_ratio)
        return None

    # ── Kaydetme ──────────────────────────────────────────────────────────────

    def store(self, source: str, target: str, model: str = "", tgt_lang: str = "",
              profanity: str = "", schema_name: str = "", source_language: str = "",
              context_fingerprint: str = "") -> bool:
        """Yeni bir çeviri çiftini TM'ye kaydet. Hata varsa False döner."""
        if not source or not target:
            return False
        _t = target.strip()
        _s = source.strip()
        if _is_missing_translation(_t):
            return False
        if _s.lower() == _t.lower():
            return False
        if not _is_safe_target(_t, _s, tgt_lang):
            return False
        fingerprint = self._settings_fingerprint(
            model, profanity, schema_name, source_language, context_fingerprint)
        h = self._hash(source, tgt_lang, fingerprint)
        try:
            with self._lock:
                conn = self._get_conn()
                conn.execute(
                    "INSERT OR REPLACE INTO tm(hash,source,target,model,ts,tgt_lang,profanity,schema_name,src_lang,context_key) "
                    "VALUES(?,?,?,?,?,?,?,?,?,?)",
                    (h, source.strip(), target.strip(), model, time.time(),
                      tgt_lang.strip().lower(), profanity.strip().lower() if profanity else "",
                      schema_name.strip().lower() if schema_name else "",
                       source_language.strip().lower() if source_language else "",
                      _context_key(context_fingerprint)),
                )
                conn.commit()
            return True
        except Exception:
            return False

    def store_batch(self, pairs: list[tuple[str, str]], model: str = "", tgt_lang: str = "",
                    profanity: str = "", schema_name: str = "", source_language: str = "",
                    context_fingerprint: str = ""):
        """Toplu kaydetme. pairs = [(source, target), ...]"""
        if not pairs:
            return True
        fingerprint = self._settings_fingerprint(
            model, profanity, schema_name, source_language, context_fingerprint)
        rows = []
        for source, target in pairs:
            if not source or not target or _is_missing_translation(target):
                continue
            if source.strip().lower() == target.strip().lower():
                continue
            if not _is_safe_target(target.strip(), source.strip(), tgt_lang):
                continue
            rows.append((
                self._hash(source, tgt_lang, fingerprint),
                source.strip(),
                target.strip(),
                model,
                time.time(),
                tgt_lang.strip().lower(),
                profanity.strip().lower() if profanity else "",
                schema_name.strip().lower() if schema_name else "",
                source_language.strip().lower() if source_language else "",
                _context_key(context_fingerprint),
            ))
        if not rows:
            return True
        try:
            with self._lock:
                conn = self._get_conn()
                conn.executemany(
                    "INSERT OR REPLACE INTO tm(hash,source,target,model,ts,tgt_lang,profanity,schema_name,src_lang,context_key) "
                    "VALUES(?,?,?,?,?,?,?,?,?,?)",
                    rows,
                )
                conn.commit()
            return True
        except Exception:
            return False

    # ── İstatistikler ─────────────────────────────────────────────────────────

    def stats(self) -> dict:
        try:
            with self._lock:
                conn = self._get_conn()
                row = conn.execute("SELECT COUNT(*) FROM tm").fetchone() if conn else None
            return {"total": row[0] if row else 0}
        except Exception:
            return {"total": 0}

    def hit_count_session(self) -> int:
        """Bu oturumda kaç kez TM'den çeviri alındığını döner (bellekte tutar)."""
        return getattr(self, '_session_hits', 0)

    def record_hit(self):
        """TM'den bir çeviri kullanıldığında çağrılır."""
        with self._lock:
            self._session_hits = getattr(self, '_session_hits', 0) + 1

    def reset_session_hits(self):
        self._session_hits = 0

    # ── Temizlik ──────────────────────────────────────────────────────────────

    def close(self):
        with self._lock:
            self._closed = True
            if self._conn:
                try:
                    self._conn.execute("PRAGMA optimize")
                    self._conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
                except sqlite3.Error:
                    pass
                self._conn.close()
                self._conn = None

    def __del__(self):
        try:
            self.close()
        except Exception:
            pass
