# -*- coding: utf-8 -*-
"""Codex Tur 8/9/10 devri (`Raporlar/CODEX/bug-taramasi-2026-0*-tur*.md`).

Dokuz madde, hepsi gerçek arşivde ölçülmüş. Buradaki testler ölçümün
kilididir.
"""
import os
import unittest
from pathlib import Path

import subtitle_translator_gui as gui


class HamBackupPathTest(unittest.TestCase):
    """Tur 8 madde 1: yarım teslimin ham yedeği yanlış klasörde aranıyordu.

    Yazan taraf (`_save_raw_backup`) hem `Raporlar/Kurtarma` sarmalını
    çözüyor hem `.partial` ekini atıyordu; okuyan taraf ikisini de
    yapmıyordu. Arşivde 127 partial dosyanın 122'sinde yedek DURURKEN 0'ı
    bulunuyordu.
    """

    def test_partial_output_resolves_to_the_sibling_ham_folder(self):
        root = Path("D:/iş/bölüm")
        partial = root / "Raporlar" / "Kurtarma" / "x.partial.srt"
        self.assertEqual(gui._delivery_report_dir(partial) / "Ham",
                         root / "Raporlar" / "Ham")

    def test_partial_stem_drops_the_partial_suffix(self):
        self.assertEqual(gui._delivery_output_stem("a/b/x.partial.srt"), "x")
        self.assertEqual(gui._delivery_output_stem("a/b/x.srt"), "x")

    def test_reader_and_writer_agree_on_a_real_shape(self):
        """Yazıcının kurduğu yolu okuyucu bulmalı."""
        import tempfile
        with tempfile.TemporaryDirectory() as root:
            base = Path(root, "bölüm")
            ham_dir = base / "Raporlar" / "Ham"
            ham_dir.mkdir(parents=True)
            (ham_dir / "x.abc1234567.ham.srt").write_text(
                "1\n00:00:01,000 --> 00:00:02,000\nBir.\n", encoding="utf-8")
            partial = base / "Raporlar" / "Kurtarma" / "x.partial.srt"
            partial.parent.mkdir(parents=True)
            partial.write_text("1\n00:00:01,000 --> 00:00:02,000\nBir.\n",
                               encoding="utf-8")
            found = gui._ham_backup_path(partial)
            self.assertIsNotNone(found)
            self.assertEqual(Path(found).name, "x.abc1234567.ham.srt")


class LostCueNeighbourTest(unittest.TestCase):
    """Tur 8 madde 2: komşu cue'ya taşınmış çeviri "teslimde yok" sanılıyordu.

    Cue birleştirme meşru bir son işlem; ham zaman damgası kaybolsa da metin
    komşu cue'da duruyor olabilir. Öneri "Ham yedekteki çeviriyi geri koy"
    olduğu için uygulanması metni ikinci kez eklerdi.
    """

    OUT = [("1", "00:00:03,000 --> 00:00:08,000",
            "ama orayı hiç bu Rastalarla\ngördüğüm gibi görmemiştim.")]

    def test_text_merged_into_a_neighbour_is_not_lost(self):
        ham = [("3", "00:00:05,490 --> 00:00:06,690", "bu Rastalarla.")]
        self.assertEqual(
            gui.detect_lost_translated_cues(ham, self.OUT), [])

    def test_punctuation_difference_does_not_hide_the_match(self):
        """`New York'ta,` → `New York'ta öyle bir şeydi ki--`"""
        out = [("2", "00:00:00,000 --> 00:00:04,000",
                "New York'ta öyle bir şeydi ki--")]
        ham = [("1", "00:00:00,180 --> 00:00:03,210", "New York'ta,")]
        self.assertEqual(gui.detect_lost_translated_cues(ham, out), [])

    def test_a_genuinely_missing_line_is_still_reported(self):
        ham = [("9", "00:43:22,000 --> 00:43:27,040",
                "Tüm sanatçılar gibi, otoportre geleneğinin içindeyim.")]
        out = [("1", "00:50:00,000 --> 00:50:02,000", "Alakasız bir replik.")]
        self.assertEqual(
            [row[0] for row in gui.detect_lost_translated_cues(ham, out)],
            ["9"])

    def test_short_common_text_does_not_earn_the_escape(self):
        """Kısa metin komşuda tesadüfen geçebilir; eşiğin altında sayılmaz."""
        ham = [("1", "00:00:01,000 --> 00:00:02,000", "Evet.")]
        out = [("1", "00:00:03,000 --> 00:00:05,000", "Evet. Öyle oldu.")]
        self.assertEqual(
            [row[0] for row in gui.detect_lost_translated_cues(ham, out)],
            ["1"])


class MidwordProperNameTest(unittest.TestCase):
    """Tur 8 madde 3: `Pater Noster` ve `World Wide Web` yanlış alarmdı.

    Kaynak ortografisi (`Paternoster`, `worldwide`) hedefteki özel ad
    sınırına üstün değildir. Bozuk bölünmede ikinci parça küçük kalır.
    """

    def test_multiword_proper_name_is_not_a_broken_split(self):
        self.assertEqual(
            gui._midword_space_ids([("1", "x", "Pater Noster yazıyor,")],
                                   {"1": "It says Paternoster,"}),
            [])
        self.assertEqual(
            gui._midword_space_ids([("1", "x", "World Wide Web olacaktı.")],
                                   {"1": "worldwide web"}),
            [])

    def test_lowercase_second_part_is_still_a_broken_split(self):
        self.assertEqual(
            gui._midword_space_ids([("1", "x", "Piram itler harika.")],
                                   {"1": "Piramitler are great."}),
            ["1"])


class ForeignCreditFormsTest(unittest.TestCase):
    """Tur 9 madde 1: üç künye biçimi sert "eksik diyalog" hatası üretiyordu."""

    def test_measured_credit_forms_are_recognised(self):
        for text in ("<b>Traducerea şi adaptarea: Livioi</b>",
                     "Traducerea si adaptarea: Livioi",
                     "Srpski titl: tplc",
                     "SubtitIes by:",
                     "Laser S. FiIm s.r.I. - Roma"):
            with self.subTest(text=text):
                self.assertTrue(gui._looks_like_credit_or_promo(text))

    def test_real_dialogue_is_not_silenced(self):
        """Rusça konuşma etiketi künye DEĞİLDİR — gerçek replik."""
        for text in ("ПЕРЕВОДЧИК: Как и все художники,",
                     "ÇEVİRMEN: Tüm sanatçılar gibi, otoportre geleneğinde.",
                     "Titl kelimesi cümlede geçebilir"):
            with self.subTest(text=text):
                self.assertFalse(gui._looks_like_credit_or_promo(text))


class FindingIdentityTest(unittest.TestCase):
    """Tur 9 madde 2 ve 3: bulgu kimliği hem çakışıyor hem kalıcı değildi."""

    SRC = [("1", "00:00:01,000 --> 00:00:02,000", "One."),
           ("2", "00:00:03,000 --> 00:00:04,000", "Two.")]

    def _build(self, folder, delta=0):
        out = [(str(1 + delta), "00:00:01,000 --> 00:00:02,000", "Bir."),
               (str(2 + delta), "00:00:03,000 --> 00:00:04,000", "İki.")]
        rows = [{"name": "x.srt",
                 "source_path": f"{folder}/s.srt",
                 "output_path": f"{folder}/x.srt",
                 "delivery_audit": {
                     "untranslated_fragment_ids": [str(2 + delta)]}}]
        return gui.build_finding_rows(
            rows,
            read_cues=lambda p: self.SRC if str(p).endswith("s.srt") else out)

    def test_id_survives_cue_renumbering(self):
        first = self._build("A", 0)[0]
        second = self._build("A", 1000)[0]
        self.assertNotEqual(first["cue_no"], second["cue_no"])
        self.assertEqual(first["id"], second["id"])

    def test_same_basename_in_two_folders_gets_two_ids(self):
        self.assertNotEqual(self._build("A")[0]["id"],
                            self._build("B")[0]["id"])

    def test_file_key_separates_paths_that_share_their_tail(self):
        """Arşivde son üç bileşeni aynı, içeriği farklı iki teslim var."""
        left = gui._finding_file_key(
            "x.srt", r"D:\kök\HAZIR DİZİLER\dizi\bölüm\x.srt")
        right = gui._finding_file_key(
            "x.srt", r"D:\kök\HAZIR FİLMLER\dizi\bölüm\x.srt")
        self.assertNotEqual(left, right)

    def test_decision_scope_is_one_file(self):
        left = self._build("A")
        right = self._build("B")
        kept, suppressed = gui.apply_finding_decisions(
            left + right, {left[0]["id"]: {"karar": "yanlis_alarm"}})
        self.assertEqual(len(suppressed), 1)
        self.assertEqual(len(kept), 1)
        self.assertEqual(kept[0]["id"], right[0]["id"])


class FormatCoverageFontTest(unittest.TestCase):
    """Tur 10 madde 1: bilerek silinen `<font>` "geri koy" diye raporlanıyordu.

    Zaman damgasıyla kesin eşleşen 482 biçim kaybının 381'i `<font>`'tu.
    """

    def _lost(self, source, delivered):
        return gui._format_coverage_lost_ids(
            [("1", "x", delivered)], {"1": source})

    def test_deliberately_removed_font_is_not_a_finding(self):
        self.assertEqual(
            self._lost('<font color="#ffff00">generals.</font>',
                       "generaller."),
            [])

    def test_position_tag_removal_is_not_a_finding(self):
        self.assertEqual(self._lost(r"{\an8}Üstte", "Üstte"), [])

    def test_italic_and_bold_losses_are_still_reported(self):
        self.assertEqual(self._lost("<i>Bir ses.</i>", "Bir ses."), ["1"])
        self.assertEqual(self._lost("<b>Dikkat!</b>", "Dikkat!"), ["1"])


class ReportCoverageTest(unittest.TestCase):
    """Tur 10 madde 2 ve 3: özet/karar/kapsam bulguların çoğunu görmüyordu."""

    ROWS = [{"name": "x.srt", "source_path": "d/s.srt",
             "output_path": "d/x.srt",
             "delivery_audit": {"missing_dialogue_ids": ["1"]}}]

    def _findings(self):
        src = [("1", "00:00:01,000 --> 00:00:02,000", "One.")]
        out = [("1", "00:00:09,000 --> 00:00:10,000", "Başka.")]
        return gui.build_finding_rows(
            self.ROWS,
            read_cues=lambda p: src if str(p).endswith("s.srt") else out)

    def test_delivery_audit_findings_reach_the_summary_rows(self):
        findings = self._findings()
        self.assertTrue(findings)
        narrow = gui._report_finding_rows(self.ROWS)
        wide = gui._report_finding_rows(self.ROWS, findings)
        self.assertGreater(len(wide), len(narrow))
        self.assertIn("missing_dialogue_ids", {row[1] for row in wide})

    def test_actionable_class_lands_in_the_critical_group(self):
        self.assertEqual(gui._report_group_for("missing_dialogue_ids"),
                         "KRİTİK")
        self.assertEqual(gui._report_group_for("expected_removed_ids"),
                         "BİÇİM")

    def test_summary_and_decisions_mention_the_finding(self):
        findings = self._findings()
        label = gui._report_finding_label("missing_dialogue_ids")
        index = gui.build_report_index_text(
            self.ROWS, "run", ["a.txt"], findings=findings)
        decisions = gui.build_decisions_report_text(
            self.ROWS, "run", findings=findings)
        self.assertIn(label, index)
        self.assertIn(label, decisions)

    def test_coverage_verifies_the_wider_set(self):
        findings = self._findings()
        decisions = gui.build_decisions_report_text(
            self.ROWS, "run", findings=findings)
        coverage = gui.verify_report_coverage(
            self.ROWS, decisions, findings=findings)
        self.assertTrue(coverage["ok"])
        self.assertGreaterEqual(
            coverage["found"], len(gui._report_finding_rows(self.ROWS)) + 1)

    def test_summary_is_written_after_every_other_report(self):
        """`00-OZET.md` yazımı, `report_paths` tamamlandıktan SONRA olmalı."""
        import inspect
        source = inspect.getsource(gui.App._save_quality_report)
        index_at = source.index('atomic_write_text(index_path')
        for later in ('bulgular.jsonl', 'ceviri_raporu.json',
                      'İşlem Dökümleri'):
            with self.subTest(later=later):
                self.assertLess(source.index(later), index_at)


if __name__ == "__main__":
    unittest.main()
