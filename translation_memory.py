"""
Translation Memory — SQLite tabanlı çeviri önbelleği.
Aynı kaynak metni tekrar API'ye göndermez, token tasarrufu sağlar.
Fuzzy eşleştirme: %85+ benzerlik için SequenceMatcher kullanır.
"""
import sqlite3
import hashlib
import threading
import time
from difflib import SequenceMatcher
from pathlib import Path

FUZZY_THRESHOLD = 0.85  # minimum benzerlik oranı


def _is_missing_translation(target: str) -> bool:
    text = str(target or "").strip()
    return text.startswith("[HATA") or text == "[ÇEVİRİ EKSİK]"


def _is_safe_target(target: str) -> bool:
    """Hedef metin sızıntı/bozuk-token içeriyorsa False — TM'ye KAYDETME (bkz.
    plans/future-quality-guards-brief.md Görev 2: geçmişte DB'ye giren hatalı bir
    çeviri, fuzzy/exact eşleşmeyle GELECEK bölümlere geri taşınır — guard'ları
    by-pass eden tek yol). hybrid_translate döngüsel import riskine karşı
    fonksiyon-içi lazy-import edilir; import/çalışma hatasında fail-open (True) —
    TM kaydı kritik yol değil, bu gate'in kendisi asla dosya yazımını engellememeli."""
    try:
        import hybrid_translate as ht
        if ht.has_non_turkish_target_leak(target):
            return False
        if ht.find_garble_tokens(target):
            return False
    except Exception:
        return True
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
        self._init_db()

    # ── Bağlantı ──────────────────────────────────────────────────────────────

    def _get_conn(self) -> sqlite3.Connection:
        if self._conn is None:
            self._conn = sqlite3.connect(str(self.db_path), check_same_thread=False, timeout=30)
            self._conn.execute("PRAGMA journal_mode=WAL")
        return self._conn

    def _init_db(self):
        try:
            conn = self._get_conn()
        except sqlite3.OperationalError as e:
            if "locked" in str(e).lower() or "unable" in str(e).lower():
                self._conn = None
                import sys
                print(f"[TM] DB kilitli, çeviri belleği devre dışı: {e}", file=sys.stderr)
                return
            raise
        conn.execute("""
            CREATE TABLE IF NOT EXISTS tm (
                hash    TEXT PRIMARY KEY,
                source  TEXT NOT NULL,
                target  TEXT NOT NULL,
                model   TEXT DEFAULT '',
                ts      REAL DEFAULT 0,
                tgt_lang TEXT DEFAULT '',
                profanity TEXT DEFAULT '',
                schema_name TEXT DEFAULT ''
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_tgt_lang_len ON tm(tgt_lang, LENGTH(source))")
        
        # Migrasyon: eski DB'lerde ek kolonlar yoksa ekle
        cursor = conn.execute("PRAGMA table_info(tm)")
        columns = {row[1] for row in cursor.fetchall()}
        for col_name, col_def in {"schema_name": " TEXT DEFAULT ''", "profanity": " TEXT DEFAULT ''",
                                    "tgt_lang": " TEXT DEFAULT ''"}.items():
            if col_name not in columns:
                try:
                    conn.execute(f"ALTER TABLE tm ADD COLUMN {col_name}{col_def}")
                    conn.commit()
                except Exception:
                    pass

    # ── Hash ──────────────────────────────────────────────────────────────────

    @staticmethod
    def _settings_fingerprint(model: str = "", profanity: str = "") -> str:
        """Ayarların özetini döndürür — farklı model/profanity farklı TM girişi demektir."""
        parts = []
        model_short = (model or "").strip().lower().replace(" ", "-")[:40]
        if model_short:
            parts.append(f"m:{model_short}")
        prof = (profanity or "").strip().lower()[:20]
        if prof:
            parts.append(f"p:{prof}")
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

    def lookup(self, source: str, tgt_lang: str = "", model: str = "", profanity: str = "") -> str | None:
        """Kaynak metni TM'de ara. Bulursa hedef metni döner, yoksa None.
        model ve profanity aynı ayarlarla kaydedilmiş girişleri bulmak için kullanılır."""
        if not source or not source.strip():
            return None
        fingerprint = self._settings_fingerprint(model, profanity)
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
        # Fallback: settings-aware olmayan eski girişleri dene (sadece ayar verilmişse)
        if row is None and fingerprint:
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

    def lookup_batch(self, sources: list, tgt_lang: str = "", model: str = "", profanity: str = "") -> dict:
        """Birden çok kaynak metni TEK sorguda arar. {source: target} döner
        (yalnızca bulunanlar). Satır-satır lookup'a göre büyük dosyalarda hızlı."""
        fingerprint = self._settings_fingerprint(model, profanity)
        uniq = {}
        for s in sources:
            if s and s.strip():
                uniq[self._hash(s, tgt_lang, fingerprint)] = s
        if not uniq:
            return {}
        result = {}
        hashes = list(uniq.keys())
        # SQLite değişken limiti (~999) — parça parça sorgula
        with self._lock:
            conn = self._get_conn()
            for i in range(0, len(hashes), 900):
                batch = hashes[i:i + 900]
                ph = ",".join("?" * len(batch))
                for h, target in conn.execute(
                        f"SELECT hash, target FROM tm WHERE hash IN ({ph})", batch):
                    src = uniq.get(h)
                    if src is not None:
                        result[src] = target
        # Fallback: settings-aware olmayan eski girişler için
        if not result and fingerprint:
            uniq2 = {}
            for s in sources:
                if s and s.strip():
                    uniq2[self._hash(s, tgt_lang, "")] = s
            hashes2 = list(uniq2.keys())
            for i in range(0, len(hashes2), 900):
                batch = hashes2[i:i + 900]
                ph = ",".join("?" * len(batch))
                for h, target in conn.execute(
                        f"SELECT hash, target FROM tm WHERE hash IN ({ph})", batch):
                    src = uniq2.get(h)
                    if src is not None:
                        result[src] = target
        return result

    def fuzzy_lookup(self, source: str, threshold: float = FUZZY_THRESHOLD,
                     tgt_lang: str = "", model: str = "", profanity: str = "") -> tuple[str, float] | None:
        """Fuzzy eşleştirme: %threshold+ benzerlik varsa (çeviri, oran) döner.
        Tam eşleşme varsa önce onu döner. Yoksa kısa adaylara (±40% uzunluk) bakar.
        Pahalı DB taramasını kısaltmak için uzunluk filtrelemesi yapar.
        """
        if not source or not source.strip():
            return None
        # Önce tam eşleşme dene (hızlı yol)
        exact = self.lookup(source, tgt_lang=tgt_lang, model=model, profanity=profanity)
        if exact is not None:
            return (exact, 1.0)

        src_norm = " ".join(source.strip().lower().split())
        src_len  = len(src_norm)
        if src_len < 6:
            return None  # çok kısa metinlerde fuzzy anlamsız

        # DB'den uzunluk filtreli ve hedef dile göre adaylar çek (±40% uzunluk)
        lo = int(src_len * 0.6)
        hi = int(src_len * 1.4)
        lang = tgt_lang.strip().lower()
        # Hedef dil belirtilmişse YALNIZCA o dile bak — eskiden `OR tgt_lang=''` etiketsiz
        # (başka dile ait olabilecek) eski kayıtları sızdırıp yanlış fuzzy eşleşme verebiliyordu.
        if lang:
            with self._lock:
                rows = self._get_conn().execute(
                    "SELECT source, target FROM tm WHERE tgt_lang = ? AND LENGTH(source) BETWEEN ? AND ? LIMIT 500",
                    (lang, lo, hi)
                ).fetchall()
        else:
            with self._lock:
                rows = self._get_conn().execute(
                    "SELECT source, target FROM tm WHERE LENGTH(source) BETWEEN ? AND ? LIMIT 500",
                    (lo, hi)
                ).fetchall()

        best_target = None
        best_ratio  = 0.0
        matcher = SequenceMatcher(isjunk=None, autojunk=False)
        matcher.set_seq2(src_norm)
        for db_src, db_tgt in rows:
            candidate_norm = " ".join(db_src.strip().lower().split())
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
              profanity: str = "", schema_name: str = "") -> bool:
        """Yeni bir çeviri çiftini TM'ye kaydet. Hata varsa False döner."""
        if not source or not target:
            return False
        _t = target.strip()
        _s = source.strip()
        if _is_missing_translation(_t):
            return False
        if _s.lower() == _t.lower():
            return False
        if not _is_safe_target(_t):
            return False
        fingerprint = self._settings_fingerprint(model, profanity)
        h = self._hash(source, tgt_lang, fingerprint)
        try:
            with self._lock:
                conn = self._get_conn()
                conn.execute(
                    "INSERT OR REPLACE INTO tm(hash,source,target,model,ts,tgt_lang,profanity,schema_name) "
                    "VALUES(?,?,?,?,?,?,?,?)",
                    (h, source.strip(), target.strip(), model, time.time(),
                     tgt_lang.strip().lower(), profanity.strip().lower()[:20] if profanity else "",
                     schema_name.strip().lower()[:40] if schema_name else ""),
                )
                conn.commit()
            return True
        except Exception:
            return False

    def store_batch(self, pairs: list[tuple[str, str]], model: str = "", tgt_lang: str = "",
                    profanity: str = "", schema_name: str = ""):
        """Toplu kaydetme. pairs = [(source, target), ...]"""
        if not pairs:
            return
        fingerprint = self._settings_fingerprint(model, profanity)
        rows = []
        for source, target in pairs:
            if not source or not target or _is_missing_translation(target):
                continue
            if source.strip().lower() == target.strip().lower():
                continue
            if not _is_safe_target(target.strip()):
                continue
            rows.append((
                self._hash(source, tgt_lang, fingerprint),
                source.strip(),
                target.strip(),
                model,
                time.time(),
                tgt_lang.strip().lower(),
                profanity.strip().lower()[:20] if profanity else "",
                schema_name.strip().lower()[:40] if schema_name else "",
            ))
        if rows:
            with self._lock:
                conn = self._get_conn()
                conn.executemany(
                    "INSERT OR REPLACE INTO tm(hash,source,target,model,ts,tgt_lang,profanity,schema_name) "
                    "VALUES(?,?,?,?,?,?,?,?)",
                    rows,
                )
                conn.commit()

    # ── İstatistikler ─────────────────────────────────────────────────────────

    def stats(self) -> dict:
        with self._lock:
            row = self._get_conn().execute("SELECT COUNT(*) FROM tm").fetchone()
        return {"total": row[0] if row else 0}

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
        if self._conn:
            self._conn.close()
            self._conn = None

    def __del__(self):
        self.close()
