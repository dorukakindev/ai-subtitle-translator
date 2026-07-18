"""S04E15 (Vampires of PhilaHELLphia) vakası — plans/s04e12-cue-shift-without-repair-
brief.md Görev 6: kısa/ünlem bir cue komşusunun diyaloğunu yutunca komşu cue boş
kalıyor; bu gerçek diyalog kaybı SDH temizliğiyle karışıp SESSİZCE siliniyordu.

Kök neden iki parçalıydı:
1. `_is_untranslated(src, "")` her zaman False dönüyordu — boş çeviriyi hiç
   'onarılması gerekiyor' diye işaretlemiyordu.
2. `clean_sdh_blocks` girdi metni ZATEN boşsa (temizlenecek hiçbir SFX/köşeli
   parantez içeriği yoktu) bile bloğu sessizce düşürüyordu.
İkisi birlikte: gerçek diyaloglu bir cue boşalınca hem onarım listesine hiç
girmiyor hem de final dosyadan iz bırakmadan siliniyordu.
"""
import unittest

import subtitle_translator_gui as gui
import sdh_cleaner as sdh


class IsUntranslatedEmptyTest(unittest.TestCase):
    def test_real_dialogue_with_empty_translation_is_flagged(self):
        self.assertTrue(gui._is_untranslated("WHAT A GREAT ROOM THIS IS. WOW!", ""))

    def test_sfx_only_source_with_empty_translation_not_flagged(self):
        # SFX-only kaynak boş çeviriyle de meşru — clean_sdh nasılsa boşa indirir.
        self.assertFalse(gui._is_untranslated("[ LAUGHS ]", ""))
        self.assertFalse(gui._is_untranslated("[ BOTH LAUGH ]", ""))
        self.assertFalse(gui._is_untranslated("♪♪♪", ""))

    def test_mixed_sfx_and_dialogue_with_empty_translation_is_flagged(self):
        # S04E15 #17 tarzı: SFX etiketi + gerçek diyalog aynı cue'da.
        self.assertTrue(gui._is_untranslated("[ Chuckling ] ONLY IN NEW YORK.", ""))

    def test_empty_source_never_flagged(self):
        self.assertFalse(gui._is_untranslated("", ""))
        self.assertFalse(gui._is_untranslated("", "bir şey"))

    def test_existing_source_equals_target_behavior_unchanged(self):
        # Mevcut davranış (kaynak==hedef tespiti, karışık harfli gerçek cümle) regresyona uğramamalı.
        self.assertTrue(gui._is_untranslated(
            "This is a really long sentence about something.",
            "This is a really long sentence about something.",
        ))
        # ALL CAPS başlık/tabela metni hâlâ muaf.
        self.assertFalse(gui._is_untranslated("ODDITIES SEASON FOUR", "ODDITIES SEASON FOUR"))


class CleanSdhPreservesRealDialogueGapsTest(unittest.TestCase):
    # NOT: clean_sdh_blocks KAYNAK-FARKINDA. src_map verilirse boş çeviri yalnızca
    # kaynağı gerçek diyalogsa korunur; kaynağı boş/SFX olan cue'lar düşürülür
    # (aksi hâlde kaynak-boş cue'lar ekranda [ÇEVİRİ EKSİK] olarak görünürdü —
    # Clash of the Gods Hades regresyonu, 2026-07-08). src_map yoksa boş cue düşer.

    def _src(self, **kw):
        return {str(k): v for k, v in kw.items()}

    def test_real_dialogue_empty_cue_preserved_when_src_map_given(self):
        blocks = [
            ("361", "00:00:01,000 --> 00:00:02,000",
             "Evan: Oo. [KIKIRDAR] Ne harika bir oda bu, vay be!"),
            ("362", "00:00:02,000 --> 00:00:03,000", ""),
            ("363", "00:00:03,000 --> 00:00:04,000", "Hey, Laura."),
        ]
        src_map = self._src(**{"361": "...", "362": "WHAT A GREAT ROOM THIS IS. WOW!",
                               "363": "HEY, LAURA."})
        result = sdh.clean_sdh_blocks(blocks, src_map=src_map)
        ids = [b[0] for b in result]
        self.assertIn("362", ids, "kaynağı gerçek diyalog olan boş cue korunmalı")
        self.assertEqual(dict((b[0], b[2]) for b in result)["362"], "")

    def test_empty_source_empty_cue_dropped_even_with_src_map(self):
        # REGRESYON KİLİDİ (Clash of the Gods Hades): kaynağı ZATEN boş olan cue,
        # çevirisi de boşsa DÜŞÜRÜLMELİ — ekranda [ÇEVİRİ EKSİK] göstermemeli.
        blocks = [
            ("1", "00:00:01,000 --> 00:00:02,000", ""),
            ("2", "00:00:02,000 --> 00:00:03,000", "Normal replik."),
        ]
        src_map = self._src(**{"1": "", "2": "NORMAL LINE."})
        result = sdh.clean_sdh_blocks(blocks, src_map=src_map)
        ids = [b[0] for b in result]
        self.assertNotIn("1", ids, "kaynağı boş cue düşürülmeli")
        self.assertIn("2", ids)

    def test_sfx_source_empty_cue_dropped_with_src_map(self):
        blocks = [("5", "00:00:01,000 --> 00:00:02,000", "")]
        src_map = self._src(**{"5": "[ MUSIC ]"})
        result = sdh.clean_sdh_blocks(blocks, src_map=src_map)
        self.assertEqual(result, [], "kaynağı SFX-only olan boş cue düşürülmeli")

    def test_empty_cue_dropped_without_src_map(self):
        # src_map verilmezse güvenli eski davranış: boş cue düşer.
        blocks = [("1", "00:00:01,000 --> 00:00:02,000", ""),
                  ("2", "00:00:02,000 --> 00:00:03,000", "Var.")]
        result = sdh.clean_sdh_blocks(blocks)
        self.assertEqual([b[0] for b in result], ["2"])

    def test_genuine_sfx_only_cue_still_dropped(self):
        # Dolu SFX metniyle gelip SDH temizliğiyle boşa inen cue hâlâ düşürülmeli.
        blocks = [
            ("28", "00:00:01,000 --> 00:00:02,000", "[KAHKAHA]"),
            ("29", "00:00:02,000 --> 00:00:03,000", "Normal replik."),
        ]
        result = sdh.clean_sdh_blocks(blocks, src_map=self._src(**{"28": "[ LAUGHS ]", "29": "X."}))
        ids = [b[0] for b in result]
        self.assertNotIn("28", ids)
        self.assertIn("29", ids)

    def test_end_to_end_reaches_repair_pass(self):
        """src_map ile korunan #362 artık _repair_untranslated_sync'in kriterine
        (hata_indices) giriyor mu — Görev 6 hedefinin tam doğrulaması."""
        blocks = [
            ("361", "00:00:01,000 --> 00:00:02,000",
             "Evan: Oo. [KIKIRDAR] Ne harika bir oda bu, vay be!"),
            ("362", "00:00:02,000 --> 00:00:03,000", ""),
        ]
        raw_src_map = {"362": "WHAT A GREAT ROOM THIS IS. WOW!"}
        cleaned = sdh.clean_sdh_blocks(blocks, src_map=raw_src_map)
        flagged = [
            idx for (idx, ts, text) in cleaned
            if raw_src_map.get(str(idx))
            and (str(text).startswith("[HATA") or gui._is_untranslated(raw_src_map[str(idx)], str(text)))
        ]
        self.assertIn("362", flagged)


class RepairSyncDropsSfxOnlyTest(unittest.TestCase):
    """Explorer 1 #36/#636 vakası: _repair_untranslated_sync clean_sdh'ten SONRA
    çalışıyor. Kaynağı SFX/müzik-only olan bir [HATA] cue'yu onarmaya çalışırsa,
    API'den taze bir SDH çevirisi ("[MÜZİK ÇALIYOR]") döner ve bu artık clean_sdh
    tarafından bir daha temizlenmediği için final dosyaya sızar. Fix: böyle
    cue'lar onarılmaz, doğrudan düşürülür — client=None olsa bile (API'ye hiç
    gerek yok, bu yüzden mock client gerekmez)."""

    def test_sfx_only_source_hata_cue_dropped_not_repaired(self):
        blocks = [
            ("36", "00:00:01,000 --> 00:00:02,000", "[HATA]"),
            ("37", "00:00:02,000 --> 00:00:03,000", "Normal replik."),
        ]
        raw_src_map = {"36": "[MUSIC PLAYING]", "37": "NORMAL LINE."}
        out, repaired = gui._repair_untranslated_sync(
            blocks, raw_src_map, client=None, src_lang="English", tgt_lang="Turkish")
        ids = [b[0] for b in out]
        self.assertNotIn("36", ids, "SFX-only kaynaklı [HATA] cue düşürülmeli")
        self.assertIn("37", ids)
        self.assertEqual(repaired, 0)

    def test_real_dialogue_hata_cue_not_dropped_without_client(self):
        # client yoksa onarılamaz ama SFX-only OLMADIĞI için de düşürülmemeli —
        # [HATA] olarak kalıp _fill_hata_with_source'a düşmeli (görünür kalsın).
        blocks = [("362", "00:00:01,000 --> 00:00:02,000", "[HATA]")]
        raw_src_map = {"362": "WHAT A GREAT ROOM THIS IS. WOW!"}
        out, repaired = gui._repair_untranslated_sync(
            blocks, raw_src_map, client=None, src_lang="English", tgt_lang="Turkish")
        self.assertEqual(len(out), 1)
        self.assertEqual(out[0][0], "362")
        self.assertEqual(out[0][2], "[HATA]")
        self.assertEqual(repaired, 0)

    def test_mixed_sfx_and_dialogue_hata_cues(self):
        blocks = [
            ("1", "00:00:01,000 --> 00:00:02,000", "Zaten çevrili."),
            ("2", "00:00:02,000 --> 00:00:03,000", "[HATA]"),   # SFX-only kaynak
            ("3", "00:00:03,000 --> 00:00:04,000", "[HATA]"),   # gerçek diyalog
        ]
        raw_src_map = {"1": "ALREADY TRANSLATED.", "2": "[ MUSIC PLAYING ]",
                       "3": "REAL DIALOGUE LINE."}
        out, repaired = gui._repair_untranslated_sync(
            blocks, raw_src_map, client=None, src_lang="English", tgt_lang="Turkish")
        ids = [b[0] for b in out]
        self.assertEqual(ids, ["1", "3"], "yalnızca SFX-only #2 düşürülmeli, sıra korunmalı")

    def test_no_hata_cues_returns_blocks_unchanged(self):
        blocks = [("1", "00:00:01,000 --> 00:00:02,000", "Tamamdır.")]
        out, repaired = gui._repair_untranslated_sync(
            blocks, {"1": "FINE."}, client=None, src_lang="English", tgt_lang="Turkish")
        self.assertEqual(out, blocks)
        self.assertEqual(repaired, 0)


if __name__ == "__main__":
    unittest.main()
