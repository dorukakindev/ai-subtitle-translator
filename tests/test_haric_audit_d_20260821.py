# -*- coding: utf-8 -*-
"""HARIC_YENI_BUG_DENETIMI_2026-08-21.md — madde 24-29."""
import hashlib
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import series_memory as sm
import subtitle_formats as sf
import subtitle_translator_gui as g
from video_subtitles import SubtitleStream

NL = chr(10)


class LegacyEncodingPrefersTurkishEvidenceTest(unittest.TestCase):
    """Madde 24: geçerli CP1254 Türkçe SRT doğru açılmalı."""

    def _round_trip(self, body, encoding):
        text = "1" + NL + "00:00:01,000 --> 00:00:02,000" + NL + body + NL
        handle, path = tempfile.mkstemp(suffix=".srt")
        os.close(handle)
        try:
            with open(path, "wb") as out:
                out.write(text.encode(encoding))
            return sf.read_subtitle_text(path).splitlines()[2]
        finally:
            os.unlink(path)

    def test_short_turkish_files_survive(self):
        for body in ("İyi günler, nasılsın?", "Çığlık, öğüt, şüphe."):
            with self.subTest(body=body):
                self.assertEqual(self._round_trip(body, "cp1254"), body)

    def test_the_other_legacy_encodings_still_win_their_own_cases(self):
        for body, encoding in (
                ("Rodríguez y Muñoz están aquí.", "mac_roman"),
                ("He said “hello” — really.", "cp1252"),
                ("Zażółć gęślą jaźń.", "cp1250"),
                ("Привет, как дела?", "cp1251")):
            with self.subTest(encoding=encoding):
                self.assertEqual(self._round_trip(body, encoding), body)


class TolerantSrtTimestampsTest(unittest.TestCase):
    """Madde 25: milisaniyesiz ve 4+ haneli kesirler kabul edilmeli."""

    def _timestamp(self, line):
        body = "1" + NL + line + NL + "Hello." + NL
        handle, path = tempfile.mkstemp(suffix=".srt")
        os.close(handle)
        try:
            with open(path, "w", encoding="utf-8") as out:
                out.write(body)
            rows = list(g.parse_srt(path))
        finally:
            os.unlink(path)
        return rows[0][1] if rows else ""

    def test_a_missing_fraction_becomes_zero_milliseconds(self):
        self.assertEqual(self._timestamp("00:00:01 --> 00:00:03"),
                         "00:00:01,000 --> 00:00:03,000")

    def test_extra_precision_is_truncated_to_milliseconds(self):
        for line in ("00:00:01,1234 --> 00:00:03,5678",
                     "00:00:01,123456 --> 00:00:03,567890"):
            with self.subTest(line=line):
                self.assertEqual(self._timestamp(line),
                                 "00:00:01,123 --> 00:00:03,567")

    def test_the_existing_formats_are_unchanged(self):
        for line, expected in (
                ("00:00:01,500 --> 00:00:03,250", "00:00:01,500 --> 00:00:03,250"),
                ("00:00:01,5 --> 00:00:03,12", "00:00:01,500 --> 00:00:03,120"),
                ("00:00:01.500 --> 00:00:03.250", "00:00:01,500 --> 00:00:03,250")):
            with self.subTest(line=line):
                self.assertEqual(self._timestamp(line), expected)


class TmContextFingerprintTest(unittest.TestCase):
    """Madde 26: kanonik bağlam değişince exact-TM ıskalamalı."""

    def test_an_empty_context_keeps_the_existing_fingerprint(self):
        legacy = hashlib.sha256(json.dumps(
            {"source_sha256": "sha", "locked_terms": []},
            ensure_ascii=False, separators=(",", ":")).encode("utf-8")).hexdigest()
        self.assertEqual(g._tm_context_fingerprint("sha"), legacy)
        self.assertEqual(g._tm_context_fingerprint("sha", {}, {}), legacy)

    def test_a_series_canon_change_produces_a_miss(self):
        self.assertNotEqual(
            g._tm_context_fingerprint("sha", {}, {"series_canon": "informal"}),
            g._tm_context_fingerprint("sha", {}, {"series_canon": "formal"}))

    def test_an_analysis_depth_change_produces_a_miss(self):
        self.assertNotEqual(
            g._tm_context_fingerprint("sha", {}, {"analysis_depth": "Gelişmiş"}),
            g._tm_context_fingerprint("sha", {}, {"analysis_depth": "Maksimum"}))
        self.assertNotEqual(
            g._tm_context_fingerprint("sha"),
            g._tm_context_fingerprint("sha", {}, {"analysis_depth": "Gelişmiş"}))

    def test_key_order_and_blank_values_do_not_matter(self):
        self.assertEqual(
            g._tm_context_fingerprint("sha", {}, {"a": "1", "b": "2"}),
            g._tm_context_fingerprint("sha", {}, {"b": "2", "a": "1"}))
        self.assertEqual(
            g._tm_context_fingerprint("sha"),
            g._tm_context_fingerprint("sha", {}, {"analysis_depth": "  "}))

    def test_term_isolation_still_holds(self):
        self.assertNotEqual(
            g._tm_context_fingerprint("sha", {"A": "B"}),
            g._tm_context_fingerprint("sha", {"A": "C"}))


class EmbeddedStreamDefaultTest(unittest.TestCase):
    """Madde 27: forced/SDH/yorum akışı varsayılan seçilmemeli."""

    @staticmethod
    def _pick(streams):
        english = [stream for stream in streams if stream.supported
                   and stream.language.lower() in {"eng", "en", "english"}]
        ranked = sorted(english or [s for s in streams if s.supported],
                        key=lambda stream: stream.selection_rank)
        return ranked[0] if ranked else None

    def test_the_full_default_track_wins_over_forced(self):
        chosen = self._pick([
            SubtitleStream(2, "subrip", "eng", "English Forced", forced=True),
            SubtitleStream(4, "subrip", "eng", "English Full", default=True)])
        self.assertEqual(chosen.index, 4)

    def test_commentary_loses_to_a_full_track(self):
        chosen = self._pick([
            SubtitleStream(2, "subrip", "eng", "Commentary", commentary=True),
            SubtitleStream(3, "subrip", "eng", "English Full")])
        self.assertEqual(chosen.index, 3)

    def test_titles_are_used_when_disposition_is_missing(self):
        chosen = self._pick([
            SubtitleStream(2, "subrip", "eng", "English Forced"),
            SubtitleStream(3, "subrip", "eng", "English SDH"),
            SubtitleStream(4, "subrip", "eng", "English Full")])
        self.assertEqual(chosen.index, 4)

    def test_a_lone_forced_track_is_selectable_but_flagged(self):
        chosen = self._pick([
            SubtitleStream(2, "subrip", "eng", "English Forced", forced=True)])
        self.assertEqual(chosen.index, 2)
        self.assertTrue(chosen.restricted)

    def test_a_single_untagged_track_is_unaffected(self):
        chosen = self._pick([SubtitleStream(2, "subrip", "", "Track")])
        self.assertEqual(chosen.index, 2)
        self.assertFalse(chosen.restricted)


class ManualJsonlProvenanceTest(unittest.TestCase):
    """Madde 28: JSONL seçilen kaynağa ait olduğunu kanıtlamalı."""

    def _setup(self):
        folder = Path(tempfile.mkdtemp())
        source_a = folder / "a.srt"
        source_a.write_text("1" + NL + "00:00:01,000 --> 00:00:02,000"
                            + NL + "How are you?" + NL + NL, encoding="utf-8")
        source_b = folder / "b.srt"
        source_b.write_text("1" + NL + "00:00:01,000 --> 00:00:02,000"
                            + NL + "Please stop." + NL + NL, encoding="utf-8")
        jsonl = folder / "out.jsonl"
        jsonl.write_text("{}", encoding="utf-8")
        return folder, source_a, source_b, jsonl

    def test_a_matching_source_is_verified(self):
        folder, source_a, _source_b, jsonl = self._setup()
        digest = hashlib.sha256(source_a.read_bytes()).hexdigest()
        (folder / "batch_fmap_x.json").write_text(
            json.dumps({"source_hash": digest}), encoding="utf-8")
        verdict, _detail = g.manual_jsonl_source_verdict(jsonl, source_a)
        self.assertEqual(verdict, "verified")

    def test_another_films_jsonl_fails_closed(self):
        folder, source_a, source_b, jsonl = self._setup()
        digest = hashlib.sha256(source_a.read_bytes()).hexdigest()
        (folder / "batch_fmap_x.json").write_text(
            json.dumps({"source_hash": digest}), encoding="utf-8")
        verdict, detail = g.manual_jsonl_source_verdict(jsonl, source_b)
        self.assertEqual(verdict, "mismatch")
        self.assertTrue(detail.strip())

    def test_without_provenance_the_result_is_unverified(self):
        _folder, _source_a, source_b, jsonl = self._setup()
        verdict, _detail = g.manual_jsonl_source_verdict(jsonl, source_b)
        self.assertEqual(verdict, "unknown")


class SiblingEpisodeFoldersShareMemoryTest(unittest.TestCase):
    """Madde 29: ayrı `Episode N` klasörleri ortak dizi kökü kullanmalı."""

    def test_sibling_episode_folders_resolve_to_one_root(self):
        first = sm.series_memory_root("X:/Show/Episode 1/Show.S01E01.srt")
        second = sm.series_memory_root("X:/Show/Episode 2/Show.S01E02.srt")
        self.assertEqual(first, second)
        self.assertEqual(first.name, "Show")

    def test_a_different_show_keeps_its_own_identity(self):
        self.assertEqual(
            sm.parse_series_key("X:/Show/Episode 2/Other.Show.S01E01.srt")[0],
            "other-show")
        self.assertEqual(
            sm.parse_series_key("X:/Show/Episode 1/Show.S01E01.srt")[0], "show")

    def test_turkish_episode_folders_are_recognised(self):
        self.assertEqual(
            sm.series_memory_root("X:/Show/Bölüm 3/Show.S01E03.srt").name,
            "Show")

    def test_the_recognised_layouts_are_unchanged(self):
        self.assertEqual(
            sm.series_memory_root("X:/Show.tv.s01/Show.S01E01.srt").name,
            "Show.tv.s01")
        self.assertEqual(
            sm.series_memory_root("X:/Show/Season 1/Show.S01E01.srt").name,
            "Season 1")

    def test_a_plain_film_folder_is_untouched(self):
        self.assertEqual(
            sm.series_memory_root("X:/Filmler/movie.srt").name, "Filmler")


if __name__ == "__main__":
    unittest.main()
