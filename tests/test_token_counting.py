# -*- coding: utf-8 -*-
"""Maliyet tahmini gerçek tokenizasyon kullanır, orana düşer."""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import subtitle_translator_gui as g


class TokenCountingTest(unittest.TestCase):
    """Eski kod tiktoken'i yalnız 'kurulu mu' diye yokluyor ve chars/3 ya da
    chars/4 seçiyordu. 12 gerçek dosyada (950 bin karakter) ölçüldü:
    İngilizce kaynak 3,70 karakter/token, Türkçe hedef 3,27. Yani chars/3
    kaynağı %23 fazla, chars/4 hedefi %18 eksik sayıyordu. Koddaki "tam
    tokenizasyon çok yavaş" notu da yanlıştı: 950 bin karakter 0,1 saniye.
    """

    def test_an_empty_text_is_zero(self):
        self.assertEqual(g.count_tokens(""), 0)
        self.assertEqual(g.count_tokens(None), 0)

    def test_a_real_sentence_is_counted(self):
        self.assertGreater(g.count_tokens("Merhaba dünya, bu bir testtir."), 3)

    def test_it_falls_back_without_tiktoken(self):
        saved_enc, saved_tried = g._TOKEN_ENCODING, g._TOKEN_ENCODING_TRIED
        try:
            g._TOKEN_ENCODING, g._TOKEN_ENCODING_TRIED = None, True
            text = "x" * 370
            self.assertEqual(g.count_tokens(text, 3.7), 100)
        finally:
            g._TOKEN_ENCODING, g._TOKEN_ENCODING_TRIED = saved_enc, saved_tried

    def test_the_two_languages_have_their_own_ratio(self):
        # Tek orana indirgemek hangi tarafı seçersen diğerini yanıltıyordu.
        self.assertNotEqual(g._CHARS_PER_TOKEN_SOURCE, g._CHARS_PER_TOKEN_TARGET)
        self.assertGreater(g._CHARS_PER_TOKEN_SOURCE, g._CHARS_PER_TOKEN_TARGET)

    def test_special_tokens_do_not_raise(self):
        # Altyazıda '<|endoftext|>' geçerse tiktoken varsayılanı hata verir.
        self.assertGreater(g.count_tokens("bir <|endoftext|> metin"), 0)

    def test_the_estimator_uses_the_counter(self):
        import inspect
        source = inspect.getsource(g.estimate_tokens)
        self.assertIn("count_tokens(", source)
        self.assertNotIn("total_chars // 3", source)
        self.assertNotIn("total_chars // 4", source)


if __name__ == "__main__":
    unittest.main()
