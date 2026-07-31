"""
subtitle_formats.py için birim testler.

Kapsar:
- SRT parse (normal, boş blok atlama)
- VTT parse (timestamp dönüşümü, cue ID)
- ASS parse (stil filtresi, zaman damgası dönüşümü)
- get_subtitle_files deterministik sıralama
- parse_any uzantı yönlendirmesi
"""
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock


def _write_temp(content: str, suffix: str) -> str:
    tmp = tempfile.NamedTemporaryFile(mode="w", suffix=suffix,
                                      encoding="utf-8", delete=False)
    tmp.write(content)
    tmp.close()
    return tmp.name


class ParseSrtTest(unittest.TestCase):
    def test_basic_srt_parse(self):
        srt = "1\n00:00:01,000 --> 00:00:03,000\nHello world\n\n"
        path = _write_temp(srt, ".srt")
        from subtitle_formats import parse_any
        blocks = parse_any(path)
        self.assertEqual(len(blocks), 1)
        idx, ts, text = blocks[0]
        self.assertEqual(idx, "1")
        self.assertIn("-->", ts)
        self.assertEqual(text, "Hello world")
        os.unlink(path)

    def test_multi_block_srt(self):
        srt = (
            "1\n00:00:01,000 --> 00:00:02,000\nFirst\n\n"
            "2\n00:00:03,000 --> 00:00:04,000\nSecond\n\n"
        )
        path = _write_temp(srt, ".srt")
        from subtitle_formats import parse_any
        blocks = parse_any(path)
        self.assertEqual(len(blocks), 2)
        os.unlink(path)

    def test_short_block_skipped(self):
        srt = "1\n00:00:01,000 --> 00:00:02,000\n"  # metin yok
        path = _write_temp(srt, ".srt")
        from subtitle_formats import parse_any
        blocks = parse_any(path)
        self.assertEqual(len(blocks), 0)
        os.unlink(path)


class ParseVttTest(unittest.TestCase):
    def test_malformed_visual_format_tags_are_removed_from_translation_input(self):
        from subtitle_formats import clean_translation_source_text

        source = "< i>Hello</ i>\n< b >World</ b >\n2 < 3"
        self.assertEqual(
            clean_translation_source_text(source),
            "Hello\nWorld\n2 < 3",
        )

    def test_basic_vtt_parse(self):
        vtt = "WEBVTT\n\n1\n00:00:01.000 --> 00:00:03.000\nSubtitle text\n\n"
        path = _write_temp(vtt, ".vtt")
        from subtitle_formats import parse_any
        blocks = parse_any(path)
        self.assertEqual(len(blocks), 1)
        _, ts, text = blocks[0]
        self.assertIn("-->", ts)
        self.assertEqual(text, "Subtitle text")
        os.unlink(path)

    def test_vtt_timestamp_converted_to_srt_format(self):
        vtt = "WEBVTT\n\n00:00:01.500 --> 00:00:03.250\nLine\n\n"
        path = _write_temp(vtt, ".vtt")
        from subtitle_formats import parse_any
        blocks = parse_any(path)
        _, ts, _ = blocks[0]
        # VTT nokta → SRT virgül
        self.assertIn(",", ts)
        os.unlink(path)

    def test_vtt_inline_tags_preserved_for_restoration(self):
        vtt = "WEBVTT\n\n1\n00:00:01.000 --> 00:00:02.000\n<b>Bold text</b>\n\n"
        path = _write_temp(vtt, ".vtt")
        from subtitle_formats import parse_any, _clean_vtt_text, restore_format_tags
        blocks = parse_any(path)
        _, _, text = blocks[0]
        self.assertIn("<b>", text)
        self.assertIn("Bold", text)
        self.assertEqual(_clean_vtt_text(text), "Bold text")
        self.assertEqual(restore_format_tags(text, "Kalın metin"), "<b>Kalın metin</b>")
        os.unlink(path)

    def test_vtt_math_angle_brackets_preserved(self):
        vtt = "WEBVTT\n\n00:00:01.000 --> 00:00:02.000\n2 < 3 and 5 > 4\n"
        path = _write_temp(vtt, ".vtt")
        from subtitle_formats import parse_any
        blocks = parse_any(path)
        self.assertEqual(blocks[0][2], "2 < 3 and 5 > 4")
        os.unlink(path)

    def test_vtt_comma_timestamps_without_blank_lines_are_separate_cues(self):
        vtt = (
            "WEBVTT\n"
            "1:23,456 --> 1:24,000\nFirst\n"
            "00:01:25,000 --> 00:01:26,000\nSecond\n"
        )
        path = _write_temp(vtt, ".vtt")
        from subtitle_formats import parse_any
        blocks = parse_any(path)
        self.assertEqual([(b[1], b[2]) for b in blocks], [
            ("00:01:23,456 --> 00:01:24,000", "First"),
            ("00:01:25,000 --> 00:01:26,000", "Second"),
        ])
        os.unlink(path)


class ParseAssTest(unittest.TestCase):
    # parse_ass ilk Format: satırını Events kolonları olarak alır;
    # [V4+ Styles] kısmını dahil etmiyoruz (kendi Format satırı çakışırdı).
    _HEADER = (
        "[Script Info]\nScriptType: v4.00+\n\n"
        "[Events]\n"
        "Format: Layer, Start, End, Style, Actor, MarginL, MarginR, MarginV, Effect, Text\n"
    )

    def test_basic_ass_parse(self):
        content = (
            self._HEADER +
            "Dialogue: 0,0:00:01.00,0:00:03.00,Default,,0,0,0,,Hello world\n"
        )
        path = _write_temp(content, ".ass")
        from subtitle_formats import parse_any
        blocks = parse_any(path)
        self.assertEqual(len(blocks), 1)
        _, ts, text = blocks[0]
        self.assertEqual(text, "Hello world")
        self.assertIn("-->", ts)
        os.unlink(path)

    def test_ass_casing_and_spaces_dialogue(self):
        content = (
            self._HEADER +
            " dialogue: 0,0:00:01.00,0:00:03.00,Default,,0,0,0,,Robustness test\n"
        )
        path = _write_temp(content, ".ass")
        from subtitle_formats import parse_any
        blocks = parse_any(path)
        self.assertEqual(len(blocks), 1)
        _, _, text = blocks[0]
        self.assertEqual(text, "Robustness test")
        os.unlink(path)

    def test_ass_two_digit_hour_parsed(self):
        """10+ saatlik içerik: (\d) yerine (\d{1,2}) gerekir."""
        content = (
            self._HEADER +
            "Dialogue: 0,10:00:01.00,10:00:03.00,Default,,0,0,0,,Long content\n"
        )
        path = _write_temp(content, ".ass")
        from subtitle_formats import parse_any
        blocks = parse_any(path)
        self.assertEqual(len(blocks), 1)
        _, ts, text = blocks[0]
        self.assertIn("10:", ts)
        self.assertEqual(text, "Long content")
        os.unlink(path)

    def test_ass_override_tags_preserved_for_restoration(self):
        content = (
            self._HEADER +
            r"Dialogue: 0,0:00:01.00,0:00:03.00,Default,,0,0,0,,{\i1}Italic{\i0}" + "\n"
        )
        path = _write_temp(content, ".ass")
        from subtitle_formats import parse_any, _clean_ass_text
        blocks = parse_any(path)
        _, _, text = blocks[0]
        self.assertIn("{\\i1}", text)
        self.assertIn("Italic", text)
        self.assertEqual(_clean_ass_text(text), "Italic")
        os.unlink(path)

    def test_ass_parser_to_restore_keeps_open_and_reset_tags(self):
        content = (
            self._HEADER +
            r"Dialogue: 0,0:00:01.00,0:00:03.00,Default,,0,0,0,,{\i1}Italic{\i0}" + "\n"
        )
        path = _write_temp(content, ".ass")
        from subtitle_formats import parse_any, restore_format_tags
        blocks = parse_any(path)
        self.assertEqual(restore_format_tags(blocks[0][2], "İtalik"),
                         r"{\i1}İtalik{\i0}")
        os.unlink(path)

    def test_ass_single_digit_fraction_and_hard_space(self):
        content = (
            self._HEADER +
            r"Dialogue: 0,0:00:01.5,0:00:03.0,Default,,0,0,0,,Hello\hworld" + "\n"
        )
        path = _write_temp(content, ".ass")
        from subtitle_formats import parse_any
        blocks = parse_any(path)
        self.assertEqual(blocks[0][1], "00:00:01,500 --> 00:00:03,000")
        self.assertEqual(blocks[0][2], "Hello world")
        os.unlink(path)

    def test_ass_sign_style_is_preserved_for_translation(self):
        content = (
            self._HEADER +
            "Dialogue: 0,0:00:01.00,0:00:02.00,sign,,0,0,0,,Sign text\n"
            "Dialogue: 0,0:00:03.00,0:00:04.00,Default,,0,0,0,,Normal text\n"
        )
        path = _write_temp(content, ".ass")
        from subtitle_formats import parse_any
        blocks = parse_any(path)
        texts = [b[2] for b in blocks]
        self.assertIn("Sign text", texts)
        self.assertIn("Normal text", texts)
        os.unlink(path)

    def test_ass_prefers_english_bilingual_lyric_track(self):
        content = (
            self._HEADER +
            "Dialogue: 0,0:00:01.00,0:00:02.00,OP J,,0,0,0,,UMI WA ARETERU\n"
            "Dialogue: 0,0:00:01.00,0:00:02.00,OP E,,0,0,0,,THE SEA IS ROUGH\n"
            "Dialogue: 0,0:00:03.00,0:00:04.00,EDJ,,0,0,0,,Ame no shizuku\n"
            "Dialogue: 0,0:00:03.00,0:00:04.00,EDE,,0,0,0,,Drops of rain\n"
            "Dialogue: 0,0:00:05.00,0:00:06.00,OP J,,0,0,0,,Unpaired romaji\n"
            "Dialogue: 0,0:00:07.00,0:00:08.00,OP,,0,0,0,,Generic opening lyric\n"
            "Dialogue: 0,0:00:09.00,0:00:10.00,Sign,,0,0,0,,Meaningful sign\n"
        )
        path = _write_temp(content, ".ass")
        from subtitle_formats import parse_any
        blocks = parse_any(path)
        texts = [b[2] for b in blocks]
        self.assertNotIn("UMI WA ARETERU", texts)
        self.assertNotIn("Ame no shizuku", texts)
        self.assertIn("THE SEA IS ROUGH", texts)
        self.assertIn("Drops of rain", texts)
        self.assertIn("Unpaired romaji", texts)
        self.assertIn("Generic opening lyric", texts)
        self.assertIn("Meaningful sign", texts)
        os.unlink(path)

    def test_ass_events_format_ignores_brackets_before_custom_columns(self):
        content = (
            "[Script Info]\n\n[Events]\n"
            "; [metadata kept before the format]\n"
            "Format: Start, End, Text, Style\n"
            "Dialogue: 0:00:01.00,0:00:03.00,Hello [there],Default\n"
        )
        path = _write_temp(content, ".ass")
        from subtitle_formats import parse_any
        blocks = parse_any(path)
        self.assertEqual(len(blocks), 1)
        self.assertEqual(blocks[0][2], "Hello [there]")
        os.unlink(path)


class GetSubtitleFilesTest(unittest.TestCase):
    def test_recursive_discovery_walks_tree_once_for_all_formats(self):
        import subtitle_formats
        with tempfile.TemporaryDirectory() as d:
            for name in ("one.srt", "two.vtt", "three.ass", "four.ssa"):
                Path(d, name).write_text("", encoding="utf-8")
            real_walk = subtitle_formats.os.walk
            with mock.patch.object(
                    subtitle_formats.os, "walk", wraps=real_walk) as walk:
                files = subtitle_formats.get_subtitle_files(d, recursive=True)

        self.assertEqual(len(files), 4)
        walk.assert_called_once()

    def test_deterministic_ordering(self):
        """Aynı klasör iki kez tarandığında aynı sıra döner."""
        from subtitle_formats import get_subtitle_files
        with tempfile.TemporaryDirectory() as d:
            for name in ["c.srt", "a.srt", "b.vtt"]:
                Path(d, name).write_text("", encoding="utf-8")

            first  = get_subtitle_files(d, recursive=False)
            second = get_subtitle_files(d, recursive=False)

            self.assertEqual(first, second)

    def test_no_duplicates(self):
        """Aynı dosya sonuç listesinde en fazla bir kez yer alır."""
        from subtitle_formats import get_subtitle_files
        with tempfile.TemporaryDirectory() as d:
            Path(d, "sub.srt").write_text("", encoding="utf-8")

            files = get_subtitle_files(d, recursive=True)

            self.assertEqual(len(files), len(set(files)))

    def test_unknown_extension_excluded(self):
        from subtitle_formats import get_subtitle_files
        with tempfile.TemporaryDirectory() as d:
            Path(d, "video.mp4").write_text("", encoding="utf-8")
            Path(d, "sub.srt").write_text("", encoding="utf-8")

            files = get_subtitle_files(d, recursive=False)

            self.assertTrue(all(f.endswith((".srt", ".vtt", ".ass", ".ssa"))
                                for f in files))

    def test_cikti_subfolder_excluded_from_recursive(self):
        """Kural 1: <girdi>/ÇIKTI içindeki çıktılar yeniden toplanmaz."""
        from subtitle_formats import get_subtitle_files
        with tempfile.TemporaryDirectory() as d:
            Path(d, "kaynak.srt").write_text("", encoding="utf-8")
            outdir = Path(d, "ÇIKTI")
            outdir.mkdir()
            (outdir / "kaynak.srt").write_text("", encoding="utf-8")  # çeviri çıktısı

            files = get_subtitle_files(d, recursive=True)
            names = [Path(f).name for f in files]
            self.assertEqual(names, ["kaynak.srt"])  # yalnız kaynak, ÇIKTI/ hariç
            self.assertFalse(any("ÇIKTI" in Path(f).parts for f in files))

    def test_ham_backup_excluded(self):
        """.ham.srt yedekleri asla girdi olarak toplanmaz."""
        from subtitle_formats import get_subtitle_files
        with tempfile.TemporaryDirectory() as d:
            Path(d, "film.srt").write_text("", encoding="utf-8")
            Path(d, "film.ham.srt").write_text("", encoding="utf-8")  # ham yedek

            files = get_subtitle_files(d, recursive=True)
            names = [Path(f).name for f in files]
            self.assertIn("film.srt", names)
            self.assertNotIn("film.ham.srt", names)

    def test_generated_same_folder_outputs_excluded(self):
        """Aynı klasöre yazılan sonuç/yardımcı dosyalar sonraki taramada kaynak olmaz."""
        from subtitle_formats import get_subtitle_files
        with tempfile.TemporaryDirectory() as d:
            kept = ("film.srt", "film.trailer.srt", "film.stage.srt")
            generated = (
                "film.tr.srt",
                "film.partial.srt",
                "film.postprocess.bak.srt",
                "film.postprocess.2.bak.srt",
                "film.wave1of2.srt",
                "film.wave2of2.srt",
                ".film.srt.batch_abc.stage.srt",
                ".film.srt.twowave.stage.srt",
            )
            for name in kept + generated:
                Path(d, name).write_text("", encoding="utf-8")

            names = [Path(path).name for path in get_subtitle_files(d, recursive=True)]

            self.assertEqual(names, sorted(kept))

    def test_generated_outputs_excluded_in_nonrecursive_scan(self):
        from subtitle_formats import get_subtitle_files
        with tempfile.TemporaryDirectory() as d:
            Path(d, "source.vtt").write_text("", encoding="utf-8")
            Path(d, "source.tr.srt").write_text("", encoding="utf-8")
            Path(d, "source.partial.srt").write_text("", encoding="utf-8")

            names = [Path(path).name for path in get_subtitle_files(d, recursive=False)]

            self.assertEqual(names, ["source.vtt"])

    def test_scanned_dir_itself_named_cikti_still_collected(self):
        """Kural 2: taranan klasörün KENDİSİ ÇIKTI adlıysa içindekiler yine toplanır
        (Downloads/ÇIKTI'yı girdi seçme durumu yanlışlıkla boşalmasın)."""
        from subtitle_formats import get_subtitle_files
        with tempfile.TemporaryDirectory() as d:
            root = Path(d, "ÇIKTI")
            sub = root / "Film"
            sub.mkdir(parents=True)
            (sub / "Film.srt").write_text("", encoding="utf-8")

            files = get_subtitle_files(str(root), recursive=True)
            names = [Path(f).name for f in files]
            self.assertEqual(names, ["Film.srt"])

    def test_cikti_file_named_not_excluded(self):
        """Dizin değil DOSYA adı 'ÇIKTI.srt' ise dışlanmaz (yalnız dizin bileşeni sayılır)."""
        from subtitle_formats import get_subtitle_files
        with tempfile.TemporaryDirectory() as d:
            Path(d, "ÇIKTI.srt").write_text("", encoding="utf-8")
            files = get_subtitle_files(d, recursive=False)
            self.assertEqual([Path(f).name for f in files], ["ÇIKTI.srt"])


class ParseSrtEdgeCasesTest(unittest.TestCase):
    def test_semicolon_timestamp_separators_reach_hybrid_parser(self):
        srt = (
            "1\n00;02;32,000 --> 00;02;38,000\nFirst\n\n"
            "2\n00:02:39,000 --> 00:02:41,000\nSecond\n"
        )
        path = _write_temp(srt, ".srt")
        import hybrid_translate as ht
        cues = ht.load_srt(path)
        self.assertEqual(len(cues), 2)
        self.assertEqual(cues[0].start, "00:02:32,000")
        self.assertEqual(cues[0].end, "00:02:38,000")
        os.unlink(path)

    def test_duplicate_cue_numbers_not_overwritten(self):
        srt = "1\n00:00:01,000 --> 00:00:02,000\nFirst\n\n1\n00:00:03,000 --> 00:00:04,000\nSecond\n"
        path = _write_temp(srt, ".srt")
        import subtitle_translator_gui as gui
        blocks = gui.parse_srt(path)
        self.assertEqual(len(blocks), 2)
        self.assertEqual([b[0] for b in blocks], ["1", "2"])
        raw_map = gui._raw_src_map_from_cues(blocks)
        self.assertEqual(len(raw_map), 2)
        self.assertEqual(raw_map["1"], "First")
        self.assertEqual(raw_map["2"], "Second")
        os.unlink(path)

    def test_invalid_or_empty_cue_headers_handled(self):
        srt = "abc\n00:00:01,000 --> 00:00:02,000\nFirst\n\n00:00:03,000 --> 00:00:04,000\nSecond\n"
        path = _write_temp(srt, ".srt")
        import subtitle_translator_gui as gui
        blocks = gui.parse_srt(path)
        self.assertEqual(len(blocks), 2)
        self.assertEqual([b[0] for b in blocks], ["1", "2"])
        os.unlink(path)

    def test_gap_cue_numbers_parsed_sequentially(self):
        srt = "1\n00:00:01,000 --> 00:00:02,000\nFirst\n\n3\n00:00:03,000 --> 00:00:04,000\nSecond\n\n7\n00:00:05,000 --> 00:00:06,000\nThird\n"
        path = _write_temp(srt, ".srt")
        import subtitle_translator_gui as gui
        blocks = gui.parse_srt(path)
        self.assertEqual(len(blocks), 3)
        self.assertEqual([b[0] for b in blocks], ["1", "3", "7"])
        os.unlink(path)

    def test_localizer_srt_duplicate_handling(self):
        srt = "1\n00:00:01,000 --> 00:00:02,000\nFirst\n\n1\n00:00:03,000 --> 00:00:04,000\nSecond\n"
        import subtitle_localizer.srt as localizer_srt
        cues = localizer_srt.parse_srt(srt)
        self.assertEqual(len(cues), 2)
        self.assertEqual([c.index for c in cues], [1, 2])

    def test_localizer_preserves_unique_increasing_gaps(self):
        srt = "1\n00:00:01,000 --> 00:00:02,000\nFirst\n\n3\n00:00:03,000 --> 00:00:04,000\nSecond\n"
        import subtitle_localizer.srt as localizer_srt
        cues = localizer_srt.parse_srt(srt)
        self.assertEqual([c.index for c in cues], [1, 3])

    def test_gui_and_localizer_preserve_internal_leading_spaces_equally(self):
        srt = (
            "1\n00:00:01,000 --> 00:00:02,000\n"
            "First line\n  indented continuation\n"
        )
        path = _write_temp(srt, ".srt")
        import subtitle_localizer.srt as localizer_srt
        import subtitle_translator_gui as gui
        try:
            gui_blocks = gui.parse_srt(path)
            localizer_blocks = localizer_srt.parse_srt(srt)
        finally:
            os.unlink(path)

        self.assertEqual(gui_blocks[0][2], localizer_blocks[0].text)
        self.assertIn("\n  indented", gui_blocks[0][2])

    def test_hybrid_srt_recovers_missing_separator_between_cues(self):
        srt = (
            "1\n00:00:01,000 --> 00:00:02,000\nFirst\n"
            "2\n00:00:03,000 --> 00:00:04,000\nSecond\n"
        )
        path = _write_temp(srt, ".srt")
        import hybrid_translate as ht
        try:
            cues = ht.load_srt(path)
            self.assertEqual([(c.index, c.text) for c in cues], [(1, "First"), (2, "Second")])
        finally:
            os.unlink(path)

    def test_hybrid_srt_recovers_body_after_blank_line(self):
        srt = (
            "1\n00:00:01,000 --> 00:00:02,000\n\nReal dialogue.\n\n"
            "2\n00:00:03,000 --> 00:00:04,000\nSecond.\n"
        )
        path = _write_temp(srt, ".srt")
        import hybrid_translate as ht
        try:
            cues = ht.load_srt(path)
            self.assertEqual([(c.index, c.text) for c in cues],
                             [(1, "Real dialogue."), (2, "Second.")])
        finally:
            os.unlink(path)

    def test_hybrid_srt_accepts_three_digit_hours(self):
        path = _write_temp(
            "1\n100:00:01,000 --> 100:00:02,000\nCentury line\n", ".srt")
        import hybrid_translate as ht
        try:
            cues = ht.load_srt(path)
            self.assertEqual([(c.start, c.end, c.text) for c in cues], [
                ("100:00:01,000", "100:00:02,000", "Century line")])
        finally:
            os.unlink(path)


if __name__ == "__main__":
    unittest.main()
