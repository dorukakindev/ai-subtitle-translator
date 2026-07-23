import unittest
from types import SimpleNamespace

import hybrid_translate as ht


class SourceLanguageLeftoverTest(unittest.TestCase):
    def test_validator_flags_german_words_left_in_turkish(self):
        cues = [
            SimpleNamespace(index=1, text="Ein Kind mit Flügeln."),
            SimpleNamespace(index=2, text="Mehr Federn, Vater."),
            SimpleNamespace(index=3, text="Ich will ihr einen Käfig bauen lassen."),
        ]
        blocks = [
            (1, "00:00:01,000 --> 00:00:02,000", "Flügel'li bir çocuk."),
            (2, "00:00:02,000 --> 00:00:03,000", "Daha çok Federn, baba."),
            (3, "00:00:03,000 --> 00:00:04,000", "Ona bir Käfig yaptırmak istiyorum."),
        ]

        hits = ht.run_validators(blocks, cues)

        self.assertEqual([str(hit[0]) for hit in hits], ["1", "2", "3"])
        for hit in hits:
            self.assertIn("SOURCE_LANG_LEFTOVER", hit[3])

    def test_validator_does_not_flag_turkish_umlaut_words(self):
        cues = [SimpleNamespace(index=1, text="Please wait.")]
        blocks = [(1, "00:00:01,000 --> 00:00:02,000", "Lütfen biraz bekleyin.")]

        self.assertEqual(ht.run_validators(blocks, cues), [])

    def test_validator_does_not_flag_turkish_bulur(self):
        cues = [SimpleNamespace(index=1, text="Find the obstruction and bring it out.")]
        blocks = [
            (
                1,
                "00:00:01,000 --> 00:00:02,000",
                "aletle tıkanıklığı bulur,\nyakalar ve çıkarırdın.",
            )
        ]

        self.assertEqual(ht.run_validators(blocks, cues), [])

    def test_wide_latin_guard_flags_lowercase_non_turkish_letters(self):
        self.assertTrue(ht.has_non_turkish_target_leak("To jest zły wynik."))
        self.assertTrue(ht.has_non_turkish_target_leak("qora pichoq"))
        self.assertTrue(ht.has_non_turkish_target_leak("patlatılmış kəllə"))

    def test_wide_latin_guard_allows_preserved_proper_names(self):
        self.assertFalse(ht.has_non_turkish_target_leak("Buñuel'in filmleri çok önemli."))
        self.assertFalse(ht.has_non_turkish_target_leak("Juárez burada anılıyor."))
        self.assertFalse(ht.has_non_turkish_target_leak("Dükkânda hâlâ katı hâlden gaza geçiyor."))

    def test_source_term_with_latin_diacritic_and_turkish_suffix_is_allowed(self):
        self.assertFalse(ht.has_non_turkish_target_leak(
            "Rapé ve hapé--", source_text="Rapé and hapé--"))
        self.assertFalse(ht.has_non_turkish_target_leak(
            "rapéyi burun deliklerine üflemek", source_text="blow the rapé into the nostrils"))
        self.assertFalse(ht.has_non_turkish_target_leak(
            "rapénin şifası", source_text="the medicine of rapé"))
        self.assertTrue(ht.has_non_turkish_target_leak(
            "rapéyi burun deliklerine üflemek", source_text="blow the medicine into the nostrils"))

    def test_homoglyph_normalization_allows_cyrillic_a_in_turkish_word(self):
        self.assertEqual(ht.normalize_latin_homoglyphs("BАNA"), "BANA")
        self.assertFalse(ht.has_non_turkish_target_leak("O da BАNA kavanozda şeyler getirdi."))
        self.assertTrue(ht.has_non_turkish_target_leak("Bu текст Türkçe değil."))

    def test_validator_flags_turkic_drift_and_bad_common_terms(self):
        cues = [
            SimpleNamespace(index=1, text="I am throwing a holiday party."),
            SimpleNamespace(index=2, text="I want a taxidermy centerpiece."),
            SimpleNamespace(index=3, text="This was my competition piece."),
            SimpleNamespace(index=4, text="Maybe a reindeer."),
        ]
        blocks = [
            (1, "00:00:01,000 --> 00:00:02,000", "Bir bäýram/holidaý oturylyşyğı vereceğim."),
            (2, "00:00:02,000 --> 00:00:03,000", "Bir taksidermiya ortadagy bezeg istiyorum."),
            (3, "00:00:03,000 --> 00:00:04,000", "Bu benim bäseke işi parçamdı."),
            (4, "00:00:04,000 --> 00:00:05,000", "Belki bir buğu."),
        ]

        hits = ht.run_validators(blocks, cues)
        reasons = {str(idx): reason for idx, _ts, _text, reason in hits}

        self.assertIn("NON_TURKISH_TARGET_LEAK", reasons["1"])
        self.assertIn("TERM_MISTRANSLATION:holiday", reasons["1"])
        self.assertIn("TERM_MISTRANSLATION:centerpiece", reasons["2"])
        self.assertIn("TERM_MISTRANSLATION:taxidermy", reasons["2"])
        self.assertIn("TERM_MISTRANSLATION:competition_piece", reasons["3"])
        self.assertIn("TERM_MISTRANSLATION:reindeer", reasons["4"])

    def test_validator_flags_orrery_and_electromagnet_flow_traps(self):
        cues = [
            SimpleNamespace(index=1, text="These mechanical clockwork orreries are my favorite."),
            SimpleNamespace(index=2, text="I can turn on one or both of these electromagnets."),
        ]
        blocks = [
            (1, "00:00:01,000 --> 00:00:02,000", "Bu mekanik saat işi oreriler favorim."),
            (2, "00:00:02,000 --> 00:00:03,000", "bu elektromıknatısların açabiliyorum."),
        ]

        hits = ht.run_validators(blocks, cues)
        reasons = {str(idx): reason for idx, _ts, _text, reason in hits}

        self.assertIn("TERM_MISTRANSLATION:orrery", reasons["1"])
        self.assertIn("TERM_MISTRANSLATION:electromagnet_flow", reasons["2"])
        self.assertIn("BAD_TURKISH_CASE_FLOW", reasons["2"])

    def test_validator_flags_under_budget_meaning_flip(self):
        cues = [
            SimpleNamespace(index=1, text="I did stay under your budget, but it was pricey."),
            SimpleNamespace(index=2, text="I did stay under your budget, but it was pricey."),
        ]
        blocks = [
            (1, "00:00:01,000 --> 00:00:02,000", "Bütçeni aştım ama fiyatı yüksekti."),
            (2, "00:00:02,000 --> 00:00:03,000", "Bütçeni aşmadım ama fiyatı yüksekti."),
        ]

        hits = ht.run_validators(blocks, cues)
        reasons = {str(idx): reason for idx, _ts, _text, reason in hits}

        self.assertIn("TERM_MISTRANSLATION:under_budget", reasons["1"])
        self.assertNotIn("2", reasons)

    def test_validator_flags_pupil_and_fake_out_mistranslations(self):
        cues = [
            SimpleNamespace(index=1, text="Now you're just pupils, which is disconcerting."),
            SimpleNamespace(index=2, text="He can use it to fake out his opponents."),
        ]
        blocks = [
            (1, "00:00:01,000 --> 00:00:02,000", "Artık sadece pupillersın, bu tedirgin edici."),
            (2, "00:00:02,000 --> 00:00:03,000", "Rakiplerini biraz oyalamak için kullanabilir."),
        ]

        hits = ht.run_validators(blocks, cues)
        reasons = {str(idx): reason for idx, _ts, _text, reason in hits}

        self.assertIn("TERM_MISTRANSLATION:pupil", reasons["1"])
        self.assertIn("TERM_MISTRANSLATION:fake_out", reasons["2"])

    def test_validator_flags_speaker_register_flip_minority(self):
        cues = [
            SimpleNamespace(index=1, text="JOHN: Please come in."),
            SimpleNamespace(index=2, text="JOHN: I will show you."),
            SimpleNamespace(index=3, text="JOHN: You can sit here."),
            SimpleNamespace(index=4, text="JOHN: Look at this."),
        ]
        blocks = [
            (1, "00:00:01,000 --> 00:00:02,000", "JOHN: Siz içeri buyurun."),
            (2, "00:00:02,000 --> 00:00:03,000", "JOHN: Size göstereceğim."),
            (3, "00:00:03,000 --> 00:00:04,000", "JOHN: Siz buraya oturabilirsiniz."),
            (4, "00:00:04,000 --> 00:00:05,000", "JOHN: Sen şuna bak."),
        ]

        hits = ht.run_validators(blocks, cues)
        reasons = {str(idx): reason for idx, _ts, _text, reason in hits}

        self.assertIn("REGISTER_FLIP:sen_against_siz", reasons["4"])

    def test_on_screen_text_detector_does_not_crash_on_title_case(self):
        self.assertFalse(ht.looks_like_on_screen_text("Professional wrestler"))
        self.assertTrue(ht.looks_like_on_screen_text("MOUNTING TENSIONS"))

    def test_quality_glossary_filters_bad_targets_and_injects_common_terms(self):
        cleaned = ht.sanitize_glossary_for_turkish({
            "holiday party": "bäýram/holidaý oturylyşyğı",
            "taxidermy": "taksidermi",
        })
        self.assertEqual(cleaned, {"taxidermy": "taksidermi"})

        guard = ht.quality_glossary_for_source(
            "I want taxidermy as a holiday centerpiece, maybe a reindeer competition piece. "
            "If someone comes in cash in hand, call it a day. "
            "This mummy phallus should have gilding, gold leaf, and linen wrappings. "
            "Would you like to see the abdominal scar? "
            "Can we get a discount on the rat?"
            "The client wants a macabre ride in the Macabre Mobile."
        )
        self.assertEqual(guard["holiday centerpiece"], "tatil/bayram masa süsü")
        self.assertEqual(guard["centerpiece"], "masa süsü")
        self.assertEqual(guard["taxidermy"], "taksidermi")
        self.assertEqual(guard["reindeer"], "ren geyiği")
        self.assertEqual(guard["competition piece"], "yarışma parçası")
        self.assertEqual(guard["cash in hand"], "nakit parayla")
        self.assertEqual(guard["call it a day"], "paydos etmek")
        self.assertEqual(guard["mummy"], "mumya")
        self.assertEqual(guard["phallus"], "fallus")
        self.assertEqual(guard["gilding"], "altın yaldız")
        self.assertEqual(guard["gold leaf"], "altın varak")
        self.assertEqual(guard["linen wrappings"], "keten sargılar")
        self.assertEqual(guard["abdominal scar"], "karındaki yara izi")
        self.assertEqual(guard["scar"], "yara izi")
        self.assertEqual(guard["rat"], "sıçan")
        self.assertEqual(guard["client"], "müşteri")
        self.assertEqual(guard["macabre"], "ürkütücü/ölüm temalı")
        self.assertEqual(guard["macabre mobile"], "ürkütücü araba")

    def test_validator_flags_cash_in_hand_mistranslation(self):
        cues = [SimpleNamespace(index=1, text="If someone comes in, cash in hand...")]
        blocks = [(1, "00:00:01,000 --> 00:00:02,000", "Biri içeri girip nakit basarsa...")]

        hits = ht.run_validators(blocks, cues)
        reasons = {str(idx): reason for idx, _ts, _text, reason in hits}

        self.assertIn("TERM_MISTRANSLATION:cash_in_hand", reasons["1"])

    def test_validator_flags_oddities_term_artifacts(self):
        cues = [
            SimpleNamespace(index=1, text="It's a condition called automatonophobia."),
            SimpleNamespace(index=2, text="It's a ventriloquist dummy."),
            SimpleNamespace(index=3, text="I design an exploded skull for a chiropractor."),
            SimpleNamespace(index=4, text="I'm flattered, man."),
            SimpleNamespace(index=5, text="I am a repeat customer."),
            SimpleNamespace(index=6, text="Is this mummy phallus authentic?"),
            SimpleNamespace(index=7, text="That baby could land an uppercut."),
            SimpleNamespace(index=8, text="Would you like to see the scar?"),
            SimpleNamespace(index=9, text="These are polio braces."),
            SimpleNamespace(index=10, text="He went to mortuary school and used wound-filler."),
            SimpleNamespace(index=11, text="I'm a sideshow performer."),
            SimpleNamespace(index=12, text="A body modification centerpiece in his collection."),
            SimpleNamespace(index=13, text="Can we get a discount on the rat?"),
            SimpleNamespace(index=14, text="The client wants something macabre."),
        ]
        blocks = [
            (1, "00:00:01,000 --> 00:00:02,000", "Avtomatonofobi denen bir durum."),
            (2, "00:00:02,000 --> 00:00:03,000", "Bir ventriloq kuklası."),
            (3, "00:00:03,000 --> 00:00:04,000", "Chiropraktör için partlatılmış kəllə tasarlarım."),
            (4, "00:00:04,000 --> 00:00:05,000", "Çok düşündürücüsün, dostum."),
            (5, "00:00:05,000 --> 00:00:06,000", "Ben repeat customer'ım."),
            (6, "00:00:06,000 --> 00:00:07,000", "Bu mummy phallus authentic mi?"),
            (7, "00:00:07,000 --> 00:00:08,000", "O bebek yükseltme indirebilir."),
            (8, "00:00:08,000 --> 00:00:09,000", "Jaalimi görmek ister misin?"),
            (9, "00:00:09,000 --> 00:00:10,000", "Bunlar polio için brasekler."),
            (10, "00:00:10,000 --> 00:00:11,000", "Mortuary school'a gitti ve wound-filler'ı kullandı."),
            (11, "00:00:11,000 --> 00:00:12,000", "Ben sideshow performerım."),
            (12, "00:00:12,000 --> 00:00:13,000", "Collection'ında body modification merkez parçası."),
            (13, "00:00:13,000 --> 00:00:14,000", "Şu rat'le indirim koparabilir miyiz?"),
            (14, "00:00:14,000 --> 00:00:15,000", "Client için macabre bir şey."),
        ]

        hits = ht.run_validators(blocks, cues)
        reasons = {str(idx): reason for idx, _ts, _text, reason in hits}

        self.assertIn("TERM_MISTRANSLATION:automatonophobia", reasons["1"])
        self.assertIn("TERM_MISTRANSLATION:ventriloquism", reasons["2"])
        self.assertIn("TERM_MISTRANSLATION:exploded_skull", reasons["3"])
        self.assertIn("TERM_MISTRANSLATION:chiropractor", reasons["3"])
        self.assertIn("TERM_MISTRANSLATION:flattered", reasons["4"])
        self.assertIn("TERM_MISTRANSLATION:repeat_customer", reasons["5"])
        self.assertIn("TERM_MISTRANSLATION:mummy", reasons["6"])
        self.assertIn("TERM_MISTRANSLATION:phallus", reasons["6"])
        self.assertIn("TERM_MISTRANSLATION:authentic", reasons["6"])
        self.assertIn("TERM_MISTRANSLATION:uppercut", reasons["7"])
        self.assertIn("TERM_MISTRANSLATION:scar", reasons["8"])
        self.assertIn("TERM_MISTRANSLATION:braces", reasons["9"])
        self.assertIn("TERM_MISTRANSLATION:mortuary", reasons["10"])
        self.assertIn("TERM_MISTRANSLATION:wound_filler", reasons["10"])
        self.assertIn("TERM_MISTRANSLATION:sideshow", reasons["11"])
        self.assertIn("TERM_MISTRANSLATION:body_modification", reasons["12"])
        self.assertIn("TERM_MISTRANSLATION:collection", reasons["12"])
        self.assertIn("TERM_MISTRANSLATION:rat", reasons["13"])
        self.assertIn("TERM_MISTRANSLATION:client", reasons["14"])
        self.assertIn("TERM_MISTRANSLATION:macabre", reasons["14"])

    def test_validator_flags_english_words_with_turkish_suffixes(self):
        cues = [SimpleNamespace(index=1, text="He wants a strange medical gurney.")]
        blocks = [(1, "00:00:01,000 --> 00:00:02,000", "Garip medical gurney'i istiyor.")]

        hits = ht.run_validators(blocks, cues)
        reasons = {str(idx): reason for idx, _ts, _text, reason in hits}

        self.assertIn("EN_TURKISH_SUFFIX_LEFTOVER", reasons["1"])

    def test_validator_flags_hunting_picking_and_life_mask_traps(self):
        cues = [
            SimpleNamespace(index=1, text="We spent our lives hunting and picking."),
            SimpleNamespace(index=2, text="Covered in alginate and plaster to make a life mask."),
        ]
        blocks = [
            (1, "00:00:01,000 --> 00:00:02,000", "HUNTER VE SEÇEREK..."),
            (2, "00:00:02,000 --> 00:00:03,000", "ölüm maskesi yapmak için kaplandı."),
        ]

        hits = ht.run_validators(blocks, cues)
        reasons = {str(idx): reason for idx, _ts, _text, reason in hits}

        self.assertIn("TERM_MISTRANSLATION:hunting_picking", reasons["1"])
        self.assertIn("TERM_MISTRANSLATION:life_mask", reasons["2"])

    def test_validator_flags_speaker_label_absorbing_next_dialogue(self):
        cues = [
            SimpleNamespace(index=1, text="Ryan:"),
            SimpleNamespace(index=2, text="What are we doing here?"),
        ]
        blocks = [
            (1, "00:00:01,000 --> 00:00:02,000", "Ryan: Burada ne yapıyoruz?"),
            (2, "00:00:02,000 --> 00:00:03,000", "Burada ne yapıyoruz?"),
        ]

        hits = ht.run_validators(blocks, cues)
        reasons = {str(idx): reason for idx, _ts, _text, reason in hits}

        self.assertIn("SPEAKER_LABEL_ABSORBED_TEXT", reasons["1"])

    def test_validator_flags_aorist_early_verb_closure(self):
        cues = [
            SimpleNamespace(index=1, text="When he comes"),
            SimpleNamespace(index=2, text="home."),
        ]
        blocks = [
            (1, "00:00:01,000 --> 00:00:02,000", "Eve gelir."),
            (2, "00:00:02,000 --> 00:00:03,000", "geldiğinde."),
        ]

        hits = ht.run_validators(blocks, cues)
        reasons = {str(idx): reason for idx, _ts, _text, reason in hits}

        self.assertIn("EARLY_VERB_CLOSURE", reasons["1"])

    def test_validator_flags_general_dangling_start_fragment(self):
        cues = [
            SimpleNamespace(index=1, text="Because of the plan"),
            SimpleNamespace(index=2, text="we had to wait."),
        ]
        blocks = [
            (1, "00:00:01,000 --> 00:00:02,000", "Plan için"),
            (2, "00:00:02,000 --> 00:00:03,000", "beklemek zorunda kaldık."),
        ]

        hits = ht.run_validators(blocks, cues)
        reasons = {str(idx): reason for idx, _ts, _text, reason in hits}

        self.assertIn("DANGLING_TURKISH_FRAGMENT", reasons["1"])

    def test_validator_flags_negation_loss(self):
        cues = [SimpleNamespace(index=1, text="I don't think this is safe.")]
        blocks = [(1, "00:00:01,000 --> 00:00:02,000", "Bence bu güvenli.")]

        hits = ht.run_validators(blocks, cues)
        reasons = {str(idx): reason for idx, _ts, _text, reason in hits}

        self.assertIn("NEGATION_LOSS", reasons["1"])

    def test_validator_accepts_turkish_negative_verb(self):
        cues = [SimpleNamespace(index=1, text="I don't know.")]
        blocks = [(1, "00:00:01,000 --> 00:00:02,000", "Bilmiyorum.")]

        self.assertEqual(ht.run_validators(blocks, cues), [])

    def test_validator_allows_cannot_wait_idiom(self):
        cues = [SimpleNamespace(index=1, text="I can't wait to see it.")]
        blocks = [(1, "00:00:01,000 --> 00:00:02,000", "Gormek icin sabirsizlaniyorum.")]

        hits = ht.run_validators(blocks, cues)
        reasons = "|".join(reason for _idx, _ts, _text, reason in hits)

        self.assertNotIn("NEGATION_LOSS", reasons)

    def test_validator_accepts_common_turkish_negation_suffixes(self):
        cases = [
            ("We don't allow smoking here.", "Burada sigara içmeye izin vermeyiz."),
            ("You shouldn't try this at home.", "Bunu evde denememen gereken bir şey."),
            ("Do not try this at home.", "Bunu evde denemeyin."),
            ("Maybe we won't poke around there.", "Belki orayı çok kurcalamayız."),
            ("I'm not sure.", "Pek emin değilim."),
            ("What I don't have is a two-faced pig.", "Bende olmayan şey iki yüzlü bir domuz."),
        ]
        for source, translated in cases:
            with self.subTest(translated=translated):
                cues = [SimpleNamespace(index=1, text=source)]
                blocks = [(1, "00:00:01,000 --> 00:00:02,000", translated)]
                hits = ht.run_validators(blocks, cues)
                reasons = "|".join(reason for _idx, _ts, _text, reason in hits)
                self.assertNotIn("NEGATION_LOSS", reasons)

    def test_validator_checks_negation_across_fragment_group(self):
        cues = [
            SimpleNamespace(index=1, text="I don't really"),
            SimpleNamespace(index=2, text="care for him."),
        ]
        blocks = [
            (1, "00:00:01,000 --> 00:00:02,000", "Ondan pek"),
            (2, "00:00:02,000 --> 00:00:03,000", "hoşlanmıyorum."),
        ]

        hits = ht.run_validators(blocks, cues)
        reasons = "|".join(reason for _idx, _ts, _text, reason in hits)

        self.assertNotIn("NEGATION_LOSS", reasons)

    def test_validator_flags_question_mark_mismatch(self):
        cues = [SimpleNamespace(index=1, text="Are you sure?")]
        blocks = [(1, "00:00:01,000 --> 00:00:02,000", "Eminsin.")]

        hits = ht.run_validators(blocks, cues)
        reasons = {str(idx): reason for idx, _ts, _text, reason in hits}

        self.assertIn("QUESTION_MARK_MISMATCH", reasons["1"])

    def test_validator_allows_question_mark_for_question_like_source(self):
        cues = [SimpleNamespace(index=1, text="I was gone for how long.")]
        blocks = [(1, "00:00:01,000 --> 00:00:02,000", "Ne kadar yoktum ki?")]

        self.assertEqual(ht.run_validators(blocks, cues), [])

    def test_validator_flags_number_mismatch(self):
        cues = [SimpleNamespace(index=1, text="There were 12 people in 1998.")]
        blocks = [(1, "00:00:01,000 --> 00:00:02,000", "1999'da 11 kişi vardı.")]

        hits = ht.run_validators(blocks, cues)
        reasons = {str(idx): reason for idx, _ts, _text, reason in hits}

        self.assertIn("NUMBER_MISMATCH", reasons["1"])


if __name__ == "__main__":
    unittest.main()
