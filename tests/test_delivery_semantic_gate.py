# -*- coding: utf-8 -*-
"""Teslim denetimi artık anlamsal çöküşü ve bozuk yazımı da görüyor.

Derin denetim Tur 4, madde 1 ve 2: iki dedektör de kod tabanında VARDI ama
diske yazılan dosyanın denetimine hiç bağlı değildi, dolayısıyla ağır anlam
kaybı olan dosya status=ok alabiliyordu.

Her ikisi de YALNIZ RAPORLAR: status 'review' olur, sert hata sayılmaz,
dosya otomatik değiştirilmez.

Gerçek arşiv ölçümü (181 kaynak-teslim çifti, 129.878 teslim cue'su):
yalnız bu iki sinyal yüzünden 5 dosya ok -> review oldu ve beşi de gerçek:
Five Suns #556 anlam çöküşü, Sacred Wonders E01/E02/E03 ve Question of God
4of4'te ALL-CAPS kaynağın Türkçe küçültülmesinden doğan noktasız ı bozulması
(SAHIB -> sahıb, PATTI -> pattı, MILAN -> mılan, SIGMUND -> Sıgmund).
Sert hata sayısı 23'te sabit kaldı.
"""
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import hybrid_translate as ht
import subtitle_translator_gui as gui


def _srt(rows) -> str:
    out = []
    for index, (start, end, text) in enumerate(rows, 1):
        out.append(f"{index}\n{start} --> {end}\n{text}\n")
    return "\n".join(out)


def _tmp(content: str) -> str:
    handle, path = tempfile.mkstemp(suffix=".srt")
    os.close(handle)
    with open(path, "w", encoding="utf-8") as stream:
        stream.write(content)
    return path


class SemanticLossTest(unittest.TestCase):
    def test_a_collapsed_cue_is_flagged(self):
        blocks = [(1, "00:00:01,000 --> 00:00:02,000", "kim?")]
        sources = {"1": "Shall there be no rest from them?"}
        self.assertEqual(
            gui._delivery_semantic_loss_ids(blocks, sources), ["1"])

    def test_a_real_translation_is_not_flagged(self):
        blocks = [(1, "00:00:01,000 --> 00:00:02,000",
                   "Onlardan hiç kurtuluş olmayacak mı?")]
        sources = {"1": "Shall there be no rest from them?"}
        self.assertEqual(gui._delivery_semantic_loss_ids(blocks, sources), [])

    def test_a_cue_without_a_source_is_skipped(self):
        blocks = [(1, "00:00:01,000 --> 00:00:02,000", "kim?")]
        self.assertEqual(gui._delivery_semantic_loss_ids(blocks, {}), [])

    def test_a_short_source_never_counts(self):
        blocks = [(1, "00:00:01,000 --> 00:00:02,000", "Ne?")]
        self.assertEqual(
            gui._delivery_semantic_loss_ids(blocks, {"1": "What?"}), [])


class GarbleIdsTest(unittest.TestCase):
    def test_dotless_i_corruption_is_flagged(self):
        blocks = [(1, "00:00:01,000 --> 00:00:02,000", "Bir anda mılan düşüyor")]
        sources = {"1": "SUDDENLY MILAN STUMBLES AND FALLS DOWN"}
        self.assertEqual(gui._delivery_garble_ids(blocks, sources), ["1"])

    def test_a_term_kept_from_a_neighbouring_cue_is_not_garble(self):
        # 'carnyx' kendi cue'sunun kaynağında yok, komşusunda var.
        blocks = [
            (1, "00:00:01,000 --> 00:00:02,000", "Bir carnyx bulundu burada"),
            (2, "00:00:03,000 --> 00:00:04,000", "Boru sesi duyuldu sonra"),
        ]
        sources = {
            "1": "Something was discovered right here at this very spot",
            "2": ("A carnyx horn was blown and the sound carried across the "
                  "whole of the northern valley below them"),
        }
        self.assertEqual(gui._delivery_garble_ids(blocks, sources), [])

    def test_a_non_latin_source_silences_the_source_bound_rules(self):
        # Rusça/Arapça kaynakta 'dux' ya da madde işareti 'a' aranamaz.
        blocks = [(1, "00:00:01,000 --> 00:00:02,000",
                   '"femina dux facti", yani kadın öncüydü')]
        sources = {"1": 'يقول "فيرجيل"، "فيمينا دوكس فاكتي"'}
        self.assertEqual(gui._delivery_garble_ids(blocks, sources), [])

    def test_an_invented_word_is_still_caught(self):
        blocks = [(1, "00:00:01,000 --> 00:00:02,000",
                   "Burada simwolika denen bir şey var")]
        # Latin kaynak eşiği: kural ancak kaynak gerçekten Latin alfabeliyse
        # konuşur, o yüzden gerçekçi uzunlukta bir kaynak veriliyor.
        sources = {"1": "There is something here they call symbolism today",
                   "2": ("the quick brown fox jumps over a lazy dog while "
                         "seven bright ships sail past every harbour wall "
                         "and many people watch them from their windows")}
        self.assertEqual(gui._delivery_garble_ids(blocks, sources), ["1"])

    def test_a_file_too_short_to_judge_stays_silent(self):
        # Kaynak sözcük dağarcığı bir karar vermeye yetmiyorsa kaynağa bağlı
        # kurallar susar; uydurma sanılan şey meşru bir alıntı olabilir.
        blocks = [(1, "00:00:01,000 --> 00:00:02,000", "simwolika")]
        self.assertEqual(
            gui._delivery_garble_ids(blocks, {"1": "symbolism"}), [])

    def test_clean_text_is_clean(self):
        blocks = [(1, "00:00:01,000 --> 00:00:02,000", "Merhaba dünya")]
        self.assertEqual(
            gui._delivery_garble_ids(blocks, {"1": "Hello world"}), [])


class DotlessIRuleTest(unittest.TestCase):
    """R9: ALL-CAPS kaynağın Türkçe kurallarıyla küçültülmesi."""

    def test_the_caps_lowering_defect(self):
        for target, source in (("sahıb", "THE SRI GURU GRANTH SAHIB."),
                               ("pattı", "MEMBERS OF PATTI'S CONGREGATION"),
                               ("mılan", "MILAN STUMBLES"),
                               ("Sıgmund", "SIGMUND FREUD")):
            self.assertTrue(
                ht._garble_dotless_i_tokens(target, source), (target, source))

    def test_ordinary_turkish_words_are_untouched(self):
        for target, source in (("kadın geldi", "the woman came"),
                               ("ışık vardı", "there was light"),
                               ("kısa bir an", "a short moment")):
            self.assertEqual(ht._garble_dotless_i_tokens(target, source), [],
                             target)

    def test_a_word_the_source_already_spells_that_way_is_kept(self):
        self.assertEqual(ht._garble_dotless_i_tokens("kadın", "kadın"), [])

    def test_ignorecase_does_not_erase_the_very_difference(self):
        # 'ı'.upper() == 'I' olduğu için re.IGNORECASE ikisini eşleştirir;
        # kural bu yüzden büyük/küçük harfi elle indirir.
        self.assertTrue(ht._garble_dotless_i_tokens("sahıb", "SAHIB"))


class ProperNameHarmonyTest(unittest.TestCase):
    """R5: yabancı özel adda ek telaffuza göre gelir, yazılışa göre değil."""

    def test_foreign_names_are_no_longer_flagged(self):
        for text, source in (("François'yı gördün mü?", "Have you seen him?"),
                             ("Bardo Thödol'e göre", "according to the Bardo")):
            rules = {rule for _tok, rule in ht.find_garble_tokens(text, source)}
            self.assertNotIn("R5_vowel_harmony", rules, text)

    def test_a_lowercase_stem_is_still_checked(self):
        rules = {rule for _tok, rule in ht.find_garble_tokens("sahıb'e", "")}
        self.assertIn("R5_vowel_harmony", rules)

    def test_a_turkish_proper_name_is_still_checked(self):
        # Ayıraç büyük harf değil, gövdenin KENDİ uyumu: "Mısır" (ı-ı)
        # Türkçe biçimlidir, dolayısıyla ekindeki hata gerçektir.
        rules = {rule for _tok, rule in ht.find_garble_tokens("Mısır'in", "")}
        self.assertIn("R5_vowel_harmony", rules)

    def test_stem_harmony_classifier(self):
        self.assertTrue(ht._garble_stem_is_harmonic("Mısır"))
        self.assertTrue(ht._garble_stem_is_harmonic("Pattı"))
        self.assertFalse(ht._garble_stem_is_harmonic("François"))
        self.assertFalse(ht._garble_stem_is_harmonic("Thödol"))


class SourceBoundRulesTest(unittest.TestCase):
    def test_a_suffixed_loanword_is_bound_to_its_stem(self):
        self.assertTrue(ht._garble_stem_in_source("carnyxlerin", "a carnyx"))
        self.assertTrue(
            ht._garble_stem_in_source("conquistadorları", "the conquistadors"))
        self.assertFalse(ht._garble_stem_in_source("simwolika", "symbolism"))

    def test_a_list_marker_present_in_the_source_is_not_garble(self):
        self.assertEqual(
            ht.find_garble_tokens("a) ülkenin savunması", "a) for the defence"),
            [])


class AuditWiringTest(unittest.TestCase):
    def _audit(self, source_rows, output_rows):
        spath = _tmp(_srt(source_rows))
        opath = _tmp(_srt(output_rows))
        try:
            return gui._subtitle_delivery_audit(spath, opath)
        finally:
            os.unlink(spath)
            os.unlink(opath)

    def test_semantic_loss_turns_ok_into_review_but_not_a_hard_error(self):
        rows_src = [("00:00:01,000", "00:00:02,000",
                     "Shall there be no rest from them?")]
        rows_out = [("00:00:01,000", "00:00:02,000", "kim?")]
        audit = self._audit(rows_src, rows_out)
        self.assertEqual(audit.get("semantic_loss_ids"), ["1"])
        self.assertEqual(audit.get("status"), "review")
        self.assertIn("semantic_loss",
                      {row["reason"] for row in audit["review_details"]})

    def test_the_hard_gate_is_unchanged_by_the_new_signals(self):
        audit = {"status": "review", "semantic_loss_ids": ["1"],
                 "garble_ids": ["2"]}
        self.assertFalse(gui._delivery_audit_has_hard_error(audit))


if __name__ == "__main__":
    unittest.main()
