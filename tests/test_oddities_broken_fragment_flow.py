"""Oddities broken cross-cue flow guards from real S05E08 output."""

import unittest

import hybrid_translate as ht


_APPLY = lambda text: ht._apply_local_fixes(text)[0]


def _reasons(blocks):
    hits = ht.run_validators(blocks)
    return {str(idx): reason for idx, _ts, _text, reason in hits}


class BrokenFragmentFlowTest(unittest.TestCase):
    def test_flags_now_living_here_dangling_after_visit_line(self):
        blocks = [
            (102, "00:00:01,000 --> 00:00:02,000", "ben de aşağıda yaşayan eski bir müzisyen arkadaşımı ziyarete gidiyorum"),
            (103, "00:00:02,000 --> 00:00:03,000", "şimdi burada yaşayan."),
        ]
        self.assertIn("BROKEN_FRAGMENT_FLOW", _reasons(blocks).get("103", ""))

    def test_does_not_flag_now_living_here_without_context(self):
        blocks = [
            (1, "00:00:01,000 --> 00:00:02,000", "New Orleans çok güzel."),
            (2, "00:00:02,000 --> 00:00:03,000", "şimdi burada yaşayan."),
        ]
        self.assertNotIn("2", _reasons(blocks))

    def test_flags_stranded_title_name_after_display_line(self):
        blocks = [
            (300, "00:00:01,000 --> 00:00:02,000", "burada yerleşik topluluğumuzun çalışmalarını sergiliyoruz,"),
            (301, "00:00:02,000 --> 00:00:03,000", "adı THE MUDLARK PUPPETEERS."),
        ]
        self.assertIn("BROKEN_FRAGMENT_FLOW", _reasons(blocks).get("301", ""))

    def test_flags_en_biraz_case_flow(self):
        blocks = [
            (310, "00:00:01,000 --> 00:00:02,000", "Bana ne yapacağından en biraz korktum."),
        ]
        self.assertIn("BROKEN_FRAGMENT_FLOW", _reasons(blocks).get("310", ""))

    def test_flags_bilime_doktuk_after_intro_fragment(self):
        blocks = [
            (23, "00:00:01,000 --> 00:00:02,000", "bu işi..."),
            (24, "00:00:02,000 --> 00:00:03,000", "bilime döktük."),
        ]
        self.assertIn("BROKEN_FRAGMENT_FLOW", _reasons(blocks).get("24", ""))


class BrokenFragmentLocalFixTest(unittest.TestCase):
    def test_en_biraz_local_fix(self):
        self.assertEqual(_APPLY("Bana ne yapacağından en biraz korktum."), "Bana ne yapacağından biraz korktum.")

    def test_mudlark_adi_local_fix(self):
        self.assertEqual(_APPLY("adı THE MUDLARK PUPPETEERS."), "adı da THE MUDLARK PUPPETEERS.")

    def test_mudlark_adi_does_not_touch_other_name(self):
        self.assertEqual(_APPLY("adı Henry."), "adı Henry.")


if __name__ == "__main__":
    unittest.main()
