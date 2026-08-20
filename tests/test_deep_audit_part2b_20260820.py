# -*- coding: utf-8 -*-
"""YENI_DERIN_BUGLAR_VE_DUZELTME_REHBERI.md (Part 2) — ikinci tur.

Madde 3, 4, 9, 10, 13, 14/38, 17, 21, 24, 26, 28, 29, 31, 32, 35, 36, 43.
"""
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import hybrid_translate as ht
import sdh_cleaner
import series_memory as sm
import subtitle_formats as sf
import subtitle_translator_gui as g


class SeasonCanonHintIsEpisodeScopedTest(unittest.TestCase):
    """Madde 3 ve 19: kanon ipucu bölüm kısıtıyla ve sayısal sırayla alınmalı."""

    def _memory(self):
        memory = sm.SeriesMemory.__new__(sm.SeriesMemory)
        memory._data = {
            "terms": {"Negotiator": "Müzakereci", "Ghost": "Hayalet"},
            "characters": {},
            "address_map": [],
            "term_origins": {
                sm._term_origin_key("Negotiator"): "s01e001",
                sm._term_origin_key("Ghost"): "s01e005",
            },
            "character_origins": {},
            "address_origins": {},
            "updated_eps": ["s01e001", "s01e005"],
        }
        return memory

    def test_later_episode_terms_are_withheld(self):
        hint = self._memory().build_hint(before_episode=(1, 3))
        self.assertIn("Müzakereci", hint)
        self.assertNotIn("Hayalet", hint)

    def test_unscoped_hint_returns_everything(self):
        hint = self._memory().build_hint()
        self.assertIn("Müzakereci", hint)
        self.assertIn("Hayalet", hint)

    def test_unpadded_legacy_tags_compare_numerically(self):
        self.assertEqual(sm._episode_order("s01e002"), (1, 2))
        self.assertEqual(sm._episode_order("s1e10"), (1, 10))
        self.assertIsNone(sm._episode_order("bozuk"))
        self.assertLess(sm._episode_order("s1e2"), sm._episode_order("s1e10"))


class PluralAddressIsNotFormalTest(unittest.TestCase):
    """Madde 4: çoğul 'siz' resmî hitap sayılmamalı."""

    @staticmethod
    def _blocks(texts):
        return [
            (str(i), "00:00:0%d,000 --> 00:00:0%d,000" % (i % 9, (i + 1) % 9), t)
            for i, t in enumerate(texts, 1)
        ]

    def test_explicit_plural_lines_are_skipped(self):
        result = g.detect_address_register_mix(self._blocks([
            "Siz de gelin, hepiniz.", "Sizler nasılsınız?", "Sen nasılsın?",
            "Sen gel.", "Sana dedim.", "Senin evin.", "Seni gördüm.",
            "Sende kaldı.", "Senden aldım.", "Sen bilirsin.", "Sen kalk.",
            "Sen otur.", "Sen yaz."]))
        self.assertEqual(result["formal"], 0)
        self.assertFalse(result["mixed"])

    def test_singular_formal_is_still_counted(self):
        result = g.detect_address_register_mix(self._blocks([
            "Siz nasılsınız?", "Size söyledim.", "Sizi gördüm.",
            "Sen nasılsın?", "Sen gel.", "Sana dedim.", "Senin evin.",
            "Seni gördüm.", "Sende kaldı.", "Senden aldım.", "Sen bilirsin.",
            "Sen kalk."]))
        self.assertEqual(result["formal"], 3)
        self.assertTrue(result["mixed"])


class ContractionIsNotAQuoteTest(unittest.TestCase):
    """Madde 9: İngilizce kısaltma kesmesi tırnak sanılmamalı."""

    def test_contractions_produce_no_titles(self):
        self.assertEqual(
            ht.quoted_work_titles("I don't know what it's about, we'll see."),
            set())

    def test_real_titles_still_found(self):
        self.assertEqual(
            ht.quoted_work_titles('He read "War and Peace" today.'),
            {"war and peace"})

    def test_title_containing_an_apostrophe_survives(self):
        self.assertEqual(
            ht.quoted_work_titles("She wrote 'The Cat's Cradle' in 1963."),
            {"the cat's cradle"})


class PresentationHeadingsAreNotSpeakersTest(unittest.TestCase):
    """Madde 10: 'Problem:' bir konuşmacı değildir."""

    def test_headings_are_kept(self):
        for tr, src in (("Problem: kaynak yok.", "Problem: no source."),
                        ("Sonuç: başarılı.", "Result: successful."),
                        ("Adım 1: başla.", "Step 1: begin."),
                        ("Kural: uy.", "Rule: obey.")):
            with self.subTest(tr=tr):
                self.assertEqual(sdh_cleaner.strip_labels_by_source(tr, src), tr)

    def test_real_speaker_labels_are_still_stripped(self):
        self.assertEqual(
            sdh_cleaner.strip_labels_by_source("AHMET: merhaba.", "AHMET: Hello."),
            "merhaba.")


class AssSpeakerPrefixKeepsOverrideFirstTest(unittest.TestCase):
    """Madde 13: konuşmacı öneki konum etiketinin ÖNÜNE geçmemeli."""

    HEADER = (
        "[Script Info]\n[V4+ Styles]\n"
        "Format: Name, Fontname\nStyle: Default,Arial\n"
        "[Events]\n"
        "Format: Layer, Start, End, Style, Name, MarginL, MarginR, "
        "MarginV, Effect, Text\n"
    )

    def _parse(self, dialogue):
        handle, path = tempfile.mkstemp(suffix=".ass")
        os.close(handle)
        try:
            with open(path, "w", encoding="utf-8") as out:
                out.write(self.HEADER + dialogue + "\n")
            return list(sf.parse_ass(path))
        finally:
            os.unlink(path)

    def test_prefix_lands_after_the_position_tag(self):
        tag = "{" + chr(92) + "an8}"
        blocks = self._parse(
            "Dialogue: 0,0:00:01.00,0:00:03.00,Default,Ali,0,0,0,,"
            + tag + "Merhaba")
        self.assertTrue(blocks)
        self.assertTrue(blocks[0][2].startswith(tag), blocks[0][2])
        self.assertIn("Ali:", blocks[0][2])

    def test_untagged_line_keeps_the_plain_prefix(self):
        blocks = self._parse(
            "Dialogue: 0,0:00:01.00,0:00:03.00,Default,Ali,0,0,0,,Merhaba")
        self.assertTrue(blocks)
        self.assertTrue(blocks[0][2].startswith("Ali:"), blocks[0][2])


class CategoryMatchingFallbacksTest(unittest.TestCase):
    """Madde 14 ve 38: şema anahtarı ve İngilizce tür adı eşlenmeli."""

    def setUp(self):
        self.categories = g._detect_categories()

    def test_schema_keys_resolve(self):
        for key, expected in (("history_documentary", "Tarih Belgeseli"),
                              ("reality_street", "Reality / Sokak Argosu"),
                              ("cyberpunk_sci_fi", "Siberpunk / Distopya")):
            with self.subTest(key=key):
                self.assertEqual(
                    g._match_category(key, self.categories), expected)

    def test_english_genres_resolve(self):
        for name, expected in (("Documentary", "Belgesel"),
                               ("Comedy", "Komedi (Sitcom)"),
                               ("Horror", "Korku / Gerilim"),
                               ("Sci-Fi", "Siberpunk / Distopya"),
                               ("Romance", "Romantik Drama")):
            with self.subTest(name=name):
                self.assertEqual(
                    g._match_category(name, self.categories), expected)

    def test_unknown_answers_still_return_none(self):
        self.assertIsNone(g._match_category("zzz-unknown", self.categories))


class MidwordSpaceFileEvidenceTest(unittest.TestCase):
    """Madde 17: Türkçeleşmiş kelime bölünmesi dosya içi kanıtla yakalanır."""

    BLOCKS = [
        ("1", "00:00:01,000 --> 00:00:03,000", "Piram itler büyük."),
        ("2", "00:00:03,000 --> 00:00:05,000", "Piramitler Mısır'da."),
        ("3", "00:00:05,000 --> 00:00:07,000", "Piramitler antik yapılar."),
        ("4", "00:00:07,000 --> 00:00:09,000", "Her şey yolunda gidiyor."),
        ("5", "00:00:09,000 --> 00:00:11,000", "Herşeyi anladım sonunda."),
        ("6", "00:00:11,000 --> 00:00:13,000", "Herşeyi biliyorum artık."),
    ]
    CUES = {"1": "The pyramids are huge.", "2": "Pyramids are in Egypt.",
            "3": "Pyramids are ancient.", "4": "Everything is fine.",
            "5": "I understood everything.", "6": "I know everything."}

    def test_split_word_is_flagged_and_legit_pair_is_not(self):
        self.assertEqual(g._midword_space_ids(self.BLOCKS, self.CUES), ["1"])


class TokenBudgetMappingTest(unittest.TestCase):
    """Madde 31: max_completion_tokens gpt-5 dışında max_tokens'a dönmeli."""

    def test_legacy_models_receive_max_tokens(self):
        out = ht._normalize_chat_create_kwargs(
            "gpt-4o", {"max_completion_tokens": 300})
        self.assertEqual(out.get("max_tokens"), 300)
        self.assertNotIn("max_completion_tokens", out)

    def test_gpt5_keeps_max_completion_tokens(self):
        out = ht._normalize_chat_create_kwargs(
            "gpt-5.4-mini", {"max_tokens": 300})
        self.assertNotIn("max_tokens", out)
        self.assertGreaterEqual(out.get("max_completion_tokens"), 300)


class LineBreaksRunAfterQcTest(unittest.TestCase):
    """Madde 43: QC'nin uzattığı satırlar da kırılmalı."""

    LONG = ("Bu gerçekten çok uzun bir cümledir ve tek satırda kalırsa "
            "altyazı sınırını aşar bu yüzden kırılmalıdır")

    def test_finalize_applies_line_breaks_when_enabled(self):
        blocks = [("1", "00:00:01,000 --> 00:00:05,000", self.LONG)]
        src = {"1": "This is a very long sentence indeed."}
        without, _ = g._finalize_translation_blocks(blocks, src)
        with_breaks, _ = g._finalize_translation_blocks(
            blocks, src, line_breaks=True)
        self.assertNotIn("\n", without[0][2])
        self.assertIn("\n", with_breaks[0][2])


class SingleControlByteRepairTest(unittest.TestCase):
    """Madde 24: tek C1 kontrol karakteri de onarılmalı."""

    def test_english_contractions_use_cp1252(self):
        for raw, expected in (("It\x92s here.", "It’s here."),
                              ("Don\x92t worry, it\x92s fine.",
                               "Don’t worry, it’s fine."),
                              ("we\x92ll see", "we’ll see")):
            with self.subTest(raw=raw):
                self.assertEqual(
                    sf._repair_embedded_mac_roman_controls(raw), expected)

    def test_mac_roman_accents_are_not_broken(self):
        self.assertEqual(
            sf._repair_embedded_mac_roman_controls("Rodr\x92guez lives here."),
            "Rodríguez lives here.")

    def test_quote_pairs_still_decode(self):
        self.assertEqual(
            sf._repair_embedded_mac_roman_controls("He said \x93hi\x94."),
            "He said “hi”.")


class MojibakeFreeSourceTest(unittest.TestCase):
    """Madde 30: kaynakta çift kodlanmış Türkçe dize kalmamalı."""

    FILES = ("subtitle_translator_gui.py", "hybrid_translate.py",
             "subtitle_formats.py", "sdh_cleaner.py", "credential_store.py",
             "repair_batches.py", "series_memory.py", "translation_memory.py")
    MARKERS = ("Ä±", "ÅŸ", "ÄŸ", "Ã¼", "Ã§", "Ã¶", "Ä°")

    def test_no_double_encoded_turkish(self):
        root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        for name in self.FILES:
            path = os.path.join(root, name)
            if not os.path.exists(path):
                continue
            with open(path, "r", encoding="utf-8") as handle:
                data = handle.read()
            for marker in self.MARKERS:
                with self.subTest(file=name, marker=marker):
                    self.assertNotIn(marker, data)

    def test_local_fix_patterns_match_real_turkish(self):
        patterns = ht._LOCAL_FIX_SAFE_WITHOUT_SOURCE_PATTERNS
        joined = " ".join(str(getattr(p, "pattern", p)) for p in patterns)
        self.assertIn("yaşadığı", joined)
        self.assertIn("yaşadıkları", joined)


if __name__ == "__main__":
    unittest.main()
