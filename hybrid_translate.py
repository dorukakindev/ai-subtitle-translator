"""
Hybrid Translator: yardimci model analizi -> OpenAI Batch ceviri.
Mevcut subtitle_localizer projesini import ederek kullanir.
"""

import re
import sys
import json
import math
import time
import hashlib
import traceback
import unicodedata
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed as _as_completed
from app_state import (atomic_write_json, best_effort_cancel_remote_batch,
                       mutate_batch_ids, state_dir, state_path)

_SUBTITLE_PROJECT_PATH = r"C:\Users\T\Desktop\PROJE\Altyazı Çevirisi"
_PROJECT_ROOT = Path(__file__).resolve().parent
_KNOWN_SUBTITLE_PROJECT_PATHS = [
    _PROJECT_ROOT,
    Path(r"C:\Users\T\Desktop\PROJE\Diğer Projeler\Altyazı Çevirisi"),
    Path(r"C:\Users\T\Desktop\PROJE\Altyazı Çevirisi"),
]

_TURKISH_CHARS = set("çÇğĞıİöÖşŞüÜ")

_TURKISH_STOPWORDS = frozenset({
    "bir", "bu", "şu", "o", "ve", "ile", "için", "ama", "fakat", "ancak",
    "çünkü", "ki", "de", "da", "mi", "mu", "mü", "mı", "daha", "en",
    "çok", "az", "tüm", "her", "hiç", "bazı", "kendi", "kendime", "kendine",
    "ben", "sen", "o", "biz", "siz", "onlar", "bana", "sana", "ona",
    "bize", "size", "onlara", "beni", "seni", "bizi", "sizi", "onları",
    "benim", "senin", "onun", "bizim", "sizin", "onların", "burası", "şurası", "orası",
    "burada", "şurada", "orada", "bura", "şura", "ora",
    "şimdi", "sonra", "önce", "hemen", "henüz", "hâlâ", "hala",
    "çünkü", "yani", "acaba", "belki", "keşke", "sanki",
    "değil", "veya", "ya", "ne", "nasıl", "neden", "niçin", "niye",
    "böyle", "şöyle", "öyle", "biraz", "birazdan", "kadar", "gibi", "diye",
    "ise", "idi", "iken", "oldukça", "adeta", "tam", "nerede", "nereden",
    "nereye", "hangi", "kim", "kime", "kimi", "kimin",
    "birkaç", "birçok", "birtakım", "herkes", "herkese", "herkesin", "her şey",
    "bir şey", "birisi", "birine", "birini", "birbirine", "birbiri",
    "yok", "var", "hayır", "evet", "tamam", "peki", "olur",
    "üzere", "karşı", "diğer", "başka", "sadece", "yalnız", "ancak",
    "asla", "hiçbir", "hiçbir şey", "hiçbiri", "yine", "gene",
    "eğer", "madem", "mademki", "oysa", "oysaki", "hâlbuki",
    "esasen", "aslında", "ayrıca", "üstelik", "hem", "hem de", "zaten",
    "doğru", "yanlış", "güzel", "kötü", "iyi", "fena",
    "istiyorum", "istiyor", "istediğin", "istediğim", "gerek", "lazım",
    "belki", "acaba", "sanki", "yoksa", "öyleyse", "neyse",
    "buyrun", "buyurun", "lütfen", "afedersiniz", "özür", "pardon",
    "teşekkür", "sağ ol", "sağol", "merhaba", "hoşça kal", "görüşürüz",
    "efendim", "bey", "hanım", "hanımefendi", "beyefendi",
})

_ENGLISH_STOPWORDS = frozenset({
    "the", "a", "an", "and", "or", "but", "in", "on", "at", "to", "for",
    "of", "with", "by", "from", "as", "is", "was", "are", "were", "be",
    "been", "being", "have", "has", "had", "do", "does", "did", "will",
    "would", "could", "should", "may", "might", "shall", "can", "must",
    "i", "you", "he", "she", "it", "we", "they", "me", "him", "her",
    "us", "them", "my", "your", "his", "its", "our", "their", "mine",
    "yours", "hers", "ours", "theirs", "this", "that", "these", "those",
    "what", "which", "who", "whom", "whose", "where", "when", "why",
    "how", "all", "each", "every", "both", "few", "more", "most",
    "some", "any", "no", "not", "only", "just", "so", "than", "too",
    "very", "here", "there", "up", "down", "out", "off", "over",
    "about", "into", "through", "during", "before", "after", "above",
    "below", "between", "under", "again", "further", "once", "then",
    "if", "because", "while", "unless", "until", "though", "although",
    "like", "know", "get", "go", "see", "make", "want", "think",
    "say", "come", "take", "look", "find", "give", "tell", "work",
    "call", "try", "ask", "need", "feel", "become", "leave", "put",
    "mean", "keep", "let", "begin", "seem", "help", "turn", "show",
    "hear", "play", "run", "move", "live", "believe", "hold", "bring",
    "happen", "write", "provide", "sit", "stand", "lose", "pay", "meet",
    "include", "continue", "set", "learn", "change", "lead", "understand",
    "watch", "follow", "stop", "create", "speak", "read", "allow", "add",
    "spend", "grow", "open", "walk", "win", "offer", "remember", "love",
    "consider", "appear", "buy", "wait", "serve", "die", "send", "expect",
    "build", "stay", "fall", "cut", "reach", "kill", "raise", "pass",
})

_TR_FILENAME_SIGNALS = re.compile(
    r'(?:^|[\s._-])(?:Turkish|Türkçe|turkish|türkçe)(?:[\s._-]|$)'
    r'|\.tr\.(?:srt|vtt|ass)$'
    r'|_tr\.(?:srt|vtt|ass)$',
    re.IGNORECASE
)

_FILENAME_SIGNAL_WORDS = ("turkish", "türkçe", "_tr.", ".tr.")

_CONTENT_SAMPLE_CHARS = 3000


def is_source_likely_turkish(filename: str = "", text: str = "") -> bool:
    if not text and not filename:
        return False
    if filename:
        full_lower = filename.lower().replace(" ", "")
        for sig in _FILENAME_SIGNAL_WORDS:
            if sig in full_lower:
                return True
    if not text or len(text) < 100:
        return False
    sample = text[:_CONTENT_SAMPLE_CHARS]
    tr_char_count = sum(1 for c in sample if c in _TURKISH_CHARS)
    total_alpha = sum(1 for c in sample if c.isalpha())
    if total_alpha == 0:
        return False
    tr_char_ratio = tr_char_count / total_alpha
    words = re.findall(r"[a-z]+", sample.lower())
    if not words:
        return False
    tr_stop = sum(1 for w in words if w in _TURKISH_STOPWORDS)
    en_stop = sum(1 for w in words if w in _ENGLISH_STOPWORDS)
    total_stop = tr_stop + en_stop
    if total_stop < 5:
        return tr_char_ratio > 0.08
    tr_ratio = tr_stop / total_stop
    if tr_char_ratio > 0.03 and tr_ratio > 0.55:
        return True
    return False


CONTEXT_LINES   = 20  # preceding cues sent as rolling context
LOOKAHEAD_LINES = 10  # next-chunk cues sent as read-ahead
SCENE_GAP_SEC   = 3.0   # gap ≥ this resets rolling context (new scene)
# Bir çok-satırlı cümle fragman grubu en fazla bu kadar cue sürebilir; daha uzun
# kapanmayan dizi = noktalamasız dosya (gerçek cümle değil) → bağımsız bırakılır.
MAX_FRAG_GROUP  = 10
CPS_WARN_LIMIT = 24    # characters/second — Turkish naturally longer than English; 24 is safe for TR subs

ANALYSIS_DEPTH_LABELS = ("Standart", "Gelismis", "Maksimum")
_ANALYSIS_DEPTH_DISPLAY = {
    "standard": "Standart",
    "advanced": "Gelismis",
    "maximum": "Maksimum",
}
_ANALYSIS_DEPTH_CONFIG = {
    "standard": {
        "chunk_size": 2000,
        "sample_limit": 250,
        "max_tokens": 1800,
        "scene_note_limit": 20,
    },
    "advanced": {
        "chunk_size": 900,
        "sample_limit": 900,
        "max_tokens": 4500,
        "scene_note_limit": 25,
    },
    "maximum": {
        "chunk_size": 550,
        "sample_limit": 550,
        "max_tokens": 7000,
        "scene_note_limit": 35,
    },
}


def normalize_analysis_depth(value: str) -> str:
    raw = str(value or "").strip()
    if not raw:
        return "standard"
    ascii_key = unicodedata.normalize("NFKD", raw).encode("ascii", "ignore").decode("ascii")
    key = ascii_key.lower().replace("-", "_").replace(" ", "_")
    aliases = {
        "standard": "standard",
        "standart": "standard",
        "normal": "standard",
        "default": "standard",
        "advanced": "advanced",
        "gelismis": "advanced",
        "gelismis_analiz": "advanced",
        "deep": "advanced",
        "maximum": "maximum",
        "maksimum": "maximum",
        "max": "maximum",
    }
    return aliases.get(key, "standard")


def analysis_depth_label(value: str) -> str:
    return _ANALYSIS_DEPTH_DISPLAY[normalize_analysis_depth(value)]


def _analysis_depth_config(value: str) -> dict:
    return _ANALYSIS_DEPTH_CONFIG[normalize_analysis_depth(value)]


# ── Timestamp / CPS yardımcıları ─────────────────────────────────────────────

def _ts_to_sec(ts: str) -> float:
    """'00:01:23,456' → 83.456"""
    ts = ts.replace(',', '.')
    h, m, s = ts.split(':')
    return int(h) * 3600 + int(m) * 60 + float(s)


def cps(text: str, duration_sec: float) -> float:
    """Characters per second (display speed) for a subtitle block."""
    chars = len(text.replace('\n', ' ').strip())
    return chars / duration_sec if duration_sec > 0 else 0.0


def _clean_source_text(text: str) -> str:
    """Strip HTML / ASS formatting tags from source subtitle text before translation."""
    text = re.sub(r'</?[a-zA-Z][^>]*>', '', text)   # <i>, <b>, <font color=...>
    text = re.sub(r'\{[^}]+\}', '', text)             # {an8}, {\c&HFFFFFF&}
    text = re.sub(r'  +', ' ', text)
    return text.strip()


_TERM_RE_CACHE = {}


def term_in_text(term: str, text_lower: str) -> bool:
    """Sözlük/deyim anahtarının chunk metninde geçip geçmediğini KELİME-SINIRI
    duyarlı kontrol eder.

    Eski davranış ham substring'di: 'art' anahtarı 'start'/'departed' içinde,
    'win' 'window' içinde yanlışça eşleşip alakasız terimi enjekte ediyordu.

    - Tek-kelimelik alfasayısal anahtar (İngilizce kaynak terimi): sol sınır +
      İngilizce çoğul/iyelik eki ('s / 's) toleransı. 'detonator' → 'detonators'
      eşleşir; 'art' → 'start'/'artist' eşleşMEZ.
    - Çok kelimeli veya noktalama/tire içeren anahtar ('New York', "rock'n'roll",
      'co-op'): güvenli substring fallback (regex sınırı bunlarda kayıp verir).
    """
    if not term or not text_lower:
        return False
    key = term.lower().strip()
    if not key:
        return False
    if " " in key or not re.fullmatch(r"\w+", key, re.UNICODE):
        return key in text_lower                      # çok kelimeli / noktalamalı → substring
    pat = _TERM_RE_CACHE.get(key)
    if pat is None:
        pat = re.compile(r"(?<!\w)" + re.escape(key) + r"(?:'?s)?(?!\w)", re.UNICODE)
        _TERM_RE_CACHE[key] = pat
    return pat.search(text_lower) is not None


def _ends_sentence(text: str) -> bool:
    """True if text ends with sentence-closing punctuation (handles trailing quotes)."""
    t = text.strip().rstrip('"\'»"\u201d')
    return bool(t) and t[-1] in '.!?…'


def _ellipsis_continues(cur: str, nxt: str) -> bool:
    """'...' ile biten satır devam cümlesi mi? Sonraki satır elipsisle veya
    küçük harfle başlıyorsa cümle sarkıyor demektir ('Düşünüyordum...' / '...dün olanları')."""
    c = cur.rstrip('"\'»” ').rstrip()
    if not (c.endswith('...') or c.endswith('…')):
        return False
    n = nxt.lstrip('"\'«“ ').lstrip()
    return bool(n) and (n.startswith('...') or n.startswith('…') or n[0].islower())


def _tag_fragments(cues: list, scene_gap_sec: float = None) -> dict:
    """Detect multi-line sentence fragments among subtitle cues.
    Returns {cue.index: tag} where tag is:
      'none'  — complete standalone sentence
      'start' — first line of a multi-line sentence
      'mid'   — middle of a multi-line sentence (3+ line groups)
      'end'   — last line of a multi-line sentence
    """
    tags = {}
    n = len(cues)
    gap_limit = SCENE_GAP_SEC if scene_gap_sec is None else float(scene_gap_sec)

    def _closes(k: int) -> bool:
        """cues[k] cümleyi kapatıyor mu? (elipsis devamı kapatmaz)"""
        t = _clean_source_text(cues[k].text)
        if not _ends_sentence(t):
            return False
        nxt = _clean_source_text(cues[k + 1].text) if k + 1 < n else ""
        return not _ellipsis_continues(t, nxt)

    def _scene_break_before(k: int) -> bool:
        if k <= 0 or gap_limit <= 0:
            return False
        try:
            return (_ts_to_sec(cues[k].start) - _ts_to_sec(cues[k - 1].end)) >= gap_limit
        except Exception:
            return False

    i = 0
    while i < n:
        if _closes(i) or i == n - 1:
            tags[cues[i].index] = "none"
            i += 1
        else:
            # Start of a multi-line sentence group — collect until sentence ends
            group = [i]
            j = i + 1
            closed = False
            while j < n:
                if _scene_break_before(j):
                    break
                group.append(j)
                if _closes(j) or j == n - 1:
                    closed = True
                    break
                j += 1
            i = group[-1] + 1
            if not closed:
                for k in group:
                    tags[cues[k].index] = "none"
                continue
            # GÜVENLİK: aşırı uzun "kapanmayan" grup = noktalama yok (gerçek cümle değil).
            # Hepsini bağımsız (none) bırak → chunk'lama serbest böler, dev chunk oluşmaz.
            if len(group) > MAX_FRAG_GROUP:
                for k in group:
                    tags[cues[k].index] = "none"
                continue
            if len(group) == 1:
                tags[cues[group[0]].index] = "none"
            elif len(group) == 2:
                tags[cues[group[0]].index] = "start"
                tags[cues[group[1]].index] = "end"
            else:
                tags[cues[group[0]].index] = "start"
                for k in group[1:-1]:
                    tags[cues[k].index] = "mid"
                tags[cues[group[-1]].index] = "end"
    return tags


def _fragment_groups(cues: list, frag_tags: dict | None = None,
                     scene_gap_sec: float = None) -> tuple[dict, list]:
    """Return per-cue fragment group ids and compact source sentence groups."""
    if frag_tags is None:
        frag_tags = _tag_fragments(cues, scene_gap_sec=scene_gap_sec)
    groups = []
    group_by_idx = {}
    current = []

    def _idx(cue):
        return getattr(cue, "index", None)

    def _text(cue):
        return _clean_source_text(getattr(cue, "text", str(cue)))

    def _flush():
        nonlocal current
        if len(current) < 2:
            current = []
            return
        first = _idx(current[0])
        last = _idx(current[-1])
        group_id = f"fg_{first}_{last}"
        items = []
        for cue in current:
            idx = _idx(cue)
            group_by_idx[idx] = group_id
            items.append(idx)
        groups.append({
            "id": group_id,
            "items": items,
        })
        current = []

    for cue in cues:
        idx = _idx(cue)
        tag = frag_tags.get(idx, "none")
        if tag == "start":
            _flush()
            current = [cue]
        elif tag in {"mid", "end"} and current:
            current.append(cue)
            if tag == "end":
                _flush()
        else:
            _flush()
    _flush()
    return group_by_idx, groups


def _scene_cut_near(cues: list, start_i: int, target_end: int, window: int = 5,
                    scene_gap_sec: float = None):
    """Chunk hedefinin ±window satır penceresinde sahne sınırı (≥SCENE_GAP_SEC boşluk) arar.
    Bulursa kesim index'ini döner (chunk o index'ten ÖNCE biter), yoksa None.
    Sahne sınırında kesmek, chunk'ların konuşma bütünlüğüne hizalanmasını sağlar."""
    n = len(cues)
    best = None
    gap_limit = SCENE_GAP_SEC if scene_gap_sec is None else float(scene_gap_sec)
    for cand in range(max(start_i + 1, target_end - window),
                      min(n, target_end + window + 1)):
        try:
            gap = _ts_to_sec(cues[cand].start) - _ts_to_sec(cues[cand - 1].end)
        except Exception:
            continue
        if gap >= gap_limit and (best is None
                                 or abs(cand - target_end) < abs(best - target_end)):
            best = cand
    return best


def _make_smart_chunks(cues: list, chunk_size: int, frag_tags: dict = None,
                       scene_gap_sec: float = None) -> list:
    """Split cues into chunks that avoid cutting mid-sentence.
    Prefers scene boundaries near the target size, then sentence boundaries,
    and never splits inside a fragment group (start/mid/end must stay in same chunk)."""
    chunk_size = max(int(chunk_size or 1), 1)
    if frag_tags is None:
        frag_tags = _tag_fragments(cues, scene_gap_sec=scene_gap_sec)
    chunks = []
    i = 0
    n = len(cues)
    while i < n:
        end = min(i + chunk_size, n)
        if end < n:
            # 1) Tercih: sahne sınırına hizala (±5 satır penceresi)
            scene_cut = _scene_cut_near(cues, i, end, scene_gap_sec=scene_gap_sec)
            if scene_cut is not None:
                end = scene_cut
            else:
                # 2) Cümle sonuna hizala (up to +5)
                for extra in range(0, 6):
                    check_idx = end - 1 + extra
                    if check_idx >= n:
                        end = n
                        break
                    text = _clean_source_text(cues[check_idx].text)
                    if _ends_sentence(text):
                        end = min(check_idx + 1, n)
                        break
            # Never cut inside a fragment group: if the last cue in this
            # chunk is 'start' or 'mid', push forward until we hit 'end' —
            # ama sert tavan koy ki noktasız uç durumda chunk şişmesin
            _frag_ceiling = min(n, i + chunk_size + MAX_FRAG_GROUP)
            while (end < _frag_ceiling
                   and frag_tags.get(cues[end - 1].index) in ("start", "mid")):
                end += 1
        chunks.append(cues[i:end])
        i = end
    return chunks


def _has_subtitle_localizer(path: Path) -> bool:
    return (path / "subtitle_localizer").is_dir()


def resolve_subtitle_project_path(path: str = "") -> str:
    candidates = []
    if path:
        raw = Path(path).expanduser()
        candidates.extend([raw, raw.parent])
    candidates.extend(_KNOWN_SUBTITLE_PROJECT_PATHS)

    seen = set()
    for candidate in candidates:
        try:
            resolved = candidate.resolve()
        except Exception:
            resolved = candidate
        key = str(resolved).lower()
        if key in seen:
            continue
        seen.add(key)
        if _has_subtitle_localizer(resolved):
            return str(resolved)

    raise ModuleNotFoundError(
        "subtitle_localizer bulunamadı. External Project Path, subtitle_localizer klasörünü "
        "içeren proje kökü olmalı."
    )


def set_project_path(path: str):
    global _SUBTITLE_PROJECT_PATH
    _SUBTITLE_PROJECT_PATH = resolve_subtitle_project_path(path)


def _ensure_path():
    project_path = resolve_subtitle_project_path(_SUBTITLE_PROJECT_PATH)
    if project_path and project_path not in sys.path:
        sys.path.insert(0, project_path)


# ── SRT yükleme ──────────────────────────────────────────────────────────────

def load_srt(filepath: str) -> list:
    _ensure_path()
    from subtitle_localizer.srt import parse_srt
    from subtitle_formats import read_subtitle_text
    text = read_subtitle_text(filepath)
    result = parse_srt(text)
    if not result and text.lstrip().startswith("WEBVTT"):
        from subtitle_formats import parse_vtt
        blocks = parse_vtt(filepath)
        srt_text = "\n\n".join(f"{i}\n{ts}\n{txt}"
                               for i, (idx, ts, txt) in enumerate(blocks, 1))
        return parse_srt(srt_text)
    return result


def load_subtitle(filepath: str) -> list:
    """SRT/VTT/ASS -> subtitle_localizer Cue listesi. VTT/ASS, subtitle_formats ile
    (idx, SRT-zaman, metin) demetlerine cevrilip SRT metni olarak ayni parser'a verilir -
    boylece hybrid analiz/ceviri Cue nesnelerini her formatta alir (eskiden yalniz .srt)."""
    ext = Path(filepath).suffix.lower()
    if ext in (".vtt", ".ass", ".ssa"):
        _ensure_path()
        from subtitle_localizer.srt import parse_srt
        from subtitle_formats import parse_vtt, parse_ass
        blocks = parse_vtt(filepath) if ext == ".vtt" else parse_ass(filepath)
        srt_text = "\n\n".join(f"{i}\n{ts}\n{txt}"
                               for i, (idx, ts, txt) in enumerate(blocks, 1))
        return parse_srt(srt_text)
    return load_srt(filepath)


def load_glossary(filepath: str) -> dict:
    if not filepath or not Path(filepath).exists():
        return {}
    ext = Path(filepath).suffix.lower()
    encodings = ["utf-8-sig", "cp1254"]
    content = None
    for enc in encodings:
        try:
            with open(filepath, "r", encoding=enc) as f:
                content = f.read()
            break
        except (UnicodeDecodeError, UnicodeError):
            continue
    if content is None:
        return {}
    result = {}
    if ext == ".json":
        try:
            parsed = json.loads(content)
            if isinstance(parsed, dict):
                for k, v in parsed.items():
                    ks = str(k).strip() if k is not None else ""
                    if not ks:
                        continue
                    vs = None
                    if isinstance(v, str):
                        vs = v.strip()
                    elif type(v) in (int, float) and not isinstance(v, bool):
                        vs = str(v).strip()
                    if ks and vs:
                        result[ks] = vs
        except json.JSONDecodeError:
            pass
    else:
        import csv
        for line in content.splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            k, v = None, None
            if "\t" in line:
                k, _, v = line.partition("\t")
            elif "=" in line:
                k, _, v = line.partition("=")
            elif "," in line:
                try:
                    parsed_csv = next(csv.reader([line]))
                    if len(parsed_csv) >= 2:
                        k, v = parsed_csv[0], parsed_csv[1]
                except Exception:
                    pass
            if k is not None and v is not None:
                ks, vs = k.strip(), v.strip()
                if ks and vs:
                    result[ks] = vs
    return result


# ── Context önbelleği ─────────────────────────────────────────────────────────

def _cache_path(filepath: str) -> Path:
    p = Path(filepath)
    return p.parent / ".context_cache" / (p.name + ".json")


def _legacy_cache_path(filepath: str) -> Path:
    p = Path(filepath)
    return p.parent / ".context_cache" / (p.stem + ".json")


def _cache_sig(filepath: str) -> str:
    """Kaynak dosyanın SHA-256 tabanlı akış imzası (sha256:<hex>). Dosya içeriği değişince değişir."""
    try:
        h = hashlib.sha256()
        with open(filepath, "rb") as f:
            while chunk := f.read(65536):
                h.update(chunk)
        return f"sha256:{h.hexdigest()}"
    except Exception:
        return ""


def save_context_cache(context, filepath: str, character_examples: dict = None,
                       pronoun_map: dict = None, character_styles: dict = None,
                       scene_emotions: list = None, idiom_map: dict = None,
                       cultural_refs: list = None, target_language: str = "",
                       analysis_depth: str = "standard"):
    _ensure_path()
    sig = _cache_sig(filepath)
    if not sig or not sig.startswith("sha256:"):
        return
    path = _cache_path(filepath)
    data = {
        "source_language":    context.source_language,
        "summary":            context.summary,
        "setting":            context.setting,
        "tone":               context.tone,
        "characters":         [{"name": c.name, "speaking_style": c.speaking_style}
                               for c in context.characters],
        "recurring_terms":    context.recurring_terms,
        "scene_notes":        context.scene_notes,
        "character_examples": character_examples or {},
        "pronoun_map":        pronoun_map or {},
        # New fields — v2 cache
        "character_styles":   character_styles or {},
        "scene_emotions":     scene_emotions or [],
        "idiom_map":          idiom_map or {},
        "cultural_refs":      cultural_refs or [],
        "analysis_depth":     normalize_analysis_depth(analysis_depth),
        "_sig":               sig,   # kaynak dosya imzası (bayat-önbellek koruması)
        "target_language":    target_language or "",  # hedef dil değişirse analizi yeniden kullanma
    }
    # Atomik yazım: yarım kalan dosya bozuk önbellek bırakmasın
    try:
        atomic_write_json(path, data)
    except Exception:
        pass


def _scene_plan_cache_is_stale(scenes) -> bool:
    """True if a cached scene_emotions list predates the scene-plan feature (only
    the old one-line 'arc' field, no 'summary'/'speakers'/etc.) — treat as a
    cache-miss so the richer plan gets extracted fresh instead of silently
    carrying forward a field-poor scene list forever."""
    if not isinstance(scenes, list) or not scenes:
        return False
    return not any(isinstance(s, dict) and "summary" in s for s in scenes)


def load_context_cache(filepath: str, expected_target: str = "", expected_analysis_depth: str = ""):
    """Returns 7-tuple or None:
    (ContextMemory, char_examples, pronoun_map, character_styles, scene_emotions, idiom_map, cultural_refs)
    Old v1 caches (missing new fields) are handled gracefully with empty defaults.
    """
    _ensure_path()
    path = _cache_path(filepath)
    if not path.exists():
        return None
    try:
        cur_sig = _cache_sig(filepath)
        if not cur_sig or not cur_sig.startswith("sha256:"):
            return None

        from subtitle_localizer.models import ContextMemory, CharacterVoice
        with open(path, encoding="utf-8") as f:
            d = json.load(f)

        cached_sig = d.get("_sig")
        if not isinstance(cached_sig, str) or not cached_sig.startswith("sha256:") or cached_sig != cur_sig:
            return None

        if expected_target:
            cached_target = d.get("target_language")
            if not cached_target or cached_target != expected_target:
                return None

        if expected_analysis_depth:
            raw_cached_depth = d.get("analysis_depth")
            if not raw_cached_depth:
                return None
            cached_depth = normalize_analysis_depth(raw_cached_depth)
            expected_depth = normalize_analysis_depth(expected_analysis_depth)
            if cached_depth != expected_depth:
                return None
        memory = ContextMemory(
            source_language=d.get("source_language", ""),
            summary=d.get("summary", ""),
            setting=d.get("setting", ""),
            tone=d.get("tone", ""),
            characters=[CharacterVoice(name=c["name"], speaking_style=c["speaking_style"])
                        for c in d.get("characters", [])],
            recurring_terms=sanitize_glossary_for_turkish(
                d.get("recurring_terms", {}),
                target_language=(d.get("target_language") or expected_target or "tr"),
            ),
            scene_notes=d.get("scene_notes", []),
        )
        _scene_emotions = d.get("scene_emotions", [])
        if _scene_plan_cache_is_stale(_scene_emotions):
            _scene_emotions = []
        return (
            memory,
            d.get("character_examples", {}),
            d.get("pronoun_map", {}),
            d.get("character_styles", {}),    # v2 — empty for old caches
            _scene_emotions,                   # v2 — empty for old/stale-shape caches
            d.get("idiom_map", {}),            # v2 — empty for old caches
            d.get("cultural_refs", []),        # v2 — empty for old caches
        )
    except Exception:
        # Bozuk/eksik önbellek → sil ve cache-miss olarak dön
        try:
            clear_context_cache(filepath)
        except Exception:
            pass
        return None


def clear_context_cache(filepath: str):
    path = _cache_path(filepath)
    if path.exists():
        try:
            path.unlink()
        except Exception:
            pass
    legacy_path = _legacy_cache_path(filepath)
    if legacy_path != path and legacy_path.exists():
        try:
            legacy_path.unlink()
        except Exception:
            pass


# ── Batch Session State ───────────────────────────────────────────────────────
#
# Tracks per-file status across phases so a crashed/interrupted hybrid batch
# can be resumed without re-submitting already-completed files.
#
# Session JSON lives in <script_dir>/_batch_sessions/<hash>_session.json.
# Each unique input_dir gets its own session file; the same file is reused
# across runs so completed files accumulate and are not re-processed.
#
# File statuses:
#   "pending"   — not yet submitted
#   "submitted" — batch_id exists, waiting for OpenAI
#   "completed" — Phase 2 done, SRT written
#   "failed"    — Phase 1 or Phase 2 error (will retry on next run)

def _session_dir() -> Path:
    return state_path(__file__, "_batch_sessions")


def _batch_id_path() -> Path:
    return state_path(__file__, "batch_id.txt")


def _batch_fmap_path(batch_id: str) -> Path:
    return state_path(__file__, f"batch_fmap_{batch_id}.json")


def _session_path(input_dir: str) -> Path:
    h = hashlib.md5(str(input_dir).encode("utf-8")).hexdigest()[:12]
    return _session_dir() / f"{h}_session.json"


def batch_session_fingerprint(input_dir: str, output_dir: str, filepaths: list,
                              settings: dict) -> str:
    files = []
    for fp in filepaths or []:
        p = Path(fp)
        try:
            st = p.stat()
            files.append((str(p.resolve()), st.st_size, st.st_mtime_ns))
        except OSError:
            files.append((str(p), None, None))
    payload = {
        "input_dir": str(input_dir),
        "output_dir": str(output_dir),
        "files": files,
        "settings": settings or {},
    }
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8", "replace")).hexdigest()


def load_batch_session(input_dir: str) -> dict | None:
    """Load existing session for input_dir. Returns None if not found or corrupted."""
    try:
        p = _session_path(input_dir)
        if not p.exists():
            return None
        with open(p, encoding="utf-8") as f:
            data = json.load(f)
        # Guard against hash collisions
        if data.get("input_dir") != str(input_dir):
            return None
        return data
    except Exception:
        return None


def create_batch_session(input_dir: str, output_dir: str, filepaths: list,
                         fingerprint: str = "") -> dict:
    """Create or merge a batch session for the given file list.

    If a session already exists for this input_dir, completed/submitted statuses
    are preserved and only newly-added files get 'pending'. This enables seamless
    resume without re-processing already-done files.

    Returns the session dict (already persisted to disk).
    """
    existing = load_batch_session(input_dir)
    now = time.strftime("%Y-%m-%dT%H:%M:%S")

    if existing and fingerprint and existing.get("fingerprint") != fingerprint:
        existing = None

    if existing:
        session = existing
        session["updated_at"] = now
        session["output_dir"] = output_dir
        # Merge: add new files as pending, keep existing statuses intact
        for fp in filepaths:
            key = str(fp)
            if key not in session["files"]:
                session["files"][key] = {"status": "pending"}
            elif session["files"][key].get("status") == "failed":
                # Retry failed files on next run
                session["files"][key] = {"status": "pending"}
    else:
        session = {
            "version": 1,
            "created_at": now,
            "updated_at": now,
            "input_dir": str(input_dir),
            "output_dir": output_dir,
            "fingerprint": fingerprint,
            "files": {str(fp): {"status": "pending"} for fp in filepaths},
        }

    _save_batch_session(session)
    return session


def _save_batch_session(session: dict):
    session["updated_at"] = time.strftime("%Y-%m-%dT%H:%M:%S")
    p = _session_path(session["input_dir"])
    p.parent.mkdir(exist_ok=True)
    atomic_write_json(p, session)


def update_batch_session(session: dict, filepath: str, status: str,
                         batch_id: str = None, out_path: str = None):
    """Update a file's status in the session and persist to disk immediately."""
    key = str(filepath)
    now = time.strftime("%Y-%m-%dT%H:%M:%S")
    entry = session["files"].setdefault(key, {})
    entry["status"] = status
    if batch_id is not None:
        entry["batch_id"] = batch_id
    if out_path is not None:
        entry["out_path"] = out_path
    if status == "submitted":
        entry["submitted_at"] = now
    elif status in ("completed", "failed"):
        entry["completed_at"] = now
    _save_batch_session(session)


def clear_batch_session(input_dir: str):
    """Delete the session file for this input_dir (called when all files are done)."""
    try:
        p = _session_path(input_dir)
        if p.exists():
            p.unlink()
    except Exception:
        pass


def batch_session_summary(session: dict, filepaths: list) -> dict:
    """Return status counts for the given file list."""
    counts = {"pending": 0, "submitted": 0, "completed": 0, "failed": 0}
    for fp in filepaths:
        st = session["files"].get(str(fp), {}).get("status", "pending")
        counts[st] = counts.get(st, 0) + 1
    return counts


def load_fmap_for_batch(batch_id: str, detailed: bool = False):
    """Load a hybrid batch fmap.

    detailed=True returns (status, fmap). Status is one of: ok, valid_empty,
    missing, invalid_json, invalid_schema, io_error.
    """
    def _result(status, fmap=None):
        if detailed:
            return status, fmap
        return fmap if status in ("ok", "valid_empty") else None

    fmap_path = _batch_fmap_path(batch_id)
    if not fmap_path.exists():
        return _result("missing")
    try:
        with open(fmap_path, encoding="utf-8") as f:
            fmap_data = json.load(f)
    except json.JSONDecodeError:
        return _result("invalid_json")
    except Exception:
        return _result("io_error")

    if not isinstance(fmap_data, dict) or not isinstance(fmap_data.get("fmap"), dict):
        return _result("invalid_schema")
    raw_fmap = fmap_data["fmap"]
    try:
        fmap = {}
        for cid, info in raw_fmap.items():
            if not isinstance(cid, str) or not isinstance(info, list):
                return _result("invalid_schema")
            rows = []
            for row in info:
                if not isinstance(row, (list, tuple)) or len(row) < 3:
                    return _result("invalid_schema")
                rows.append(tuple(row))
            fmap[cid] = rows
    except Exception:
        return _result("invalid_schema")
    return _result("ok" if fmap else "valid_empty", fmap)


# ── Yardimci model analizi ───────────────────────────────────────────────────

def _generate_character_examples(
    characters,
    tgt_lang: str,
    helper_api_key: str,
    helper_url: str,
    helper_model: str,
    log_fn=None,
):
    """Generate 2 sample dialogue lines + register/dialect classification per character.

    Returns tuple: (examples_dict, styles_dict) where:
        examples_dict: {char_name: ["line1", "line2"]}
        styles_dict:   {char_name: {"register": "blue_collar", "dialect": "standard"}}
    Used by analyze_with_helper to give the translator richer voice anchoring.
    """
    if not characters:
        return {}, {}
    try:
        from openai import OpenAI
        client = OpenAI(api_key=helper_api_key, base_url=helper_url)

        char_list = "\n".join(
            f"- {c.name}: {c.speaking_style or 'no specific style noted'}"
            for c in characters[:6]
        )
        prompt = (
            f"For each character below, do TWO things:\n"
            f"1. Write exactly 2 short natural dialogue lines in {tgt_lang}. Lines must "
            f"sound colloquial, authentic, and match each character's speaking style. "
            f"Max 10 words per line. Spoken language only.\n"
            f"2. Classify the character's voice register and dialect.\n"
            f"   - register options: 'formal', 'educated', 'neutral', 'blue_collar', 'street', 'young'\n"
            f"   - dialect options: 'standard', 'rural', 'coastal', 'eastern', 'urban_slang'\n\n"
            f"Characters:\n{char_list}\n\n"
            f'Output JSON:\n'
            f'{{\n'
            f'  "examples": {{"CharacterName": ["line1", "line2"], ...}},\n'
            f'  "styles":   {{"CharacterName": {{"register": "blue_collar", "dialect": "standard"}}, ...}}\n'
            f'}}\n'
            f"Return ONLY the JSON."
        )
        resp = _safe_chat_create(
            client,
            model=helper_model,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=900,
            temperature=0.7,
        )
        raw = resp.choices[0].message.content.strip() if resp.choices else ""

        if not raw:
            return {}, {}

        if raw.startswith("```"):
            raw = "\n".join(raw.split("\n")[1:]).rsplit("```", 1)[0].strip()

        if not raw:
            return {}, {}

        def _parse(payload):
            try:
                data = json.loads(payload)
                return data.get("examples", {}) or {}, data.get("styles", {}) or {}
            except json.JSONDecodeError:
                if "{" in payload and "}" in payload:
                    start = payload.find("{")
                    end = payload.rfind("}") + 1
                    try:
                        data = json.loads(payload[start:end])
                        return data.get("examples", {}) or {}, data.get("styles", {}) or {}
                    except Exception:
                        pass
                return {}, {}

        return _parse(raw)
    except Exception as _e:
        if log_fn:
            log_fn(f"Karakter örnekleri oluşturulamadı: {_e}", "warn")
        return {}, {}


def _generate_pronoun_map(
    context,
    tgt_lang: str,
    helper_api_key: str,
    helper_url: str,
    helper_model: str,
) -> dict:
    """Determine sen/siz (informal/formal) address for each character pair.
    Returns e.g. {"Sherry-Matt": "sen", "Dr.Tolin-Sherry": "siz"}.
    Only meaningful when tgt_lang is Turkish (tr)."""
    if not context.characters or len(context.characters) < 2:
        return {}
    if "tr" not in tgt_lang.lower() and "turkish" not in tgt_lang.lower():
        return {}
    try:
        from openai import OpenAI
        client = OpenAI(api_key=helper_api_key, base_url=helper_url)

        chars = [c.name for c in context.characters[:6]]
        char_styles = "\n".join(
            f"- {c.name}: {c.speaking_style or '—'}"
            for c in context.characters[:6]
        )
        setting = context.setting or ""
        summary = context.summary or ""

        prompt = (
            f"You are analyzing a {tgt_lang} subtitle translation project.\n"
            f"Setting: {setting}\nSummary: {summary}\n"
            f"Characters:\n{char_styles}\n\n"
            f"For Turkish translation, determine whether each character pair uses "
            f"informal ('sen') or formal ('siz') address when speaking TO each other.\n"
            f"Consider: age, social status, relationship type, setting.\n"
            f"Characters: {', '.join(chars)}\n\n"
            f'Output JSON: {{"pronoun_map": {{"CharA-CharB": "sen", "CharC-CharD": "siz"}}}}\n'
            f"List only pairs that clearly interact. Omit uncertain pairs.\n"
            f"Return ONLY the JSON."
        )
        resp = _safe_chat_create(
            client,
            model=helper_model,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=400,
            temperature=0.2,
        )
        raw = (resp.choices[0].message.content or "").strip()

        # Skip empty responses
        if not raw:
            return {}

        # Strip markdown code blocks if present
        if raw.startswith("```"):
            raw = "\n".join(raw.split("\n")[1:]).rsplit("```", 1)[0].strip()

        # Validate and parse JSON
        if not raw:
            return {}

        try:
            data = json.loads(raw)
            return data.get("pronoun_map", {})
        except json.JSONDecodeError:
            # If JSON parsing fails, try to extract JSON object manually
            if "{" in raw and "}" in raw:
                start = raw.find("{")
                end = raw.rfind("}") + 1
                try:
                    data = json.loads(raw[start:end])
                    return data.get("pronoun_map", {})
                except Exception:
                    pass
            return {}
    except Exception:
        return {}


_SCENE_PLAN_MAX_SPEAKERS = 6
_SCENE_PLAN_MAX_REFERENTS = 8
_SCENE_PLAN_SUMMARY_CHARS = 220
_SCENE_PLAN_TONE_CHARS = 120
_SCENE_PLAN_GOAL_CHARS = 100
_SCENE_PLAN_REFERENT_CHARS = 100


def _sanitize_scene_plan_entry(raw: dict) -> dict | None:
    """Coerce/validate one LLM-produced scene-plan entry into a safe, bounded shape.

    Pure function (no I/O) so it's testable without hitting the network. Returns
    None if the entry is missing start/end (unusable for chunk-overlap matching).
    """
    if not isinstance(raw, dict):
        return None

    def _as_int(value, default=None):
        try:
            return int(value)
        except (TypeError, ValueError):
            return default

    start = _as_int(raw.get("start"))
    end = _as_int(raw.get("end"))
    if start is None or end is None:
        return None

    summary = str(raw.get("summary") or "").strip()[:_SCENE_PLAN_SUMMARY_CHARS]
    tone = str(raw.get("tone") or "").strip()[:_SCENE_PLAN_TONE_CHARS]

    raw_speakers = raw.get("speakers")
    speakers = []
    if isinstance(raw_speakers, list):
        for s in raw_speakers[:_SCENE_PLAN_MAX_SPEAKERS]:
            name = str(s or "").strip()
            if name:
                speakers.append(name[:60])

    raw_goals = raw.get("speaker_goals")
    speaker_goals = {}
    if isinstance(raw_goals, dict):
        for k, v in list(raw_goals.items())[:_SCENE_PLAN_MAX_SPEAKERS]:
            key = str(k or "").strip()[:60]
            val = str(v or "").strip()[:_SCENE_PLAN_GOAL_CHARS]
            if key and val:
                speaker_goals[key] = val

    raw_referents = raw.get("referents")
    referents = {}
    if isinstance(raw_referents, dict):
        for k, v in list(raw_referents.items())[:_SCENE_PLAN_MAX_REFERENTS]:
            key = str(k or "").strip()[:30]
            val = str(v or "").strip()[:_SCENE_PLAN_REFERENT_CHARS]
            if key and val:
                referents[key] = val

    return {
        "start": start,
        "end": end,
        "summary": summary,
        "speakers": speakers,
        "speaker_goals": speaker_goals,
        "referents": referents,
        "tone": tone,
    }


def _extract_emotional_arc(
    cues: list,
    tgt_lang: str,
    helper_api_key: str,
    helper_url: str,
    helper_model: str,
    log_fn=None,
) -> list:
    """Extract a per-scene semantic plan from the subtitle file.

    Groups cues into scene blocks by 3-second silence gaps, then asks Helper
    to describe each scene: what's happening, who's speaking and what they want,
    what ambiguous pronouns/deictics refer to, and the overall tone/trajectory.
    This is the context that most helps a translation model resolve pronouns,
    speaker intent, and register correctly — plain per-chunk ctx/next_ctx alone
    cannot carry "who wants what" or "what does 'it' refer to" reliably.

    Returns list of dicts (each sanitized via _sanitize_scene_plan_entry):
        [{"start": idx, "end": idx, "summary": "...", "speakers": [...],
          "speaker_goals": {...}, "referents": {...}, "tone": "..."}]
    Used by build_batch_requests/build_requests to inject per-chunk scene context.
    """
    if not cues:
        return []
    try:
        from openai import OpenAI
        client = OpenAI(api_key=helper_api_key, base_url=helper_url)

        # Group cues into scenes by 3-second gaps
        scenes = []
        current_scene = [cues[0]]
        for prev, curr in zip(cues, cues[1:]):
            try:
                gap = _ts_to_sec(curr.start) - _ts_to_sec(prev.end)
            except Exception:
                gap = 0
            if gap >= SCENE_GAP_SEC:
                scenes.append(current_scene)
                current_scene = [curr]
            else:
                current_scene.append(curr)
        if current_scene:
            scenes.append(current_scene)

        # Limit to first 30 scenes to keep call small
        scenes = scenes[:30]

        scenes_json = []
        for sc in scenes:
            text_sample = " ".join(
                _clean_source_text(c.text) for c in sc[:8]  # first 8 lines as sample
            )
            scenes_json.append({
                "start": sc[0].index,
                "end": sc[-1].index,
                "sample": text_sample[:350],
            })

        arc_lang = tgt_lang if tgt_lang else "English"
        prompt = (
            f"You are analyzing subtitle scenes to build a compact scene plan that helps a "
            f"translation model resolve pronouns, speaker intent, and tone correctly.\n"
            f"For each scene below, using ONLY what is visible in its sample text, provide:\n"
            f"  summary: one short {arc_lang} sentence — what is happening, who does what\n"
            f"  speakers: character/speaker names visible in the sample (empty list if none identifiable)\n"
            f"  speaker_goals: for each listed speaker, one short {arc_lang} phrase for what they want "
            f"or are trying to do in this scene\n"
            f"  referents: for pronouns/deictics that appear AMBIGUOUS in the sample "
            f"(it/this/that/he/she/they/there/etc.), map the exact source word to a short {arc_lang} "
            f"phrase naming what it refers to. Only include ones you can confidently resolve from the "
            f"sample; omit ones you cannot.\n"
            f"  tone: one short {arc_lang} phrase for the scene's emotional tone/trajectory "
            f"(e.g. under 10 words)\n"
            f"Do NOT invent facts absent from the sample. If a field has nothing to report, use an "
            f"empty list/object/string for it — never guess.\n\n"
            f"Scenes:\n{json.dumps(scenes_json, ensure_ascii=False)}\n\n"
            f'Return JSON: {{"scenes": [{{"start": N, "end": N, "summary": "...", "speakers": ["..."], '
            f'"speaker_goals": {{"Name": "..."}}, "referents": {{"it": "..."}}, "tone": "..."}}]}}\n'
            f"Return ONLY the JSON."
        )
        resp = _safe_chat_create(
            client,
            model=helper_model,
            messages=[{"role": "user", "content": prompt}],
            # Ölçülen teorik max ~8000 (30 sahne, tüm alanlar dolu); eski 3000 sınırı
            # gpt-5 ailesinde reasoning token'larını da içerdiğinden (bkz.
            # _safe_chat_create max_tokens->max_completion_tokens dönüşümü) uzun
            # belgesellerde JSON'u kesip fonksiyonu sessizce [] döndürebiliyordu.
            # Alanlar zaten _sanitize_scene_plan_entry ile sınırlı — üst-sınır
            # kontrollü, sınırsız büyüme riski yok.
            max_tokens=8000,
            temperature=0.3,
        )
        raw = (resp.choices[0].message.content or "").strip()
        if not raw:
            return []
        if raw.startswith("```"):
            raw = "\n".join(raw.split("\n")[1:]).rsplit("```", 1)[0].strip()
        if not raw:
            return []
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            data = None
            if "{" in raw and "}" in raw:
                start_i = raw.find("{")
                end_i = raw.rfind("}") + 1
                try:
                    data = json.loads(raw[start_i:end_i])
                except Exception:
                    data = None
        if not isinstance(data, dict):
            return []
        raw_scenes = data.get("scenes", [])
        if not isinstance(raw_scenes, list):
            return []
        sanitized = [_sanitize_scene_plan_entry(s) for s in raw_scenes]
        return [s for s in sanitized if s]
    except Exception as e:
        if log_fn:
            log_fn(f"Sahne planı çıkarılamadı: {e}", "warn")
        return []


def _generate_idiom_map(
    cues: list,
    tgt_lang: str,
    helper_api_key: str,
    helper_url: str,
    helper_model: str,
    log_fn=None,
) -> dict:
    """Detect English idiomatic expressions in cues; generate natural target-language equivalents.

    Returns dict: {"beating a dead horse": "boşa çabalamak", ...} (up to 30 entries)
    """
    if not cues:
        return {}
    try:
        from openai import OpenAI
        client = OpenAI(api_key=helper_api_key, base_url=helper_url)

        # Sample up to 300 cues evenly to stay within token limits
        sample_step = max(1, len(cues) // 300)
        sample_texts = [_clean_source_text(c.text) for c in cues[::sample_step]][:300]
        combined = "\n".join(sample_texts)

        prompt = (
            f"You are a translation expert specializing in {tgt_lang}.\n"
            f"Analyze the following subtitle text and identify:\n"
            f"1. English idiomatic expressions (e.g. 'beating a dead horse', 'spill the beans')\n"
            f"2. Colloquial phrases with non-literal meaning (e.g. 'cut me some slack', 'on thin ice')\n"
            f"3. Cultural slang that would sound unnatural if translated literally\n\n"
            f"For each, provide the most natural {tgt_lang} equivalent that preserves the MEANING "
            f"(not a word-for-word translation).\n"
            f"Only include expressions that actually appear in the text. Maximum 30 entries.\n\n"
            f"Text:\n{combined[:3000]}\n\n"
            f'Return JSON: {{"idioms": {{"english expression": "{tgt_lang} equivalent", ...}}}}\n'
            f"Return ONLY the JSON. If no idioms found, return {{\"idioms\": {{}}}}"
        )
        resp = _safe_chat_create(
            client,
            model=helper_model,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=800,
            temperature=0.3,
        )
        raw = (resp.choices[0].message.content or "").strip()
        if not raw:
            return {}
        if raw.startswith("```"):
            raw = "\n".join(raw.split("\n")[1:]).rsplit("```", 1)[0].strip()
        try:
            data = json.loads(raw)
            return data["idioms"] if isinstance(data.get("idioms"), dict) else {}
        except json.JSONDecodeError:
            if "{" in raw and "}" in raw:
                start_i = raw.find("{")
                end_i = raw.rfind("}") + 1
                try:
                    data = json.loads(raw[start_i:end_i])
                    return data["idioms"] if isinstance(data.get("idioms"), dict) else {}
                except Exception:
                    pass
            return {}
    except Exception as e:
        if log_fn:
            log_fn(f"Deyim haritası oluşturulamadı: {e}", "warn")
        return {}


def _generate_cultural_refs(
    cues: list,
    schema: dict,
    tgt_lang: str,
    helper_api_key: str,
    helper_url: str,
    helper_model: str,
    log_fn=None,
) -> list:
    """Detect cultural references (pop culture, brand names, regional references) in cues.
    Recommends keep/localize/gloss action for each.

    Returns list of dicts: [{src, type, action, target}]
    """
    if not cues:
        return []
    try:
        from openai import OpenAI
        client = OpenAI(api_key=helper_api_key, base_url=helper_url)

        sample_step = max(1, len(cues) // 200)
        sample_texts = [_clean_source_text(c.text) for c in cues[::sample_step]][:200]
        combined = "\n".join(sample_texts)

        # Genre hint to guide localization decisions
        genre = schema.get("name", "general") if schema else "general"
        is_comedy = "comedy" in genre.lower() or "sitcom" in genre.lower()
        localize_default = "localize" if not is_comedy else "keep"

        prompt = (
            f"Analyze this subtitle text for cultural references that a translator must handle.\n"
            f"Genre: {genre}\n\n"
            f"Identify:\n"
            f"- Pop culture references (movie/show/song/character names, memes)\n"
            f"- Brand names and products\n"
            f"- Regional/cultural expressions (American places, institutions, customs)\n"
            f"- Historical figures or events mentioned\n\n"
            f"For each reference, decide the best translation strategy for {tgt_lang} audience:\n"
            f"  'keep'     — audience will recognize it, keep unchanged (e.g. Marvel, Netflix)\n"
            f"  'localize' — replace with {tgt_lang} equivalent (e.g. US baseball team → Turkish equivalent)\n"
            f"  'gloss'    — keep but add brief clarification in parentheses\n\n"
            f"Default for this genre: {localize_default}\n\n"
            f"Text:\n{combined[:2500]}\n\n"
            f'Return JSON: {{"refs": [{{"src": "...", "type": "pop_culture|brand|regional|historical", "action": "keep|localize|gloss", "target": "Turkish equivalent if localize"}}]}}\n'
            f"Only include items that clearly appear in the text. Return ONLY the JSON."
        )
        resp = _safe_chat_create(
            client,
            model=helper_model,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=600,
            temperature=0.3,
        )
        raw = (resp.choices[0].message.content or "").strip()
        if not raw:
            return []
        if raw.startswith("```"):
            raw = "\n".join(raw.split("\n")[1:]).rsplit("```", 1)[0].strip()
        try:
            data = json.loads(raw)
            return data["refs"] if isinstance(data.get("refs"), list) else []
        except json.JSONDecodeError:
            if "{" in raw and "}" in raw:
                start_i = raw.find("{")
                end_i = raw.rfind("}") + 1
                try:
                    data = json.loads(raw[start_i:end_i])
                    return data["refs"] if isinstance(data.get("refs"), list) else []
                except Exception:
                    pass
            return []
    except Exception as e:
        if log_fn:
            log_fn(f"Kültürel referanslar çıkarılamadı: {e}", "warn")
        return []


def _strip_code_fence(raw: str) -> str:
    """Fenced ```json ... ``` kod bloklarını (tek satır veya çok satırlı) güvenle soyar."""
    raw = (raw or "").strip()
    if not raw.startswith("```"):
        return raw
    if "\n" not in raw and raw.endswith("```") and raw.count("```") >= 2:
        inner = raw[3:-3].strip()
        if inner.lower().startswith("json"):
            inner = inner[4:].strip()
        return inner
    lines = raw.split("\n")
    inner = "\n".join(lines[1:])
    return inner.rsplit("```", 1)[0].strip()


def _extract_json_object(raw: str) -> dict:
    """JSON objesini ham API cevabından çıkarır.

    Anthropic ve diğer modeller bazen JSON çevresine açıklama metni ekler.
    Bu fonksiyon o durumu handle eder:
    - ```json ... ``` bloklarını soyar
    - Brace sayma ile gerçek JSON nesnesini bulur (rfind ile sona eklenen
      metin nedeniyle yanlış kesme sorununu giderir)
    - Son aşamada regex ile anahtar alanları dağınık yanıttan toparlamayı dener
    """
    raw = _strip_code_fence(raw)
    if not raw:
        return {}
    # Önce direkt parse dene
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        pass
    # JSON nesnesi için brace sayma ile gerçek sınırları bul
    if "{" not in raw:
        return {}
    start_i = raw.find("{")
    depth = 0
    end_i = -1
    in_string = False
    escape_next = False
    for idx in range(start_i, len(raw)):
        ch = raw[idx]
        if escape_next:
            escape_next = False
            continue
        if ch == "\\" and in_string:
            escape_next = True
            continue
        if ch == '"':
            in_string = not in_string
            continue
        if in_string:
            continue
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                end_i = idx + 1
                break
    if end_i == -1:
        return {}
    bracket_json = raw[start_i:end_i]
    try:
        return json.loads(bracket_json)
    except Exception:
        pass

    # ── Recovery 1: trailing commaları temizle ──
    try:
        cleaned = re.sub(r",\s*([}\]])", r"\1", bracket_json)
        cleaned = re.sub(r"([{\[,])\s*,", r"\1", cleaned)
        return json.loads(cleaned)
    except Exception:
        pass

    # ── Recovery 2: Python-lite değerleri JSON'a çevir (True/False/None) ──
    try:
        fixed = bracket_json
        fixed = re.sub(r'\bTrue\b', 'true', fixed)
        fixed = re.sub(r'\bFalse\b', 'false', fixed)
        fixed = re.sub(r'\bNone\b', 'null', fixed)
        fixed = re.sub(r",\s*([}\]])", r"\1", fixed)
        return json.loads(fixed)
    except Exception:
        pass

    # ── Recovery 3: string içi kontrolsüz tırnakları onarmaya çalış ──
    try:
        fixed = _repair_unescaped_quotes_in_strings(bracket_json)
        if fixed:
            fixed = re.sub(r",\s*([}\]])", r"\1", fixed)
            fixed = re.sub(r'\bTrue\b', 'true', fixed)
            fixed = re.sub(r'\bFalse\b', 'false', fixed)
            fixed = re.sub(r'\bNone\b', 'null', fixed)
            return json.loads(fixed)
    except Exception:
        pass

    # ── Recovery 4: regex ile anahtar alanları dağınık yanıttan çek ──
    return _regex_extract_analysis_fields(raw)


def _repair_unescaped_quotes_in_strings(text: str) -> str:
    """JSON string değerleri içindeki kontrolsüz çift tırnakları escape etmeye çalışır."""
    out = []
    i = 0
    in_string = False
    escape_next = False
    in_value = False
    while i < len(text):
        ch = text[i]
        if escape_next:
            out.append(ch)
            escape_next = False
            i += 1
            continue
        if in_string:
            if ch == '\\':
                out.append(ch)
                escape_next = True
                i += 1
                continue
            if ch == '"':
                out.append(ch)
                in_string = False
                in_value = False
                i += 1
                continue
            out.append(ch)
            i += 1
            continue
        if ch == '"':
            if text[i:i+3] in ('": "', '": [', '": {'):
                out.append(ch)
                in_string = True
                in_value = True
                i += 1
                continue
            if in_value and text[i-1:i+2] in ('",', '"\n', '"}'):
                out.append(ch)
                in_value = False
                i += 1
                continue
            out.append(ch)
            i += 1
            continue
        out.append(ch)
        i += 1
    return "".join(out)


def _regex_extract_analysis_fields(text: str) -> dict:
    """Regex ile dağınık model yanıtından ana analiz alanlarını çekmeye çalışır."""
    result = {}

    def _first(pattern, group=1):
        m = re.search(pattern, text, re.IGNORECASE | re.DOTALL)
        return m.group(group).strip() if m else None

    tone = _first(r'"tone"\s*[:=]\s*"([^"]*)"')
    if tone:
        result["tone"] = tone

    summary = _first(r'"summary"\s*[:=]\s*"([^"]*)"')
    if summary:
        result["summary"] = summary

    setting = _first(r'"setting"\s*[:=]\s*"([^"]*)"')
    if setting:
        result["setting"] = setting

    source_lang = _first(r'"source_language"\s*[:=]\s*"([^"]*)"')
    if source_lang:
        result["source_language"] = source_lang

    chars = []
    for m in re.finditer(r'"name"\s*[:=]\s*"([^"]*)"', text):
        name = m.group(1).strip()
        if name and name not in chars:
            chars.append(name)
    if chars:
        result["characters"] = [{"name": n, "speaking_style": ""} for n in chars]

    terms = {}
    for m in re.finditer(r'"([^"]+)"\s*[:=]\s*"([^"]*)"\s*[,}]', text):
        key = m.group(1).strip()
        val = m.group(2).strip()
        if key and val and key not in ("name", "speaking_style", "tone", "summary",
                                         "setting", "source_language", "characters",
                                         "recurring_terms", "scene_notes"):
            terms[key] = val
    if terms:
        result["recurring_terms"] = sanitize_glossary_for_turkish(terms)

    notes = []
    for m in re.finditer(r'"scene_notes"\s*[:=]\s*\[(.*?)\]', text, re.DOTALL):
        inner = m.group(1)
        for nm in re.finditer(r'"([^"]*)"', inner):
            n = nm.group(1).strip()
            if n:
                notes.append(n)
    if notes:
        result["scene_notes"] = notes

    return result


def _trunc_err_for_log(estr: str) -> str:
    """Hata mesajı içindeki [raw head: ...] kısmını log'a uygun kısaltır."""
    m = re.search(r"\[raw head:\s*(.*?)\]", estr, re.DOTALL)
    if not m:
        return ""
    head = m.group(1).strip()
    if len(head) > 150:
        head = head[:150] + "..."
    tail = ""
    tm = re.search(r"\[raw tail:\s*(.*?)\]$", estr, re.DOTALL)
    if tm:
        tail_val = tm.group(1).strip()
        if tail_val and len(tail_val) > 120:
            tail = f" | tail: ...{tail_val[-120:]}"
        elif tail_val:
            tail = f" | tail: {tail_val}"
    return f" | raw: {head}{tail}"


def empty_analysis_result(source_language: str = "en"):
    """Return a minimal analysis tuple so translation can continue without helper context."""
    from subtitle_localizer.models import ContextMemory
    return (ContextMemory(source_language=source_language or "en", summary=""), {}, {}, {}, [], {}, [])


def _fallback_context_memory(cues: list, source_language: str = "en", reason: str = ""):
    """Build a minimal per-chunk context when helper analysis cannot be parsed."""
    from subtitle_localizer.models import ContextMemory, CharacterVoice

    def _cue_index(cue, default):
        return getattr(cue, "index", default)

    def _add_name(names, value):
        name = re.sub(r"\s+", " ", str(value or "").strip(" :-\t\r\n"))
        if not name or len(name) > 40:
            return
        key = name.lower()
        if key not in {n.lower() for n in names}:
            names.append(name)

    names = []
    for cue in (cues or [])[:80]:
        text = _clean_source_text(getattr(cue, "text", str(cue)))
        bracket = re.match(r"\s*\[([^\]]{2,40})\]", text)
        if bracket:
            _add_name(names, bracket.group(1))
            continue
        speaker = re.match(r"\s*([A-Z][A-Z0-9 .'\-]{1,38}):", text)
        if speaker:
            _add_name(names, speaker.group(1).title())

    start = _cue_index(cues[0], "?") if cues else "?"
    end = _cue_index(cues[-1], "?") if cues else "?"
    notes = [f"fallback_context: helper analysis returned invalid JSON; cue_range={start}-{end}"]
    if reason:
        notes.append(f"analysis_error: {str(reason)[:180]}")

    return ContextMemory(
        source_language=source_language or "en",
        summary=f"Fallback context for cues {start}-{end}.",
        setting="",
        tone="fallback",
        characters=[
            CharacterVoice(name=name, speaking_style="speaker label detected; fallback context")
            for name in names[:8]
        ],
        recurring_terms={},
        scene_notes=notes,
    )


def _is_deepseek_endpoint(api_url: str, model: str) -> bool:
    return "deepseek" in (api_url or "").lower() or (model or "").lower().startswith("deepseek")


def _is_openai_compatible_endpoint(api_url: str, model: str) -> bool:
    return True


API_REQUEST_TIMEOUT_SECONDS = 300


def _safe_chat_create(client, **kwargs):
    model = kwargs.get("model", "")
    model_lower = (model or "").lower()
    base_url = str(getattr(client, "base_url", "")).lower().rstrip("/")

    # Bedrock and Anthropic provider check
    is_bedrock = False
    is_anthropic = False
    explicit_openai = False
    try:
        from helper_models import normalize_helper_model_label, resolve_helper_model, _CONFIGS, _ALIASES
        norm_label = normalize_helper_model_label(model)
        is_known_model = (model in _CONFIGS) or (model.lower() in _ALIASES) or (norm_label in _CONFIGS and norm_label != "gpt-5.4-mini")
        cfg = resolve_helper_model(norm_label)
        if cfg.provider == "bedrock":
            is_bedrock = True
        elif cfg.provider == "anthropic":
            is_anthropic = True
        elif cfg.provider == "openai" and is_known_model:
            explicit_openai = True
    except Exception:
        pass

    # Fallback/dynamic detection based on URL or model name
    if not is_bedrock and not is_anthropic and not explicit_openai:
        if "bedrock" in base_url or "bedrock" in model_lower:
            is_bedrock = True
        elif ("anthropic" in base_url or base_url.endswith("/messages")
              or ("claude" in model_lower and "/messages" in base_url)):
            if "bedrock" not in base_url and "bedrock" not in model_lower:
                is_anthropic = True

    if is_bedrock:
        api_key = getattr(client, "api_key", None)
        from helper_models import call_bedrock_converse
        return call_bedrock_converse(
            model_id=model,
            messages=kwargs.get("messages", []),
            temperature=kwargs.get("temperature"),
            max_tokens=kwargs.get("max_tokens") or kwargs.get("max_completion_tokens"),
            api_key_str=api_key,
            base_url=base_url
        )

    if is_anthropic:
        api_key = getattr(client, "api_key", None)
        from helper_models import call_anthropic_messages
        return call_anthropic_messages(
            model_id=model,
            messages=kwargs.get("messages", []),
            temperature=kwargs.get("temperature"),
            max_tokens=kwargs.get("max_tokens") or kwargs.get("max_completion_tokens"),
            api_key_str=api_key,
            base_url=base_url
        )

    kwargs = _normalize_chat_create_kwargs(model, kwargs)

    kwargs.setdefault("timeout", API_REQUEST_TIMEOUT_SECONDS)
    return client.chat.completions.create(**kwargs)


def _normalize_chat_create_kwargs(model: str, kwargs: dict) -> dict:
    kwargs = dict(kwargs or {})
    model_lower = (model or "").lower()
    is_reasoning = (
        model_lower.startswith("o1")
        or model_lower.startswith("o3")
        or model_lower.startswith("o4")
    )
    is_gpt5 = model_lower.startswith("gpt-5") or model_lower.startswith("codex-")
    if is_reasoning or is_gpt5:
        kwargs.pop("temperature", None)
        kwargs.pop("response_format", None)
        if "messages" in kwargs:
            new_msgs = []
            for msg in kwargs["messages"]:
                if msg.get("role") == "system":
                    new_msgs.append({"role": "developer", "content": msg.get("content", "")})
                else:
                    new_msgs.append(msg)
            kwargs["messages"] = new_msgs
        if "max_tokens" in kwargs:
            kwargs["max_completion_tokens"] = kwargs.pop("max_tokens")
    return kwargs


def _get_usage_details(usage):
    if not usage:
        return 0, 0
    if isinstance(usage, dict):
        total = usage.get("total_tokens", 0) or 0
        prompt_details = usage.get("prompt_tokens_details") or {}
        cached = prompt_details.get("cached_tokens", 0) or 0
        return total, cached
    
    total = getattr(usage, "total_tokens", 0) or 0
    cached = 0
    try:
        p_details = getattr(usage, "prompt_tokens_details", None)
        if p_details:
            cached = getattr(p_details, "cached_tokens", 0) or 0
    except Exception:
        pass
    return total, cached


def _scene_plan_payload_entry(scene: dict) -> dict | None:
    """Build the compact, payload-ready dict for one scene-plan entry — drops
    start/end (cue-index bookkeeping the model doesn't need) and legacy 'arc'
    (old cache shape, superseded by 'tone'). Returns None if the entry has
    nothing worth injecting (all fields empty — e.g. a stale/legacy cache row)."""
    if not isinstance(scene, dict):
        return None
    entry = {}
    summary = str(scene.get("summary") or "").strip()
    if summary:
        entry["summary"] = summary
    speakers = scene.get("speakers")
    if isinstance(speakers, list) and speakers:
        entry["speakers"] = [str(s) for s in speakers if str(s or "").strip()]
    speaker_goals = scene.get("speaker_goals")
    if isinstance(speaker_goals, dict) and speaker_goals:
        entry["speaker_goals"] = {str(k): str(v) for k, v in speaker_goals.items() if str(v or "").strip()}
    referents = scene.get("referents")
    if isinstance(referents, dict) and referents:
        entry["referents"] = {str(k): str(v) for k, v in referents.items() if str(v or "").strip()}
    tone = str(scene.get("tone") or "").strip()
    if not tone:
        # Legacy cache rows (pre scene-plan) stored the trajectory under 'arc'.
        tone = str(scene.get("arc") or "").strip()
    if tone:
        entry["tone"] = tone[:240]
    return entry or None


def _scene_context_for_chunk(scene_emotions: list | None, start_idx: int, end_idx: int) -> list:
    """Return ALL scene-plan entries that overlap [start_idx, end_idx] — a chunk
    can span more than one scene, and injecting only the first (old behavior)
    silently dropped context for the rest of the chunk."""
    if not scene_emotions:
        return []

    def _as_int(value, default=0):
        try:
            return int(value)
        except (TypeError, ValueError):
            return default

    start_idx = _as_int(start_idx)
    end_idx = _as_int(end_idx)
    matches = []
    for scene in scene_emotions:
        if not isinstance(scene, dict):
            continue
        s_start = _as_int(scene.get("start"))
        s_end = _as_int(scene.get("end"))
        if s_start <= end_idx and s_end >= start_idx:
            entry = _scene_plan_payload_entry(scene)
            if entry:
                matches.append(entry)
    return matches


def _helper_model_log_name(api_url: str, model: str) -> str:
    if not model:
        return "Yardimci model"
    # Provider model IDs should show friendly labels in logs.
    try:
        from helper_models import normalize_helper_model_label, resolve_helper_model
        cfg = resolve_helper_model(normalize_helper_model_label(model))
        if cfg.provider in ("deepseek", "bedrock", "openai", "anthropic") and cfg.model == model:
            return cfg.label
    except Exception:
        pass
    return model


_ANALYSIS_RISK_RE = re.compile(
    r"(\?|\!|\.{3}|[♪♫]|\b(ain't|y'all|gonna|wanna|gotta|dude|bro|sir|ma'am|"
    r"shit|fuck|bitch|ass|damn|hell|slang|meme|song|lyrics)\b)",
    re.IGNORECASE,
)


def _analysis_sample_for_depth(cues: list, analysis_depth: str = "standard") -> list:
    """Return subtitle samples for the helper analysis prompt.

    Standard keeps the legacy first-250 behavior. Deeper modes spend more tokens
    by sampling across the whole chunk, with extra attention to scene boundaries
    and risky slang/idiom-heavy lines.
    """
    cfg = _analysis_depth_config(analysis_depth)
    limit = int(cfg["sample_limit"])
    if not cues or limit <= 0:
        return []

    depth_key = normalize_analysis_depth(analysis_depth)
    if depth_key == "standard":
        selected = list(range(min(limit, len(cues))))
    elif len(cues) <= limit:
        selected = list(range(len(cues)))
    else:
        selected_set = set()

        def add(idx: int):
            if 0 <= idx < len(cues) and len(selected_set) < limit:
                selected_set.add(idx)

        edge_count = min(max(30, limit // 8), 120)
        for idx in range(edge_count):
            add(idx)
        for idx in range(len(cues) - edge_count, len(cues)):
            add(idx)

        boundary_budget = max(20, limit // 8)
        boundary_added = 0
        for idx in range(1, len(cues)):
            try:
                gap = _ts_to_sec(cues[idx].start) - _ts_to_sec(cues[idx - 1].end)
            except Exception:
                gap = 0
            if gap >= SCENE_GAP_SEC:
                add(idx - 1)
                add(idx)
                boundary_added += 2
                if boundary_added >= boundary_budget:
                    break

        risk_budget = max(40, limit // 5)
        risk_added = 0
        for idx, cue in enumerate(cues):
            text = _clean_source_text(getattr(cue, "text", str(cue)))
            if _ANALYSIS_RISK_RE.search(text) or len(text) <= 14:
                before = len(selected_set)
                add(idx)
                if len(selected_set) > before:
                    risk_added += 1
                if risk_added >= risk_budget:
                    break

        remaining = limit - len(selected_set)
        if remaining > 0:
            for pos in range(remaining):
                idx = round(pos * (len(cues) - 1) / max(1, remaining - 1))
                add(idx)

        selected = sorted(selected_set)

    return [
        {
            "id": getattr(cue, "index", idx + 1),
            "pos": idx + 1,
            "text": _clean_source_text(getattr(cue, "text", str(cue))),
        }
        for idx, cue in ((idx, cues[idx]) for idx in selected)
    ]


def _analyze_context_openai_compatible(
    cues: list,
    api_key: str,
    api_url: str,
    model: str,
    glossary: dict,
    style: str,
    source_language: str,
    target_language: str,
    analysis_depth: str = "standard",
    log_fn=None,
):
    _ensure_path()
    from openai import OpenAI
    from subtitle_localizer.models import ContextMemory, CharacterVoice

    depth_key = normalize_analysis_depth(analysis_depth)
    depth_cfg = _analysis_depth_config(depth_key)
    sample = _analysis_sample_for_depth(cues, depth_key)
    depth_guidance = ""
    if depth_key != "standard":
        depth_guidance = (
            f"Analysis depth: {analysis_depth_label(depth_key)}. Spend the extra token budget on "
            "translation-critical decisions, not generic plot recap.\n"
            "- In recurring_terms, include names, nicknames, brands, lore terms, slang, catchphrases, "
            "relationship labels, and repeated jokes that need consistent Turkish handling.\n"
            "- In characters, distinguish narrator voice, quoted dialogue, on-screen text, interviews, "
            "songs/lyrics, and group speakers when visible.\n"
            f"- In scene_notes, include cue ranges when useful and call out register, chronology, ambiguity, "
            f"ellipsis/fragment continuations, cultural references, and sen/siz risks. "
            f"Write AT MOST {depth_cfg['scene_note_limit']} scene_notes; keep each under 80 characters; "
            f"prefer single-line descriptions over timestamp ranges.\n"
        )
        if depth_key == "maximum":
            depth_guidance += (
                f"- Maximum mode: be thorough but stay within token budget. "
                f"Prioritize quality over quantity — {depth_cfg['scene_note_limit']} tight, actionable notes "
                f"are better than verbose descriptions. "
                "Capture dialect/slang, profanity intensity, running gags, emotional turns, and terminology "
                "that could break continuity later.\n"
            )
    prompt = (
        "Analyze this subtitle chunk for translation context. Return ONLY valid JSON.\n"
        f"Source language hint: {source_language}\n"
        f"Target language: {target_language}\n"
        f"Style: {style}\n"
        f"{depth_guidance}"
        f"Glossary: {json.dumps(glossary or {}, ensure_ascii=False)[:1200]}\n\n"
        "Required JSON shape:\n"
        "{\n"
        '  "source_language": "en",\n'
        '  "summary": "short plot/context summary",\n'
        '  "setting": "where/when/social context",\n'
        '  "tone": "overall tone",\n'
        '  "characters": [{"name": "Name", "speaking_style": "voice/register"}],\n'
        '  "recurring_terms": {"source term": "target-language decision"},\n'
        '  "scene_notes": ["translation-relevant note"],\n'
        '  "relationship_notes": ["optional, deeper modes only"],\n'
        '  "translation_risks": ["optional, deeper modes only"]\n'
        "}\n\n"
        f"Subtitles:\n{json.dumps(sample, ensure_ascii=False)}"
    )
    client = OpenAI(api_key=api_key, base_url=api_url)
    # Anthropic modelleri response_format desteklemez; system mesajı ile JSON zorluyoruz
    _is_anthropic_model = False
    try:
        from helper_models import normalize_helper_model_label, resolve_helper_model
        _cfg = resolve_helper_model(normalize_helper_model_label(model))
        _is_anthropic_model = _cfg.provider in ("anthropic", "bedrock")
    except Exception:
        pass
    if not _is_anthropic_model:
        _base = (api_url or "").lower()
        _is_anthropic_model = (
            "anthropic" in _base
            or ("claude" in (model or "").lower() and "anthropic" in _base)
        )

    _messages: list
    _extra: dict
    if _is_anthropic_model:
        # Anthropic/Bedrock: system mesajı ile JSON çıktısını zorla, response_format gönderme
        _messages = [
            {"role": "system", "content": "You are a JSON-only assistant. Always respond with a single valid JSON object and nothing else. Do not include any explanation, preamble, or markdown formatting."},
            {"role": "user", "content": prompt},
        ]
        _extra = {}
    else:
        _messages = [{"role": "user", "content": prompt}]
        _extra = {"response_format": {"type": "json_object"}}

    resp = _safe_chat_create(
        client,
        model=model,
        messages=_messages,
        max_tokens=int(depth_cfg["max_tokens"]),
        temperature=0.2,
        **_extra,
    )
    raw = resp.choices[0].message.content if resp.choices else ""
    data = _extract_json_object(raw)
    if not data:
        snippet = (raw or "")[:300]
        tail = (raw or "")[-300:] if len(raw or "") > 600 else ""
        raise RuntimeError(
            f"context analysis returned invalid JSON "
            f"[raw head: {snippet}]" + (f" [raw tail: {tail}]" if tail else "")
        )

    characters = []
    for item in data.get("characters", [])[:12]:
        if isinstance(item, dict) and item.get("name"):
            characters.append(CharacterVoice(
                name=str(item.get("name", "")).strip(),
                speaking_style=str(item.get("speaking_style", "")).strip(),
            ))

    recurring_terms = sanitize_glossary_for_turkish(
        data.get("recurring_terms", {}), target_language=target_language, log_fn=log_fn
    )
    if not isinstance(recurring_terms, dict):
        recurring_terms = {}
    scene_notes = data.get("scene_notes", [])
    if not isinstance(scene_notes, list):
        scene_notes = []
    for extra_key in ("relationship_notes", "translation_risks", "continuity_notes", "register_rules"):
        extra = data.get(extra_key)
        if isinstance(extra, list):
            scene_notes.extend(f"{extra_key}: {str(item)}" for item in extra if item)
        elif isinstance(extra, dict):
            scene_notes.extend(f"{extra_key}: {k}: {v}" for k, v in extra.items())
        elif isinstance(extra, str) and extra.strip():
            scene_notes.append(f"{extra_key}: {extra.strip()}")

    return ContextMemory(
        source_language=str(data.get("source_language") or source_language or ""),
        summary=str(data.get("summary") or ""),
        setting=str(data.get("setting") or ""),
        tone=str(data.get("tone") or ""),
        characters=characters,
        recurring_terms={str(k): str(v) for k, v in recurring_terms.items()},
        scene_notes=[str(x) for x in scene_notes[:int(depth_cfg["scene_note_limit"])]],
    )


def analyze_with_helper(
    cues: list,
    helper_api_key: str,
    helper_url: str = "https://api.openai.com/v1",
    helper_model: str = "gpt-5.4-mini",
    style: str = "natural",
    source_language: str = "en",
    target_language: str = "tr",
    glossary: dict = None,
    chunk_size: int = 2000,
    max_workers: int = 2,
    log_fn=None,
    stop_flag_fn=None,
    progress_fn=None,
    schema: dict = None,  # Content schema for cultural ref genre-aware decisions
    analysis_depth: str = "standard",
):
    """Returns (ContextMemory, character_examples_dict) or None on failure."""
    _ensure_path()
    from subtitle_localizer.models import ContextAnalysisRequest

    use_openai_compatible = _is_openai_compatible_endpoint(helper_url, helper_model)
    provider = None
    MiniMaxAPIError = Exception
    if not use_openai_compatible:
        from subtitle_localizer.minimax_client import MiniMaxProvider, MiniMaxAPIError
        provider = MiniMaxProvider(
            api_key=helper_api_key,
            api_url=helper_url,
            model=helper_model,
        )

    glossary = glossary or {}
    depth_key = normalize_analysis_depth(analysis_depth)
    depth_cfg = _analysis_depth_config(depth_key)
    effective_chunk_size = min(int(chunk_size), int(depth_cfg["chunk_size"]))
    chunks = [cues[i:i+effective_chunk_size] for i in range(0, len(cues), effective_chunk_size)]

    helper_name = _helper_model_log_name(helper_url, helper_model)
    if log_fn:
        log_fn(f"{helper_name} analizi [{analysis_depth_label(depth_key)}]: "
               f"{len(cues)} satır → {len(chunks)} chunk "
               f"(x{min(max_workers, len(chunks))} paralel)", "info")

    memories    = [None] * len(chunks)
    done_count  = 0
    failed      = False

    def _analyze(i):
        """Geçici hatalarda (429 / 5xx) en fazla 3 kez yeniden dener."""
        req = ContextAnalysisRequest(
            cues=chunks[i],
            glossary=glossary,
            style=style,
            source_language_hint=source_language,
            target_language=target_language,
        )
        last_exc = None
        for attempt in range(3):
            try:
                if use_openai_compatible:
                    return i, _analyze_context_openai_compatible(
                        chunks[i],
                        api_key=helper_api_key,
                        api_url=helper_url,
                        model=helper_model,
                        glossary=glossary,
                        style=style,
                        source_language=source_language,
                        target_language=target_language,
                        analysis_depth=depth_key,
                        log_fn=log_fn,
                    )
                return i, provider.analyze_context(req)
            except Exception as e:
                estr = str(e)
                invalid_json = "invalid json" in estr.lower()
                transient = (
                    "429" in estr or "rate limit" in estr.lower()
                    or any(c in estr for c in ("500", "502", "503", "504"))
                    or invalid_json
                )
                last_exc = e
                if transient and attempt < 2:
                    if invalid_json and log_fn:
                        detail = _trunc_err_for_log(estr)
                        log_fn(
                            f"  Chunk {i+1} analiz cevabi JSON degil; yeniden deneniyor ({attempt+2}/3){detail}",
                            "warn",
                        )
                    time.sleep(2 ** attempt)
                    continue
                if invalid_json:
                    if log_fn:
                        detail = _trunc_err_for_log(estr)
                        log_fn(
                            f"  Chunk {i+1} analiz JSON olarak kurtarilamadi; guvenli bos baglamla devam{detail}",
                            "warn",
                        )
                    return i, _fallback_context_memory(chunks[i], source_language, str(e))
                raise
        raise last_exc

    chunk_errors = 0
    with ThreadPoolExecutor(max_workers=max_workers) as ex:
        futures = {ex.submit(_analyze, i): i for i in range(len(chunks))}
        for fut in _as_completed(futures):
            if stop_flag_fn and stop_flag_fn():
                failed = True
                break
            i = futures[fut]   # chunk index — fut.result() fırlatsa bile bağlı olmalı
            try:
                i, memory = fut.result()
            except MiniMaxAPIError as e:
                chunk_errors += 1
                if log_fn:
                    log_fn(f"  Chunk {i+1} analiz hatası: {e} — atlanıyor", "warn")
                continue
            except Exception as e:
                chunk_errors += 1
                if log_fn:
                    tb = traceback.format_exception(type(e), e, e.__traceback__)
                    compact = "".join(tb[-2:]).strip().replace("\n", " | ")
                    log_fn(f"  Chunk {i+1} beklenmeyen hata: {e} | {compact}", "err")
                continue

            memories[i] = memory
            done_count  += 1

            if progress_fn:
                progress_fn(done_count, len(chunks))
            if log_fn:
                chars = ", ".join(c.name for c in memory.characters[:4])
                log_fn(f"  Chunk {i+1}: Ton:{memory.tone or '?'} | "
                       f"Karakterler:{chars or '—'} | Terimler:{len(memory.recurring_terms)}", "ok")

    # Only abort if user stopped, or EVERY chunk failed
    if failed:
        return None
    successful = [m for m in memories if m is not None]
    if not successful:
        if log_fn:
            log_fn("Tüm analiz chunk'ları başarısız oldu", "err")
        return None
    if chunk_errors > 0 and log_fn:
        log_fn(f"{chunk_errors} chunk atlandı, {len(successful)} başarılı analizle devam", "warn")
    # Sadece başarılı analizleri birleştir — None backfill özet kirlenmesine yol açıyordu
    merged = _merge_memories(successful, target_language=target_language, log_fn=log_fn)
    if log_fn and merged.recurring_terms:
        log_fn(f"Sabit terimler: {merged.recurring_terms}", "ok")

    # Generate character few-shot examples + register/dialect classification (single call)
    if log_fn and merged.characters:
        log_fn(f"Karakter örnekleri oluşturuluyor ({len(merged.characters[:6])} karakter)...", "info")
    examples, character_styles = _generate_character_examples(
        merged.characters, target_language,
        helper_api_key, helper_url, helper_model,
        log_fn=log_fn,
    )
    if log_fn and examples:
        log_fn(f"Karakter örnekleri hazır: {', '.join(examples.keys())}", "ok")
    if log_fn and character_styles:
        log_fn(f"Karakter register: {character_styles}", "ok")

    # Generate pronoun/address map (sen vs siz per character pair)
    pronoun_map = _generate_pronoun_map(
        merged, target_language,
        helper_api_key, helper_url, helper_model,
    )
    if log_fn and pronoun_map:
        log_fn(f"Hitap haritası: {pronoun_map}", "ok")

    # Extract per-scene semantic plan (summary/speakers/goals/referents/tone)
    if log_fn:
        log_fn("Sahne planı analizi yapılıyor...", "info")
    scene_emotions = _extract_emotional_arc(
        cues, target_language,
        helper_api_key, helper_url, helper_model,
        log_fn=log_fn,
    )
    if log_fn and scene_emotions:
        _with_ref = sum(1 for s in scene_emotions if isinstance(s, dict) and s.get("referents"))
        _with_goal = sum(1 for s in scene_emotions if isinstance(s, dict) and s.get("speaker_goals"))
        log_fn(f"Sahne planı: {len(scene_emotions)} sahne "
               f"({_with_ref}'inde gönderge çözümü, {_with_goal}'inde konuşmacı hedefi)", "ok")

    # Generate idiomatic expression map
    if log_fn:
        log_fn("Deyim haritası oluşturuluyor...", "info")
    idiom_map = _generate_idiom_map(
        cues, target_language,
        helper_api_key, helper_url, helper_model,
        log_fn=log_fn,
    )
    if log_fn and idiom_map:
        log_fn(f"Deyim haritası: {len(idiom_map)} deyim", "ok")

    # Generate cultural reference decisions
    if log_fn:
        log_fn("Kültürel referanslar analiz ediliyor...", "info")
    cultural_refs = _generate_cultural_refs(
        cues, schema, target_language,
        helper_api_key, helper_url, helper_model,
        log_fn=log_fn,
    )
    if log_fn and cultural_refs:
        log_fn(f"Kültürel referanslar: {len(cultural_refs)} madde", "ok")

    # Return extended tuple:
    # (merged, examples, pronoun_map, character_styles, scene_emotions, idiom_map, cultural_refs)
    # Callers unpacking first 3 still work; add *_ to catch extras safely.
    return merged, examples, pronoun_map, character_styles, scene_emotions, idiom_map, cultural_refs


def _merge_memories(memories: list, target_language: str = "tr", log_fn=None):
    _ensure_path()
    from subtitle_localizer.models import ContextMemory

    if not memories:
        return ContextMemory(source_language="en", summary="")
    if len(memories) == 1:
        memories[0].recurring_terms = sanitize_glossary_for_turkish(
            getattr(memories[0], "recurring_terms", {}),
            target_language=target_language, log_fn=log_fn,
        )
        return memories[0]

    merged_terms = {}
    for m in memories:
        merged_terms.update(m.recurring_terms)

    seen = set()
    merged_chars = []
    for m in memories:
        for c in m.characters:
            key = c.name.lower()
            if key not in seen:
                seen.add(key)
                merged_chars.append(c)

    seen_notes = set()
    merged_notes = []
    for m in memories:
        for n in m.scene_notes:
            if n not in seen_notes:
                seen_notes.add(n)
                merged_notes.append(n)

    summaries = [m.summary for m in memories if m.summary]
    base = memories[0]

    return ContextMemory(
        source_language=base.source_language,
        summary=" | ".join(summaries),
        setting=next((m.setting for m in memories if m.setting), ""),
        tone=next((m.tone for m in memories if m.tone), ""),
        characters=merged_chars,
        recurring_terms=sanitize_glossary_for_turkish(
            merged_terms, target_language=target_language, log_fn=log_fn
        ),
        scene_notes=merged_notes,
    )


# ── Sistem prompt üretici ─────────────────────────────────────────────────────

def _infer_register(tone: str) -> str:
    tone_l = tone.lower()
    if any(w in tone_l for w in ("documentary", "narrator", "exposition", "neutral")):
        return "documentary"
    if any(w in tone_l for w in ("comedy", "humor", "humorous", "sitcom", "funny", "jokes")):
        return "comedy"
    if any(w in tone_l for w in ("action", "thriller", "tense", "suspense")):
        return "action"
    if any(w in tone_l for w in ("drama", "emotional", "serious", "gritty")):
        return "drama"
    return "general"


from prompt_constants import PROFANITY_RULES as _PROFANITY_RULES, REGISTER_GUIDANCE as _REGISTER_GUIDANCE, JSON_INSTRUCTION


def build_system_prompt(
    context,
    src_lang: str,
    tgt_lang: str,
    schema: dict = None,
    character_examples: dict = None,
    profanity: str = "Orta",
    pronoun_map: dict = None,
    character_styles: dict = None,  # {char_name: {register, dialect}} from analysis
    idiom_map: dict = None,         # {english_idiom: turkish_equivalent}
    cultural_refs: list = None,     # [{src, type, action, target}]
) -> str:
    register = _infer_register(context.tone or "")

    parts = [
        f"You are a professional subtitle translator from {src_lang} to {tgt_lang}.",
        f"CRITICAL: Every translated line MUST be in {tgt_lang} ONLY. "
        f"Never output German, French, Spanish, Dutch, or any language other than {tgt_lang}. "
        f"TURKIC GUARD: when {tgt_lang} is Turkish, write ONLY Türkiye (Anatolian) Turkish — NEVER drift into "
        f"sibling Turkic languages (Uzbek, Azerbaijani, Turkmen, Tatar, Kazakh). Avoid leaks like "
        f"'qora'→'kara/siyah', 'yuqori'→'yüksek', 'pichoq'→'bıçak', 'qilich'→'kılıç', 'jang'→'savaş', "
        f"'qon'→'kan'. Words containing q/w/x are almost always foreign — they are a strong signal of Turkic "
        f"drift, though established loanwords like 'web', 'wifi', 'fax' and proper nouns ('Warp', 'xenos', 'vox') may use them. "
        f"Never output Turkmen-like forms such as 'bäýram', 'holidaý', 'oturylyşyğı', 'ortadagy bezeg', "
        f"'geňlikleri', 'taksidermiya', or 'bäseke'; use real Turkish: 'yılbaşı/tatil partisi', "
        f"'masa süsü', 'taksidermi', 'yarışma parçası'. "
        f"If the source contains foreign words, still translate everything into {tgt_lang}.\n"
        f"NEVER add parenthetical translator notes or glosses '(...)' that do not exist in the source "
        f"line. Translate the term; do not explain it.",
        "SCRIPT GUARD: Turkish uses the Latin alphabet only. "
        f"NEVER output Arabic (ع،ح), Tamil (கோயில்), Devanagari (देव), Cyrillic (текст), "
        "CJK (寺), or ANY non-Latin script characters. "
        "If you see 'temple', 'mosque', 'shrine', translate to Turkish words: "
        "tapınak, cami, türbe — NEVER use the word's form in another language's script.",
        "",
    ]

    if schema and schema.get("rules"):
        parts.append(f"## CONTENT TYPE: {schema['name'].upper()}")
        parts.extend(schema["rules"])
        parts.append("")

    # ── Content context ───────────────────────────────────────────────────────
    context_lines = []
    if context.summary:
        context_lines.append(f"Summary: {context.summary}")
    if context.setting:
        context_lines.append(f"Setting: {context.setting}")
    if context.tone:
        context_lines.append(f"Tone: {context.tone}")
    if context.characters:
        context_lines.append("Characters and their speaking styles:")
        for c in context.characters:
            style = c.speaking_style or "no specific style noted"
            # Enrich with register/dialect if available
            char_key = c.name
            style_info = ""
            if character_styles:
                st = character_styles.get(char_key) or character_styles.get(char_key.lower())
                if st:
                    reg = st.get("register", "")
                    dia = st.get("dialect", "")
                    if reg or dia:
                        style_info = f" | Register: {reg}" + (f" | Dialect: {dia}" if dia and dia != "standard" else "")
            context_lines.append(f"  - {c.name}: {style}{style_info}")
            # Attach few-shot examples if available
            if character_examples:
                exs = character_examples.get(c.name) or character_examples.get(c.name.lower())
                if exs:
                    for ex in exs[:2]:
                        context_lines.append(f'      Sample line: "{ex}"')
        context_lines.append(
            "  (Keep all character names exactly as listed above — do not translate them)")
    if context.scene_notes:
        context_lines.append("Scene notes:")
        for n in context.scene_notes:
            context_lines.append(f"  - {n}")

    if context_lines:
        parts.append("## CONTENT CONTEXT")
        parts.extend(context_lines)
        parts.append("")

    # ── Idiomatic expressions ─────────────────────────────────────────────────
    if isinstance(idiom_map, dict) and idiom_map:
        parts.append("## IDIOMATIC EXPRESSION MAPPINGS")
        parts.append(
            "These English idioms/expressions appear in this content. "
            "Use the given natural Turkish equivalent (NOT a literal translation):"
        )
        for en_idiom, tr_equiv in list(idiom_map.items())[:30]:
            parts.append(f"  \"{en_idiom}\" → \"{tr_equiv}\"")
        parts.append("")

    # ── Cultural references ───────────────────────────────────────────────────
    if isinstance(cultural_refs, list) and cultural_refs:
        keep_refs = [r for r in cultural_refs if isinstance(r, dict) and r.get("action") == "keep"]
        localize_refs = [r for r in cultural_refs if isinstance(r, dict) and r.get("action") == "localize"]
        gloss_refs = [r for r in cultural_refs if isinstance(r, dict) and r.get("action") == "gloss"]
        if keep_refs or localize_refs or gloss_refs:
            parts.append("## CULTURAL REFERENCES")
            if keep_refs:
                parts.append("Keep these references as-is (audience will recognize them):")
                for r in keep_refs[:10]:
                    parts.append(f"  \"{r['src']}\" → keep unchanged")
            if localize_refs:
                parts.append("Localize these to Turkish equivalents:")
                for r in localize_refs[:10]:
                    target = r.get("target", "")
                    parts.append(f"  \"{r['src']}\" → \"{target}\"" if target else f"  \"{r['src']}\" → find natural Turkish equivalent")
            if gloss_refs:
                parts.append("Add brief parenthetical gloss for these:")
                for r in gloss_refs[:5]:
                    target = r.get("target", "")
                    parts.append(f"  \"{r['src']}\" → keep + add brief clarification")
            parts.append("")

    # ── Mandatory terms ───────────────────────────────────────────────────────
    safe_recurring_terms = sanitize_glossary_for_turkish(
        getattr(context, "recurring_terms", {}), target_language=tgt_lang
    )
    if safe_recurring_terms:
        parts.append("## MANDATORY TERM TRANSLATIONS")
        parts.append("Use these exact translations every time — no substitutions allowed:")
        for src, tgt in safe_recurring_terms.items():
            parts.append(f"  {src} → {tgt}")
        parts.append("")

    # ── Translation rules ─────────────────────────────────────────────────────
    parts += [
        "## TRANSLATION RULES",
        f"- Natural, fluent {tgt_lang} — never word-for-word literal",
        "- MEANING-FIRST / sense-for-sense: infer what the speaker or narrator intends ONLY from the visible source "
        "words and surrounding context before translating. Preserve the speech act, implication, subtext, emotion, "
        "and cause-effect; use natural Turkish phrasing when word order and wording change, but "
        "never add unstated ideas. Duration/CPS beats source length: keep Turkish concise for the cue duration; "
        "aim for <=21 CPS and "
        "stay <=24 CPS when possible. Never map source words one by one.",
        "- Preserve polarity exactly: not/never/no/n't must stay negative in Turkish; never flip a denial into "
        "an affirmation or an affirmation into a denial.",
        "- Before translating pronouns and deictics (this/that/it/he/she/him/her/there), resolve what they refer "
        "to. If the 'scene' key's 'referents' field names it explicitly, use that; otherwise resolve from "
        "ctx/next_ctx; if still unclear, keep the Turkish wording neutral rather than inventing a referent.",
        f"- Match the tone exactly: {context.tone or 'match source'}",
        "- Keep the same number of lines as the original subtitle block",
        "- Keep the same number of subtitle lines inside each cue; preserve the existing \\n structure unless a "
        "minimal rebalance is needed for readable Turkish.",
        "- Keep character names, brand names, and proper nouns unchanged",
        "- Preserve ALL HTML-like inline tags exactly: <i>...</i>, <b>...</b>, <u>...</u>, <font ...>",
        "- Informal address (man, dude, buddy, bro) → 'dostum', 'arkadaşım', 'kanka'",
        "- Titles/honorifics use Turkish convention, NOT literal: 'Mr. Smith'→'Bay Smith' or naturally "
        "'Smith Bey'; 'Mrs./Ms. Smith'→'Smith Hanım'; 'Dr. Brown'→'Doktor Brown'; 'Professor X'→'Profesör X'; "
        "ranks use the Turkish rank ('Captain'→'Yüzbaşı', 'Sergeant'→'Çavuş', 'Officer Reed'→'Memur Reed'). "
        "Standalone vocative 'Sir'/'ma'am'→'efendim' (NEVER 'Bay'/'Bayan' alone); 'my lord/lady'→'lordum/leydim'. "
        "Bey/Hanım FOLLOW a first name ('Mr. John'→'John Bey'); Bay/Bayan/Doktor/Profesör/ranks stay BEFORE the "
        "name. Match the chosen sen/siz register.",
        "- Spoken times/numbers use natural Turkish SPEECH, not a literal digit reading: 'half past three'→"
        "'üç buçuk', 'quarter to nine'→'dokuza çeyrek var', 'a.m./p.m.'→drop or 'sabah/akşam'; spoken numbers "
        "stay words ('two thousand'→'iki bin'). Do NOT round or change any value; keep on-screen/written numbers, "
        "dates, scores and exact technical figures EXACTLY. Decimal point in digits → comma (3.5→3,5).",
        "- On-screen TEXT (signs, captions, headlines, displayed messages/letters, location/date cards) is a "
        "label, not speech: render it in flat, neutral Turkish — no colloquial fillers (yani/işte/vay be). "
        "Still correct and natural; keep any source italics. E.g. sign 'EXIT'→'ÇIKIŞ'; text 'On my way'→'Yoldayım'.",
        "- False friends: actually→aslında/gerçekte (NOT aktüel), eventually→sonunda/eninde sonunda "
        "(NOT eventüel), sympathetic→anlayışlı/duyarlı (NOT automatically sempatik), sensible→mantıklı, "
        "ultimately→nihayetinde/sonuçta, fabric→kumaş, library→kütüphane, preservative→koruyucu madde.",
        "- Possessive forms: 'my girlfriend'→'sevgilim' (NOT 'severim'), "
        "'my friend'→'arkadaşım', 'my name'→'adım'",
        "- For technical terms NOT in the glossary, prefer internationally accepted loanwords "
        "('detonatör', 'dinamit', 'robot', 'laser') — do NOT invent Turkish equivalents",
        "- Translate ALL [SFX]/[ACTION] tags to Turkish (e.g. [LAUGHS]→[KAHKAHA], "
        "[SIGHS]→[İÇ ÇEKİŞ], [GASPS]→[NEFES KESİLİŞ], [GAGGING]→[ÖĞÜRME], "
        "[CRYING]→[AĞLAMA], [GROANS]→[İNLEME], [WHISPERING]→[FISILDAMA]) — "
        "never leave an [SFX] tag untranslated",
        "- CRITICAL: every numbered id in the payload MUST receive its own translation, even if its source "
        "is a single word, a short interjection ('Okay.', 'Yeah, yeah.', 'Oh.'), or a bracketed sound effect. "
        "NEVER merge a short cue's meaning into a neighboring id's translation, and NEVER leave a short cue's "
        "translation empty or skip it — doing so shifts every subsequent id's alignment and desyncs the subtitles.",
        "- Do NOT invent words that do not exist in the target language",
        "- Do NOT invent pseudo-Turkish or foreign-looking words. If a term is unknown, use established Turkish, "
        "an accepted loanword, or a concise natural paraphrase.",
        "- If 'ctx' key present: those are preceding context only — do NOT translate them",
        "- Output ONLY the translated text — no notes, no explanations",
        "",
        "## CONCRETE EXAMPLES — CORRECT vs WRONG",
        "  'IT'S A DETONATOR.' → CORRECT: 'BU BİR DETONATÖR.' | WRONG: 'BU BİR DÜRTÜKLEYİCİ.'",
        "  'WE'LL TALK, MAN.' → CORRECT: 'KONUŞURUZ, DOSTUM.' | WRONG: 'KONUŞURUZ, KİMSE.'",
        "  'MY GIRLFRIEND' → CORRECT: 'SEVGİLİM' | WRONG: 'SEVERİM' (wrong grammar)",
        "  'BAT WINGS' → CORRECT: 'YARASA KANATLARI' | WRONG: 'YUSUFÇUK KANATLARI'",
        "  'SHE HAS A LION'S BODY.' → CORRECT: 'ASLAN BEDENİ VAR.' | WRONG: hallucinated text",
        "  'KNOCK KNOCK.' (door) → CORRECT: 'TOK TOK.' | WRONG: 'KAPİ KİM?' (that is the reply)",
        "  'YES, SIR.' → CORRECT: 'EVET, EFENDİM.' | WRONG: 'EVET, BAY.'",
        "",
        "## IDIOM & REGISTER TRAPS — translate the MEANING, never word-for-word",
        "  Archaic/poetic English MUST be translated: 'ye'→'ey'/'siz', 'thee/thou'→'sen'",
        "    'look upon my works, ye mighty' → 'eserlerime bakın, ey ulular' | WRONG: 'ye büyükler'",
        "  Exclamation idioms → natural Turkish exclamation, NOT a literal proper-noun:",
        "    'Great Scott!' → 'Vay canına!'/'Aman Tanrım!' | WRONG: 'Büyük Scott!'",
        "    'Holy smokes!' → 'Vay be!'; 'Geez/Jeez' → 'Off ya'/'Tanrım'",
        "  '-ass' is an INTENSIFIER (kocaman/baya), NOT sexual:",
        "    'big-ass door' → 'koca mı koca kapı' | WRONG: 'koca sikli kapı' (vulgar & wrong)",
        "  Figurative business idioms → meaning: 'bottom line' (profit) → 'kâr hanesi'/'kâr', WRONG: 'alt çizgi'",
        "  Known songs/rhymes use their familiar Turkish form:",
        "    'Row, row, row your boat' → 'Kürek çek, kürek çek...' | WRONG: 'Küre küre' ('row'=kürek çekmek)",
        "  Lines marked with ♪/♫ (or clearly sung) are LYRICS: translate for MEANING with natural, rhythmic "
        "Turkish — never warp meaning to force a rhyme; KEEP the ♪/♫ markers; do NOT inject colloquial markers "
        "(yani/işte/ya) into sung lines.",
        "",
        "## TURKISH SYNTAX & FLOW",
        "- Turkish is SOV — let the finite verb fall at the clause end; do NOT carry English S-V-O order when it yields stilted Turkish.",
        "- AVOID premature verb closure (erken yüklem kapanması) on cross-cue sentences. If a sentence continues in the next block, do NOT write a finished Turkish verb in the current block (e.g. do NOT translate 'Throughout history, humanity has struggled / with fears of Armageddon' as 'Tarih boyunca insanlık boğuştu, / Armageddon korkularıyla'). Instead, delay the verb to the end of the sentence or keep the sentence open using Turkish relative clauses, participles, or conjunctions.",
        "- Subtitle Sentence Splitting & Info Flow: When a single sentence spans across multiple contiguous subtitle blocks:",
        "  * If they are close in time (dialogue flows naturally), prioritize natural Turkish word order (SOV). It is preferred to shift information across boundaries (e.g. putting the dependent clause 'Yağmur yağdığı için' in the first subtitle, and the verb 'markete gittim' in the second) to keep the Turkish flow smooth and standard.",
        "  * If there is a noticeable time gap (> 1.5 seconds) between the subtitles, try to keep the meaning of each block self-contained. In this case, you may use natural-sounding inverted sentences (devrik cümle) or conjunctions ('çünkü', 'fakat') to prevent displaying translations of future speech too early.",
        "- English subordinate clauses ('when/because/after X, Y') usually collapse into ONE Turkish clause via "
        "a converb/participle: 'When he arrived, she left' → 'O gelince kadın gitti' (NOT two sentences).",
        "- Pro-drop: omit subject pronouns the verb ending already carries ('I'm going'→'Gidiyorum', not "
        "'Ben gidiyorum') unless the pronoun is contrastive/emphatic.",
        "- Dummy 'it' (weather/time/existential) has NO Turkish subject: 'It's raining'→'Yağmur yağıyor', "
        "'It's three o'clock'→'Saat üç' — never 'O yağıyor'.",
        "",
        f"## {register.upper()} REGISTER GUIDANCE",
    ] + _REGISTER_GUIDANCE[register].splitlines()

    # ── Profanity level ───────────────────────────────────────────────────────
    parts.append("")
    parts.extend(_PROFANITY_RULES.get(profanity, _PROFANITY_RULES["Orta"]))

    # ── Transliteration guard (critical) ─────────────────────────────────────
    parts += [
        "",
        "## TRANSLITERATION GUARD — CRITICAL",
        f"NEVER leave English slang/profanity untranslated in {tgt_lang}:",
        "  ass / ass- → göt, kıç  (NEVER write 'ass' or 'assını')",
        "  shit / shitting → bok, sıçmak  (NEVER write 'shit')",
        "  fuck / fucking → sik-, orospu çocuğu  (NEVER write 'fuck')",
        "  damn → kahretsin, lanet  (NEVER write 'damn')",
        "  hell → cehennem, kahretsin  (NEVER write 'hell')",
        "  bitch → orospu, kaltak, it  (NEVER write 'bitch')",
        "  crap → bok, saçmalık  (NEVER write 'crap')",
        "Scan your output: an untranslated English SLANG word, profanity, or everyday word is an error. "
        "(Proper nouns, brand/character names, and accepted loanwords/technical terms — 'detonatör', 'robot', "
        "'laser', 'online' — are NOT errors.)",
    ]

    # ── Pronoun/address map (Turkish sen/siz) ────────────────────────────────
    if pronoun_map:
        parts += [
            "",
            "## TURKISH ADDRESS RULES (sen / siz)",
            "Use these address forms consistently throughout the translation:",
        ]
        for pair, form in pronoun_map.items():
            parts.append(f"  {pair}: {form}")

    # ── Natural speech markers (not for documentary) ──────────────────────────
    if register != "documentary":
        parts += [
            "",
            "## NATURAL TURKISH SPEECH MARKERS",
            "Use these naturally where they genuinely fit — do NOT force them into every line:",
            '- Emphasis/filler: "yani", "işte", "zaten", "ya"',
            '- Surprise/reaction: "aa", "of", "vay be", "ya ne biçim"',
            '- Casual assent: "tamam", "anladım", "olur", "peki"',
            "- Only insert when a native speaker would naturally say it there",
            '- Subtractive too: English discourse markers map selectively — "well"→şey/yani or nothing, '
            '"you know"→usually nothing or işte, "I mean"→yani, "like"→usually nothing. The yes/no question '
            'particle "mi/mı/mu/mü" is REQUIRED for evet/hayır questions but must NOT be added to wh-questions '
            "(kim/ne/nerede/niye/nasıl already mark them).",
        ]

    return "\n".join(parts)


# ── Native Okuyucu Refleks Pass ──────────────────────────────────────────────

def native_reader_pass(
    tr_blocks: list,
    helper_api_key: str,
    helper_url: str = "https://api.openai.com/v1",
    helper_model: str = "gpt-5.4-mini",
    tgt_lang: str = "Turkish",
    log_fn=None,
    analysis_result=None,  # Optional: (context, char_examples, pronoun_map, ...) tuple
    token_callback=None,
    src_map: dict = None,
) -> list:
    """Native reader reflex pass — Helper reads translated subtitles as a native viewer
    and naturally rewrites lines that 'sound translated'.

    Distinct from polish_pass (fixes literalism) and critic_pass (fixes register errors).
    This pass targets: awkward word order, unnatural idiom rendering, un-native phrasing
    that is technically correct but sounds foreign.

    Args:
        tr_blocks: list of (idx, ts, text) translated subtitle blocks
        analysis_result: Optional tuple from analyze_with_helper for context injection
        token_callback: Optional callable(token_count) for updating token statistics

    Returns modified tr_blocks list with naturalness improvements applied.
    """
    if not tr_blocks:
        return tr_blocks

    CHUNK_SIZE = 150
    MAX_FIX_RATIO = 0.20

    try:
        from openai import OpenAI
        client = OpenAI(api_key=helper_api_key, base_url=helper_url)
    except Exception as e:
        if log_fn:
            log_fn(f"Native Pass bağlantı hatası: {e}", "err")
        return tr_blocks

    # Build context info for the prompt
    context_info = ""
    if analysis_result:
        try:
            ctx = analysis_result[0]  # ContextMemory
            parts_ctx = []
            if ctx.tone:
                parts_ctx.append(f"Tone: {ctx.tone}")
            if ctx.setting:
                parts_ctx.append(f"Setting: {ctx.setting}")
            character_styles = analysis_result[3] if len(analysis_result) > 3 else None
            if character_styles:
                style_lines = []
                for name, info in list(character_styles.items())[:5]:
                    reg = info.get("register", "") if isinstance(info, dict) else ""
                    if reg:
                        style_lines.append(f"{name}: {reg}")
                if style_lines:
                    parts_ctx.append("Characters: " + ", ".join(style_lines))
            if parts_ctx:
                context_info = "\nContent context: " + " | ".join(parts_ctx)
            pronoun_map = analysis_result[2] if len(analysis_result) > 2 else None
            if isinstance(pronoun_map, dict) and pronoun_map:
                context_info += "\nsen/siz (koru): " + "; ".join(
                    f"{k}={v}" for k, v in list(pronoun_map.items())[:6])
            idiom_map = analysis_result[5] if len(analysis_result) > 5 else None
            if isinstance(idiom_map, dict) and idiom_map:
                context_info += ("\nŞu deyimleri doğal Türkçe karşılığıyla oku (literal DEĞİL): "
                                 + "; ".join(f"{k}→{v}" for k, v in list(idiom_map.items())[:8]))
        except Exception:
            pass

    result = list(tr_blocks)
    idx_to_pos = {str(b[0]): i for i, b in enumerate(result)}
    
    # Reconstruct mock cues for fragment tagging if src_map is provided
    frag_tags = {}
    if src_map:
        class MockCue:
            def __init__(self, index, text):
                self.index = index
                self.text = text
        mock_cues = []
        for idx, ts, text in result:
            src_t = src_map.get(str(idx), "")
            mock_cues.append(MockCue(idx, src_t))
        try:
            frag_tags = _tag_fragments(mock_cues)
        except Exception:
            frag_tags = {}
            
    eligible_count = sum(1 for _, _, text in result if text and text != "[HATA]")
    max_total_fixes = max(1, math.ceil(eligible_count * MAX_FIX_RATIO)) if eligible_count else 0
    total_fixed = 0
    total_rejected = 0
    total_cap_rejected = 0
    reject_reasons = {}
    total_chunks = math.ceil(len(result) / CHUNK_SIZE)

    for chunk_i in range(0, len(result), CHUNK_SIZE):
        chunk = result[chunk_i:chunk_i + CHUNK_SIZE]
        chunk_ids = {str(idx) for idx, _ts, _text in chunk}
        chunk_num = chunk_i // CHUNK_SIZE + 1

        if log_fn:
            log_fn(f"Native Pass {chunk_num}/{total_chunks} ({len(chunk)} satır)...", "info")

        items = []
        for idx, ts, text in chunk:
            if not text or text == "[HATA]":
                continue
            it = {"id": str(idx), "tr": text}
            if src_map:
                src_t = src_map.get(str(idx))
                if src_t:
                    it["en"] = src_t
                tag = frag_tags.get(idx, "none")
                if tag != "none":
                    it["frag"] = tag
            items.append(it)
        if not items:
            continue

        # Build ctx/next_ctx for context continuity
        ctx_lines = []
        if chunk_i > 0:
            ctx_start = max(0, (chunk_i // CHUNK_SIZE) * CHUNK_SIZE - CHUNK_SIZE)
            for prev in result[ctx_start:ctx_start + CHUNK_SIZE]:
                if prev[2] and prev[2] != "[HATA]":
                    ctx_lines.append(prev[2])
        next_lines = []
        nxt_start = chunk_i + CHUNK_SIZE
        if nxt_start < len(result):
            for nxt in result[nxt_start:min(nxt_start + CHUNK_SIZE, len(result))]:
                if nxt[2] and nxt[2] != "[HATA]":
                    next_lines.append(nxt[2])

        payload = {"tr": items}
        if ctx_lines:
            payload["ctx"] = ctx_lines[-12:]
        if next_lines:
            payload["next_ctx"] = next_lines[:8]
        payload_json = json.dumps(payload, ensure_ascii=False)

        frag_instruction = ""
        if src_map:
            frag_instruction = (
                "- Cümle Akışı (Söz Dizimi): Eğer ardışık satırlarda 'frag' alanı varsa ('start', 'mid', 'end'), bu satırlar tek bir İngilizce cümlenin parçalarıdır. Türkçe çevirilerde İngilizce söz dizimi (SVO) sırası nedeniyle bilgi akışının 'sondan başa' gidiyor gibi durmasını (örn. erken yüklem kapanıp nesnelerin arkadan gelmesini) engelle. Bilgileri/kelimeleri bu satırlar arasında Türkçe kurallarına göre (SOV) yeniden dağıt. Cümle en son satırda ('end') yüklemle bitsin, önceki satırlar ('start', 'mid') Türkçe'de devam bekleyen yapıda olsun.\n"
                "  Örnek:\n"
                "    Girdi: \n"
                "      id: 2, en: Throughout history, humanity has struggled, tr: Tarih boyunca insanlık boğuştu, frag: start\n"
                "      id: 3, en: with fears of Armageddon, tr: Armageddon korkularıyla, frag: end\n"
                "    Çıktı (fixed):\n"
                "      id: 2: Tarih boyunca insanlık,\n"
                "      id: 3: Armageddon korkularıyla boğuştu.\n"
            )

        prompt = (
            f"Sen Türkiye'de doğup büyümüş, sadece Türkçe okuyan bir film izleyicisisin.{context_info}\n"
            f"Aşağıdaki altyazıları oku. Bazıları 'çevrilmiş gibi' duruyor — yani söz dizimi yapay, "
            f"deyim akışı bozuk veya hiçbir Türk'ün söylemeyeceği kelime kalıpları var.\n\n"
            f"SADECE doğal olmayan satırları düzelt:\n"
            f"- Doğal Türkçe konuşma sesine kavuştur\n"
            f"- Anlamı değiştirme, sadece doğallığı artır\n"
            f"- Zaten iyi olan satırları değiştirme\n"
            f"{frag_instruction}\n"
            f"En fazla {max_total_fixes} satır düzelt (yaklaşık %20 sınırı). "
            f"Sadece en emin olduğun satırları seç.\n\n"
            f"Altyazılar:\n{payload_json}\n\n"
            f'JSON array döndür: [{{"id":"N","fixed":"..."}}] — sadece düzeltilenleri.\n'
            f"Hiç düzeltme yoksa [] döndür."
        )

        try:
            resp = _safe_chat_create(
                client,
                model=helper_model,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=len(chunk) * 80,
                temperature=0.2,
            )
            if token_callback and resp.usage:
                tot, cached = _get_usage_details(resp.usage)
                try:
                    token_callback(tot, cached=cached)
                except TypeError:
                    token_callback(tot)
            content = (resp.choices[0].message.content or "").strip() if resp.choices else ""
            if not content:
                continue
            content = _extract_json_array(content)
            if not content:
                continue
            fixes = json.loads(content)
            if not isinstance(fixes, list):
                continue
            chunk_pos_by_id = {str(idx): pos for pos, (idx, _ts, _text) in enumerate(chunk)}
            for fix in fixes:
                if not isinstance(fix, dict):
                    continue
                fid   = str(fix.get("id", ""))
                ftext = fix.get("fixed", "")
                if fid and ftext and fid in chunk_ids and fid in idx_to_pos:
                    if total_fixed >= max_total_fixes:
                        total_cap_rejected += 1
                        continue
                    pos = idx_to_pos[fid]
                    old_idx, old_ts, old_text = result[pos]
                    source_text = src_map.get(fid, "") if src_map else ""
                    chunk_pos = chunk_pos_by_id.get(fid)
                    neighbor_texts = []
                    if chunk_pos is not None:
                        start = max(0, chunk_pos - 2)
                        end = min(len(chunk), chunk_pos + 3)
                        neighbor_texts = [chunk[i][2] for i in range(start, end) if i != chunk_pos]
                    ok, reason = validate_polish_candidate(
                        old_text,
                        ftext,
                        source_text,
                        neighbor_texts=neighbor_texts,
                        fragment_tag=frag_tags.get(old_idx, "none"),
                    )
                    if not ok:
                        total_rejected += 1
                        reject_reasons[reason] = reject_reasons.get(reason, 0) + 1
                        continue
                    result[pos] = (old_idx, old_ts, ftext)
                    total_fixed += 1
        except Exception as chunk_err:
            if log_fn:
                log_fn(f"Native Pass chunk {chunk_num} hatası: {chunk_err}", "warn")
            continue

    if log_fn:
        if total_rejected:
            reason_txt = ", ".join(f"{name}: {count}" for name, count in sorted(reject_reasons.items()))
            log_fn(f"Native Pass: {total_rejected} öneri güvenlik filtresinden döndü ({reason_txt})", "warn")
        if total_cap_rejected:
            log_fn(f"Native Pass: {total_cap_rejected} öneri %20 sınırı nedeniyle atlandı", "warn")
        if total_fixed:
            log_fn(f"Native Pass: {total_fixed} satır doğallaştırıldı ✓", "ok")
        else:
            log_fn("Native Pass: tüm satırlar zaten doğal ✓", "ok")

    return result


# ── Okuma hızı sıkıştırma (reading-speed condensation) ────────────────────────

def _block_duration(ts: str) -> float:
    """'HH:MM:SS,mmm --> HH:MM:SS,mmm' biçiminden süreyi (saniye) döner."""
    try:
        start_s, end_s = ts.split('-->')
        return _ts_to_sec(end_s.strip()) - _ts_to_sec(start_s.strip())
    except Exception:
        return 0.0


def find_fast_lines(tr_blocks: list, cps_limit: float = 21.0) -> list:
    """CPS (karakter/saniye) sınırını aşan satırları döner.
    Returns: [(id_str, text, char_budget), ...]
    char_budget = okunabilir uzunluk hedefi (cps_limit * süre).
    Saf fonksiyon — API çağrısı yok, test edilebilir."""
    fast = []
    for idx, ts, text in tr_blocks:
        if not text or text.strip() == "[HATA]":
            continue
        dur = _block_duration(ts)
        if dur <= 0:
            continue
        visible = len(text.replace('\n', ' ').strip())
        if visible / dur > cps_limit:
            budget = max(int(cps_limit * dur), 1)
            fast.append((str(idx), text, budget))
    return fast


def condense_fast_lines(
    tr_blocks: list,
    helper_api_key: str,
    helper_url: str = "https://api.openai.com/v1",
    helper_model: str = "gpt-5.4-mini",
    tgt_lang: str = "Turkish",
    cps_limit: float = 21.0,
    log_fn=None,
    token_callback=None,
    src_map: dict = None,
) -> tuple:
    """Okuma hızı sınırını aşan satırları, anlamı ve tonu koruyarak kısaltır.
    Profesyonel altyazıcının 'ekrana sığdırma' refleksini taklit eder.
    Returns (corrected_tr_blocks, n_condensed)."""
    if not tr_blocks:
        return tr_blocks, 0

    fast = find_fast_lines(tr_blocks, cps_limit)
    if not fast:
        if log_fn:
            log_fn("Okuma hızı: tüm satırlar sınır içinde ✓", "ok")
        return tr_blocks, 0

    if log_fn:
        log_fn(f"Okuma hızı: {len(fast)} satır çok hızlı (>{cps_limit:.0f} kar/sn) — kısaltılıyor...", "info")

    try:
        from openai import OpenAI
        client = OpenAI(api_key=helper_api_key, base_url=helper_url)
    except Exception as e:
        if log_fn:
            log_fn(f"Kısaltma pass bağlantı hatası: {e}", "err")
        return tr_blocks, 0

    result = list(tr_blocks)
    idx_to_pos = {str(b[0]): i for i, b in enumerate(result)}
    CHUNK_SIZE = 40
    total = 0
    reject_counts = {}

    for chunk_i in range(0, len(fast), CHUNK_SIZE):
        chunk = fast[chunk_i:chunk_i + CHUNK_SIZE]
        items = [{"id": fid, "text": txt, "max_chars": budget}
                 for fid, txt, budget in chunk]
        if src_map:
            for it in items:
                en = src_map.get(it["id"], "")
                if en:
                    it["en"] = en
        prompt = (f"Sen profesyonel bir altyazı editörüsün. Aşağıdaki {tgt_lang} altyazı satırları "
                  f"ekranda kaldıkları süreye göre okunamayacak kadar uzun.\n"
                  f"Her satırı, ANLAMI ve TONU koruyarak 'max_chars' karakter sınırına olabildiğince "
                  f"yaklaşacak şekilde KISALT.\n"
                  f"Kurallar:\n"
                  f"- Aynı dilde ({tgt_lang}) kal — yeniden çeviri yapma\n"
                  f"- Kaynak metin ('en') varsa, kısaltma İngilizcedeki anlamla birebir uyuşmalı\n"
                  f"- Gereksiz/tekrar eden kelimeleri at; doğal ve akıcı kalsın\n"
                  f"- Anlamı ASLA değiştirme, bilgi atlatma\n"
                  f"- <i>, <b> gibi etiketleri ve [SFX] etiketlerini koru\n"
                  f"- Bir satır anlamı bozmadan kısalamıyorsa olduğu gibi bırak (listeye ekleme)\n\n"
                  f"Satırlar:\n{json.dumps(items, ensure_ascii=False)}\n\n"
                  f"JSON array döndür: [{{\"id\":\"N\",\"short\":\"...\"}}] — yalnızca kısalttıklarını.")
        try:
            resp = _safe_chat_create(
                client,
                model=helper_model,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=len(chunk) * 60,
                temperature=0.2,
            )
            if token_callback and resp.usage:
                tot, cached = _get_usage_details(resp.usage)
                try:
                    token_callback(tot, cached=cached)
                except TypeError:
                    token_callback(tot)
            content = (resp.choices[0].message.content or "").strip() if resp.choices else ""
            if not content:
                continue
            content = _extract_json_array(content)
            if not content:
                continue
            fixes = json.loads(content)
            if not isinstance(fixes, list):
                continue
            for fix in fixes:
                if not isinstance(fix, dict):
                    continue
                fid   = str(fix.get("id", ""))
                short = (fix.get("short") or "").strip()
                if not fid or not short or fid not in idx_to_pos:
                    continue
                pos = idx_to_pos[fid]
                old_idx, old_ts, old_text = result[pos]
                # Yalnızca gerçekten kısaldıysa uygula — uzatma/aynı kalma engellenir
                if len(short.replace('\n', ' ')) < len(old_text.replace('\n', ' ')):
                    # CPS kontrolü: kısaltma sonrası hala limitin altında mı?
                    old_cps = cps(old_text, _block_duration(old_ts))
                    new_cps = cps(short, _block_duration(old_ts))
                    if new_cps < old_cps and new_cps <= max(cps_limit, CPS_WARN_LIMIT):
                        en_src = src_map.get(fid, "") if src_map else ""
                        ok, reason = validate_condense_candidate(old_text, short, en_src)
                        if not ok:
                            reject_counts[reason] = reject_counts.get(reason, 0) + 1
                            continue
                        result[pos] = (old_idx, old_ts, short)
                        total += 1
        except Exception as e:
            if log_fn:
                log_fn(f"Kısaltma chunk hatası: {e}", "warn")
            continue

    if log_fn:
        if total:
            log_fn(f"Okuma hızı: {total} satır kısaltıldı ✓", "ok")
        else:
            log_fn("Okuma hızı: uygun kısaltma bulunamadı", "ok")
        if reject_counts:
            log_fn(f"Kısaltma: {sum(reject_counts.values())} öneri güvenlik filtresinden döndü "
                   f"({', '.join(f'{k}:{v}' for k, v in sorted(reject_counts.items()))})", "warn")
    return result, total


# ── Kalite kontrolü ───────────────────────────────────────────────────────────

def back_translation_check(
    src_map: dict,
    tr_blocks: list,
    api_key: str,
    base_url: str = "https://api.openai.com/v1",
    model: str = "gpt-5.4-mini",
    src_lang: str = "English",
    tgt_lang: str = "Turkish",
    log_fn=None,
    token_callback=None,
    chunk_size: int = 40,
) -> list:
    """Geri Ã§eviri anlam kontrolÃ¼ (RAPOR-ONLY â€” Ã§eviriyi DEÄÄ°ÅTÄ°RMEZ).

    İki aşamalı: aynı yönde LLM-yargısının kaçırdığı gerçek yanlış çevirileri yakalar.
      Stage 1 (kör): {tgt_lang} çevirileri, kaynağı GÖRMEDEN {src_lang}'a geri çevrilir.
      Stage 2: geri çeviri orijinal kaynakla karşılaştırılır; YALNIZCA sert anlam
      sapmaları (negasyon ters dönmesi, yanlış özne/nesne/kişi, yanlış sayı/miktar,
      deÄŸiÅŸen olgu, atlanan/eklenen anlam) iÅŸaretlenir â€” Ã¼slup/eÅŸanlam/sÃ¶zdizimi DEÄÄ°L.

    Dönüş: [{"idx","src","tr","back","reason"}] (yalnız işaretlenenler)."""
    try:
        from openai import OpenAI
        client = OpenAI(api_key=api_key, base_url=base_url)
    except Exception as e:
        if log_fn:
            log_fn(f"Geri çeviri: bağlantı hatası: {e}", "err")
        return []

    items = []
    for idx, ts, text in tr_blocks:
        sidx = str(idx)
        tr  = (text or "").strip()
        src = (src_map.get(sidx, "") or "").strip()
        if not tr or not src or tr == "[HATA]" or tr.startswith("[HATA"):
            continue
        # çok kısa / yalnız SFX/etiket/♪ satırlarını atla (sapma yargısı anlamsız)
        core = re.sub(r"\[[^\]]*\]|♪|♫|<[^>]+>", "", tr).strip()
        if len(core) < 12:
            continue
        items.append({"idx": sidx, "src": src, "tr": tr})

    if not items:
        return []
    if log_fn:
        log_fn(f"Geri çeviri anlam kontrolü: {len(items)} satır incelenecek...", "info")

    flagged = []
    for start in range(0, len(items), chunk_size):
        chunk = items[start:start + chunk_size]

        # ── Stage 1: kör geri çeviri (kaynak GÖSTERİLMEZ) ──
        bt_payload = [{"id": it["idx"], "tr": it["tr"]} for it in chunk]
        bt_prompt = (
            f"Translate each {tgt_lang} subtitle line below back into natural {src_lang}. "
            f"Translate ONLY what is written — do NOT add, omit, 'correct', or infer meaning. "
            f"Return ONLY a JSON array [{{\"id\":\"N\",\"en\":\"...\"}}].\n\n"
            f"{json.dumps(bt_payload, ensure_ascii=False)}"
        )
        back_map = {}
        try:
            resp = _safe_chat_create(
                client, model=model,
                messages=[{"role": "user", "content": bt_prompt}],
                max_tokens=len(chunk) * 60 + 300, temperature=0.0,
            )
            if token_callback and getattr(resp, "usage", None):
                tot, cached = _get_usage_details(resp.usage)
                try:
                    token_callback(tot, cached=cached)
                except TypeError:
                    token_callback(tot)
            content = (resp.choices[0].message.content or "").strip() if resp.choices else ""
            for o in json.loads(_extract_json_array(content) or "[]"):
                if isinstance(o, dict) and o.get("id") is not None:
                    back_map[str(o["id"])] = str(o.get("en", "")).strip()
        except Exception as e:
            if log_fn:
                log_fn(f"Geri çeviri stage-1 chunk hatası: {e}", "warn")
            continue

        # ── Stage 2: kaynak vs geri-çeviri sapma yargısı (muhafazakâr) ──
        cmp_payload = [{"id": it["idx"], "src": it["src"], "back": back_map.get(it["idx"], "")}
                       for it in chunk if back_map.get(it["idx"])]
        if not cmp_payload:
            continue
        cmp_prompt = (
            f"You compare an ORIGINAL {src_lang} subtitle line ('src') with a blind "
            f"back-translation ('back') of its {tgt_lang} translation. Flag a line ONLY when "
            f"'back' reveals a HARD meaning error in the translation: negation flipped, wrong "
            f"subject/object/person, wrong number/quantity, a changed fact, or clearly "
            f"omitted/added meaning. Do NOT flag style, synonyms, word order, register, tense "
            f"nuance, or minor paraphrase. Be conservative — when unsure, do NOT flag.\n"
            f"Return ONLY a JSON array of flagged items [{{\"id\":\"N\",\"reason\":\"short reason\"}}]; "
            f"return [] if none.\n\n{json.dumps(cmp_payload, ensure_ascii=False)}"
        )
        try:
            resp = _safe_chat_create(
                client, model=model,
                messages=[{"role": "user", "content": cmp_prompt}],
                max_tokens=len(chunk) * 40 + 300, temperature=0.0,
            )
            if token_callback and getattr(resp, "usage", None):
                tot, cached = _get_usage_details(resp.usage)
                try:
                    token_callback(tot, cached=cached)
                except TypeError:
                    token_callback(tot)
            content = (resp.choices[0].message.content or "").strip() if resp.choices else ""
            by_idx = {it["idx"]: it for it in chunk}
            for o in json.loads(_extract_json_array(content) or "[]"):
                if not isinstance(o, dict):
                    continue
                fid = str(o.get("id", ""))
                reason = str(o.get("reason", "")).strip()
                if fid in by_idx and reason:
                    it = by_idx[fid]
                    flagged.append({"idx": fid, "src": it["src"], "tr": it["tr"],
                                    "back": back_map.get(fid, ""), "reason": reason})
        except Exception as e:
            if log_fn:
                log_fn(f"Geri çeviri stage-2 chunk hatası: {e}", "warn")
            continue

    if log_fn:
        log_fn(f"Geri çeviri: {len(flagged)} şüpheli satır işaretlendi (çeviri değiştirilMEDİ)",
               "warn" if flagged else "ok")
    return flagged


def quality_check_with_helper(
    cues: list,
    tr_blocks: list,
    helper_api_key: str,
    helper_url: str = "https://api.openai.com/v1",
    helper_model: str = "gpt-5.4-mini",
    tgt_lang: str = "Turkish",
    log_fn=None,
    analysis_result=None,  # Optional: (ContextMemory, char_examples, pronoun_map)
) -> list:
    """
    Compare original cues with translated blocks.
    Returns list of issues: [{id, original, current, problem, suggestion, severity}]

    Args:
        analysis_result: Optional tuple of (ContextMemory, char_examples_dict, pronoun_map)
            from analyze_with_helper() to provide context injection for better QC.
    """
    try:
        from openai import OpenAI
        client = OpenAI(api_key=helper_api_key, base_url=helper_url)

        QC_CHUNK = 200  # lines per API call — Helper handles this comfortably
        tr_dict = {str(idx): text for idx, ts, text in tr_blocks}

        all_pairs = []
        for c in cues:
            if hasattr(c, "text"):
                cue_id, cue_text = c.index, c.text
            else:
                cue_id, cue_text = c[0], c[2]
            tr_text = tr_dict.get(str(cue_id), "")
            if tr_text and tr_text != "[HATA]":
                all_pairs.append({"id": str(cue_id), "orig": cue_text, "tr": tr_text})

        if not all_pairs:
            return []

        total_chunks = math.ceil(len(all_pairs) / QC_CHUNK)
        if log_fn:
            log_fn(f"Helper QC: {len(all_pairs)} satır, {total_chunks} chunk...", "info")

        # Build context-aware prompt
        context_info = ""
        if analysis_result:
            try:
                context, char_examples, pronoun_map = analysis_result[:3]
                character_styles = analysis_result[3] if len(analysis_result) > 3 else None
                context_parts = []

                if context.tone:
                    context_parts.append(f"Tone/Style: {context.tone}")

                if context.setting:
                    context_parts.append(f"Setting: {context.setting}")

                if context.characters:
                    char_names = ", ".join(c.name for c in context.characters[:5])
                    context_parts.append(f"Characters: {char_names}" +
                                        ("..." if len(context.characters) > 5 else ""))

                if isinstance(pronoun_map, dict) and pronoun_map:
                    pairs = ", ".join(f"{k}={v}" for k, v in list(pronoun_map.items())[:10])
                    context_parts.append(f"Register patterns (sen/siz): {pairs}")

                if character_styles:
                    style_lines = []
                    for name, info in list(character_styles.items())[:8]:
                        reg = info.get("register", "") if isinstance(info, dict) else ""
                        if reg:
                            style_lines.append(f"  {name}: {reg}")
                    if style_lines:
                        context_parts.append("Character voices:\n" + "\n".join(style_lines))

                safe_terms = sanitize_glossary_for_turkish(
                    getattr(context, "recurring_terms", {}), target_language=tgt_lang, log_fn=log_fn
                )
                if safe_terms:
                    terms = list(safe_terms.keys())[:8]
                    terms_str = ", ".join(f"{t}→{safe_terms[t]}" for t in terms)
                    context_parts.append(f"Key terms: {terms_str}" +
                                        ("..." if len(safe_terms) > 8 else ""))

                if context_parts:
                    context_info = "\n\nContent Context:\n" + "\n".join(context_parts)
            except Exception as e:
                if log_fn:
                    log_fn(f"QC context injection hatası (ignored): {e}", "warn")

        all_issues = []

        for chunk_i, cs in enumerate(range(0, len(all_pairs), QC_CHUNK)):
            chunk = all_pairs[cs:cs + QC_CHUNK]
            chunk_by_id = {pair["id"]: pair for pair in chunk}
            chunk_num = chunk_i + 1
            if log_fn:
                log_fn(f"QC chunk {chunk_num}/{total_chunks} ({len(chunk)} satır)...", "info")

            pairs_json = json.dumps(chunk, ensure_ascii=False)

            # Turkish-specific error patterns
            turkish_errors = (
                "\n\nTurkish-Specific Issues to Check:\n"
                "1. Sen/Siz Register Mismatch: Wrong formal/informal pronoun (sen vs siz) for character relationships\n"
                "2. Literalism: Mechanical word-for-word translation instead of natural Turkish phrase\n"
                "3. Unnecessary Particles: Over-use of 'mi', 'mu', 'de', 'da', or 'ki' where Turkish doesn't need them\n"
                "4. Verbal Noun Abuse: '-ıyor' (present continuous) where gerund '-arak' or '-ince' is more natural\n"
                "5. Meaning Shift: Content missing, added, or significantly altered from original\n"
                "6. Profanity Register: Wrong level of profanity for scene tone (too mild/harsh)\n"
                "7. Unnatural Phrasing: Sounds awkward or un-native (violates Turkish word order or flow)"
            )

            prompt = (
                f"You are a professional Turkish subtitle translation reviewer. "
                f"Review these subtitle pairs (original → Turkish translation).{context_info}\n\n"
                f"{turkish_errors}\n\n"
                f"Subtitle pairs:\n{pairs_json}\n\n"
                f'Return JSON: {{"issues": [{{"id": "5", "original": "...", '
                f'"current": "...", "problem": "Sen/Siz Register Mismatch", '
                f'"suggestion": "...", "severity": "high|med|low"}}]}}\n'
                f"Use severity=high for meaning loss, missing content, wrong register, names/numbers/tags, "
                f"or any fix that needs human judgment. Use med/low only for safe, local naturalness fixes.\n"
                f"Return empty issues array if no significant problems found. "
                f"Only flag REAL problems — do not nitpick stylistic choices unless they violate Turkish conventions."
            )

            try:
                resp = _safe_chat_create(
                    client,
                    model=helper_model,
                    messages=[{"role": "user", "content": prompt}],
                    max_tokens=12000,   # 3000 yetersizdi: çok hatalı dosyalarda JSON kesilip TÜM sorunlar düşüyordu
                    temperature=0.2,
                )
                content = (resp.choices[0].message.content or "").strip() if resp.choices else ""
                if not content:
                    if log_fn:
                        log_fn(f"QC chunk {chunk_num}: boş yanıt, atlanıyor", "warn")
                    continue
                if content.startswith("```"):
                    content = "\n".join(content.split("\n")[1:]).rsplit("```", 1)[0].strip()
                if not content:
                    continue
                data = _extract_json_object(content)   # prose önsöz/kod-çiti toleransı
                raw_issues = data.get("issues", []) if isinstance(data, dict) else []
                chunk_issues = []
                for raw_issue in raw_issues if isinstance(raw_issues, list) else []:
                    if not isinstance(raw_issue, dict):
                        continue
                    issue_id = str(raw_issue.get("id", ""))
                    expected = chunk_by_id.get(issue_id)
                    if not expected:
                        continue
                    if (_normalize_qc_match_text(raw_issue.get("current"))
                            != _normalize_qc_match_text(expected["tr"])):
                        continue
                    issue = dict(raw_issue)
                    issue["id"] = issue_id
                    issue["original"] = expected["orig"]
                    issue["current"] = expected["tr"]
                    issue["severity"] = normalize_qc_severity(issue.get("severity"))
                    chunk_issues.append(issue)
                all_issues.extend(chunk_issues)
                if log_fn and chunk_issues:
                    log_fn(f"  QC chunk {chunk_num}: {len(chunk_issues)} sorun", "warn")
            except Exception as chunk_err:
                if log_fn:
                    log_fn(f"QC chunk {chunk_num} hatası: {chunk_err}", "err")
                continue

        if log_fn:
            if all_issues:
                log_fn(f"QC tamamlandı: {len(all_issues)} sorun bulundu", "warn")
            else:
                log_fn("QC tamamlandı: sorun bulunamadı ✓", "ok")
        return all_issues
    except json.JSONDecodeError as e:
        if log_fn:
            log_fn(f"QC JSON parse hatası: {e} — yanıt: {content[:200] if 'content' in dir() else '?'}", "err")
        return []
    except Exception as e:
        if log_fn:
            tb = traceback.format_exception(type(e), e, e.__traceback__)
            compact = "".join(tb[-2:]).strip().replace("\n", " | ")
            log_fn(f"QC hatası: {e} | {compact}", "err")
        return []


def normalize_qc_severity(value) -> str:
    """Normalize helper QC severity and fail closed for older/malformed responses."""
    sev = str(value or "").strip().lower()
    if sev in {"high", "med", "low"}:
        return sev
    if sev in {"medium", "moderate"}:
        return "med"
    return "high"


def _normalize_qc_match_text(value) -> str:
    if value is None:
        return ""
    return re.sub(r"\s+", " ", _clean_source_text(str(value))).strip().casefold()


def split_qc_issues_for_review(issues: list) -> tuple[list, list]:
    """Split QC issues into safe auto-fix candidates and manual-review issues."""
    auto_issues = []
    review_issues = []
    for raw_issue in issues or []:
        if not isinstance(raw_issue, dict):
            continue
        issue = dict(raw_issue)
        severity = normalize_qc_severity(issue.get("severity"))
        issue["severity"] = severity
        if severity in {"med", "low"}:
            ok, _reason = validate_polish_candidate(issue.get("current", ""), issue.get("suggestion", ""))
            if ok:
                auto_issues.append(issue)
                continue
        review_issues.append(issue)
    return auto_issues, review_issues


# ── Critic Pass ───────────────────────────────────────────────────────────────

# Local regex fixes — instant, no API call needed
_LOCAL_FIXES = [
    # English slang transliterations — most common mistakes
    (re.compile(r'\bmy ass\b',     re.I), 'benim götüm'),
    (re.compile(r'\basses\b',      re.I), 'götler'),
    (re.compile(r'\bass\b',        re.I), 'göt'),
    (re.compile(r'\basshole\b',    re.I), 'orospu çocuğu'),
    (re.compile(r'\bshit\b',       re.I), 'bok'),
    (re.compile(r'\bshitting\b',   re.I), 'sıçıyor'),
    (re.compile(r'\bbullshit\b',   re.I), 'saçmalık'),
    (re.compile(r'\bfuck\b',       re.I), 'sik'),
    (re.compile(r'\bfucking\b',    re.I), 'kahrolası'),
    (re.compile(r'\bfucked\b',     re.I), 'mahvolmuş'),
    (re.compile(r'\bdamn\b',       re.I), 'kahretsin'),
    (re.compile(r'\bdamned\b',     re.I), 'lanet'),
    (re.compile(r'\bhell\b',       re.I), 'cehennem'),
    (re.compile(r'\bbitch\b',      re.I), 'orospu'),
    (re.compile(r'\bcrap\b',       re.I), 'bok'),
    (re.compile(r'\bcrappy\b',     re.I), 'berbat'),
    (re.compile(r'\bpiss\b',       re.I), 'çiş'),
    (re.compile(r'\bpissed\b',     re.I), 'sinirli'),
    (re.compile(r'\bbastard\b',    re.I), 'piç'),
    (re.compile(r'\bscrew you\b',  re.I), 'defol'),
    (re.compile(r'\bscrew it\b',   re.I), 'bırak gitsin'),
    # Dutch residue that commonly leaks from NL subtitles and polish passes.
    (re.compile(r'\bmetafoor\b', re.I), 'metafor'),
    (re.compile(r'\bhoofse\s+(?:liefde|aşk)\b', re.I), 'saray aşkı'),
    (re.compile(r'\bthe\s+Laatste\s+Avondmaal\b', re.I), 'Son Akşam Yemeği'),
    (re.compile(r'\b(?:het|de)\s+Laatste\s+Avondmaal\b', re.I), 'Son Akşam Yemeği'),
    (re.compile(r"\b(?:het\s+)?Barre\s+Land['’]in\b", re.I), "Çorak Ülke'nin"),
    (re.compile(r"\b(?:het\s+)?Barre\s+Land['’]i\b", re.I), "Çorak Ülke'yi"),
    (re.compile(r'\b(?:het\s+)?Barre\s+Land\b', re.I), 'Çorak Ülke'),
    (re.compile(r'\bDe\s+Heilige\s+Graal\s+şatosu', re.I), 'Kutsal Kâse Şatosu'),
    (re.compile(r'\bDe\s+Heilige\s+Graal\b', re.I), 'Kutsal Kâse'),
    (re.compile(r'\bDe\s+Toverberg[’\']i\b', re.I), 'Büyülü Dağ’ı'),
    (re.compile(r'\bDe\s+Toverberg\b', re.I), 'Büyülü Dağ'),
    (
        re.compile(r'\bWereld\s+als\s+Wil\s+en\s+Voorstelling[’\']ını\b', re.I),
        'İrade ve Tasarım Olarak Dünya’sını',
    ),
    (
        re.compile(r'\bWereld\s+als\s+Wil\s+en\s+Voorstelling[’\']ıdır\b', re.I),
        'İrade ve Tasarım Olarak Dünya’sıdır',
    ),
    (re.compile(r'\bWereld\s+als\s+Wil\s+en\s+Voorstelling\b', re.I), 'İrade ve Tasarım Olarak Dünya'),
    (re.compile(r'\bmyt(?:le|e)\b', re.I), 'mit'),
    (re.compile(r'\bmytheyi\b', re.I), 'miti'),
    (re.compile(r'\bmythe\s+kurucu\b', re.I), 'mit kurucu'),
    (re.compile(r"queeste'ye", re.I), 'arayışa'),
    (re.compile(r"queeste'sine", re.I), 'arayışına'),
    (re.compile(r'\bqueeste\b', re.I), 'arayış'),
    (re.compile(r'\bnihai\s+zenginlik\b', re.I), 'nihai lütuf'),
    (re.compile(r'\bBu\s+zenginlik,', re.I), 'Bu lütuf,'),
    (re.compile(r'\bzenginlik\s+arayış', re.I), 'lütuf arayış'),
    # Typo: "evett" → "evet"
    (re.compile(r'\bevett\b', re.I), 'evet'),
    # Missing Turkish prefix: skelet/skeleti/skelette → iskelet/iskeleti/iskelette
    (re.compile(r'\bskelet(\w*)', re.I), r'iskelet\1'),
    # Technical term: psychochemical → psikokimyasal
    (re.compile(r'\bpsikokimyasal\b', re.I), 'psikokimyasal'),
    (re.compile(r'\bpsikokimyasallar\b', re.I), 'psikokimyasallar'),
    (re.compile(r'\bpsychochemical\b', re.I), 'psikokimyasal'),
    (re.compile(r'\bpsychochemicals\b', re.I), 'psikokimyasallar'),
    # Dotless-i fix: yasadıkları → yaşadıkları
    (re.compile(r'\byasadıkları\b', re.I), 'yaşadıkları'),
    (re.compile(r'\byasadığı\b', re.I), 'yaşadığı'),
    # Unnatural phrasing: "iyi olmayan muamele" → "kötü muamele"
    (re.compile(r'\biyi olmayan muamele\b', re.I), 'kötü muamele'),
    # ENT Turkic/source residue
    (re.compile(r'\bGULAKLA\b'), 'KULAKLA'),
    (re.compile(r'\bGULAGY\b'), 'KULAK'),
    (re.compile(r'\bGULAH\b'), 'KULAK'),
    (re.compile(r'\bGULAK\b'), 'KULAK'),
    (re.compile(r'\bBOKURDAKLA\b'), 'BOĞAZLA'),
    (re.compile(r'\bBOKURDAGLA\b'), 'BOĞAZLA'),
    (re.compile(r'\bBOGURDAKLA\b'), 'BOĞAZLA'),
    (re.compile(r'\bBOKURDAK\b'), 'BOĞAZ'),
    (re.compile(r'\bBOKURDAG\b'), 'BOĞAZ'),
    (re.compile(r'\bBOGURDAK\b'), 'BOĞAZ'),
    (re.compile(r'\bGulakla\b'), 'Kulakla'),
    (re.compile(r'\bGulagy\b'), 'Kulak'),
    (re.compile(r'\bGulah\b'), 'Kulak'),
    (re.compile(r'\bGulak\b'), 'Kulak'),
    (re.compile(r'\bBokurdakla\b'), 'Boğazla'),
    (re.compile(r'\bBokurdagla\b'), 'Boğazla'),
    (re.compile(r'\bBogurdakla\b'), 'Boğazla'),
    (re.compile(r'\bBokurdak\b'), 'Boğaz'),
    (re.compile(r'\bBokurdag\b'), 'Boğaz'),
    (re.compile(r'\bBogurdak\b'), 'Boğaz'),
    (re.compile(r'\bgulakla\b', re.I), 'kulakla'),
    (re.compile(r'\bgulagy\b', re.I), 'kulak'),
    (re.compile(r'\bgulah\b', re.I), 'kulak'),
    (re.compile(r'\bgulak\b', re.I), 'kulak'),
    (re.compile(r'\bbokurdakla\b', re.I), 'boğazla'),
    (re.compile(r'\bbokurdagla\b', re.I), 'boğazla'),
    (re.compile(r'\bbogurdakla\b', re.I), 'boğazla'),
    (re.compile(r'\bbokurdak\b', re.I), 'boğaz'),
    (re.compile(r'\bbokurdag\b', re.I), 'boğaz'),
    (re.compile(r'\bbogurdak\b', re.I), 'boğaz'),
    (re.compile(r'\b(KULAK)([\s,]+)(BURUN)([\s,]+)WE([\s,]+)(BOĞAZ)(LA)?\b'), r'\1\2\3\4VE\5\6\7'),
    (re.compile(r'\b([Kk]ulak)([\s,]+)([Bb]urun)([\s,]+)we([\s,]+)([Bb]oğaz)(la)?\b'), r'\1\2\3\4ve\5\6\7'),
    # S04E08 Turkic residue: dyz (Türkmence diz), haryt bazary (bit pazarı).
    # Önce bilinen ekli biçimler (ünlü uyumu düzeltilerek), sonra genel yakalayıcı.
    (re.compile(r'\bDYZUNUN\b'), 'DİZİNİN'),
    (re.compile(r'\bDYZUNU\b'), 'DİZİNİ'),
    (re.compile(r'\bDYZY\b'), 'DİZİ'),
    (re.compile(r'\bDYZ\b'), 'DİZ'),
    (re.compile(r'\bDyzunun\b'), 'Dizinin'),
    (re.compile(r'\bDyzunu\b'), 'Dizini'),
    (re.compile(r'\bDyz\b'), 'Diz'),
    (re.compile(r'\bdyzunun\b', re.I), 'dizinin'),
    (re.compile(r'\bdyzun[uy]\b', re.I), 'dizini'),
    (re.compile(r'\bdyzun\b', re.I), 'dizin'),
    (re.compile(r'\bdyzümle\b', re.I), 'dizimle'),
    (re.compile(r'\bdyzünü\b', re.I), 'dizini'),
    (re.compile(r'\bdyzün\b', re.I), 'dizin'),
    (re.compile(r'\bdyzü\b', re.I), 'dizi'),
    (re.compile(r'\bdyzy\b', re.I), 'dizi'),
    (re.compile(r'\bdyzle\b', re.I), 'dizle'),
    (re.compile(r'\bdyzd[ae]\b', re.I), 'dizde'),
    (re.compile(r'\bdyz[ae]\b', re.I), 'dize'),
    (re.compile(r'\bdyz\b', re.I), 'diz'),
    (re.compile(r'\bdyz(\w*)', re.I), r'diz\1'),
    (re.compile(r'\bulus\s+haryt\s+bazaryn(\w*)\b', re.I), r'bit pazarın\1'),
    (re.compile(r'\bharyt\s+bazaryn(\w*)\b', re.I), r'bit pazarın\1'),
    (re.compile(r'\bbazaryn(\w*)\b', re.I), r'pazarın\1'),
    # English leftover: motorcycle accident (S04E08 açılışı) — ekli biçimler önce
    (re.compile(r"\bmotorcycle\s+accident['’]ının\b", re.I), 'motosiklet kazasının'),
    (re.compile(r"\bmotorcycle\s+accident['’]t[ae]n\b", re.I), 'motosiklet kazasından'),
    (re.compile(r"\bmotorcycle\s+accident['’]t[ae]\b", re.I), 'motosiklet kazasında'),
    (re.compile(r"\bmotorcycle\s+accident['’][ıi]\b", re.I), 'motosiklet kazasını'),
    (re.compile(r'\bMOTORCYCLE\s+ACCIDENT\b'), 'MOTOSİKLET KAZASI'),
    (re.compile(r'\bmotorcycle\s+accident\b', re.I), 'motosiklet kazası'),
    (re.compile(r'\bMOTORCYCLE\b'), 'MOTOSİKLET'),
    (re.compile(r'\bmotorcycle\b', re.I), 'motosiklet'),
    # S04E04 Turkic residue: "İçki gowak / içki otag'a hoş geldin(iz)" (WELCOME TO
    # THE INNER LAIR). No word-level auto-replace for gowak/otag (context-free
    # substitution would be wrong) — only this full phrase is safe to rewrite.
    # Regex ends at "geldin" (no trailing \b) so the "iz" of "geldiniz" survives.
    (re.compile(r"İçki\s+gowak\s*/\s*içki\s+otag['’]?a\s+hoş\s+geldin", re.I),
     'İç mabede hoş geldin'),
    # S04E04 polish-introduced typo: doubled first letter ("tek" → "ttek")
    (re.compile(r'\bttek\b', re.I), 'tek'),
    # S04E03 Turkic residue: guş (Türkmence kuş) — bölüm kuş taksidermisi, 14 cue'da sızdı.
    # Türkçede 'guş' önekli kelime yok → generic önek değişimi güvenli; ek \1 ile korunur.
    (re.compile(r'\bGUŞ(\w*)'), r'KUŞ\1'),
    (re.compile(r'\bGuş(\w*)'), r'Kuş\1'),
    (re.compile(r'\bguş(\w*)', re.I), r'kuş\1'),
    # English leftover: a drug → flag replacement (model tends to leave it verbatim)
    (re.compile(r'\ba drug\b', re.I), 'bir ilaç'),
    (re.compile(r'\bdrug\b', re.I), 'ilaç'),
    (re.compile(r'\bdrugs\b', re.I), 'ilaçlar'),
    # Tutankhamun-specific: Boy King → Çocuk Kral / Genç Kral
    (re.compile(r'\bBoy\s+King\b', re.I), 'Çocuk Kral'),
    # Common documentary residues
    (re.compile(r'\bBabylon\b', re.I), 'Babil'),
    (re.compile(r'\b(\d+(?:[.,]\d+)?)\s+feet\b', re.I), r'\1 fit'),
    (re.compile(r'\[([^\]\n]{1,30})\s+speaking\]', re.I), r'[\1 konuşuyor]'),
    # Plural agreement fix: bir oğlanın yüzleri → bir oğlanın yüzü
    (re.compile(r'\bbir\s+oğlanın\s+yüzleri\b', re.I), 'bir oğlanın yüzü'),
    # Documentary/religious residues from Somali/Arabic/English mixing
    (re.compile(r'\bGod\s+/\s+Allah\b', re.I), 'Tanrı'),
    (re.compile(r'\bHebrew\s+Bible\b', re.I), 'İbrani Kutsal Kitabı'),
    # Bible → Kutsal Kitap with Turkish suffix voicing fix (Kitap ends with unvoiced p)
    (re.compile(r"\bBible['’](da|de)\b", re.I), "Kutsal Kitap'ta"),
    (re.compile(r"\bBible['’](dan|den)\b", re.I), "Kutsal Kitap'tan"),
    (re.compile(r"\bBible['’]([ıiuü])\b", re.I), r"Kutsal Kitap'\1"),
    (re.compile(r"\bBible['’](in|ın|un|ün)\b", re.I), "Kutsal Kitap'ın"),
    (re.compile(r'\bBible\b', re.I), 'Kutsal Kitap'),
    # Cibraani context-dependent: language context → İbranice
    (re.compile(r'\bCibraani\s+(dilinde|dili)\b', re.I), 'İbranice'),
    (re.compile(r'\bCibraani\s+sözcüğü\b', re.I), 'İbranice'),
    # Cibraani context: plural people → İbraniler
    (re.compile(r'\bCibraaniler\b', re.I), 'İbraniler'),
    # Cibraani context: modifier for culture/religion terms → İbrani
    (re.compile(r'\bCibraani\s+(tanrısı|geleneği|kültürü|halkı|inancı|toplumu)\b', re.I), r'İbrani \1'),
    # Fallback: bare Cibraani → İbrani
    (re.compile(r'\bCibraani\b', re.I), 'İbrani'),
    # Monotheism / tawxiid compound → clean Turkish
    (re.compile(r'\bmonotheism\s*/\s*tawxiid\b', re.I), 'tek tanrıcılık'),
    (re.compile(r'\bilaahyada\b', re.I), 'ilahlar'),
    # Henotheism / doorashada compound → clean Turkish (consumes rest of Somali phrase)
    (re.compile(r'\bhenotheism\s*/\s*doorashada[\w\s]+?(?=[.,!?]|$)', re.I), 'henoteizm'),
    (re.compile(r'\bhenotheism\b', re.I), 'henoteizm'),
    (re.compile(r'\bmonotheism\b', re.I), 'tek tanrıcılık'),
    (re.compile(r'\bQuran\b', re.I), 'Kuran'),
    # Dawut patşa (Somali) → Kral Davud
    (re.compile(r"\bDawut\s+patşa[\u0027\u2019]?nın\b", re.I), "Kral Davud'un"),
    (re.compile(r'\bDawut\s+patşa\b', re.I), 'Kral Davud'),
    (re.compile(r"\bDawut[\u0027\u2019]?a\b", re.I), "Davud'a"),
    (re.compile(r'\bDawut\b', re.I), 'Davud'),
    # Solomon patşa → Kral Solomon
    (re.compile(r'\bSolomon\s+patşa\b', re.I), 'Kral Solomon'),
    # Äht sandygy → Ahit Sandığı
    (re.compile(r"\bÄht\s+sandygy[\u0027\u2019]?nu\b", re.I), "Ahit Sandığı'nı"),
    (re.compile(r'\bÄht\s+sandygy\b', re.I), 'Ahit Sandığı'),
    (re.compile(r"\bsandygy[\u0027\u2019]?nu\b", re.I), "Sandığı'nı"),
    (re.compile(r'\bsandygy\b', re.I), 'Sandığı'),
    (re.compile(r'\bsandygyny\b', re.I), "Sandığı'nı"),
    # Iýerusalim → Kudüs
    (re.compile(r"\bIýerusalim[\u0027\u2019]?e\b", re.I), "Kudüs'e"),
    (re.compile(r"\bIýerusalim[\u0027\u2019]?de\b", re.I), "Kudüs'te"),
    (re.compile(r"\bIýerusalim[\u0027\u2019]?den\b", re.I), "Kudüs'ten"),
    (re.compile(r'\bIýerusalim\b', re.I), 'Kudüs'),
    # Ysraýyl → İsrail
    (re.compile(r"\bYsraýyl[\u0027\u2019]?da\b", re.I), "İsrail'de"),
    (re.compile(r"\bYsraýyl[\u0027\u2019]?in\b", re.I), "İsrail'in"),
    (re.compile(r"\bYsraýyl[\u0027\u2019]?e\b", re.I), "İsrail'e"),
    (re.compile(r'\bYsraýyl\b', re.I), 'İsrail'),
    # ybadathane → tapınak
    (re.compile(r'\bybadathanesinin\b', re.I), 'tapınağının'),
    (re.compile(r'\bybadathanesine\b', re.I), 'tapınağına'),
    (re.compile(r'\bybadathanesinde\b', re.I), 'tapınağında'),
    (re.compile(r'\bybadathanesinden\b', re.I), 'tapınağından'),
    (re.compile(r'\bybadathanem\b', re.I), 'tapınağım'),
    (re.compile(r'\bybadathanenin\b', re.I), 'tapınağın'),
    (re.compile(r'\bybadathaneye\b', re.I), 'tapınağa'),
    (re.compile(r'\bybadathanede\b', re.I), 'tapınakta'),
    (re.compile(r'\bybadathaneden\b', re.I), 'tapınaktan'),
    (re.compile(r'\bybadathanesi\b', re.I), 'tapınağı'),
    (re.compile(r'\bybadathaneler\b', re.I), 'tapınaklar'),
    (re.compile(r'\bybadathane\b', re.I), 'tapınak'),
    # English residue → Turkish
    (re.compile(r'\bKing\s+David\b', re.I), 'Kral Davud'),
    (re.compile(r'\bKing\s+Solomon\b', re.I), 'Kral Solomon'),
    (re.compile(r'\bWorld\s+Freemasonry\b', re.I), 'Dünya Masonluğu'),
    (re.compile(r'\bTemple\s+Institute\b', re.I), 'Tapınak Enstitüsü'),
    # religion → din (English residue with Turkish suffixes)
    (re.compile(r"\breligion[\u0027\u2019]larına\b", re.I), 'dinlerine'),
    (re.compile(r"\breligion[\u0027\u2019]larını\b", re.I), 'dinlerini'),
    (re.compile(r"\breligion[\u0027\u2019]ları\b", re.I), 'dinleri'),
    (re.compile(r"\breligion[\u0027\u2019]u\b", re.I), 'dini'),
    (re.compile(r"\breligion[\u0027\u2019]ı\b", re.I), 'dini'),
    (re.compile(r'\breligions\b', re.I), 'dinler'),
    (re.compile(r'\breligion\b', re.I), 'din'),
    # Egypt → Mısır
    (re.compile(r"\bEgypt[\u0027\u2019]e\b", re.I), "Mısır'a"),
    (re.compile(r'\bEgypt\b', re.I), 'Mısır'),
    # zodiac → zodyak
    (re.compile(r"\bzodiac[\u0027\u2019][ıi]n\b", re.I), 'zodyağın'),
    (re.compile(r"\bzodiac[\u0027\u2019]ta\b", re.I), 'zodyakta'),
    (re.compile(r"\bzodiac[\u0027\u2019][ıiuü]\b", re.I), 'zodyağı'),
    (re.compile(r'\bzodiac\b', re.I), 'zodyak'),
    # Virgo → Başak
    (re.compile(r"\bVirgo[\u0027\u2019]dur,?\s+Bakire\b", re.I), "Başak'tır, Bakire"),
    (re.compile(r"\bVirgo,\s+the\s+Virgin\b", re.I), 'Başak, Bakire'),
    (re.compile(r"\bVirgo,\s+Bakire\b", re.I), 'Başak, Bakire'),
    (re.compile(r'\bVirgo\b', re.I), 'Başak'),
    # Samoan fa'a'aitiiti (shrunken/small head context)
    (re.compile(r'\bkafa\s+fa[\u0027\u2019]?a[\u0027\u2019]?aitiiti\b', re.I), 'küçültülmüş kafa'),
    (re.compile(r'\bulu\s+fa[\u0027\u2019]aitiiti\b', re.I), 'küçültülmüş kafa'),
    (re.compile(r'\bfa[\u0027\u2019]?a[\u0027\u2019]?aitiiti\b', re.I), 'küçültülmüş'),
    (re.compile(r'\bfa[\u0027\u2019]aitiiti\b', re.I), 'küçültülmüş'),
    # Sloth → tembel hayvan
    (re.compile(r'\bSlotha\b', re.I), 'tembel hayvanı'),
    (re.compile(r"\bsloth[\u0027\u2019]a\b", re.I), 'tembel hayvana'),
    (re.compile(r"\bsloth[\u0027\u2019][uı]\b", re.I), 'tembel hayvanı'),
    (re.compile(r'\bsloth\b', re.I), 'tembel hayvan'),
    # fox skin → sloth skin in head-shrinking context
    (re.compile(r'\btilki\s+derisi\b', re.I), 'tembel hayvan derisi'),
    # Uzbek/Turkic residue — holiday context
    (re.compile(r'\bBAYRAMONA\b', re.I), 'bayram'),
    (re.compile(r"\bKO[\u0027\u2019]RSATIB[\u0027\u2019\s-]*TUSUNTIRISH\b", re.I), 'gösterip açıklama'),
    # Straitjacket English residue
    (re.compile(r'\bstra[ıi]tjacket\b', re.I), 'deli gömleği'),
    (re.compile(r'\bstra[ıi]tjaket\b', re.I), 'deli gömleği'),
    # Alligator English residue
    (re.compile(r'\balligator\b', re.I), 'timsah'),
    (re.compile(r'\balligator\s+dili\b', re.I), 'timsah dili'),
    (re.compile(r'\balligator\s+saldırıları\b', re.I), 'timsah saldırıları'),
    # Şinek residue (Arabic → Turkish)
    (re.compile(r'\bşinek\b', re.I), 'sinek'),
    (re.compile(r'\bşineğin\b', re.I), 'sineğin'),
    (re.compile(r'\bşineğe\b', re.I), 'sineğe'),
    # Turkic residue — time machine
    (re.compile(r'\bvaxt\s+mashinasi\b', re.I), 'zaman makinesi'),
    (re.compile(r'\bvaqt\s+mashinasi\b', re.I), 'zaman makinesi'),
    (re.compile(r'\bmashinasi\b', re.I), 'makinesi'),
    # Turkic residue — explosive device
    (re.compile(r'\bportlatgich\s+qurilma\b', re.I), 'patlatma düzeneği'),
    (re.compile(r'\bportlatgich\b', re.I), 'patlatıcı'),
    (re.compile(r'\bqurilma\b', re.I), 'düzenek'),
    # Detonator → natural Turkish
    (re.compile(r'\bdetonator\b', re.I), 'patlatıcı'),
    (re.compile(r'\bdetonatör\b', re.I), 'patlatıcı'),
    # Ear protection phrase
    (re.compile(r'\bKulak\s+kapaklarımı\b'), 'Kulaklıklarımı'),
    (re.compile(r'\bkulak\s+kapaklarımı\b', re.I), 'kulaklıklarımı'),
    (re.compile(r'\bKulak\s+kapaklarını\b'), 'Kulaklıklarını'),
    (re.compile(r'\bkulak\s+kapaklarını\b', re.I), 'kulaklıklarını'),
    # Polish intro fix
    (re.compile(r'\bbilim\s+gibi\s+yapmaya\s+verdik\b', re.I), 'iyice ustalaştırdık'),
    # S05E10 — medical residue
    (re.compile(r'\bmedisina\s+nusgasy\b', re.I), 'tıbbi örnek'),
    (re.compile(r'\bmedisina\s+koleksiyonu\b', re.I), 'tıbbi örnek koleksiyonu'),
    (re.compile(r'\bmedisina\b', re.I), 'tıbbi'),
    # S05E10 — prison / torture / execution
    (re.compile(r'\btürmede\b', re.I), 'hapishanede'),
    (re.compile(r'\btürme\b', re.I), 'hapishane'),
    (re.compile(r'\bejir\s+ýetirmek\b', re.I), 'işkence'),
    (re.compile(r'\bazap\b', re.I), 'işkence'),
    (re.compile(r'\bbaşy\s+kesmek\b', re.I), 'baş kesme'),
    # S05E10 — spear
    (re.compile(r'\bmızrağı\s+deken\b', re.I), 'mızrağı atan'),
    # Store → dükkân (with Turkish possessive suffixes)
    (re.compile(r"\bstore[\u0027\u2019]unda\b", re.I), 'dükkânında'),
    (re.compile(r"\bstore[\u0027\u2019]u\b", re.I), 'dükkânı'),
    # Invitation fix
    (re.compile(r'\bgelmeye\s+sevinirim\b', re.I), 'gelmenize sevinirim'),
    # Intro idiom fix
    (re.compile(r'\bişin\s+suyunu\s+çıkardık\b', re.I), 'işin tekniğini oturttuk'),
    # Oddities intro title cleanup
    (re.compile(
        r'(?:SIRA\s+DIŞI|TUHAF)\s+DÜNYA(?:YA|SINDA|SI)\s+HOŞ\s+GELDİNİZ'
        r'\s*(?:\n)?\s*["\u201c\u201d]*ODDITIES["\u201c\u201d]*[\u0027\u2019]İN',
        re.I
    ), '"ODDITIES"in sıra dışı dünyasına\nhoş geldiniz'),
    (re.compile(
        r'["\u201c\u201d]*ODDITIES["\u201c\u201d]*\s*IN\s+TUHAF\s+DÜNYASINA\s+HOŞ\s+GELDİNİZ',
        re.I
    ), '"ODDITIES"in tuhaf dünyasına\nhoş geldiniz'),
    (re.compile(
        r'TUHAF\s+DÜNYASINA\s+HOŞ\s+GELDİNİZ\s*(?:\n\s*)?["\u201c\u201d]*ODDITIES["\u201c\u201d]*(?:[\u0027\u2019])?İN',
        re.I
    ), '"ODDITIES"in tuhaf dünyasına\nhoş geldiniz'),
    (re.compile(
        r'(?:SIRA\s+DIŞI|TUHAF)\s+DÜNYASI(?:NA|NDA)?\s+["\u201c\u201d]*ODDITIES["\u201c\u201d]*[\u0027\u2019]İN',
        re.I
    ), '"ODDITIES"in sıra dışı dünyası'),
    # S04E08 varyantı: 'TUHAFLIK DÜNYASINA HOŞ GELDİNİZ, "Oddities."'
    (re.compile(
        r'TUHAFLIK\s+DÜNYASINA\s+HOŞ\s+GELDİNİZ[,.]?\s*(?:\n\s*)?'
        r'["“”]*ODDITIES\.?["“”]*\.?',
        re.I
    ), '"ODDITIES"in tuhaf dünyasına\nhoş geldiniz.'),
    # OBSCURA grandma line
    (re.compile(
        r'OBSCURA\s+annenizin\s+antika\s+dükkânı\s+değil',
        re.I
    ), 'Obscura, anneannenizin antikacısı değil'),
    (re.compile(
        r'Obscura,\s*büyükannenizin\s+antikacı\s+dükkânı\s+değil',
        re.I
    ), 'Obscura, anneannenizin antikacısı değil'),
    (re.compile(
        r'Tabii,?\s*büyükanneniz\s+biraz\s+çatlak\s+değilse\.?',
        re.I
    ), 'Tabii anneanneniz biraz çatlaksa o ayrı.'),
    # Bilime döktük → natural
    (re.compile(r'\bbilime\s+döktük\b', re.I), 'bu işte iyice ustalaştık'),
    (re.compile(r'\biyice\s+bir\s+bilime\s+çevirdik\b', re.I), 'bu işte iyice ustalaştık'),
    (re.compile(r'\b(morbid\s+şeylere)\s+ile\s+(kemiklere)\b', re.I), r'\1 ve \2'),
    (re.compile(r'\bantikacılıkta\s+çağrısını\s+buldu\b', re.I), 'antikacılıkta aradığı şeyi buldu'),
    # Broken-flow cleanup from real Oddities output
    (re.compile(r'\ben\s+biraz\b', re.I), 'biraz'),
    (re.compile(r'\badı\s+(?=THE\s+MUDLARK\b)', re.I), 'adı da '),
    (re.compile(r'\bbirinin\s+o\s+öğrenmesi\b', re.I), 'birinin öğrenmesi'),
    (re.compile(r'\belimizde\s+geçen\b', re.I), 'elimizden geçen'),
    # Oddities title case regression: "ODDITIES"E → "ODDITIES"in
    (re.compile(
        r'["\u201c\u201d]*ODDITIES["\u201c\u201d]*\s*E\b(?!\w)',
        re.I
    ), '"ODDITIES"in'),
    # Obscura grandma typo variants
    (re.compile(
        r'OBSCURA,\s+BÜYÜKANANEMİN\s+ANTİKA\s+DÜKKANI\s+DEĞİL',
        re.I
    ), 'Obscura, anneannenizin antikacısı değil'),
    (re.compile(
        r'OBSCURA,\s+BÜYÜKANANENİN\s+ANTİKA\s+DÜKKANI\s+DEĞİL',
        re.I
    ), 'Obscura, anneannenizin antikacısı değil'),
    # S04E11 — Oddities title stray apostrophe: "ODDITIES"'in → "ODDITIES"in
    (re.compile(
        r'["\u201c\u201d]*ODDITIES["\u201c\u201d]*[\u0027\u2019]+(?:in|ın)',
        re.I
    ), '"ODDITIES"in'),
    # S04E11 — Both:/BOTH: speaker label → İkisi:
    (re.compile(r'^Both:\s*', re.I), 'İkisi: '),
    # S04E11 — Oddities intro literal flow
    (re.compile(r'\bbilim\s+haline\s+getirmek\s+için\b', re.I), 'bu işte iyice ustalaşmak için'),
    (re.compile(r'\bbilim\s+haline\s+getirdik\b', re.I), 'bu işte iyice ustalaştık'),
    # S04E11 — Vajina ki... → Vajina değil...
    (re.compile(
        r'Vajina\s+ki\.\.\.\s+şey,\s+üretradan\s+bahsediyoruz\.?',
        re.I
    ), 'Vajina değil... şey, üretradan bahsediyoruz.'),
    # S04E11 — cassowary → kasuar
    (re.compile(r'\bkassovar\s+kuşu\b', re.I), 'kasuar kuşu'),
    (re.compile(r'\bkassovar\s+hançerleri\b', re.I), 'kasuar hançerleri'),
    (re.compile(r'\bkassovar\b', re.I), 'kasuar'),
    # S04E11 — Obscura grandma: Tabii, anneannen biraz kaçık değilse → o ayrı
    (re.compile(
        r'Tabii?,\s*(anneannen(?:iz)?)\s+biraz\s+(kaçık|çatlak)\s+değilse\.?',
        re.I
    ), r'Tabii \1 biraz \2 değilse o ayrı.'),
    # S04E02/E05/E09/E16 — Oddities title: "ODDITIES"'E / "ODDITIES. " → "ODDITIES"in
    (re.compile(
        r'["\u201c\u201d]*ODDITIES["\u201c\u201d]*[\u0027\u2019]*\s*E\b(?!\w)',
        re.I
    ), '"ODDITIES"in'),
    (re.compile(
        r'["\u201c\u201d]*ODDITIES["\u201c\u201d]*\s*\.\s+',
        re.I
    ), '"ODDITIES" '),
    # S04E02/E05/E09/E16 — Intro: BU İŞİ... İŞİ İYİCE... / işin bilimini çıkardık
    (re.compile(
        r'BU\s+İŞİ\.\.\.\s+İŞİ\s+İYİCE\s+USTALIĞA\s+DÖKMEYE',
        re.I
    ), 'Bu işte iyice ustalaşmaya'),
    (re.compile(r'\bişin\s+bilimini\s+çıkardık\b', re.I), 'işin tekniğini oturttuk'),
    # S04E02/E05/E09/E16 — English residue: deal eden → uğraşan
    (re.compile(r'\bdeal\s+eden\b', re.I), 'uğraşan'),
    # S04E02/E05/E09/E16 — Broken sentence cleanup
    (re.compile(
        r'\bböyle\s+şeylere\.\s*$',
        re.MULTILINE
    ), 'böyle şeyler yani.'),
    # S04E02/E05/E09/E16 — Typo cleanup
    (re.compile(r'\bmikrofom\b', re.I), 'mikrofon'),
    (re.compile(r'\bona\s+de\b', re.I), 'ona da'),
    (re.compile(r'\bWoodstoc[\u0027\u2019]a\b', re.I), "Woodstock'a"),
]

# Pattern to detect suspicious lines (contain English words that shouldn't be there)
_SUSPICIOUS_PATTERN = re.compile(
    r'\b(ass|shit|fuck|damn|hell|bitch|crap|piss|bastard|screw|'
    r'gonna|wanna|gotta|yeah|okay|alright|oh my god)\b',
    re.IGNORECASE
)

# Additional English words that are clearly out-of-place in Turkish subtitles
_EN_LEFTOVER = re.compile(
    r'\b(literally|actually|basically|seriously|honestly|obviously|totally'
    r'|whatever|like really|you know|i mean|come on|shut up|no way'
    r'|for real|dude|bro|sis|guys|wait what|somehow|anyhow|kind of|sort of'
    r'|drug|drugs|feet|speaking|Babylon'
    r'|Bible|Quran|henotheism|monotheism'
    r'|Freemasonry|Temple\s+Institute'
    r'|religion|Egypt|zodiac|Virgo'
    r'|sloth'
    r'|straitjacket|alligator'
    r'|detonator'
    r'|cassowary'
    r'|deal\s+eden)\b',
    re.IGNORECASE
)

# Lowercase English words carrying Turkish suffixes are almost always untranslated
# source residue: client'ımız, rat'le, macabre mobile'ında, coroner's office'i.
_ENGLISH_TURKISH_SUFFIX_LEFTOVER = re.compile(
    r"\b(?:[a-z]{3,}(?:['’]s)?\s+){0,2}[a-z]{3,}['’][a-zçğıöşü]{1,14}\b"
)

# Common non-Turkish source words that models sometimes leave verbatim in Turkish
# output. Keep this list conservative: it only sends the line to the helper critic.
_SOURCE_LANG_LEFTOVER = re.compile(
    r"\b("
    r"flügel(?:n|ler(?:i(?:m(?:i|iz)?|miz)?|imiz|iniz)?|li)?"
    r"|federn(?:i|ler(?:i)?)?"
    r"|käfig(?:den|de|e|i|ler(?:i)?)?"
    r"|nicht|und|oder|aber|wenn|dann|doch|sein|seine|seinen|einen|einem"
    r"|psix\w*|shaxs\w*|xavf\w*|daraj\w*|buyuk\w*|narsiss\w*|haqli"
    r"|Cibraani|ilaahyada|doorashada|tawxiid"
    r"|Dawut|Ysraýyl|Iýerusalim|ybadathane|Äht|sandygy"
    r"|fa[\u0027\u2019]?a[\u0027\u2019]?aitiiti|fa[\u0027\u2019]?aitiiti"
    r"|BAYRAMONA"
    r"|KO[\u0027\u2019]RSATIB[\u0027\u2019\s-]*TUSUNTIRISH"
    r"|stra[ıi]tjacket"
    r"|alligator"
    r"|şinek"
    r"|şineğin|şineğe"
    r"|vaxt|vaqt|mashinasi"
    r"|portlatgich|qurilma"
    r"|detonator|detonatör"
    r"|medisina|nusgasy"
    r"|türme|ejir|ýetirmek|başy|deken"
    r"|gulak|gulah|gulagy|gulakla|bokurdak|bokurdag|bogurdak|we"
    r"|dyz\w*|haryt\w*|bazaryn\w*"
    r"|motorcycle|accident"
    r"|gowak\w*|otag\w*"
    r"|guş\w*"
    r")\b",
    re.IGNORECASE,
)

_TR_ODDITY_RE = re.compile(
    r"\bki\s+da\b|\bo['’](?:nu|na|nun|nda|ndan)\b|\bİsrael\b",
    re.IGNORECASE,
)

_TURKIC_DRIFT_RE = re.compile(
    r"\b(?:holidaý\w*|bäýram\w*|oturyly\w*|ortadagy|bezeg|geň\w*|"
    r"taksidermiya\w*|bäseke\w*|qora|yuqori|pichoq|kerak|emas|bilan|"
    r"uchun|yaxshi|yomon|shaxs\w*|xavf\w*|daraj\w*|haqli|o['’‘`]?zini|"
    r"k[əƏ]ll[əƏ]|avtomatonofobi\w*|ventriloq\w*|partladylan\w*|"
    r"Äht\w*|sandygy\w*|Iýerusalim\w*|Ysraýyl\w*|ybadathane\w*|"
    r"BAYRAMONA\w*|KO[\u0027\u2019]RSATIB[\u0027\u2019\s-]*TUSUNTIRISH|"
    r"vaxt\w*|vaqt\w*|mashinasi\w*|portlatgich\w*|qurilma\w*|"
    r"medisina\w*|nusgasy\w*|türme\w*|ejir\w*|ýetirmek\w*|başyn\w*|başy\b|deken\w*|"
    r"gulak\w*|gulah\w*|gulagy\w*|bokurdak\w*|bokurdag\w*|bogurdak\w*|we|"
    r"dyz\w*|haryt\w*|bazaryn\w*|gowak\w*|otag\w*|guş\w*)\b",
    re.IGNORECASE,
)

_COME_IN_AT_PRICE_RE = re.compile(
    r"\bcome\s+in\s+(right\s+)?at\s+\d+\b",
    re.IGNORECASE,
)
_COME_IN_AT_TR_GIRMEK_RE = re.compile(
    r"\bgirmek\b|\bgirmem\b|\bgireceğ\w*\b|\bgiriyor\w*\b",
    re.IGNORECASE | re.UNICODE,
)
_LATIN_EXTENDED_CHAR_RE = re.compile(r"[\u00C0-\u024F\u0250-\u02AF]")
_TARGET_TURKISH_LATIN_ALLOW = set(
    "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz"
    "ÇĞİÖŞÜçğıöşüÂâÎîÛû"
)
_TOKEN_WITH_LATIN_EXTENDED_RE = re.compile(r"[^\W\d_][^\s]*[\u00C0-\u024F\u0250-\u02AF][^\s]*", re.UNICODE)
_FOREIGN_SCRIPT_RE = re.compile(
    r"[\u0400-\u04FF\u0500-\u052F\u0600-\u06FF\u0900-\u097F\u0B80-\u0BFF\u4E00-\u9FFF]"
)
_CYRILLIC_LATIN_HOMOGLYPH_TRANS = str.maketrans({
    "А": "A", "В": "B", "Е": "E", "К": "K", "М": "M", "Н": "H",
    "О": "O", "Р": "P", "С": "C", "Т": "T", "Х": "X",
    "а": "a", "е": "e", "о": "o", "р": "p", "с": "c", "у": "y", "х": "x",
})


_MUSIC_ONLY_RE = re.compile(
    r'^[\s*♪♫\u266a\u266b]+$'
    r'|^(?=.*[*♪♫])[\*\s♪♫]*'
    r'(?:[A-Za-z]{2,4}(?:[-–][A-Za-z]{2,4})?(?:\s+[A-Za-z]{2,4}(?:[-–][A-Za-z]{2,4})?)*)'
    r'[\*\s♪♫]*$'
    r'|^\[MÜZİK\]$|^\[MUSIC\]$'
    r'|^♪[^♪]*♪$',
    re.I,
)


def normalize_latin_homoglyphs(text: str) -> str:
    """Convert Cyrillic letters that are visually identical to Latin letters.

    Models occasionally emit a single Cyrillic homoglyph inside an otherwise
    Turkish word (e.g. BĞNA with Cyrillic A). Normalize only safe one-to-one
    glyphs; real Cyrillic words will still contain foreign script and be flagged.
    """
    return str(text or "").translate(_CYRILLIC_LATIN_HOMOGLYPH_TRANS)

_COMMON_TURKISH_TERM_GUARD = (
    ("holiday party", "tatil/bayram/yılbaşı partisi"),
    ("holiday parties", "tatil/bayram/yılbaşı partileri"),
    ("holiday centerpiece", "tatil/bayram masa süsü"),
    ("centerpiece", "masa süsü"),
    ("taxidermy", "taksidermi"),
    ("taxidermist", "taksidermist"),
    ("automatonophobia", "otomatonofobi"),
    ("ventriloquism", "ventrilokluk"),
    ("ventriloquist", "ventrilok"),
    ("ventriloquist dummy", "ventrilok kuklası"),
    ("exploded skull", "patlatılmış kafatası"),
    ("skull preparation", "kafatası hazırlığı"),
    ("chiropractor", "kiropraktör"),
    ("polio braces", "polio korseleri"),
    ("braces", "korseler"),
    ("orthotics", "ortezler"),
    ("mortuary school", "cenaze hizmetleri okulu"),
    ("mortuary", "cenaze hazırlığı"),
    ("wound-filler", "yara dolgusu"),
    ("wound filler", "yara dolgusu"),
    ("sideshow performer", "yan gösteri sanatçısı"),
    ("sideshow stunts", "yan gösteri numaraları"),
    ("body modification", "beden modifikasyonu"),
    ("mummy parts", "mumya parçaları"),
    ("mummy", "mumya"),
    ("phallus", "fallus"),
    ("mummified phallus", "mumyalanmış fallus"),
    ("repeat customer", "devamlı müşteri"),
    ("authentic", "gerçek"),
    ("uppercut", "aparkat"),
    ("gold leaf", "altın varak"),
    ("gilding", "altın yaldız"),
    ("linen wrappings", "keten sargılar"),
    ("rat", "sıçan"),
    ("client", "müşteri"),
    ("macabre", "ürkütücü/ölüm temalı"),
    ("macabre mobile", "ürkütücü araba"),
    ("medical stuff", "tıbbi şeyler"),
    ("coroner's office", "adli tabip ofisi"),
    ("coroner's table", "adli tabip masası"),
    ("coroner's tools", "adli tabip aletleri"),
    ("coroner's gurney", "adli tabip sedyesi"),
    ("hunting and picking", "araştırıp seçerek"),
    ("mechanical clockwork orreries", "mekanik saat mekanizmalı gök modelleri"),
    ("clockwork orreries", "saat mekanizmalı gök modelleri"),
    ("orreries", "gök modelleri"),
    ("orrery", "gök modeli"),
    ("electromagnets", "elektromıknatıslar"),
    ("electromagnet", "elektromıknatıs"),
    ("life mask", "yaşam maskesi"),
    ("death mask", "ölüm maskesi"),
    ("abdominal scar", "karındaki yara izi"),
    ("scars", "yara izleri"),
    ("scar", "yara izi"),
    ("reindeer", "ren geyiği"),
    ("caribou", "karibu"),
    ("competition piece", "yarışma parçası"),
    ("cash in hand", "nakit parayla"),
    ("cash-in-hand", "nakit parayla"),
    ("stay under your budget", "bütçeni aşmamak"),
    ("stayed under your budget", "bütçeni aşmadım"),
    ("under your budget", "bütçenin altında"),
    ("pupils", "göz bebekleri"),
    ("pupil", "göz bebeği"),
    ("fake out", "şaşırtmak"),
    ("on the house", "ikram"),
    ("under the weather", "keyfi yerinde değil"),
    ("break a leg", "bol şans"),
    ("piece of cake", "çocuk oyuncağı"),
    ("cut me some slack", "biraz anlayış göster"),
    ("on thin ice", "bıçak sırtında"),
    ("call it a day", "paydos etmek"),
    ("in the bag", "çantada keklik"),
    ("i'm flattered", "sağ ol"),
)

_DANGLING_FRAGMENT_TAIL_RE = re.compile(
    r"(?:\b(?:veren|olabileceğini|olduğunu|düzeyini|kavramını|takdire|bazı|sanki)\.?\s*)$",
    re.IGNORECASE,
)

# Parenthetical SFX that should have been cleaned by SDH pass
_SFX_LEFTOVER_RE = re.compile(r'\([^)\n]{2,80}\)')

# ── Garble-token kuralları (deterministik, API'siz) — bkz. plans/future-quality-guards-brief.md
# NOT: R1-R4 hepsi "(?<!['’])\b" öneki kullanır — apostrof \w DEĞİL, o yüzden çıplak
# \b "Mısır'daki" içindeki "daki"yi veya "ay'a" içindeki "a"yı BAĞIMSIZ kelime sanıp
# yanlış-pozitif üretiyordu (apostrof-bitişik meşru ekler, kopuk/başıboş ek değil).
# Lookbehind bunu apostroften hemen sonra gelen eşleşmeleri eleyerek düzeltir.
_GARBLE_NOT_AFTER_APOS = r"(?<!['’])"

# R1: başıboş tek harf (gerçek örnekler: "a astronom", "orada a olduğunu", "kıtasını a").
# 'o' (zamir) ve 'e' (ünlem) kasıtlı hariç.
_GARBLE_STRAY_LETTER_RE = re.compile(_GARBLE_NOT_AFTER_APOS + r'\b[aıuüö]\b')
# R2: küçük-harf w/q/x içeren token (ör. "simwolika"); allowlist'te olanlar ve
# büyük-harfle başlayanlar (özel isim) hariç.
_GARBLE_WQX_RE = re.compile(_GARBLE_NOT_AFTER_APOS + r'\b[a-zçğıöşü]*[wqx][a-zçğıöşü]*\b')
_GARBLE_WQX_ALLOWLIST = frozenset({
    "web", "wifi", "www", "fax", "show", "taxi",
    # Valid loanwords/technical terms that appear naturally in Turkish subtitles.
    "bowling", "rex", "watt", "wattı",
    # murex = mor boya salyangozu (Tyrian purple) — arkeoloji/tarih belgesellerinde
    # meşru bilimsel terim; Türkçe ekli hâlleriyle birlikte (watt/wattı deseni).
    "murex", "murexler", "murexleri", "murexi", "murexin",
})
# R3: başıboş ek — bağımsız kelime olarak asla var olmayan ek parçaları
# (ör. "gündönümünde deki"). Apostrof-bitişik ("Mısır'daki") HARİÇ — o R5'in işi.
_GARBLE_STRAY_SUFFIX_RE = re.compile(_GARBLE_NOT_AFTER_APOS + r'\b(deki|daki|teki|taki)\b', re.IGNORECASE)
# R4: Türkçe'de imkânsız ek dizisi (ör. "toplumlarde").
_GARBLE_IMPOSSIBLE_SUFFIX_RE = re.compile(_GARBLE_NOT_AFTER_APOS + r'\b\w*(?:larde|lerda|larte|lerta)\b', re.IGNORECASE)
# R5: apostrof ek uyumu — "Gövde'ek" kalıbında gövde Türkçe-özel harf içeriyorsa
# (ASCII-only gövdeler, örn. yabancı özel isimler, atlanır — "Google'da" gibi meşru
# yazım/telaffuz farkları için) gövdenin son ünlüsüyle ekin İLK ünlüsü kalınlık
# (art/ön) uyumu kontrol edilir. Yalnızca art/ön (2 yönlü) uyum kontrol edilir —
# düzlük/yuvarlaklık (4 yönlü) uyumu KAPSAM DIŞI (brief'teki örnekler yalnızca
# art/ön karışıklığı: Mısır'teki→Mısır'daki, Mısır'in→Mısır'ın).
_GARBLE_APOSTROPHE_RE = re.compile(r"([A-Za-zÇĞİÖŞÜçğıöşü]+)['’]([a-zçğıöşü]+)")
_GARBLE_TR_SPECIAL_CHARS = set("çğıöşüÇĞİÖŞÜ")
_GARBLE_BACK_VOWELS = set("aıou")
_GARBLE_FRONT_VOWELS = set("eiöü")
# R6: İngilizce sıra sayısı kalıntısı (ör. "19th century").
_GARBLE_EN_ORDINAL_RE = re.compile(r'\b\d+(?:st|nd|rd|th)\b', re.IGNORECASE)


_GARBLE_WORD_RE = re.compile(r"[^\W\d_]+", re.UNICODE)


def _garble_neighbor_is_capitalized(s: str, start: int, end: int) -> bool:
    """Başıboş-harf eşleşmesinin (R1) hemen komşusunda Büyük-harfle başlayan bir
    kelime varsa True — yabancı-dilde özel-isim dizisi göstergesi (ör. İspanyolca
    "Monumento a la Humanidad" içindeki 'a' edatı, başıboş Türkçe harf DEĞİL)."""
    before_words = _GARBLE_WORD_RE.findall(s[:start])
    after_words = _GARBLE_WORD_RE.findall(s[end:])
    if before_words and before_words[-1][:1].isupper():
        return True
    if after_words and after_words[0][:1].isupper():
        return True
    return False


def _garble_first_vowel(word: str) -> str:
    for ch in word.lower():
        if ch in "aeıioöuü":
            return ch
    return ""


def _garble_last_vowel(word: str) -> str:
    for ch in reversed(word.lower()):
        if ch in "aeıioöuü":
            return ch
    return ""


def find_garble_tokens(text) -> list:
    """Bozuk/yabancı token'ları deterministik kurallarla yakalar (API yok, ~sıfır
    yanlış-pozitif hedefli). Döner: [(token, kural_adı), ...].

    Hem run_validators (koşu-içi critic düzeltmesi) hem scan_translation_quality
    (yazım-sonrası tarama) TEK bu fonksiyonu paylaşır. Kural detayları/kanıtları:
    plans/future-quality-guards-brief.md."""
    s = str(text or "")
    if not s.strip():
        return []
    found = []

    for m in _GARBLE_STRAY_LETTER_RE.finditer(s):
        if _garble_neighbor_is_capitalized(s, m.start(), m.end()):
            continue  # özel-isim dizisinin parçası olabilir (ör. "Monumento a la Humanidad")
        found.append((m.group(0), "R1_stray_letter"))

    for m in _GARBLE_WQX_RE.finditer(s):
        tok = m.group(0)
        # Tek harfli "x"/"w"/"q" matematik sembolü/değişken/kısaltma olabilir
        # (gerçek garble değil) — yalnızca 2+ harfli token'lar (ör. "simwolika",
        # "wedges") sayılır.
        if len(tok) < 2 or tok.lower() in _GARBLE_WQX_ALLOWLIST or tok[:1].isupper():
            continue
        found.append((tok, "R2_wqx_token"))

    for m in _GARBLE_STRAY_SUFFIX_RE.finditer(s):
        found.append((m.group(0), "R3_stray_suffix"))

    for m in _GARBLE_IMPOSSIBLE_SUFFIX_RE.finditer(s):
        found.append((m.group(0), "R4_impossible_suffix"))

    for m in _GARBLE_APOSTROPHE_RE.finditer(s):
        stem, suffix = m.group(1), m.group(2)
        if not any(c in _GARBLE_TR_SPECIAL_CHARS for c in stem):
            continue  # ASCII gövde (yabancı özel isim) — atla
        stem_vowel = _garble_last_vowel(stem)
        suffix_vowel = _garble_first_vowel(suffix)
        if not stem_vowel or not suffix_vowel:
            continue
        stem_back = stem_vowel in _GARBLE_BACK_VOWELS
        suffix_back = suffix_vowel in _GARBLE_BACK_VOWELS
        if stem_back != suffix_back:
            found.append((m.group(0), "R5_vowel_harmony"))

    for m in _GARBLE_EN_ORDINAL_RE.finditer(s):
        found.append((m.group(0), "R6_english_ordinal"))

    return found

# On-screen text detection: all-caps short lines, date/location patterns, standalone labels.
_OST_DETECT_RE = re.compile(
    r"^(?:\d{1,4}[-–—]\d{1,4}|[A-Z][a-zçğıöşü]+,\s*\d{4}|"
    r"[A-Z][a-zçğıöşü]+(?:–|—)[A-Z][a-zçğıöşü]+"
    r"|(?:CHAPTER|SECTION|PART|ACT|SCENE|DAY|NIGHT|LATER|THEN|SIX|YEAR|MONTH|YEAR)\s+\d+|\d+\s+(?:MINUTES|SECONDS|HOURS|DAYS)?)",
    re.IGNORECASE,
)


def looks_like_on_screen_text(text: str) -> bool:
    """SRT/VTT'de ekran yazısı olma olasılığı yüksek satırları tespit eder."""
    core = _clean_source_text(str(text or ""))
    core = re.sub(r"^\s*[-–—]?\s*[^:\n]{1,40}:\s*", "", core).strip()
    core = re.sub(r"\[[^\]]*\]|\([^)]*\)", "", core).strip()
    if len(core.split()) < 2 or len(core.split()) > 15:
        return False
    if _has_speaker_label(core):
        return False
    if _OST_DETECT_RE.search(core):
        return True
    stripped = core.rstrip()
    return bool(
        stripped.isupper()
        and 8 <= len(stripped) <= 60
        and stripped[-1:] not in {".", "!", "?"}
    )

_SOURCE_NEGATION_RE = re.compile(
    r"\b(?:not|never|nothing|nobody|none|neither|nor|without|cannot|can't|won't|"
    r"don't|doesn't|didn't|isn't|aren't|wasn't|weren't|haven't|hasn't|hadn't|"
    r"shouldn't|wouldn't|couldn't|mustn't)\b|\bno\b|\b\w+n['’]t\b",
    re.IGNORECASE,
)
_TURKISH_NEGATION_WORD_RE = re.compile(
    r"\b(?:değil\w*|"
    r"yok(?:tur|tu|muş|sa|sam|san|sak|sanız|salar|sun|sunuz|um|uz|lar|ken|"
    r"tular|tuk|tun|tunuz|muşuz|muşsun)?|"
    r"hayır|hiç|hiçbir|hiçbiri|hiçkimse|asla|sakın)\b|"
    r"\bne\b.{0,80}\bne\b",
    re.IGNORECASE,
)
_TURKISH_NEGATION_SUFFIX_RE = re.compile(
    r"(?:(?:ma|me)(?:"
    r"m|n|z|"
    r"d[ıiuüi]|t[ıiuüi]|mış|miş|muş|müş|"
    r"dan|den|s[ıi]n|l[ıi]|"
    r"y(?:acağ|eceğ|acak|ecek|an|en|[ıiuü]m|[ıiuü]z|[ıiuü]n|im|ım|iz|ız|in|ın)"
    r")|(?:mı|mi|mu|mü)yor)\w*$",
    re.IGNORECASE,
)
# Bare negative imperative: "-ma/-me" is only a negation suffix (not a noun like
# "elma", "sinema", "krema") when it sits at the END of a clause — the sentence
# stops right there because Turkish negative imperatives are clause-final in SOV
# order. So require -ma/-me to be immediately followed by punctuation, optional
# closing quote/bracket, or end of line/string (position-sensitive — must run on
# the raw text, not on a word list, or the punctuation context is lost).
#
# Apostrophe/curly-apostrophe are only accepted as a terminator when NOT
# followed by a word character: Turkish attaches possessive/case suffixes to
# proper nouns with an apostrophe ("Roma'da", "Salome'ye"), and those proper
# nouns frequently end in "-ma/-me" themselves — treating a bare apostrophe as
# always-terminal caused exactly that false trigger on real subtitle files.
# A true closing quote apostrophe is followed by whitespace/punctuation/EOL,
# never directly by more letters, so the (?!\w) keeps that case working.
_BARE_NEGATIVE_IMPERATIVE_RE = re.compile(
    r"\w*(?:ma|me)(?=[ \t]*(?:[.,!?;:…\")\]]|['’](?!\w)|$))",
    re.IGNORECASE | re.MULTILINE,
)
_SOURCE_INTERROGATIVE_RE = re.compile(
    r"\b(?:who|what|when|where|why|how|which|whose|whom)\b",
    re.IGNORECASE,
)
_NUMERIC_TOKEN_RE = re.compile(r"(?<![\w])[-+]?\d+(?:[.,:/-]\d+)*(?![\w])")
_SEN_REGISTER_RE = re.compile(
    r"\b(?:sen|seni|sana|sende|senden|senin|sensin)\b",
    re.IGNORECASE,
)
_SIZ_REGISTER_RE = re.compile(
    r"\b(?:siz|sizi|size|sizde|sizden|sizin|sizsiniz)\b",
    re.IGNORECASE,
)
_BAD_TURKISH_CASE_FLOW_RE = re.compile(
    r"\b[\wçğıöşü]+(?:ın|in|un|ün|nın|nin|nun|nün)\s+"
    r"(?:aç|kapat|çevir|al|ver|gör|yap|kullan)(?:abil|ebil)?(?:iyor|ıyorum|iyorum|uyor|üyorum)\w*\b",
    re.IGNORECASE,
)

_TR_FINITE_VERB_TAIL_RE = re.compile(
    r"(?:"
    r"(?:[dt][ıiuü]|di|du|dı|dü|ti|tu|tı|tü)(?:m|n|k|nız|niz|nuz|nüz|lar|ler)?|"
    r"yor(?:um|sun|uz|sunuz|lar|ler)?|"
    r"(?:acak|ecek)(?:ım|im|sın|sin|ız|iz|sınız|siniz|lar|ler)?|"
    r"(?:malı|meli)(?:yım|yim|sın|sin|yız|yiz|sınız|siniz)?|"
    r"(?:[aeıiuü]r)(?:ım|im|sın|sin|ız|iz|sınız|siniz|lar|ler)?|"
    r"(?:dır|dir|dur|dür|tır|tir|tur|tür)"
    r")$",
    re.IGNORECASE,
)


def _looks_like_early_turkish_verb_closure(text: str) -> bool:
    """Heuristic: a fragment line appears to close with a finite Turkish predicate."""
    if not text:
        return False
    core = re.sub(r"<[^>]+>|\{[^}]+\}|\[[^\]]+\]", " ", str(text))
    core = re.sub(r"^\s*[-–—]?\s*[^:\n]{1,40}:\s*", "", core).strip()
    if len(core.split()) < 2:
        return False
    last = re.sub(r'''["' “”‘’»«…)\].,!?;:]+$''', "", core).split()
    if not last:
        return False
    tail = last[-1].lower()
    if tail in {"bir", "var", "kadar", "her", "eğer", "meğer"}:
        return False
    if tail.endswith(("sa", "se", "ken", "ince", "ınca", "unca", "ünce", "arak", "erek")):
        return False
    return bool(_TR_FINITE_VERB_TAIL_RE.search(tail))


# ── Sözlük hedef-dil guard'ı (glossary-level) ─────────────────────────────────
# Ayrı tutulur (bkz. plans/sozluk-hedef-dil-guard-brief.md): find_garble_tokens
# (yukarıda) çevrilmiş altyazı METNİNİ tarar ve tests/test_garble_rules.py onun
# 6 kuralını kilitler — burası SADECE glossary DEĞERLERİNİ (sözlük hedef terimlerini)
# tarayan R_wqx sinyalidir, find_garble_tokens'a dokunmadan.
_GLOSSARY_WORD_RE = re.compile(r"[^\W\d_]+", re.UNICODE)
_GLOSSARY_WQX_CHAR_RE = re.compile(r"[wqxWQX]")
_GLOSSARY_GUARD_TURKISH_TARGETS = frozenset({"tr", "tur", "turkish", "türkçe", "turkce"})



_TR_APOSTROPHIC_SUFFIXES = frozenset({
    "in", "\u0131n", "un", "\u00fcn", "nin", "n\u0131n", "nun", "n\u00fcn",
    "de", "da", "te", "ta", "den", "dan", "ten", "tan",
    "e", "a", "ye", "ya", "i", "\u0131", "u", "\u00fc", "yi", "y\u0131", "yu", "y\u00fc",
    "le", "la", "yle", "yla", "ler", "lar", "li", "l\u0131", "lu", "l\u00fc",
    "lik", "l\u0131k", "luk", "l\u00fck"
})


def _glossary_token_matches_key(word: str, key_tokens: set[str], raw_value: str = "") -> bool:
    w = str(word or "").strip()
    wl = w.lower()
    if not wl:
        return False

    if wl in key_tokens:
        return True

    for suff in _TR_APOSTROPHIC_SUFFIXES:
        if wl.endswith(suff):
            stem = wl[:-len(suff)]
            if stem in key_tokens:
                return True

    if (wl + "s") in key_tokens and raw_value:
        pattern = re.compile(rf"\b{re.escape(w)}['\u2019]([a-z\u00e7\u011f\u0131\u00f6\u015f\u00fcA-Z\u00c7\u011e\u0130\u00d6\u015e\u00dc]+)", re.IGNORECASE)
        m = pattern.search(raw_value)
        if m:
            suff = m.group(1).lower()
            if suff in _TR_APOSTROPHIC_SUFFIXES:
                return True

    return False

def _glossary_wqx_token(value: str, glossary_key: str | None = None) -> str | None:
    """R_wqx: Türk alfabesinde q/w/x yoktur. `value` içindeki bu harfleri taşıyan
    ilk kelimeyi döner — TEK kelimelik + büyük-harfle-başlayan hedefler hariç
    (gerçek özel isim/marka: Washington, Xerox, WhatsApp). Çok-kelimeli bir hedefte
    w/q/x varsa özel isim değil, yabancı dil sızıntısıdır (bkz. Adım 1,
    plans/sozluk-hedef-dil-guard-brief.md).

    `glossary_key` verilirse (yalnızca sözlük sanitize yolundan çağrılınca):
    büyük-harfle-başlayan VE kaynakta (anahtarda) aynen geçen w/q/x'li kelimeler
    de hariç tutulur. Gerçek olay (2 Louis Theroux belgeseli, 2026-07-20):
    "North Side of Milwaukee"->"Milwaukee'nin Kuzey Yakası", "Milwaukee PD"->
    "Milwaukee Polis Teşkilatı", "SWAT team"->"SWAT ekibi" gibi DÜZGÜN ÇEVRİLMİŞ
    çok kelimeli hedefler, içlerinde kaynaktan aynen korunmuş bir özel isim
    (Milwaukee, SWAT) taşıdıkları için tek-kelime istisnasına (yukarısı, apostrof
    kesme işareti kelime karakteri sayılmadığından "Milwaukee'nin" iki token'a
    bölünüyor) hiç uymuyor ve TÜM sözlüğü (30-32 terim) götürüyordu."""
    words = _GLOSSARY_WORD_RE.findall(str(value or ""))
    if not words:
        return None
    hits = [w for w in words if _GLOSSARY_WQX_CHAR_RE.search(w)]
    if not hits:
        return None
    if len(words) == 1 and hits[0][:1].isupper():
        return None  # tek-kelime + büyük harf: gerçek özel isim/marka olabilir
    if glossary_key is not None:
        key_tokens = {w.lower() for w in _GLOSSARY_WORD_RE.findall(str(glossary_key or ""))}
        non_hits = [w for w in words if not _GLOSSARY_WQX_CHAR_RE.search(w)]
        if (
            non_hits
            and all(w[:1].isupper() for w in words)
            and all(w.lower() in key_tokens for w in non_hits)
        ):
            return None
        # Apostroflu Türkçe ek bağlamı, çoğul kaynak anahtarın tekil kökünü güvenle
        # korur ("Newsweeks" -> "Newsweek'ler"). Gerçek olay (rough.treatment.1978,
        # 2026-07-20): apostrof kelimeyi böldüğü için exact-match istisnası tutmadı
        # ve 50 terimlik sözlük komple gitti.
        hits = [
            w for w in hits
            if not (
                w[:1].isupper()
                and _glossary_token_matches_key(w, key_tokens, raw_value=value)
            )
        ]
        if not hits:
            return None
    return hits[0]


def _glossary_target_is_source_kept_asis(key: str, value: str) -> bool:
    """Hedef, kaynağın kendi kelimelerinin AYNISI mı (sırası değişmiş olsa da)?
    Gerçek olay (2026-07-20, 4 Louis Theroux belgeseli art arda): "Joe Exotic"->
    "Joe Exotic", "GW Exotic Animal Park"->"GW Exotic Animal Park", "Wynnewood,
    Oklahoma"->"Oklahoma, Wynnewood", "Daniella Weiss"->"Daniella Weiss", "West
    Block"->"West Block" gibi ÇOK KELİMELİ özel isimler (kişi/kurum/yer adı) hiç
    çevrilmeden aynen bırakıldığı için R_wqx'i tetikleyip TÜM sözlüğü (42-77
    terim) götürüyordu -- tek-kelimelik-özel-isim istisnası (yukarısı) çok dar,
    yalnızca "Washington" gibi TEK kelimeyi kapsıyor. Kaynakla hedefin kelime
    kümesi birebir aynıysa hiçbir çeviri olmamış demektir -- bu YABANCI DİLE
    SÜRÜKLENME değil, bilinçli "bu özel ismi çevirme" kararıdır; w/q/x harfi
    olması kaynağın kendi İngilizce harfleri olduğu için anlamsızdır."""
    def _tokens(s):
        return frozenset(_GLOSSARY_WORD_RE.findall(str(s or "").lower()))
    key_tokens = _tokens(key)
    return bool(key_tokens) and key_tokens == _tokens(value)


_PRESERVED_TERM_TR_SUFFIXES = frozenset({
    "i", "ı", "u", "ü", "yi", "yı", "yu", "yü", "e", "a", "ye", "ya",
    "de", "da", "te", "ta", "den", "dan", "ten", "tan",
    "in", "ın", "un", "ün", "nin", "nın", "nun", "nün",
    "le", "la", "yle", "yla", "ler", "lar",
})


def _source_preserves_latin_extended_token(token: str, source_text: str) -> bool:
    value = str(token or "").strip(".,;:!?()[]{}\"'“”‘’<>-–—").casefold()
    if not value or not source_text:
        return False
    for source_token in _GLOSSARY_WORD_RE.findall(str(source_text)):
        source_value = source_token.casefold()
        if value == source_value:
            return True
        if value.startswith(source_value) and value[len(source_value):] in _PRESERVED_TERM_TR_SUFFIXES:
            return True
    return False


def non_turkish_leak_token(text: str, *, glossary_target: bool = False,
                            glossary_key: str | None = None,
                            source_text: str = "") -> str | None:
    """Return the first concrete token that trips the non-Turkish-target-leak
    detector, or None if the text is clean. Single source of truth for
    has_non_turkish_target_leak — also used to name the offending word in
    retry/log messages so a false-positive vs. a real leak can be told apart
    without re-reading the whole line.
    """
    value = normalize_latin_homoglyphs(str(text or ""))
    m = _FOREIGN_SCRIPT_RE.search(value)
    if m:
        return m.group(0)
    m = _TURKIC_DRIFT_RE.search(value)
    if m:
        return m.group(0)
    if not _LATIN_EXTENDED_CHAR_RE.search(value):
        if glossary_target:
            token = _glossary_wqx_token(value, glossary_key=glossary_key)
            if token:
                return token
        return None
    for match in _TOKEN_WITH_LATIN_EXTENDED_RE.finditer(value):
        token = match.group(0).strip(".,;:!?()[]{}\"' “”‘’»<>")
        if not any(
            "\u00C0" <= ch <= "\u024F" and ch not in _TARGET_TURKISH_LATIN_ALLOW
            for ch in token
        ):
            continue
        # Proper names can legitimately preserve Latin diacritics (Buñuel, Juárez, Björk).
        # Lowercase tokens with these characters are almost always target-language drift.
        if token[:1].isupper():
            continue
        if _source_preserves_latin_extended_token(token, source_text):
            continue
        return token
    if glossary_target:
        token = _glossary_wqx_token(value, glossary_key=glossary_key)
        if token:
            return token
    return None


def has_non_turkish_target_leak(text: str, *, glossary_target: bool = False,
                                 glossary_key: str | None = None,
                                 source_text: str = "") -> bool:
    """Detect non-Turkey-Turkish leaks that should never appear in Turkish output."""
    return non_turkish_leak_token(text, glossary_target=glossary_target,
                                  glossary_key=glossary_key,
                                  source_text=source_text) is not None


# ── Sözlük hedefinde gloss/talimat guard'ı (bkz. plans/sozluk-gloss-ve-half-sayi-brief.md) ──
# Üç filmde üst üste görülen ayrı bir sınıf: analiz geçişi hedef alanına ÇEVİRİ
# değil META-YORUM yazıyor -- 'Caesar (Sezar)', 'Bembem (özel ad, aynen
# korunacak)', 'görümce / yenge bağlama göre'. Ana model bunu ya satıra basıyor
# (Salome: 15 cue'da 'Caesar'ın (Sezar)' gibi parantezli kalıntı) ya da tutarsız
# biçimde telafi etmeye çalışıyor.
#
# POLİTİKA FARKI — R_wqx (yukarıdaki whole-glossary-drop) İLE KARIŞTIRMA:
#   - R_wqx: TÜM sözlüğü atar, çünkü tetikleyen sinyal TOPLU DİL ÇÖKMESİdir
#     (model bambaşka bir dile -- Somalice vb. -- kaymış).
#   - Bu guard: SADECE o TERİMİ atar, çünkü model Türkçe ÜRETMİŞTİR -- sadece iki
#     seçenek arasında karar veremeyip kaynağı parantez/eğik çizgiyle hedefe
#     sızdırmıştır. Diğer terimler bu durumdan etkilenmiş olmak zorunda değildir.
#   - Kurtarmaya ÇALIŞILMAZ: 'Caesar (Sezar)' -> hedef "Caesar" mı "Sezar" mı
#     belirsiz. Terimi atmak güvenlidir -- model sözlüksüz kaldığında zaten
#     doğrusunu buluyor (Salome'de sözlüksüz cue'larda serbestçe "Sezar" demiş).
_GLOSSARY_GLOSS_BRACKET_RE = re.compile(r"[()\[\]]")
# Eğik çizgi kuralı yalnızca BOŞLUKLU " / " biçimini yakalar (seçenek ayırıcısı);
# bitişik "AC/DC", "24/7" gibi gerçek terimler yanlış-pozitif almasın diye.
_GLOSSARY_GLOSS_SLASH_RE = re.compile(r"\s/\s")
_GLOSSARY_META_CLAUSE_RE = re.compile(
    r";\s*(?:bağlama\s+göre|spiritüel\s+bağlamda|italik\b|çeviri\s+yok\b)",
    re.IGNORECASE,
)


def _glossary_gloss_or_instruction_marker(value: str) -> str | None:
    """Hedefte çeviri değil gloss/talimat sızıntısı var mı? Varsa kısa bir
    gerekçe etiketi, yoksa None döner. Yalnızca HEDEF için -- kaynaktaki
    parantezlere bu fonksiyon hiç bakmaz (çağıran yalnızca value'yu verir)."""
    value_s = str(value or "")
    if _GLOSSARY_GLOSS_BRACKET_RE.search(value_s):
        return "parantez/köşeli-parantez gloss"
    if _GLOSSARY_GLOSS_SLASH_RE.search(value_s):
        return "eğik çizgili seçenek"
    if _GLOSSARY_META_CLAUSE_RE.search(value_s):
        return "noktalı virgüllü talimat"
    return None


# ── Sözlük hedefinde uzun meta-yorum guard'ı (üçüncü, ayrı sınıf) ─────────────
# Gerçek olay (The Shivering Truth S01E02, 2026-07-19): analiz geçişi 'maggot'
# için ÇEVİRİ değil bir NASIL-ÇEVRİLMELİ notu yazdı: "qurt/qurtçuk değil; askerî
# hakaret olarak mecazi 'pislik'/'larva' yerine doğrudan 'çürük kurt' anlamı
# vermeden, komik ve aşağılayıcı askerî hakaret olarak çevrilmeli: ... yerleşik
# karşılığı yoksa açıklamasız bırakılabilir." Bu notun içindeki "qurt" (muhtemelen
# "kurt" yazım kayması) R_wqx'i tetikledi ve TÜM sözlük atıldı -- 'sir'->'komutanım',
# 'Private'->'er', 'Sergeant'->'çavuş', 'church'->'kilise' gibi dört tertemiz terim
# de beraberinde gitti. Sonuç: 'church' çıktıda 3 kez HİÇ ÇEVRİLMEDEN kaldı.
#
# Ayırt edici sinyal UZUNLUK: gerçek bir sözlük değeri (tek kelimelik terim de
# olsa, çok-kelimeli bir deyim çevirisi de olsa) kısadır -- bugüne dek görülen
# HİÇBİR gerçek terim (5 farklı dosyada) 7 kelimeyi geçmedi. Meta-yorumlar/notlar
# 25-50+ kelime sürer. Bu kontrol wqx taramasından ÖNCE çalışır ve tetiklenirse
# `continue` eder -- yani böyle bir notun içindeki kazara yabancı harf, hiçbir
# zaman `wqx_hits`e ulaşmaz ve whole-glossary-drop'u tetikleyemez. Yalnızca O
# terim tek-başına düşürülür (politika: bkz. yukarıdaki R_wqx/gloss ayrımı --
# burası da "sadece bu terim" tarafında, "tüm sözlük" tarafında değil).
_GLOSSARY_VERBOSE_WORD_THRESHOLD = 10
_ROMAN_NUMERAL_RE = re.compile(
    r"M{0,4}(?:CM|CD|D?C{0,3})(?:XC|XL|L?X{0,3})(?:IX|IV|V?I{0,3})"
)


def _glossary_verbose_meta_commentary_marker(value: str) -> str | None:
    """Paragraf uzunluğunda meta-yorum/talimat mı (çeviri değil)? Varsa kısa bir
    gerekçe etiketi, yoksa None döner."""
    words = str(value or "").split()
    if len(words) > _GLOSSARY_VERBOSE_WORD_THRESHOLD:
        return "uzun açıklama/not (çeviri değil)"
    return None


def _roman_numeral_value(value: str) -> int | None:
    text = str(value or "").strip().upper()
    if len(text) < 4 or not _ROMAN_NUMERAL_RE.fullmatch(text):
        return None
    values = {"I": 1, "V": 5, "X": 10, "L": 50, "C": 100, "D": 500, "M": 1000}
    total = 0
    for pos, char in enumerate(text):
        number = values[char]
        total += -number if pos + 1 < len(text) and number < values[text[pos + 1]] else number
    return total


def sanitize_glossary_for_turkish(glossary: dict | None, target_language: str = "tr",
                                   log_fn=None) -> dict:
    """Drop glossary targets that would force non-Turkish/Turkic drift into the output.

    target_language: the guard is Turkish-specific (Turkish-alphabet / Turkic-drift
    checks are meaningless for other targets) — for any other target the glossary
    is returned unmodified.

    Beyond the existing per-term filtering, a term whose target trips R_wqx
    (Turkish has no q/w/x) causes the WHOLE glossary to be dropped, not just that
    term. Real incident (The Blood of Hussain, 2026-07-16): an analysis pass
    drifted into Somali for EVERY term in the glossary at once, including terms
    that individually look harmless to the other 3 checks (no foreign script, no
    drift-list word, no diacritic) — e.g. "Bangiga Adduunka" for World Bank, or
    "mu'addinka" for Muezzin. One unmistakably-foreign term (R_wqx) is a reliable
    sign the whole batch collapsed into another language; dropping it all is
    cheap -- the model still translates the term on its own (e.g. "Armed Forces"
    -> "Silahli Kuvvetler") -- versus letting a wrong language spread through the
    file. See plans/sozluk-hedef-dil-guard-brief.md.
    """
    if not isinstance(glossary, dict):
        return {}
    tgt = str(target_language or "tr").strip().lower()
    if tgt not in _GLOSSARY_GUARD_TURKISH_TARGETS:
        return {str(k): str(v) for k, v in glossary.items() if k and v}

    cleaned = {}
    dropped_terms = {}
    gloss_dropped_terms = {}
    wqx_hits = {}
    for key, value in glossary.items():
        if not key or not value:
            continue
        value_s = str(value)
        roman_value = _roman_numeral_value(str(key))
        if roman_value is not None and value_s.strip().isdigit() and int(value_s.strip()) != roman_value:
            if log_fn:
                log_fn(
                    f"Sozluk guard: yanlis Roma rakami donusumu duzeltildi: "
                    f"{key}->{value_s} yerine {roman_value}",
                    "warn",
                )
            value_s = str(roman_value)
        # Uzun meta-yorum kontrolü EN ÖNCE çalışır ve tetiklenirse `continue` eder --
        # böylece notun içindeki kazara yabancı harf wqx_hits'e hiç ulaşmaz ve
        # whole-glossary-drop'u tetikleyemez (bkz. yukarıdaki blok yorumu).
        verbose_reason = _glossary_verbose_meta_commentary_marker(value_s)
        if verbose_reason:
            gloss_dropped_terms[str(key)] = (value_s, verbose_reason)
            continue
        # Kaynağın kendi kelimeleri aynen (özel isim) kaldıysa hiçbir dil-sızıntı
        # kontrolü çalıştırılmaz -- ne wqx ne de non_turkish_leak_token. Bkz.
        # yukarıdaki _glossary_target_is_source_kept_asis blok yorumu.
        if _glossary_target_is_source_kept_asis(key, value_s):
            cleaned[str(key)] = value_s
            continue
        if _glossary_wqx_token(normalize_latin_homoglyphs(value_s), glossary_key=key) is not None:
            wqx_hits[str(key)] = value_s
        if has_non_turkish_target_leak(value_s, glossary_target=True, glossary_key=key):
            dropped_terms[str(key)] = value_s
            continue
        gloss_reason = _glossary_gloss_or_instruction_marker(value_s)
        if gloss_reason:
            # SADECE bu terim atılır -- whole-glossary-drop DEĞİL (bkz. yukarıdaki
            # politika-farkı yorumu). wqx_hits zaten yukarıda unconditional
            # toplandığı için, bu terimde AYRICA q/w/x varsa whole-glossary-drop
            # yine de kazanır (aşağıdaki "if wqx_hits" kontrolü).
            gloss_dropped_terms[str(key)] = (value_s, gloss_reason)
            continue
        cleaned[str(key)] = value_s

    if wqx_hits:
        if log_fn:
            pairs = ", ".join(f"{k}->{v}" for k, v in wqx_hits.items())
            log_fn(
                "Sozluk guard: Turkce'de olmayan q/w/x harfi tasiyan hedef terim "
                f"bulundu ({pairs}); SOZLUGUN TAMAMI ({len(glossary)} terim) atildi "
                "-- yanlis sozlukten iyidir.",
                "warn",
            )
        return {}

    if dropped_terms and log_fn:
        pairs = ", ".join(f"{k}->{v}" for k, v in dropped_terms.items())
        log_fn(f"Sozluk guard: supheli/yabanci hedef nedeniyle atilan terim(ler): {pairs}", "warn")

    if gloss_dropped_terms and log_fn:
        pairs = ", ".join(f"{k}->{v} ({reason})" for k, (v, reason) in gloss_dropped_terms.items())
        log_fn(
            "Sozluk guard: hedef alaninda ceviri degil aciklama/secenek bulundu, "
            f"SADECE bu terim(ler) atildi (sozlugun geri kalani korunur): {pairs}",
            "warn",
        )
    return cleaned


def quality_glossary_for_source(text: str) -> dict:
    """Small fixed terminology guard for common subtitle traps seen in QA."""
    text_l = str(text or "").lower()
    return {
        src: tgt
        for src, tgt in _COMMON_TURKISH_TERM_GUARD
        if term_in_text(src, text_l)
    }


_EXPLICIT_SOURCE_YES_RE = re.compile(r"^\s*(?:[-–—]\s*)?(?:yes|oui|ja|sí|sì)\b", re.IGNORECASE)
_EXPLICIT_SOURCE_NO_RE = re.compile(r"^\s*(?:[-–—]\s*)?(?:no|non|nein)\b", re.IGNORECASE)
_EXPLICIT_TURKISH_YES_RE = re.compile(r"^\s*(?:[-–—]\s*)?evet\b", re.IGNORECASE)
_EXPLICIT_TURKISH_NO_RE = re.compile(r"^\s*(?:[-–—]\s*)?hayır\b", re.IGNORECASE)


def _has_explicit_answer_polarity_flip(source_text: str, translated_text: str) -> bool:
    src = str(source_text or "")
    tr = str(translated_text or "")
    return bool(
        (_EXPLICIT_SOURCE_YES_RE.search(src) and _EXPLICIT_TURKISH_NO_RE.search(tr))
        or (_EXPLICIT_SOURCE_NO_RE.search(src) and _EXPLICIT_TURKISH_YES_RE.search(tr))
    )


def _common_term_mistranslation_reasons(source_text: str, translated_text: str) -> list[str]:
    src = str(source_text or "").lower()
    tr = str(translated_text or "").lower()
    reasons = []
    if _has_explicit_answer_polarity_flip(source_text, translated_text):
        reasons.append("EXPLICIT_ANSWER_POLARITY_FLIP")
    if re.search(r"\b(?:holiday|holidays)\b", src) and re.search(r"holidaý|bäýram|oturyly", tr):
        reasons.append("TERM_MISTRANSLATION:holiday")
    if re.search(r"\bcenterpiece\b", src) and re.search(r"ortadagy|bezeg", tr):
        reasons.append("TERM_MISTRANSLATION:centerpiece")
    if re.search(r"\btaxiderm(?:y|ist)\b", src) and re.search(r"taksidermiya", tr):
        reasons.append("TERM_MISTRANSLATION:taxidermy")
    if re.search(r"\bautomatonophobia\b", src) and re.search(r"\bavtomatonofobi", tr):
        reasons.append("TERM_MISTRANSLATION:automatonophobia")
    if re.search(r"\bventriloqu", src) and re.search(r"\bventriloq", tr):
        reasons.append("TERM_MISTRANSLATION:ventriloquism")
    if re.search(r"\bventriloquist", src) and re.search(r"\bventriloquist", tr):
        reasons.append("TERM_MISTRANSLATION:ventriloquist")
    if re.search(r"\b(?:exploded skull|skull preparation)\b", src) and re.search(
        r"k[əƏ]ll[əƏ]|patlatılmış\s+k[âa]se|partlatılmış", tr
    ):
        reasons.append("TERM_MISTRANSLATION:exploded_skull")
    if re.search(r"\bchiropractor\b", src) and re.search(r"\bchiropraktör", tr):
        reasons.append("TERM_MISTRANSLATION:chiropractor")
    if re.search(r"\b(?:polio\s+)?braces\b", src) and re.search(r"\bbrasek", tr):
        reasons.append("TERM_MISTRANSLATION:braces")
    if re.search(r"\bmortuary\b", src) and re.search(r"\bmortuary\b", tr):
        reasons.append("TERM_MISTRANSLATION:mortuary")
    if re.search(r"\bwound[-\s]+filler\b", src) and re.search(r"\bwound[-\s]+filler", tr):
        reasons.append("TERM_MISTRANSLATION:wound_filler")
    if re.search(r"\bsideshow\b", src) and re.search(r"\bsideshow", tr):
        reasons.append("TERM_MISTRANSLATION:sideshow")
    if re.search(r"\bbody[-\s]+modification\b", src) and re.search(r"\bbody[-\s]+modification", tr):
        reasons.append("TERM_MISTRANSLATION:body_modification")
    if re.search(r"\bcollection\b", src) and re.search(r"\bcollection['’]?(?:ı|i|u|ü|n|nda|nde)", tr):
        reasons.append("TERM_MISTRANSLATION:collection")
    if re.search(r"\brat\b", src) and re.search(r"\brat(?:['’]?[a-zçğıöşü]+)?\b", tr):
        reasons.append("TERM_MISTRANSLATION:rat")
    if re.search(r"\bclient\b", src) and re.search(r"\bclient(?:['’]?[a-zçğıöşü]+)?\b", tr):
        reasons.append("TERM_MISTRANSLATION:client")
    if re.search(r"\bmacabre\b", src) and re.search(r"\bmacabre(?:\s+mobile)?(?:['’]?[a-zçğıöşü]+)?\b", tr):
        reasons.append("TERM_MISTRANSLATION:macabre")
    if re.search(r"\bmedical\s+stuff\b", src) and re.search(r"\blukmançylyk|degişli\s+zatlar", tr):
        reasons.append("TERM_MISTRANSLATION:medical_stuff")
    if re.search(r"\bcoroner['’]s\s+(?:office|gurney|table|tools)\b", src) and re.search(
        r"\b(?:coroner|koroner)['’]s\b|\bgurney\b|\btable\b", tr
    ):
        reasons.append("TERM_MISTRANSLATION:coroner_equipment")
    if re.search(r"\bhunting\s+and\s+picking\b", src) and re.search(r"\bhunter\s+ve\b", tr):
        reasons.append("TERM_MISTRANSLATION:hunting_picking")
    if re.search(r"\blife\s+mask\b", src) and re.search(r"\bölüm\s+maskesi\b|\bölüm maskesi\b", tr):
        reasons.append("TERM_MISTRANSLATION:life_mask")
    if re.search(r"\borreries?\b", src) and re.search(r"\boreriler\b|\borreries?\b", tr):
        reasons.append("TERM_MISTRANSLATION:orrery")
    if re.search(r"\belectromagnets?\b", src) and re.search(r"\belektromıknatısların\s+açabiliyorum\b", tr):
        reasons.append("TERM_MISTRANSLATION:electromagnet_flow")
    if re.search(r"\bmummy\b", src) and re.search(r"\bmummy\b", tr):
        reasons.append("TERM_MISTRANSLATION:mummy")
    if re.search(r"\bphallus\b", src) and re.search(r"\bphallus\b", tr):
        reasons.append("TERM_MISTRANSLATION:phallus")
    if re.search(r"\brepeat customer\b", src) and re.search(r"\brepeat customer\b", tr):
        reasons.append("TERM_MISTRANSLATION:repeat_customer")
    if re.search(r"\bauthentic\b", src) and re.search(r"\bauthentic\b", tr):
        reasons.append("TERM_MISTRANSLATION:authentic")
    if re.search(r"\buppercut\b", src) and re.search(r"\byükseltme\b", tr):
        reasons.append("TERM_MISTRANSLATION:uppercut")
    if re.search(r"\bgold leaf\b", src) and re.search(r"\bgold leaf\b", tr, re.IGNORECASE):
        reasons.append("TERM_MISTRANSLATION:gold_leaf")
    if re.search(r"\bgilding\b", src) and re.search(r"\bgilding\b", tr, re.IGNORECASE):
        reasons.append("TERM_MISTRANSLATION:gilding")
    if re.search(r"\bscars?\b", src) and re.search(r"\bjaal(?:im|imi|am|lar|ler)?\b", tr):
        reasons.append("TERM_MISTRANSLATION:scar")
    if re.search(r"\bcompetition piece\b", src) and re.search(r"bäseke", tr):
        reasons.append("TERM_MISTRANSLATION:competition_piece")
    if re.search(r"\b(?:reindeer|caribou)\b", src) and re.search(r"\bbuğu\b", tr):
        reasons.append("TERM_MISTRANSLATION:reindeer")
    if re.search(r"\bcash[-\s]+in[-\s]+hand\b", src) and re.search(r"\bnakit\s+bas\w*", tr):
        reasons.append("TERM_MISTRANSLATION:cash_in_hand")
    if re.search(r"\b(?:stay|stayed|staying|keep|kept)\s+under\s+(?:your\s+)?budget\b|\bunder\s+(?:your\s+)?budget\b", src) and re.search(
        r"\bbütçe\w*\s+aş(?:t[ıiuü]m|t[ıiuü]n|t[ıiuü]|mak|m[ıiuü]ş)", tr
    ):
        reasons.append("TERM_MISTRANSLATION:under_budget")
    if re.search(r"\bpupils?\b", src) and re.search(r"\bpupil(?:ler|l[ıiuü]|[ıiuü]|sin|s[ıiuü]n|sın|sun)?", tr):
        reasons.append("TERM_MISTRANSLATION:pupil")
    if re.search(r"\bfake\s+out\b", src) and re.search(r"\boyala\w*", tr):
        reasons.append("TERM_MISTRANSLATION:fake_out")
    if re.search(r"\bi['’]?m\s+flattered\b", src) and re.search(r"\bdüşündürüc", tr):
        reasons.append("TERM_MISTRANSLATION:flattered")
    return reasons


def _looks_like_dangling_turkish_fragment(text: str, fragment_tag: str | None = None) -> bool:
    """Heuristic for translated cue fragments that end as an object/modifier, not a sentence."""
    core = re.sub(r"<[^>]+>|\{[^}]+\}|\[[^\]]+\]", " ", str(text or ""))
    core = re.sub(r"^\s*[-–—]?\s*[^:\n]{1,40}:\s*", "", core).strip()
    core = re.sub(r"\s+", " ", core)
    if len(core.split()) < 2:
        return False
    if _TR_ODDITY_RE.search(core):
        return True
    tag = fragment_tag or "none"
    if tag in {"end", "none"} and _DANGLING_FRAGMENT_TAIL_RE.search(core):
        return True
    if tag not in {"start", "mid"}:
        return False
    if re.search(r"\b(?:bazı|sanki)\s*$", core, re.IGNORECASE):
        return True
    if _looks_like_early_turkish_verb_closure(core):
        return False
    tail = re.sub(r'''["' “”‘’»«…)\].,!?;:]+$''', "", core).split()[-1].lower()
    if tail in {"ve", "veya", "ya", "ama", "fakat", "çünkü", "ki", "ile", "için", "gibi"}:
        return True
    if len(tail) < 4:
        return False
    return bool(re.search(
        r"(?:mek|mak|ma|me|mayı|meyi|dığı|diği|duğu|düğü|acağını|eceğini|"
        r"den|dan|ten|tan|de|da|e|a|ı|i|u|ü|nı|ni|nu|nü|ını|ini|unu|ünü|"
        r"lar|ler|lı|li|lu|lü|sal|sel)$",
        tail,
        re.IGNORECASE,
    ))


_SPEAKER_PREFIX_RE = re.compile(
    r'^\s*(?:[-–—]\s*)?(?:\[[^\]]{1,80}\]\s*)?([^:\n]{1,80}):'
)


def _ascii_fold(value: str) -> str:
    return unicodedata.normalize("NFKD", value or "").encode("ascii", "ignore").decode("ascii")


def _speaker_label_prefix(text: str) -> str:
    first = str(text or "").splitlines()[0] if text else ""
    first = re.sub(r'^\s*(?:</?[a-zA-Z][^>]*>|\{[^}]*\})+', '', first).strip()
    m = _SPEAKER_PREFIX_RE.match(first)
    if not m:
        return ""
    label = m.group(1).strip()
    if not re.search(r'[^\W_]', label, re.UNICODE):
        return ""
    letters = "".join(ch for ch in label if ch.isalpha())
    folded = _ascii_fold(label).lower()
    first_word = folded.replace(".", " ").split()[0] if folded.replace(".", " ").split() else ""
    common = {"narrator", "man", "woman", "kadin", "adam", "anlatici", "doctor", "dr"}
    has_parenthetical = "(" in label or ")" in label
    has_title_dot = "." in label
    is_all_caps = bool(letters) and letters.upper() == letters
    if not (is_all_caps or has_parenthetical or has_title_dot or first_word in common):
        return ""
    return label


def _has_speaker_label(text: str) -> bool:
    return bool(_speaker_label_prefix(text))


def _speaker_label_and_rest(text: str) -> tuple[str, str]:
    lines = str(text or "").splitlines()
    first = lines[0] if lines else ""
    first = re.sub(r'^\s*(?:</?[a-zA-Z][^>]*>|\{[^}]*\})+', '', first).strip()
    match = _SPEAKER_PREFIX_RE.match(first)
    if not match:
        return "", ""
    label = _speaker_label_prefix(first)
    if not label:
        raw_label = match.group(1).strip()
        words = raw_label.replace(".", " ").split()
        nameish = (
            1 <= len(words) <= 4
            and any(ch.isalpha() for ch in raw_label)
            and all((word[:1].isupper() or word.isupper()) for word in words)
        )
        if not nameish:
            return "", ""
        label = raw_label
    rest = first[match.end():].strip()
    if len(lines) > 1:
        rest = (rest + "\n" + "\n".join(lines[1:])).strip()
    return label, rest


def _speaker_label_absorbed_text(src_text: str, tr_text: str) -> bool:
    src_label, src_rest = _speaker_label_and_rest(src_text)
    if not src_label or _has_wordlike_text(src_rest):
        return False
    tr_label, tr_rest = _speaker_label_and_rest(tr_text)
    return bool(tr_label and _has_wordlike_text(tr_rest))


def _semantic_text_for_validator(text: str) -> str:
    s = re.sub(r'</?[a-zA-Z][^>]*>', '', str(text or ''))
    s = re.sub(r'\{[^}]*\}', '', s)
    s = re.sub(r'\([^)]*\)|\[[^\]]*\]|[\u266a_]+', '', s)
    return s.strip()


def _has_wordlike_text(text: str) -> bool:
    return bool(re.search(r'[^\W_]', text or '', re.UNICODE))


def _is_punct_only_translation(src_text: str, tr_text: str) -> bool:
    src_sem = _semantic_text_for_validator(src_text)
    if not _has_wordlike_text(src_sem):
        return False
    tr_sem = _semantic_text_for_validator(tr_text)
    return not _has_wordlike_text(tr_sem)


def _length_ratio_outlier(src_text: str, tr_text: str) -> bool:
    src_sem = _semantic_text_for_validator(src_text)
    tr_sem = _semantic_text_for_validator(tr_text)
    if len(src_sem) <= 4 or not tr_sem:
        return False
    ratio = len(tr_sem) / max(len(src_sem), 1)
    return ratio < 0.12 or ratio > 5.0


def _has_source_negation(text: str) -> bool:
    src = _semantic_text_for_validator(text)
    return bool(_SOURCE_NEGATION_RE.search(src))


def _source_negation_requires_turkish_negation(text: str) -> bool:
    """True when source negation must remain visibly negative in Turkish.

    Some English idioms look negative but are naturally affirmative in Turkish
    ("can't wait" -> "sabirsizlaniyorum"). Keep those out of hard validators.
    """
    src = _semantic_text_for_validator(text)
    if re.search(r"\b(?:cannot|can\s+not|can['\u2019]?t)\s+wait\b", src, re.IGNORECASE):
        return False
    return _has_source_negation(src)


def _has_turkish_negation(text: str) -> bool:
    tr = _semantic_text_for_validator(text)
    if _TURKISH_NEGATION_WORD_RE.search(tr):
        return True
    if _BARE_NEGATIVE_IMPERATIVE_RE.search(tr):
        return True
    words = re.findall(r"[^\W\d_]+", tr.lower(), re.UNICODE)
    return any(_TURKISH_NEGATION_SUFFIX_RE.search(word) for word in words)


def _question_mark_mismatch(src_text: str, tr_text: str) -> bool:
    src = _semantic_text_for_validator(src_text)
    tr = _semantic_text_for_validator(tr_text)
    if "?" in src:
        return "?" not in tr
    if "?" not in tr:
        return False
    return not _SOURCE_INTERROGATIVE_RE.search(src)


def _normalized_numeric_tokens(text: str) -> list[str]:
    value = _semantic_text_for_validator(text)
    return [m.group(0).replace(",", ".") for m in _NUMERIC_TOKEN_RE.finditer(value)]


def _numeric_token_mismatch(src_text: str, tr_text: str) -> bool:
    src_nums = _normalized_numeric_tokens(src_text)
    if not src_nums:
        return False
    tr_nums = _normalized_numeric_tokens(tr_text)
    remaining = list(tr_nums)
    for token in src_nums:
        if token not in remaining:
            return True
        remaining.remove(token)
    return False


# ── Yazıyla yazılmış sayı tespiti (bkz. plans/yaziyla-sayi-tespiti-brief.md) ──
# _numeric_token_mismatch yalnızca RAKAM görür ("1400"); "fourteen hundred" gibi
# yazıyla yazılmış sayılar bu validator'ın kavram uzayında yoktu (#384: "fourteen
# hundred years ago" -> "on dört yüz yıl önce", doğrusu "bin dört yüz"). Bu blok
# TRİYAJ amaçlıdır — düzeltmez, yalnızca run_validators'a SPELLED_NUMBER_MISMATCH
# reason'ı ekler; karar Critic Pass'a (LLM) bırakılır. validate_polish_candidate'a
# BİLEREK dokunulmadı (tests/test_polish_safety.py "source_numbers" reason'ını
# assertEqual ile kilitliyor).
_EN_NUMBER_WORDS = {
    "zero": 0, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
    "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10,
    "eleven": 11, "twelve": 12, "thirteen": 13, "fourteen": 14,
    "fifteen": 15, "sixteen": 16, "seventeen": 17, "eighteen": 18,
    "nineteen": 19, "twenty": 20, "thirty": 30, "forty": 40,
    "fifty": 50, "sixty": 60, "seventy": 70, "eighty": 80, "ninety": 90,
    "hundred": 100, "thousand": 1000, "million": 10 ** 6, "billion": 10 ** 9,
}
_EN_NUMBER_MULTIPLIERS = frozenset({"hundred", "thousand", "million", "billion"})
_EN_NUMBER_WORD_TOKEN_RE = re.compile(r"[A-Za-z]+")


def _en_number_group_value(group: list) -> int:
    """Bir ardışık İngilizce sayı-sözcüğü grubunu tek bir tamsayıya çevirir.
    'fourteen hundred' -> 1400 (çarpım); 'one hundred twenty' -> 120 (toplama);
    'two thousand' -> 2000."""
    result = 0
    current = 0
    for word in group:
        if word in ("a", "an"):
            current += 1
            continue
        value = _EN_NUMBER_WORDS[word]
        if value == 100:
            current = (current or 1) * value
        elif value >= 1000:
            result += (current or 1) * value
            current = 0
        else:
            current += value
    return result + current


def _en_spelled_numbers(text: str) -> list:
    """Ardışık İngilizce sayı sözcüklerini gruplayıp değere çevirir.
    'fourteen hundred' -> [1400]; 'thirteen wounds' -> [13]; 'twenty-five' -> [25]
    (tire otomatik olarak ayrı kelime sayılır); sayı sözcüğü yoksa [].

    Muhafazakar filtre: yalnızca çarpan (hundred/thousand/million/billion) içeren
    VEYA >=2 sözcüklü VEYA >12 değerli gruplar raporlanır — tek başına 'one'/'two'
    gibi belirteç kullanımları (ör. 'one of them') atlanır.

    'half' (bkz. plans/sozluk-gloss-ve-half-sayi-brief.md, Salome #921): SADECE
    'half a <çarpan>' kalıbı belirsizliksizdir -> çarpan/2 ('half a hundred' -> 50,
    'half a thousand' -> 500). Bunun dışındaki HER 'half' kullanımı (ör. 'half the
    kingdom' zaten sayı sözcüğü içermediği için doğal olarak [], 'half a dozen'
    'dozen' desteklenmediği için doğal olarak [], ama 'one and a half hundred'
    gibi tuhaf sıralamalar ayrıca bastırılmalı) o grubu SESSİZCE atlar — tahmin
    yürütmek yerine [] dönmek güvenlidir, çünkü _spelled_number_mismatch kaynak
    boşsa hiç çalışmaz (bkz. onun docstring'i)."""
    tokens = [w.lower() for w in _EN_NUMBER_WORD_TOKEN_RE.findall(str(text or ""))]
    n = len(tokens)
    results = []
    i = 0
    while i < n:
        word = tokens[i]
        is_num = word in _EN_NUMBER_WORDS
        is_article = (
            word in ("a", "an") and i + 1 < n and tokens[i + 1] in _EN_NUMBER_MULTIPLIERS
        )
        if not (is_num or is_article):
            i += 1
            continue
        preceded_by_half = i > 0 and tokens[i - 1] == "half"
        group = [word]
        j = i + 1
        while j < n:
            nxt = tokens[j]
            if nxt in _EN_NUMBER_WORDS:
                group.append(nxt)
                j += 1
            elif nxt in ("a", "an") and j + 1 < n and tokens[j + 1] in _EN_NUMBER_MULTIPLIERS:
                group.append(nxt)
                j += 1
            else:
                break
        if preceded_by_half:
            if is_article:
                # 'half a hundred' / 'half a thousand' -> çarpan/2, belirsizlik yok.
                results.append(_en_number_group_value(group) // 2)
            # else: 'half hundred', 'one and a half hundred' gibi 'half a <çarpan>'
            # kalıbına UYMAYAN kullanımlar belirsizdir -> bu grubu sessizce atla.
            i = j
            continue
        value = _en_number_group_value(group)
        has_multiplier = any(g in _EN_NUMBER_MULTIPLIERS for g in group)
        if has_multiplier or len(group) >= 2 or value > 12:
            results.append(value)
        i = j
    return results


_TR_NUMBER_WORDS = {
    "sıfır": 0, "bir": 1, "iki": 2, "üç": 3, "dört": 4, "beş": 5,
    "altı": 6, "yedi": 7, "sekiz": 8, "dokuz": 9,
    "on": 10, "yirmi": 20, "otuz": 30, "kırk": 40, "elli": 50,
    "altmış": 60, "yetmiş": 70, "seksen": 80, "doksan": 90,
    "yüz": 100, "bin": 1000, "milyon": 10 ** 6, "milyar": 10 ** 9,
}
_TR_NUMBER_MULTIPLIERS = frozenset({"yüz", "bin", "milyon", "milyar"})
_TR_NUMBER_WORD_TOKEN_RE = re.compile(r"[^\W\d_]+", re.UNICODE)


def _tr_number_group_values(group: list) -> list:
    """Bir ardışık Türkçe sayı-sözcüğü grubunu bir veya daha fazla tamsayıya çevirir.

    KRİTİK: 'yüz' YALNIZCA tek haneli (1-9) bir katsayıyı çarpar — bu, gerçek
    Türkçe sayı grameri kısıtıdır ('dört yüz' geçerli, 'on dört yüz' geçersiz;
    1400 için tek doğru biçim 'bin dört yüz'dür). Bu yüzden 'on dört yüz' gibi
    gramer dışı bir sıralama TEK bir 1400 değeri ÜRETMEZ — [14, 100] gibi ayrı
    parçalar döner (bkz. plans/yaziyla-sayi-tespiti-brief.md, #384)."""
    values = []
    result = 0
    current = 0
    for word in group:
        value = _TR_NUMBER_WORDS[word]
        if word == "yüz":
            if 1 <= current <= 9:
                current = current * 100
            else:
                if current or result:
                    values.append(result + current)
                result = 0
                current = 100
        elif value >= 1000:
            result += (current or 1) * value
            current = 0
        else:
            current += value
    if current or result or not values:
        values.append(result + current)
    return values


def _tr_spelled_numbers(text: str) -> list:
    """Ardışık Türkçe sayı sözcüklerini gruplayıp değere çevirir.
    'bin dört yüz' -> [1400]. Ekli 'yüz'/'bir'/'bin' (yüzünü, birini, yüzden, ...)
    sayı DEĞİLDİR — tam kelime tokenizasyonu (regex kelime sınırları) bunu doğal
    olarak dışlar, çünkü 'yüzünü' tek bir token'dır ve 'yüz' sözlüğüyle birebir
    eşleşmez. Aynı muhafazakar filtre İngilizce tarafla (_en_spelled_numbers)
    tutarlıdır."""
    tokens = [w.lower() for w in _TR_NUMBER_WORD_TOKEN_RE.findall(str(text or ""))]
    n = len(tokens)
    results = []
    i = 0
    while i < n:
        if tokens[i] not in _TR_NUMBER_WORDS:
            i += 1
            continue
        j = i
        group = []
        while j < n and tokens[j] in _TR_NUMBER_WORDS:
            group.append(tokens[j])
            j += 1
        has_multiplier = any(g in _TR_NUMBER_MULTIPLIERS for g in group)
        for value in _tr_number_group_values(group):
            if has_multiplier or len(group) >= 2 or value > 12:
                results.append(value)
        i = j
    return results


def _digit_tokens_as_ints(text: str) -> list:
    """Metindeki rakam token'larını (ör. '1400', '1,400') tamsayıya çevirir —
    yazıyla sayının rakamla çevrilmiş halini (#384: '1400 yıl önce') kabul etmek
    için, böylece rakamla doğru çeviri yanlış-pozitif almaz."""
    values = []
    for tok in _normalized_numeric_tokens(text):
        digits = re.sub(r"\D", "", tok)
        if digits:
            try:
                values.append(int(digits))
            except ValueError:
                pass
    return values


def _spelled_number_mismatch(src_text: str, tr_text: str) -> bool:
    """Kaynakta yazıyla sayı varsa ('fourteen hundred'), çeviride aynı değer
    (yazıyla veya rakamla) yoksa True.

    KAYNAK-GÜTMELİ: kaynakta yazıyla sayı YOKSA hiç çalışmaz — Türkçede 'yüz'
    (100/face) ve 'bir' (1/a) tuzağını (bkz. _has_head_to_face_regression) bu
    şekilde susturur; çeviri tarafı asla taranmaz çünkü kaynakta zaten sayı yok."""
    src_vals = _en_spelled_numbers(src_text)
    if not src_vals:
        return False
    tr_vals = _tr_spelled_numbers(tr_text) + _digit_tokens_as_ints(tr_text)
    for val in src_vals:
        if val not in tr_vals:
            return True
    return False


def _turkish_register_marker(text: str) -> str:
    """Return explicit sen/siz marker when a line visibly uses one form."""
    value = _semantic_text_for_validator(text).lower()
    has_sen = bool(_SEN_REGISTER_RE.search(value))
    has_siz = bool(_SIZ_REGISTER_RE.search(value))
    if has_sen == has_siz:
        return ""
    return "sen" if has_sen else "siz"


def _has_bad_turkish_case_flow(text: str) -> bool:
    """Catch obvious genitive/object-case breaks such as 'elektromıknatısların açabiliyorum'."""
    value = _semantic_text_for_validator(text)
    return bool(_BAD_TURKISH_CASE_FLOW_RE.search(value))


# En→TR profanity intensity tiers (1=mild, 2=moderate, 3=strong, 4=vulgar)
_PROFANITY_INTENSITY_MAP = [
    (re.compile(r"\b(darn|heck|gosh|jeez|geez|oh my god)\b", re.I), 1),
    (re.compile(r"\b(damn|crap|hell|blast)\b", re.I), 2),
    (re.compile(r"\b(bitch|bastard|bullshit|screw|shoot|freaking)\b", re.I), 2),
    (re.compile(r"\b(holy shit|son of a bitch|what the fuck)\b", re.I), 3),
    (re.compile(r"\b(shit|ass|fuck|fucking|fucked|asshole|motherfucker)\b", re.I), 3),
    (re.compile(r"\bnigger\b", re.I), 4),
]


def _source_profanity_intensity(text: str) -> int:
    """Kaynak metindeki en yüksek profanity yoğunluğunu döndürür (0-4)."""
    val = str(text or "").lower()
    max_tier = 0
    for pat, tier in _PROFANITY_INTENSITY_MAP:
        if pat.search(val):
            max_tier = max(max_tier, tier)
    return max_tier


_TURKISH_PROFANITY_TR = {
    "lanet": 2, "kahretsin": 2, "cehennem": 2, "of be": 1,
    "sik": 3, "orospu": 3, "kaltak": 3, "göt": 3, "bok": 2,
    "amk": 4, "amına koyayım": 4, "aq": 4, "puşt": 4, "piç": 3,
    "ibne": 4, "yavşak": 3, "gavat": 4,
}


def _turkish_profanity_intensity(text: str) -> int:
    """Türkçe metindeki en yüksek profanity yoğunluğunu döndürür (0-4)."""
    val = str(text or "").lower()
    max_tier = 0
    for word, tier in _TURKISH_PROFANITY_TR.items():
        if word in val:
            max_tier = max(max_tier, tier)
    return max_tier


def run_validators(tr_blocks: list, cues: list = None, glossary: dict = None,
                   series_terms: dict = None) -> list:
    """Deterministic pre-check before Helper Critic Pass.
    Returns list of (idx, ts, text, reason_str) for lines needing review."""
    orig_dict: dict = {}
    orig_clean_dict: dict = {}
    speaker_by_id: dict = {}
    frag_tags: dict = {}
    frag_group_ids: dict = {}
    tr_text_by_id = {str(idx): text for idx, _ts, text in tr_blocks}
    if cues:
        for c in cues:
            clean = _clean_source_text(c.text)
            orig_clean_dict[str(c.index)] = clean
            orig_dict[str(c.index)] = clean.lower()
            speaker = _speaker_label_prefix(clean)
            if speaker:
                speaker_by_id[str(c.index)] = _ascii_fold(speaker).lower()
        try:
            frag_tags = _tag_fragments(cues)
            _group_by_idx, fragment_groups = _fragment_groups(cues, frag_tags)
            for group in fragment_groups:
                ids = [str(item) for item in group.get("items", []) if item is not None]
                for sid in ids:
                    frag_group_ids[sid] = ids
        except Exception:
            frag_tags = {}
            frag_group_ids = {}

    register_flips: dict[str, str] = {}
    if speaker_by_id:
        speaker_markers: dict[str, dict[str, int]] = {}
        marker_by_id: dict[str, str] = {}
        for idx, _ts, text in tr_blocks:
            sid = str(idx)
            speaker = speaker_by_id.get(sid)
            if not speaker:
                continue
            marker = _turkish_register_marker(text)
            if not marker:
                continue
            marker_by_id[sid] = marker
            counts = speaker_markers.setdefault(speaker, {"sen": 0, "siz": 0})
            counts[marker] += 1
        for sid, marker in marker_by_id.items():
            speaker = speaker_by_id.get(sid)
            counts = speaker_markers.get(speaker, {})
            other = "siz" if marker == "sen" else "sen"
            own_count = counts.get(marker, 0)
            other_count = counts.get(other, 0)
            total_count = own_count + other_count
            if total_count >= 4 and other_count >= 3 and own_count <= max(1, int(total_count * 0.25)):
                register_flips[sid] = f"REGISTER_FLIP:{marker}_against_{other}"

    suspicious = []
    for pos, (idx, ts, text) in enumerate(tr_blocks):
        if not text or text == "[HATA]" or "[ÇEVİRİ EKSİK]" in str(text):
            continue
        if _MUSIC_ONLY_RE.match(str(text).strip()):
            continue
        reasons = []

        if _EN_LEFTOVER.search(text):
            reasons.append("EN_LEFTOVER")

        if _ENGLISH_TURKISH_SUFFIX_LEFTOVER.search(text):
            reasons.append("EN_TURKISH_SUFFIX_LEFTOVER")

        if _SOURCE_LANG_LEFTOVER.search(text):
            reasons.append("SOURCE_LANG_LEFTOVER")

        if has_non_turkish_target_leak(text):
            reasons.append("NON_TURKISH_TARGET_LEAK")

        if _SFX_LEFTOVER_RE.search(text):
            reasons.append("SFX_LEFTOVER")

        if _TR_ODDITY_RE.search(text):
            reasons.append("TURKISH_ODDITY")

        if _has_bad_turkish_case_flow(text):
            reasons.append("BAD_TURKISH_CASE_FLOW")

        garble_hits = find_garble_tokens(text)
        if garble_hits:
            tokens = ",".join(dict.fromkeys(tok for tok, _rule in garble_hits))
            reasons.append(f"GARBLE_TOKEN({tokens})")

        # Single letter target: source has meaning but target is just "B" etc.
        stripped_tr = text.strip().strip(".,;:!?")
        if len(stripped_tr) == 1 and stripped_tr.isalpha():
            src = orig_clean_dict.get(str(idx), "")
            if len(src.split()) >= 3:
                reasons.append("SINGLE_LETTER_TARGET")

        orig_clean = orig_clean_dict.get(str(idx), "")
        if orig_clean:
            src_intensity = _source_profanity_intensity(orig_clean)
            tr_intensity = _turkish_profanity_intensity(text)
            if src_intensity >= 2 and tr_intensity == 0:
                reasons.append("PROFANITY_INTENSITY_MISMATCH")
            elif src_intensity > 0 and tr_intensity > 0 and abs(src_intensity - tr_intensity) >= 2:
                reasons.append("PROFANITY_INTENSITY_MISMATCH")
        if orig_clean:
            if _is_punct_only_translation(orig_clean, text):
                reasons.append("PUNCT_ONLY_TRANSLATION")
            if _length_ratio_outlier(orig_clean, text):
                reasons.append("LENGTH_RATIO_OUTLIER")
            if "(" in text and "(" not in orig_clean:
                reasons.append("PAREN_NOTE")
            if " / " in text and " / " not in orig_clean:
                reasons.append("ALT_SLASH")
            neg_src = orig_clean
            neg_tr = text
            group_ids = frag_group_ids.get(str(idx))
            if group_ids:
                neg_src = " ".join(
                    orig_clean_dict.get(gid, "") for gid in group_ids
                    if orig_clean_dict.get(gid, "") not in ("[HATA]", "[ÇEVİRİ EKSİK]")
                )
                neg_tr = " ".join(
                    tr_text_by_id.get(gid, "") for gid in group_ids
                    if tr_text_by_id.get(gid, "") not in ("[HATA]", "[ÇEVİRİ EKSİK]")
                )
            if _source_negation_requires_turkish_negation(neg_src) and not _has_turkish_negation(neg_tr):
                reasons.append("NEGATION_LOSS")
            if _question_mark_mismatch(orig_clean, text):
                reasons.append("QUESTION_MARK_MISMATCH")
            if _numeric_token_mismatch(orig_clean, text):
                reasons.append("NUMBER_MISMATCH")
            if _spelled_number_mismatch(orig_clean, text):
                reasons.append("SPELLED_NUMBER_MISMATCH")
            if _has_speaker_label(orig_clean) != _has_speaker_label(text):
                reasons.append("SPEAKER_LABEL_MISMATCH")
            if _speaker_label_absorbed_text(orig_clean, text):
                reasons.append("SPEAKER_LABEL_ABSORBED_TEXT")
            reasons.extend(_common_term_mistranslation_reasons(orig_clean, text))
            flip_reason = register_flips.get(str(idx))
            if flip_reason:
                reasons.append(flip_reason)

        tag = frag_tags.get(idx) or frag_tags.get(str(idx))
        if tag is None:
            try:
                tag = frag_tags.get(int(idx))
            except Exception:
                tag = None
        if tag in ("start", "mid") and _looks_like_early_turkish_verb_closure(text):
            reasons.append("EARLY_VERB_CLOSURE")
        if _looks_like_dangling_turkish_fragment(text, tag):
            reasons.append("DANGLING_TURKISH_FRAGMENT")

        if glossary and orig_dict:
            orig = orig_dict.get(str(idx), "")
            orig_lower = orig.lower()
            text_lower = text.lower()
            for src_term, tr_term in list(glossary.items()):
                if len(src_term) <= 4:
                    continue
                src_pat = r'\b' + re.escape(src_term.lower()) + r'\b'
                tr_pat  = r'\b' + re.escape(tr_term.lower()) + r'\b'
                if (re.search(src_pat, orig_lower)
                        and not re.search(tr_pat, text_lower)):
                    reasons.append(f"GLOSS_MISS:{src_term}=>{tr_term}")
                    break

        if series_terms and orig_dict:
            orig = orig_dict.get(str(idx), "")
            orig_lower = orig.lower()
            text_lower = text.lower()
            for src_term, tr_term in list(series_terms.items()):
                if len(src_term) <= 4:
                    continue
                src_pat = r'\b' + re.escape(src_term.lower()) + r'\b'
                tr_pat  = r'\b' + re.escape(tr_term.lower()) + r'\b'
                if (re.search(src_pat, orig_lower)
                        and not re.search(tr_pat, text_lower)):
                    reasons.append(f"SERIES_MEMORY_FLIP:{src_term}=>{tr_term}")
                    break

        if orig_dict:
            src_text = orig_dict.get(str(idx), "")
            if src_text and _has_idiom_come_in_at_price(src_text, text):
                reasons.append("IDIOM_MISTRANSLATION:come_in_at_price")
            if src_text and _has_orphan_fragment(src_text, text):
                reasons.append("ORPHAN_FRAGMENT")
            if src_text and _has_dar_person_drift(src_text, text):
                reasons.append("DAR_PERSON_DRIFT")
            if src_text and _has_reign_mistranslation(src_text, text):
                reasons.append("REIGN_MISTRANSLATION")
            if src_text and _has_idiom_holds_water(src_text, text):
                reasons.append("IDIOM_MISTRANSLATION:holds_water")
            if src_text and _has_dominates_missing_predicate(src_text, text):
                reasons.append("DOMINATES_MISSING_PREDICATE")
            if src_text and _has_short_source_overexpansion(src_text, text):
                reasons.append("SHORT_SOURCE_OVEREXPANSION")
            if src_text and _has_greek_word_explanation_loss(src_text, text):
                reasons.append("GREEK_WORD_EXPLANATION_LOSS")

        # FOX_SLOTH_INCONSISTENCY: tilki derisi in sloth context
        if _has_fox_sloth_inconsistency(text, tr_blocks, pos):
            reasons.append("FOX_SLOTH_INCONSISTENCY")

        # WEIRD_TURKISH_PHRASE: known unnatural Turkish patterns
        if re.search(r'\bderece\s+köylerine\b', text, re.IGNORECASE):
            reasons.append("WEIRD_TURKISH_PHRASE:derece_köylerine")

        # NEIGHBOR_ECHO: checked against the NEXT block (add for non-last items)
        if pos < len(tr_blocks) - 1 and _has_consecutive_echo(tr_blocks, pos):
            reasons.append("NEIGHBOR_ECHO")
        if pos < len(tr_blocks) - 1 and _has_neighbor_prefix_echo(tr_blocks, pos):
            reasons.append("NEIGHBOR_PREFIX_ECHO")
        if pos < len(tr_blocks) - 1 and _has_conjunction_fragment_spill(tr_blocks, pos):
            reasons.append("CONJUNCTION_FRAGMENT_SPILL")
        if pos < len(tr_blocks) - 1 and _has_neighbor_semantic_repeat(tr_blocks, pos):
            reasons.append("NEIGHBOR_SEMANTIC_REPEAT")
        if _has_broken_fragment_flow(tr_blocks, pos):
            reasons.append("BROKEN_FRAGMENT_FLOW")

        if reasons:
            suspicious.append((idx, ts, text, "|".join(reasons)))

    return suspicious


def _extract_json_array(raw: str) -> str:
    """Return the first valid JSON array found in raw text (handles preamble / code fences)."""
    raw = _strip_code_fence(raw)
    if not raw:
        return ""

    # Direct parse
    try:
        json.loads(raw)
        return raw
    except Exception:
        pass
    # Find first [...] block
    start = raw.find('[')
    end   = raw.rfind(']')
    if start != -1 and end > start:
        candidate = raw[start:end + 1]
        try:
            json.loads(candidate)
            return candidate
        except Exception:
            pass
    return ""  # Return empty string instead of raw, so caller knows parse failed


def _salvage_json_objects(raw: str) -> list:
    """Recover complete objects from a truncated JSON array and drop the partial tail."""
    raw = (raw or "").strip()
    if raw.startswith("```"):
        raw = "\n".join(raw.split("\n")[1:]).rsplit("```", 1)[0].strip()
    start = raw.find('[')
    if start == -1:
        return []
    dec = json.JSONDecoder()
    i, n, out = start + 1, len(raw), []
    while i < n:
        while i < n and raw[i] in ' \t\r\n,':
            i += 1
        if i >= n or raw[i] == ']':
            break
        if raw[i] != '{':
            break
        try:
            obj, end = dec.raw_decode(raw, i)
        except Exception:
            break
        if isinstance(obj, dict):
            out.append(obj)
        i = end
    return out


def _translation_items_from_raw(raw: str) -> list | None:
    """Parse batch translation JSON; salvage complete items if the array is truncated."""
    extracted = _extract_json_array(raw or "")
    if extracted:
        try:
            data = json.loads(extracted)
            if isinstance(data, list):
                return data
            if isinstance(data, dict) and isinstance(data.get("tr"), list):
                return data["tr"]
        except Exception:
            pass
    salvaged = _salvage_json_objects(raw or "")
    return salvaged or None


_POLISH_NUMBER_RE = re.compile(r"(?<!\w)[+-]?\d+(?:[.,:/]\d+)*(?:[%$€₺])?(?!\w)")
_POLISH_FORMAT_RE = re.compile(r"</?[a-zA-Z][^>]*>|\{[^}]+\}")
_POLISH_BRACKET_LABEL_RE = re.compile(r"\[[^\]\n]{1,40}\]")
_POLISH_TERMINAL_PUNCT_RE = re.compile(r"[.!?…][\"')\]\s]*$", re.UNICODE)
_POLISH_FOREIGN_SCRIPT_RE = re.compile(
    r"[\u0400-\u052F\u0600-\u06FF\u0750-\u077F\u0900-\u097F"
    r"\u0B80-\u0BFF\u3040-\u30FF\u3400-\u4DBF\u4E00-\u9FFF]",
    re.UNICODE,
)
_POLISH_ENGLISH_RESIDUE_RE = re.compile(
    r"\b(ass|shit|fuck|fucking|damn|hell|bitch|bro|dude|yeah|okay|ok|"
    r"gonna|wanna|gotta|ain't|y'all|audience|laughing|laughter|cheering|"
    r"applauding|applause|chuckles|chuckling|somehow|anyhow|kind\s+of|sort\s+of|"
    r"holiday|holidays|music\s+playing|disco\s+music|"
    r"drug|drugs)\b",
    re.IGNORECASE,
)
_POLISH_ENGLISH_BACKSLIDE_PHRASE_RE = re.compile(
    r"\b("
    r"so\s+is\s+this|is\s+this|this\s+is|that\s+is|there\s+is|there\s+are|"
    r"what\s+is|where\s+is|when\s+is|why\s+is|how\s+is|"
    r"do\s+you|did\s+you|will\s+you|would\s+you|could\s+you|"
    r"i\s+mean|you\s+know"
    r")\b",
    re.IGNORECASE,
)
_POLISH_ENGLISH_BACKSLIDE_WORD_RE = re.compile(
    r"\b("
    r"about|after|again|against|also|and|another|are|around|because|before|"
    r"being|but|could|did|does|even|every|fire|for|from|had|has|have|"
    r"here|how|into|is|just|like|make|maybe|more|must|now|only|or|our|"
    r"out|over|really|should|so|still|that|the|their|them|then|there|"
    r"these|they|this|those|through|was|were|what|when|where|which|while|"
    r"who|why|will|with|would|yes|you|your"
    r")\b",
    re.IGNORECASE,
)
_POLISH_MODEL_CORRUPTION_RE = re.compile(
    r"\b(?:thek|Thek|THEK|iyeleri|İyeleri|IYELERI|mekişi|MEKİŞİ)\b",
)
_POLISH_SPEAKER_LABEL_RE = re.compile(
    r"(?m)^\s*[-\u2013\u2014]?\s*[\w ._'/.-]{2,30}:\s*",
    re.UNICODE,
)
_POLISH_CAUSATIVE_WANT_RE = re.compile(
    r"\b([\wÃ§ÄŸÄ±Ã¶ÅŸÃ¼Ã‡ÄÄ°Ã–ÅÃœ]+m[ae]k)\s+istet\w*",
    re.IGNORECASE | re.UNICODE,
)
_POLISH_LITERAL_TRAPS = (
    "sahip olmak",
    "sahip ol",
    "gerçekleştirmek",
    "bu doğru değil mi",
    "benim için",
    "senin için",
    "alt çizgi",
    "büyük scott",
)


def build_polish_context_hint(analysis_result=None, tgt_lang: str = "Turkish") -> str:
    """Compact, optional context block for the meaning-preserving polish pass."""
    if not analysis_result:
        return ""
    try:
        ctx = analysis_result[0]
    except Exception:
        return ""

    parts = []
    try:
        if getattr(ctx, "tone", ""):
            parts.append(f"Tone/register: {str(ctx.tone)[:240]}")
        if getattr(ctx, "setting", ""):
            parts.append(f"Setting: {str(ctx.setting)[:220]}")
        if getattr(ctx, "summary", ""):
            parts.append(f"Context summary: {str(ctx.summary)[:320]}")
        chars = getattr(ctx, "characters", []) or []
        char_bits = []
        for c in chars[:8]:
            name = getattr(c, "name", "")
            style = getattr(c, "speaking_style", "")
            if name:
                char_bits.append(f"{name}: {style}" if style else str(name))
        if char_bits:
            parts.append("Character voices: " + "; ".join(char_bits))

        pronoun_map = analysis_result[2] if len(analysis_result) > 2 else None
        if isinstance(pronoun_map, dict) and pronoun_map:
            pairs = [f"{k}={v}" for k, v in list(pronoun_map.items())[:10]]
            parts.append("sen/siz decisions: " + "; ".join(pairs))

        idiom_map = analysis_result[5] if len(analysis_result) > 5 else None
        if isinstance(idiom_map, dict) and idiom_map:
            idioms = [f"{k}->{v}" for k, v in list(idiom_map.items())[:12]]
            parts.append("Idiom decisions: " + "; ".join(idioms))

        cultural_refs = analysis_result[6] if len(analysis_result) > 6 else None
        if isinstance(cultural_refs, list) and cultural_refs:
            refs = []
            for ref in cultural_refs[:8]:
                if isinstance(ref, dict) and ref.get("src"):
                    action = ref.get("action", "keep")
                    target = ref.get("target", "")
                    refs.append(f"{ref.get('src')}={action}" + (f":{target}" if target else ""))
            if refs:
                parts.append("Cultural refs: " + "; ".join(refs))
    except (IndexError, TypeError, AttributeError, KeyError):
        pass

    if not parts:
        return ""
    return (
        f"\n\nPROJECT CONTEXT FOR POLISH ({tgt_lang}):\n"
        + "\n".join(f"- {p}" for p in parts)
        + "\n"
    )


def polish_risk_hints(source_text: str = "", translated_text: str = "") -> list[str]:
    """Small hints that tell the polish model where a line may need attention."""
    tr = str(translated_text or "")
    src = str(source_text or "")
    hints = []
    tr_l = tr.lower()
    if len(tr.replace("\n", " ")) >= 42:
        hints.append("long_or_fast_line")
    if _POLISH_ENGLISH_RESIDUE_RE.search(tr) or _english_backslide_score(tr) >= 3:
        hints.append("english_residue")
    if any(trap in tr_l for trap in _POLISH_LITERAL_TRAPS):
        hints.append("literal_or_stilted_turkish")
    if src and _clean_source_text(src).lower() == _clean_source_text(tr).lower():
        hints.append("possibly_untranslated")
    if re.search(r"\b(\w+)(?:\s+\1\b){1,}", tr_l, re.UNICODE):
        hints.append("accidental_repetition")
    return hints


def _strip_polish_guard_noise(text: str) -> str:
    cleaned = _POLISH_FORMAT_RE.sub(" ", str(text or ""))
    cleaned = _POLISH_SPEAKER_LABEL_RE.sub(" ", cleaned)
    cleaned = re.sub(r"\[[A-Z0-9 _/-]{2,30}\]", " ", cleaned)
    return cleaned


def _canonical_polish_guard_text(text: str) -> str:
    cleaned = _strip_polish_guard_noise(text).lower()
    cleaned = _clean_source_text(cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned, flags=re.UNICODE)
    return cleaned.strip()


def _polish_neighbor_segments(text: str) -> list[str]:
    segments = []
    full = _canonical_polish_guard_text(text)
    if len(full) >= 18 and len(full.split()) >= 3:
        segments.append(full)
    for line in str(text or "").splitlines():
        part = _canonical_polish_guard_text(line)
        if len(part) >= 12 and len(part.split()) >= 2:
            segments.append(part)
    return list(dict.fromkeys(segments))


def _english_backslide_score(text: str) -> int:
    cleaned = _strip_polish_guard_noise(text).lower()
    phrase_hits = len(_POLISH_ENGLISH_BACKSLIDE_PHRASE_RE.findall(cleaned))
    word_hits = len(_POLISH_ENGLISH_BACKSLIDE_WORD_RE.findall(cleaned))
    return word_hits + (phrase_hits * 3)


def _regex_hit_set(pattern: re.Pattern, text: str) -> set[str]:
    return {m.group(0).lower() for m in pattern.finditer(_strip_polish_guard_noise(text))}


def _has_new_english_residue(original_text: str, candidate_text: str) -> bool:
    old_residue = _regex_hit_set(_POLISH_ENGLISH_RESIDUE_RE, original_text)
    new_residue = _regex_hit_set(_POLISH_ENGLISH_RESIDUE_RE, candidate_text)
    if new_residue - old_residue:
        return True
    old_backslide = _regex_hit_set(_POLISH_ENGLISH_BACKSLIDE_WORD_RE, original_text)
    new_backslide = _regex_hit_set(_POLISH_ENGLISH_BACKSLIDE_WORD_RE, candidate_text)
    return bool(new_backslide - old_backslide)


def _has_english_backslide(original_text: str, candidate_text: str) -> bool:
    old_score = _english_backslide_score(original_text)
    new_score = _english_backslide_score(candidate_text)
    if new_score <= old_score:
        return False
    cleaned_new = _strip_polish_guard_noise(candidate_text)
    if _POLISH_ENGLISH_BACKSLIDE_PHRASE_RE.search(cleaned_new):
        return True
    return new_score >= 3 and (new_score - old_score) >= 3


def _has_source_echo(source_text: str, original_text: str, candidate_text: str) -> bool:
    source = _canonical_polish_guard_text(source_text)
    candidate = _canonical_polish_guard_text(candidate_text)
    original = _canonical_polish_guard_text(original_text)
    if not source or not candidate or candidate == original:
        return False
    if len(source) < 12 or len(source.split()) < 3:
        return False
    return candidate == source or source in candidate


def _has_causative_want_backslide(original_text: str, candidate_text: str) -> bool:
    old = _strip_polish_guard_noise(original_text).lower()
    new = _strip_polish_guard_noise(candidate_text).lower()
    for match in _POLISH_CAUSATIVE_WANT_RE.finditer(old):
        infinitive = re.escape(match.group(1))
        if re.search(rf"\b{infinitive}\s+isti(?:yor|yordu|yecek|yorum|yoruz|yorsun|yorlar)\w*", new):
            return True
    return False


def _has_neighbor_echo(
    original_text: str,
    candidate_text: str,
    neighbor_texts: list[str] | None = None,
) -> bool:
    if not neighbor_texts:
        return False
    original = _canonical_polish_guard_text(original_text)
    candidate_segments = _polish_neighbor_segments(candidate_text)
    if not candidate_segments:
        return False
    for candidate_segment in candidate_segments:
        if candidate_segment and candidate_segment in original:
            continue
        for neighbor in neighbor_texts:
            neighbor_text = _canonical_polish_guard_text(neighbor)
            if len(neighbor_text) < 12:
                continue
            if candidate_segment == neighbor_text or candidate_segment in neighbor_text:
                return True
    return False


def _has_fragment_terminal_backslide(
    original_text: str,
    candidate_text: str,
    fragment_tag: str = "",
) -> bool:
    if fragment_tag not in {"start", "mid"}:
        return False
    old = _strip_polish_guard_noise(original_text).strip()
    new = _strip_polish_guard_noise(candidate_text).strip()
    return not _POLISH_TERMINAL_PUNCT_RE.search(old) and bool(_POLISH_TERMINAL_PUNCT_RE.search(new))


def _has_foreign_script_backslide(original_text: str, candidate_text: str) -> bool:
    return (
        not _POLISH_FOREIGN_SCRIPT_RE.search(str(original_text or ""))
        and bool(_POLISH_FOREIGN_SCRIPT_RE.search(str(candidate_text or "")))
    )


def _has_idiom_come_in_at_price(source_text: str, candidate_text: str) -> bool:
    """Detect when 'come in (right) at X' (price/offer) is literally translated
    as 'girmek' in Turkish — should use 'çıkmak' or 'istemek'."""
    if not source_text or not candidate_text:
        return False
    if not _COME_IN_AT_PRICE_RE.search(source_text):
        return False
    # If source has the idiom but Turkish uses girmek/girmem/girecek → flag
    return bool(_COME_IN_AT_TR_GIRMEK_RE.search(candidate_text))


_TO_NAME_RE = re.compile(r'\bto\s+[A-Z][a-zA-Z\'’]*\b')

def _has_to_name_reimport(source_text: str, original_text: str, candidate_text: str) -> bool:
    """Detect when 'to [Name]' from source is reimported into a candidate that
    previously had the correct Turkish dative form (e.g. 'to John' → 'John'a')."""
    if not source_text or not original_text or not candidate_text:
        return False
    if original_text == candidate_text:
        return False
    def _name_key(match: str) -> str:
        name = match.split(None, 1)[1]
        if name.endswith("'s"):
            name = name[:-2]
        if name.endswith("'nin"):
            name = name[:-4]
        if name.endswith("'nın"):
            name = name[:-4]
        return name.lower()

    src_names = {_name_key(m) for m in _TO_NAME_RE.findall(source_text)}
    if not src_names:
        return False
    old_names = {_name_key(m) for m in _TO_NAME_RE.findall(original_text)}
    new_names = {_name_key(m) for m in _TO_NAME_RE.findall(candidate_text)}
    reimported = (new_names - old_names) & src_names
    return bool(reimported)


def _has_english_reimport(source_text: str, original_text: str, candidate_text: str) -> bool:
    """Detect when polish re-imports an English source word that was properly
    Turkish-ized or absent in the original translation (e.g. operatik→operatic)."""
    if not source_text or not original_text or not candidate_text:
        return False
    if original_text == candidate_text:
        return False
    src_words = set(w.lower() for w in re.findall(r'\b([a-zA-Z]{4,})\b', source_text))
    if not src_words:
        return False
    old_words = set(w.lower() for w in re.findall(r'\b([a-zA-Z]{4,})\b', original_text))
    new_words = set(w.lower() for w in re.findall(r'\b([a-zA-Z]{4,})\b', candidate_text))
    imported = (new_words - old_words) & src_words
    return bool(imported)


_TR_FILLER_WORDS = {"da", "de", "şey", "yani", "hani", "ya", "ama", "ki", "mi", "mu", "mü", "mı", "ha", "ee", "he",
                    "ve", "şekilde", "olan", "olduğu", "hakkında",
                    "artık", "sonra", "dediğimizde"}

def _has_orphan_fragment(source_text: str, candidate_text: str) -> bool:
    """Flag when source has 4+ meaningful words but target is just filler or very short."""
    if not source_text or not candidate_text:
        return False
    # Count meaningful source words (3+ letters, not filler)
    src_tokens = [w for w in source_text.split() if len(w) >= 3 and w.lower() not in _TR_FILLER_WORDS]
    if len(src_tokens) < 4:
        return False
    # If target is just filler words or ≤2 chars after strip, flag
    tr_stripped = candidate_text.strip().strip(".,;:!?")
    if len(tr_stripped) <= 2:
        return True
    tr_tokens = candidate_text.split()
    if not tr_tokens:
        return True
    non_filler = [w for w in tr_tokens if w.lower().strip(".,;:!?") not in _TR_FILLER_WORDS]
    # All tokens are filler or target is suspiciously short
    return len(non_filler) == 0 or (len(tr_stripped) <= 4 and len(tr_tokens) <= 2)


def _has_consecutive_echo(tr_blocks: list, pos: int) -> bool:
    """Flag when two consecutive target lines are identical short phrases."""
    if pos < 0 or pos + 1 >= len(tr_blocks):
        return False
    _idx1, _ts1, text1 = tr_blocks[pos]
    _idx2, _ts2, text2 = tr_blocks[pos + 1]
    if not text1 or not text2 or text1 == "[HATA]" or text2 == "[HATA]":
        return False
    t1 = text1.strip().strip(".,;:!?").lower()
    t2 = text2.strip().strip(".,;:!?").lower()
    if t1 != t2 or len(t1) < 3:
        return False
    return True


def _has_neighbor_prefix_echo(tr_blocks: list, pos: int) -> bool:
    """Flag when last tokens of block N repeat at start of block N+1.
    Catches multi-word suffix→prefix and single-word echo for words ≥5 chars."""
    if pos < 0 or pos + 1 >= len(tr_blocks):
        return False
    _idx1, _ts1, text1 = tr_blocks[pos]
    _idx2, _ts2, text2 = tr_blocks[pos + 1]
    if not text1 or not text2 or text1 == "[HATA]" or text2 == "[HATA]":
        return False
    t1 = text1.strip().strip(".,;:!?").lower()
    t2 = text2.strip().strip(".,;:!?").lower()
    t1_tokens = [w for w in re.findall(r"[a-zçğıöşü]+", t1) if len(w) >= 3]
    t2_tokens = [w for w in re.findall(r"[a-zçğıöşü]+", t2) if len(w) >= 3]
    if len(t1_tokens) < 1 or len(t2_tokens) < 1:
        return False
    # Multi-word prefix echo (2-4 words)
    if len(t1_tokens) >= 2 and len(t2_tokens) >= 2:
        for n in range(min(4, len(t1_tokens)), 1, -1):
            suffix = " ".join(t1_tokens[-n:])
            prefix = " ".join(t2_tokens[:n])
            if suffix == prefix:
                return True
        # Adjacent semantic duplicate: both lines restart with the same phrase.
        for n in range(min(5, len(t1_tokens), len(t2_tokens)), 2, -1):
            if " ".join(t1_tokens[:n]) == " ".join(t2_tokens[:n]):
                return True
    # Single-word echo: last word of prev ≥5 chars matches first word of next
    if (len(t1_tokens[-1]) >= 5
            and t1_tokens[-1] == t2_tokens[0]
            and t2_tokens[0] not in ("ama", "ve", "de", "da", "ki", "ile")):
        return True
    return False


def _has_neighbor_prefix_echo_text(original_text: str, candidate_text: str, neighbor_texts: list[str]) -> bool:
    """Check if candidate repeats the tail of any neighbor at its start."""
    if not original_text or not candidate_text or not neighbor_texts:
        return False
    c_tokens = [w for w in re.findall(r"[a-zçğıöşü]+", candidate_text.lower()) if len(w) >= 3]
    if len(c_tokens) < 2:
        return False
    for nt in neighbor_texts:
        if not nt or nt == "[HATA]":
            continue
        n_tokens = [w for w in re.findall(r"[a-zçğıöşü]+", nt.lower()) if len(w) >= 3]
        if len(n_tokens) < 2:
            continue
        for n in range(min(4, len(n_tokens)), 1, -1):
            suffix = " ".join(n_tokens[-n:])
            prefix = " ".join(c_tokens[:n])
            if suffix == prefix:
                return True
    return False


def _has_conjunction_fragment_spill(tr_blocks: list, pos: int) -> bool:
    """Detect when a cue ends with conjunctive-incomplete phrase spilling to next cue."""
    if pos < 0 or pos + 1 >= len(tr_blocks):
        return False
    _idx1, _ts1, text1 = tr_blocks[pos]
    _idx2, _ts2, text2 = tr_blocks[pos + 1]
    if not text1 or not text2 or text1 == "[HATA]" or text2 == "[HATA]":
        return False
    t1 = re.sub(r"\[HATA\].*$", "", str(text1)).strip().strip(".,;:!?-\"'")
    m = re.search(r'\bçünkü\s+(.+)$', t1, re.IGNORECASE)
    if m:
        after = m.group(1).strip().strip(".,;:!?")
        words = [w for w in after.split() if w]
        if 1 <= len(words) <= 3:
            return True
    return False


def _has_neighbor_semantic_repeat(tr_blocks: list, pos: int) -> bool:
    """Detect when adjacent cues repeat the same meaning (e.g. yineleme/tekrarlanma + nedeni)."""
    if pos < 0 or pos + 1 >= len(tr_blocks):
        return False
    _idx1, _ts1, text1 = tr_blocks[pos]
    _idx2, _ts2, text2 = tr_blocks[pos + 1]
    if not text1 or not text2 or text1 == "[HATA]" or text2 == "[HATA]":
        return False
    t1 = text1.strip().strip(".,;:!?").lower()
    t2 = text2.strip().strip(".,;:!?").lower()
    if len(t1) < 12 or len(t2) < 12:
        return False
    # Both end with the same 5+-char suffix (e.g. "nedeni")
    for n in range(min(10, len(t1), len(t2)), 4, -1):
        if t1[-n:] == t2[-n:]:
            if any(w in t1 for w in ["yinele", "tekrarla", "sürekli"]):
                if any(w in t2 for w in ["yinele", "tekrarla", "sürekli"]):
                    return True
            break
    return False


def _has_broken_fragment_flow(tr_blocks: list, pos: int) -> bool:
    """Catch real output cases where a cue is grammatical alone but broken in cross-cue flow."""
    if pos < 0 or pos >= len(tr_blocks):
        return False
    _idx, _ts, text = tr_blocks[pos]
    if not text or text == "[HATA]" or "[ÇEVİRİ EKSİK]" in str(text):
        return False

    cur = re.sub(r"\s+", " ", _semantic_text_for_validator(str(text))).strip().lower()
    prev = ""
    next_text = ""
    if pos > 0:
        prev = re.sub(r"\s+", " ", _semantic_text_for_validator(str(tr_blocks[pos - 1][2]))).strip().lower()
    if pos + 1 < len(tr_blocks):
        next_text = re.sub(r"\s+", " ", _semantic_text_for_validator(str(tr_blocks[pos + 1][2]))).strip().lower()

    # Real S05E08 case: previous cue says visiting an old musician friend;
    # this cue is left as a dangling afterthought instead of modifying that friend.
    if re.fullmatch(r"(?:şimdi|artık) burada yaşayan[.!?…]*", cur):
        if re.search(r"(?:müzisyen|arkadaş|ziyaret|ziyarete gid)", prev):
            return True

    # Real S05E08 case: title/name is stranded as "adı THE ..." after a display/community line.
    if re.match(r"adı\s+(?:da\s+)?(?:the\s+)?[a-z0-9'’ -]{4,}", cur, re.IGNORECASE):
        if re.search(r"(?:sergiliyoruz|çalışmalarını|topluluğumuz|mekanın|mekânın)", prev):
            return True

    # Real S05E08 case: mechanical phrase from "I was kind of scared...".
    if re.search(r"\ben\s+biraz\b", cur):
        return True

    # Intro phrase split as "bu işi... / bilime döktük" should be reviewed as a flow group.
    if re.search(r"\bbilime\s+döktük\b", cur) and re.search(r"\bbu işi\b|araştırıp seçerek|toplayıp", prev + " " + next_text):
        return True

    return False


_DAR_WOULD_NOT_KNOW_RE = re.compile(
    r"\b(?:he|she)\s+would(?:n['’]t| not)\s+know\b|"
    r"\bpossibility\s+(?:he|she)\s+would(?:n['’]t| not)\s+know\b",
    re.IGNORECASE,
)
_DAR_BILLMEME_IPTIMALI_RE = re.compile(
    r"\bbilmeme\w*\s+ihtimali\b",
    re.IGNORECASE | re.UNICODE,
)

def _has_dar_person_drift(source_text: str, candidate_text: str) -> bool:
    """Detect source 'he/she would not know' translated as 'bilmeme ihtimali' (dar/dative drift)."""
    if not source_text or not candidate_text:
        return False
    if not _DAR_WOULD_NOT_KNOW_RE.search(source_text):
        return False
    return bool(_DAR_BILLMEME_IPTIMALI_RE.search(candidate_text))


_INTO_HIS_REIGN_RE = re.compile(
    r"\b(?:\d+|ten|five|six|seven|eight|nine)\s+years?\s+into\s+(?:his|her|the|their)\s+reign\b",
    re.IGNORECASE,
)
_TAHTA_CIKTI_RE = re.compile(r"\btahta\s+çıktı\b", re.IGNORECASE | re.UNICODE)


def _has_reign_mistranslation(source_text: str, candidate_text: str) -> bool:
    if not source_text or not candidate_text:
        return False
    if not _INTO_HIS_REIGN_RE.search(source_text):
        return False
    return bool(_TAHTA_CIKTI_RE.search(candidate_text))


_HOLDS_WATER_RE = re.compile(r"\bholds?\s+water\b", re.IGNORECASE)
_HOLDS_WATER_BAD_RE = re.compile(r"\bayakta\s+duran\b", re.IGNORECASE | re.UNICODE)


def _has_idiom_holds_water(source_text: str, candidate_text: str) -> bool:
    if not source_text or not candidate_text:
        return False
    if not _HOLDS_WATER_RE.search(source_text):
        return False
    return bool(_HOLDS_WATER_BAD_RE.search(candidate_text))


_DOMINATES_SOURCE_RE = re.compile(r"\b(?:dominates?|governs?|rules?|controls?)\b", re.IGNORECASE)
_DOMINATES_TR_OK_RE = re.compile(
    r"\b(?:h\u00fckmed|hakim|h\u00e2kim|egemen|kontrol|y\u00f6net|etkile|belirle)\w*",
    re.IGNORECASE | re.UNICODE,
)


def _has_dominates_missing_predicate(source_text: str, candidate_text: str) -> bool:
    """Flag complete source sentences like 'Saturn dominates X' when Turkish is left as a noun fragment."""
    if not source_text or not candidate_text:
        return False
    if not _DOMINATES_SOURCE_RE.search(source_text):
        return False
    if _DOMINATES_TR_OK_RE.search(candidate_text):
        return False
    words = re.findall(r"[^\W\d_]+", _semantic_text_for_validator(candidate_text).lower(), re.UNICODE)
    return not any(_TR_FINITE_VERB_TAIL_RE.search(word) for word in words)


def _has_short_source_overexpansion(source_text: str, target_text: str) -> bool:
    """Flag when source ≤3 words but target is very long (≥8 words).
    Indicates the model absorbed neighbor text into a short source cue."""
    if not source_text or not target_text:
        return False
    src_words = [w for w in source_text.split() if len(w) >= 2]
    if len(src_words) > 3:
        return False
    tr_words = [w for w in target_text.split() if len(w) >= 2]
    if len(tr_words) < 8:
        return False
    return True


def _has_destructive_shorten(original_text: str, candidate_text: str) -> bool:
    old = _canonical_polish_guard_text(original_text)
    new = _canonical_polish_guard_text(candidate_text)
    if len(old) < 80:
        return False
    if len(new) < 30:
        return True
    return len(new) < len(old) * 0.45


def _has_dangling_fragment_word_deletion(original_text: str, candidate_text: str) -> bool:
    old_words = re.findall(r"[A-Za-zÇĞİÖŞÜçğıöşü]+", _canonical_polish_guard_text(original_text))
    new_words = re.findall(r"[A-Za-zÇĞİÖŞÜçğıöşü]+", _canonical_polish_guard_text(candidate_text))
    return len(old_words) >= 3 and len(new_words) < len(old_words)


def _has_question_regression(original_text: str, candidate_text: str) -> bool:
    """Reject polish that scrambles a natural Turkish question structure."""
    if not original_text or not candidate_text:
        return False
    if "?" not in original_text or "?" not in candidate_text:
        return False
    old_lower = original_text.lower()
    new_lower = candidate_text.lower()
    # Look for "kim" questions — old should have the subject right before "kim"
    if "kim" not in old_lower or "kim" not in new_lower:
        return False
    old_tokens = old_lower.strip("?").split()
    new_tokens = new_lower.strip("?").split()
    try:
        old_kim_pos = old_tokens.index("kim")
    except ValueError:
        return False
    try:
        new_kim_pos = new_tokens.index("kim")
    except ValueError:
        return False
    if old_kim_pos == 0 or new_kim_pos == 0:
        return False
    # Get the word right before "kim" in both
    old_before = old_tokens[old_kim_pos - 1]
    new_before = new_tokens[new_kim_pos - 1]
    if old_before != new_before:
        return True
    return False


def _has_english_article_reimport(original_text: str, candidate_text: str) -> bool:
    """Detect when a Polish pass re-imports the English article 'a' into Turkish text."""
    if not original_text or not candidate_text:
        return False
    # Only flag when candidate has lowercase standalone 'a' (English article),
    # NOT uppercase 'A' (Turkish letter name like "A planı").
    if re.search(r'(?<!\w)a\s+[a-zçğıöşü]', candidate_text):
        old_lower = original_text.lower()
        if not re.search(r'\ba\b', old_lower):
            return True
    return False


def _has_greek_word_explanation_loss(source_text: str, target_text: str) -> bool:
    """Detect when source mentions 'Greek word' but target omits the explanation."""
    if not source_text or not target_text:
        return False
    if 'greek word' in source_text.lower():
        return not any(term in target_text.lower() for term in ['yunanca', 'yunan'])
    return False


def _has_first_person_intent_shift(source_text: str, original_text: str, candidate_text: str) -> bool:
    """Detect when polish shifts first-person intent (I'd like to talk) to plural/impersonal."""
    if not source_text or not original_text or not candidate_text:
        return False
    src_lower = source_text.lower()
    if not any(p in src_lower for p in ["i'd like to talk", "i want to talk", "i would like to talk",
                                         "i'd like to speak", "i want to speak", "i'd like to discuss",
                                         "i'd like to mention", "i want to mention"]):
        return False
    old_lower = original_text.lower()
    if not any(p in old_lower for p in ["konuşmak istiyorum", "bahsetmek istiyorum",
                                         "konuşmak isterim", "bahsetmek isterim"]):
        return False
    new_lower = candidate_text.lower()
    # Check if new shifted away from first-person singular
    if any(p in new_lower for p in ["konuşacağız", "bahsedeceğiz", "konuşuruz", "bahsederiz"]):
        if not any(p in new_lower for p in ["istiyorum", "isterim"]):
            return True
    return False


def _has_first_person_to_imperative_regression(old: str, new: str) -> bool:
    """Reject polish that swaps first-person 'deneyeyim/deneyim' to imperative 'dene'."""
    old_lower = old.lower()
    new_lower = new.lower()
    if not ("deneyeyim" in old_lower or "deneyim" in old_lower):
        return False
    return bool(re.search(r'\bdene\b', new_lower)) and "deneyeyim" not in new_lower and "deneyim" not in new_lower


def _has_woodstock_regression(old: str, new: str) -> bool:
    """Reject polish that truncates 'Woodstock' to 'Woodstoc'."""
    old_upper = old.upper()
    new_upper = new.upper()
    if "WOODSTOCK" not in old_upper:
        return False
    return bool(re.search(r'\bwoodstoc\b', new_upper, re.I)) and "woodstock" not in new_upper


def _has_fragment_redistribution_regression(old: str, new: str) -> bool:
    """Reject polish that moves key objects to another line, leaving the current line meaningless."""
    old_lower = old.lower()
    new_lower = new.lower()
    if not ("yarattığım" in old_lower or "göstereceğim" in old_lower):
        return False
    return "yarasayı" in old_lower and "seni" in new_lower and "yarasa" not in new_lower


def _has_fox_sloth_inconsistency(text: str, tr_blocks: list, pos: int) -> bool:
    """Detect 'tilki derisi' when neighboring cues mention tembel hayvan/sloth context."""
    if not text:
        return False
    if not re.search(r'tilki', text, re.IGNORECASE) or not re.search(r'derisi', text, re.IGNORECASE):
        return False
    _FOX_SLOTH_CTX = re.compile(r'tembel\s+hayvan|sloth|kafa', re.IGNORECASE)
    for offset in range(-2, 3):
        if offset == 0:
            continue
        np = pos + offset
        if np < 0 or np >= len(tr_blocks):
            continue
        _idx, _ts, nt = tr_blocks[np]
        if nt and _FOX_SLOTH_CTX.search(nt):
            return True
    return False


def _has_head_to_face_regression(original_text: str, candidate_text: str) -> bool:
    """Detect when polish drops 'kafa' (head) and replaces core noun with 'yüz' (face)."""
    if not original_text or not candidate_text:
        return False
    old_lower = original_text.lower()
    new_lower = candidate_text.lower()
    if "biçilmiş kafa" not in old_lower:
        return False
    if "kafa" in new_lower:
        return False
    if re.search(r'\byüz\b', new_lower):
        return True
    return False


def _has_research_to_hunting_regression(old: str, new: str) -> bool:
    """Reject polish that changes 'araştırıp seçerek' to 'avlanıp seçerek'."""
    old_lower = old.lower()
    new_lower = new.lower()
    return "araştırıp seçerek" in old_lower and "avlanıp seçerek" in new_lower


def _has_oddities_intro_regression(old: str, new: str) -> bool:
    """Reject polish that replaces intro mastery language with science-literal phrasing."""
    old_lower = old.lower()
    new_lower = new.lower()
    has_intro_hint = (
        "ustalaştır" in old_lower
        or "ustalık" in old_lower
        or "ustalaş" in old_lower
        or "tekniğini oturttuk" in old_lower
        or "kitabını yazacak" in old_lower
        or "araştırıp seçerek" in old_lower
    )
    science_literal = (
        "bilim gibi yapmaya" in new_lower
        or "bilim gibi yaptık" in new_lower
        or "bilime döktük" in new_lower
        or "bilime çevirdik" in new_lower
        or "bir bilime çevirdik" in new_lower
        or "bilim haline getirmek" in new_lower
        or "bilim haline getirdik" in new_lower
        or "bilimini çıkardık" in new_lower
        or "ustalığa dök" in new_lower
    )
    return has_intro_hint and science_literal


def _has_fragment_expansion_regression(old: str, new: str) -> bool:
    """Reject polish that expands a tiny sentence fragment by copying neighbor content."""
    old_sem = re.sub(r"\s+", " ", _semantic_text_for_validator(old)).strip().lower()
    new_sem = re.sub(r"\s+", " ", _semantic_text_for_validator(new)).strip().lower()
    if old_sem in {"sadece", "yalnızca"} and len(new_sem.split()) >= 3:
        return True
    return False


def _has_stray_o_learning_regression(old: str, new: str) -> bool:
    """Reject the ungrammatical 'birinin o öğrenmesi' polish regression."""
    old_sem = re.sub(r"\s+", " ", _semantic_text_for_validator(old)).strip().lower()
    new_sem = re.sub(r"\s+", " ", _semantic_text_for_validator(new)).strip().lower()
    return "birinin öğrenmesi" in old_sem and "birinin o öğrenmesi" in new_sem


def _has_welcome_deletion(old: str, new: str) -> bool:
    """Reject polish that deletes 'hoş' from 'hoş geldiniz'."""
    old_lower = old.lower()
    new_lower = new.lower()
    return "hoş geldiniz" in old_lower and new_lower.strip() == "geldiniz"


def _has_lets_see_to_imperative_regression(old: str, new: str) -> bool:
    """Reject polish that changes 'boğuluşunu görelim' to 'boğulsun'."""
    old_lower = old.lower()
    new_lower = new.lower()
    return ("görelim" in old_lower or "izleyelim" in old_lower) and _is_imperative_only(new_lower)


def _is_imperative_only(text: str) -> bool:
    """Check if text is a bare 3rd-person imperative (boğulsun, ölsün, etc.)."""
    t = text.strip()
    return bool(re.fullmatch(r'\S+(?:sun|sün|sin|sın)', t)) and ' ' not in t


def _has_invitation_subject_regression(old: str, new: str) -> bool:
    """Reject polish that changes 'gelmenize sevinirim' to 'gelmeye sevinirim'."""
    old_lower = old.lower()
    new_lower = new.lower()
    return "gelmenize sevinirim" in old_lower and "gelmeye sevinirim" in new_lower


def _has_oddities_intro_idiom_regression(old: str, new: str) -> bool:
    """Reject polish that replaces 'ustalık/ustalaş/sistemleştir' with 'işin suyunu çıkardık'."""
    old_lower = old.lower()
    new_lower = new.lower()
    has_intro_hint = (
        re.search(r'ustal[ıi][kğ]', old_lower)
        or "ustalaş" in old_lower
        or "sistemleştir" in old_lower
    )
    return bool(has_intro_hint) and "işin suyunu çıkardık" in new_lower


def _has_grandma_to_mother_regression(old: str, new: str) -> bool:
    """Reject polish that swaps 'anneanne/büyükanne' to 'anne' in antique context."""
    import unicodedata
    old_norm = unicodedata.normalize('NFKC', old).lower().replace('\u0307', '')
    new_norm = unicodedata.normalize('NFKC', new).lower().replace('\u0307', '')
    has_grandma_context = (
        (re.search(r'anneanne|büyükanne|büyükananem', old_norm) is not None)
        and ("antikacı" in old_norm or "antika" in old_norm)
    )
    if not has_grandma_context:
        return False
    return bool(re.search(r'\bannenizin\b', new_norm))


def _has_unnecessary_da_deletion(old: str, new: str) -> bool:
    """Reject polish that drops 'da' from 'adı da'."""
    old_lower = old.lower()
    new_lower = new.lower()
    return "adı da" in old_lower and new_lower.strip().startswith("adı") and "da" not in new_lower


def _has_oddities_title_case_regression(old: str, new: str) -> bool:
    """Reject polish that changes 'ODDITIES'İN' to 'ODDITIES'E' or 'ODDITIES. '."""
    import unicodedata
    old_norm = unicodedata.normalize('NFKC', old).lower().replace('\u0307', '')
    new_norm = unicodedata.normalize('NFKC', new).lower().replace('\u0307', '')
    if 'oddities' not in old_norm or 'oddities' not in new_norm:
        return False
    has_old_good = (
        '"in' in old_norm or "'in" in old_norm
        or '"ın' in old_norm or "'ın" in old_norm
    )
    if not has_old_good:
        return False
    has_new_dative = (
        ('"e' in new_norm or "'e" in new_norm)
        and '"in' not in new_norm
        and "'in" not in new_norm
        and '"ın' not in new_norm
        and "'ın" not in new_norm
    )
    has_new_dot = bool(re.search(r'oddities[\.\s]+["\s]', new_norm))
    return has_new_dative or has_new_dot


def _has_turkish_question_loss(old: str, new: str) -> bool:
    """Reject polish that drops Turkish question particles (mı/mi/mu/mü) or 'yoksa'."""
    import unicodedata
    old_norm = unicodedata.normalize('NFKC', old).lower().replace('\u0307', '')
    new_norm = unicodedata.normalize('NFKC', new).lower().replace('\u0307', '')
    has_question = bool(re.search(r'\b(mı|mi|mu|mü)\b', old_norm)) or "yoksa" in old_norm
    if not has_question:
        return False
    new_has_question = bool(re.search(r'\b(mı|mi|mu|mü)\b', new_norm)) or "yoksa" in new_norm
    return not new_has_question


def _has_neighbor_semantic_copy(old: str, new: str, neighbor_texts: list[str] | None) -> bool:
    """Reject when candidate copies neighbor content that original didn't share."""
    if not neighbor_texts:
        return False
    old_tokens = set(_meaningful_tokens(old))
    new_tokens = set(_meaningful_tokens(new))
    if len(new_tokens) < 5:
        return False
    for nt in neighbor_texts:
        if not nt:
            continue
        nt_tokens = set(_meaningful_tokens(nt))
        if len(nt_tokens) < 5:
            continue
        old_overlap = len(old_tokens & nt_tokens)
        new_overlap = len(new_tokens & nt_tokens)
        if new_overlap >= 4 and (new_overlap - old_overlap) >= 3:
            return True
    return False


def _meaningful_tokens(text: str) -> list[str]:
    """Extract content words from text, skipping stopwords and punctuation."""
    _STOPS = frozenset({
        "bir", "bu", "ve", "da", "de", "ile", "mi", "mu", "mı", "mü",
        "ki", "de", "için", "gibi", "ama", "veya", "veya", "ise",
        "her", "o", "o", "şu", "ne", "ya", "da", "daha", "en",
        "mi", "mı", "mu", "mü", "da", "de", "ise",
    })
    tokens = re.findall(r'\b[a-zA-ZçğıöşüÇĞİÖŞÜ]{3,}\b', text.lower())
    return [t for t in tokens if t not in _STOPS]


def _polish_norm(text: str) -> str:
    """NFKC normalize → lower → strip combining dot → â/î/û→a/i/u for safe comparison."""
    import unicodedata
    n = unicodedata.normalize('NFKC', text).lower()
    n = n.replace('\u0307', '')
    n = n.replace('â', 'a').replace('î', 'i').replace('û', 'u')
    return n


_CONTENT_DRIFT_STOPS = frozenset({
    "bir", "bu", "ve", "da", "de", "ile", "mi", "mu", "mı", "mü",
    "ki", "için", "icin", "gibi", "ama", "veya", "ise",
    "her", "o", "şu", "ne", "ya", "daha", "en",
    "ben", "sen", "biz", "siz", "onlar", "yani", "şey", "sey",
    "hani", "işte", "iste",
    "bence", "sence", "bizce", "sizce", "onca", "onlarca",
    "böyle", "boyle", "şöyle", "öyle", "nasıl", "nasil",
    "çok", "cok", "az", "fazla", "yarın", "yarin",
    "şimdi", "simdi", "sonra", "önce", "once",
})


_TURKISH_SUFFIXES_ASCII = [
    "ecekti", "acakti", "ecekmis", "acakmis",
    "ecegim", "acagim", "eceksin", "acaksin",
    "ecegiz", "acagiz", "ecekler", "acaklar",
    "misti", "mustu",
    "iyordum", "iyordun", "iyordu",
    "iyorum", "iyorsun", "iyoruz", "iyorsunuz",
    "iyor", "uyor",
    "siniz", "sunuz",
    "mis", "mus",
    "mek", "mak",
    "dir", "tir", "dur", "tur",
    "lar", "ler", "lari", "leri",
    "den", "dan", "ten", "tan",
    "nin", "na", "ne", "ni",
    "de", "da", "te", "ta",
    "di", "ti", "du", "tu",
    "se", "sa", "me", "ma",
    "in", "im", "iz", "il", "ip", "is",
    "un", "um", "uz", "ul", "up", "us",
    "yi", "yim", "yin", "yiz",
    "li", "siz", "ci", "lu", "suz", "cu",
    "ca", "ce",
    "ki",
]


def _turkish_stem(word: str) -> str:
    """Strip one layer of common Turkish suffixes, return stem (or word unchanged).

    Normalizes Turkish chars to ASCII before suffix matching, so 'gidiyorum'
    and 'bakıyorum' both match. Remaining suffix chars are returned from the
    original word (not the normalized form) to preserve stem comparison accuracy.
    """
    if len(word) <= 3:
        return word
    w_norm = (word.lower()
              .replace('ç', 'c').replace('ğ', 'g')
              .replace('ı', 'i').replace('ö', 'o')
              .replace('ş', 's').replace('ü', 'u'))
    for sfx in _TURKISH_SUFFIXES_ASCII:
        if w_norm.endswith(sfx):
            stem_len = len(word) - len(sfx)
            if stem_len >= 3:
                return word[:stem_len]
    return word


def _share_stem(t1: str, t2: str) -> bool:
    """Check if two Turkish tokens share a stem via suffix stripping + prefix fallback."""
    if len(t1) < 3 or len(t2) < 3:
        return False
    s1 = _turkish_stem(t1)
    s2 = _turkish_stem(t2)
    if s1 == s2:
        return True
    # Stem-level prefix: threshold 3 (stems already suffix-stripped, more reliable)
    shorter, longer = (s1, s2) if len(s1) <= len(s2) else (s2, s1)
    if len(shorter) >= 3 and longer.startswith(shorter):
        return True
    # Original-level prefix: threshold 4 (raw tokens, more conservative)
    shorter, longer = (t1, t2) if len(t1) <= len(t2) else (t2, t1)
    if len(shorter) >= 4 and longer.startswith(shorter):
        return True
    return False


def _has_stem_match(token: str, old_tokens: list[str]) -> bool:
    """Check if token shares a stem with any old token."""
    return any(_share_stem(token, ot) for ot in old_tokens)


def is_safe_polish_edit(old: str, new: str) -> bool:
    """True if the change is a safe surface edit (typo, case, punct) not a rewrite."""
    from difflib import SequenceMatcher
    if old == new:
        return True
    o_fixed, _ = _apply_local_fixes(old)
    n_fixed, _ = _apply_local_fixes(new)
    old_norm = _polish_norm(o_fixed)
    new_norm = _polish_norm(n_fixed)
    if old_norm == new_norm:
        return True
    o_words = old_norm.split()
    n_words = new_norm.split()
    if len(o_words) != len(n_words):
        return SequenceMatcher(None, old_norm, new_norm).ratio() >= 0.90
    for ow, nw in zip(o_words, n_words):
        if ow == nw:
            continue
        if len(ow) <= 2 or len(nw) <= 2:
            return False
        ratio = SequenceMatcher(None, ow, nw).ratio()
        threshold = 0.90 if len(ow) <= 3 or len(nw) <= 3 else 0.85
        if ratio < threshold:
            return False
        if abs(len(ow) - len(nw)) > 3:
            return False
    return True


def _has_content_word_drift(old: str, new: str, source_text: str = "") -> bool:
    """Reject polish that introduces content words absent from the original.

    Uses suffix-stripping stem matching to handle Turkish agglutinative morphology:
    'konuşmak' and 'konuşacağız' share the stem 'konuş' and are NOT counted as drift.
    source_text: when present and containing content not in old, raises leniency
    (new tokens may be source-faithful corrections, not drift).
    """
    if not old or not new:
        return False
    o_fixed, _ = _apply_local_fixes(old)
    n_fixed, _ = _apply_local_fixes(new)
    old_norm = _polish_norm(o_fixed)
    new_norm = _polish_norm(n_fixed)
    o_tokens = [t for t in re.findall(r'\b[a-zA-ZçğıöşüÇĞİÖŞÜ]{3,}\b', old_norm)
                if t not in _CONTENT_DRIFT_STOPS]
    n_tokens = [t for t in re.findall(r'\b[a-zA-ZçğıöşüÇĞİÖŞÜ]{3,}\b', new_norm)
                if t not in _CONTENT_DRIFT_STOPS]
    if not o_tokens:
        return False
    # Find new tokens that don't share a stem with any old token
    new_only = set()
    for nt in n_tokens:
        if nt not in o_tokens and not _has_stem_match(nt, o_tokens):
            new_only.add(nt)
    if not new_only:
        return False
    # 3+ new stems → always drift (clear rewrite), source can't justify
    if len(new_only) >= 3:
        return True
    # 2 new stems → drift if old has ≥2 meaningful tokens, UNLESS source justifies it
    if len(new_only) == 2 and len(o_tokens) >= 2:
        if source_text:
            src_norm = _polish_norm(source_text)
            src_tokens = set(re.findall(r'\b[a-zA-Z]{3,}\b', src_norm))
            old_unique = set(o_tokens)
            # Source must have substantially more content than old captured
            # (≥5 source words AND ≥3 more than old) → old likely dropped content
            if len(src_tokens) >= 5 and len(src_tokens) >= len(old_unique) + 3:
                return False
        return True
    # 1 new stem → never drift (normal polish: intensifier, synonym, pronoun)
    return False


def _has_introduced_typo(old: str, new: str) -> bool:
    """Reject a suggestion that introduces a doubled-first-letter typo not present
    in the original (e.g. 'tek' -> 'ttek'). Scoped narrowly (token length >= 4
    before checking) so legitimate short interjections like 'Aaa'/'Ooo' are never
    flagged — those are always 2-3 chars and fall below the length floor.
    """
    if not old or not new:
        return False
    old_tokens = set(re.findall(r"[a-zA-ZçğıöşüÇĞİÖŞÜ]{2,}", old.lower()))
    new_tokens = re.findall(r"[a-zA-ZçğıöşüÇĞİÖŞÜ]{4,}", new.lower())
    for nt in new_tokens:
        if nt in old_tokens:
            continue
        if nt[0] == nt[1] and nt[1:] in old_tokens:
            return True
    return False


def _has_word_merge(old: str, new: str) -> bool:
    """Reject a suggestion that merges two ADJACENT Turkish words into one
    (e.g. 'ya törensel' -> 'yatörensel', F2 #183 — a real polish corruption
    that _has_introduced_typo does NOT catch, since it's a word-fusion, not a
    doubled first letter). new'deki 7+ harfli, old'da bulunmayan her token,
    old'daki iki ardışık token'ın bitişik birleşimine eşitse reddedilir."""
    if not old or not new:
        return False
    old_tokens = re.findall(r"[a-zçğıöşü]+", old.lower())
    new_tokens = re.findall(r"[a-zçğıöşü]+", new.lower())
    old_set = set(old_tokens)
    for nt in new_tokens:
        if len(nt) < 7 or nt in old_set:
            continue
        for i in range(len(old_tokens) - 1):
            if old_tokens[i] + old_tokens[i + 1] == nt:
                return True
    return False


def _has_char_deletion(old: str, new: str) -> bool:
    """Reject a polish suggestion that corrupted a word by DELETING one character,
    producing a shorter non-preserved token (e.g. 'nihai' -> 'ihai', 'battığını' ->
    'batığını' — real single-cue polish corruptions this session that neither
    find_garble_tokens nor _has_introduced_typo catches).

    ASYMMETRIC by design (no Turkish word-list available to check validity): only
    the SHORTENING direction is flagged, so legitimate fixes that ADD a char
    ('batdığını' -> 'battığını') never match. FP-guard: the deleted char must NOT be
    in the token's last 2 positions — final-region deletions overlap with legitimate
    Turkish case/suffix edits (genitive 'arabanın' -> accusative 'arabanı' drops a
    final 'n'), which are valid polish, not corruption.
    """
    if not old or not new:
        return False
    old_tokens = set(re.findall(r"[a-zçğıöşü]+", old.lower()))
    new_tokens = re.findall(r"[a-zçğıöşü]+", new.lower())
    for nt in new_tokens:
        if len(nt) < 4 or nt in old_tokens:
            continue
        for ot in old_tokens:
            if len(ot) != len(nt) + 1:
                continue
            for k in range(len(ot) - 2):  # son 2 pozisyonu atla (ek/durum düzeltmesi FP'si)
                if ot[:k] + ot[k + 1:] == nt:
                    return True
    return False


_MEDICAL_CONTEXT_RE = re.compile(r"\b(medical|doctor|anatom(?:y|ic)|ent|throat|nose|ear|tıbbi|doktor|anatomik)\b", re.I)


def _meaningful_drift_tokens(text: str) -> list[str]:
    return [
        t for t in re.findall(r'\b[a-zA-ZçğıöşüÇĞİÖŞÜ]{3,}\b', text)
        if t not in _CONTENT_DRIFT_STOPS
    ]


def _has_content_word_loss(old: str, new: str, source_text: str = "") -> bool:
    """Reject polish that drops key content words from the accepted Turkish line."""
    if not old or not new:
        return False
    o_fixed, _ = _apply_local_fixes(old)
    n_fixed, _ = _apply_local_fixes(new)
    old_norm = _polish_norm(o_fixed)
    new_norm = _polish_norm(n_fixed)
    o_tokens = _meaningful_drift_tokens(old_norm)
    n_tokens = _meaningful_drift_tokens(new_norm)
    if not o_tokens:
        return False
    missing = []
    matched = 0
    for ot in o_tokens:
        if ot in n_tokens or _has_stem_match(ot, n_tokens):
            matched += 1
        else:
            missing.append(ot)
    if not missing:
        return False
    if source_text:
        return len(missing) >= 2
    if len(o_tokens) <= 3:
        return len(o_tokens) >= 3 and len(missing) >= 2 and matched == 0
    return False


def _has_medical_adjective_deletion(source_text: str, original_text: str, candidate_text: str) -> bool:
    if not original_text or not candidate_text:
        return False
    old_norm = _polish_norm(_apply_local_fixes(original_text)[0])
    new_norm = _polish_norm(_apply_local_fixes(candidate_text)[0])
    if "tıbbi" not in old_norm or "tıbbi" in new_norm:
        return False
    src_norm = _polish_norm(source_text or "")
    return bool(_MEDICAL_CONTEXT_RE.search(src_norm) or _MEDICAL_CONTEXT_RE.search(old_norm))


def _has_proposition_drift(old: str, new: str, source_text: str = "") -> bool:
    """Reject polish that drops an ALL-CAPS proposition (>=4 chars) from the original."""
    if not old or not new:
        return False
    old_caps = set(re.findall(r'\b[A-ZÇĞİÖŞÜ]{4,}\b', old))
    if not old_caps:
        return False
    new_norm = _polish_norm(new)
    for cap in old_caps:
        cap_norm = _polish_norm(cap)
        if cap_norm not in new_norm:
            return True
    return False


def _reflow_to_line_count(text: str, target_lines: int) -> str:
    """candidate_text'i target_lines kadar satıra, kelime sınırında ve karakter
    sayısına göre dengeli biçimde yeniden sarar. Gerçek olay (2026-07-21, 5
    dosyalık koşu): Critic önerilerinin reddedilen bölümünün büyük çoğunluğu
    (ör. Metamorfose'da 181 reddin 165'i) SADECE satır SAYISI orijinalden
    farklı diye atılıyordu — içerik iyi olsa bile. Bu, atmadan ÖNCE öneriyi
    orijinalin satır sayısına yeniden sarmayı dener."""
    words = str(text or "").split()
    if not words or target_lines <= 1:
        return " ".join(words)
    total_len = sum(len(w) for w in words) + max(0, len(words) - 1)
    target_per_line = total_len / target_lines
    lines: list[str] = []
    current: list[str] = []
    current_len = 0
    for w in words:
        add_len = len(w) + (1 if current else 0)
        if current and current_len + add_len > target_per_line and len(lines) < target_lines - 1:
            lines.append(" ".join(current))
            current = [w]
            current_len = len(w)
        else:
            current.append(w)
            current_len += add_len
    lines.append(" ".join(current))
    return "\n".join(lines)


def validate_polish_candidate(
    original_text: str,
    candidate_text: str,
    source_text: str = "",
    neighbor_texts: list[str] | None = None,
    fragment_tag: str = "",
) -> tuple[bool, str]:
    """Fail closed when a polish suggestion breaks subtitle structure or hard tokens."""
    old = "" if original_text is None else str(original_text)
    new = "" if candidate_text is None else str(candidate_text)
    src = "" if source_text is None else str(source_text)
    if not new.strip():
        return False, "empty"
    if not old.strip() and new.strip():
        return False, "old_empty"
    if old.startswith("[HATA"):
        return False, "hata_placeholder"
    if old.strip() == "[ÇEVİRİ EKSİK]":
        return False, "missing_placeholder"
    if old.count("\n") != new.count("\n"):
        return False, "linebreak_count"
    if _POLISH_FORMAT_RE.findall(old) != _POLISH_FORMAT_RE.findall(new):
        return False, "format_tags"
    if _POLISH_BRACKET_LABEL_RE.findall(old) != _POLISH_BRACKET_LABEL_RE.findall(new):
        return False, "bracket_labels"
    old_numbers = _POLISH_NUMBER_RE.findall(old)
    if old_numbers:
        new_numbers = _POLISH_NUMBER_RE.findall(new)
        missing = [n for n in old_numbers if n not in new_numbers]
        if missing:
            return False, "numbers"
    old_has_dash = old.lstrip().startswith(("-", "–", "—"))
    new_has_dash = new.lstrip().startswith(("-", "–", "—"))
    if old_has_dash != new_has_dash:
        return False, "speaker_dash"
    if _has_english_backslide(old, new):
        return False, "english_backslide"
    if _has_new_english_residue(old, new):
        return False, "english_residue"
    if not _POLISH_MODEL_CORRUPTION_RE.search(old) and _POLISH_MODEL_CORRUPTION_RE.search(new):
        return False, "model_corruption"
    if _has_introduced_typo(old, new):
        return False, "introduced_typo"
    if _has_word_merge(old, new):
        return False, "word_merge"
    if _has_foreign_script_backslide(old, new):
        return False, "foreign_script"
    if not has_non_turkish_target_leak(old) and has_non_turkish_target_leak(new):
        return False, "non_turkish_target"
    if src and _has_source_echo(src, old, new):
        return False, "source_echo"
    if src and _has_english_reimport(src, old, new):
        return False, "english_reimport"
    if _has_english_article_reimport(old, new):
        return False, "english_article_reimport"
    if src and _has_to_name_reimport(src, old, new):
        return False, "to_name_reimport"
    if src and _source_negation_requires_turkish_negation(src) and not _has_turkish_negation(new):
        return False, "source_negation"
    if src and _has_explicit_answer_polarity_flip(src, new):
        return False, "source_polarity"
    if src and _question_mark_mismatch(src, new):
        return False, "source_question"
    if src and _numeric_token_mismatch(src, new):
        return False, "source_numbers"
    if _has_causative_want_backslide(old, new):
        return False, "causative_backslide"
    if src and _has_short_source_overexpansion(src, new):
        return False, "short_source_overexpansion"
    if src and _has_greek_word_explanation_loss(src, new):
        return False, "greek_word_loss"
    if src and _has_first_person_intent_shift(src, old, new):
        return False, "first_person_intent_shift"
    if _has_first_person_to_imperative_regression(old, new):
        return False, "first_person_intent_shift"
    if _has_head_to_face_regression(old, new):
        return False, "head_to_face_regression"
    if _has_research_to_hunting_regression(old, new):
        return False, "research_to_hunting_regression"
    if _has_oddities_intro_regression(old, new):
        return False, "oddities_intro_regression"
    if _has_fragment_expansion_regression(old, new):
        return False, "fragment_expansion_regression"
    if _has_stray_o_learning_regression(old, new):
        return False, "stray_o_learning_regression"
    if _has_welcome_deletion(old, new):
        return False, "welcome_deletion"
    if _has_lets_see_to_imperative_regression(old, new):
        return False, "lets_see_to_imperative_regression"
    if _has_invitation_subject_regression(old, new):
        return False, "invitation_subject_regression"
    if _has_oddities_intro_idiom_regression(old, new):
        return False, "oddities_intro_idiom_regression"
    if _has_grandma_to_mother_regression(old, new):
        return False, "grandma_to_mother_regression"
    if _has_unnecessary_da_deletion(old, new):
        return False, "unnecessary_da_deletion"
    if _has_oddities_title_case_regression(old, new):
        return False, "oddities_title_case_regression"
    if _has_woodstock_regression(old, new):
        return False, "proper_noun_regression"
    if _has_turkish_question_loss(old, new):
        return False, "turkish_question_loss"
    if _has_neighbor_echo(old, new, neighbor_texts):
        return False, "neighbor_echo"
    if neighbor_texts and _has_neighbor_semantic_copy(old, new, neighbor_texts):
        return False, "neighbor_semantic_copy"
    if neighbor_texts and _has_neighbor_prefix_echo_text(old, new, neighbor_texts):
        return False, "neighbor_prefix_echo"
    if _has_fragment_terminal_backslide(old, new, fragment_tag):
        return False, "fragment_terminal"
    if _has_destructive_shorten(old, new):
        return False, "too_short"
    if _has_question_regression(old, new):
        return False, "question_regression"
    if _has_fragment_redistribution_regression(old, new):
        return False, "fragment_redistribution_regression"
    if _has_medical_adjective_deletion(src, old, new):
        return False, "medical_adjective_deletion"
    if _has_proposition_drift(old, new, source_text=src):
        return False, "proposition_drift"
    if _has_content_word_drift(old, new, source_text=src):
        return False, "content_word_drift"
    if _has_content_word_loss(old, new, source_text=src):
        return False, "content_word_loss"
    # Son-çare yapısal kontrol: anlam-düzeyli guard'lardan (negation/question/drift/loss)
    # SONRA — "Bilmiyorum"->"Biliyorum" hem char-deletion hem negation-loss'tur; daha
    # anlamlı olan source_negation reason'ı kazansın diye burada, en sonda.
    if _has_char_deletion(old, new):
        return False, "char_deletion"
    max_len = max(len(old) * 2 + 20, len(old) + 80)
    if len(new) > max_len:
        return False, "too_long"
    return True, ""


def apply_polish_group_atomic(proposals: dict, original_by_id: dict,
                              group_expected: dict | None = None,
                              src_map: dict | None = None) -> tuple[dict, int, dict]:
    """Grup-atomik Polish kabul mantığı (bkz. plans/polish-group-atomicity-brief.md,
    plans/quality-round2-fixes-brief.md Görev B).

    proposals: {sid: (new_text, ok, reason, group_id)} — her cue için model önerisi,
    validate_polish_candidate sonucu ve (varsa) fragment grup id'si.
    original_by_id: {sid: original_text} — değişip değişmediğini belirlemek için.
    group_expected: {group_id: [sid, ...]} — grubun BEKLENEN üyeleri, cue sırasında.
    None ise (v1 davranış) yalnız proposals'ta DÖNEN üyeler arasında hep-ya-da-hiç
    uygulanır; kısmi-yanıt ve birleşik-anlam kontrolleri ATLANIR.
    src_map: {sid: kaynak metin} — birleşik-anlam doğrulaması için (group_expected
    verilmişse kullanılır).

    Bir fragment grubunda DEĞİŞEN üyelerden biri reddedildiyse, o grubun HİÇBİR
    değişikliği uygulanmaz. group_expected verilmişse ayrıca: (a) grubun beklenen
    üyelerinden biri modelden hiç DÖNMEMİŞSE grup geri alınır (cümle bütünlüğü ancak
    grubun tamamı görülerek doğrulanabilir), (b) beklenen üyeler cue sırasında
    birleştirilip validate_polish_candidate ile birleşik-anlam kontrolünden geçirilir
    (kelime cue'lar arasında taşınırsa geçer, tamamen düşerse yakalanır). Singleton
    cue'lar bağımsız uygulanır.

    Returns (result_map, rejected_count, rejected_reasons)."""
    from collections import defaultdict
    result_map: dict = {}
    rejected = 0
    rejected_reasons: dict = {}

    if group_expected is not None:
        sid_to_group = {}
        for gid, sids in group_expected.items():
            for s in sids:
                sid_to_group[s] = gid
    else:
        sid_to_group = {
            sid: group_id
            for sid, (_new_text, _ok, _reason, group_id) in proposals.items()
            if group_id is not None
        }

    singles = []
    group_members: dict = defaultdict(list)
    for sid in proposals:
        gid = sid_to_group.get(sid)
        if gid is None:
            singles.append(sid)
        else:
            group_members[gid].append(sid)

    for sid in singles:
        new_text, ok, reason, _group_id = proposals[sid]
        if ok:
            result_map[sid] = new_text
        else:
            rejected += 1
            rejected_reasons[reason] = rejected_reasons.get(reason, 0) + 1

    for group_id, sids in group_members.items():
        changed = [s for s in sids if proposals[s][0] != original_by_id.get(s)]
        if not changed:
            continue

        all_ok = all(proposals[s][1] for s in changed)
        if not all_ok:
            fail_reason = next((proposals[s][2] for s in changed if not proposals[s][1]),
                                "group_atomic_reject")
            key = "group_atomic:" + str(fail_reason)
            rejected += len(changed)
            rejected_reasons[key] = rejected_reasons.get(key, 0) + len(changed)
            continue

        if group_expected is not None:
            expected_members = group_expected.get(group_id, sids)
            missing = [s for s in expected_members if s not in proposals]
            if missing:
                key = "group_atomic:partial_response"
                rejected += len(changed)
                rejected_reasons[key] = rejected_reasons.get(key, 0) + len(changed)
                continue

            old_joined = "\n".join(original_by_id.get(s, "") for s in expected_members)
            new_joined = "\n".join(
                proposals[s][0] if s in proposals else original_by_id.get(s, "")
                for s in expected_members)
            src_joined = " ".join(
                s2 for s2 in (
                    (src_map or {}).get(s, "").strip() for s in expected_members
                ) if s2)
            joined_ok, joined_reason = validate_polish_candidate(
                old_joined, new_joined, source_text=src_joined)
            if not joined_ok:
                key = "group_atomic_joined:" + str(joined_reason)
                rejected += len(changed)
                rejected_reasons[key] = rejected_reasons.get(key, 0) + len(changed)
                continue

        for s in changed:
            result_map[s] = proposals[s][0]

    return result_map, rejected, rejected_reasons


def validate_condense_candidate(original_text: str, candidate_text: str,
                                source_text: str = "") -> tuple[bool, str]:
    """condense_fast_lines için DAR güvenlik doğrulaması. validate_polish_candidate'in
    yalnızca güvenlik-kritik, KISALTMAYLA ÇATIŞMAYAN alt-kümesi — kelime-kaybı/çok-kısa
    kontrolleri BİLEREK yok (condense kelime atmayı kasıtlı yapar). fail-closed:
    (True,"") kabul, (False,reason) reddet → çağıran orijinali korur."""
    old = "" if original_text is None else str(original_text)
    new = "" if candidate_text is None else str(candidate_text)
    src = "" if source_text is None else str(source_text)
    if not new.strip():
        return False, "empty"
    if _POLISH_FORMAT_RE.findall(old) != _POLISH_FORMAT_RE.findall(new):
        return False, "format_tags"
    if _POLISH_BRACKET_LABEL_RE.findall(old) != _POLISH_BRACKET_LABEL_RE.findall(new):
        return False, "bracket_labels"
    old_numbers = _POLISH_NUMBER_RE.findall(old)
    if old_numbers:
        new_numbers = _POLISH_NUMBER_RE.findall(new)
        if any(n not in new_numbers for n in old_numbers):
            return False, "numbers"
    if old.lstrip().startswith(("-", "–", "—")) != new.lstrip().startswith(("-", "–", "—")):
        return False, "speaker_dash"
    if _has_english_backslide(old, new):
        return False, "english_backslide"
    if _has_new_english_residue(old, new):
        return False, "english_residue"
    if not _POLISH_MODEL_CORRUPTION_RE.search(old) and _POLISH_MODEL_CORRUPTION_RE.search(new):
        return False, "model_corruption"
    if _has_introduced_typo(old, new):
        return False, "introduced_typo"
    if _has_foreign_script_backslide(old, new):
        return False, "foreign_script"
    if not has_non_turkish_target_leak(old) and has_non_turkish_target_leak(new):
        return False, "non_turkish_target"
    if src and _source_negation_requires_turkish_negation(src) and not _has_turkish_negation(new):
        return False, "source_negation"
    if _has_content_word_drift(old, new, source_text=src):
        return False, "content_word_drift"
    return True, ""


def _apply_local_fixes(text: str) -> tuple[str, int]:
    """Apply instant regex-based fixes. Returns (fixed_text, n_fixes)."""
    count = 0
    for pattern, replacement in _LOCAL_FIXES:
        new = pattern.sub(replacement, text)
        if new != text:
            count += 1
            text = new
    return text, count


def consistency_sweep(
    cues: list,
    tr_blocks: list,
    log_fn=None,
    minority_threshold: float | None = None,
    min_words: int = 3,
) -> tuple:
    """Normalize recurring source phrases to their most common translation.
    By default, only normalizes when a strict majority (>50%) of occurrences agree.
    minority_threshold can loosen that rule by allowing a bounded non-winning share.
    Accepts cue objects (.index/.text) or (idx, ts, text) tuples.
    Returns (corrected_tr_blocks, n_fixes)."""
    from collections import Counter, defaultdict

    if not cues or not tr_blocks:
        return tr_blocks, 0

    orig_dict: dict = {}
    for c in cues:
        # Dikkat: tuple'ın yerleşik .index METODU vardır — ayrımı .text ile yap
        if hasattr(c, "text"):
            orig_dict[str(c.index)] = _clean_source_text(c.text).strip().lower()
        else:
            orig_dict[str(c[0])] = _clean_source_text(c[2]).strip().lower()
    result = list(tr_blocks)

    # Group translated lines by their normalized source text
    source_groups: dict = defaultdict(list)   # src → [(result_pos, tr_text)]
    for i, (idx, ts, text) in enumerate(result):
        src = orig_dict.get(str(idx), "")
        # Default keeps the older ≥3-word guard; callers can lower it for stricter sweeps.
        if src and text and text != "[HATA]" and len(src.split()) >= min_words:
            source_groups[src].append((i, text))

    fixes = 0
    for src, positions in source_groups.items():
        if len(positions) < 2:
            continue
        counter = Counter(tr for _, tr in positions)
        if len(counter) == 1:
            continue  # all already consistent
        clean_common = [
            (tr, count) for tr, count in counter.most_common()
            if not has_non_turkish_target_leak(tr)
        ]
        if not clean_common:
            continue
        best_tr, best_count = clean_common[0]
        if minority_threshold is None:
            should_normalize = best_count > len(positions) / 2
        else:
            threshold = max(0.0, min(1.0, float(minority_threshold)))
            second_count = counter.most_common(2)[1][1] if len(counter) > 1 else 0
            non_winning_share = (len(positions) - best_count) / len(positions)
            should_normalize = best_count > second_count and non_winning_share <= threshold
        if should_normalize:
            for pos, tr in positions:
                if tr != best_tr:
                    old_idx, old_ts, _ = result[pos]
                    result[pos] = (old_idx, old_ts, best_tr)
                    fixes += 1

    if log_fn:
        if fixes:
            log_fn(f"Consistency sweep: {fixes} tekrar tutarsızlığı normalize edildi", "ok")
        else:
            log_fn("Consistency sweep: tutarsızlık bulunamadı ✓", "ok")

    return result, fixes


def final_consistency_sweep(
    cues: list,
    tr_blocks: list,
    log_fn=None,
    min_words: int = 3,
) -> tuple:
    """Run a second, safety-checked consistency sweep after critic/polish edits."""
    swept, fixes = consistency_sweep(cues, tr_blocks, log_fn=None, min_words=min_words)
    if not fixes:
        # first_seen fallback kaldırıldı — bağlam-kördü: majority sweep anlaşamadığında
        # (yani bağlam-bağımlılığın en olası olduğu durumda) ilk görülen çeviriyi diğer
        # tekrarlara dayatmak yanlış olabilir ("Come on." sahneye göre farklı çevrilebilir).
        return list(tr_blocks), 0
    result = list(tr_blocks)
    orig_dict = {}
    for c in (cues or []):
        if hasattr(c, "text"):
            orig_dict[str(c.index)] = _clean_source_text(c.text).strip()
        else:
            orig_dict[str(c[0])] = _clean_source_text(c[2]).strip()
    accepted = 0
    for pos, (old_block, new_block) in enumerate(zip(tr_blocks, swept)):
        if old_block[2] == new_block[2]:
            continue
        old_idx, old_ts, old_text = old_block
        new_text = new_block[2]
        if str(new_text).strip() in {"[ÇEVİRİ EKSİK]", "[HATA]"} or str(new_text).startswith("[HATA"):
            continue
        ok, _reason = validate_polish_candidate(
            old_text,
            new_text,
            source_text=orig_dict.get(str(old_idx), ""),
        )
        if ok:
            result[pos] = (old_idx, old_ts, new_text)
            accepted += 1
    if log_fn and accepted:
        log_fn(f"Final consistency sweep: {accepted} tutarsızlık normalize edildi", "ok")
    return result, accepted


# ── QC Auto-Fix ───────────────────────────────────────────────────────────────

def qc_auto_fix(
    issues: list,
    tr_blocks: list,
    openai_api_key: str = None,
    model: str = "",
    tgt_lang: str = "Turkish",
    base_url: str = "",
    helper_url: str = "",
    log_fn=None,
    helper_api_key: str = None,
) -> list:
    """Re-translate QC-flagged blocks with explicit error feedback via OpenAI / Helper LLM.

    Each approved issue is re-sent to the translator with the problem description
    and suggestion as guidance — producing a proper re-translation instead of
    blindly applying the QC suggestion text.

    Falls back to applying suggestion text directly if the API call fails.

    Args:
        issues:  approved QC issues [{id, original, current, problem, suggestion}]
        tr_blocks: current translated blocks [(idx, ts, text), ...]

    Returns updated tr_blocks with corrections applied.
    """
    if not issues:
        return tr_blocks

    api_key = helper_api_key or openai_api_key
    try:
        from openai import OpenAI
        client = OpenAI(api_key=api_key, base_url=(helper_url or base_url or None))
    except Exception as e:
        if log_fn:
            log_fn(f"QC Auto-Fix bağlantı hatası: {e}", "err")
        return tr_blocks

    result = list(tr_blocks)
    idx_to_pos = {str(b[0]): i for i, b in enumerate(result)}

    system = (
        f"You are a professional subtitle translator fixing a specific error in a {tgt_lang} translation. "
        f"Output ONLY the corrected {tgt_lang} subtitle text. No explanations, no quotes."
    )

    fixed = 0
    seen_issue_ids = set()
    for issue in issues:
        if not isinstance(issue, dict):
            continue
        issue_id   = str(issue.get("id", ""))
        problem    = issue.get("problem", "")
        current    = issue.get("current", "")
        suggestion = issue.get("suggestion", "")
        source     = issue.get("original", "")

        if not issue_id or issue_id in seen_issue_ids or issue_id not in idx_to_pos:
            continue

        pos = idx_to_pos[issue_id]
        old_idx, old_ts, old_text = result[pos]

        # Model 'current' metni ile gerçek cue metnini reconcile et
        clean_curr = _normalize_qc_match_text(current)
        clean_old = _normalize_qc_match_text(old_text)
        if not clean_curr or not clean_old or clean_curr != clean_old:
            if log_fn:
                log_fn(f"QC Auto-Fix #{issue_id} atlandı: model 'current' metni ({repr(str(current)[:30])}) "
                       f"gerçek cue metni ({repr(str(old_text)[:30])}) ile uyuşmuyor", "warn")
            continue

        seen_issue_ids.add(issue_id)

        user_msg = (
            f"Source: {source}\n"
            f"Wrong translation: {current or old_text}\n"
            f"Problem: {problem}\n"
            f"Hint: {suggestion}\n\n"
            f"Provide the corrected {tgt_lang} translation:"
        )

        api_applied = False
        try:
            resp = _safe_chat_create(
                client,
                model=model,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user",   "content": user_msg},
                ],
                max_completion_tokens=300,
                temperature=0.2,
            )
            new_text = (resp.choices[0].message.content or "").strip() if resp.choices else ""
            if new_text and new_text != "[HATA]":
                ok, _reason = validate_polish_candidate(old_text, new_text, source_text=source)
                if ok:
                    result[pos] = (old_idx, old_ts, new_text)
                    fixed += 1
                    api_applied = True
                elif log_fn:
                    log_fn(f"QC Auto-Fix #{issue_id} güvenlik filtresinden döndü ({_reason}) — öneri denecek", "warn")
        except Exception as e:
            if log_fn:
                log_fn(f"QC Auto-Fix #{issue_id} hatası: {e} — öneri denecek", "warn")

        if api_applied:
            continue

        # Fallback öneri metni de mutlaka validator'dan geçmeli
        if suggestion:
            sugg_text = str(suggestion).strip()
            if sugg_text and sugg_text != "[HATA]":
                ok_sugg, _reason_sugg = validate_polish_candidate(old_text, sugg_text, source_text=source)
                if ok_sugg:
                    result[pos] = (old_idx, old_ts, sugg_text)
                    fixed += 1
                elif log_fn:
                    log_fn(f"QC Auto-Fix #{issue_id} öneri metni güvenlik filtresinden reddedildi ({_reason_sugg}) — atlandı", "warn")

    if log_fn:
        log_fn(f"QC Auto-Fix: {fixed}/{len(issues)} satır yeniden çevrildi ✓", "ok")

    return result


# ── Otomatik Sözlük Oluşturucu ────────────────────────────────────────────────

def build_glossary_suggestions(
    cues: list,
    tr_blocks: list,
    src_lang: str,
    tgt_lang: str,
    helper_api_key: str,
    helper_url: str = "https://api.openai.com/v1",
    helper_model: str = "gpt-5.4-mini",
    existing_glossary: dict = None,
    log_fn=None,
) -> list:
    """Extract translation pairs worth adding to the glossary from a completed translation.

    Identifies proper nouns, technical terms, idiomatic expressions, and recurring
    phrases that received a deliberate translation choice.

    Args:
        existing_glossary: terms already in the glossary (excluded from suggestions)

    Returns list of {src, tgt, category, reason} dicts.
    """
    if not cues or not tr_blocks:
        return []

    try:
        from openai import OpenAI
        client = OpenAI(api_key=helper_api_key, base_url=helper_url)
    except Exception as e:
        if log_fn:
            log_fn(f"Glossary builder bağlantı hatası: {e}", "err")
        return []

    tr_dict = {str(idx): text for idx, ts, text in tr_blocks}
    pairs = []
    for c in cues:
        src = _clean_source_text(c.text)
        tgt_text = tr_dict.get(str(c.index), "")
        if src and tgt_text and tgt_text != "[HATA]":
            pairs.append({"src": src, "tgt": tgt_text})

    if not pairs:
        return []

    # Tüm dosyaya eşit yayılan 200 örnek (eskiden 400'e adımlayıp 200'e kırpınca yalnız
    # dosyanın ilk yarısı örnekleniyordu → sondaki terimler sözlüğe hiç girmiyordu)
    step = max(1, len(pairs) // 200)
    sample = pairs[::step][:200]

    existing_keys = set((existing_glossary or {}).keys())
    existing_hint = ", ".join(list(existing_keys)[:40]) if existing_keys else "none"

    prompt = (
        f"Analyze this completed {src_lang}→{tgt_lang} subtitle translation.\n"
        f"Identify translation pairs worth saving to a reusable terminology glossary.\n\n"
        f"Focus on:\n"
        f"1. proper_noun — character names, places, organizations, products\n"
        f"2. technical — specialized vocabulary with deliberate translation choice\n"
        f"3. idiom — phrase where non-literal translation was used\n"
        f"4. recurring — multi-word phrase appearing several times\n\n"
        f"Exclude: common everyday words, pronouns, basic verbs, single-word filler.\n"
        f"Already in glossary (exclude these): {existing_hint}\n\n"
        f"Translation sample:\n{json.dumps(sample, ensure_ascii=False)}\n\n"
        f'Return JSON: {{"suggestions": ['
        f'{{"src": "...", "tgt": "...", "category": "proper_noun|technical|idiom|recurring", "reason": "..."}}]}}\n'
        f"Max 30 suggestions. Return ONLY the JSON."
    )

    try:
        resp = _safe_chat_create(
            client,
            model=helper_model,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=1500,
            temperature=0.2,
        )
        raw = (resp.choices[0].message.content or "").strip()
        if not raw:
            return []
        if raw.startswith("```"):
            raw = "\n".join(raw.split("\n")[1:]).rsplit("```", 1)[0].strip()
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            if "{" in raw and "}" in raw:
                s, e2 = raw.find("{"), raw.rfind("}") + 1
                try:
                    data = json.loads(raw[s:e2])
                except Exception:
                    return []
            else:
                return []

        # LLM bazen {"suggestions": [...]} yerine doğrudan [...] döner
        if isinstance(data, list):
            suggestions = data
        else:
            suggestions = data.get("suggestions", []) if isinstance(data, dict) else []
        lower_existing = {k.lower() for k in existing_keys}
        new_suggestions = [
            sg for sg in suggestions
            if sg.get("src") and sg.get("tgt")
            and sg["src"].lower() not in lower_existing
        ]

        if log_fn:
            log_fn(f"Glossary builder: {len(new_suggestions)} yeni terim önerildi", "ok")
        return new_suggestions

    except Exception as e:
        if log_fn:
            log_fn(f"Glossary builder hatası: {e}", "err")
        return []


def critic_pass_with_helper(
    cues: list,
    tr_blocks: list,
    helper_api_key: str,
    helper_url: str = "https://api.openai.com/v1",
    helper_model: str = "gpt-5.4-mini",
    tgt_lang: str = "Turkish",
    log_fn=None,
    glossary: dict = None,
    analysis_result=None,  # Optional: (ContextMemory, char_examples, pronoun_map)
    change_log: list | None = None,
) -> list:
    """Two-stage critic pass:
    Stage 1 — Local regex fixes (instant): known English slang patterns.
    Stage 2 — Helper review (fast): ONLY suspicious lines, not the whole file.
    Returns improved blocks list [(idx, ts, text), ...].

    Args:
        analysis_result: Optional tuple of (ContextMemory, char_examples_dict, pronoun_map)
            from analyze_with_helper() to provide context for better fixes.
        change_log: Optional list; if given, each ACTUALLY applied fix appends
            {"id","reason","source","before","after"} — caller can write a
            before/after change report (bkz. QC'nin qc_degisiklikler.txt'i,
            2026-07-20 — Critic 150-200 satır değiştirebiliyor ama hangi
            satırın NEDEN değiştiğini kimse göremiyordu).
    """

    if not tr_blocks:
        return tr_blocks

    result     = list(tr_blocks)
    idx_to_pos = {str(b[0]): i for i, b in enumerate(result)}
    orig_dict  = {str(c.index): c.text for c in cues} if cues else {}
    result_ids = [str(b[0]) for b in result]
    tr_text_by_id = {str(b[0]): b[2] for b in result}
    frag_tags = {}
    frag_group_by_id = {}
    if cues:
        try:
            frag_tags = _tag_fragments(cues)
        except Exception:
            frag_tags = {}
        current_group = []
        for c in cues:
            cid = str(c.index)
            tag = frag_tags.get(c.index) or frag_tags.get(cid)
            if tag == "start":
                current_group = [cid]
            elif tag == "mid" and current_group:
                current_group.append(cid)
            elif tag == "end" and current_group:
                current_group.append(cid)
                for gid in current_group:
                    frag_group_by_id[gid] = list(current_group)
                current_group = []
            elif tag != "mid":
                current_group = []

    # ── Stage 1: instant local fixes ─────────────────────────────────────────
    local_fixed = 0
    for i, (idx, ts, text) in enumerate(result):
        if not text or text == "[HATA]":
            continue
        fixed, n = _apply_local_fixes(text)
        if n:
            result[i] = (idx, ts, fixed)
            local_fixed += 1

    if log_fn and local_fixed:
        log_fn(f"Critic Pass (local): {local_fixed} transliterasyon düzeltildi", "ok")

    # ── Stage 2: Helper — only suspicious lines ──────────────────────────────
    # Deterministic validators first (fast, no API call)
    validator_hits: set = set()
    v_reasons: dict = {}
    for v_idx, _, _, reason in run_validators(result, cues, glossary):
        key = str(v_idx)
        validator_hits.add(key)
        v_reasons[key] = reason

    helper_ids = set()
    for idx, ts, text in result:
        sid = str(idx)
        if text and text != "[HATA]" and (_SUSPICIOUS_PATTERN.search(text) or sid in validator_hits):
            helper_ids.add(sid)
    flow_group_reason_tokens = (
        "EARLY_VERB_CLOSURE",
        "DANGLING_TURKISH_FRAGMENT",
        "ORPHAN_FRAGMENT",
        "SHORT_SOURCE_OVEREXPANSION",
        "BROKEN_FRAGMENT_FLOW",
    )
    flow_reasons_by_id: dict[str, set[str]] = {}
    for sid, reason in v_reasons.items():
        if any(token in reason for token in flow_group_reason_tokens):
            group_ids = frag_group_by_id.get(sid, [sid])
            helper_ids.update(group_ids)
            for gid in group_ids:
                flow_reasons_by_id.setdefault(str(gid), set()).update(
                    token.strip() for token in re.split(r"[;,|]", reason) if token.strip()
                )
        if "SPEAKER_LABEL_ABSORBED_TEXT" in reason:
            helper_ids.add(sid)
            pos = idx_to_pos.get(sid)
            if pos is not None and pos + 1 < len(result_ids):
                helper_ids.add(result_ids[pos + 1])
        if "BROKEN_FRAGMENT_FLOW" in reason:
            pos = idx_to_pos.get(sid)
            if pos is not None:
                if pos > 0:
                    helper_ids.add(result_ids[pos - 1])
                helper_ids.add(sid)
                if pos + 1 < len(result_ids):
                    helper_ids.add(result_ids[pos + 1])

    suspicious = [
        (idx, ts, text)
        for idx, ts, text in result
        if text and text != "[HATA]" and str(idx) in helper_ids
    ]

    if not suspicious:
        if log_fn:
            log_fn("Critic Pass (Helper): şüpheli satır yok, atlanıyor ✓", "ok")
        return result

    v_count = len(validator_hits)
    p_count = sum(1 for idx, ts, text in suspicious
                  if _SUSPICIOUS_PATTERN.search(text))
    flow_count = sum(1 for reason in v_reasons.values()
                     if any(token in reason for token in flow_group_reason_tokens))
    if log_fn:
        log_fn(
            f"Critic Pass (Helper): {len(suspicious)} şüpheli satır "
            f"(pattern:{p_count}, validator:{v_count}, flow:{flow_count}) inceleniyor...", "info"
        )

    try:
        from openai import OpenAI
        client = OpenAI(api_key=helper_api_key, base_url=helper_url)
    except Exception as e:
        if log_fn:
            log_fn(f"Critic Pass Helper bağlantı hatası: {e}", "err")
        return result

    # Build context-aware prompt
    context_info = ""
    if analysis_result:
        try:
            context, char_examples, pronoun_map = analysis_result[:3]
            character_styles = analysis_result[3] if len(analysis_result) > 3 else None
            context_parts = []

            if context.tone:
                context_parts.append(f"Tone: {context.tone}")

            if context.setting:
                context_parts.append(f"Setting: {context.setting}")

            if pronoun_map:
                context_parts.append(f"Register patterns (sen/siz): {pronoun_map}")

            if character_styles:
                style_lines = []
                for name, info in list(character_styles.items())[:8]:
                    reg = info.get("register", "") if isinstance(info, dict) else ""
                    if reg:
                        style_lines.append(f"  {name}: {reg}")
                if style_lines:
                    context_parts.append("Character voices:\n" + "\n".join(style_lines))

            if context_parts:
                context_info = "\n\nContent Context:\n" + "\n".join(context_parts)
        except Exception as e:
            if log_fn:
                log_fn(f"Critic context injection hatası (ignored): {e}", "warn")

    # Turkish-specific error patterns
    turkish_fixes = (
        "\n\nTurkish-Specific Issues to Fix:\n"
        "1. Leftover English: Transliterated words or English phrases in Turkish subtitle\n"
        "2. Sen/Siz Register: Verify formal/informal pronoun matches the relationship/tone\n"
        "   If reason includes REGISTER_FLIP, compare the speaker's established address pattern and fix only the "
        "minority line if it is an accidental sen/siz switch.\n"
        "3. Unnatural Phrasing: Word order or verb conjugation that violates Turkish conventions\n"
        "   If reason includes BAD_TURKISH_CASE_FLOW, fix the Turkish case/word-order break "
        "(e.g. genitive '-in/-ın' used where an object '-i/-ı' or reordered phrase is required).\n"
        "4. Over-Particles: Remove unnecessary 'mi', 'mu', 'de', 'da', 'ki' that clutter the phrase\n"
        "5. Verbal Noun Errors: Replace mechanical '-ıyor' with natural '-arak', '-ince', or imperatives\n"
        "6. Cross-Cue Turkish Flow: fix EARLY_VERB_CLOSURE by keeping start/mid fragments open and "
        "placing the finite Turkish verb at the natural final fragment when the source sentence continues\n"
        "7. Meaning Preservation: fix NEGATION_LOSS, QUESTION_MARK_MISMATCH, NUMBER_MISMATCH, and "
        "SPELLED_NUMBER_MISMATCH. Negative source lines must remain negative; questions must remain "
        "questions; digits, dates, and quantities must preserve the same numeric value, whether written "
        "as digits or spelled out (e.g. source 'fourteen hundred' must become Turkish 'bin dört yüz', "
        "not a literal word-for-word 'on dört yüz')\n"
        "8. Read-Aloud Flow & CPS: if Turkish reads choppy, overly mechanical, or too long for the cue duration, "
        "rewrite it with natural spoken Turkish word order. Duration/CPS beats source length: aim for <=21 CPS "
        "and avoid >24 CPS when possible without dropping facts\n"
        "9. Speaker-only cue integrity: if the source cue is only a speaker label like 'Ryan:', the translation "
        "must stay only that label. Do not absorb the next cue's dialogue into it; move dialogue back to the "
        "following cue when needed\n"
        "10. Profanity Intensity: if reason includes PROFANITY_INTENSITY_MISMATCH, the source has strong "
        "profanity but the Turkish is too soft (or vice versa). Match the original intensity: "
        "mild → 'lanet/kahretsin', moderate → 'bok/göt', strong → 'sik/amk/orospu çocuğu'."
    )

    # Send all suspicious lines in one shot (they're already filtered, should be small).
    # 300'den 100'e indirildi (2026-07-21): bir chunk'ın JSON'ı bozuk/kesik dönerse
    # o chunk'taki TÜM satırlar (300'e kadar) sessizce atlanıyordu -- daha küçük
    # chunk, bir hata olduğunda kaybı sınırlar.
    MINIMAX_CHUNK = 100
    mm_fixed = 0
    reflow_recovered = 0
    critic_rejected = 0
    critic_rejected_reasons: dict[str, int] = {}
    reason_stats: dict[str, dict[str, int]] = {}

    def _reason_tokens(reason_str: str) -> list[str]:
        if not reason_str:
            return ["PATTERN_ONLY"]
        toks = [tok.split("(", 1)[0].strip() for tok in reason_str.split("|")]
        return [t for t in toks if t] or ["PATTERN_ONLY"]

    for chunk_start in range(0, len(suspicious), MINIMAX_CHUNK):
        chunk = suspicious[chunk_start:chunk_start + MINIMAX_CHUNK]
        chunk_ids = {str(idx) for idx, _ts, _text in chunk}
        pairs = []
        for idx, ts, text in chunk:
            pair = {"id": str(idx), "orig": orig_dict.get(str(idx), ""), "tr": text}
            duration = _block_duration(str(ts))
            if duration > 0:
                pair["d"] = round(duration, 2)
                pair["cps"] = round(cps(str(text), duration), 1)
            tag = frag_tags.get(idx) or frag_tags.get(str(idx))
            if tag and tag != "none":
                pair["frag"] = tag
                group_ids = frag_group_by_id.get(str(idx))
                if group_ids:
                    pair["frag_group"] = group_ids
                    pair["group_orig"] = " ".join(
                        orig_dict.get(gid, "") for gid in group_ids
                        if orig_dict.get(gid, "")
                    )
                    pair["group_tr"] = " ".join(
                        tr_text_by_id.get(gid, "") for gid in group_ids
                        if tr_text_by_id.get(gid, "")
                    )
            reason = v_reasons.get(str(idx), "")
            if reason:
                pair["reason"] = reason
                structural_reasons = (
                    "SPEAKER_LABEL_MISMATCH",
                    "SPEAKER_LABEL_ABSORBED_TEXT",
                    "LENGTH_RATIO_OUTLIER",
                    "PUNCT_ONLY_TRANSLATION",
                )
                if any(token in reason for token in structural_reasons):
                    pos = idx_to_pos.get(str(idx))
                    if pos is not None and pos > 0:
                        prev_id = result_ids[pos - 1]
                        pair["prev"] = {
                            "id": prev_id,
                            "orig": orig_dict.get(prev_id, ""),
                            "tr": tr_text_by_id.get(prev_id, ""),
                        }
                    if pos is not None and pos + 1 < len(result_ids):
                        next_id = result_ids[pos + 1]
                        pair["next"] = {
                            "id": next_id,
                            "orig": orig_dict.get(next_id, ""),
                            "tr": tr_text_by_id.get(next_id, ""),
                        }
            if any(token in reason for token in flow_group_reason_tokens):
                pair["must_fix_flow"] = True
            # Sözlük/dizi hafızası kaçağı tespit edildiyse zorunlu karşılığı fixer'a ilet (#6)
            try:
                for tok in (reason or "").split("|"):
                    if ("=>" in tok and ("GLOSS_MISS:" in tok or "SERIES_MEMORY_FLIP:" in tok)):
                        prefix = "GLOSS_MISS:" if "GLOSS_MISS:" in tok else "SERIES_MEMORY_FLIP:"
                        src_t, tr_t = tok[len(prefix):].split("=>", 1)
                        if src_t.strip() and tr_t.strip():
                            pair["must_use"] = {src_t: tr_t}
                        break
            except Exception:
                pass
            pairs.append(pair)

        prompt = (
            f"You are a professional {tgt_lang} subtitle editor. "
            f"These lines were flagged as potentially containing errors.{context_info}\n\n"
            f"{turkish_fixes}\n\n"
            f"GLOSSARY: if a line has a \"must_use\" field {{source: target}}, the {tgt_lang} text MUST "
            f"contain that exact target term (rewrite the line to include it, keeping it natural).\n\n"
            f"CROSS-CUE FLOW: items may include frag='start|mid|end', frag_group, group_orig, and group_tr. "
            f"Those items are parts of one source sentence; read group_orig as the complete source sentence "
            f"before editing any single subtitle line.\n"
            f"MANDATORY FLOW FIX: if an item has must_fix_flow=true or reason includes EARLY_VERB_CLOSURE, "
            f"DANGLING_TURKISH_FRAGMENT, ORPHAN_FRAGMENT, or SHORT_SOURCE_OVEREXPANSION, do NOT treat it "
            f"as a stylistic preference. The Turkish group is incomplete, closes too early, or distributes "
            f"the meaning unnaturally. Return fixes for the affected ids in the frag_group unless doing so "
            f"would change the meaning. Keep start/mid fragments open and let the final frag='end' line "
            f"carry the natural finite Turkish verb when the source sentence continues.\n"
            f"Example:\n"
            f"  Bad: id 4 'Ufak bir tadını alacaksınız' + id 5 'bir fosseptik teknisyeni olmanın ne demek olduğunun.'\n"
            f"  Better: id 4 'Fosseptik teknisyenliğinin' + id 5 'nasıl bir şey olduğunu tadacaksınız.'\n"
            f"Preserve the total meaning across the group and keep each subtitle concise.\n\n"
            f"PARENTHETICAL NOTE FIX: if reason includes PAREN_NOTE, the {tgt_lang} text added a "
            f"parenthetical translator gloss '(...)' explaining a term that the source line does not "
            f"have in parentheses. Remove the added parenthetical note — translate the term naturally "
            f"into the sentence instead of explaining it in parentheses.\n\n"
            f"ALTERNATIVE-TRANSLATION FIX: if reason includes ALT_SLASH, the {tgt_lang} text contains "
            f"two alternative translations joined by ' / ' that the source does not have. Pick the single "
            f"best translation and remove the alternative.\n\n"
            f"LINE COUNT: the 'fixed' text must contain EXACTLY the same number of line breaks (\\n) as the "
            f"original 'tr' field for that id — if 'tr' has 2 lines, 'fixed' must also be exactly 2 lines. "
            f"Redistribute words across the same number of lines; never merge lines into one or split one "
            f"line into more.\n\n"
            f"GARBLE FIX: if reason includes GARBLE_TOKEN, the listed token(s) are broken/foreign — "
            f"rewrite ONLY those tokens as natural Turkish (fix vowel harmony, remove stray letters, "
            f"join broken suffixes); do not change anything else in the line.\n\n"
            f"READ-ALOUD/CPS FIX: pairs may include d=duration seconds and cps=current Turkish characters/second. "
            f"If cps is high or the Turkish would sound awkward when read aloud, shorten and redistribute naturally; "
            f"target <=21 CPS and avoid >24 CPS when possible. Remove filler first, never drop names, numbers, facts, "
            f"negation, or speaker ownership.\n\n"
            f"Fix ONLY lines that have real problems — ignore stylistic preferences.\n\n"
            f"Lines:\n{json.dumps(pairs, ensure_ascii=False)}\n\n"
            f'Return ONLY fixes as JSON array: [{{"id":"5","fixed":"..."}}]\n'
            f"Return [] only if there are no real problems and no must_fix_flow=true items."
        )

        try:
            resp = _safe_chat_create(
                client,
                model=helper_model,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=len(chunk) * 60,
                temperature=0.1,
            )
            content = (resp.choices[0].message.content or "").strip() if resp.choices else ""
            if not content:
                if log_fn:
                    log_fn(f"Critic Helper chunk boş yanıt döndü — {len(chunk)} satır bu turda atlandı", "warn")
                continue
            content = _extract_json_array(content)
            if not content:
                if log_fn:
                    log_fn(f"Critic Helper chunk JSON çıkarılamadı — {len(chunk)} satır bu turda atlandı", "warn")
                continue
            fixes = json.loads(content)
            if not isinstance(fixes, list):
                if log_fn:
                    log_fn(f"Critic Helper chunk beklenmeyen format — {len(chunk)} satır bu turda atlandı", "warn")
                continue
            proposed_ids = {
                str(fix.get("id", ""))
                for fix in fixes
                if isinstance(fix, dict) and str(fix.get("id", "")) in chunk_ids and str(fix.get("id", "")) in idx_to_pos
            }
            for fix in fixes:
                if not isinstance(fix, dict):
                    continue
                fid   = str(fix.get("id", ""))
                ftext = fix.get("fixed", "")
                if fid and ftext and fid in chunk_ids and fid in idx_to_pos:
                    pos = idx_to_pos[fid]
                    old_idx, old_ts, old_text = result[pos]
                    neighbor_start = max(0, pos - 2)
                    neighbor_end = min(len(result), pos + 3)
                    neighbor_texts = [
                        result[n][2] for n in range(neighbor_start, neighbor_end)
                        if n != pos
                    ]
                    fragment_tag = (
                        frag_tags.get(old_idx)
                        or frag_tags.get(str(old_idx))
                        or frag_tags.get(fid)
                        or "none"
                    )
                    reason_toks = list(dict.fromkeys(
                        _reason_tokens(v_reasons.get(fid, ""))
                        + list(flow_reasons_by_id.get(fid, set()))
                    ))
                    for tok in reason_toks:
                        reason_stats.setdefault(tok, {"suggested": 0, "accepted": 0})
                        reason_stats[tok]["suggested"] += 1
                    final_text = str(ftext)
                    if (
                        any(token in flow_group_reason_tokens for token in reason_toks)
                        and _has_dangling_fragment_word_deletion(old_text, final_text)
                        and not all(
                            str(group_id) in proposed_ids
                            for group_id in frag_group_by_id.get(fid, [fid])
                        )
                    ):
                        critic_rejected += 1
                        reason = "dangling_fragment_word_deletion"
                        critic_rejected_reasons[reason] = critic_rejected_reasons.get(reason, 0) + 1
                        continue
                    ok, reason = validate_polish_candidate(
                        old_text,
                        final_text,
                        source_text=orig_dict.get(fid, ""),
                        neighbor_texts=neighbor_texts,
                        fragment_tag=fragment_tag,
                    )
                    # Öneri SADECE satır sayısı yüzünden reddedildiyse atmadan önce
                    # orijinalin satır sayısına yeniden sarmayı dene (bkz.
                    # _reflow_to_line_count docstring — gerçek olay, 2026-07-21).
                    if not ok and reason == "linebreak_count":
                        reflowed = _reflow_to_line_count(final_text, old_text.count("\n") + 1)
                        if reflowed != final_text:
                            ok2, reason2 = validate_polish_candidate(
                                old_text, reflowed,
                                source_text=orig_dict.get(fid, ""),
                                neighbor_texts=neighbor_texts,
                                fragment_tag=fragment_tag,
                            )
                            if ok2:
                                ok, reason, final_text = True, reason2, reflowed
                                reflow_recovered += 1
                    if not ok:
                        critic_rejected += 1
                        critic_rejected_reasons[reason] = critic_rejected_reasons.get(reason, 0) + 1
                        continue
                    result[pos] = (old_idx, old_ts, final_text)
                    mm_fixed += 1
                    for tok in reason_toks:
                        reason_stats[tok]["accepted"] += 1
                    if change_log is not None:
                        change_log.append({
                            "id": fid,
                            "reason": v_reasons.get(fid, "") or "pattern/local",
                            "source": orig_dict.get(fid, ""),
                            "before": old_text,
                            "after": final_text,
                        })
        except Exception as e:
            if log_fn:
                log_fn(f"Critic Helper chunk hatası ({len(chunk)} satır atlandı): {e}", "warn")

    if log_fn:
        if critic_rejected:
            reason_bits = ", ".join(
                f"{reason}:{count}" for reason, count in sorted(critic_rejected_reasons.items())
            )
            log_fn(
                f"Critic Pass (Helper): {critic_rejected} öneri güvenlik filtresinden döndü ({reason_bits})",
                "warn",
            )
        if mm_fixed:
            reflow_bit = f" ({reflow_recovered} tanesi satır-sayısı yeniden sarılarak kurtarıldı)" if reflow_recovered else ""
            log_fn(f"Critic Pass (Helper): {mm_fixed} satır düzeltildi ✓{reflow_bit}", "ok")
        else:
            log_fn("Critic Pass (Helper): ek düzeltme gerekmedi ✓", "ok")
        if reason_stats:
            stats_str = ", ".join(
                f"{tok}:{v['accepted']}/{v['suggested']}"
                for tok, v in sorted(reason_stats.items(), key=lambda kv: -kv[1]["suggested"])
            )
            log_fn(f"Critic Pass (Helper): sebep-bazlı isabet — {stats_str}", "info")

    return result


# ── Batch istekleri ───────────────────────────────────────────────────────────


def build_batch_requests(cues: list, system_prompt: str, model: str,
                         chunk_size: int = 25,
                         glossary: dict = None,
                         scene_emotions: list = None,
                         idiom_map: dict = None,
                         tm=None,
                         tgt_lang: str = "",
                         context_lines: int = None,
                         lookahead_lines: int = None,
                         scene_gap_sec: float = None,
                         temperature: float = None) -> tuple[list, dict]:
    if context_lines is None:
        context_lines = CONTEXT_LINES
    if lookahead_lines is None:
        lookahead_lines = LOOKAHEAD_LINES
    scene_gap_sec = SCENE_GAP_SEC if scene_gap_sec is None else float(scene_gap_sec)
    temperature = 0.2 if temperature is None else float(temperature)
    json_instruction = JSON_INSTRUCTION
    full_prompt = system_prompt + json_instruction

    # Pre-split into smart chunks (avoids cutting mid-sentence)
    frag_tags = _tag_fragments(cues, scene_gap_sec=scene_gap_sec)
    chunks = _make_smart_chunks(
        cues, chunk_size, frag_tags=frag_tags, scene_gap_sec=scene_gap_sec)
    # Fragment tags for all cues (computed once, used per-chunk)
    frag_group_ids, fragment_groups = _fragment_groups(cues, frag_tags, scene_gap_sec=scene_gap_sec)

    requests = []
    file_map = {}
    prev_ctx        = []
    prev_scene_ctx  = []   # last lines of the most recently completed scene
    prev_end_sec    = None
    actual_start    = 0

    for ci, chunk in enumerate(chunks):
        cid         = f"chunk_{actual_start}"
        file_map[cid] = [(c.index, c.start, c.end) for c in chunk]

        # Scene break detection: preserve last 6 lines of the closing scene as a
        # bridge so the model retains who/what was involved without treating it as
        # a continuing conversation thread.
        scene_broke = False
        try:
            first_start_sec = _ts_to_sec(chunk[0].start)
            if prev_end_sec is not None and (first_start_sec - prev_end_sec) >= scene_gap_sec:
                prev_scene_ctx = prev_ctx[-6:] if prev_ctx else []
                prev_ctx = []
                scene_broke = True
        except Exception:
            pass

        # Build tr_items with source cleanup + duration + fragment tag
        tr_items = []
        for c in chunk:
            try:
                dur = round(_ts_to_sec(c.end) - _ts_to_sec(c.start), 2)
            except Exception:
                dur = 2.0
            item = {"i": c.index, "t": _clean_source_text(c.text), "d": dur}
            if looks_like_on_screen_text(c.text):
                item["is_ost"] = True
            tag = frag_tags.get(c.index, "none")
            if tag != "none":
                item["frag"] = tag
                if c.index in frag_group_ids:
                    item["frag_group"] = frag_group_ids[c.index]
            tr_items.append(item)

        payload = {"tr": tr_items}
        chunk_ids = {c.index for c in chunk}
        chunk_groups = [
            group for group in fragment_groups
            if any(group_item in chunk_ids for group_item in group["items"])
        ]
        if chunk_groups:
            payload["sentence_groups"] = chunk_groups
        if prev_ctx:
            payload["ctx"] = prev_ctx
        if scene_broke and prev_scene_ctx:
            payload["prev_scene"] = prev_scene_ctx
        # Lookahead: first N lines of next chunk
        if ci + 1 < len(chunks):
            next_items = [{"i": c.index, "t": _clean_source_text(c.text)}
                          for c in chunks[ci + 1][:lookahead_lines]]
            if next_items:
                payload["next_ctx"] = next_items
        # Lowercased chunk text — bu chunk için bir kez hesapla (glossary + idiom eşleşmesi paylaşır)
        chunk_text_lower = None
        if glossary or idiom_map:
            chunk_text_lower = " ".join(
                _clean_source_text(c.text).lower() for c in chunk)

        # Active glossary: only inject terms that appear in this chunk
        if chunk_text_lower is None:
            chunk_text_lower = " ".join(_clean_source_text(c.text).lower() for c in chunk)
        quality_terms = quality_glossary_for_source(chunk_text_lower or "")
        if glossary:
            active = {k: v for k, v in glossary.items()
                      if term_in_text(k, chunk_text_lower)}
            active = {**quality_terms, **sanitize_glossary_for_turkish(active, target_language=tgt_lang)}
            if active:
                payload["glossary"] = active
        elif quality_terms:
            payload["glossary"] = quality_terms

        # Active idioms: only inject idioms whose source phrase appears in this chunk
        if idiom_map:
            active_idioms = {k: v for k, v in idiom_map.items()
                             if term_in_text(k, chunk_text_lower)}
            if active_idioms:
                payload["idioms"] = active_idioms

        # Scene plan: inject ALL scenes overlapping this chunk (a chunk can span >1 scene)
        if scene_emotions:
            scene_plan = _scene_context_for_chunk(
                scene_emotions, chunk[0].index, chunk[-1].index)
            if scene_plan:
                payload["scene"] = scene_plan

        # Update for next iteration — enrich with TM translations when available
        prev_ctx = []
        for c in chunk[-context_lines:]:
            item = {"i": c.index, "t": _clean_source_text(c.text)}
            if tm is not None:
                clean_source = _clean_source_text(c.text)
                cached = tm.lookup(clean_source, tgt_lang=tgt_lang, model=model)
                if cached is None:
                    fuzzy = tm.fuzzy_lookup(clean_source, threshold=0.95, tgt_lang=tgt_lang, model=model)
                    cached = fuzzy[0] if fuzzy else None
                if cached:
                    item["tr"] = cached
                    tm.record_hit()
            prev_ctx.append(item)
        try:
            prev_end_sec = _ts_to_sec(chunk[-1].end)
        except Exception:
            prev_end_sec = None

        # gpt-5 serisi temperature desteklemiyor — batch body'ye ekleme
        _model_lower = model.lower()
        _is_no_temp = (
            _model_lower.startswith("gpt-5")
            or _model_lower.startswith("codex-")
            or _model_lower.startswith("o1")
            or _model_lower.startswith("o3")
            or _model_lower.startswith("o4")
        )
        batch_body = {
            "model": model,
            "messages": [
                {"role": "system", "content": full_prompt},
                {"role": "user",   "content": json.dumps(payload, ensure_ascii=False)},
            ],
            # Token bütçesi GERÇEK chunk uzunluğuna göre (nominal chunk_size'a göre değil) —
            # akıllı chunk'layıcı sahne/cümle sınırına uzayıp chunk_size'ı aşabiliyor; sabit
            # bütçe büyük chunk'larda yanıtı kesip JSON'u bozuyordu (sonra onarım gerekiyordu).
            # +500 taban: gpt-5 reasoning token'ları + JSON yapısı için pay.
            "max_completion_tokens": max(chunk_size, len(chunk)) * 120 + 500,
        }
        if _is_no_temp:
            for msg in batch_body["messages"]:
                if msg["role"] == "system":
                    msg["role"] = "developer"
        if not _is_no_temp:
            batch_body["temperature"] = temperature
        requests.append({
            "custom_id": cid,
            "method": "POST",
            "url": "/v1/chat/completions",
            "body": batch_body,
        })
        actual_start += len(chunk)

    return requests, file_map


# ── OpenAI Batch gönder & bekle ───────────────────────────────────────────────

def submit_batch(
    openai_api_key: str,
    requests: list,
    log_fn=None,
    file_map: dict = None,
    output_path: str = None,
    source_path: str = None,
    output_dir: str = None,
    base_url: str = "",
    source_language: str = "",
) -> str | None:
    """Submit batch to OpenAI and return batch_id. Does NOT wait.

    source_path/output_dir kurtarma (resume) için saklanır: resume bunları GÖNDERİM
    ANINDAKİ hâliyle bilmek zorundadır, çünkü program yeniden başlatıldığında UI'daki
    girdi/çıktı kutuları başka bir şeye (ör. ayarlardaki eski varsayılan) dönmüş olabilir
    ve çıktı yolundan kaynağı geriye hesaplamak da güvenilir değildir (bkz.
    _resolve_output_path: Kural 2'de araya dosya-adı alt-klasörü girer, ayrıca çıktı
    her zaman .srt iken kaynak .vtt/.ass olabilir)."""
    from openai import OpenAI
    client = OpenAI(api_key=openai_api_key, base_url=base_url or None)

    import tempfile
    state_dir(__file__).mkdir(parents=True, exist_ok=True)
    tmp = tempfile.NamedTemporaryFile(
        mode="w", encoding="utf-8", suffix=".jsonl", prefix="_batch_upload_",
        dir=state_dir(__file__), delete=False)
    jsonl_path = Path(tmp.name)
    try:
        with tmp as f:
            for req in requests:
                f.write(json.dumps(req, ensure_ascii=False) + "\n")

        if log_fn:
            log_fn(f"{len(requests)} istek OpenAI'a yükleniyor...", "info")

        with open(jsonl_path, "rb") as f:
            uploaded = client.files.create(file=f, purpose="batch")
    finally:
        try:
            jsonl_path.unlink(missing_ok=True)
        except Exception:
            pass

    batch = client.batches.create(
        input_file_id=uploaded.id,
        endpoint="/v1/chat/completions",
        completion_window="24h",
    )

    try:
        mutate_batch_ids(_batch_id_path(), add=[batch.id])

        if file_map is not None:
            fmap_path = _batch_fmap_path(batch.id)
            fmap_data = {
                "type": "hybrid",
                "output_path": output_path or "",
                "source_path": source_path or "",
                "output_dir": output_dir or "",
                "source_language": source_language or "",
                "fmap": {cid: [list(x) for x in info] for cid, info in file_map.items()},
            }
            atomic_write_json(fmap_path, fmap_data)
    except Exception as exc:
        cancelled = best_effort_cancel_remote_batch(client, batch.id, log_fn)
        if cancelled:
            try:
                mutate_batch_ids(_batch_id_path(), remove=[batch.id])
            except Exception:
                pass
        raise RuntimeError(
            f"Batch oluşturuldu ancak recovery metadata kaydedilemedi ({batch.id}); "
            f"uzak iptal={'başarılı' if cancelled else 'başarısız'}"
        ) from exc

    if log_fn:
        log_fn(f"Batch gönderildi: {batch.id}", "ok")

    return batch.id


def wait_for_batch(
    openai_api_key: str,
    batch_id: str,
    log_fn=None,
    stop_flag_fn=None,
    progress_fn=None,
    base_url: str = "",
    detailed: bool = False,
):
    """Poll a batch. detailed=True terminal ve polling-abort durumlarını ayırır."""
    from openai import OpenAI
    client = OpenAI(api_key=openai_api_key, base_url=base_url or None)
    consecutive_errors = 0
    max_consecutive_errors = 10

    while True:
        if stop_flag_fn and stop_flag_fn():
            return ({"output_file_id": None, "terminal": False, "status": "stopped"}
                    if detailed else None)

        try:
            batch     = client.batches.retrieve(batch_id)
            counts    = batch.request_counts
            total     = counts.total     or 1
            completed = counts.completed or 0
            failed    = counts.failed    or 0
            consecutive_errors = 0
        except Exception as e:
            consecutive_errors += 1
            if log_fn:
                log_fn(f"Batch sorgulama hatası ({consecutive_errors}/{max_consecutive_errors}): {e}", "warn")
            if consecutive_errors >= max_consecutive_errors:
                if log_fn:
                    log_fn(f"Batch sorgulama çok fazla hata verdi, iptal ediliyor: {batch_id}", "err")
                return ({"output_file_id": None, "terminal": False,
                         "status": "polling_aborted"} if detailed else None)
            for _ in range(5):
                if stop_flag_fn and stop_flag_fn():
                    return ({"output_file_id": None, "terminal": False, "status": "stopped"}
                            if detailed else None)
                time.sleep(1)
            continue

        if progress_fn:
            progress_fn(completed, total, failed, batch.status)
        if log_fn:
            log_fn(f"{batch.status} — {completed}/{total}  hatalı: {failed}", "")

        if batch.status == "completed":
            if log_fn:
                log_fn("Batch tamamlandı, indiriliyor...", "ok")
            if failed > 0 and batch.error_file_id:
                try:
                    err_content = client.files.content(batch.error_file_id).text
                    err_lines = err_content.strip().splitlines()
                    logged_errors = set()
                    for line in err_lines[:5]:
                        try:
                            res = json.loads(line)
                            err_obj = res.get("error")
                            if not err_obj and res.get("response") and res["response"].get("body"):
                                body = res["response"]["body"]
                                if isinstance(body, dict):
                                    err_obj = body.get("error")
                            if err_obj and isinstance(err_obj, dict):
                                msg = err_obj.get("message", "")
                                if msg and msg not in logged_errors:
                                    logged_errors.add(msg)
                                    if log_fn:
                                        log_fn(f"Hata detayı: {msg}", "err")
                        except Exception:
                            continue
                except Exception as e:
                    if log_fn:
                        log_fn(f"Hata dosyası okunamadı: {e}", "err")
            if detailed:
                return {"output_file_id": batch.output_file_id,
                        "terminal": True, "status": "completed"}
            return batch.output_file_id
        elif batch.status in ("failed", "expired", "cancelled"):
            if log_fn:
                log_fn(f"Batch başarısız: {batch.status}", "err")
            if batch.error_file_id:
                try:
                    err_content = client.files.content(batch.error_file_id).text
                    err_lines = err_content.strip().splitlines()
                    logged_errors = set()
                    for line in err_lines[:5]:
                        try:
                            res = json.loads(line)
                            err_obj = res.get("error")
                            if not err_obj and res.get("response") and res["response"].get("body"):
                                body = res["response"]["body"]
                                if isinstance(body, dict):
                                    err_obj = body.get("error")
                            if err_obj and isinstance(err_obj, dict):
                                msg = err_obj.get("message", "")
                                if msg and msg not in logged_errors:
                                    logged_errors.add(msg)
                                    if log_fn:
                                        log_fn(f"Hata detayı: {msg}", "err")
                        except Exception:
                            continue
                except Exception as e:
                    if log_fn:
                        log_fn(f"Hata dosyası okunamadı: {e}", "err")
            return ({"output_file_id": None, "terminal": True, "status": batch.status}
                    if detailed else None)

        for _ in range(30):
            if stop_flag_fn and stop_flag_fn():
                return ({"output_file_id": None, "terminal": False, "status": "stopped"}
                        if detailed else None)
            time.sleep(1)


def submit_and_wait(
    openai_api_key: str,
    requests: list,
    log_fn=None,
    stop_flag_fn=None,
    progress_fn=None,
    file_map: dict = None,
    output_path: str = None,
    base_url: str = "",
) -> str | None:
    """Legacy wrapper: submit then wait. Use submit_batch+wait_for_batch for multi-file."""
    batch_id = submit_batch(openai_api_key, requests, log_fn, file_map, output_path,
                            base_url=base_url)
    if batch_id is None:
        return None
    return wait_for_batch(openai_api_key, batch_id, log_fn, stop_flag_fn, progress_fn,
                          base_url=base_url)


# ── Sonuçları kaydet ──────────────────────────────────────────────────────────

def _normalize_output_text(text: str) -> str:
    """Final SRT write-time cleanup shared by hybrid/batch output paths."""
    text = normalize_latin_homoglyphs(str(text))
    text = unicodedata.normalize("NFC", text.strip()).replace("\t", " ")
    text, _ = _apply_local_fixes(text)
    text = re.sub(r"\n{2,}", "\n", text)
    try:
        import sdh_cleaner
    except Exception:
        return text
    text = sdh_cleaner.normalize_sdh_descriptors(text)
    text = sdh_cleaner.normalize_speaker_labels(text)
    text = sdh_cleaner.normalize_turkish_artifacts(text)
    return text


def save_results(
    openai_api_key: str,
    output_file_id: str,
    file_map: dict,
    output_path: str,
    log_fn=None,
    token_callback=None,
    src_cues: list = None,
    base_url: str = "",
) -> tuple:
    """Returns (yazılan_satır_sayısı, eksik-çeviri işaretleme_sayısı).

    output_file_id str VEYA list olabilir: iki-dalgalı batch (B3) iki ayrı çıktı
    dosyasının içeriğini TEK birleşik SRT'ye yazmak için liste geçer. file_map her
    iki dalganın custom_id'lerini de kapsamalı (birleşik fmap)."""
    from openai import OpenAI
    client  = OpenAI(api_key=openai_api_key, base_url=base_url or None)
    _ids = output_file_id if isinstance(output_file_id, (list, tuple)) else [output_file_id]
    content = "\n".join(client.files.content(_id).text for _id in _ids if _id)

    srt_blocks = {}
    token_sum  = 0
    token_cached_sum = 0

    for line in content.strip().splitlines():
        try:
            res = json.loads(line)
        except Exception:
            if log_fn:
                log_fn(f"Satır ayrıştırılamadı: {line[:80]}", "warn")
            continue
        cid  = res["custom_id"]
        info = file_map.get(cid, [])

        if not info:
            # Bu custom_id file_map'te yok — chunk sonuca dahil edilemiyor
            if log_fn:
                log_fn(f"[WARN] {cid}: file_map'te eşleşme yok, chunk atlandı", "warn")
            continue
        if res.get("error"):
            for (idx, start, end) in info:
                srt_blocks[idx] = (str(idx), f"{start} --> {end}", "[HATA]")
            if log_fn:
                log_fn(f"İstek hatası ({cid}): {res['error'].get('message','')}", "err")
            continue

        body = res["response"]["body"]
        finish_reason = ""
        try:
            finish_reason = body.get("choices", [{}])[0].get("finish_reason", "")
        except (IndexError, AttributeError, TypeError):
            pass
        if finish_reason == "content_filter":
            if log_fn:
                log_fn(f"{cid}: yanıt kesildi (finish_reason={finish_reason})", "err")
            for (idx, start, end) in info:
                srt_blocks[idx] = (str(idx), f"{start} --> {end}", "[HATA]")
            continue
        if finish_reason == "length" and log_fn:
            log_fn(f"{cid}: yanıt kesildi; tamamlanan JSON öğeleri kurtarılıyor", "warn")

        if body.get("usage"):
            token_sum += body["usage"].get("total_tokens", 0)
            try:
                p_details = body["usage"].get("prompt_tokens_details") or {}
                token_cached_sum += p_details.get("cached_tokens", 0) or 0
            except Exception:
                pass

        raw = body["choices"][0]["message"]["content"].strip()
        if not raw:
            if log_fn:
                log_fn(f"{cid}: boş yanıt", "err")
            for (idx, start, end) in info:
                srt_blocks[idx] = (str(idx), f"{start} --> {end}", "[HATA]")
            continue

        # Robust JSON extraction: markdown fence + prose preamble + truncated array salvage
        raw_clean = raw
        if raw_clean.startswith("```"):
            raw_clean = "\n".join(raw_clean.split("\n")[1:]).rsplit("```", 1)[0].strip()

        items = _translation_items_from_raw(raw_clean)
        if items and isinstance(items, list):
            trans_map = {}
            for item in items:
                if isinstance(item, dict) and "i" in item and "t" in item:
                    trans_map[str(item["i"])] = item["t"]
            if log_fn and len(trans_map) < len(info):
                log_fn(f"{cid}: JSON kısmi kurtarıldı — {len(trans_map)}/{len(info)} satır korundu", "warn")
        else:
            if log_fn:
                log_fn(f"{cid}: JSON parse başarısız — chunk [HATA] yazılıyor "
                       f"(ham: {raw_clean[:80]!r})", "err")
            trans_map = {}
        for (idx, start, end) in info:
            text = trans_map.get(str(idx), "[HATA]")
            srt_blocks[idx] = (str(idx), f"{start} --> {end}", text)

    if token_callback and token_sum:
        try:
            token_callback(token_sum, cached=token_cached_sum)
        except TypeError:
            token_callback(token_sum)

    # Batch API output cannot be retried inline; never write non-Turkish target leaks silently.
    leak_marked = 0
    for key, (idx, ts, text) in list(srt_blocks.items()):
        if text and not str(text).startswith("[HATA") and has_non_turkish_target_leak(text):
            srt_blocks[key] = (idx, ts, "[HATA_NON_TURKISH_TARGET]")
            leak_marked += 1

    # [HATA] satırlarını kaynak metinle doldurma; eksik çeviriyi görünür işaretle bırak.
    n_marked = 0
    if src_cues:
        try:
            from subtitle_formats import restore_format_tags
            raw_map = {str(c.index): c.text for c in src_cues if hasattr(c, "text")}
            for key, (idx, ts, text) in list(srt_blocks.items()):
                src = raw_map.get(str(idx), "")
                if not str(text or "").strip():
                    if _has_wordlike_text(_clean_source_text(src)):
                        srt_blocks[key] = (idx, ts, "[ÇEVİRİ EKSİK]")
                        n_marked += 1
                    else:
                        srt_blocks[key] = (idx, ts, "")
                    continue
                if str(text).startswith("[HATA"):
                    if src:
                        srt_blocks[key] = (idx, ts, "[ÇEVİRİ EKSİK]")
                        n_marked += 1
                        continue
                srt_blocks[key] = (idx, ts, restore_format_tags(raw_map.get(str(idx), ""), text))
        except Exception as e:
            if log_fn:
                log_fn(f"[UYARI] post-processing hatası, etiketler geri yüklenemedi: {e}", "warn")

    _out = Path(output_path).with_suffix(".srt")   # çıktı her zaman SRT
    _out.parent.mkdir(parents=True, exist_ok=True)
    _tmp_srt = _out.with_suffix(".srt.tmp")        # atomik yazım
    with open(_tmp_srt, "w", encoding="utf-8") as f:
        for key in sorted(srt_blocks, key=lambda k: (0, int(k)) if str(k).isdigit() else (1, str(k))):
            idx, ts, text = srt_blocks[key]
            text = _normalize_output_text(text)
            f.write(f"{idx}\n{ts}\n{text}\n\n")
    _tmp_srt.replace(_out)

    count = len(srt_blocks)
    if log_fn:
        log_fn(f"Kaydedildi: {output_path}  ({count} satır)", "ok")
        if leak_marked:
            log_fn(f"{leak_marked} hedef-dil kaçağı eksik-çeviri işaretine yönlendirildi", "warn")
        if n_marked:
            log_fn(f"{n_marked} çevrilemeyen satır kaynak metne düşürülmedi; [ÇEVİRİ EKSİK] olarak işaretlendi", "warn")
    return count, n_marked
