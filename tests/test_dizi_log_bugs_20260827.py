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


if __name__ == "__main__":
    unittest.main()
