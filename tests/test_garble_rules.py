"""find_garble_tokens (hybrid_translate.py) — deterministik, API'siz bozuk/yabancı
token tespiti. Altı kural, hepsi gerçek teslim edilmiş dosyalarda bulunan garble
örneklerine dayanıyor (bkz. plans/future-quality-guards-brief.md Görev 1).
"""
import unittest

import hybrid_translate as ht


class StrayLetterR1Test(unittest.TestCase):
    def test_stray_a_between_words_flagged(self):
        hits = ht.find_garble_tokens("Ve Tabetha Boyajian adlı a astronom")
        self.assertIn(("a", "R1_stray_letter"), hits)

    def test_stray_a_at_line_end_flagged(self):
        hits = ht.find_garble_tokens("Avrasya kıtasını a araştırmaya başladığımız")
        self.assertIn(("a", "R1_stray_letter"), hits)

    def test_pronoun_o_not_flagged(self):
        self.assertEqual(ht.find_garble_tokens("o gitti eve."), [])

    def test_interjection_e_not_flagged(self):
        self.assertEqual(ht.find_garble_tokens("e, ne olmuş yani?"), [])

    def test_apostrophe_attached_single_letter_not_flagged(self):
        # "ay'a" (aya/moon-DAT) — apostrof-bitişik meşru ek, başıboş harf DEĞİL.
        self.assertEqual(ht.find_garble_tokens("1969'da ay'a gittiler."), [])

    def test_quoted_word_with_turkish_case_suffix_not_flagged(self):
        self.assertEqual(
            ht.find_garble_tokens('"Keskin nişancılar"ı içeri aldı.'), [])
        self.assertEqual(
            ht.find_garble_tokens('Bu "anlam"ı cümleye koyun.'), [])

    def test_hyphenated_lyric_syllables_not_flagged(self):
        self.assertEqual(
            ht.find_garble_tokens(
                "Ram'ı ram-a-lam-a-ding-dong'a kim koydu"
            ),
            [],
        )

    def test_foreign_proper_name_preposition_not_flagged(self):
        # Explorer 2 #662 gerçek olayı: İspanyolca özel isim "Monumento a la
        # Humanidad" içindeki 'a' edatı, komşusunda Büyük-harfli kelime var —
        # başıboş Türkçe harf DEĞİL, özel-isim dizisinin parçası.
        self.assertEqual(
            ht.find_garble_tokens("bugünkü adını, Monumento a la Humanidad adını aldı."),
            [])

    def test_real_stray_letter_after_line_break_still_flagged(self):
        # Göbekli 2 fixed #711 gerçek olayı (henüz düzeltilmemiş): satır sonrasında
        # başıboş 'a', komşularında büyük harf yok — hâlâ flaglenmeli.
        hits = ht.find_garble_tokens("Bu, uzayda yol almak için\na bir sistem mi?")
        self.assertIn(("a", "R1_stray_letter"), hits)

    def test_repeated_initial_stray_consonant_after_line_break_flagged(self):
        hits = ht.find_garble_tokens(
            "Gerekli etkinlikle işinizi yapıp yeterli enerji merkezlerden\ng geçtiğinde,"
        )
        self.assertIn(("g", "R1_stray_letter"), hits)

    def test_lowercase_variable_without_repeated_initial_not_flagged(self):
        self.assertEqual(ht.find_garble_tokens("x ekseni ile g kuvvetini ölçtük."), [])


class WqxTokenR2Test(unittest.TestCase):
    def test_simwolika_flagged(self):
        hits = ht.find_garble_tokens("esas olarak Luciferçi simwolika yaydıkları")
        self.assertIn(("simwolika", "R2_wqx_token"), hits)

    def test_allowlisted_web_not_flagged(self):
        self.assertEqual(ht.find_garble_tokens("web sitesine gir."), [])

    def test_allowlisted_show_not_flagged(self):
        self.assertEqual(ht.find_garble_tokens("bir de show izle."), [])

    def test_valid_loanwords_not_flagged(self):
        samples = [
            "Bir Tyrannosaurus rex kemiği bulduk.",
            "Bu makinenin 100 watt gücü var.",
            "Tipik mikrodalganın 1.000 wattı vardır.",
            "Bir hayal edin, bowling dönemi.",
        ]
        for sample in samples:
            self.assertEqual(ht.find_garble_tokens(sample), [], msg=sample)

    def test_proper_noun_starting_uppercase_not_flagged(self):
        self.assertEqual(ht.find_garble_tokens("Wolfgang geldi."), [])


class StraySuffixR3Test(unittest.TestCase):
    def test_broken_deki_flagged(self):
        hits = ht.find_garble_tokens("özellikle kış gündönümünde deki belirli noktalara.")
        self.assertIn(("deki", "R3_stray_suffix"), hits)

    def test_attached_daki_not_flagged(self):
        # "Mısır'daki" — apostrof-bitişik, kopuk ek DEĞİL.
        self.assertEqual(ht.find_garble_tokens("Mısır'daki Konsey başkanı."), [])

    def test_quoted_title_suffix_and_ottoman_compound_are_not_garble(self):
        self.assertEqual(
            ht.find_garble_tokens('"Kaptan Fracassa"daki komedyenler'), [])
        self.assertEqual(ht.find_garble_tokens("Zat-ı Alileri geldi."), [])

    def test_natural_word_ending_in_deki_pattern_not_confused(self):
        self.assertEqual(ht.find_garble_tokens("evdeki eşyalar dağınıktı."), [])

    def test_genitive_teki_is_valid_turkish(self):
        self.assertEqual(ht.find_garble_tokens("Ayyaşın teki."), [])
        self.assertEqual(ht.find_garble_tokens("Beyinsizin teki."), [])


class ImpossibleSuffixR4Test(unittest.TestCase):
    def test_toplumlarde_flagged(self):
        hits = ht.find_garble_tokens("kulübelerin ilkel toplumlarde var olduğu.")
        self.assertIn(("toplumlarde", "R4_impossible_suffix"), hits)

    def test_normal_toplumlarda_not_flagged(self):
        self.assertEqual(ht.find_garble_tokens("kulübelerin ilkel toplumlarda var olduğu."), [])


class VowelHarmonyR5Test(unittest.TestCase):
    def test_misir_teki_wrong_harmony_flagged(self):
        hits = ht.find_garble_tokens("Mısır'teki Yüksek Antikiteler Konseyi'nin başındaki adamı,")
        self.assertIn(("Mısır'teki", "R5_vowel_harmony"), hits)

    def test_misir_in_wrong_harmony_flagged(self):
        hits = ht.find_garble_tokens("Mısır'in, şu an ona atfettiğimiz önemden")
        self.assertIn(("Mısır'in", "R5_vowel_harmony"), hits)

    def test_misir_daki_correct_harmony_not_flagged(self):
        self.assertEqual(
            ht.find_garble_tokens("Mısır'daki Yüksek Antikiteler Konseyi'nin başındaki adamı,"),
            [])

    def test_ascii_stem_foreign_name_skipped(self):
        # "York" tamamen ASCII — yabancı özel isimde yazım/telaffuz uyumu farklı
        # kurallara tabi; R5 bu gövdeleri kasıtlı atlıyor.
        self.assertEqual(ht.find_garble_tokens("New York'ta yaşıyorum."), [])


class EnglishOrdinalR6Test(unittest.TestCase):
    def test_19th_century_flagged(self):
        hits = ht.find_garble_tokens("bu mağara sisteminin girişini 19th century'in ilk dönemlerinde")
        self.assertIn(("19th", "R6_english_ordinal"), hits)

    def test_18th_century_flagged(self):
        hits = ht.find_garble_tokens("ancak 18th century'de, bir İskoç kaşif")
        self.assertIn(("18th", "R6_english_ordinal"), hits)

    def test_plain_year_not_flagged(self):
        self.assertEqual(ht.find_garble_tokens("1969'da ay'a gittiler."), [])

    def test_turkish_ordinal_not_flagged(self):
        self.assertEqual(ht.find_garble_tokens("19. yüzyılın ortasında bildirildi."), [])


class CleanSentenceTest(unittest.TestCase):
    def test_ordinary_turkish_sentences_return_empty(self):
        sentences = [
            "Bu tamamen normal bir Türkçe cümledir, sorun yok.",
            "Sfenks anıtının, Giza platosunun doğu kenarında duran.",
            "Neredeyse 2.500 yıl önce burada bir filozof doğdu.",
            "Dünyanın dört bir yanından araştırmacıları çeken bir gizem.",
        ]
        for s in sentences:
            self.assertEqual(ht.find_garble_tokens(s), [], msg=s)

    def test_empty_and_none_return_empty(self):
        self.assertEqual(ht.find_garble_tokens(""), [])
        self.assertEqual(ht.find_garble_tokens(None), [])
        self.assertEqual(ht.find_garble_tokens("   "), [])


class TranslatableEnglishResidueTest(unittest.TestCase):
    def test_real_hamilton_residues_are_flagged(self):
        cases = (
            ("a psychedelic toad", "psychedelic bir kurbağa", "psychedelic"),
            ("aqueous mercury nitrate", "aqueous mercury nitrate ile", "aqueous"),
            ("God can take a man", "God bir insanı kurtarabilir", "God"),
            ("Just try Jesus", "Bir Jesus'u dene", "Jesus"),
            ("a craving for Christ", "Christ için özlem", "Christ"),
            ("an insoluble adduct", "çözünmeyen bir adduct", "adduct"),
            ("an entourage effect", "bir entourage effect", "entourage effect"),
            ("a batch reactor", "bir batch reactor", "batch reactor"),
            ("a psychedelic researcher", "bir psychedelik araştırmacısı", "psychedelik"),
        )
        for source, target, expected in cases:
            with self.subTest(target=target):
                self.assertIn(
                    expected,
                    ht.find_translatable_english_residue(source, target),
                )

    def test_unrelated_names_are_not_flagged(self):
        self.assertEqual(
            ht.find_translatable_english_residue(
                "Uncle Fester founded Venom Press.",
                "Uncle Fester, Venom Press'i kurdu.",
            ),
            [],
        )

    def test_explicit_identity_glossary_protects_term(self):
        self.assertEqual(
            ht.find_translatable_english_residue(
                "Jesus spoke.", "Jesus konuştu.", {"Jesus": "Jesus"}
            ),
            [],
        )

    def test_run_validators_routes_residue_to_quality_pass(self):
        class Cue:
            index = "765"
            text = "The aluminum is amalgamated with aqueous mercury nitrate."

        hits = ht.run_validators(
            [("765", "00:00:01,000 --> 00:00:03,000",
              "Alüminyum aqueous mercury nitrate ile amalgamlanır.")],
            cues=[Cue()],
        )
        self.assertTrue(any("TRANSLATABLE_ENGLISH_RESIDUE" in row[3] for row in hits))


class KnownModelCorruptionTest(unittest.TestCase):
    def test_serialized_json_separator_is_garble(self):
        self.assertEqual(
            ht.find_garble_tokens("halüsinasyon yapan?},{"),
            [("},{", "R8_serialized_json_residue")],
        )

    def test_delivered_hamilton_corruptions_are_flagged(self):
        for token in ("gerten", "ekaranlıkta", "balonjoje", "ezehri"):
            with self.subTest(token=token):
                self.assertIn(
                    (token, "R7_model_corruption"),
                    ht.find_garble_tokens(f"Bu {token} bozuk."),
                )


if __name__ == "__main__":
    unittest.main()
