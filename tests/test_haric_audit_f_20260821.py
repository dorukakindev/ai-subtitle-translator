# -*- coding: utf-8 -*-
"""HARIC_YENI_BUG_DENETIMI_2026-08-21.md — madde 7, 8, 12."""
import os
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import subtitle_translator_gui as g

NL = chr(10)
SOURCE_BODY = "1" + NL + "00:00:01,000 --> 00:00:02,000" + NL + "Hello." + NL + NL
TARGET_BODY = "1" + NL + "00:00:01,000 --> 00:00:02,000" + NL + "Merhaba." + NL + NL


class RenamedOutputKeepsProvenanceTest(unittest.TestCase):
    """Madde 7: yeniden adlandırılan final içerik hash'iyle bulunmalı."""

    def _setup(self):
        folder = Path(tempfile.mkdtemp())
        reports = folder / "Raporlar"
        reports.mkdir()
        source = folder / "kaynak.srt"
        source.write_text(SOURCE_BODY, encoding="utf-8")
        output = folder / "Original Release.srt"
        output.write_text(TARGET_BODY, encoding="utf-8")
        g._write_output_source_fingerprint(
            reports, output, g._file_content_sha256(source))
        return reports, source, output

    def test_the_original_name_still_matches(self):
        reports, source, output = self._setup()
        self.assertTrue(g._output_matches_source_fingerprint(
            reports, output, source, verify_output=True))

    def test_a_renamed_output_is_still_recognised(self):
        reports, source, output = self._setup()
        renamed = output.with_name("Film (1986).srt")
        output.rename(renamed)
        self.assertTrue(g._output_matches_source_fingerprint(
            reports, renamed, source, verify_output=True))

    def test_edited_content_is_still_rejected(self):
        reports, source, output = self._setup()
        renamed = output.with_name("Film (1986).srt")
        output.rename(renamed)
        renamed.write_text("BOZULDU", encoding="utf-8")
        self.assertFalse(g._output_matches_source_fingerprint(
            reports, renamed, source, verify_output=True))


class UploadReadyMarkerTest(unittest.TestCase):
    """Madde 8: teslim klasörüne açık `YÜKLEMEYE HAZIR.txt`."""

    def _run_record(self):
        folder = Path(tempfile.mkdtemp())
        output_dir = folder / "out"
        reports = Path(g._resolve_report_dir(str(folder), str(output_dir)))
        reports.mkdir(parents=True, exist_ok=True)
        files = {}
        outputs = {}
        for name, status in (("DoneFilm", "done"), ("ReviewFilm", "review")):
            target_folder = output_dir / name
            target_folder.mkdir(parents=True, exist_ok=True)
            source = folder / (name + ".en.srt")
            source.write_text(SOURCE_BODY, encoding="utf-8")
            output = target_folder / (name + ".srt")
            output.write_text(TARGET_BODY, encoding="utf-8")
            g._write_output_source_fingerprint(
                reports, output, g._file_content_sha256(source))
            files[str(source)] = {"status": status, "output_path": str(output)}
            outputs[name] = output
        record = {
            "run_id": "run:1",
            "ended_at": "2026-08-21T12:00:00",
            "settings": {"input_dir": str(folder), "output_dir": str(output_dir)},
            "files": files,
        }
        return record, outputs

    @staticmethod
    def _marker(output):
        return output.parent / g._UPLOAD_READY_MARKER_NAME

    def test_only_the_done_delivery_gets_the_marker(self):
        record, outputs = self._run_record()
        g._write_upload_ready_markers(record)
        self.assertTrue(self._marker(outputs["DoneFilm"]).is_file())
        self.assertFalse(self._marker(outputs["ReviewFilm"]).is_file())

    def test_the_marker_names_the_run_and_the_file_hash(self):
        record, outputs = self._run_record()
        g._write_upload_ready_markers(record)
        text = self._marker(outputs["DoneFilm"]).read_text(encoding="utf-8")
        self.assertIn("YÜKLEMEYE HAZIR", text)
        self.assertIn("run:1", text)
        self.assertIn("DoneFilm.srt", text)
        self.assertIn(g._file_content_sha256(outputs["DoneFilm"]), text)

    def test_an_edited_delivery_loses_its_marker(self):
        record, outputs = self._run_record()
        g._write_upload_ready_markers(record)
        outputs["DoneFilm"].write_text("BOZULDU", encoding="utf-8")
        g._write_upload_ready_markers(record)
        self.assertFalse(self._marker(outputs["DoneFilm"]).is_file())

    def test_the_source_queue_marker_is_a_separate_contract(self):
        self.assertNotEqual(
            g._UPLOAD_READY_MARKER_NAME, g._COMPLETION_MARKER_NAME)


class FilenameLanguageIsOnlyAHintTest(unittest.TestCase):
    """Madde 12: dosya adı etiketi içerik analizini atlamamalı."""

    @staticmethod
    def _detect(files, detected_language="French"):
        stub = SimpleNamespace(
            _cached_blocks_for=lambda fp: [("1", "", "Bonjour tout le monde")],
            _update_tokens=lambda *args, **kwargs: None,
            _log=lambda *args, **kwargs: None,
        )
        calls = []

        def fake_detect(client, cues, model, log_fn=None, token_callback=None,
                        filename="", cancel_context=None):
            calls.append(filename)
            return detected_language

        with patch.object(g, "detect_source_language_with_ai",
                          side_effect=fake_detect):
            results = g.App._detect_source_languages_parallel(
                stub, object(), files, "gpt-5.4")
        return results, calls

    def test_content_wins_over_a_wrong_filename_label(self):
        results, calls = self._detect(["Actually.French.eng.srt"])
        self.assertEqual(results["Actually.French.eng.srt"], "French")
        self.assertEqual(calls, ["Actually.French.eng.srt"])

    def test_a_single_token_name_is_not_a_language_code(self):
        for name in ("Ara.srt", "Dan.srt", "Fin.srt", "Chi.srt"):
            with self.subTest(name=name):
                self.assertEqual(
                    g.infer_source_language_from_filename(name),
                    g.AUTO_LANGUAGE)

    def test_a_release_style_label_is_still_a_usable_hint(self):
        self.assertEqual(
            g.infer_source_language_from_filename("Movie.1990.eng.srt"),
            "English")

    def test_the_hint_is_used_when_there_is_no_readable_dialogue(self):
        stub = SimpleNamespace(
            _cached_blocks_for=lambda fp: [],
            _update_tokens=lambda *args, **kwargs: None,
            _log=lambda *args, **kwargs: None,
        )
        with patch.object(g, "parse_subtitle", return_value=[]):
            with patch.object(g, "detect_source_language_with_ai",
                              side_effect=AssertionError("çağrılmamalı")):
                results = g.App._detect_source_languages_parallel(
                    stub, object(), ["Movie.1990.eng.srt"], "gpt-5.4")
        self.assertEqual(results["Movie.1990.eng.srt"], "English")


if __name__ == "__main__":
    unittest.main()
