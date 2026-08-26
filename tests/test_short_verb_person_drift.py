# -*- coding: utf-8 -*-
"""Kisa (iki harfli) fiil koklerinde kisi kaymasi.

Turkcenin en sik fiilleri iki harflidir (et-, de-, ye-, ol-, um-) ve kisi
imzasi desenleri uc harflik govde istedigi icin bu ailenin tamami guard'a
gorunmuyordu: 'tesekkur ediyorum' -> 'tesekkur ediyor' gecip gidiyordu.
'et-' ayrica butun birlesik fiil ailesini tasidigi icin bosluk buyuktu.
"""
import unittest

import hybrid_translate as ht


class ShortVerbPersonSignatureTest(unittest.TestCase):
    def test_two_letter_stems_get_a_signature(self):
        for word, expected in (
            ("ediyorum", ("ed", "present_1sg")),
            ("ediyor", ("ed", "present_3sg")),
            ("umuyorum", ("um", "present_1sg")),
            ("umuyor", ("um", "present_3sg")),
            ("olacağım", ("ol", "future_1sg")),
            ("olacak", ("ol", "future_3sg")),
        ):
            with self.subTest(word=word):
                self.assertEqual(ht._turkish_person_signature(word), expected)

    def test_three_letter_stems_still_work(self):
        self.assertEqual(ht._turkish_person_signature("yapıyorum"),
                         ("yap", "present_1sg"))
        self.assertEqual(ht._turkish_person_signature("geldim"),
                         ("gel", "past_1sg"))

    def test_ordinary_nouns_do_not_get_a_verb_signature(self):
        # Esigi toptan ikiye indirmek 'kadın' -> 'ka'+'dı'+'n' gibi sahte
        # past_2sg imzalari uretirdi; izin yalniz gercek fiil koklerinde.
        for word in ("kadın", "aydın", "odun", "düğün", "bütün"):
            with self.subTest(word=word):
                self.assertIsNone(ht._turkish_person_signature(word))


class ShortVerbPersonDriftTest(unittest.TestCase):
    def test_first_to_third_person_is_rejected(self):
        for original, candidate in (
            ("Bunun için sana teşekkür ediyorum.",
             "Bunun için sana teşekkür ediyor."),
            ("Gerçeği ortaya çıkarmayı umuyorum.",
             "Gerçeği ortaya çıkarmayı umuyor."),
            ("Yarın orada olacağım.", "Yarın orada olacak."),
        ):
            with self.subTest(original=original):
                self.assertTrue(
                    ht._has_turkish_person_drift(original, candidate, ""))

    def test_polish_guard_rejects_the_shift(self):
        ok, reason = ht.validate_polish_candidate(
            "Bunun için sana teşekkür ediyorum.",
            "Bunun için sana teşekkür ediyor.",
            source_text="I thank you for this.",
            tgt_lang="Turkish",
        )
        self.assertFalse(ok)
        self.assertEqual(reason, "person_drift")

    def test_untouched_person_is_not_rejected(self):
        self.assertFalse(ht._has_turkish_person_drift(
            "Bunun için sana teşekkür ediyorum.",
            "Bunun için size teşekkür ediyorum.",
            "",
        ))


if __name__ == "__main__":
    unittest.main()
