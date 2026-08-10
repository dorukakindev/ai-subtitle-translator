"""final_consistency_sweep (hybrid_translate.py) — first_seen fallback kaldırıldı
(bkz. plans/quality-quickwins-brief.md Görev 1). Majority sweep bir çoğunluk
BULAMADIĞINDA artık ilk görülen çeviriyi diğer tekrarlara dayatmıyor (bağlam-kördü,
ör. "Come on." sahneye göre farklı çevrilebilir). Majority BULUNDUĞUNDA ise
(Branch B) davranış aynı: `validate_polish_candidate` ile yeniden doğrulanarak
güvenli biçimde normalize edilir.
"""
import unittest

import hybrid_translate as ht


class NoMajorityLeavesUnchangedTest(unittest.TestCase):
    def test_three_way_split_untouched(self):
        # Aynı kaynak (>=3 kelime) 3 farklı çeviriyle — hiçbir çoğunluk yok.
        # Eskiden first_seen ilkini dayatırdı; artık DOKUNULMAMALI.
        cues = [
            ("1", "00:00:01,000 --> 00:00:02,000", "Come on now."),
            ("2", "00:00:02,000 --> 00:00:03,000", "Different line."),
            ("3", "00:00:03,000 --> 00:00:04,000", "Come on now."),
            ("4", "00:00:04,000 --> 00:00:05,000", "Come on now."),
        ]
        blocks = [
            ("1", "00:00:01,000 --> 00:00:02,000", "Hadi ama."),
            ("2", "00:00:02,000 --> 00:00:03,000", "Başka satır."),
            ("3", "00:00:03,000 --> 00:00:04,000", "Yapma şimdi."),
            ("4", "00:00:04,000 --> 00:00:05,000", "Hadi gidelim."),
        ]
        swept, fixes = ht.final_consistency_sweep(cues, blocks)
        self.assertEqual(fixes, 0)
        self.assertEqual([b[2] for b in swept], [b[2] for b in blocks])


class MajorityStillNormalizesTest(unittest.TestCase):
    def test_three_vs_one_normalizes_to_majority(self):
        cues = [
            ("1", "00:00:01,000 --> 00:00:02,000", "This is a test line."),
            ("2", "00:00:02,000 --> 00:00:03,000", "This is a test line."),
            ("3", "00:00:03,000 --> 00:00:04,000", "Unrelated line here."),
            ("4", "00:00:04,000 --> 00:00:05,000", "This is a test line."),
            ("5", "00:00:05,000 --> 00:00:06,000", "This is a test line."),
        ]
        blocks = [
            ("1", "00:00:01,000 --> 00:00:02,000", "Bu bir test satırı."),
            ("2", "00:00:02,000 --> 00:00:03,000", "Bu bir test satırı."),
            ("3", "00:00:03,000 --> 00:00:04,000", "Alakasız satır burada."),
            ("4", "00:00:04,000 --> 00:00:05,000", "Bu bir test satırıdır."),
            ("5", "00:00:05,000 --> 00:00:06,000", "Bu bir test satırı."),
        ]
        swept, fixes = ht.final_consistency_sweep(cues, blocks)
        self.assertEqual(swept[3][2], "Bu bir test satırı.")
        self.assertGreaterEqual(fixes, 1)

    def test_majority_name_error_does_not_overwrite_source_correct_minority(self):
        cues = [
            ("1", "00:00:01,000 --> 00:00:02,000", "Mary arrived."),
            ("2", "00:00:02,000 --> 00:00:03,000", "Mary arrived."),
            ("3", "00:00:03,000 --> 00:00:04,000", "Mary arrived."),
        ]
        blocks = [
            ("1", "00:00:01,000 --> 00:00:02,000", "John geldi."),
            ("2", "00:00:02,000 --> 00:00:03,000", "John geldi."),
            ("3", "00:00:03,000 --> 00:00:04,000", "Mary geldi."),
        ]

        swept, fixes = ht.consistency_sweep(cues, blocks)

        self.assertEqual(swept, blocks)
        self.assertEqual(fixes, 0)


class ShortSourceNeverTouchedTest(unittest.TestCase):
    def test_below_min_words_untouched_even_with_repeats(self):
        cues = [
            ("1", "00:00:01,000 --> 00:00:02,000", "Come on."),
            ("2", "00:00:02,000 --> 00:00:03,000", "Come on."),
            ("3", "00:00:03,000 --> 00:00:04,000", "Come on."),
        ]
        blocks = [
            ("1", "00:00:01,000 --> 00:00:02,000", "Hadi ama."),
            ("2", "00:00:02,000 --> 00:00:03,000", "Yapma şimdi."),
            ("3", "00:00:03,000 --> 00:00:04,000", "Hadi gidelim."),
        ]
        swept, fixes = ht.final_consistency_sweep(cues, blocks)
        self.assertEqual(fixes, 0)
        self.assertEqual([b[2] for b in swept], [b[2] for b in blocks])


if __name__ == "__main__":
    unittest.main()
