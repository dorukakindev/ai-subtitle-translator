# -*- coding: utf-8 -*-
"""22 filmlik teslimin satır satır denetiminden çıkan kod bulguları.

Kaynak: `plans/teslim-20260827-kod-bulgulari-brief.md` (Opus, 2026-08-28).
Ölçümler programın ürettiği hal (`*.pre-opus-20260828.srt`) üzerinden.
"""
import unittest

import sdh_cleaner as sdh
import subtitle_translator_gui as gui


class BrokenItalicTest(unittest.TestCase):
    """Madde 3: bozuk kaynak italiği teslimde 4 seviyeye çıkıyordu.

    São Bernardo #837/#894. `restore_format_tags` dengesiz çıktı veriyor
    (`<i>`×2, `</i>`×4), teslim hazırlığı onu 4/4 iç içe hâle "dengeliyordu".
    """

    def _delivered(self, text):
        return gui._prepare_upload_ready_blocks(
            [("1", "00:00:05,000 --> 00:00:07,000", text)], "Turkish")[0][2]

    def test_nested_italics_collapse_to_one_outer_pair(self):
        got = self._delivered(
            "<i>Ben kuruyorum,\n<i>o yıkıyor!</i></i></i></i>")
        self.assertEqual(got, "<i>Ben kuruyorum,\no yıkıyor!</i>")

    def test_healthy_italics_are_untouched(self):
        for text in ("<i>Tamamen italik.</i>",
                     "Dedi ki <i>hayır</i> ve gitti.",
                     "<i>Satır bir</i>\n<i>Satır iki</i>",
                     "Hiç etiket yok."):
            with self.subTest(text=text):
                self.assertEqual(self._delivered(text), text)

    def test_detector_flags_only_broken_nesting(self):
        self.assertTrue(gui._italic_nesting_is_broken("<i><i>Canary</i></i>"))
        self.assertTrue(gui._italic_nesting_is_broken("<i>Açık kaldı."))
        self.assertFalse(gui._italic_nesting_is_broken("<i>Sağlam.</i>"))
        self.assertFalse(gui._italic_nesting_is_broken("Etiketsiz."))

    def test_finding_class_is_registered(self):
        self.assertIn("broken_italic_ids", gui._FINDING_CLASSES)


class MixedCapsLabelTest(unittest.TestCase):
    """Madde 2b: diyalogla aynı cue'daki BÜYÜK HARF SDH etiketi.

    Etiket çeviriye giriyor ve Türkçe olarak dönüyordu (`SHE LAUGHS`→`GÜLER`).
    Kural dile bağımsız olduğu için iki biçimi de teslimde yakalar.

    Ölçüm: 2 milyon kaynak cue'da kolonsuz biçimin 21 adayı vardı; kalanda
    başka caps sözcük arama kaydıyla 17/17 doğru. Teslim tarafında canlı
    kalıntı 14 cue'ydu ve hepsi gerçek etiketti.
    """

    def test_sound_label_before_dialogue_is_stripped(self):
        for text, expected in (
                ("HE WHISTLES She's a smasher.", "She's a smasher."),
                ("ISLIK ÇALAR Taş gibiymiş.", "Taş gibiymiş."),
                ("KUKLA: İn aşağı!", "İn aşağı!"),
                ("CEMAAT: Evet yapabilir!", "Evet yapabilir!")):
            with self.subTest(text=text):
                got, hit = sdh.strip_mixed_caps_label(text)
                self.assertTrue(hit)
                self.assertEqual(got, expected)

    def test_standalone_caps_cue_is_left_alone(self):
        """Tek başına caps cue etiket mi tabela mı ayırt edilemez."""
        for text in ("SATILIK", "EUROPCAR CAR RENTAL", "KURU TEMİZLEME",
                     "SHE LAUGHS"):
            with self.subTest(text=text):
                self.assertEqual(sdh.strip_mixed_caps_label(text), (text, False))

    def test_mixed_case_title_is_not_a_label(self):
        """Kalanda başka caps sözcük varsa bu bir BAŞLIKTIR, etiket değil."""
        for text in ("HER ŞEYİ BİR Gergedan GİBİ",
                     "VE TAJINDER’İN Nektar Havuzu’NDA"):
            with self.subTest(text=text):
                self.assertEqual(sdh.strip_mixed_caps_label(text), (text, False))

    def test_initials_and_single_letters_are_not_labels(self):
        for text in ("H G Wells gibi aydınlar da öyleydi.",
                     "O Pat Sharp mı?",
                     "Normal bir cümle burada duruyor."):
            with self.subTest(text=text):
                self.assertEqual(sdh.strip_mixed_caps_label(text), (text, False))

    def test_delivery_applies_it(self):
        got = gui._prepare_upload_ready_blocks(
            [("1", "00:00:05,000 --> 00:00:07,000", "KUKLA: İn aşağı!")],
            "Turkish")[0][2]
        self.assertEqual(got, "İn aşağı!")


class RepetitionCollapseTest(unittest.TestCase):
    """Madde 1: cue içi tekrar çöküşü (What Happened Was #1770/#1775/#1776).

    Ham kuralın isabeti %14'tü (21 adayın 18'i kaynağın retorik tekrarı).
    Üç eleme birlikte: ünlem listesi, ≥5 tekrar, kaynakta n-gram tekrarı yok.
    Ölçüm: 3/3 gerçek yakalandı, 317 kaynak eşli teslimde 0 yanlış alarm.
    """

    def _flag(self, translated, source):
        return bool(gui._repetition_collapse_ids(
            [("1", "x", translated)], {"1": source}))

    def test_model_degeneration_is_caught(self):
        for translated, source in (
                ("Yani, işte işte işte işte işte işte işte işte",
                 "I mean, I know it's gonna be uncomfortable at work,"),
                ("O zaman işte işte işte işte işte işte işte işte işte",
                 "So, I'll see you at work."),
                ("-İşte işte işte işte işte işte işte işte işte işte",
                 "-See you at work.")):
            with self.subTest(translated=translated[:24]):
                self.assertTrue(self._flag(translated, source))

    def test_faithful_repetition_is_not_flagged(self):
        for translated, source in (
                ("Para... para... PARA!", "Money... money... MONEY!"),
                ("Defol! Defol! Defol!", "Get out! Get out! Get out!"),
                ("Korkuyorum! Korkuyorum! Korkuyorum!",
                 "I'm scared! I'm scared! I'm scared!")):
            with self.subTest(translated=translated[:24]):
                self.assertFalse(self._flag(translated, source))

    def test_source_unit_may_be_longer_than_one_word(self):
        """`to you, to you, to you` → tekrar birimi iki sözcük."""
        self.assertFalse(
            self._flag("Sana, sana, sana sana, sana",
                       "To you, to you, to you"))

    def test_apostrophe_split_source_still_counts_as_repetition(self):
        """`I won't go.` `\\w+` ile dört jeton; n-gram sınırı 4 olmalı."""
        self.assertFalse(
            self._flag(
                "Gitmeyeceğim. Gitmeyeceğim. Gitmeyeceğim. Gitmeyeceğim.",
                "I won't go. I won't go. I won't go. I won't go."))

    def test_interjections_and_lyrics_are_exempt(self):
        for text in ("La la la la la la la",
                     "Vay, vay, vay, vay, vay, vay",
                     "Evet, evet, evet, evet, evet"):
            with self.subTest(text=text):
                self.assertEqual(
                    gui._repetition_collapse_ids([("1", "x", text)], {}), [])

    def test_finding_class_is_registered(self):
        self.assertIn("repetition_collapse_ids", gui._FINDING_CLASSES)
        self.assertEqual(
            gui._FINDING_CLASSES["repetition_collapse_ids"][0], "kesin")


class EnglishFillerTest(unittest.TestCase):
    """Madde 4: `um` / `uh` çevrilmeden kalıyor (What Happened Was, 6 cue)."""

    def test_filler_is_flagged(self):
        for text in ("Şey, uh, bazen, evet.",
                     "çünkü, um--",
                     "uh...",
                     "Yeah, olabilir"):
            with self.subTest(text=text):
                self.assertTrue(gui._ENGLISH_FILLER_RE.search(text))

    def test_turkish_suffix_after_a_quote_is_not_a_filler(self):
        """`"Los Panchos"um.` — tırnak da sözcük sınırı sayılmalı."""
        self.assertIsNone(
            gui._ENGLISH_FILLER_RE.search('Hayır, ben "Los Panchos"um.'))

    def test_word_boundary_holds_inside_turkish_words(self):
        for text in ("Rivetot'um burada.", "Umut kesilmez.", "Ruhum daraldı."):
            with self.subTest(text=text):
                self.assertIsNone(gui._ENGLISH_FILLER_RE.search(text))

    def test_finding_class_is_registered(self):
        self.assertIn("english_filler_ids", gui._FINDING_CLASSES)


if __name__ == "__main__":
    unittest.main()
