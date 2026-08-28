# -*- coding: utf-8 -*-
"""`is_ost` işareti SDH ses etiketine de vuruyor — uyarı PROMPTTA.

`is_ost` zararsız bir ipucu değil: paylaşılan prompt bloğu modele
"ON-SCREEN TEXT (a sign, caption, title card…) — Translate it as written
display text" diyor. İşaret caps sezgisiyle konuyor ve o kalıp SDH ses
etiketiyle BİREBİR aynı (`SHE WAILS`, `CHOIR SINGS`), yani silinmesi
gereken etiket modele KORUNACAK tabela diye tanıtılıyordu — `GÜLER` /
`KEKELİYOR` / `MÜZİK KESİLİR` sınıfının besleyicilerinden biri.

Ölçüm (60 gerçek kaynak dosya): 140 `is_ost` işaretinin örneklenen hepsi
SDH ses etiketiydi, tek bir gerçek tabela yoktu.

Ayrımı KODDA yapmayı denedim ve yapılamadı — `sdh_cleaner`ın üç yordamı da
gerçek tabelaları SDH sayıyor, ses-fiili listesiyle kurulan ayırıcı da
15 örneğin 10'unu yakalayıp `BREAKING NEWS`i yanlış işaretledi. Ayrım
caps'ten belirsiz; dosya düzeyindeki caps kapısının varlık sebebi de bu.
Bu yüzden dedektör GENİŞ bırakıldı ve karar metni gören modele verildi.
"""
import unittest

import hybrid_translate as ht


class OstHintIsNotTrustedAloneTest(unittest.TestCase):
    """Dedektörün ayırmadığı testle KAYIT ALTINDA."""

    def test_detector_flags_both_classes(self):
        for text in ("SHE WAILS", "CHOIR SINGS",
                     "ADVANCED GENOMIC TESTING", "MOUNTING TENSIONS"):
            with self.subTest(text=text):
                self.assertTrue(ht.looks_like_on_screen_text(text))

    def test_sdh_cleaner_cannot_separate_them_either(self):
        """Kodda ayırmayı denemeden önce buraya bak."""
        import sdh_cleaner as sdh
        for text in ("SHE WAILS", "POLICE STATION"):
            with self.subTest(text=text):
                self.assertTrue(
                    sdh.is_structural_sdh_cue(text, allow_caps_heuristic=True))

    def test_ordinary_dialogue_is_never_ost(self):
        for text in ("Bunu neden yaptın?", "I told you already.",
                     "He walked into the room and sat down."):
            with self.subTest(text=text):
                self.assertFalse(ht.looks_like_on_screen_text(text))


class OstPromptContractTest(unittest.TestCase):
    """Karar modele verildiğine göre, verildiği cümle testle kilitli."""

    def _prompts(self):
        import subtitle_translator_gui as gui
        from tests.test_prompt_payload_contract import _hybrid_request
        sync = gui._build_sync_system_prompt(
            "English", "Turkish", None, "Orta")
        hybrid, _payload = _hybrid_request()
        return sync, hybrid

    def test_both_prompts_warn_that_the_flag_is_only_a_hint(self):
        for prompt in self._prompts():
            self.assertIn("is_ost", prompt)
            self.assertIn("ON-SCREEN TEXT", prompt)
            self.assertIn("is a hint, not a fact", prompt)
            self.assertIn("SDH label", prompt)

    def test_the_warning_names_the_shape_it_guards(self):
        sync, _hybrid = self._prompts()
        for example in ("SHE WAILS", "CHOIR SINGS", "BELL RINGS"):
            with self.subTest(example=example):
                self.assertIn(example, sync)


if __name__ == "__main__":
    unittest.main()
