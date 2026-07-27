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
from pathlib import Path

from app_state import atomic_write_json

# 'Show.Name.S01E05.720p' → show + season + ep
_SXXEXX = re.compile(
    r'^(?P<show>.+?)[ ._\-]+[Ss](?P<season>\d{1,2})[ ._\-]?[Ee](?P<ep>\d{1,3})')
# 'Show Name 1x05' → show + season + ep (ayraç zorunlu: çözünürlük '1280x720' eşleşmez)
_NXNN = re.compile(
    r'^(?P<show>.+?)[ ._\-]+(?P<season>\d{1,2})x(?P<ep>\d{1,3})(?:\D|$)')


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


def parse_series_key(filename: str):
    """'Show.Name.S01E05.720p.srt' → ('show-name', 1, 5). Dizi değilse None."""
    stem = Path(filename).stem
    for rx in (_SXXEXX, _NXNN):
        m = rx.match(stem)
        if m:
            return _slugify(m.group("show")), int(m.group("season")), int(m.group("ep"))
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
    VERSION   = 1
    MAX_TERMS = 40
    MAX_CHARS = 15
    MAX_ADDR  = 12

    def __init__(self, path: Path, data: dict):
        self._path = path
        self._data = data

    # ── Yükleme / kaydetme ────────────────────────────────────────────────────

    @classmethod
    def load(cls, input_dir: str, show_slug: str,
             target_language: str = "tr",
             source_language: str = "en") -> "SeriesMemory":
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
        data.setdefault("version", cls.VERSION)
        data.setdefault("show", show_slug)
        data.setdefault("target_language", target_key)
        data.setdefault("source_language", source_key)
        data.setdefault("updated_eps", [])
        data.setdefault("terms", {})
        data.setdefault("characters", {})
        data.setdefault("address_map", [])
        if not isinstance(data.get("updated_eps"), list):
            data["updated_eps"] = []
        if not isinstance(data.get("terms"), dict):
            data["terms"] = {}
        if not isinstance(data.get("characters"), dict):
            data["characters"] = {}
        if not isinstance(data.get("address_map"), list):
            data["address_map"] = []
        return cls(path, data)

    def save(self):
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            atomic_write_json(self._path, self._data)
        except Exception as e:
            import sys
            print(f"[series_memory] kaydetme hatası {self._path}: {e}", file=sys.stderr)

    # ── Birleştirme (ilk karar kanon) ─────────────────────────────────────────

    def merge_terms(self, terms: dict):
        if not isinstance(terms, dict):
            return
        t = self._data["terms"]
        for src, tgt in terms.items():
            if not (src and tgt) or str(src) in t:
                continue
            # Kaynak==hedef (küçük-harf sıradan kelime) İngilizce sızıntısı üretir;
            # özel ad/kısaltma (büyük harf içeren) korunur.
            s, v = str(src).strip(), str(tgt).strip()
            if s.lower() == v.lower() and s.islower():
                continue
            t[str(src)] = str(tgt)

    def merge_characters(self, chars):
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
        for name, style in items:
            if name and str(name) not in c:
                c[str(name)] = {"style": str(style or "")}

    def merge_address_map(self, pairs):
        """pairs: [{a, b, register}] (pairwise) | {name: register} (per-character)."""
        amap = self._data["address_map"]
        seen = {(p.get("a"), p.get("b")) for p in amap if isinstance(p, dict)}
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
            key = (e["a"], e["b"])
            if key not in seen:
                seen.add(key)
                amap.append(e)

    def mark_episode(self, season, ep):
        try:
            tag = f"s{int(season):02d}e{int(ep):02d}"
        except Exception:
            return
        if tag not in self._data["updated_eps"]:
            self._data["updated_eps"].append(tag)

    # ── Prompt hint'i ─────────────────────────────────────────────────────────

    def build_hint(self) -> str:
        terms = self._data.get("terms") or {}
        chars = self._data.get("characters") or {}
        addr  = self._data.get("address_map") or []
        if not (terms or chars or addr):
            return ""
        lines = ["\n## SERIES MEMORY (decisions from earlier episodes — follow strictly)"]
        if terms:
            lines.append("Fixed term translations (use EXACTLY these, never re-decide):")
            lines.extend(f"- '{s}' → '{t}'" for s, t in list(terms.items())[:self.MAX_TERMS])
        if chars:
            lines.append("Characters (keep each voice consistent across episodes):")
            for name, meta in list(chars.items())[:self.MAX_CHARS]:
                style = meta.get("style") if isinstance(meta, dict) else ""
                lines.append(f"- {name}" + (f": {style}" if style else ""))
        if addr:
            lines.append("Address register (Turkish sen/siz — keep consistent):")
            for a in addr[:self.MAX_ADDR]:
                if not isinstance(a, dict):
                    continue
                aa, bb, reg = a.get("a"), a.get("b"), a.get("register")
                if aa and reg:
                    lines.append(f"- {aa} → {bb}: '{reg}'" if bb else f"- {aa}: '{reg}'")
        return "\n".join(lines) + "\n"

    def get_terms(self) -> dict:
        return dict(self._data.get("terms") or {})

    def counts(self) -> dict:
        return {"terms": len(self._data.get("terms", {})),
                "characters": len(self._data.get("characters", {})),
                "address": len(self._data.get("address_map", []))}
