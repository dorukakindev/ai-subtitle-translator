"""
project_memory.py — Bölümler arası proje düzeyinde terim hafızası.

Bir dizi çevrilirken S01E01'de tespit edilen karakter isimleri, özel terimler
ve glossary girişleri S01E02'de otomatik olarak kullanılır.

Saklama: <input_dir>/.project_memory.json dosyasında.
"""

import json
import re
from pathlib import Path


def is_self_translation(src, tgt) -> bool:
    """Kaynak==hedef mi (kelime kendine 'çevriliyor' → İngilizce sızıntısı)?
    İstisna: özel ad / kısaltma / büyük harf içeren terimler (Ayn Rand, IQ, marka
    adları) gerçekten korunmalı; SADECE tamamı küçük-harf sıradan kelimeleri reddet
    (camera→camera, train→train, police→police gibi)."""
    s, t = str(src).strip(), str(tgt).strip()
    return bool(s) and s.lower() == t.lower() and s.islower()


class ProjectMemory:
    """Belirli bir giriş klasörüne bağlı proje hafızası."""

    def __init__(self, input_dir: str):
        self.input_dir = Path(input_dir)
        self._path = self.input_dir / ".project_memory.json"
        self._data: dict = self._load()

    # ── Yükleme / Kaydetme ────────────────────────────────────────────────────

    def _load(self) -> dict:
        if self._path.exists():
            try:
                with open(self._path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                pass
        return {
            "glossary": {},        # src → tgt terim eşlemeleri
            "characters": {},      # orijinal_isim → TR karşılığı (ya da aynısı)
            "proper_nouns": {},    # yer/kurum/marka adları
            "pronoun_map": {},     # sen/siz tercihleri per karakter
            "series_notes": [],    # serbest metin notlar
        }

    def save(self):
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            # Atomik yazım: çökme/yarım yazım JSON'u bozmasın
            _tmp = self._path.with_name(self._path.name + ".tmp")
            with open(_tmp, "w", encoding="utf-8") as f:
                json.dump(self._data, f, indent=2, ensure_ascii=False)
            _tmp.replace(self._path)
        except Exception:
            pass

    # ── Glossary ──────────────────────────────────────────────────────────────

    def get_glossary(self) -> dict:
        return dict(self._data.get("glossary", {}))

    def update_glossary(self, new_terms: dict):
        """Yeni terim çiftlerini proje sözlüğüne ekler (mevcut girişler korunur)."""
        gl = self._data.setdefault("glossary", {})
        for src, tgt in new_terms.items():
            if not (src and tgt) or src in gl:
                continue
            # 'train'→'train', 'camera'→'camera' gibi kaynak==hedef girdileri
            # İngilizce'yi Türkçe çıktıya sızdırır. Özel ad/kısaltma (Ayn Rand, IQ)
            # gerçekten korunmalı, onları engelleme.
            if is_self_translation(src, tgt):
                continue
            gl[src] = tgt
        self.save()

    def merge_glossary_from_analysis(self, recurring_terms: dict):
        """ContextMemory.recurring_terms'den otomatik terim çıkarımı."""
        if not isinstance(recurring_terms, dict):
            return
        self.update_glossary(recurring_terms)

    # ── Karakter isimleri ─────────────────────────────────────────────────────

    def get_characters(self) -> dict:
        return dict(self._data.get("characters", {}))

    def update_characters(self, names: list):
        """Karakter isimlerini kaydet (değişmez olarak)."""
        if not names:
            return
        chars = self._data.setdefault("characters", {})
        for name in names:
            if not isinstance(name, str):
                name = "" if name is None else str(name)
            name = name.strip()
            if name and name not in chars:
                chars[name] = name  # isimleri olduğu gibi koru
        self.save()

    # ── Pronoun map ───────────────────────────────────────────────────────────

    def get_pronoun_map(self) -> dict:
        return dict(self._data.get("pronoun_map", {}))

    def update_pronoun_map(self, pmap: dict):
        if not isinstance(pmap, dict):
            return
        pm = self._data.setdefault("pronoun_map", {})
        # İlk karar kanon: mevcut girişlerin ÜZERİNE yazma, yalnız yeni karakterleri ekle
        for k, v in pmap.items():
            if k not in pm:
                pm[k] = v
        self.save()

    # ── Notlar ────────────────────────────────────────────────────────────────

    def add_note(self, note: str):
        notes = self._data.setdefault("series_notes", [])
        if note and note not in notes:
            notes.append(note)
        self.save()

    def get_notes(self) -> list:
        return list(self._data.get("series_notes", []))

    # ── Birleşik context özeti ────────────────────────────────────────────────

    def build_context_hint(self) -> str:
        """Çeviri system prompt'una enjekte edilecek kısa özet döner."""
        parts = []
        gl = self.get_glossary()
        if gl:
            term_lines = [f"  {s} → {t}" for s, t in list(gl.items())[:30]]
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
        self._data = {
            "glossary": {}, "characters": {}, "proper_nouns": {},
            "pronoun_map": {}, "series_notes": [],
        }
        self.save()

    def stats(self) -> dict:
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
