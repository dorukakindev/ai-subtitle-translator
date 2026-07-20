"""_lang_iso639_1 regression — bkz. hybrid_translate.sanitize_glossary_for_turkish.

Gerçek olay (Louis Theroux 'Drinking to Oblivion', 2026-07-20): analyze_with_helper
çağrı yerinde target_language=tgt.lower()[:2] kullanılıyordu. self.tgt_var varsayılanı
"Turkish" olduğu için bu "tu" üretiyordu — Türkçenin gerçek ISO 639-1 kodu "tr" (ilk iki
harfi değil). sanitize_glossary_for_turkish yalnızca "tr"/"tur"/"turkish" tanıdığı için
"tu" hiçbir zaman eşleşmiyor, guard sessizce devre dışı kalıyordu (wqx/gloss-marker/
verbose-meta-commentary hiçbiri hiç çalışmamış oluyordu). Aynı naif [:2] dilimi
German->"ge" (doğrusu "de"), Spanish->"sp" ("es"), Portuguese/Polish->"po" (çakışma),
Chinese->"ch" ("zh"), Dutch->"du" ("nl"), Swedish->"sw" ("sv") için de yanlış üretiyordu.
"""
import unittest

import subtitle_translator_gui as gui


class LangIso6391Test(unittest.TestCase):
    def test_turkish_maps_to_tr_not_naive_slice(self):
        self.assertEqual(gui._lang_iso639_1("Turkish"), "tr")
        self.assertNotEqual(gui._lang_iso639_1("Turkish"), "Turkish".lower()[:2])

    def test_all_supported_languages_map_correctly(self):
        expected = {
            "Turkish": "tr", "English": "en", "German": "de", "French": "fr",
            "Spanish": "es", "Italian": "it", "Portuguese": "pt", "Russian": "ru",
            "Japanese": "ja", "Korean": "ko", "Chinese": "zh", "Arabic": "ar",
            "Dutch": "nl", "Polish": "pl", "Swedish": "sv", "Norwegian": "no",
            "Danish": "da", "Finnish": "fi",
        }
        for name, code in expected.items():
            self.assertIn(name, gui.LANGUAGES, f"{name} LANGUAGES listesinden düştü mü?")
            self.assertEqual(gui._lang_iso639_1(name), code)

    def test_unknown_language_falls_back_to_naive_slice(self):
        self.assertEqual(gui._lang_iso639_1("Klingon"), "kl")

    def test_analyze_with_helper_receives_tr_so_glossary_guard_stays_active(self):
        # asıl regresyon: doğru kod artık analyze_with_helper'a "tr" veriyor,
        # bu da sanitize_glossary_for_turkish'in guard'ını aktif tutuyor.
        import hybrid_translate as ht

        tgt = "Turkish"
        real_call_value = gui._lang_iso639_1(tgt)
        self.assertIn(real_call_value, ht._GLOSSARY_GUARD_TURKISH_TARGETS)

        # eski (buggy) davranış aynı guard'ı kör ediyordu — burada belgeleniyor
        old_buggy_value = tgt.lower()[:2]
        self.assertNotIn(old_buggy_value, ht._GLOSSARY_GUARD_TURKISH_TARGETS)


if __name__ == "__main__":
    unittest.main()
