"""
Denetimden (Frisky Dingo 1x01-1x03) çıkan tekrarlayan çeviri hatalarını hedefleyen
'IDIOM & REGISTER TRAPS' prompt kuralları HER İKİ system prompt'ta da bulunmalı
(CLAUDE.md: sync ve hybrid promptları senkron kalmalı).
"""
import unittest
from pathlib import Path

import subtitle_translator_gui as gui

# Denetimde gözlemlenen birebir hata→düzeltme çiftleri
KEY_TOKENS = [
    "MEANING-FIRST",
    "sense-for-sense",
    "unstated ideas",
    "Duration/CPS beats source length",
    "<=21 CPS",
    "<=24 CPS",
    "Preserve polarity exactly",
    "pronouns and deictics",
    "Keep the same number of subtitle lines",
    "Do NOT invent pseudo-Turkish",
    "<font ...>",
    "False friends",
    "actually→aslında",
    "glossary target has the wrong sense",
    "IDIOM & REGISTER TRAPS",
    "ye büyükler",        # arkaik 'ye' çevrilmeden bırakma
    "Büyük Scott",        # 'Great Scott!' literal
    "koca sikli kapı",    # 'big-ass' yanlış cinsel register
    "alt çizgi",          # 'bottom line' literal
    "Küre küre",          # 'Row row row' → fiil/isim karışması
]


class IdiomTrapsInSyncPromptTest(unittest.TestCase):
    def test_sync_prompt_contains_all_traps(self):
        p = gui._build_sync_system_prompt("English", "Turkish", None, "Orta")
        for tok in KEY_TOKENS:
            self.assertIn(tok, p, f"sync promptta eksik: {tok}")


class IdiomTrapsInHybridPromptTest(unittest.TestCase):
    """build_system_prompt harici ContextMemory gerektirir; kaynak metinde doğrula."""
    def test_hybrid_prompt_source_contains_all_traps(self):
        src = Path("hybrid_translate.py").read_text(encoding="utf-8")
        src += "\n" + Path("prompt_constants.py").read_text(encoding="utf-8")
        for tok in KEY_TOKENS:
            self.assertIn(tok, src, f"hybrid promptta eksik: {tok}")


class MeaningFirstInGuiReviewPromptsTest(unittest.TestCase):
    def test_gui_review_and_polish_prompts_keep_meaning_first_rules(self):
        src = Path("subtitle_translator_gui.py").read_text(encoding="utf-8")
        self.assertIn("word-for-word rendering that misses intent", src)
        self.assertIn("Preserve polarity, questions, and numbers exactly", src)
        self.assertIn("Olumsuzluğu, soru kipini ve sayısal değeri aynen koru", src)
        self.assertIn("ANLAM ÖNCELİĞİ", src)


class HybridQualityGuardSourceTest(unittest.TestCase):
    def test_hybrid_source_keeps_cps_and_idiom_guards(self):
        src = Path("hybrid_translate.py").read_text(encoding="utf-8")
        self.assertIn("Read-Aloud Flow & CPS", src)
        self.assertIn("cash in hand", src)
        self.assertIn("TERM_MISTRANSLATION:cash_in_hand", src)


if __name__ == "__main__":
    unittest.main()
