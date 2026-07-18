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

    def test_vtt_inline_tags_stripped(self):
        vtt = "WEBVTT\n\n1\n00:00:01.000 --> 00:00:02.000\n<b>Bold</b> text\n\n"
        path = _write_temp(vtt, ".vtt")
        from subtitle_formats import parse_any
        blocks = parse_any(path)
        _, _, text = blocks[0]
        self.assertNotIn("<b>", text)
        self.assertIn("Bold", text)
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

    def test_ass_override_tags_removed(self):
        content = (
            self._HEADER +
            r"Dialogue: 0,0:00:01.00,0:00:03.00,Default,,0,0,0,,{\i1}Italic{\i0}" + "\n"
        )
        path = _write_temp(content, ".ass")
        from subtitle_formats import parse_any
        blocks = parse_any(path)
        _, _, text = blocks[0]
        self.assertNotIn("{", text)
        self.assertIn("Italic", text)
        os.unlink(path)

    def test_ass_sign_style_skipped(self):
        content = (
            self._HEADER +
            "Dialogue: 0,0:00:01.00,0:00:02.00,sign,,0,0,0,,Sign text\n"
            "Dialogue: 0,0:00:03.00,0:00:04.00,Default,,0,0,0,,Normal text\n"
        )
        path = _write_temp(content, ".ass")
        from subtitle_formats import parse_any
        blocks = parse_any(path)
        texts = [b[2] for b in blocks]
        self.assertNotIn("Sign text", texts)
        self.assertIn("Normal text", texts)
        os.unlink(path)


class GetSubtitleFilesTest(unittest.TestCase):
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


if __name__ == "__main__":
    unittest.main()
