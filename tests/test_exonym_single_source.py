# -*- coding: utf-8 -*-
"""Egzonim kararı tek tablodan gelsin, uzun ada dokunmasın.

İki ayrı liste vardı: `prompt_constants.FOREIGN_EXONYM_MAP` (otomatik
düzeltmeyi süren) ve GUI'de ayrı bir tespit tablosu. Modern ülke adları
yalnız ikincisine eklenmişti, yani otomatik düzeltme onları göremiyordu.
Tespit tablosu artık paylaşılan tablodan TÜRETİLİYOR; üstüne yalnız
açıkça gerekçelendirilmiş bir genişletme biniyor.

Ayrı bir kusur: ek şartı (`China'daki` biçimi) tek başına yetmiyordu.
Gerçek arşivde `Historic England'ın` → `Historic İngiltere'nin` ve
`New Mexico'da` → `New Meksika'da` çıkıyordu — biri kurum, biri ABD
eyaleti. Ölçüm: eski tabloyla bile dokunulan cue 29 → 22 (7 yanlış
yeniden yazma engellendi); yeni tabloyla 34.
"""
import unittest

import subtitle_translator_gui as g
from prompt_constants import FOREIGN_EXONYM_MAP


class ExonymTableSourceTest(unittest.TestCase):
    def test_detection_table_covers_the_shared_map(self):
        for name, turkish in FOREIGN_EXONYM_MAP.items():
            if not name.isascii():
                continue
            if name.title().casefold() == turkish.casefold():
                continue
            with self.subTest(name=name):
                self.assertEqual(g._EXONYM_TR.get(name.title()), turkish)

    def test_no_identity_mapping_anywhere(self):
        for table in (FOREIGN_EXONYM_MAP, g._EXONYM_TR):
            for name, turkish in table.items():
                with self.subTest(name=name):
                    self.assertNotEqual(name.casefold(), turkish.casefold())

    def test_person_name_forms_stay_detection_only(self):
        # `Milan'ın` / `Sofia'nın` / `Roman'ın` kişi adı da olabilir; otomatik
        # düzeltme bunları YENİDEN YAZMAMALI.
        #
        # `troy` ve `florence` BİLİNÇLİ olarak otomatik düzeltmede: 2026-08-24
        # kararı, gerekçesi prompt_constants içinde yazılı (Strangest Things
        # S02E03'te 35 cue elle 'Truva'ya düzeltilmişti). Bu testin işi o
        # kararı ters çevirmek değil, YENİ ad eklerken aynı riskin sessizce
        # alınmasını engellemek.
        for name in ("milan", "sofia", "roman"):
            with self.subTest(name=name):
                self.assertNotIn(name, FOREIGN_EXONYM_MAP)
        for name in ("Milan", "Sofia", "Roman", "Troy"):
            with self.subTest(name=name):
                self.assertIn(name, g._EXONYM_TR)


class ExonymAutoFixGuardTest(unittest.TestCase):
    def test_plain_suffixed_name_is_corrected(self):
        value, changed = g.normalize_foreign_exonyms("Siberia'dan geldi.")
        self.assertEqual(changed, 1)
        self.assertIn("Sibirya'dan", value)

    def test_part_of_a_longer_name_is_left_alone(self):
        for text in ("Historic England'ın arşivleri",
                     "New Mexico'da bir kasaba",
                     "Great Britain'in kuzeyi"):
            with self.subTest(text=text):
                value, changed = g.normalize_foreign_exonyms(text)
                self.assertEqual(changed, 0)
                self.assertEqual(value, text)

    def test_bare_word_is_never_rewritten(self):
        # Ek yoksa dokunulmaz: 'Captain America' bozulmamalı.
        value, changed = g.normalize_foreign_exonyms("Captain America geldi.")
        self.assertEqual(changed, 0)
        self.assertEqual(value, "Captain America geldi.")

    def test_sentence_start_is_still_corrected(self):
        value, changed = g.normalize_foreign_exonyms("China'daki fabrika.")
        self.assertEqual(changed, 1)
        self.assertIn("Çin'deki", value)


if __name__ == "__main__":
    unittest.main()
