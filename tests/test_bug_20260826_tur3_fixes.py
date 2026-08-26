# -*- coding: utf-8 -*-
"""Tur 3: olumsuzluk sayacı, özel ad hitabı, 'processed by' künyesi."""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import hybrid_translate as ht
import subtitle_formats as sf
import subtitle_translator_gui as g


class OrdinaryWordsAreNotNegationTest(unittest.TestCase):
    """Sayaç, gövdesi serbest bırakılmış bir desenle 'ma/me' arıyordu; gövde
    SIFIR harf de olabildiği için 'Memnun' ('' + me + m), 'Mezar' ('' + me +
    z), 'Amazon' ('A' + ma + z) olumsuz sayılıyordu. 'sakın' ise
    re.IGNORECASE altında 'sakin' ile eşleşiyordu.

    Sayaç, Polish ve Condense adaylarının olumsuzluk DÜŞÜRMESİNİ engelleyen
    guard'ı besliyor: yanlış taban, gerçek olumsuzluğu koruyan doğru bir
    adayı reddettirebiliyor.

    284.076 gerçek cue ölçüldü: 326 dosyada 4.518 yanlış sayım düştü,
    artan sayım 0.
    """

    def test_the_measured_false_positives(self):
        for text in ("Tamam.", "Tamamen farklı.", "Sakin ol.", "Memnun oldum.",
                     "Mezar taşı.", "Agamemnon geldi.", "Amazon nehri.",
                     "Tamamdır.", "Sakince yürüdü."):
            with self.subTest(text=text):
                self.assertEqual(ht.reliable_turkish_negation_count(text), 0)

    def test_real_negation_still_counts(self):
        for text in ("Gelmedi.", "Yapmam.", "Gitmez.", "Olmadı.", "demedi",
                     "Yemem.", "gelmeyen adam", "Sakın gitme!", "Değil.",
                     "Gelmiyor.", "yapmayacağım", "olmayabilir"):
            with self.subTest(text=text):
                self.assertGreaterEqual(
                    ht.reliable_turkish_negation_count(text), 1)

    def test_two_negations_are_two(self):
        self.assertEqual(ht.reliable_turkish_negation_count("Hiç yok."), 2)


class ProperNamesAreNotSecondPersonTest(unittest.TestCase):
    """'-din/-sen/-tin' ile biten özel adlar ikinci tekil hitap sayılıyordu;
    14 dosyada 61 cue yanlış 'samimi' işaretlendi ve 2 dosyanın karışık
    hitap kararını ters çevirdi.

    Konuma bakan bir kural denendi ve ÖLÇÜM REDDETTİ: altyazıda replikler
    tire ile başladığı için 'cümle ortasında büyük harf' ölçütü
    'Affedersin', 'Anladın', 'Bilirsin' gibi 366 GERÇEK hitabı da eliyordu.
    Ölçülen adlar mevcut TR_ADDRESS_FALSE_STEMS mekanizmasına eklendi;
    arşivde 22 dosyada 92 token.
    """

    def test_the_measured_names(self):
        for name in ("Andersen", "Petersen", "Augustin", "Odin", "Bardin",
                     "Sikhandin", "Myrddin", "Austin", "Rodin", "Verdun",
                     "Ürdün"):
            with self.subTest(name=name):
                self.assertFalse(sf.is_turkish_second_person_token(name))

    def test_real_second_person_survives(self):
        for word in ("geldin", "yaptın", "sordun", "Affedersin", "Anladın",
                     "Bilirsin", "Neredeydin", "gittin"):
            with self.subTest(word=word):
                self.assertTrue(sf.is_turkish_second_person_token(word))

    def test_dialogue_lines_still_count_as_informal(self):
        ts = "00:00:01,000 --> 00:00:03,000"
        result = g.detect_address_register_mix(
            [("1", ts, "- Affedersin. - Anladın mı?")], min_total=0)
        self.assertEqual(result["informal"], 1)


class ProcessedByNeedsCreditContextTest(unittest.TestCase):
    """'processed by' tek başına künye değildi: edilgen bir anlatı cümlesi
    ('ARE PROCESSED BY THE BRAIN...') künye sayılıp kaynağı silinebilir
    işaretleniyordu. Dal 3 kez ateşliyor, 2'si yanlıştı.

    Gerçek künye ya satır başındadır ('Processed by C.M.C. - Paris',
    test_upload_ready_finalization ile kilitli) ya da altyazıdan söz eder.
    """

    def test_narrative_passive_is_not_a_credit(self):
        for text in ("ARE PROCESSED BY THE BRAIN AT DIFFERENT SPEEDS.",
                     "The data is processed by the computer."):
            with self.subTest(text=text):
                self.assertFalse(g._is_delivery_credit(text))
                self.assertFalse(g._source_cue_is_delivery_removable(text))

    def test_a_line_initial_credit_still_matches(self):
        self.assertTrue(g._is_delivery_credit("Processed by C.M.C. - Paris"))

    def test_a_subtitle_credit_still_matches(self):
        self.assertTrue(
            g._is_delivery_credit("Subtitle ripped and processed by someone"))
        self.assertTrue(g._is_delivery_credit("Subs processed by TeamX"))


if __name__ == "__main__":
    unittest.main()
