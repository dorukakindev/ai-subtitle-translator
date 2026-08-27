# -*- coding: utf-8 -*-
"""2026-08-27 dizi koşusu devri (`Raporlar/OPUS/bug-devri-20260827-dizi-logu.md`).

Her madde gerçek teslim dosyasında ölçülmüştü; buradaki testler ölçümün
kilididir.
"""
import unittest

import sdh_cleaner as sdh
import subtitle_translator_gui as gui


class PilcrowMusicNoteTest(unittest.TestCase):
    """Madde 1: EIA-608/SCC kökenli altyazıda nota karakteri ¶ olarak yazılıyor.

    `black market S01E06`: 34 ¶, hiç ♪ yok; 17 cue'nun gövdesi tam olarak
    `¶¶`. SDH temizliği bunları düşürmediği için hem teslime gidiyor hem de
    kaynak == aday olduğu için "çevrilmemiş" sayılıyorlardı.

    ¶ genel nota kümesine GİREMEZ: mojibake dosyalarda gerçek harfin baytıdır
    (`GyÃ¶rgy` içindeki ¶, ö'nün ikinci baytı). Arşiv ölçümü: ¶ geçen 80
    cue'nun 68'i harfsiz (nota), 12'si mojibake — düzeltme ikisini de doğru
    ayırıyor.
    """

    def test_pilcrow_only_cue_is_sdh(self):
        for probe in ("¶¶", "¶", "¶ ¶", "¶¶¶"):
            with self.subTest(probe=probe):
                self.assertTrue(sdh.is_structural_sdh_cue(probe))
                self.assertTrue(sdh.src_is_sfx_only(
                    probe, allow_caps_heuristic=True))
                self.assertTrue(gui._source_cue_is_delivery_removable(probe))

    def test_music_note_cue_still_recognised(self):
        for probe in ("♪♪", "♫♫", "♪ ♪", "[ ♪♪♪ ]"):
            with self.subTest(probe=probe):
                self.assertTrue(gui._source_cue_is_delivery_removable(probe))

    def test_mojibake_letters_are_not_music_notes(self):
        """¶ HARFLE birlikte geçiyorsa nota değildir - cue korunmalı."""
        for probe in ("GyÃ¶rgy SimÃ³, ErzsÃ©bet Farkas.",
                      "BÃ¶zsi what?!",
                      "I'm BÃ¶zsi TÃ³th."):
            with self.subTest(probe=probe):
                self.assertFalse(sdh.is_structural_sdh_cue(probe))
                self.assertFalse(sdh.src_is_sfx_only(
                    probe, allow_caps_heuristic=True))
                self.assertFalse(gui._source_cue_is_delivery_removable(probe))

    def test_lyric_with_words_is_not_dropped_as_a_bare_note(self):
        """Nota ARASINDA sözcük varsa cue şarkı sözüdür, çıplak nota değil."""
        self.assertFalse(sdh.is_structural_sdh_cue("¶ La la la ¶"))
        self.assertFalse(sdh.is_structural_sdh_cue("♪ La la la ♪"))


class FindingAddressTest(unittest.TestCase):
    """Madde 4: `bulgular.jsonl` cue numarası teslim dosyasını göstermiyordu.

    Denetim listelerinin çoğu TESLİM kimliği üretir; zaman damgası ise yalnız
    kaynakta aranıyordu. Numaralar iki dosyada da 1..N olduğu için kaynakta
    "bulunuyor" ve YANLIŞ cue'nun zamanı yazılıyordu.
    """

    SRC = [("1", "00:00:01,000 --> 00:00:02,000", "One."),
           ("2", "00:00:03,000 --> 00:00:04,000", "Two."),
           ("3", "00:00:05,000 --> 00:00:06,000", "Three.")]
    # Teslimde numaralar kaymış (eski orta imza böyle yapıyordu)
    OUT = [("2", "00:00:01,000 --> 00:00:02,000", "Bir."),
           ("3", "00:00:03,000 --> 00:00:04,000", "Two."),
           ("4", "00:00:05,000 --> 00:00:06,000", "Üç.")]

    def _rows(self, block):
        return [{"name": "x", "source_path": "s.srt", "output_path": "o.srt",
                 "delivery_audit": block}]

    def _build(self, block):
        def read_cues(path):
            return self.SRC if str(path) == "s.srt" else self.OUT
        return gui.build_finding_rows(self._rows(block), read_cues=read_cues)

    def test_output_side_id_resolves_against_the_delivery(self):
        found = self._build({"untranslated_fragment_ids": ["3"]})
        self.assertEqual(len(found), 1)
        # Teslimdeki #3 -> 00:00:03; kaynaktaki #3 (00:00:05) DEĞİL
        self.assertEqual(found[0]["zaman"], "00:00:03,000 --> 00:00:04,000")
        self.assertEqual(found[0]["teslim"], "Two.")
        self.assertEqual(found[0]["teslim_cue_no"], "3")
        # Kaynak metni de zaman damgasından çözülür, numaradan değil
        self.assertEqual(found[0]["kaynak"], "Two.")

    def test_source_side_id_resolves_against_the_source(self):
        found = self._build({"missing_dialogue_ids": ["3"]})
        self.assertEqual(len(found), 1)
        self.assertEqual(found[0]["zaman"], "00:00:05,000 --> 00:00:06,000")
        self.assertEqual(found[0]["kaynak"], "Three.")

    def test_every_finding_carries_a_timestamp(self):
        found = self._build({
            "untranslated_fragment_ids": ["2", "3", "4"],
            "missing_dialogue_ids": ["1", "2"],
            "residual_sdh_ids": ["4"],
        })
        self.assertTrue(found)
        for finding in found:
            with self.subTest(finding=finding["sinif"] + finding["cue_no"]):
                self.assertTrue(str(finding["zaman"]).strip())

    def test_delivery_address_is_empty_when_the_cue_was_removed(self):
        """Teslimde olmayan cue için uydurma adres verilmez."""
        found = self._build({"missing_dialogue_ids": ["1"]})
        self.assertEqual(len(found), 1)
        # 00:00:01 teslimde VAR, o yüzden dolu olmalı
        self.assertEqual(found[0]["teslim_cue_no"], "2")

    def test_jsonl_carries_the_delivery_address(self):
        def read_cues(path):
            return self.SRC if str(path) == "s.srt" else self.OUT
        body = gui.build_findings_jsonl(
            self._rows({"untranslated_fragment_ids": ["3"]}),
            read_cues=read_cues)
        self.assertIn("teslim_cue_no", body)


class CriticalFindingsReachJsonlTest(unittest.TestCase):
    """Madde 5: KRİTİK sınıflar adreslenebilir çıktıya hiç girmiyordu.

    Tarama kimlikleri hesaplayıp `len()` ile atıyordu; sayı rapora giriyor
    ama cue düzeyi kayıt üretilemiyordu. Bu koşuda 20 KRİTİK bulgunun hiçbiri
    `bulgular.jsonl`'e ulaşmadı.
    """

    def test_scan_keeps_ids_for_critical_classes(self):
        for key in ("cue_id_leak_ids", "source_residue_ids",
                    "missing_predicate_ids", "format_coverage_lost_ids"):
            with self.subTest(key=key):
                self.assertIn(key, gui._FINDING_CLASSES)

    def test_leaked_cue_number_becomes_an_addressable_finding(self):
        blocks = [("106", "00:00:01,000 --> 00:00:02,000", "Bir cümle."),
                  ("107", "00:00:03,000 --> 00:00:04,000",
                   "Sadakati bu kadar yücelten sen,\n108"),
                  ("109", "00:00:05,000 --> 00:00:06,000", "Son cümle.")]
        scan = gui._scan_delivery_blocks(blocks, [])
        self.assertIn("107", scan.get("cue_id_leak_ids") or [])
        self.assertEqual(scan.get("cue_id_leak"), 1)

        rows = [{"name": "x", "source_path": "s.srt", "output_path": "o.srt",
                 "delivery_scan": {"cue_id_leak_ids":
                                   scan["cue_id_leak_ids"]}}]
        found = gui.build_finding_rows(
            rows, read_cues=lambda path: blocks)
        self.assertEqual(len(found), 1)
        self.assertEqual(found[0]["cue_no"], "107")
        self.assertEqual(found[0]["teslim_cue_no"], "107")
        self.assertTrue(found[0]["zaman"])

    def test_counts_are_still_reported(self):
        """Sayılar kaldırılmadı - kimlikler YANINA eklendi."""
        blocks = [("1", "00:00:01,000 --> 00:00:02,000", "Bir.")]
        scan = gui._scan_delivery_blocks(blocks, [])
        for key in ("cue_id_leak", "source_residue", "missing_predicate"):
            with self.subTest(key=key):
                self.assertIsInstance(scan.get(key), int)


class DeliveryFontTagTest(unittest.TestCase):
    """Madde 3: `<font color>` teslimde kararsız kalıyordu.

    `restore_format_tags` yalnız kaynağı TAM SARAN etiketi geri koyabiliyor;
    gerisi modelin etiketi koruyup korumamasına kalıyordu. Real Hustle E01:
    kaynakta 525 cue etiketli, teslimde 78. Etiket sadık biçimde geri
    konamadığına göre tutarlı tek durum onu kaldırmak.
    """

    def _delivered(self, text):
        blocks = [("1", "00:00:05,000 --> 00:00:07,000", text)]
        result = gui._prepare_upload_ready_blocks(blocks, "Turkish")
        return result[0][2]

    def test_full_wrap_font_tag_is_removed(self):
        self.assertEqual(
            self._delivered('<font color="#ffff00">Renkli satır.</font>'),
            "Renkli satır.")

    def test_inline_font_tag_is_removed(self):
        self.assertEqual(
            self._delivered('Yarısı <font color="#00ff00">renkli</font> satır.'),
            "Yarısı renkli satır.")

    def test_italic_and_bold_survive(self):
        self.assertEqual(self._delivered("<i>Eğik.</i>"), "<i>Eğik.</i>")
        self.assertEqual(self._delivered("<b>Kalın.</b>"), "<b>Kalın.</b>")

    def test_position_tag_removal_is_unchanged(self):
        """Konum kodu teslimde ZATEN kaldırılıyordu; renk değişikliği ona
        dokunmadı (ayrı sayaç: position_tags_removed)."""
        self.assertEqual(self._delivered(r"{\an8}Üstte."), "Üstte.")


class MidwordSpaceFalseAlarmTest(unittest.TestCase):
    """Madde 6: `_midword_space_ids` 2. kuralı doğru Türkçeyi işaretliyordu.

    Teslim arşivinde ölçüm: 165 bulgu, 22 farklı çift; `orta çağ` (53),
    `tarih öncesi` (33), `yasa dışı` (18) gibi TDK'da AYRI yazılan sözcükler
    baskındı. Sıklıkla ayırmayı denedim, tutmadı (`orta çağ` dosya başına
    ort. 5,8; gerçek bulgu `dünya nın` 3,0). Düzeltmeden sonra 165 -> 4.
    """

    def _ids(self, *texts):
        blocks = [(str(i + 1), "00:00:0%d,000 --> 00:00:0%d,500" % (i, i + 1),
                   t) for i, t in enumerate(texts)]
        return gui._midword_space_ids(blocks, None)

    def test_real_split_word_is_still_caught(self):
        self.assertEqual(
            self._ids("Piram itler harika.", "Piramitler harika.",
                      "Piramitler yine."),
            ["1"])

    def test_tdk_separate_compounds_are_not_flagged(self):
        for separate, joined in (("orta çağ", "ortaçağ"),
                                 ("tarih öncesi", "tarihöncesi"),
                                 ("yasa dışı", "yasadışı"),
                                 ("yağlı boya", "yağlıboya"),
                                 ("demir yolu", "demiryolu"),
                                 ("bal mumu", "balmumu")):
            with self.subTest(pair=separate):
                self.assertEqual(
                    self._ids("Bu %s bir örnektir." % separate,
                              "Burada %s var." % joined,
                              "Yine %s geçiyor." % joined),
                    [])

    def test_punctuation_between_words_is_not_a_midword_space(self):
        """Araya tırnak/virgül giriyorsa bölünme değil, noktalamadır."""
        self.assertEqual(
            self._ids('"gezinti"nin karşıtı.', "gezintinin biri.",
                      "gezintinin diğeri."),
            [])
        self.assertEqual(
            self._ids("- O neydi? - Hiç, bir ifade işte.",
                      "hiçbir şey yok.", "hiçbir zaman."),
            [])

    def test_whitelist_has_no_unreachable_entries(self):
        r"""Sözcükler `[^\W\d_]+` ile bulunuyor; kesme işaretli anahtar
        hiçbir zaman eşleşemez (listede böyle bir yazım hatası vardı)."""
        for left, right in gui._MIDWORD_LEGITIMATE_PAIRS:
            with self.subTest(pair=(left, right)):
                self.assertRegex(left, r"^[^\W\d_]+$")
                self.assertRegex(right, r"^[^\W\d_]+$")


class PartialRunReportDirTest(unittest.TestCase):
    """Madde 7: yarım koşuda rapor iç içe klasöre yazılıyordu.

    `row["output_path"]` kısmi dosyadır ve zaten `.../Raporlar/Kurtarma/`
    altındadır; `parent / "Raporlar"` demek raporu
    `.../Raporlar/Kurtarma/Raporlar/` içine gömüyordu (9 bölümde oluştu).
    """

    def test_normal_output_writes_next_to_the_file(self):
        got = gui._delivery_report_dir(r"D:\iş\bölüm\x.srt")
        self.assertEqual(got.name, "Raporlar")
        self.assertEqual(got.parent.name, "bölüm")

    def test_partial_output_reuses_the_existing_reports_folder(self):
        got = gui._delivery_report_dir(
            r"D:\iş\bölüm\Raporlar\Kurtarma\x.partial.srt")
        self.assertEqual(got.name, "Raporlar")
        self.assertEqual(got.parent.name, "bölüm")
        self.assertNotIn("Kurtarma", str(got))


class LineBreakKeepsTagsWholeTest(unittest.TestCase):
    """Madde 2: satır kırma `<font\ncolor=...>` üretiyordu — GİZİL.

    Bugünkü kodda üretilemiyor: `_find_best_split` etiket içindeki boşluğu
    aday saymıyor (`_position_is_inside_tag`). Rapordaki 20 cue eski
    sürümün çıktısı. Sınıf gerçekten yaşandığı için kilitleniyor.
    """

    BROKEN = __import__("re").compile(r"<[^>\n]*\n|\{[^}\n]*\n")

    def _wrapped(self, text):
        value = gui._break_to_line_budget(text, gui._MAX_LINES)
        value = gui._rebalance_line_break(value)
        return gui._redistribute_two_lines(value)

    def test_three_font_wrapped_lines_are_rewrapped_without_splitting_tags(self):
        text = ('<font color="#ffff00">Bir iki uc dort</font>\n'
                '<font color="#ffff00">bes alti yedi sekiz</font>\n'
                '<font color="#ffff00">dokuz on onbir oniki</font>')
        self.assertIsNone(self.BROKEN.search(self._wrapped(text)))

    def test_tag_with_an_inner_space_is_never_a_split_point(self):
        for text in (
            'Bu cumlenin ortasinda <font color="#ff0000">renkli</font> bir '
            'sozcuk var ve satir cok uzun oldugu icin kirilmasi gerekiyor',
            'aaaa bbbb cccc dddd <font color="#00ff00">eeee</font> ffff '
            'gggg hhhh iiii jjjj kkkk llll',
            'Baslangic metni burada <font face="Arial, Helvetica">renkli '
            'kisim</font> ve devami boyle uzayip gidiyor',
            r'{\an8\pos(10, 20)}Bu satir cok uzun oldugu icin kirilmak '
            r'zorunda kalacak bir sekilde yazildi',
        ):
            with self.subTest(text=text[:40]):
                self.assertIsNone(self.BROKEN.search(self._wrapped(text)))


if __name__ == "__main__":
    unittest.main()
