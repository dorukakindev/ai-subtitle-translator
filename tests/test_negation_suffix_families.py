# -*- coding: utf-8 -*-
"""Olumsuzluğu ek üzerinden taşıyan biçimler de sayılır."""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import hybrid_translate as ht


class SuffixCarriedNegationIsCountedTest(unittest.TestCase):
    """Sayaç yalnız bitmiş fiil çekimlerini görüyordu.

    Ölçüm: 202 gerçek teslimde (148.662 cue) 1.185 yeni biçim yakalandı,
    rastgele 24 örneğin 24'ü gerçek olumsuzluktu; olumsuzluk görülebilen
    cue 26.249 -> 27.092. Bedeli iki yönlü ölçüldü: kullanıcının kabul
    ettiği 770 ham->nihai değişikliğinde 'olumsuzluk düşürüldü' kararı
    85 -> 86, yani tek bir ek red (o da gerçek bir yakalama).
    """

    REAL = (
        ("olmayan", "-mAyAn sıfat-fiili"),
        ("benzeri olmayan", "-mAyAn, ayrı sözcükle"),
        ("gelmeyişi", "-mAyIş isim-fiili"),
        ("vermeyişinin sebebi", "-mAyIş, iyelik ekli"),
        ("olmayalım", "-mAyAlIm istek kipi"),
        ("olmayabilirler", "-mAyAbil yeterlilik"),
        ("kopyalayamayacağı", "yumuşamış gelecek zaman"),
        ("gitmeyerek", "-mAyArAk zarf-fiili"),
        ("bilinmeyen", "edilgen + -mAyAn"),
        ("yaşlanmayacağımızı", "dönüşlü + gelecek"),
    )

    # Bu sözcüklerde 'ma'/'me' hecesi var ama olumsuzluk YOK.
    TRAPS = ("Mayan uygarlığı", "Mayıs ayında", "maya kültürü", "Almanya",
             "Himalaya", "kumaş boyayan usta", "deneyen", "sayan makine",
             "meyve", "yayan gitti")

    def test_suffix_carried_negation_is_seen(self):
        for text, why in self.REAL:
            with self.subTest(why=why):
                self.assertGreaterEqual(
                    ht.reliable_turkish_negation_count(text), 1)

    def test_ordinary_words_are_not_negations(self):
        for text in self.TRAPS:
            with self.subTest(text=text):
                self.assertEqual(ht.reliable_turkish_negation_count(text), 0)

    def test_a_two_letter_stem_is_required(self):
        # 'Mayan' bunsuz 'ma' + 'yan' diye olumsuz sayılırdı.
        self.assertEqual(ht.reliable_turkish_negation_count("Mayan"), 0)
        self.assertEqual(ht.reliable_turkish_negation_count("olmayan"), 1)

    def test_the_previously_known_forms_still_count(self):
        for text in ("gitmedim", "gelmiyor", "değil", "yok", "hiçbir şey",
                     "yapamam", "bilmemek"):
            with self.subTest(text=text):
                self.assertGreaterEqual(
                    ht.reliable_turkish_negation_count(text), 1)

    def test_a_dropped_negation_is_now_visible_to_the_guard(self):
        # Polish/Condense guard'ı bu sayaca bakıyor; 'gelmeyişi' -> 'gelişi'
        # eskiden iki tarafta da 0 döndüğü için fark edilmiyordu.
        self.assertGreater(ht.reliable_turkish_negation_count("gelmeyişi"),
                           ht.reliable_turkish_negation_count("gelişi"))

    def test_the_guard_still_reads_this_counter(self):
        import inspect
        source = inspect.getsource(ht.validate_polish_candidate)
        self.assertIn("reliable_turkish_negation_count", source)


if __name__ == "__main__":
    unittest.main()
