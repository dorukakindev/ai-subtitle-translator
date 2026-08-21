# -*- coding: utf-8 -*-
"""HARIC_YENI_BUG_DENETIMI_2026-08-21.md — madde 9-16 ve 30."""
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import subtitle_formats as sf
import subtitle_translator_gui as g
import translation_memory as tm

NEWLINE = chr(10)


def _write_vtt(folder, body, header=""):
    path = os.path.join(folder, "sample.vtt")
    with open(path, "w", encoding="utf-8") as handle:
        handle.write("WEBVTT" + NEWLINE + header + NEWLINE + NEWLINE + body)
    return path


class VttEntityDecodingTest(unittest.TestCase):
    """Madde 9: WebVTT karakter referansları çözülmeli."""

    def test_named_and_numeric_entities_decode(self):
        for value, expected in (("Tom &amp; Jerry", "Tom & Jerry"),
                                ("&nbsp;", " "),
                                ("&#65;&#x42;", "AB"),
                                ("&hellip;", "…"),
                                ("&lrm;", "‎")):
            with self.subTest(value=value):
                self.assertEqual(sf.decode_vtt_entities(value), expected)

    def test_plain_ampersand_and_unknown_entities_survive(self):
        for value in ("AT&T", "&filmname;", "5 & 7"):
            with self.subTest(value=value):
                self.assertEqual(sf.decode_vtt_entities(value), value)

    def test_escaped_markup_is_not_turned_into_a_real_tag(self):
        # Cozulseydi sonraki temizlik katmani onu gercek etiket sanip silerdi.
        value = "&lt;i&gt;ekranda gorunecek&lt;/i&gt;"
        self.assertEqual(sf.decode_vtt_entities(value), value)

    def test_comparison_entities_still_decode(self):
        self.assertEqual(sf.decode_vtt_entities("5 &lt; 7"), "5 < 7")

    def test_the_parser_applies_the_decoding(self):
        with tempfile.TemporaryDirectory() as folder:
            path = _write_vtt(
                folder,
                "00:00:01.000 --> 00:00:02.000" + NEWLINE
                + "Tom &amp; Jerry" + NEWLINE)
            blocks = list(sf.parse_vtt(path))
        self.assertEqual(blocks[0][2], "Tom & Jerry")


class ExactMemoryLineShapeTest(unittest.TestCase):
    """Madde 10: satır yapısı farklı kaynaklar aynı kayda düşmemeli."""

    SETTINGS = {"tgt_lang": "tr", "model": "gpt", "schema_name": "film",
                "source_language": "english", "context_fingerprint": "ctx"}

    def _memory(self):
        folder = tempfile.mkdtemp()
        memory = tm.TranslationMemory(os.path.join(folder, "tm.db"))
        self.addCleanup(memory.close)
        return memory

    def test_multiline_and_single_line_sources_stay_separate(self):
        memory = self._memory()
        memory.store("Come" + NEWLINE + "here", "Gel" + NEWLINE + "buraya",
                     **self.SETTINGS)
        self.assertIsNone(memory.lookup("Come here", **self.SETTINGS))
        self.assertEqual(
            memory.lookup("Come" + NEWLINE + "here", **self.SETTINGS),
            "Gel" + NEWLINE + "buraya")

    def test_batch_lookup_applies_the_same_rule(self):
        memory = self._memory()
        memory.store("Come" + NEWLINE + "here", "Gel" + NEWLINE + "buraya",
                     **self.SETTINGS)
        found = memory.lookup_batch(
            ["Come here", "Come" + NEWLINE + "here"], **self.SETTINGS)
        self.assertNotIn("Come here", found)
        self.assertIn("Come" + NEWLINE + "here", found)

    def test_case_insensitive_lookup_is_deliberately_kept(self):
        # Teslim harf durumunu kaynaktan yeniden turetiyor; buyuk/kucuk
        # duyarsiz arama testle kilitli bir tasarim.
        memory = self._memory()
        memory.store("Run.", "Kos.", **self.SETTINGS)
        self.assertEqual(memory.lookup("RUN.", **self.SETTINGS), "Kos.")


class UnsupportedTagsAreNotRestoredTest(unittest.TestCase):
    """Madde 11: yalnız desteklenen biçim etiketleri geri yazılmalı."""

    def test_arbitrary_tags_are_dropped(self):
        for source in ("<script>alert(1)</script>Hello.", "<blink>Hi</blink>",
                       "<marquee>Hi</marquee>"):
            with self.subTest(source=source):
                self.assertEqual(
                    sf.restore_format_tags(source, "Merhaba."), "Merhaba.")

    def test_supported_wrapping_still_round_trips(self):
        self.assertEqual(
            sf.restore_format_tags("<i>Hello.</i>", "Merhaba."),
            "<i>Merhaba.</i>")
        self.assertEqual(
            sf.restore_format_tags("<b><i>Hi</i></b>", "Selam"),
            "<b><i>Selam</i></b>")
        self.assertEqual(
            sf.restore_format_tags('<font color="#fff">Hi</font>', "Selam"),
            '<font color="#fff">Selam</font>')


class GeneratedArtifactNeedsEvidenceTest(unittest.TestCase):
    """Madde 13 ve 30: program çıktısı kararı komşu kaynak kanıtına bağlı."""

    NAMES = ("movie.vtt", "movie.vtt.srt", "movie.ass", "movie.ass.srt",
             "film.srt", "film.tr.srt", "indirilen.tr.srt",
             "x.partial.srt", "y.ham.srt", ".z.stage.srt")

    def _folder(self):
        folder = tempfile.mkdtemp()
        for name in self.NAMES:
            with open(os.path.join(folder, name), "w",
                      encoding="utf-8") as handle:
                handle.write("1" + NEWLINE + "00:00:01,000 --> 00:00:02,000"
                             + NEWLINE + "x" + NEWLINE + NEWLINE)
        return folder

    def test_outputs_with_a_neighbouring_source_are_excluded(self):
        folder = self._folder()
        for name in ("movie.vtt.srt", "movie.ass.srt", "film.tr.srt"):
            with self.subTest(name=name):
                self.assertTrue(
                    sf.is_generated_subtitle_file(os.path.join(folder, name)))

    def test_a_standalone_language_tagged_file_is_a_source(self):
        folder = self._folder()
        self.assertFalse(
            sf.is_generated_subtitle_file(
                os.path.join(folder, "indirilen.tr.srt")))

    def test_internal_artefacts_never_need_evidence(self):
        with tempfile.TemporaryDirectory() as folder:
            for name in ("x.partial.srt", "y.ham.srt", ".z.stage.srt",
                         "w.bak.srt", "v.wave1of2.srt"):
                with self.subTest(name=name):
                    self.assertTrue(
                        sf.is_generated_subtitle_file(
                            os.path.join(folder, name)))

    def test_the_scan_returns_only_the_real_sources(self):
        folder = self._folder()
        found = sorted(os.path.basename(path) for path
                       in sf.get_subtitle_files(folder, recursive=False))
        self.assertEqual(
            found, ["film.srt", "indirilen.tr.srt", "movie.ass", "movie.vtt"])


class SharedTimestampSourceMapTest(unittest.TestCase):
    """Madde 14: aynı zaman damgalı ayrı cue'lar birbirini ezmemeli."""

    class _Cue:
        def __init__(self, index, start, end, text):
            self.index, self.start, self.end, self.text = index, start, end, text

    def test_two_cues_sharing_a_span_get_their_own_source(self):
        blocks = [("1", "00:00:01,000 --> 00:00:03,000", "Bir"),
                  ("2", "00:00:01,000 --> 00:00:03,000", "Iki")]
        cues = [self._Cue("1", "00:00:01,000", "00:00:03,000", "One"),
                self._Cue("2", "00:00:01,000", "00:00:03,000", "Two")]
        self.assertEqual(
            g._delivery_source_map(blocks, cues), {"1": "One", "2": "Two"})

    def test_a_merged_output_cue_still_gets_the_joined_source(self):
        blocks = [("1", "00:00:01,000 --> 00:00:05,000", "Birlesik")]
        cues = [self._Cue("1", "00:00:01,000", "00:00:02,000", "One"),
                self._Cue("2", "00:00:03,000", "00:00:05,000", "Two")]
        self.assertEqual(
            g._delivery_source_map(blocks, cues),
            {"1": "One" + NEWLINE + "Two"})


class VttTimestampMapTest(unittest.TestCase):
    """Madde 15: `X-TIMESTAMP-MAP` medya ofseti uygulanmalı."""

    def _parse(self, header, body):
        with tempfile.TemporaryDirectory() as folder:
            return list(sf.parse_vtt(_write_vtt(folder, body, header)))

    def test_the_offset_moves_the_cue_onto_the_media_timeline(self):
        blocks = self._parse(
            "X-TIMESTAMP-MAP=LOCAL:00:00:00.000,MPEGTS:900000",
            "00:00:01.000 --> 00:00:02.000" + NEWLINE + "Hello" + NEWLINE)
        self.assertEqual(blocks[0][1], "00:00:11,000 --> 00:00:12,000")

    def test_a_non_zero_local_anchor_is_subtracted(self):
        blocks = self._parse(
            "X-TIMESTAMP-MAP=LOCAL:00:00:05.000,MPEGTS:900000",
            "00:00:06.000 --> 00:00:07.000" + NEWLINE + "Hello" + NEWLINE)
        self.assertEqual(blocks[0][1], "00:00:11,000 --> 00:00:12,000")

    def test_a_plain_vtt_keeps_its_times(self):
        blocks = self._parse(
            "", "00:00:01.000 --> 00:00:02.000" + NEWLINE + "Hello" + NEWLINE)
        self.assertEqual(blocks[0][1], "00:00:01,000 --> 00:00:02,000")

    def test_a_broken_map_is_ignored(self):
        self.assertEqual(
            sf.parse_vtt_timestamp_map("WEBVTT" + NEWLINE + "X-TIMESTAMP-MAP=SACMA"),
            0.0)

    def test_the_counter_wraps_at_33_bits(self):
        offset = sf.parse_vtt_timestamp_map(
            "X-TIMESTAMP-MAP=LOCAL:00:00:00.000,MPEGTS:%d" % ((1 << 33) + 900000))
        self.assertAlmostEqual(offset, 10.0)


class LogRotationSurvivesAMissingFileTest(unittest.TestCase):
    """Madde 16: kaybolan tek log dosyası açılışı düşürmemeli."""

    def test_a_file_that_vanishes_does_not_raise(self):
        from pathlib import Path

        with tempfile.TemporaryDirectory() as folder:
            for index in range(3):
                with open(os.path.join(folder, "run%d.log" % index), "w",
                          encoding="utf-8") as handle:
                    handle.write("x")
            missing = Path(folder) / "gone.log"
            original_glob = Path.glob

            def _glob(self, pattern):
                found = list(original_glob(self, pattern))
                return found + [missing]

            Path.glob = _glob
            try:
                g.rotate_logs(Path(folder), keep=1)
            finally:
                Path.glob = original_glob


if __name__ == "__main__":
    unittest.main()
