# -*- coding: utf-8 -*-
"""HARIC_YENI_BUG_DENETIMI_2026-08-21.md — madde 17-23."""
import hashlib
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import subtitle_formats as sf
import subtitle_translator_gui as g

NL = chr(10)
BS = chr(92)


def _ass(script_info="", styles="", events=""):
    body = ("[Script Info]" + NL + script_info + NL
            + "[V4+ Styles]" + NL
            + "Format: Name, Fontname, PrimaryColour" + NL
            + (styles or "Style: Default,Arial,&H00FFFFFF") + NL
            + "[Events]" + NL
            + "Format: Layer, Start, End, Style, Name, MarginL, MarginR, "
              "MarginV, Effect, Text" + NL
            + events + NL)
    handle, path = tempfile.mkstemp(suffix=".ass")
    os.close(handle)
    with open(path, "w", encoding="utf-8") as out:
        out.write(body)
    return path


def _parse_ass(**kwargs):
    path = _ass(**kwargs)
    try:
        return list(sf.parse_ass(path))
    finally:
        os.unlink(path)


class ArchivedSourceNeedsTheRightVersionTest(unittest.TestCase):
    """Madde 18: arşivdeki doğru kaynak sürümü hash ile seçilmeli."""

    def _archive(self, *contents):
        folder = Path(tempfile.mkdtemp())
        archive = folder / "Raporlar" / "Kaynak"
        archive.mkdir(parents=True)
        report = folder / "Raporlar" / "ceviri_raporu.json"
        report.write_text("{}", encoding="utf-8")
        for name, body in contents:
            (archive / name).write_text(body, encoding="utf-8")
        return report, folder / "movie.en.srt"

    def test_the_expected_hash_picks_the_matching_version(self):
        digest = hashlib.sha256("NEW SOURCE".encode("utf-8")).hexdigest()
        report, source = self._archive(
            ("movie.en.srt", "OLD SOURCE"),
            ("movie.en." + digest[:12] + ".srt", "NEW SOURCE"))
        chosen = g._archived_source_candidate(
            report, source, expected_hash=digest)
        self.assertIsNotNone(chosen)
        self.assertEqual(chosen.read_text(encoding="utf-8"), "NEW SOURCE")

    def test_two_different_contents_without_a_hash_fail_closed(self):
        report, source = self._archive(
            ("movie.en.srt", "OLD SOURCE"),
            ("movie.en.abcdef123456.srt", "NEW SOURCE"))
        self.assertIsNone(g._archived_source_candidate(report, source))

    def test_a_single_version_is_still_returned(self):
        report, source = self._archive(("movie.en.srt", "ONLY SOURCE"))
        chosen = g._archived_source_candidate(report, source)
        self.assertIsNotNone(chosen)
        self.assertEqual(chosen.read_text(encoding="utf-8"), "ONLY SOURCE")

    def test_an_expected_hash_that_is_absent_returns_nothing(self):
        report, source = self._archive(("movie.en.srt", "ONLY SOURCE"))
        self.assertIsNone(
            g._archived_source_candidate(report, source, expected_hash="ff" * 32))


class AssTimerScaleTest(unittest.TestCase):
    """Madde 19: `Timer` çarpanı medya zamanına uygulanmalı."""

    DIALOGUE = "Dialogue: 0,0:00:10.00,0:00:12.00,Default,,0,0,0,,Merhaba"

    def _timestamp(self, script_info):
        rows = _parse_ass(script_info=script_info, events=self.DIALOGUE)
        return rows[0][1] if rows else ""

    def test_a_faster_script_clock_shortens_the_times(self):
        self.assertEqual(self._timestamp("Timer: 200.0000"),
                         "00:00:05,000 --> 00:00:06,000")

    def test_a_slower_script_clock_stretches_them(self):
        self.assertEqual(self._timestamp("Timer: 50.0000"),
                         "00:00:20,000 --> 00:00:24,000")

    def test_normal_missing_and_invalid_values_change_nothing(self):
        for script_info in ("", "Timer: 100.0000", "Timer: 0", "Timer: abc"):
            with self.subTest(script_info=script_info):
                self.assertEqual(self._timestamp(script_info),
                                 "00:00:10,000 --> 00:00:12,000")

    def test_a_comma_decimal_separator_is_accepted(self):
        self.assertAlmostEqual(sf.parse_ass_timer_scale("Timer: 200,0000"), 0.5)


class AssInvisibleTextTest(unittest.TestCase):
    """Madde 20: tamamen saydam metin teslime çıkmamalı."""

    STYLES = ("Style: Default,Arial,&H00FFFFFF" + NL
              + "Style: Hidden,Arial,&HFFFFFFFF")

    def _texts(self, events):
        return [row[2] for row in _parse_ass(styles=self.STYLES, events=events)]

    def test_a_fully_transparent_style_is_dropped(self):
        texts = self._texts(
            "Dialogue: 0,0:00:01.00,0:00:02.00,Hidden,,0,0,0,,GIZLI")
        self.assertEqual(texts, [])

    def test_an_event_hidden_from_start_to_end_is_dropped(self):
        texts = self._texts(
            "Dialogue: 0,0:00:01.00,0:00:02.00,Default,,0,0,0,,{"
            + BS + "alpha&HFF&}GIZLI")
        self.assertEqual(texts, [])

    def test_only_the_visible_half_survives(self):
        texts = self._texts(
            "Dialogue: 0,0:00:01.00,0:00:02.00,Default,,0,0,0,,{"
            + BS + "alpha&HFF&}gizli{" + BS + "alpha&H00&}gorunur")
        self.assertEqual(len(texts), 1)
        self.assertNotIn("gizli", texts[0])
        self.assertIn("gorunur", texts[0])

    def test_normal_and_semi_transparent_text_is_untouched(self):
        texts = self._texts(
            "Dialogue: 0,0:00:01.00,0:00:02.00,Default,,0,0,0,,Normal" + NL
            + "Dialogue: 0,0:00:03.00,0:00:04.00,Default,,0,0,0,,{"
            + BS + "alpha&H80&}yari saydam")
        self.assertEqual(len(texts), 2)
        self.assertIn("yari saydam", texts[1])


class AssWrapStyleTest(unittest.TestCase):
    """Madde 21: küçük `\\n` yalnız WrapStyle 2'de satır sonudur."""

    def _text(self, wrap_style, body):
        script_info = ("WrapStyle: %s" % wrap_style
                       if wrap_style is not None else "")
        rows = _parse_ass(
            script_info=script_info,
            events="Dialogue: 0,0:00:01.00,0:00:02.00,Default,,0,0,0,," + body)
        return rows[0][2] if rows else ""

    def test_soft_newline_is_a_space_outside_wrap_style_two(self):
        for wrap_style in (0, 1, 3, None):
            with self.subTest(wrap_style=wrap_style):
                self.assertEqual(
                    self._text(wrap_style, "Hello" + BS + "nworld"),
                    "Hello world")

    def test_soft_newline_breaks_under_wrap_style_two(self):
        self.assertEqual(
            self._text(2, "Hello" + BS + "nworld"), "Hello" + NL + "world")

    def test_hard_newline_always_breaks(self):
        for wrap_style in (0, 2):
            with self.subTest(wrap_style=wrap_style):
                self.assertEqual(
                    self._text(wrap_style, "Hello" + BS + "Nworld"),
                    "Hello" + NL + "world")


class AssDrawingSegmentsTest(unittest.TestCase):
    """Madde 22: vektör koordinatları gerçek metne karışmamalı."""

    def test_a_mixed_event_keeps_only_the_words(self):
        value = ("{" + BS + "p1}m 0 0 l 100 0 100 100 0 100{" + BS
                 + "p0}VISIBLE TEXT")
        cleaned = sf._clean_ass_text(sf.strip_ass_drawing_segments(value), 0)
        self.assertEqual(cleaned, "VISIBLE TEXT")

    def test_text_on_both_sides_of_a_drawing_is_joined(self):
        value = "once{" + BS + "p1}m 0 0 l 5 5{" + BS + "p0}sonra"
        cleaned = sf._clean_ass_text(sf.strip_ass_drawing_segments(value), 0)
        self.assertEqual(cleaned, "oncesonra")

    def test_a_pure_drawing_event_is_still_dropped(self):
        rows = _parse_ass(
            events="Dialogue: 0,0:00:01.00,0:00:02.00,Default,,0,0,0,,{"
                   + BS + "p1}m 0 0 l 100 0 100 100 0 100")
        self.assertEqual(rows, [])

    def test_dialogue_that_merely_looks_like_coordinates_survives(self):
        value = "m 0 0 diye bagirdi"
        self.assertEqual(sf.strip_ass_drawing_segments(value), value)


class ForeignTitleNeedsContextTest(unittest.TestCase):
    """Madde 23: `Mr.`/`Miss` her bağlamda unvan değildir."""

    def test_a_real_address_is_still_translated(self):
        self.assertEqual(
            g.normalize_foreign_titles("Mr. Smith, içeri gelin.",
                                       "Mr. Smith, come in.")[0],
            "Bay Smith, içeri gelin.")

    def test_work_and_character_identities_are_preserved(self):
        for value, source in (("Mr. Robot başladı.", "Mr. Robot has started."),
                              ("Miss Fortune geldi.", "Miss Fortune arrived."),
                              ("Mr. Nobody kaçtı.", "Mr. Nobody escaped.")):
            with self.subTest(value=value):
                self.assertEqual(
                    g.normalize_foreign_titles(value, source)[0], value)

    def test_a_locked_term_is_preserved(self):
        self.assertEqual(
            g.normalize_foreign_titles(
                "Mr. Blake geldi.", "Mr. Blake arrived.",
                {"Mr. Blake": "Mr. Blake"})[0],
            "Mr. Blake geldi.")

    def test_a_quoted_source_name_is_preserved(self):
        self.assertEqual(
            g.normalize_foreign_titles(
                "Mr. Blake geldi.", 'I saw "Mr. Blake" last night.')[0],
            "Mr. Blake geldi.")

    def test_the_shouted_form_still_works(self):
        self.assertEqual(
            g.normalize_foreign_titles("MR. YI dedi.", "MR. YI SAID.")[0],
            "BAY YI dedi.")


if __name__ == "__main__":
    unittest.main()
