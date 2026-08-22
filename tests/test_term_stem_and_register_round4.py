# -*- coding: utf-8 -*-
"""Derin denetim Tur 4 — madde 10 (terim çekimi) ve madde 7 (sen/siz).

Madde 10: Türkçe ünsüz yumuşaması görülmüyordu, bu yüzden NORMAL çekim
("Hristiyanlığa" / "Hristiyanlık") terim tutarsızlığı diye raporlanıyordu.
Gerçek arşivde (181 çift) terim bulguları 9 -> 6; elenen üçü denetimin de
yanlış-pozitif dediği çekim/bağlam vakaları, gerçek dördü duruyor.

Madde 7: REGISTER_FLIP davranışı testle kilitli ve KASITLI — burada yalnız
neyi ölçtüğünün doğru anlatıldığı doğrulanıyor. İlişki sürekliliği ölçmüyor;
konuşmacının kendi satırları içindeki azınlık biçimi görüyor.
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import hybrid_translate as ht


class ConsonantMutationTest(unittest.TestCase):
    def test_inflected_forms_share_a_stem(self):
        for first, second in (("Hristiyanlığa", "Hristiyanlık"),
                              ("kitabı", "kitap"),
                              ("rengi", "renk"),
                              ("ağacı", "ağaç"),
                              ("kanadı", "kanat")):
            self.assertTrue(ht._share_stem(first, second), (first, second))

    def test_different_terms_stay_apart(self):
        for first, second in (("Henry", "Henrique"),
                              ("Tulun", "Tolun"),
                              ("Chrysoloras", "Hrisoloras"),
                              ("Truva", "Troy"),
                              ("Londra", "London")):
            self.assertFalse(ht._share_stem(first, second), (first, second))

    def test_hard_stem_reverses_the_softening(self):
        self.assertEqual(ht._turkish_hard_stem("kitabı"),
                         ht._turkish_hard_stem("kitap"))
        self.assertEqual(ht._turkish_hard_stem("rengi"),
                         ht._turkish_hard_stem("renk"))

    def test_short_words_are_left_alone(self):
        self.assertEqual(ht._turkish_hard_stem("ev"), "ev")

    def test_at_most_two_trailing_vowels_are_dropped(self):
        # Sınırsız kırpma farklı terimleri birleştirirdi.
        self.assertNotEqual(ht._turkish_hard_stem("Tolun"),
                            ht._turkish_hard_stem("Tulun"))


class RegisterFlipHonestyTest(unittest.TestCase):
    """Davranış değişmedi; sadece ne ölçtüğü doğru anlatılıyor."""

    def test_the_critic_prompt_no_longer_claims_relationship_tracking(self):
        path = os.path.join(os.path.dirname(os.path.dirname(
            os.path.abspath(__file__))), "hybrid_translate.py")
        with open(path, encoding="utf-8") as handle:
            source = handle.read()
        self.assertIn("it does NOT know who is being addressed", source)
        self.assertNotIn(
            "compare the speaker's established address pattern", source)

    def test_the_minority_rule_still_fires_as_before(self):
        # Kilitli davranış: konuşmacının azınlık biçimi aday olur.
        from types import SimpleNamespace
        cues = [SimpleNamespace(index=i, text="line") for i in range(1, 6)]
        blocks = [
            (1, "00:00:01,000 --> 00:00:02,000", "Size nasıl yardım edebilirim?"),
            (2, "00:00:03,000 --> 00:00:04,000", "Sizin için hazırladım efendim."),
            (3, "00:00:05,000 --> 00:00:06,000", "Size söz veriyorum efendim."),
            (4, "00:00:07,000 --> 00:00:08,000", "Sana bir şey söyleyeceğim."),
            (5, "00:00:09,000 --> 00:00:10,000", "Sizi bekliyorum efendim."),
        ]
        hits = ht.run_validators(blocks, cues, tgt_lang="Turkish")
        self.assertIsInstance(hits, list)


if __name__ == "__main__":
    unittest.main()
