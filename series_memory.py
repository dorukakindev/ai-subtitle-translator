"""
series_memory.py — Dizi (show) bazlı bölümler arası çeviri hafızası.

`project_memory.py` klasör bazlıdır (bir klasör = tek hafıza, tüm dosyalar karışır).
Bu modül SHOW bazlıdır: dosya adından dizi+sezon+bölüm çıkarır, her dizi için ayrı
hafıza tutar (aynı klasördeki iki farklı dizi birbirine karışmaz) ve hint'i HEM düz
HEM hybrid akışlara enjekte eder (hybrid'de proje hafızası enjeksiyonu yoktu).

Çakışma kuralı: ilk bölümde verilen karar KANON olur, sonraki bölümler ezemez —
tutarlılığın bütün amacı bu.

Saklama: <input_dir>/.series_memory/<show-slug>.json
"""

import json
import re
import threading
from pathlib import Path

from app_state import _interprocess_lock, atomic_write_json

# 'Show.Name.S01E05.720p' → show + season + ep
_SXXEXX = re.compile(
    r'^(?P<show>.+?)[ ._\-]+[Ss](?P<season>\d{1,2})[ ._\-]?[Ee](?P<ep>\d{1,3})')
# 'Show Name 1x05' → show + season + ep (ayraç zorunlu: çözünürlük '1280x720' eşleşmez)
_NXNN = re.compile(
    r'^(?P<show>.+?)[ ._\-]+(?P<season>\d{1,2})x(?P<ep>\d{1,3})(?:\D|$)')
_TV_ROOT = re.compile(
    r'(?i)(?:^|[ ._\-])tv[ ._\-]*s(?P<season>\d{1,2})(?=$|[ ._\-])')
_TV_COMMON_ROOT = re.compile(r'(?i)(?:^|[ ._\-])tv(?=$|[ ._\-])')
_SEASON_DIR = re.compile(r'(?i)^(?:season[ ._\-]*|s)(?P<season>\d{1,2})$')
_EPISODE_DIR = re.compile(r'(?i)^episode[ ._\-]*(?P<ep>\d{1,3})$')
_PUNTATA = re.compile(
    r'(?i)(?:^|[ ._\-])puntata[ ._\-]*(?P<ep>\d{1,3})(?:\D|$)')
_N_OF_TOTAL = re.compile(
    r'(?i)(?:^|[ ._\-])(?P<ep>\d{1,3})[ ._\-]+of[ ._\-]+\d{1,3}(?:\D|$)')


def _slugify(show: str) -> str:
    s = re.sub(r'[._]+', ' ', show.strip().lower())
    s = re.sub(r'[^\w\s-]', '', s)        # \w Türkçe harfleri de kapsar (py3 unicode)
    s = re.sub(r'\s+', '-', s.strip())
    return s or "dizi"


def _target_key(value: str) -> str:
    raw = str(value or "tr").strip().casefold()
    aliases = {
        "turkish": "tr",
        "türkçe": "tr",
        "german": "de",
        "deutsch": "de",
        "italian": "it",
        "spanish": "es",
        "french": "fr",
        "english": "en",
    }
    key = aliases.get(raw, raw)
    key = re.sub(r"[^a-z0-9_-]+", "-", key).strip("-")
    return key or "tr"


def _source_key(value: str) -> str:
    return _target_key(value or "en")


def _tv_root_info(filename: str):
    path = Path(filename)
    for parent in path.parents:
        match = _TV_ROOT.search(parent.name)
        if not match:
            continue
        show = parent.name[:match.start()]
        show = re.sub(
            r'[ ._\-]*[\(\[]?\d{4}[\)\]]?[ ._\-]*$', '', show)
        return parent, _slugify(show), int(match.group("season"))
    for parent in path.parents:
        match = _TV_COMMON_ROOT.search(parent.name)
        if not match:
            continue
        relative_parts = path.parent.relative_to(parent).parts
        season = None
        season_pos = None
        for pos, part in enumerate(relative_parts):
            season_match = _SEASON_DIR.match(part)
            if season_match:
                season = int(season_match.group("season"))
                season_pos = pos
                break
        if season is None:
            continue
        show = parent.name[:match.start()]
        show = re.sub(
            r'[ ._\-]*[\(\[]?\d{4}[\)\]]?[ ._\-]*$', '', show)
        if show.strip():
            return parent, _slugify(show), season
        if season_pos:
            show_root = parent.joinpath(*relative_parts[:season_pos])
            return show_root, _slugify(relative_parts[season_pos - 1]), season
    return None


def series_memory_root(filename: str) -> Path:
    """Seçilmiş bölüm alt klasörlerini ortak dizi köküne bağlar."""
    info = _tv_root_info(filename)
    return info[0] if info else Path(filename).parent


def parse_series_key(filename: str):
    """'Show.Name.S01E05.720p.srt' → ('show-name', 1, 5). Dizi değilse None."""
    path = Path(filename)
    stem = path.stem
    root_info = _tv_root_info(filename)
    for rx in (_SXXEXX, _NXNN):
        m = rx.match(stem)
        if m:
            slug = root_info[1] if root_info else _slugify(m.group("show"))
            return slug, int(m.group("season")), int(m.group("ep"))
    if root_info:
        _root, slug, season = root_info
        parent_match = _EPISODE_DIR.match(path.parent.name)
        if parent_match:
            return slug, season, int(parent_match.group("ep"))
        for rx in (_PUNTATA, _N_OF_TOTAL):
            match = rx.search(stem)
            if match:
                return slug, season, int(match.group("ep"))
    return None


def sort_files_by_episode(files: list) -> list:
    """Dosyaları (dizi-slug, sezon, bölüm) sırasına dizer; dizi olmayanlar ada göre sona."""
    def key(fp):
        k = parse_series_key(fp)
        if k is None:
            return (1, Path(fp).name.lower(), 0, 0)
        slug, s, e = k
        return (0, slug, s, e)
    return sorted(files, key=key)


class SeriesMemory:
    VERSION   = 2
    MAX_TERMS = 80
    MAX_CHARS = 24
    MAX_ADDR  = 24

    def __init__(self, path: Path, data: dict):
        self._path = path
        self._data = data
        self._data.setdefault("term_origins", {})
        self._data.setdefault("character_origins", {})
        self._data.setdefault("address_origins", {})
        self._lock = threading.RLock()

    # ── Yükleme / kaydetme ────────────────────────────────────────────────────

    @classmethod
    def load(cls, input_dir: str, show_slug: str,
             target_language: str = "tr",
             source_language: str = "en") -> "SeriesMemory":
        show_slug = str(show_slug or "").strip()
        if not re.fullmatch(r"[\w-]+", show_slug, re.UNICODE):
            raise ValueError("gecersiz dizi hafizasi anahtari")
        target_key = _target_key(target_language)
        source_key = _source_key(source_language)
        base = Path(input_dir) / ".series_memory"
        if source_key == "en":
            path = (
                base / f"{show_slug}.json"
                if target_key == "tr"
                else base / target_key / f"{show_slug}.json"
            )
        else:
            path = base / f"src-{source_key}" / f"tgt-{target_key}" / f"{show_slug}.json"
        data = None
        if path.exists():
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
            except Exception:
                data = None   # bozuk JSON'a dayanıklı — sıfırdan başla
        if (isinstance(data, dict) and data.get("target_language")
                and _target_key(data["target_language"]) != target_key):
            data = None
        if (isinstance(data, dict) and data.get("source_language")
                and _source_key(data["source_language"]) != source_key):
            data = None
        if not isinstance(data, dict):
            data = {}
        try:
            previous_version = int(data.get("version", 1))
        except Exception:
            previous_version = 1
        data["version"] = cls.VERSION
        data.setdefault("show", show_slug)
        data.setdefault("target_language", target_key)
        data.setdefault("source_language", source_key)
        data.setdefault("updated_eps", [])
        data.setdefault("terms", {})
        data.setdefault("characters", {})
        data.setdefault("address_map", [])
        data.setdefault("term_origins", {})
        data.setdefault("character_origins", {})
        data.setdefault("address_origins", {})
        if not isinstance(data.get("updated_eps"), list):
            data["updated_eps"] = []
        if not isinstance(data.get("terms"), dict):
            data["terms"] = {}
        if not isinstance(data.get("characters"), dict):
            data["characters"] = {}
        if not isinstance(data.get("address_map"), list):
            data["address_map"] = []
        for key in ("term_origins", "character_origins", "address_origins"):
            if not isinstance(data.get(key), dict):
                data[key] = {}
        if previous_version < cls.VERSION:
            data.setdefault("legacy_unscoped", bool(data.get("updated_eps")))
        else:
            data.setdefault("legacy_unscoped", False)
        return cls(path, data)

    @staticmethod
    def _merge_saved_data(disk: dict, memory: dict) -> dict:
        if not isinstance(disk, dict):
            disk = {}
        memory_target = _target_key(memory.get("target_language", "tr"))
        memory_source = _source_key(memory.get("source_language", "en"))
        if ((disk.get("target_language")
             and _target_key(disk["target_language"]) != memory_target)
                or (disk.get("source_language")
                    and _source_key(disk["source_language"]) != memory_source)):
            disk = {}
        merged = {
            "version": memory.get("version", SeriesMemory.VERSION),
            "show": memory.get("show", disk.get("show", "")),
            "target_language": memory_target,
            "source_language": memory_source,
            "legacy_unscoped": bool(
                disk.get("legacy_unscoped") or memory.get("legacy_unscoped")),
        }
        for key in ("terms", "characters"):
            values = dict(disk.get(key) or {})
            known = {str(item).strip().casefold() for item in values}
            for item, value in dict(memory.get(key) or {}).items():
                folded = str(item).strip().casefold()
                if folded not in known:
                    values[item] = value
                    known.add(folded)
            merged[key] = values
        addresses = list(disk.get("address_map") or [])
        seen = {
            (str(item.get("a") or "").strip().casefold(),
             str(item.get("b") or "").strip().casefold())
            for item in addresses if isinstance(item, dict)
        }
        for item in list(memory.get("address_map") or []):
            if not isinstance(item, dict):
                continue
            key = (str(item.get("a") or "").strip().casefold(),
                   str(item.get("b") or "").strip().casefold())
            if key not in seen:
                addresses.append(item)
                seen.add(key)
        merged["address_map"] = addresses
        for key in ("term_origins", "character_origins", "address_origins"):
            origins = dict(disk.get(key) or {})
            for item, origin in dict(memory.get(key) or {}).items():
                origins.setdefault(str(item), str(origin))
            merged[key] = origins
        merged["updated_eps"] = list(dict.fromkeys(
            list(disk.get("updated_eps") or [])
            + list(memory.get("updated_eps") or [])))
        return merged

    def save(self):
        try:
            with self._lock:
                self._path.parent.mkdir(parents=True, exist_ok=True)
                with _interprocess_lock(self._path):
                    if self._path.exists():
                        try:
                            disk = json.loads(self._path.read_text(encoding="utf-8"))
                        except Exception as exc:
                            raise ValueError(
                                "mevcut dizi hafızası bozuk; veri kaybını önlemek "
                                "için üzerine yazılmadı"
                            ) from exc
                        if not isinstance(disk, dict):
                            raise ValueError(
                                "mevcut dizi hafızası nesne biçiminde değil; veri "
                                "kaybını önlemek için üzerine yazılmadı"
                            )
                    else:
                        disk = {}
                    self._data = self._merge_saved_data(disk, self._data)
                    atomic_write_json(self._path, self._data)
            return True
        except Exception as e:
            import sys
            print(f"[series_memory] kaydetme hatası {self._path}: {e}", file=sys.stderr)
            return False

    # ── Birleştirme (ilk karar kanon) ─────────────────────────────────────────

    @staticmethod
    def _episode_tag(season=None, ep=None) -> str:
        try:
            return f"s{int(season):02d}e{int(ep):03d}"
        except Exception:
            return ""

    def merge_terms(self, terms: dict, season=None, ep=None):
        if not isinstance(terms, dict):
            return
        t = self._data["terms"]
        known = {str(key).strip().casefold() for key in t}
        for src, tgt in terms.items():
            if not (src and tgt):
                continue
            # Kaynak==hedef (küçük-harf sıradan kelime) İngilizce sızıntısı üretir;
            # özel ad/kısaltma (büyük harf içeren) korunur.
            s, v = str(src).strip(), str(tgt).strip()
            if not s or s.casefold() in known:
                continue
            if s.lower() == v.lower() and s.islower():
                continue
            t[s] = v
            known.add(s.casefold())
            tag = self._episode_tag(season, ep)
            if tag:
                self._data["term_origins"].setdefault(s.casefold(), tag)

    def merge_characters(self, chars, season=None, ep=None):
        """chars: {name: style} | [{name, style|speaking_style}] | [CharacterVoice]."""
        c = self._data["characters"]
        items = []
        if isinstance(chars, dict):
            items = list(chars.items())
        elif isinstance(chars, (list, tuple)):
            for ch in chars:
                if isinstance(ch, dict) and ch.get("name"):
                    items.append((ch["name"], ch.get("style") or ch.get("speaking_style") or ""))
                elif hasattr(ch, "name"):
                    items.append((ch.name, getattr(ch, "speaking_style", "") or ""))
        known = {str(key).strip().casefold(): key for key in c}
        for name, style in items:
            clean_name = str(name or "").strip()
            if not clean_name:
                continue
            canonical = known.get(clean_name.casefold())
            if canonical is None:
                c[clean_name] = {"style": str(style or "").strip()}
                known[clean_name.casefold()] = clean_name
                tag = self._episode_tag(season, ep)
                if tag:
                    self._data["character_origins"].setdefault(
                        clean_name.casefold(), tag)
            elif (isinstance(c.get(canonical), dict)
                  and not c[canonical].get("style") and str(style or "").strip()):
                c[canonical]["style"] = str(style).strip()

    def merge_address_map(self, pairs, season=None, ep=None):
        """pairs: [{a, b, register}] (pairwise) | {name: register} (per-character)."""
        amap = self._data["address_map"]
        seen = {
            (str(p.get("a") or "").strip().casefold(),
             str(p.get("b") or "").strip().casefold())
            for p in amap if isinstance(p, dict)
        }
        entries = []
        if isinstance(pairs, dict):
            for name, reg in pairs.items():
                if name and reg:
                    entries.append({"a": str(name), "b": "", "register": str(reg)})
        elif isinstance(pairs, (list, tuple)):
            for p in pairs:
                if isinstance(p, dict) and p.get("a") and p.get("register"):
                    entries.append({"a": str(p["a"]), "b": str(p.get("b") or ""),
                                    "register": str(p["register"])})
        for e in entries:
            key = (e["a"].strip().casefold(), e["b"].strip().casefold())
            if key not in seen:
                seen.add(key)
                amap.append(e)
                tag = self._episode_tag(season, ep)
                if tag:
                    self._data["address_origins"].setdefault(
                        "\0".join(key), tag)

    def mark_episode(self, season, ep):
        try:
            tag = f"s{int(season):02d}e{int(ep):02d}"
        except Exception:
            return
        if tag not in self._data["updated_eps"]:
            self._data["updated_eps"].append(tag)

    # ── Prompt hint'i ─────────────────────────────────────────────────────────

    @staticmethod
    def _core_and_recent(items, limit):
        items = list(items)
        if len(items) <= limit:
            return items
        core_count = limit // 2
        return items[:core_count] + items[-(limit - core_count):]

    def build_hint(self, before_episode=None) -> str:
        terms = self._data.get("terms") or {}
        chars = self._data.get("characters") or {}
        addr  = self._data.get("address_map") or []
        cutoff = self._episode_tag(*(before_episode or ())) if before_episode else ""
        legacy_blocked = False
        if cutoff and self._data.get("legacy_unscoped"):
            cutoff_match = re.fullmatch(r"s(\d+)e(\d+)", cutoff)
            if cutoff_match:
                cutoff_key = tuple(map(int, cutoff_match.groups()))
                for tag in self._data.get("updated_eps") or []:
                    match = re.fullmatch(r"s(\d+)e(\d+)", str(tag), re.IGNORECASE)
                    if match and tuple(map(int, match.groups())) >= cutoff_key:
                        legacy_blocked = True
                        break

        def allowed(origin):
            if not cutoff:
                return True
            if not origin:
                return not legacy_blocked
            return str(origin) < cutoff

        term_origins = self._data.get("term_origins") or {}
        char_origins = self._data.get("character_origins") or {}
        addr_origins = self._data.get("address_origins") or {}
        terms = {
            source: target for source, target in terms.items()
            if allowed(term_origins.get(str(source).strip().casefold()))
        }
        chars = {
            name: meta for name, meta in chars.items()
            if allowed(char_origins.get(str(name).strip().casefold()))
        }
        addr = [
            item for item in addr if isinstance(item, dict) and allowed(
                addr_origins.get("\0".join((
                    str(item.get("a") or "").strip().casefold(),
                    str(item.get("b") or "").strip().casefold(),
                )))
            )
        ]
        if not (terms or chars or addr):
            return ""
        lines = ["\n## SERIES MEMORY (decisions from earlier episodes — follow strictly)"]
        if terms:
            lines.append("Fixed term translations (use EXACTLY these, never re-decide):")
            lines.extend(
                f"- '{s}' → '{t}'"
                for s, t in self._core_and_recent(terms.items(), self.MAX_TERMS)
            )
        if chars:
            lines.append("Characters (keep each voice consistent across episodes):")
            for name, meta in self._core_and_recent(chars.items(), self.MAX_CHARS):
                style = meta.get("style") if isinstance(meta, dict) else ""
                lines.append(f"- {name}" + (f": {style}" if style else ""))
        if addr:
            lines.append("Address register (Turkish sen/siz — keep consistent):")
            for a in self._core_and_recent(addr, self.MAX_ADDR):
                if not isinstance(a, dict):
                    continue
                aa, bb, reg = a.get("a"), a.get("b"), a.get("register")
                if aa and reg:
                    lines.append(f"- {aa} → {bb}: '{reg}'" if bb else f"- {aa}: '{reg}'")
        return "\n".join(lines) + "\n"

    def get_terms(self) -> dict:
        return dict(self._data.get("terms") or {})

    def get_address_map(self) -> list:
        return [dict(item) for item in (self._data.get("address_map") or [])
                if isinstance(item, dict)]

    def counts(self) -> dict:
        return {"terms": len(self._data.get("terms", {})),
                "characters": len(self._data.get("characters", {})),
                "address": len(self._data.get("address_map", []))}
