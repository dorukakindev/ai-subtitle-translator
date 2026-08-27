# -*- coding: utf-8 -*-
"""Bulgu düzeyinde liste (`bulgular.jsonl`).

Rapor JSON'u DOSYA düzeyinde: `missing_dialogue_ids: [325]`. Bulguyu okuyan
(Codex/Claude) altyazıyı açıp o numarayı bulmak zorunda kalıyordu — ve
teslimde cue numaraları yeniden numaralanıyor, yani numara güvenilir bir
adres değil. Gerçek olay: cue kimliğine dayanan bir eşleme 23.398 sahte
ihlal üretmişti.

Bu liste her bulguyu tek satıra indirir, ZAMAN DAMGASIYLA adresler ve
kaynak + teslim metnini yanına koyar.
"""
import json
import unittest

import subtitle_translator_gui as g


SOURCE = [
    ("1", "00:00:01,000 --> 00:00:02,000", "You speak Portuguese."),
    ("2", "00:00:03,000 --> 00:00:04,000", "[BUZZING]"),
    ("3", "00:00:05,000 --> 00:00:06,000", "He never answered."),
]
OUTPUT = [
    ("1", "00:00:05,000 --> 00:00:06,000", "Hiç cevap vermedi."),
]


def _reader(path):
    return SOURCE if path == "kaynak.srt" else OUTPUT


def _rows():
    return [{
        "name": "ornek.srt",
        "source_path": "kaynak.srt",
        "output_path": "teslim.srt",
        "delivery_audit": {
            "missing_dialogue_ids": ["1"],
            "expected_removed_ids": ["2"],
            "reversed_timestamp_ids": ["3"],
        },
    }]


class FindingRowsTest(unittest.TestCase):
    def test_one_row_per_finding(self):
        findings = g.build_finding_rows(_rows(), read_cues=_reader)
        self.assertEqual(len(findings), 3)
        self.assertEqual({f["sinif"] for f in findings},
                         {"missing_dialogue_ids", "expected_removed_ids",
                          "reversed_timestamp_ids"})

    def test_finding_carries_timestamp_and_both_texts(self):
        findings = g.build_finding_rows(_rows(), read_cues=_reader)
        missing = next(f for f in findings
                       if f["sinif"] == "missing_dialogue_ids")
        self.assertEqual(missing["zaman"], "00:00:01,000 --> 00:00:02,000")
        self.assertEqual(missing["kaynak"], "You speak Portuguese.")
        # O zaman aralığında teslimde cue yok — kaybın kendisi bu.
        self.assertEqual(missing["teslim"], "")

    def test_delivery_text_is_matched_by_timestamp_not_cue_number(self):
        # Teslimde cue numarası 1, kaynakta o zamana ait numara 3.
        findings = g.build_finding_rows(_rows(), read_cues=_reader)
        reversed_row = next(f for f in findings
                            if f["sinif"] == "reversed_timestamp_ids")
        self.assertEqual(reversed_row["cue_no"], "3")
        self.assertEqual(reversed_row["teslim"], "Hiç cevap vermedi.")

    def test_confidence_tiers_and_ordering(self):
        findings = g.build_finding_rows(_rows(), read_cues=_reader)
        self.assertEqual(findings[0]["guven"], "kesin")
        self.assertEqual(findings[-1]["guven"], "bilgi")

    def test_id_is_stable_across_runs(self):
        first = g.build_finding_rows(_rows(), read_cues=_reader)
        second = g.build_finding_rows(_rows(), read_cues=_reader)
        self.assertEqual([f["id"] for f in first], [f["id"] for f in second])

    def test_id_differs_per_class_and_timestamp(self):
        findings = g.build_finding_rows(_rows(), read_cues=_reader)
        self.assertEqual(len({f["id"] for f in findings}), len(findings))

    def test_unreadable_files_still_produce_findings(self):
        def broken(_path):
            raise OSError("okunamadı")
        findings = g.build_finding_rows(_rows(), read_cues=broken)
        self.assertEqual(len(findings), 3)
        self.assertEqual(findings[0]["kaynak"], "")

    def test_jsonl_body_is_one_object_per_line(self):
        body = g.build_findings_jsonl(_rows(), read_cues=_reader)
        lines = [line for line in body.split("\n") if line]
        self.assertEqual(len(lines), 3)
        for line in lines:
            self.assertIn("zaman", json.loads(line))

    def test_every_known_class_has_a_confidence(self):
        for field, meta in g._FINDING_CLASSES.items():
            with self.subTest(field=field):
                self.assertIn(meta[0], ("kesin", "muhtemel", "bilgi"))
                self.assertTrue(meta[1] and meta[2])

    def test_empty_input_is_safe(self):
        self.assertEqual(g.build_finding_rows([]), [])
        self.assertEqual(g.build_finding_rows(None), [])
        self.assertEqual(g.build_findings_jsonl([]), "")


class FindingDecisionsTest(unittest.TestCase):
    """Önceki koşunun kararı bu koşuda gürültüyü kapatsın.

    Codex bir bulguyu 'yanlış alarm' diye işaretlediğinde sonraki koşu onu
    eylem listesine yazmamalı; yoksa aynı satır her turda yeniden okunuyor
    ve okuyan taraf her turda aynı tokeni ödüyor.
    """

    def _findings(self):
        return g.build_finding_rows(_rows(), read_cues=_reader)

    def test_false_alarm_is_suppressed(self):
        findings = self._findings()
        target = findings[0]["id"]
        kept, suppressed = g.apply_finding_decisions(
            findings, {target: {"karar": "yanlis_alarm", "not": "kasıtlı"}})
        self.assertEqual(len(kept), len(findings) - 1)
        self.assertEqual(len(suppressed), 1)
        self.assertEqual(suppressed[0]["onceki_karar"], "yanlis_alarm")
        self.assertEqual(suppressed[0]["karar_notu"], "kasıtlı")

    def test_plain_string_verdict_is_accepted(self):
        findings = self._findings()
        kept, suppressed = g.apply_finding_decisions(
            findings, {findings[0]["id"]: "duzeltildi"})
        self.assertEqual(len(suppressed), 1)

    def test_unknown_verdict_keeps_the_finding(self):
        # Yanlış yazılmış tek kelime gerçek bir kaybı gizlememeli.
        findings = self._findings()
        kept, suppressed = g.apply_finding_decisions(
            findings, {findings[0]["id"]: "belki"})
        self.assertEqual(len(kept), len(findings))
        self.assertEqual(suppressed, [])

    def test_deferred_stays_in_the_list(self):
        findings = self._findings()
        kept, suppressed = g.apply_finding_decisions(
            findings, {findings[0]["id"]: {"karar": "ertelendi"}})
        self.assertEqual(len(kept), len(findings))

    def test_missing_or_broken_decision_file_suppresses_nothing(self):
        findings = self._findings()
        for table in (None, {}, [], "bozuk"):
            with self.subTest(table=table):
                kept, suppressed = g.apply_finding_decisions(findings, table)
                self.assertEqual(len(kept), len(findings))
                self.assertEqual(suppressed, [])

    def test_loader_tolerates_a_missing_file(self):
        self.assertEqual(g.load_finding_decisions("yok-boyle-bir-dosya.json"), {})


class LostTranslatedCueTest(unittest.TestCase):
    """Ham yedekte çevrilmiş satır var, teslimde yok.

    Program her dosyanın kalite geçişlerinden önceki hâlini `.ham.srt`
    olarak saklıyor ve hiç bakmıyordu. Üç teslim dosyasında gerçek diyalog
    kaybı bulundu; üçü de ham yedekte DOĞRU ÇEVRİLMİŞ hâlde duruyordu.

    Ölçüm (309 eşleşen ham/teslim çifti): ham tarafı etiket filtresi
    eklenmeden 813 alarm, eklendikten sonra 71 — bilinen üç gerçek kayıp
    her iki durumda da içinde.
    """

    HAM = [
        ("1", "00:00:01,000 --> 00:00:02,000", "Portekizce konuşuyorsun."),
        ("2", "00:00:03,000 --> 00:00:04,000", "[ÇIĞLIK]"),
        ("3", "00:00:05,000 --> 00:00:06,000", "♪♪"),
        ("4", "00:00:07,000 --> 00:00:08,000", "-[İspanyolca konuşuluyor]"),
        ("5", "00:00:09,000 --> 00:00:10,000", "Bu satır teslimde duruyor."),
    ]
    OUT = [("1", "00:00:09,000 --> 00:00:10,000", "Bu satır teslimde duruyor.")]

    def test_real_dialogue_loss_is_reported(self):
        lost = g.detect_lost_translated_cues(self.HAM, self.OUT)
        self.assertEqual([row[2] for row in lost],
                         ["Portekizce konuşuyorsun."])

    def test_translated_sdh_labels_are_not_losses(self):
        # `[ÇIĞLIK]`, `♪♪`, `-[İspanyolca konuşuluyor]` teslimden doğru
        # olarak çıkmış; bunlar alarm üretirse gerçek kayıp gürültüde
        # kaybolur (ölçüldü: 813 alarmın 730'u bu sınıftı).
        lost = g.detect_lost_translated_cues(self.HAM, self.OUT)
        bodies = [row[2] for row in lost]
        for label in ("[ÇIĞLIK]", "♪♪", "-[İspanyolca konuşuluyor]"):
            self.assertNotIn(label, bodies)

    def test_expected_removal_timestamps_are_skipped(self):
        lost = g.detect_lost_translated_cues(
            self.HAM, self.OUT,
            expected_removed_timestamps={"00:00:01,000 --> 00:00:02,000"})
        self.assertEqual(lost, [])

    def test_matching_is_by_timestamp_not_cue_number(self):
        # Teslimde cue numarası 1, ham'da o zamana ait numara 5.
        lost = g.detect_lost_translated_cues(self.HAM, self.OUT)
        self.assertNotIn("5", [row[0] for row in lost])

    def test_empty_input_is_safe(self):
        self.assertEqual(g.detect_lost_translated_cues([], []), [])
        self.assertEqual(g.detect_lost_translated_cues(None, None), [])


if __name__ == "__main__":
    unittest.main()
