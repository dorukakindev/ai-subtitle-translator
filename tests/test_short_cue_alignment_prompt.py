"""
S04E12/S04E14/S04E15 cue-kayması bulgularından çıkan pekiştirme kuralı ("her id
kendi çevirisini almalı, kısa/ünlem/SFX cue'lar komşuya birleştirilmemeli") HER
İKİ system prompt'ta da bulunmalı (CLAUDE.md: sync ve hybrid promptları senkron
kalmalı). Bkz. plans/s04e12-cue-shift-without-repair-brief.md Görev 3.
"""
import unittest
from pathlib import Path

import subtitle_translator_gui as gui

KEY_TOKENS = [
    "every numbered id in the payload MUST receive its own translation",
    "NEVER merge a short cue's meaning into a neighboring id's translation",
    "shifts every subsequent id's alignment",
]


class ShortCueAlignmentInSyncPromptTest(unittest.TestCase):
    def test_sync_prompt_contains_rule(self):
        p = gui._build_sync_system_prompt("English", "Turkish", None, "Orta")
        for tok in KEY_TOKENS:
            self.assertIn(tok, p, f"sync promptta eksik: {tok}")


class ShortCueAlignmentInHybridPromptTest(unittest.TestCase):
    """build_system_prompt harici ContextMemory gerektirir; kaynak metinde doğrula."""
    def test_hybrid_prompt_source_contains_rule(self):
        src = Path("hybrid_translate.py").read_text(encoding="utf-8")
        for tok in KEY_TOKENS:
            self.assertIn(tok, src, f"hybrid promptta eksik: {tok}")


if __name__ == "__main__":
    unittest.main()
