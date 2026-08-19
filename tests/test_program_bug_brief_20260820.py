"""plans/program-bug-brief-2026-08-20.md — ikinci parti bulguların regresyon kilidi.

Kaynak: Connections S01E08-E10, Witch Doctor S01E01 (Portekizce kaynak),
Death Scenes 1989/1992/1993. Ölçüler brief'teki gerçek cue'lardan alınmıştır.
"""
import unittest

import subtitle_translator_gui as gui


class CueFillImbalanceTest(unittest.TestCase):
    """P0-A: Death Scenes 1992 #369 — 0,4 sn'de 122 karakter (305 kar/sn)."""

    def _pair(self):
        return (
            [("368", "00:20:00,000 --> 00:20:07,000", "Bu " + "a" * 44),
             ("369", "00:20:07,000 --> 00:20:07,400", "B" * 122)],
            {"368": "x" * 150, "369": "elements."},
        )

    def test_real_case_is_detected_with_measurements(self):
        blocks, src = self._pair()
        findings = gui._cue_fill_imbalances(blocks, src)
        self.assertEqual(len(findings), 1)
        finding = findings[0]
        self.assertEqual(finding["id"], "369")
        self.assertEqual(finding["prev_id"], "368")
        self.assertGreater(finding["cps"], 300)
        self.assertLess(finding["prev_cps"], 20)

    def test_report_line_names_target_cue(self):
        blocks, src = self._pair()
        lines = gui._cue_fill_report_lines(gui._cue_fill_imbalances(blocks, src))
        self.assertIn("#369", lines[0])
        self.assertIn("#368", lines[0])

    def test_fast_cue_without_room_in_neighbour_is_not_flagged(self):
        # Önceki cue da doluysa metin taşınamaz → bulgu olmamalı
        blocks = [("1", "00:00:00,000 --> 00:00:02,000", "C" * 90),
                  ("2", "00:00:02,000 --> 00:00:02,400", "B" * 122)]
        src = {"1": "x" * 95, "2": "elements."}
        self.assertEqual(gui._cue_fill_imbalances(blocks, src), [])

    def test_fast_cue_whose_source_is_also_long_is_not_flagged(self):
        blocks = [("1", "00:00:00,000 --> 00:00:07,000", "Kısa."),
                  ("2", "00:00:07,000 --> 00:00:08,000", "B" * 60)]
        src = {"1": "Short.", "2": "y" * 58}
        self.assertEqual(gui._cue_fill_imbalances(blocks, src), [])


class CueFillIsNotAContentShiftTest(unittest.TestCase):
    """P0-B: Death Scenes 1992 #370 — content_offset yanlış pozitifi."""

    def test_short_region_after_unfinished_sentence_is_downgraded(self):
        src = {
            "368": "Death is the great leveller of all human and social",
            "369": "elements.",
            "370": "Mussolini arrived in Rome that morning.",
            "371": "Another ordinary line follows here.",
        }
        blocks = [("368", "ts", "Ölüm, bütün insani ve toplumsal"),
                  ("369", "ts", "unsurların eşitleyicisidir Mussolini gibi."),
                  ("370", "ts", "Mussolini o sabah Roma'ya vardı."),
                  ("371", "ts", "Sıradan bir satır daha geliyor.")]
        self.assertEqual(
            gui._content_offset_regions(blocks, src, min_run=2), [])

    def test_long_real_shift_is_still_reported(self):
        names = ["Calais", "Channel", "Latham", "Sangatte", "London",
                 "Wright", "Dover", "Farman", "Voisin", "Reims"]
        src = {str(i + 1): f"The story of {n} continues here."
               for i, n in enumerate(names)}
        blocks = [(str(i + 1), "ts",
                   f"{names[i - 1]} hikâyesi sürüyor." if i else "Blériot başlıyor.")
                  for i in range(len(names))]
        regions = gui._content_offset_regions(blocks, src)
        self.assertEqual(len(regions), 1)
        self.assertGreaterEqual(len(regions[0]["ids"]), 3)


class AddressRegisterMixTest(unittest.TestCase):
    """P0-C: Connections E10 — dosya ortasında 'siz'den 'sen'e geçiş (120 cue)."""

    def test_mixed_file_is_reported(self):
        blocks = ([(str(i), "ts", "Bunu görebilirsiniz ve anlarsınız.")
                   for i in range(1, 16)]
                  + [(str(i), "ts", "Bunu görebilirsin ve anlarsın.")
                     for i in range(16, 26)])
        result = gui.detect_address_register_mix(blocks)
        self.assertTrue(result["mixed"])
        self.assertGreater(result["informal"], 0)
        self.assertGreater(result["formal"], 0)

    def test_consistent_file_is_clean(self):
        blocks = [(str(i), "ts", "Bunu görebilirsiniz ve anlarsınız.")
                  for i in range(1, 26)]
        self.assertFalse(gui.detect_address_register_mix(blocks)["mixed"])

    def test_imperatives_do_not_count_as_address(self):
        blocks = [(str(i), "ts", "Şimdi bakın ve düşünün.") for i in range(1, 26)]
        result = gui.detect_address_register_mix(blocks)
        self.assertEqual((result["informal"], result["formal"]), (0, 0))
        self.assertFalse(result["mixed"])


class ForeignResidueTest(unittest.TestCase):
    """P0-D: Witch Doctor E01 — 'Ocidente'de', 'China'daki', 'Mr. Yi'."""

    def test_titles_are_normalized(self):
        text, count = gui.normalize_foreign_titles(
            "Mr. Yi ve Miss Xiao, Professor Sun ile geldi.")
        self.assertEqual(text, "Bay Yi ve Bayan Xiao, Profesör Sun ile geldi.")
        self.assertEqual(count, 3)

    def test_exonym_suffix_is_harmonised(self):
        text, count = gui.normalize_foreign_exonyms(
            "China'daki ilaçlar ve Ocidente'de acı.")
        self.assertEqual(text, "Çin'deki ilaçlar ve Batı'da acı.")
        self.assertEqual(count, 2)

    def test_bare_foreign_word_is_left_alone(self):
        # 'Captain America' gibi eser/özel adlar bozulmamalı
        text, count = gui.normalize_foreign_exonyms("Captain America geldi.")
        self.assertEqual(text, "Captain America geldi.")
        self.assertEqual(count, 0)

    def test_source_residue_signal_skips_locked_names(self):
        blocks = [("603", "ts", "Ocidente'de acıya verdiğimiz tepki"),
                  ("46", "ts", "Mussolini'yi anlatıyor")]
        src = {"603": "a nossa resposta à dor no Ocidente",
               "46": "about Mussolini today"}
        found = gui._source_residue_with_turkish_suffix(
            blocks, src, {"Mussolini": "Mussolini"})
        self.assertEqual([item["id"] for item in found], ["603"])

    def test_untranslated_line_is_not_masked_by_title_fix(self):
        """Tamamen çevrilmemiş satırda unvan düzeltmesi UYGULANMAZ — yoksa
        teslim denetiminin çevrilmemiş-parça guard'ı kör kalırdı."""
        blocks = [("1", "00:00:01,000 --> 00:00:03,000",
                   "Mrs. Regnier's lawyer.")]
        cues = [("1", "00:00:01,000 --> 00:00:03,000", "Mrs. Regnier's lawyer.")]
        result = gui._prepare_upload_ready_blocks(
            blocks, "Turkish", None, source_cues=cues)
        texts = [t for _i, _ts, t in result if t != gui._DELIVERY_SIGNATURE]
        self.assertIn("Mrs. Regnier's lawyer.", texts)


class PartialEchoTest(unittest.TestCase):
    """P1-F: komşu cue'da kısmi yankı (adjacent_duplicate kaçırıyordu)."""

    def test_tail_repeat_is_detected(self):
        blocks = [
            ("524", "ts", "Yetişkinlik hayatım boyunca hiç böyle olduğunu hatırlamıyorum"),
            ("525", "ts", "böyle olduğunu hatırlamıyorum."),
            ("526", "ts", "Tamamen farklı bir konu açıldı burada."),
        ]
        self.assertEqual(gui._partial_echo_ids(blocks), [("524", "525")])

    def test_legitimate_source_repeat_is_silent(self):
        blocks = [("347", "ts", "Nasıl hissettin o gün orada sen?"),
                  ("348", "ts", "Nasıl hissettin o gün orada sen?")]
        src = {"347": "How did you feel that day there?",
               "348": "How did you feel that day there?"}
        self.assertEqual(gui._partial_echo_ids(blocks, src), [])

    def test_unrelated_neighbours_are_clean(self):
        blocks = [("1", "ts", "Bugün hava çok güzel görünüyor."),
                  ("2", "ts", "Yarın toplantıya gitmemiz gerekiyor.")]
        self.assertEqual(gui._partial_echo_ids(blocks), [])


class MissingPredicateTest(unittest.TestCase):
    """P1-H: Death Scenes 3 #80 — yüklemsiz biten cue."""

    def test_dangling_case_ending_before_new_sentence(self):
        blocks = [
            ("80", "ts", "Kalabalığı denetleyip ölüm arabasının hastaneye gitmesine."),
            ("81", "ts", "Sonraki cümle burada başlıyor."),
        ]
        self.assertEqual(gui._missing_predicate_ids(blocks), ["80"])

    def test_complete_sentence_is_clean(self):
        blocks = [("1", "ts", "Kalabalığı denetlemeye çalıştılar."),
                  ("2", "ts", "Sonra hastaneye gittiler.")]
        self.assertEqual(gui._missing_predicate_ids(blocks), [])


class ApostropheAndTypographyTest(unittest.TestCase):
    """P1-I / P1-J: tipografik kesme ve ortak isimlerde kesme işareti."""

    def test_write_layer_flattens_typography(self):
        import tempfile
        from pathlib import Path
        with tempfile.TemporaryDirectory() as root:
            out = Path(root, "out.srt")
            gui.write_srt(str(out), [
                ("1", "00:00:01,000 --> 00:00:04,000",
                 "Mussolini’yi 1934’te gördü."),
            ], "Turkish")
            written = out.read_text(encoding="utf-8")
        self.assertIn("Mussolini'yi 1934'te gördü.", written)
        self.assertNotIn("’", written)

    def test_common_noun_apostrophe_is_dropped(self):
        self.assertEqual(
            gui.fix_common_noun_apostrophes("lamina'yı çıkardılar")[0],
            "laminayı çıkardılar")

    def test_proper_noun_and_number_keep_apostrophe(self):
        for value in ("Mussolini'yi gördü", "1934'te oldu", "d'Artagnan geldi"):
            with self.subTest(value=value):
                self.assertEqual(gui.fix_common_noun_apostrophes(value)[0], value)


class SuffixHarmonyTest(unittest.TestCase):
    """Gövde değişince ek uyumu (Çin'deki / Batı'da)."""

    def test_harmony_cases(self):
        # Kaynaştırma harfi (-y-/-n-) YENİ gövdeye göre seçilir: ünsüzle biten
        # "Mısır" -y- almaz, ünlüyle biten "Doğu" alır.
        cases = {("Çin", "daki"): "deki", ("Batı", "de"): "da",
                 ("Almanya", "dan"): "dan", ("Mısır", "yi"): "ı",
                 ("Hindistan", "ya"): "a", ("Doğu", "ya"): "ya",
                 ("Amerika", "e"): "ya", ("Yunanistan", "yi"): "ı",
                 ("Almanya", "in"): "nın", ("Çin", "nin"): "in"}
        for (stem, suffix), expected in cases.items():
            with self.subTest(stem=stem):
                self.assertEqual(
                    gui.turkish_suffix_for_stem(stem, suffix), expected)

    def test_unknown_suffix_is_left_alone(self):
        self.assertEqual(gui.turkish_suffix_for_stem("Çin", "xyz"), "xyz")


class AutoLockedProperNounTest(unittest.TestCase):
    """P1-10: sözlükte olmayan tekrar eden özel adlar kilitlenmeli."""

    SOURCE = ("Louis Barthou arrived in Marseille. The king met Barthou there. "
              "Later Barthou was shot. Everyone mourned Barthou that evening. "
              "The Black Dahlia case shocked the city. Police read the Dahlia "
              "files. Reporters called her the Dahlia for weeks.")

    def test_repeated_names_are_locked_with_identity_mapping(self):
        locked = gui.auto_locked_proper_nouns(self.SOURCE)
        self.assertEqual(locked.get("Barthou"), "Barthou")
        self.assertEqual(locked.get("Dahlia"), "Dahlia")

    def test_terms_already_in_glossary_are_not_duplicated(self):
        locked = gui.auto_locked_proper_nouns(
            self.SOURCE, {"Barthou": "Barthou"})
        self.assertNotIn("Barthou", locked)

    def test_sentence_initial_common_word_is_not_locked(self):
        source = ("Sonra gitti. Sonra geldi. Sonra kaldı. Sonra yine gitti.")
        self.assertEqual(gui.auto_locked_proper_nouns(source), {})


class NumberingPrefixPromptTest(unittest.TestCase):
    """P1-E: 'One:' / 'Problem:' önekleri düşüyordu."""

    def test_rule_present_in_both_prompts(self):
        from pathlib import Path
        sync = gui._build_sync_system_prompt("English", "Turkish", None, "Orta")
        hybrid = Path("hybrid_translate.py").read_text(encoding="utf-8")
        self.assertIn("NUMBERING AND LABEL PREFIXES", sync)
        self.assertIn("NUMBERING AND LABEL PREFIXES", hybrid)


class DeliveryScanWiringTest(unittest.TestCase):
    """Yeni sinyaller teslim taramasında görünmeli."""

    def test_scan_reports_cue_fill_with_actionable_line(self):
        blocks = [("368", "00:20:00,000 --> 00:20:07,000", "Bu " + "a" * 44),
                  ("369", "00:20:07,000 --> 00:20:07,400", "B" * 122)]
        cues = [("368", "00:20:00,000 --> 00:20:07,000", "x" * 150),
                ("369", "00:20:07,000 --> 00:20:07,400", "elements.")]
        logged = []
        stats = gui._scan_delivery_blocks(
            blocks, cues, lambda message, level="": logged.append(message))
        self.assertEqual(stats["cue_fill"], 1)
        self.assertTrue(any("#369" in line and "#368" in line for line in logged))


if __name__ == "__main__":
    unittest.main()
