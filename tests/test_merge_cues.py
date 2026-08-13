"""
merge_fragmented_cues testleri — kelime-kelime bölünmüş (Amazon WEB-DL) altyazıları
güvenle birleştirme. Senkron korunmalı, cümle/diyalog/SDH sınırları aşılmamalı.
"""
import unittest

import subtitle_translator_gui as gui


def _vlen(t):
    return gui._visible_len(t)


class HelperTest(unittest.TestCase):
    def test_visible_len_strips_tags(self):
        self.assertEqual(gui._visible_len("<i>Merhaba</i>"), len("Merhaba"))
        self.assertEqual(gui._visible_len("{\\an8}Selam"), len("Selam"))
        self.assertEqual(gui._visible_len("a\nb"), 3)  # 'a b'

    def test_is_dialogue(self):
        self.assertTrue(gui._is_dialogue_cue("- Selam\n- Naber"))
        self.assertTrue(gui._is_dialogue_cue("- Tek konuşmacı tireli"))
        self.assertFalse(gui._is_dialogue_cue("Normal cümle"))

    def test_is_sdh_only(self):
        self.assertTrue(gui._is_sdh_only("[Laughing]"))
        self.assertTrue(gui._is_sdh_only("(sighs)"))
        self.assertTrue(gui._is_sdh_only("♪"))
        self.assertTrue(gui._is_sdh_only("_"))
        self.assertFalse(gui._is_sdh_only("Konuşma [gülüyor]"))


class MergeFragmentedCuesTest(unittest.TestCase):
    def test_real_example_two_fragment(self):
        blocks = [
            ("2", "00:00:05,706 --> 00:00:07,475", "Peki, ananla ne yapacaksın"),
            ("3", "00:00:07,475 --> 00:00:07,975", "ki?"),
            ("4", "00:00:14,715 --> 00:00:15,716", "Hurlan:"),
        ]
        out = gui.merge_fragmented_cues(blocks)
        self.assertEqual(len(out), 2)
        self.assertEqual(out[0][2], "Peki, ananla ne yapacaksın ki?")
        # Birleşik cue ilk start → ikinci end aralığını kapsar (senkron korunur)
        self.assertEqual(out[0][1], "00:00:05,706 --> 00:00:07,975")
        self.assertEqual(out[1][2], "Hurlan:")  # 6.7sn boşluk → ayrı kaldı

    def test_multi_fragment_chain_wraps_two_lines(self):
        b = [
            ("59", "00:02:32,953 --> 00:02:34,688", "Biliyorum, babam ölenden beri"),
            ("60", "00:02:34,688 --> 00:02:36,490", "işsizsin, ama benim için"),
            ("61", "00:02:36,490 --> 00:02:38,192", "birini öldürmen"),
            ("62", "00:02:38,192 --> 00:02:38,592", "lazım."),
            ("63", "00:02:38,592 --> 00:02:40,428", "Ancak sen de benim için"),
        ]
        out = gui.merge_fragmented_cues(b)
        self.assertEqual(len(out), 2)  # 4 parça → 1, + ayrı yeni cümle
        self.assertEqual(out[0][1], "00:02:32,953 --> 00:02:38,592")
        self.assertLessEqual(out[0][2].count("\n") + 1, 2)  # ≤2 satır
        self.assertIn("lazım.", out[0][2])
        self.assertEqual(out[1][2], "Ancak sen de benim için")

    def test_dialogue_not_merged(self):
        b = [("1", "00:00:01,000 --> 00:00:02,000", "- Selam"),
             ("2", "00:00:02,000 --> 00:00:03,000", "- Naber")]
        self.assertEqual(len(gui.merge_fragmented_cues(b)), 2)

    def test_sentence_end_not_merged(self):
        b = [("1", "00:00:01,000 --> 00:00:02,000", "Bitti."),
             ("2", "00:00:02,000 --> 00:00:03,000", "Devam")]
        self.assertEqual(len(gui.merge_fragmented_cues(b)), 2)

    def test_source_sentence_boundary_blocks_target_punctuation_merge(self):
        ts1 = "00:00:01,000 --> 00:00:02,000"
        ts2 = "00:00:02,000 --> 00:00:03,000"
        source = [("1", ts1, "Are you coming?"), ("2", ts2, "No.")]
        translated = [("1", ts1, "Geliyor musun"), ("2", ts2, "Hayır.")]

        out = gui.merge_fragmented_cues(translated, source_cues=source)

        self.assertEqual(len(out), 2)

    def test_source_fragment_pair_still_merges_when_target_has_no_punctuation(self):
        ts1 = "00:00:01,000 --> 00:00:02,000"
        ts2 = "00:00:02,000 --> 00:00:03,000"
        source = [("1", ts1, "Are you"), ("2", ts2, "coming?")]
        translated = [("1", ts1, "Geliyor musun"), ("2", ts2, "değil mi?")]

        out = gui.merge_fragmented_cues(translated, source_cues=source)

        self.assertEqual(len(out), 1)

    def test_source_fragment_pair_uses_timestamps_after_signature_renumbering(self):
        ts1 = "00:00:01,000 --> 00:00:02,000"
        ts2 = "00:00:02,000 --> 00:00:03,000"
        source = [("1", ts1, "Are you"), ("2", ts2, "coming?")]
        translated = [("2", ts1, "Geliyor musun"), ("3", ts2, "değil mi?")]

        out = gui.merge_fragmented_cues(translated, source_cues=source)

        self.assertEqual(len(out), 1)
        self.assertEqual(out[0][1], "00:00:01,000 --> 00:00:03,000")

    def test_sdh_not_merged(self):
        b = [("1", "00:00:01,000 --> 00:00:02,000", "[Kapı kapanır]"),
             ("2", "00:00:02,000 --> 00:00:03,000", "Merhaba")]
        self.assertEqual(len(gui.merge_fragmented_cues(b)), 2)

    def test_real_gap_not_merged(self):
        # 3 saniyelik boşluk (max_gap_ms=500 üstü) → birleşmez
        b = [("1", "00:00:01,000 --> 00:00:02,000", "devam eden"),
             ("2", "00:00:05,000 --> 00:00:06,000", "cümle")]
        self.assertEqual(len(gui.merge_fragmented_cues(b)), 2)

    def test_too_long_not_merged(self):
        long1 = "x" * 50
        long2 = "y" * 50  # toplam ~100 > 84
        b = [("1", "00:00:01,000 --> 00:00:02,000", long1),
             ("2", "00:00:02,000 --> 00:00:03,000", long2)]
        self.assertEqual(len(gui.merge_fragmented_cues(b)), 2)

    def test_italic_boundary_collapsed(self):
        b = [("1", "00:00:01,000 --> 00:00:02,000", "<i>devam eden</i>"),
             ("2", "00:00:02,000 --> 00:00:03,000", "<i>cümle</i>")]
        out = gui.merge_fragmented_cues(b)
        self.assertEqual(len(out), 1)
        self.assertNotIn("</i> <i>", out[0][2])  # italik sınırı toplanmış

    def test_renumbered_sequentially(self):
        b = [("5", "00:00:01,000 --> 00:00:02,000", "Bitti."),
             ("9", "00:00:02,000 --> 00:00:03,000", "Yeni cümle.")]
        out = gui.merge_fragmented_cues(b)
        self.assertEqual([x[0] for x in out], ["1", "2"])  # yeniden numaralandı

    def test_empty_and_single(self):
        self.assertEqual(gui.merge_fragmented_cues([]), [])
        one = [("1", "00:00:01,000 --> 00:00:02,000", "Tek blok")]
        self.assertEqual(gui.merge_fragmented_cues(one), one)


class MergeAdversarialFixesTest(unittest.TestCase):
    """Adversaryal denetimde bulunan 5 kenar durumun regresyon testleri."""

    def test_cps_guard_blocks_unreadable_merge(self):
        # 6 cue × 13 karakter × 0.2sn span → her birleşme ~67 cps (okunamaz) olurdu;
        # CPS guard hiçbirini birleştirmemeli (tek cue'lar kaynaktan geldiği gibi kalır)
        ts = ["00:00:00,000 --> 00:00:00,200", "00:00:00,200 --> 00:00:00,400",
              "00:00:00,400 --> 00:00:00,600", "00:00:00,600 --> 00:00:00,800",
              "00:00:00,800 --> 00:00:01,000", "00:00:01,000 --> 00:00:01,200"]
        b = [(str(i + 1), ts[i], "kelimebir bes") for i in range(6)]  # 13 görünür karakter
        out = gui.merge_fragmented_cues(b)
        self.assertEqual(len(out), 6)  # hiç birleşme olmadı (her birleşme CPS'i aşardı)

    def test_cps_ok_realistic_merge_still_happens(self):
        # Gerçekçi: 30 karakter 2.3sn → ~13 cps → birleşmeli
        b = [("1", "00:00:05,706 --> 00:00:07,475", "Peki, ananla ne yapacaksın"),
             ("2", "00:00:07,475 --> 00:00:07,975", "ki?")]
        self.assertEqual(len(gui.merge_fragmented_cues(b)), 1)

    def test_an8_position_tag_not_duplicated_midtext(self):
        b = [("1", "00:00:01,000 --> 00:00:02,000", "{\\an8}devam eden"),
             ("2", "00:00:02,000 --> 00:00:03,000", "{\\an8}cümle")]
        out = gui.merge_fragmented_cues(b)
        self.assertEqual(len(out), 1)
        # {\an8} yalnızca başta olmalı, ortada tekrarlanmamalı
        self.assertEqual(out[0][2].count("{\\an8}"), 1)
        self.assertTrue(out[0][2].startswith("{\\an8}"))

    def test_dialogue_dash_behind_italic_not_merged(self):
        b = [("1", "00:00:01,000 --> 00:00:02,000", "<i>- Selam"),
             ("2", "00:00:02,000 --> 00:00:03,000", "<i>- Naber")]
        self.assertEqual(len(gui.merge_fragmented_cues(b)), 2)

    def test_multiline_source_rebalanced(self):
        b = [("1", "00:00:01,000 --> 00:00:02,000", "Kısa\nuzunca bir ilk parça burada"),
             ("2", "00:00:02,000 --> 00:00:03,000", "devamı")]
        out = gui.merge_fragmented_cues(b)
        self.assertEqual(len(out), 1)
        # İç newline yeniden dengelendi (eski kötü kırılma kalmadı), ≤2 satır
        self.assertLessEqual(out[0][2].count("\n"), 1)
        self.assertIn("devamı", out[0][2].replace("\n", " "))

    def test_empty_leading_cue_no_leading_space(self):
        b = [("1", "00:00:01,000 --> 00:00:02,000", ""),
             ("2", "00:00:02,000 --> 00:00:03,000", "merhaba")]
        out = gui.merge_fragmented_cues(b)
        self.assertEqual(out[0][2], out[0][2].strip())  # baş/son boşluk yok
        self.assertNotIn("\n ", out[0][2])

    def test_input_not_mutated(self):
        import copy
        b = [("1", "00:00:01,000 --> 00:00:02,000", "devam eden"),
             ("2", "00:00:02,000 --> 00:00:02,500", "cümle")]
        snapshot = copy.deepcopy(b)
        gui.merge_fragmented_cues(b)
        self.assertEqual(b, snapshot)  # girdi mutasyona uğramadı (TM/scan güvenli)


if __name__ == "__main__":
    unittest.main()
