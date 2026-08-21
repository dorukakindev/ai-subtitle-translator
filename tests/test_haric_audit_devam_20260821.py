# -*- coding: utf-8 -*-
"""HARIC_YENI_BUG_DENETIMI_DEVAM_2026-08-21.md — madde 1-6."""
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import subtitle_formats as sf
import subtitle_translator_gui as g
import hybrid_translate as ht

NL = chr(10)
SOURCE_BODY = "1" + NL + "00:00:01,000 --> 00:00:02,000" + NL + "Hello." + NL + NL
TARGET_BODY = "1" + NL + "00:00:01,000 --> 00:00:02,000" + NL + "Merhaba." + NL + NL


class WordSeparatorMarkupTest(unittest.TestCase):
    """Madde 1: <br> ve satır içi VTT damgası sözcükleri birleştirmemeli."""

    def test_line_break_tag_becomes_a_space(self):
        self.assertEqual(
            sf.clean_translation_source_text("Wait<br/>here."), "Wait here.")
        self.assertEqual(
            sf.clean_translation_source_text("Wait<br>here."), "Wait here.")
        self.assertEqual(
            sf.clean_translation_source_text("Wait<BR />here."), "Wait here.")

    def test_inline_vtt_timestamp_between_words_becomes_a_space(self):
        self.assertEqual(
            sf.clean_translation_source_text("Hello<00:00:01.000>world"),
            "Hello world")

    def test_inline_vtt_timestamp_outside_words_is_dropped(self):
        # Sözcük ortasında değilse boşluk EKLENMEZ; aksi hâlde noktalama ve
        # etiket sınırlarında sahte boşluk oluşuyordu.
        self.assertEqual(
            sf.clean_translation_source_text(
                "<v Roger><00:00:01.500>Choose {red} or {blue}.</v>"),
            "<v Roger>Choose {red} or {blue}.</v>")

    def test_word_merge_no_longer_hides_a_real_difference(self):
        # Birleşmiş metin kaynakla aynı görünmesin diye ayrım korunur.
        self.assertNotEqual(
            sf.clean_translation_source_text("Waithere."),
            sf.clean_translation_source_text("Wait<br/>here."))


class LiteralBracesAreNotEmptyTest(unittest.TestCase):
    """Madde 2: süslü parantezli düz metin 'boş hedef' sayılmamalı."""

    def test_plain_braced_text_is_visible_content(self):
        for value in ("{username}", "{red}", "{1,2,3}", "{Merhaba}"):
            with self.subTest(value=value):
                self.assertEqual(sf.translation_failure_reason(value), "")

    def test_braced_words_count_as_wordlike(self):
        # Rakamlar tasarım gereği "sözcük" sayılmaz; harf taşıyanlar sayılır.
        self.assertTrue(sf.has_visible_wordlike_text("{username}"))
        self.assertTrue(sf.has_visible_wordlike_text("{Merhaba}"))
        self.assertFalse(sf.has_visible_wordlike_text(r"{\an8}"))

    def test_ass_override_block_is_still_empty(self):
        for value in (r"{\an8}", r"{\i1}{\pos(10,20)}"):
            with self.subTest(value=value):
                self.assertEqual(
                    sf.translation_failure_reason(value), "bos_hedef")


class NumericEntityValidationTest(unittest.TestCase):
    """Madde 3: geçersiz sayısal varlık kodu çözülmemeli."""

    def test_invalid_codepoints_stay_literal(self):
        for value in ("&#xD800;", "&#55296;", "&#xFFFE;", "&#0;",
                      "&#x110000;"):
            with self.subTest(value=value):
                self.assertEqual(sf.decode_vtt_entities(value), value)

    def test_uppercase_hex_prefix_decodes(self):
        self.assertEqual(sf.decode_vtt_entities("&#X1F600;"), chr(0x1F600))
        self.assertEqual(sf.decode_vtt_entities("&#x1F600;"), chr(0x1F600))

    def test_ordinary_entities_still_decode(self):
        self.assertEqual(sf.decode_vtt_entities("&#65;"), "A")
        self.assertEqual(sf.decode_vtt_entities("&amp;"), "&")


class SubmittedBatchOwnershipTest(unittest.TestCase):
    """Madde 4: gönderilmiş batch kaynak+ayar kimliğine bağlı olmalı."""

    def setUp(self):
        self._state = tempfile.mkdtemp()
        self._patch = patch.dict(
            os.environ, {"SUBTITLE_TRANSLATOR_STATE_DIR": self._state})
        self._patch.start()
        self.addCleanup(self._patch.stop)
        self.folder = Path(tempfile.mkdtemp())

    def _source(self, name, body="Hello."):
        path = self.folder / name
        path.write_text(
            "1" + NL + "00:00:01,000 --> 00:00:02,000" + NL + body + NL + NL,
            encoding="utf-8")
        return str(path)

    def _write_fmap(self, batch_id, source, fingerprint, source_hash):
        ht._batch_id_path().parent.mkdir(parents=True, exist_ok=True)
        ht._batch_id_path().write_text(batch_id + NL, encoding="utf-8")
        ht._batch_fmap_path(batch_id).write_text(json.dumps({
            "type": "hybrid",
            "session_fingerprint": fingerprint,
            "source_path": source,
            "source_hash": source_hash,
            "output_path": source + ".tr.srt",
            "fmap": {"chunk_0": ["1"]},
        }), encoding="utf-8")

    def test_stale_fmap_hash_is_not_relinked(self):
        source = self._source("a.srt")
        old_hash = ht._cache_sig(source).removeprefix("sha256:")
        self._source("a.srt", "Hello, changed.")
        self._write_fmap("batch_old", source, "FP1", old_hash)
        session = ht.create_batch_session(
            str(self.folder), str(self.folder), [source], fingerprint="FP1")
        entry = session["files"][source]
        self.assertEqual(entry["status"], "pending")
        self.assertIsNone(entry.get("batch_id"))

    def test_matching_fmap_hash_is_a_genuine_crash_resume(self):
        source = self._source("b.srt")
        current = ht._cache_sig(source).removeprefix("sha256:")
        self._write_fmap("batch_ok", source, "FP1", current)
        session = ht.create_batch_session(
            str(self.folder), str(self.folder), [source], fingerprint="FP1")
        entry = session["files"][source]
        self.assertEqual(entry["status"], "submitted")
        self.assertEqual(entry["batch_id"], "batch_ok")

    def test_source_edited_after_submit_releases_the_batch(self):
        source = self._source("c.srt")
        current = ht._cache_sig(source).removeprefix("sha256:")
        session = ht.create_batch_session(
            str(self.folder), str(self.folder), [source], fingerprint="FP1")
        session["files"][source].update({
            "status": "submitted", "batch_id": "batch_live",
            "source_hash": current})
        ht._save_batch_session(session)
        self._source("c.srt", "Changed after submit.")
        session = ht.create_batch_session(
            str(self.folder), str(self.folder), [source], fingerprint="FP1")
        entry = session["files"][source]
        self.assertEqual(entry["status"], "pending")
        self.assertIsNone(entry.get("batch_id"))
        # Ödenmiş iş kaybolmasın diye kimliği kayıt altında kalır.
        self.assertEqual(entry.get("orphan_batch_id"), "batch_live")

    def test_settings_change_keeps_the_paid_batch_but_marks_it(self):
        source = self._source("d.srt")
        session = ht.create_batch_session(
            str(self.folder), str(self.folder), [source], fingerprint="OLD")
        session["files"][source].update(
            {"status": "submitted", "batch_id": "batch_paid"})
        ht._save_batch_session(session)
        session = ht.create_batch_session(
            str(self.folder), str(self.folder), [source], fingerprint="NEW")
        entry = session["files"][source]
        # Batch ÖDENMİŞTİR: bağlantı atılmaz…
        self.assertEqual(entry["status"], "submitted")
        self.assertEqual(entry["batch_id"], "batch_paid")
        # …ama sonucun eski ayarlarla üretildiği görünür kalır.
        self.assertTrue(entry.get("settings_fingerprint_changed"))
        self.assertEqual(entry.get("origin_fingerprint"), "OLD")


class EnglishExemptionsNeedEvidenceTest(unittest.TestCase):
    """Madde 5: 'çevrilmemiş' muafiyetleri pozitif özel-ad kanıtı istemeli."""

    ENGLISH_LEAKS = (
        "Fire Exit",
        "Emergency Exit",
        "Danger Ahead",
        "Keep Out",
        "No Entry",
        "Private Property",
        "Freedom Now",
        "Welcome Home",
        "Danger danger",
        "Help Help",
        "Stop Stop",
    )

    def test_ordinary_english_phrases_are_not_proper_names(self):
        for text in self.ENGLISH_LEAKS:
            with self.subTest(text=text):
                self.assertFalse(g._src_is_proper_name_phrase(text))

    def test_real_proper_names_stay_exempt(self):
        for text in ("New York", "John Smith", "Göbekli Tepe",
                     "Baker Street"):
            with self.subTest(text=text):
                self.assertTrue(g._src_is_proper_name_phrase(text))

    def test_evidence_helper_separates_the_two_classes(self):
        self.assertFalse(g._has_non_ordinary_english_token("Fire Exit"))
        self.assertFalse(g._has_non_ordinary_english_token("Danger Ahead"))
        self.assertTrue(g._has_non_ordinary_english_token("New York"))
        self.assertTrue(g._has_non_ordinary_english_token("Kyrie eleison"))

    def test_helper_ignores_text_without_letters(self):
        self.assertFalse(g._has_non_ordinary_english_token("123 — !?"))
        self.assertFalse(g._has_non_ordinary_english_token(""))


class UploadMarkerBlocksIncompleteRunsTest(unittest.TestCase):
    """Madde 6: yolu olmayan hatalı üye ve bitmemiş çalışma işareti bloklamalı."""

    def _record(self, members, run_status="done"):
        # Girdi ve çıktı klasörü aynı olduğunda bütün bölümler TEK bir
        # 'ÇIKTI' klasörüne yazılır — seri teslimlerinin gerçek yerleşimi.
        folder = Path(tempfile.mkdtemp())
        settings = {
            "input_dir": str(folder),
            "output_dir": str(folder),
            "tgt_lang": "Turkish",
        }
        reports = Path(g._resolve_report_dir(str(folder), str(folder)))
        reports.mkdir(parents=True, exist_ok=True)
        files = {}
        target_folder = None
        for name, status, with_output in members:
            source = folder / (name + ".srt")
            source.write_text(SOURCE_BODY, encoding="utf-8")
            output = g._resolve_output_path(
                str(folder), str(folder), str(source),
                same_folder=False, selected_roots=(),
                target_language="Turkish")
            target_folder = output.parent
            if not with_output:
                files[str(source)] = {"status": status, "output_path": ""}
                continue
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_text(TARGET_BODY, encoding="utf-8")
            g._write_output_source_fingerprint(
                reports, output, g._file_content_sha256(source))
            files[str(source)] = {
                "status": status, "output_path": str(output)}
        record = {
            "run_id": "run:devam",
            "status": run_status,
            "ended_at": "2026-08-21T12:00:00",
            "settings": settings,
            "files": files,
        }
        return record, target_folder

    def test_failed_member_without_a_path_blocks_its_folder(self):
        record, _folder = self._record(
            [("Bolum1", "done", True), ("Bolum2", "error", False)])
        ready, stale = g.upload_ready_marker_plan(record)
        self.assertEqual(ready, {})
        self.assertTrue(stale)

    def test_all_members_done_still_write_the_marker(self):
        record, folder = self._record(
            [("Bolum1", "done", True), ("Bolum2", "done", True)])
        ready, stale = g.upload_ready_marker_plan(record)
        self.assertIn(folder, ready)
        self.assertEqual(stale, set())

    def test_unfinished_run_writes_no_marker(self):
        record, _folder = self._record(
            [("Bolum1", "done", True)], run_status="error")
        ready, stale = g.upload_ready_marker_plan(record)
        self.assertEqual(ready, {})
        self.assertTrue(stale)

    def test_intended_folder_is_resolved_for_a_pathless_member(self):
        record, folder = self._record([("Bolum1", "error", False)])
        source = next(iter(record["files"]))
        self.assertEqual(
            g._intended_output_folder(source, record["settings"]), folder)


if __name__ == "__main__":
    unittest.main()
