"""
project_memory.py — Bölümler arası proje düzeyinde terim hafızası.

Bir dizi çevrilirken S01E01'de tespit edilen karakter isimleri, özel terimler
ve glossary girişleri S01E02'de otomatik olarak kullanılır.

Saklama: <input_dir>/.project_memory.json dosyasında.
"""

import json
import re
import threading
from pathlib import Path

from app_state import _interprocess_lock, atomic_write_json


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


# Analiz modeli karakter listesine sık sık unvan/meslek adı da koyar ("Doctor",
# "Captain", "Narrator"). Bunlar `KARAKTERLER:` başlığıyla isteme enjekte edilince
# model onları özel ad sanıp çevirmeden bırakıyor ("The doctor is here" →
# "Doctor geldi"). Tek başına gelen genel adlar hafızaya alınmaz; "Doctor Who" veya
# "Captain Ahab" gibi çok kelimeli gerçek adlar etkilenmez.
_COMMON_NOUN_FILTER = frozenset({
    "admiral", "agent", "boy", "boss", "captain", "chief", "colonel", "commander",
    "cook", "corporal", "detective", "doc", "doctor", "driver", "father", "general",
    "girl", "guard", "guy", "inspector", "judge", "kid", "king", "lady", "lieutenant",
    "major", "man", "master", "mister", "mother", "narrator", "nurse", "officer",
    "president", "priest", "professor", "queen", "reporter", "sergeant", "sheriff",
    "sir", "soldier", "teacher", "waiter", "woman",
    "adam", "anlatıcı", "başkan", "çocuk", "doktor", "hemşire", "kadın", "kaptan",
    "komutan", "memur", "öğretmen", "polis", "şerif", "yüzbaşı",
})


def is_generic_character_name(name) -> bool:
    """Tek kelimelik genel unvan/meslek adı mı (gerçek karakter adı değil)?"""
    text = " ".join(str(name or "").strip().split())
    if not text or " " in text:
        return False
    return text.casefold().strip(".,:;!?'\"") in _COMMON_NOUN_FILTER


def _translatable_stops() -> frozenset:
    """Baş harfi büyük yazılsa da SIRADAN olan İngilizce sözcükler."""
    try:
        from prompt_constants import TRANSLATABLE_CAPITALISED_STOPS
    except Exception:
        return frozenset()
    return frozenset(
        str(word or "").strip().casefold()
        for word in TRANSLATABLE_CAPITALISED_STOPS
    )


def is_self_translation(src, tgt) -> bool:
    """Kaynak==hedef mi (kelime kendine 'çevriliyor' → İngilizce sızıntısı)?

    İstisna: özel ad / kısaltma (Ayn Rand, IQ, marka adları) gerçekten
    korunmalı. Ancak ölçüt YALNIZ 'tamamı küçük harf' olamaz: analiz modeli
    cümle başındaki ya da başlık biçimli sözcüğü 'Camera → Camera' diye
    döndürdüğünde bu kimlik eşlemesi kalıcı hafızaya girip sonraki
    bölümlerde de sözcüğü İngilizce bırakıyordu (denetim 2026-08-21,
    madde 35). Bilinen sıradan sözcükler harf durumundan bağımsız reddedilir.
    """
    s, t = str(src).strip(), str(tgt).strip()
    if not s or s.lower() != t.lower():
        return False
    if s.islower():
        return True
    stops = _translatable_stops()
    if not stops:
        return False
    words = [word for word in re.findall(r"[^\W\d_]+", s, re.UNICODE)]
    return bool(words) and all(word.casefold() in stops for word in words)


class ProjectMemory:
    """Belirli bir giriş klasörüne bağlı proje hafızası."""

    def __init__(self, input_dir: str, target_language: str = "tr",
                 source_language: str = "en"):
        self.input_dir = Path(input_dir)
        self.target_language = _target_key(target_language)
        self.source_language = _source_key(source_language)
        if self.source_language == "en":
            filename = (
                ".project_memory.json"
                if self.target_language == "tr"
                else f".project_memory.{self.target_language}.json"
            )
        else:
            filename = (
                f".project_memory.src-{self.source_language}."
                f"tgt-{self.target_language}.json"
            )
        self._path = self.input_dir / filename
        self._lock = threading.RLock()
        self._data: dict = self._load()

    # ── Yükleme / Kaydetme ────────────────────────────────────────────────────

    def _load(self) -> dict:
        if self._path.exists():
            try:
                with open(self._path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                if isinstance(data, dict):
                    cached_target = data.get("target_language")
                    cached_source = data.get("source_language")
                    if ((not cached_target
                         or _target_key(cached_target) == self.target_language)
                            and (not cached_source
                                 or _source_key(cached_source) == self.source_language)):
                        data["target_language"] = self.target_language
                        data["source_language"] = self.source_language
                        return data
            except Exception:
                pass
        return {
            "target_language": self.target_language,
            "source_language": self.source_language,
            "glossary": {},        # src → tgt terim eşlemeleri
            "characters": {},      # orijinal_isim → TR karşılığı (ya da aynısı)
            "proper_nouns": {},    # yer/kurum/marka adları
            "pronoun_map": {},     # sen/siz tercihleri per karakter
            "series_notes": [],    # serbest metin notlar
        }

    @staticmethod
    def _merge_data(disk_data: dict, memory_data: dict) -> dict:
        memory_target = _target_key(memory_data.get("target_language", "tr"))
        memory_source = _source_key(memory_data.get("source_language", "en"))
        disk_target = (
            _target_key(disk_data.get("target_language"))
            if isinstance(disk_data, dict) and disk_data.get("target_language")
            else memory_target
        )
        if disk_target != memory_target:
            disk_data = {}
        disk_source = (
            _source_key(disk_data.get("source_language"))
            if isinstance(disk_data, dict) and disk_data.get("source_language")
            else memory_source
        )
        if disk_source != memory_source:
            disk_data = {}
        merged = {}
        for key in ("glossary", "characters", "proper_nouns", "pronoun_map"):
            values = dict(disk_data.get(key, {})) if isinstance(disk_data, dict) else {}
            for item, value in dict(memory_data.get(key, {})).items():
                values.setdefault(item, value)
            merged[key] = values
        disk_notes = list(disk_data.get("series_notes", [])) if isinstance(disk_data, dict) else []
        memory_notes = list(memory_data.get("series_notes", []))
        merged["series_notes"] = list(dict.fromkeys(disk_notes + memory_notes))
        merged["target_language"] = memory_target
        merged["source_language"] = memory_source
        return merged

    def save(self, merge_existing=True):
        with self._lock:
            try:
                self._path.parent.mkdir(parents=True, exist_ok=True)
                with _interprocess_lock(self._path):
                    if merge_existing and self._path.exists():
                        try:
                            disk_data = json.loads(self._path.read_text(encoding="utf-8"))
                        except Exception as exc:
                            raise ValueError(
                                "mevcut proje hafızası bozuk; veri kaybını önlemek "
                                "için üzerine yazılmadı"
                            ) from exc
                        if not isinstance(disk_data, dict):
                            raise ValueError(
                                "mevcut proje hafızası nesne biçiminde değil; veri "
                                "kaybını önlemek için üzerine yazılmadı"
                            )
                        self._data = self._merge_data(disk_data, self._data)
                    atomic_write_json(self._path, self._data)
                return True
            except Exception as exc:
                import sys
                print(f"[project_memory] kaydetme hatası {self._path}: {exc}", file=sys.stderr)
                return False

    # ── Glossary ──────────────────────────────────────────────────────────────

    # Prompt ipucu terim listesini KIRPIYOR; kilitli kume ise
    # kirpilmiyordu. Modele hic soylenmemis bir terim dogrulayiciya
    # dayatiliyor: yanlis locked_term_violation redleri ve gereksiz
    # terim-normalizasyonu adaylari. Kullanicinin gercek dosyasinda
    # 49 terimin 19'u bu durumdaydi.
    MAX_HINT_TERMS = 30

    def get_glossary(self) -> dict:
        """Sozlugun TAMAMI — gosterim ve duzenleme icin."""
        with self._lock:
            return dict(self._data.get("glossary", {}))

    def get_locked_glossary(self) -> dict:
        """Cevirilerde DAYATILACAK kume: prompt ipucuyla AYNI kesme."""
        with self._lock:
            items = list((self._data.get("glossary") or {}).items())
            return dict(items[:self.MAX_HINT_TERMS])

    def update_glossary(self, new_terms: dict):
        """Yeni terim çiftlerini proje sözlüğüne ekler (mevcut girişler korunur)."""
        with self._lock:
            gl = self._data.setdefault("glossary", {})
            for src, tgt in new_terms.items():
                if not (src and tgt) or src in gl:
                    continue
                if is_self_translation(src, tgt):
                    continue
                gl[src] = tgt
            return self.save()

    def merge_glossary_from_analysis(self, recurring_terms: dict):
        """ContextMemory.recurring_terms'den otomatik terim çıkarımı."""
        if not isinstance(recurring_terms, dict):
            return True
        return self.update_glossary(recurring_terms)

    # ── Karakter isimleri ─────────────────────────────────────────────────────

    def get_characters(self) -> dict:
        with self._lock:
            return dict(self._data.get("characters", {}))

    def update_characters(self, names: list):
        """Karakter isimlerini kaydet (değişmez olarak)."""
        if not names:
            return True
        with self._lock:
            chars = self._data.setdefault("characters", {})
            for name in names:
                if not isinstance(name, str):
                    name = "" if name is None else str(name)
                name = name.strip()
                if name and not is_generic_character_name(name) and name not in chars:
                    chars[name] = name
            return self.save()

    # ── Pronoun map ───────────────────────────────────────────────────────────

    def get_pronoun_map(self) -> dict:
        with self._lock:
            return dict(self._data.get("pronoun_map", {}))

    def update_pronoun_map(self, pmap: dict):
        if not isinstance(pmap, dict):
            return True
        with self._lock:
            pm = self._data.setdefault("pronoun_map", {})
            for k, v in pmap.items():
                if k not in pm:
                    pm[k] = v
            return self.save()

    # ── Notlar ────────────────────────────────────────────────────────────────

    def add_note(self, note: str):
        with self._lock:
            notes = self._data.setdefault("series_notes", [])
            if note and note not in notes:
                notes.append(note)
            return self.save()

    def get_notes(self) -> list:
        with self._lock:
            return list(self._data.get("series_notes", []))

    # ── Birleşik context özeti ────────────────────────────────────────────────

    def build_context_hint(self) -> str:
        """Çeviri system prompt'una enjekte edilecek kısa özet döner."""
        with self._lock:
            parts = []
            gl = self.get_glossary()
            if gl:
                term_lines = [
                    f"  {s} → {t}"
                    for s, t in list(gl.items())[:self.MAX_HINT_TERMS]]
                parts.append("PROJE TERİMLERİ (bu çeviride tutarlı kullan):\n" + "\n".join(term_lines))
            chars = self.get_characters()
            if chars:
                char_list = ", ".join(list(chars.keys())[:20])
                parts.append(f"KARAKTERLER: {char_list}")
            pm = self.get_pronoun_map()
            if pm:
                pm_lines = [f"  {k}: {v}" for k, v in list(pm.items())[:30]]
                parts.append("HİTAP (sen/siz):\n" + "\n".join(pm_lines))
            notes = self.get_notes()
            if notes:
                parts.append("SERİ NOTLARI:\n" + "\n".join(f"  • {n}" for n in notes[:5]))
            if not parts:
                return ""
            return "\n\n## PROJE HAFIZASI\n" + "\n\n".join(parts) + "\n"

    # ── Sıfırlama / temizlik ──────────────────────────────────────────────────

    def clear(self):
        with self._lock:
            self._data = {
                "target_language": self.target_language,
                "source_language": self.source_language,
                "glossary": {}, "characters": {}, "proper_nouns": {},
                "pronoun_map": {}, "series_notes": [],
            }
            return self.save(merge_existing=False)

    def stats(self) -> dict:
        with self._lock:
            return {
                "glossary": len(self._data.get("glossary", {})),
                "characters": len(self._data.get("characters", {})),
                "notes": len(self._data.get("series_notes", [])),
            }

    # ── Seri adı / episode tespiti ────────────────────────────────────────────

    @staticmethod
    def detect_series_key(filepath: str) -> str | None:
        """Dosya adından seri adını çıkarır: S01E01 → 'S01', 'EP01' → 'EP01'.
        Seri tespit edilemezse None döner."""
        name = Path(filepath).stem
        m = re.search(r'[Ss](\d{1,2})[Ee]\d{1,2}', name)
        if m:
            return f"S{int(m.group(1)):02d}"
        m2 = re.search(r'[Ee][Pp]?(\d{1,3})', name, re.IGNORECASE)
        if m2:
            return f"EP{int(m2.group(1)):03d}"
        return None
