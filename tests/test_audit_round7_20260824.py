# -*- coding: utf-8 -*-
"""2026-08-24 denetim turu: hitap çifti, teslim paritesi, birim, içerik dili."""
import inspect
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import hybrid_translate as ht
import series_memory as sm
import subtitle_translator_gui as g


class AddressPairsSurviveTheHandoffTest(unittest.TestCase):
    """Hybrid hitap kararlarını `{"A-B": "sen"}` diye gönderiyor; alıcı her
    anahtarı tek karakter sanıp `b`yi boş bırakıyordu. 15 gerçek dizi
    hafızasındaki 147 kaydın 147'sinde yönlü ilişki kayıptı ve prompt'a
    `- Anlatıcı-Mark Gatiss: 'siz'` diye bozuk tek bir ad yazılıyordu.
    """

    KNOWN = ["Anlatıcı", "Mark Gatiss", "Mary-Ann Ochota", "Clive"]

    def test_a_pair_key_is_split(self):
        self.assertEqual(sm._split_pair_key("Anlatıcı-Mark Gatiss", self.KNOWN),
                         ("Anlatıcı", "Mark Gatiss"))

    def test_a_hyphenated_name_is_not_broken(self):
        # 'Mary-Ann Ochota' kendi içinde tire taşıyor.
        self.assertEqual(sm._split_pair_key("Clive-Mary-Ann Ochota", self.KNOWN),
                         ("Clive", "Mary-Ann Ochota"))
        self.assertEqual(sm._split_pair_key("Mary-Ann Ochota-Clive", self.KNOWN),
                         ("Mary-Ann Ochota", "Clive"))

    def test_an_unknown_key_is_left_alone(self):
        self.assertIsNone(sm._split_pair_key("Bilinmeyen-Kisi", self.KNOWN))

    def test_a_plain_character_name_is_not_a_pair(self):
        self.assertIsNone(sm._split_pair_key("Anlatıcı", self.KNOWN))

    def test_an_existing_memory_is_repaired_on_load(self):
        data = {
            "characters": {"Anlatıcı": {}, "Mark Gatiss": {}},
            "address_map": [{"a": "Anlatıcı-Mark Gatiss", "b": "",
                             "register": "siz"}],
            "address_origins": {
                sm._character_identity("Anlatıcı-Mark Gatiss") + "\0": "s1e1"},
        }
        repaired = sm._repair_collapsed_address_pairs(data)
        self.assertEqual(repaired, 1)
        entry = data["address_map"][0]
        self.assertEqual((entry["a"], entry["b"]), ("Anlatıcı", "Mark Gatiss"))

    def test_the_origin_key_moves_with_the_entry(self):
        old_key = sm._character_identity("Anlatıcı-Mark Gatiss") + "\0"
        data = {
            "characters": {"Anlatıcı": {}, "Mark Gatiss": {}},
            "address_map": [{"a": "Anlatıcı-Mark Gatiss", "b": "",
                             "register": "siz"}],
            "address_origins": {old_key: "s1e1"},
        }
        sm._repair_collapsed_address_pairs(data)
        new_key = "\0".join((sm._character_identity("Anlatıcı"),
                             sm._character_identity("Mark Gatiss")))
        self.assertEqual(data["address_origins"].get(new_key), "s1e1")
        self.assertNotIn(old_key, data["address_origins"])

    def test_a_genuine_per_character_entry_is_untouched(self):
        # Bu biçim testle kilitli: {"Lee": "sen"} -> b boş kalmalı.
        data = {"characters": {"Lee": {}},
                "address_map": [{"a": "Lee", "b": "", "register": "sen"}],
                "address_origins": {}}
        self.assertEqual(sm._repair_collapsed_address_pairs(data), 0)


class EveryWritePathScansTheDeliveryTest(unittest.TestCase):
    """Teslim taraması üç akışta vardı, onarım-yolunda yoktu: onarılan dosya
    taranmadan teslim ediliyor ve bulguları rapora hiç girmiyordu."""

    def test_the_repair_only_path_scans(self):
        source = inspect.getsource(g.App._run_partial_repair_only_file)
        self.assertIn("_scan_delivery_blocks(", source)


class UnitConversionArithmeticIsCheckedTest(unittest.TestCase):
    """Guard kaynakta emperyal, hedefte metrik birim görünce cue'yu HİÇ
    denetlemeden geçiyordu. 202 gerçek dosyada böyle 88 cue var; doğrulayıcı
    1 bayrak veriyor ve o bayrak gerçek: '200-Pound ladies' -> '200 kiloluk'
    (doğrusu ~91 kg). Yanlış pozitif 0/88.
    """

    def test_a_wrong_conversion_is_caught(self):
        self.assertTrue(ht._imperial_conversion_is_wrong(
            "and sheep, and 200-Pound ladies", "koyunları ve 200 kiloluk kadınları"))

    def test_a_correct_conversion_passes(self):
        for src, tgt in (("a 200-pound man", "91 kiloluk bir adam"),
                         ("5 miles away", "8 kilometre uzakta"),
                         ("58 degrees Fahrenheit", "14 santigrat")):
            with self.subTest(src=src):
                self.assertFalse(ht._imperial_conversion_is_wrong(src, tgt))

    def test_an_unconverted_temperature_is_caught(self):
        self.assertTrue(ht._imperial_conversion_is_wrong(
            "58 degrees Fahrenheit", "58 derece"))

    def test_a_weight_that_is_not_currency_is_left_alone(self):
        # 'pounds' burada AĞIRLIK ve hedef de ağırlık birimi kullanıyor.
        self.assertFalse(ht._imperial_conversion_is_wrong(
            "20 pounds of feathers", "20 libre tüy"))

    def test_the_guard_no_longer_exempts_conversions_blindly(self):
        source = inspect.getsource(ht._numeric_token_mismatch)
        self.assertIn("_imperial_conversion_is_wrong", source)


class TheContentLanguageIsCheckedTest(unittest.TestCase):
    """İçerik dili YALNIZ kaynak dili 'Otomatik' seçiliyken denetleniyordu.
    Gerçek vaka: üç '.eng.srt' dosyasının içeriği tamamen Arapça ve hiçbir
    uyarı çıkmıyordu. %90+ Latin dışı bir metin İngilizce olamaz.
    """

    def test_a_turkish_language_name_resolves_to_its_iso_code(self):
        # 'İngilizce' iki harfe kırpılıp 'i̇' oluyordu ve 'English' ile
        # eşleşmediği için her İngilizce kaynağa sahte uyarı çıkıyordu.
        self.assertEqual(g._lang_iso639_1("İngilizce"), "en")
        self.assertEqual(g._lang_iso639_1("English"), "en")
        self.assertEqual(g._lang_iso639_1("Arapça"), "ar")
        self.assertEqual(g._lang_iso639_1("Yunanca"), "el")

    def test_arabic_text_is_measured_as_non_latin(self):
        self.assertGreater(
            g.non_latin_script_ratio("نعيش في عالم لا يتوقف عن الإنفاق"), 0.9)

    def test_english_text_is_not(self):
        self.assertEqual(
            g.non_latin_script_ratio("We live in a world that never stops"), 0.0)

    def test_turkish_text_is_latin(self):
        self.assertEqual(g.non_latin_script_ratio("Şu ılık günde iş çıkışı"), 0.0)

    def test_digits_and_punctuation_do_not_decide(self):
        self.assertEqual(g.non_latin_script_ratio("123 -- ... 456"), 0.0)

    def test_the_preflight_only_warns_for_latin_script_targets(self):
        source = inspect.getsource(g.scan_subtitle_preflight)
        self.assertIn("_LATIN_SCRIPT_LANGUAGE_CODES", source)
        self.assertIn("script_mismatch", source)


class TheShiftingPermissionIsScopedTest(unittest.TestCase):
    """'Bilgi kaydırmak tercih edilir' kuralı hangi cue'lar arasında
    geçerli olduğunu söylemiyordu; paylaşılan kural ise farklı cümlelerin
    anlamını taşımayı açıkça yasaklıyor."""

    def test_both_prompts_name_the_sentence_group(self):
        for source in (inspect.getsource(g._build_sync_system_prompt),
                       inspect.getsource(ht.build_system_prompt)):
            with self.subTest():
                self.assertIn("sentence_groups", source)
                self.assertIn("DIFFERENT sentences", source)



class FormatCoverageLossIsCountedTest(unittest.TestCase):
    """202 gerçek teslimde 1.111 cue'nun kaynağı baştan sona tek bir etiketle
    sarılıyken teslimi çıplak. Mevcut kod zinciri ölçülünce etiketleri DOĞRU
    geri koyuyor ve kayıp yeniden üretilemedi, bu yüzden otomatik düzeltme
    eklenmedi; sayaç sınıf tekrarlarsa görünür olsun diye var.
    """

    TS = "00:00:01,000 --> 00:00:03,000"

    def test_a_stripped_full_wrap_is_counted(self):
        blocks = [("1", self.TS, "Burası BBC Televizyon Servisi.")]
        src = {"1": "<i>This is the BBC Television Service.</i>"}
        self.assertEqual(g._format_coverage_lost_ids(blocks, src), ["1"])

    def test_a_kept_tag_is_not_counted(self):
        blocks = [("1", self.TS, "<i>Burası BBC.</i>")]
        src = {"1": "<i>This is the BBC.</i>"}
        self.assertEqual(g._format_coverage_lost_ids(blocks, src), [])

    def test_a_partially_tagged_source_is_not_counted(self):
        # Kısmi satır-içi etiket bilinçli olarak geri konmuyor.
        blocks = [("1", self.TS, "hayır dedi")]
        src = {"1": "he said <i>no</i>"}
        self.assertEqual(g._format_coverage_lost_ids(blocks, src), [])

    def test_an_untagged_source_is_not_counted(self):
        blocks = [("1", self.TS, "Merhaba")]
        self.assertEqual(g._format_coverage_lost_ids(blocks, {"1": "Hello"}), [])

    def test_the_delivery_scan_reports_it(self):
        source = inspect.getsource(g._scan_delivery_blocks)
        self.assertIn("format_coverage_lost", source)

if __name__ == "__main__":
    unittest.main()


class TheFormatCoverageCounterIsActuallyReportedTest(unittest.TestCase):
    """Sayaç hesaplanıp hiçbir yerde kullanılmıyordu: ne rapor alanları
    listesinde vardı ne log'da. Kendi yorumu "sınıf tekrarlarsa görünür
    olsun diye var" diyordu ama görünmüyordu.

    278 gerçek çiftte ölçüldü: bağlandığında 29 dosyada 574 bulgu görünür
    hâle geliyor (en çoğu A History of Art S01E02'de 225 cue).
    """

    TS = "00:00:01,000 --> 00:00:03,000"

    def test_the_count_is_a_number_and_the_ids_are_kept(self):
        blocks = [("1", self.TS, "Burası BBC."),
                  ("2", self.TS, "<i>İtalik kaldı.</i>")]
        cues = [("1", self.TS, "<i>This is the BBC.</i>"),
                ("2", self.TS, "<i>Italic kept.</i>")]
        scan = g._scan_delivery_blocks(blocks, cues)
        self.assertEqual(scan["format_coverage_lost"], 1)
        self.assertEqual(scan["format_coverage_lost_ids"], ["1"])

    def test_it_appears_in_the_report_lines(self):
        blocks = [("1", self.TS, "Burası BBC.")]
        cues = [("1", self.TS, "<i>This is the BBC.</i>")]
        scan = g._scan_delivery_blocks(blocks, cues)
        text = "\n".join(g.delivery_scan_report_lines(scan))
        self.assertIn("Kaynaktaki biçim etiketi kaybolmuş", text)

    def test_a_clean_file_reports_nothing(self):
        blocks = [("1", self.TS, "<i>Burası BBC.</i>")]
        cues = [("1", self.TS, "<i>This is the BBC.</i>")]
        scan = g._scan_delivery_blocks(blocks, cues)
        self.assertEqual(scan["format_coverage_lost"], 0)
        text = "\n".join(g.delivery_scan_report_lines(scan))
        self.assertNotIn("Kaynaktaki biçim etiketi", text)
