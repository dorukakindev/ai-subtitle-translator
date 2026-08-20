# -*- coding: utf-8 -*-
"""DERIN_BUG_DENETIMI_2026-08-20.md bulgularının regresyon testleri.

Her sınıf denetim maddesinin KARŞI ÖRNEĞİNİ kilitler; madde numarası
docstring'de verilir.
"""
import io
import json
import os
import sys
import tempfile
import types
import time
import unittest
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import hybrid_translate as ht
import sdh_cleaner
import subtitle_formats
import subtitle_translator_gui as g


class _Var:
    """Basit tk değişkeni taklidi (Tk gerektirmez)."""

    def __init__(self, value=""):
        self._value = value

    def get(self):
        return self._value

    def set(self, value):
        self._value = value

class _Cue:
    def __init__(self, index, timestamp, text):
        self.index, self.timestamp, self.text = index, timestamp, text
        self.start, self.end = [part.strip() for part in timestamp.split("-->")]


def _delivered(blocks, cues, target="Turkish"):
    rows = g._prepare_upload_ready_blocks(blocks, target, None, source_cues=cues)
    return [(idx, text) for idx, _ts, text in rows
            if "discord" not in str(text)]


class CueFillNeedsSourceContinuationTest(unittest.TestCase):
    """Madde 1: taşıma yalnız aynı kaynak cümlesinin devamında yapılmalı."""

    def test_independent_source_sentences_are_not_merged(self):
        pair = [("1", "00:00:01,000 --> 00:00:08,000", "Eve gittim"),
                ("2", "00:00:08,000 --> 00:00:08,400",
                 "Yangın çıktı hemen kaçmalıyız buradan derhal şimdi")]
        moved, count = g.rebalance_cue_fill_pairs(
            pair, {"1": "I left.", "2": "Fire!"})
        self.assertEqual(count, 0)
        self.assertEqual(moved, pair)

    def test_source_continuation_still_moves(self):
        pair = [("368", "00:30:00,000 --> 00:30:07,000", "Cümlenin ilk yarısı"),
                ("369", "00:30:07,000 --> 00:30:07,400",
                 "yani bu ikinci parça çok kısa bir cue içine "
                 "sıkıştırılmış durumda ve okunamaz.")]
        source = {"368": "A fairly long English narration sentence with room",
                  "369": "elements."}
        _moved, count = g.rebalance_cue_fill_pairs(pair, source)
        self.assertEqual(count, 1)

    def test_capitalised_continuation_is_a_new_sentence(self):
        pair = [("1", "00:00:01,000 --> 00:00:08,000", "Bir şeyler anlatıyor"),
                ("2", "00:00:08,000 --> 00:00:08,400",
                 "sonra bambaşka bir konuya geçti ve uzun uzun konuştu.")]
        _moved, count = g.rebalance_cue_fill_pairs(
            pair, {"1": "He was talking", "2": "Then everything changed"})
        self.assertEqual(count, 0)

    def test_missing_source_blocks_the_move(self):
        pair = [("1", "00:00:01,000 --> 00:00:08,000", "Bir şeyler anlatıyor"),
                ("2", "00:00:08,000 --> 00:00:08,400",
                 "sonra bambaşka bir konuya geçti ve uzun uzun konuştu.")]
        _moved, count = g.rebalance_cue_fill_pairs(pair, {})
        self.assertEqual(count, 0)


class CondenseSpeakerAndContentTest(unittest.TestCase):
    """Madde 2 ve 30: condense konuşmacı ve içerik kaybetmemeli."""

    def test_two_speakers_are_never_merged(self):
        ok, reason = ht.validate_condense_candidate(
            "- Merhaba\n- Nasılsın?", "- Merhaba, nasılsın?",
            "- Hello\n- How are you?", tgt_lang="Turkish")
        self.assertFalse(ok)
        self.assertEqual(reason, "speaker_merge")

    def test_two_speakers_kept_is_accepted(self):
        ok, _reason = ht.validate_condense_candidate(
            "- Merhaba dostum nasılsın\n- İyiyim teşekkür ederim",
            "- Merhaba nasılsın\n- İyiyim sağ ol",
            "- Hello friend how are you\n- I am fine thanks",
            tgt_lang="Turkish")
        self.assertTrue(ok)

    def test_dropping_the_object_is_content_loss(self):
        ok, reason = ht.validate_condense_candidate(
            "Maria kırmızı tren biletini kaçırdı.", "Maria kaçırdı.",
            "Maria missed the red train ticket.", tgt_lang="Turkish")
        self.assertFalse(ok)
        self.assertEqual(reason, "content_loss")

    def test_sourceless_shortening_keeps_its_freedom(self):
        ok, _reason = ht.validate_condense_candidate(
            "Bu çok uzun bir cümle, birçok gereksiz kelimeyle dolu.",
            "Uzun bir cümle burada.")
        self.assertTrue(ok)


class SharedTimestampDeletionTest(unittest.TestCase):
    """Madde 5: aynı zamanı paylaşan kredi gerçek diyaloğu silmemeli."""

    TS = "00:00:01,000 --> 00:00:02,000"

    def test_dialogue_survives_a_credit_at_the_same_timestamp(self):
        cues = [_Cue(1, self.TS, "Subtitles by Example"),
                _Cue(2, self.TS, "Hello.")]
        blocks = [("1", self.TS, "Altyazı: Example"), ("2", self.TS, "Merhaba.")]
        self.assertEqual(_delivered(blocks, cues), [("2", "Merhaba.")])

    def test_a_lone_credit_is_still_removed(self):
        cues = [_Cue(1, self.TS, "Subtitles by Example")]
        blocks = [("1", self.TS, "Altyazı: Example")]
        self.assertEqual(_delivered(blocks, cues), [])


class NarrativeScreenCardTest(unittest.TestCase):
    """Madde 6: büyük harfli ekran kartları SDH değildir."""

    def test_place_date_and_film_cards_are_kept(self):
        for card in ("BERLIN 1961", "PARIS, 1943", "THE END", "ACT I",
                     "ACT III", "PART TWO", "CHAPTER ONE", "1975",
                     "TO BE CONTINUED"):
            with self.subTest(card=card):
                self.assertFalse(sdh_cleaner.is_structural_sdh_label(card))

    def test_sound_labels_are_still_structural_sdh(self):
        for label in ("APPLAUSE", "LAUGHTER", "MUSIC PLAYING", "GUNSHOT",
                      "DOOR SLAMS", "АПЛОДИСМЕНТЫ", "ВОЙ СИРЕНЫ"):
            with self.subTest(label=label):
                self.assertTrue(sdh_cleaner.is_structural_sdh_label(label))


class OwnerMismatchIsHardErrorTest(unittest.TestCase):
    """Madde 8: cue sahiplik kayması teslimi durdurmalı."""

    def test_owner_mismatch_blocks_the_ready_marker(self):
        self.assertTrue(g._delivery_audit_has_hard_error(
            {"status": "review", "delivery_owner_mismatch_ids": ["1"]}))

    def test_clean_audit_is_still_accepted(self):
        self.assertFalse(g._delivery_audit_has_hard_error(
            {"status": "ok", "delivery_owner_mismatch_ids": []}))


class SdhLookingTargetOverRealDialogueTest(unittest.TestCase):
    """Madde 14: kaynak diyalogsa SDH-benzeri hedef silinmemeli."""

    TS = "00:00:01,000 --> 00:00:03,000"

    def test_broken_translation_is_marked_not_deleted(self):
        delivered = _delivered([("1", self.TS, "[MÜZİK]")],
                               [_Cue(1, self.TS, "Hello.")])
        self.assertEqual(delivered, [("1", "[ÇEVİRİ EKSİK]")])

    def test_real_sdh_source_is_still_dropped(self):
        delivered = _delivered([("1", self.TS, "[MÜZİK]")],
                               [_Cue(1, self.TS, "[MUSIC PLAYING]")])
        self.assertEqual(delivered, [])


class DeliverySignatureBoundsTest(unittest.TestCase):
    """Madde 44 ve 45: imza aralıkları geçerli ve çakışmasız olmalı."""

    def _signatures(self, rows):
        cues = [_Cue(idx, ts, "Line %s." % idx) for idx, ts, _t in rows]
        out = g._prepare_upload_ready_blocks(rows, "Turkish", None,
                                             source_cues=cues)
        return [g._srt_timestamp_bounds(ts) for _idx, ts, text in out
                if "discord" in str(text)]

    def test_no_signature_has_zero_or_reversed_duration(self):
        for start in ("00:00:00,000", "00:00:00,001", "00:00:00,002",
                      "00:00:05,000"):
            rows = [("1", f"{start} --> 00:00:08,000", "Merhaba dünya.")]
            with self.subTest(start=start):
                for begin, end in self._signatures(rows):
                    self.assertLess(begin, end)

    def test_signatures_do_not_overlap_each_other(self):
        rows = [("1", "00:00:10,000 --> 00:00:12,000", "Üçüncü cümle."),
                ("2", "00:00:01,000 --> 00:00:03,000", "Birinci cümle."),
                ("3", "00:00:05,000 --> 00:00:07,000", "İkinci cümle.")]
        spans = self._signatures(rows)
        self.assertEqual(len(spans), 3)
        for i in range(len(spans)):
            for j in range(i + 1, len(spans)):
                with self.subTest(pair=(i, j)):
                    self.assertFalse(
                        spans[i][1] > spans[j][0] and spans[j][1] > spans[i][0])


class NonLatinIdentityLockTest(unittest.TestCase):
    """Madde 4: Latin dışı sözcük kimlikle kilitlenmemeli."""

    GREEK = ("Η Ελλάδα είναι όμορφη. Οι Έλληνες ζουν στην Ελλάδα. "
             "Η Γερμανία και η Ελλάδα. Ο Πλάτωνα έγραψε. "
             "Ο Πλάτωνα ήταν σοφός. Διαβάσαμε τον Πλάτωνα ξανά.")

    def test_greek_words_are_not_locked(self):
        rejected = {}
        locked = g.auto_locked_proper_nouns(self.GREEK, rejected_out=rejected)
        self.assertEqual(locked, {})
        self.assertIn("Ελλάδα", rejected)

    def test_latin_names_still_lock(self):
        source = ("Louis Barthou arrived in Marseille. The king met Barthou "
                  "there. Later Barthou was shot. Everyone mourned Barthou.")
        self.assertEqual(
            g.auto_locked_proper_nouns(source).get("Barthou"), "Barthou")


class ResumeKeepsWritePolicyTest(unittest.TestCase):
    """Madde 11: yazma politikası alanları run record/resume kapsamında."""

    def test_all_three_keys_are_in_every_scalar_key_list(self):
        import re
        source = io.open(
            os.path.join(os.path.dirname(os.path.dirname(
                os.path.abspath(__file__))), "subtitle_translator_gui.py"),
            encoding="utf-8").read()
        lists = re.findall(r"scalar_keys\s*=\s*\((.*?)\n\s*\)", source, re.S)
        self.assertGreaterEqual(len(lists), 2)
        for index, body in enumerate(lists):
            for key in ("term_normalize_apply", "cue_fill_move",
                        "quality_report_only"):
                with self.subTest(list_index=index, key=key):
                    self.assertIn(key, body)


class ShortCjkEncodingTest(unittest.TestCase):
    """Madde 22: 80 bayttan kısa CJK dosyalar kayıpsız okunmalı."""

    def _roundtrip(self, encoding, body):
        directory = tempfile.mkdtemp()
        path = os.path.join(directory, "short.srt")
        payload = "1\n00:00:01,000 --> 00:00:03,000\n" + body + "\n"
        with io.open(path, "wb") as handle:
            handle.write(payload.encode(encoding))
        return subtitle_formats.read_subtitle_text(path)

    def test_japanese_and_chinese_short_files(self):
        for encoding, body in (("cp932", "はい"), ("cp932", "こんにちは世界"),
                               ("gbk", "是"), ("gbk", "你好世界")):
            with self.subTest(encoding=encoding, body=body):
                self.assertIn(body, self._roundtrip(encoding, body))

    def test_single_byte_encodings_are_not_stolen_by_cjk(self):
        for encoding, body in (("cp1254", "Merhaba dünya"),
                               ("cp1251", "Привет мир"),
                               ("cp1253", "Γεια σου"),
                               ("cp1256", "مرحبا")):
            with self.subTest(encoding=encoding):
                self.assertIn(body, self._roundtrip(encoding, body))


class AssStyleSkipTest(unittest.TestCase):
    """Madde 23: 'Note'/'Credit' stili tek başına silme gerekçesi değil."""

    ASS = ("[Events]\n"
           "Format: Layer, Start, End, Style, Name, MarginL, MarginR, "
           "MarginV, Effect, Text\n"
           "Dialogue: 0,0:00:01.00,0:00:03.00,Note,,0,0,0,,"
           "This sentence is spoken aloud.\n"
           "Dialogue: 0,0:00:04.00,0:00:06.00,Credit,,0,0,0,,"
           "Translated by Fansub Group\n"
           "Dialogue: 0,0:00:07.00,0:00:09.00,Default,,0,0,0,,Normal line.\n"
           "Dialogue: 0,0:00:10.00,0:00:12.00,Note,,0,0,0,,TL note\n")

    def test_spoken_line_in_a_note_style_is_kept(self):
        path = os.path.join(tempfile.mkdtemp(), "t.ass")
        with io.open(path, "w", encoding="utf-8") as handle:
            handle.write(self.ASS)
        texts = [text for _idx, _ts, text in subtitle_formats.parse_ass(path)]
        self.assertIn("This sentence is spoken aloud.", texts)
        self.assertIn("Normal line.", texts)
        self.assertNotIn("Translated by Fansub Group", texts)
        self.assertNotIn("TL note", texts)


class PostprocessSourceResolverTest(unittest.TestCase):
    """Madde 39, 41, 42: kaynak çözümleyicisi."""

    def _fixture(self):
        directory = Path(tempfile.mkdtemp())
        (directory / "Raporlar").mkdir()
        source = directory / "Source.srt"
        output = directory / "Movie.srt"
        source.write_text("1\n00:00:01,000 --> 00:00:02,000\nHello.\n",
                          encoding="utf-8")
        output.write_text("1\n00:00:01,000 --> 00:00:02,000\nMerhaba.\n",
                          encoding="utf-8")
        return directory, source, output

    def test_malformed_newer_report_does_not_hide_the_older_one(self):
        directory, source, output = self._fixture()
        (directory / "Raporlar" / "ceviri_raporu_older.json").write_text(
            json.dumps({"files": [{"output_path": str(output),
                                   "source_path": str(source)}]}),
            encoding="utf-8")
        time.sleep(0.02)
        (directory / "Raporlar" / "ceviri_raporu_newer.json").write_text(
            "[]", encoding="utf-8")
        self.assertEqual(g._resolve_postprocess_source(output), source)

    def test_manual_report_uses_delivery_source_path(self):
        directory, source, output = self._fixture()
        (directory / "Raporlar" / "ceviri_raporu.json").write_text(
            json.dumps({"files": [{"output_path": str(output),
                                   "source_path": str(output),
                                   "delivery_source_path": str(source)}]}),
            encoding="utf-8")
        self.assertEqual(g._resolve_postprocess_source(output), source)

    def test_source_equal_to_output_is_rejected(self):
        directory, _source, output = self._fixture()
        (directory / "Raporlar" / "ceviri_raporu.json").write_text(
            json.dumps({"files": [{"output_path": str(output),
                                   "source_path": str(output)}]}),
            encoding="utf-8")
        self.assertIsNone(g._resolve_postprocess_source(output))

    def test_archived_source_is_used_when_the_original_is_gone(self):
        directory, source, output = self._fixture()
        (directory / "Raporlar" / "ceviri_raporu.json").write_text(
            json.dumps({"files": [{"output_path": str(output),
                                   "source_path": str(source)}]}),
            encoding="utf-8")
        archive = directory / "Raporlar" / "Kaynak"
        archive.mkdir()
        (archive / "Source.srt").write_text(
            source.read_text(encoding="utf-8"), encoding="utf-8")
        source.unlink()
        self.assertEqual(g._resolve_postprocess_source(output),
                         archive / "Source.srt")

class QualityRowSchemaTest(unittest.TestCase):
    """Madde 33, 34, 46: `[null]` cevabı incelenmiş sayılmamalı."""

    def test_null_row_is_rejected(self):
        self.assertFalse(ht._quality_rows_schema_valid([None]))
        self.assertFalse(ht._quality_rows_schema_valid([{"id": "1"}, None]))

    def test_empty_list_is_a_legitimate_no_change_answer(self):
        self.assertTrue(ht._quality_rows_schema_valid([]))

    def test_object_rows_are_accepted(self):
        self.assertTrue(ht._quality_rows_schema_valid([{"id": "1"}]))

    def test_non_list_payloads_are_rejected(self):
        for payload in (None, "metin", {"issues": []}, 3):
            with self.subTest(payload=payload):
                self.assertFalse(ht._quality_rows_schema_valid(payload))

    def test_every_list_pass_consults_the_guard(self):
        source = io.open(
            os.path.join(os.path.dirname(os.path.dirname(
                os.path.abspath(__file__))), "hybrid_translate.py"),
            encoding="utf-8").read()
        # Native, Condense, Critic, QC, Nihai Anlam
        self.assertGreaterEqual(source.count("_quality_rows_schema_valid("), 5)

class PartialPromotionProvenanceTest(unittest.TestCase):
    """Madde 15, 43, 48: kısmi terfi kaynak kanıtına bağlı olmalı."""

    def _fixture(self, partial_text, source_text, legacy_broken=False):
        directory = Path(tempfile.mkdtemp())
        reports = directory / "Raporlar"
        reports.mkdir()
        source = directory / "s.srt"
        output = directory / "out.srt"
        source.write_text(
            "1\n00:00:01,000 --> 00:00:03,000\n%s\n" % source_text,
            encoding="utf-8")
        if legacy_broken:
            (reports / "Kurtarma").mkdir()
            broken = reports / "Kurtarma" / "out.partial.srt"
            broken.write_text(
                "1\n00:00:01,000 --> 00:00:03,000\n[HATA]\n", encoding="utf-8")
            g._write_output_source_fingerprint(
                reports, broken, g._file_content_sha256(source),
                source_path=source)
        partial = directory / "out.partial.srt"
        partial.write_text(
            "1\n00:00:01,000 --> 00:00:03,000\n%s\n" % partial_text,
            encoding="utf-8")
        return directory, source, output, reports, partial

    def test_partial_of_a_different_source_is_never_promoted(self):
        directory, source, output, reports, partial = self._fixture(
            "Kahveyi severim.", "I like tea.")
        other = directory / "other.srt"
        other.write_text("1\n00:00:01,000 --> 00:00:03,000\nI like coffee.\n",
                         encoding="utf-8")
        g._write_output_source_fingerprint(
            reports, partial, g._file_content_sha256(other), source_path=other)
        promoted = g.promote_complete_partial_outputs(
            [source], [output], "Turkish", report_dir=reports)
        self.assertEqual(promoted, [])
        self.assertFalse(output.exists())

    def test_matching_fingerprint_promotes_and_signs(self):
        _directory, source, output, reports, partial = self._fixture(
            "Çayı severim.", "I like tea.")
        g._write_output_source_fingerprint(
            reports, partial, g._file_content_sha256(source),
            source_path=source)
        promoted = g.promote_complete_partial_outputs(
            [source], [output], "Turkish", report_dir=reports)
        self.assertEqual(len(promoted), 1)
        self.assertTrue(g._output_matches_source_fingerprint(
            reports, output, source))

    def test_legacy_partial_is_recovered_but_not_stamped(self):
        _directory, source, output, reports, _partial = self._fixture(
            "Çayı severim.", "I like tea.")
        promoted = g.promote_complete_partial_outputs(
            [source], [output], "Turkish", report_dir=reports)
        self.assertEqual(len(promoted), 1)
        self.assertTrue(output.exists())
        self.assertFalse(g._output_matches_source_fingerprint(
            reports, output, source))

    def test_broken_first_candidate_does_not_hide_a_healthy_one(self):
        _directory, source, output, reports, _partial = self._fixture(
            "Çayı severim.", "I like tea.", legacy_broken=True)
        promoted = g.promote_complete_partial_outputs(
            [source], [output], "Turkish", report_dir=reports)
        self.assertEqual(len(promoted), 1)
        self.assertTrue(output.exists())

class StandaloneBatchSafetyTest(unittest.TestCase):
    """Madde 9, 16, 24, 25: standalone batch yolu."""

    def test_generated_artifacts_are_not_rediscovered_as_sources(self):
        import subtitle_batch_translate as sb
        directory = Path(tempfile.mkdtemp())
        for name in ("source.srt", "source.tr.srt", "source.ham.srt",
                     "source.partial.srt", ".source.stage.srt", "Movie.srt"):
            (directory / name).write_text(
                "1\n00:00:01,000 --> 00:00:02,000\nx\n", encoding="utf-8")
        (directory / "Raporlar").mkdir()
        (directory / "Raporlar" / "arsiv.srt").write_text(
            "1\n00:00:01,000 --> 00:00:02,000\nx\n", encoding="utf-8")
        found = sorted(Path(path).name for path in sb.discover_source_srt_files(
            str(directory), str(directory / "ÇIKTI")))
        self.assertEqual(found, ["Movie.srt", "source.srt"])

    def test_custom_id_hash_is_wide_enough_to_avoid_collisions(self):
        import hashlib
        seen = {}
        collisions = 0
        for number in range(50000):
            path = f"C:/x/{'a' * (number % 40)}/dir{number}/Episode.srt"
            key = hashlib.sha256(path.encode()).hexdigest()[:16]
            if key in seen:
                collisions += 1
            seen[key] = path
        self.assertEqual(collisions, 0)

    def test_empty_response_becomes_a_failure_and_a_partial_file(self):
        import subtitle_batch_translate as sb
        from unittest.mock import MagicMock, patch
        directory = Path(tempfile.mkdtemp())
        source = directory / "source.srt"
        source.write_text("1\n00:00:01,000 --> 00:00:03,000\nHello there.\n",
                          encoding="utf-8")
        output = directory / "out"
        output.mkdir()
        file_map = {"a": (str(source), 0, "1",
                          "00:00:01,000 --> 00:00:03,000")}
        client = MagicMock()
        client.files.content.return_value.text = (
            '{"custom_id":"a","response":{"body":{"choices":'
            '[{"message":{"content":""}}]}}}')
        with patch.object(sb, "_get_client", return_value=client), \
                patch.object(sb, "INPUT_FOLDER", str(directory)):
            result = sb.process_results(
                "f", file_map, [str(source)],
                input_folder=str(directory), output_folder=str(output))
        self.assertEqual(result["failed_ids"], {"a"})
        written = sorted(path.name for path in output.rglob("*.srt"))
        self.assertEqual(written, ["source.partial.srt"])

class VideoCacheIntegrityTest(unittest.TestCase):
    """Madde 26, 31: video cache kimliği ve payload bütünlüğü."""

    def test_middle_of_file_change_invalidates_the_fingerprint(self):
        import os
        import video_subtitles as vs
        directory = Path(tempfile.mkdtemp())
        video = directory / "v.mkv"
        payload = bytearray(b"A" * 262144)
        video.write_bytes(bytes(payload))
        stat = video.stat()
        before = vs._source_fingerprint(video)
        payload[131072:131136] = b"B" * 64
        video.write_bytes(bytes(payload))
        os.utime(video, ns=(stat.st_atime_ns, stat.st_mtime_ns))
        self.assertEqual(video.stat().st_size, stat.st_size)
        self.assertEqual(video.stat().st_mtime_ns, stat.st_mtime_ns)
        self.assertNotEqual(before, vs._source_fingerprint(video))

    def test_broken_payload_is_not_a_valid_cache(self):
        import video_subtitles as vs
        directory = Path(tempfile.mkdtemp())
        subtitle = directory / "c.srt"
        subtitle.write_text("1\n00:00:01,000 --> 00:00:02,000\nMerhaba.\n",
                            encoding="utf-8")
        self.assertTrue(vs._payload_has_timestamp(subtitle))
        subtitle.write_text("broken-but-nonempty", encoding="utf-8")
        self.assertFalse(vs._payload_has_timestamp(subtitle))

    def test_ass_payload_is_accepted(self):
        import video_subtitles as vs
        directory = Path(tempfile.mkdtemp())
        subtitle = directory / "c.ass"
        subtitle.write_text(
            "[Events]\nDialogue: 0,0:00:01.00,0:00:03.00,Default,,0,0,0,,Hi\n",
            encoding="utf-8")
        self.assertTrue(vs._payload_has_timestamp(subtitle))


class OutputBoundFingerprintTest(unittest.TestCase):
    """Madde 35, 36: parmak izi onaylanan ÇIKTIYA da bağlı olmalı."""

    def _fixture(self):
        directory = Path(tempfile.mkdtemp())
        reports = directory / "Raporlar"
        reports.mkdir()
        source = directory / "s.srt"
        output = directory / "o.srt"
        source.write_text(
            "1\n00:00:01,000 --> 00:00:02,000\nI see the red door.\n",
            encoding="utf-8")
        output.write_text(
            "1\n00:00:01,000 --> 00:00:02,000\nKırmızı kapıyı görüyorum.\n",
            encoding="utf-8")
        g._write_output_source_fingerprint(
            reports, output, g._file_content_sha256(source), source_path=source)
        return reports, source, output

    def test_untouched_output_matches(self):
        reports, source, output = self._fixture()
        self.assertTrue(g._output_matches_source_fingerprint(
            reports, output, source))

    def test_externally_edited_output_no_longer_matches(self):
        reports, source, output = self._fixture()
        output.write_text(
            "1\n00:00:01,000 --> 00:00:02,000\nMavi kapıyı görüyorum.\n",
            encoding="utf-8")
        self.assertFalse(g._output_matches_source_fingerprint(
            reports, output, source))

    def test_source_only_check_can_be_requested(self):
        reports, source, output = self._fixture()
        output.write_text("değişti", encoding="utf-8")
        self.assertTrue(g._output_matches_source_fingerprint(
            reports, output, source, verify_output=False))

    def test_legacy_plain_hash_sidecar_still_works(self):
        reports, source, output = self._fixture()
        sidecar = g._output_source_fingerprint_path(reports, output)
        sidecar.write_text(g._file_content_sha256(source), encoding="utf-8")
        self.assertTrue(g._output_matches_source_fingerprint(
            reports, output, source))


class AutoShutdownGenerationTest(unittest.TestCase):
    """Madde 27: eski kapanış callback'i yeni koşuyu kapatmamalı."""

    def _stub(self):
        stub = types.SimpleNamespace()
        stub._log = lambda *args, **kwargs: None
        stub._complete_session_log_text = lambda: "log"
        stub._auto_shutdown_scheduled_run_id = "RUN-B"
        stub._is_running = False
        return stub

    def test_callback_from_a_previous_run_is_ignored(self):
        stub = self._stub()
        self.assertFalse(g.App._export_log_and_shutdown(
            stub, {"run_id": "RUN-A"}, scheduled_run_id="RUN-A"))

    def test_callback_is_ignored_while_a_run_is_active(self):
        stub = self._stub()
        stub._auto_shutdown_scheduled_run_id = "RUN-A"
        stub._is_running = True
        self.assertFalse(g.App._export_log_and_shutdown(
            stub, {"run_id": "RUN-A"}, scheduled_run_id="RUN-A"))

class HelperRoleMatrixTest(unittest.TestCase):
    """Madde 18, 20: özellik → rol eşlemesi tek kaynaktan gelmeli."""

    def test_condense_is_declared_on_the_role_it_actually_uses(self):
        self.assertEqual(g.FEATURE_HELPER_ROLES["condense"], "analysis")

    def test_default_on_term_normalize_is_covered(self):
        self.assertEqual(g.FEATURE_HELPER_ROLES["term_normalize"], "polish")

    def test_preflight_checks_condense_and_term_normalize(self):
        snapshot = {
            "main_api_key": "k", "main_api_base_url": "https://api.x/v1",
            "main_model_name": "m", "condense": True, "term_normalize": True,
            "helper_keys": {"analysis": "a", "polish": "p"},
            "helper_urls": {"analysis": "https://a/v1", "polish": "https://p/v1"},
            "helper_models": {"analysis": "am", "polish": "pm"},
        }
        models = {row[3] for row in g._provider_preflight_targets(snapshot)}
        self.assertIn("am", models)
        self.assertIn("pm", models)

    def test_every_role_in_the_matrix_has_a_label(self):
        for role in set(g.FEATURE_HELPER_ROLES.values()):
            with self.subTest(role=role):
                self.assertIn(role, g.API_PROFILE_ROLE_LABELS)


class MovedDeliveryFolderTest(unittest.TestCase):
    """Madde 40: tamamlanmış klasör taşınınca provenance kaybolmamalı."""

    def test_fingerprint_survives_a_folder_move(self):
        import shutil
        base = Path(tempfile.mkdtemp())
        old = base / "OLD" / "Movie"
        old.mkdir(parents=True)
        reports = old / "Raporlar"
        reports.mkdir()
        source = old / "s.srt"
        output = old / "Movie.srt"
        source.write_text("1\n00:00:01,000 --> 00:00:02,000\nHello.\n",
                          encoding="utf-8")
        output.write_text("1\n00:00:01,000 --> 00:00:02,000\nMerhaba.\n",
                          encoding="utf-8")
        g._write_output_source_fingerprint(
            reports, output, g._file_content_sha256(source),
            source_path=source)
        self.assertTrue(g._output_matches_source_fingerprint(
            reports, output, source))
        new = base / "YUKLENECEK" / "Movie"
        new.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(old), str(new))
        self.assertTrue(g._output_matches_source_fingerprint(
            new / "Raporlar", new / "Movie.srt", new / "s.srt"))

class AutoRetryTokenTest(unittest.TestCase):
    """Madde 32: eski retry override'ı yeni koşuyu ezmemeli."""

    def _stub(self):
        stub = types.SimpleNamespace()
        stub._auto_retry_token = "TOK-A"
        stub._resume_snapshot_override = {"model": "A"}
        stub._auto_retry_continuation = True
        stub.logs = []
        stub.started = []
        stub._log = lambda message, tag="": stub.logs.append(message)
        stub._start = lambda: stub.started.append(True)
        stub.after_cancel = lambda _id: None
        return stub

    def test_manual_start_cancels_the_pending_override(self):
        stub = self._stub()
        g.App._cancel_pending_auto_retry(stub)
        self.assertIsNone(stub._resume_snapshot_override)
        self.assertFalse(stub._auto_retry_continuation)

    def test_stale_callback_does_not_start_a_run(self):
        stub = self._stub()
        g.App._cancel_pending_auto_retry(stub)
        g.App._start_auto_retry(stub, "TOK-A")
        self.assertEqual(stub.started, [])

    def test_valid_callback_starts_and_keeps_the_override(self):
        stub = self._stub()
        g.App._start_auto_retry(stub, "TOK-A")
        self.assertEqual(stub.started, [True])
        self.assertEqual(stub._resume_snapshot_override, {"model": "A"})


class BatchMissingCountOrderTest(unittest.TestCase):
    """Madde 13: eksik sayımı teslim hazırlığından SONRA yapılmalı."""

    def test_both_batch_paths_count_after_delivery_preparation(self):
        source = io.open(
            os.path.join(os.path.dirname(os.path.dirname(
                os.path.abspath(__file__))), "subtitle_translator_gui.py"),
            encoding="utf-8").read()
        lines = source.split("\n")
        for index, line in enumerate(lines):
            # Yalnız YAZIM YOLU kararini veren sayim denetlenir; rapor
            # istatistikleri zaten teslim bloklarindan hesaplaniyor.
            if "_hata_n_pre, _ = _count_hata_cps(_delivery_blocks)" not in line:
                continue
            window = "\n".join(lines[max(0, index - 12):index])
            with self.subTest(line=index + 1):
                self.assertIn("_prepare_upload_ready_blocks", window)
        self.assertNotIn("_hata_n_pre, _ = _count_hata_cps(_final_blocks)", source)
        self.assertNotIn("_hata_n_pre, _ = _count_hata_cps(pp)", source)

class PostPassTargetLanguageTest(unittest.TestCase):
    """Madde 29: kabul zinciri hedef dili taşımalı."""

    CHAIN = ("split_qc_issues_for_review",
             "validate_semantic_reconciliation_candidate",
             "apply_polish_group_atomic",
             "final_consistency_sweep",
             "consistency_sweep")

    def test_every_acceptance_function_accepts_a_target_language(self):
        import inspect
        for name in self.CHAIN:
            with self.subTest(name=name):
                signature = inspect.signature(getattr(ht, name))
                self.assertIn("tgt_lang", signature.parameters)

    def test_german_candidate_is_not_judged_by_turkish_rules(self):
        ok, _reason = ht.validate_polish_candidate(
            "Ich weiß nicht.", "Ich weiß es nicht.", "I do not know.",
            tgt_lang="German")
        self.assertTrue(ok)

    def test_turkish_rules_still_apply_for_turkish(self):
        ok, reason = ht.validate_polish_candidate(
            "Bilmiyorum.", "Biliyorum.", "I do not know.", tgt_lang="Turkish")
        self.assertFalse(ok)
        self.assertEqual(reason, "source_negation")

    def test_gui_passes_the_target_language_to_the_sweep(self):
        source = io.open(
            os.path.join(os.path.dirname(os.path.dirname(
                os.path.abspath(__file__))), "subtitle_translator_gui.py"),
            encoding="utf-8").read()
        lines = source.split("\n")
        calls = [index for index, line in enumerate(lines)
                 if "ht.final_consistency_sweep(" in line]
        self.assertTrue(calls)
        for index in calls:
            window = "\n".join(lines[index:index + 8])
            with self.subTest(line=index + 1):
                self.assertIn("tgt_lang=", window)

class PreflightStopIsTerminalTest(unittest.TestCase):
    """Madde 21: DUR ön kontrolden sonra çeviriyi başlatmamalı."""

    def _stub(self, stopped):
        stub = types.SimpleNamespace()
        stub._stop_flag = stopped
        stub._is_shutting_down = False
        stub._active_snapshot = None
        stub._resume_snapshot_override = None
        stub.logs = []
        stub.started = []
        stub.idle = []
        stub._log = lambda message, tag="": stub.logs.append(message)
        stub._log_exc = lambda message, exc: stub.logs.append(message)
        stub._set_running = lambda value: None
        stub._set_status = lambda value: None
        stub._start = lambda: stub.started.append(True)
        stub.after_idle = lambda fn: stub.idle.append(fn)
        stub.after = lambda _ms, fn: stub.idle.append(fn)
        return stub

    def test_stop_prevents_the_resume_entirely(self):
        stub = self._stub(stopped=True)
        g.App._resume_after_preflight(stub, "_flag", "Kaynak Dil")
        self.assertFalse(getattr(stub, "_flag"))
        self.assertEqual(stub.idle, [])
        self.assertEqual(stub.started, [])

    def test_stop_during_the_idle_gap_still_blocks_the_start(self):
        stub = self._stub(stopped=False)
        g.App._resume_after_preflight(stub, "_flag", "Kaynak Dil")
        self.assertEqual(len(stub.idle), 1)
        stub._stop_flag = True
        stub.idle[0]()
        self.assertEqual(stub.started, [])

    def test_normal_flow_still_starts(self):
        stub = self._stub(stopped=False)
        g.App._resume_after_preflight(stub, "_flag", "Kaynak Dil")
        stub.idle[0]()
        self.assertEqual(stub.started, [True])


class DeletedProfileLeavesNothingBehindTest(unittest.TestCase):
    """Madde 10: silinen profilin kopyalanmış alanları temizlenmeli."""

    def test_helper_role_fields_are_cleared(self):
        stub = types.SimpleNamespace()
        stub.helper_custom_key_vars = {"analysis": _Var("SECRET")}
        stub.helper_custom_url_vars = {"analysis": _Var("https://x/v1")}
        stub.helper_custom_model_vars = {"analysis": _Var("m")}
        stub.helper_model_vars = {"analysis": _Var("Özel (Custom)")}
        stub.helper_role_key_vars = {"analysis": _Var("SECRET")}
        g.App._clear_role_custom_fields(stub, "analysis")
        self.assertEqual(stub.helper_custom_key_vars["analysis"].get(), "")
        self.assertEqual(stub.helper_custom_url_vars["analysis"].get(), "")
        self.assertEqual(stub.helper_custom_model_vars["analysis"].get(), "")
        self.assertEqual(stub.helper_role_key_vars["analysis"].get(), "")
        self.assertNotEqual(
            stub.helper_model_vars["analysis"].get(), "Özel (Custom)")

    def test_unknown_role_is_tolerated(self):
        stub = types.SimpleNamespace()
        g.App._clear_role_custom_fields(stub, "critic")

class PollLayerDoesNotFinalizeTest(unittest.TestCase):
    """Madde 28: son batch terminal olunca run hemen finalize edilmemeli."""

    def _body(self, name):
        import ast
        path = os.path.join(os.path.dirname(os.path.dirname(
            os.path.abspath(__file__))), "subtitle_translator_gui.py")
        source = io.open(path, encoding="utf-8").read()
        lines = source.split("\n")
        for node in ast.walk(ast.parse(source)):
            if isinstance(node, ast.FunctionDef) and node.name == name:
                return [line for line in lines[node.lineno - 1:node.end_lineno]
                        if not line.strip().startswith("#")]
        self.fail(f"{name} bulunamadı")

    def test_poll_helpers_never_release_the_run(self):
        for name in ("_wait_batch", "_wait_batch_hybrid"):
            with self.subTest(name=name):
                body = "\n".join(self._body(name))
                self.assertNotIn("_set_running(False)", body)

    def test_callers_still_finalize(self):
        for name in ("_run_batch", "_resume_batches", "_run_hybrid"):
            with self.subTest(name=name):
                body = "\n".join(self._body(name))
                self.assertIn("_set_running(False)", body)

if __name__ == "__main__":
    unittest.main()
