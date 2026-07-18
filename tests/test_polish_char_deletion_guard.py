"""_has_char_deletion (hybrid_translate.py) — Polish Pass'in tek-karakter SİLME ile
bir kelimeyi bozup geçersiz bir token'a çevirmesini yakalar (nihai->ihai, battığını->
batığını). Bu oturumda 3 dosyada görülen tek-cue polish garble sınıfının silme alt-kümesi.

TASARIM: Türkçe kelime listesi olmadığından yalnız ASİMETRİK (kısaltma) yön yakalanır —
harf EKLEME (batdığını->battığını, meşru düzeltme) ve tamamen farklı kelime GEÇER. Ayrıca
son-2 pozisyondaki silmeler (ek/durum düzeltmesi: arabanın->arabanı) FP-guard'ıyla hariç.
Değişim garble'ı (ahşap->ohşap) bilinçli KAPSAM DIŞI (simetrik, sözlük gerektirir).
"""
import unittest

import hybrid_translate as ht


class CharDeletionGuardTest(unittest.TestCase):
    def test_first_char_deletion_rejected(self):
        # Gerçek olay (Sun Kings #465): polish "nihai"->"ihai" (baştaki n düştü).
        ok, reason = ht.validate_polish_candidate(
            "ve bunlar Ptahshepses'in nihai statüsünü açığa çıkarıyor.",
            "ve bunlar Ptahshepses'in ihai statüsünü açığa çıkarıyor.")
        self.assertFalse(ok)
        self.assertEqual(reason, "char_deletion")

    def test_mid_char_deletion_rejected(self):
        self.assertTrue(ht._has_char_deletion("battığını araştırıyor", "batığını araştırıyor"))

    def test_legit_typo_fix_adding_char_not_rejected(self):
        # Meşru düzeltme: "batdığını"->"battığını" HARF EKLER (kısaltmaz) — takılmamalı.
        self.assertFalse(ht._has_char_deletion("nihayet batdığını", "nihayet battığını"))

    def test_case_suffix_edit_not_rejected(self):
        # Genitif->akkuzatif (son 'n' düşer) meşru bir gramer düzeltmesi — FP guard'ı korur.
        self.assertFalse(ht._has_char_deletion("arabanın rengi", "arabanı gördüm"))

    def test_completely_different_word_not_rejected(self):
        self.assertFalse(ht._has_char_deletion("nihayet araştırıyor", "sonunda inceliyor"))

    def test_short_token_ignored(self):
        # 4 harften kısa token'lar taban altı — tetiklemez.
        self.assertFalse(ht._has_char_deletion("bir şey var", "ir şey var"))

    def test_new_token_preserved_in_old_not_flagged(self):
        # new'deki token old'da AYNEN varsa (gerçek kelime, tesadüfi silme değil) — geçer.
        self.assertFalse(ht._has_char_deletion("ihai bir kelime nihai değil", "ihai kaldı"))

    def test_empty_inputs_safe(self):
        self.assertFalse(ht._has_char_deletion("", "ihai"))
        self.assertFalse(ht._has_char_deletion("nihai", ""))
        self.assertFalse(ht._has_char_deletion(None, None))


if __name__ == "__main__":
    unittest.main()
