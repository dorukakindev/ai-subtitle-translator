"""_content_shift_regions / detect_alignment_issues 'content_shift' (subtitle_translator_gui.py)
— kaynağa göre SÜREKLİ içerik-ötelemesi (id↔içerik kayması) olan bölgeyi sayı+özel-isim
anchor'larıyla yakalar. number_shift/adjacent_duplicate'in GÖREMEDİĞİ 'akıcı-ama-N-cue-kaymış'
gövde sınıfı (Sun Kings mini #480-510'un 26-cue saf-kayma kısmı bu yüzden sessizdi).

FP kritik: temiz/SOV dosyada offset ~0 salınır → tetiklememeli. min_offset=2 (±1 SOV'u ele),
min_run=4 (izole eşleşmeyi ele).
"""
import os
import unittest
from pathlib import Path

import subtitle_translator_gui as gui

_NAMES = ["Ptahshepses", "Niuserre", "Khamerernebty", "Abusir", "Djoser", "Sahure",
          "Userkaf", "Neferirkare", "Menkauhor", "Djedkare", "Unas", "Sekhemket"]
_FILLER = ["Alpha", "Beta", "Gamma", "Delta", "Epsilon", "Zeta", "Eta", "Theta",
           "Iota", "Kappa", "Lambda", "Sigma"]


def _blocks_and_src(region, shift):
    """30 cue; [region] aralığında çeviri içeriği kaynağa göre `shift` cue kaymış.
    Bölge dışı cue'lar birebir (offset 0). Her cue'da özel-isim anchor'ı var."""
    src_map, blocks = {}, []
    lo, hi = region
    for k in range(30):
        i = str(k)
        src_map[i] = f"The pharaoh {_NAMES[k % len(_NAMES)]} ruled well."
    for k in range(30):
        i = str(k)
        if lo <= k <= hi:
            name = _NAMES[(k + shift) % len(_NAMES)]
        else:
            name = _NAMES[k % len(_NAMES)]
        # bölge-dışı filler'ı benzersiz yap (adjacent_duplicate gürültüsü olmasın)
        blocks.append((i, "00:00:01,000 --> 00:00:02,000",
                       f"{name} adlı firavun {_FILLER[k % len(_FILLER)]} bölgesini yönetti."))
    return blocks, src_map


def _shift_finding(blocks, src_map):
    issues = gui.detect_alignment_issues(blocks, src_map)
    return next((x for x in issues if x["type"] == "content_shift"), None)


class SustainedShiftFlaggedTest(unittest.TestCase):
    def test_plus3_shift_over_12_cues_flagged(self):
        blocks, src_map = _blocks_and_src(region=(10, 21), shift=3)
        f = _shift_finding(blocks, src_map)
        self.assertIsNotNone(f)
        # bayraklı id kümesi kaymış bölgeyi kapsamalı
        self.assertTrue(set(str(i) for i in range(10, 22)).issubset(set(f["ids"])))

    def test_minus2_shift_flagged(self):
        blocks, src_map = _blocks_and_src(region=(8, 20), shift=-2)
        self.assertIsNotNone(_shift_finding(blocks, src_map))


class NoFalsePositiveTest(unittest.TestCase):
    def test_clean_1to1_not_flagged(self):
        blocks, src_map = _blocks_and_src(region=(10, 10), shift=0)  # kayma yok
        self.assertIsNone(_shift_finding(blocks, src_map))

    def test_sov_pm1_not_flagged(self):
        # anchor bir cue kaymış (±1, meşru SOV) — min_offset=2 altında → tetiklemez.
        blocks, src_map = _blocks_and_src(region=(10, 21), shift=1)
        self.assertIsNone(_shift_finding(blocks, src_map))

    def test_short_shift_below_min_run_not_flagged(self):
        # yalnız 2 cue kaymış (min_run=4 altı) → tetiklemez.
        blocks, src_map = _blocks_and_src(region=(10, 11), shift=3)
        self.assertIsNone(_shift_finding(blocks, src_map))

    def test_no_anchors_returns_empty(self):
        src_map = {str(k): "a plain line with no proper nouns" for k in range(10)}
        blocks = [(str(k), "00:00:01,000 --> 00:00:02,000", "özel isim olmayan düz satır")
                  for k in range(10)]
        self.assertEqual(gui._content_shift_regions(blocks, src_map), [])

    def test_empty_inputs(self):
        self.assertEqual(gui._content_shift_regions([], {}), [])


class RealFileNegativeTest(unittest.TestCase):
    """Temiz gpt-5.4 çıktısı content_shift üretmemeli (FP-yok kanıtı). Dosyalar
    session'a özgü/harici olduğundan yoksa atlanır."""
    CLEAN = Path(os.environ.get("SUNKINGS_CLEAN_GPT54", "")) if os.environ.get("SUNKINGS_CLEAN_GPT54") else None
    SRC = Path(r"E:/ALTYAZILAR/Altyazilar/HBO-Max/Unearthed/Season 10/Rise of Egypt's Sun Kings/Unearthed_S10E05_Rise of Egypt's Sun Kings.English(US).srt")
    FIN = Path(r"C:/Users/K/Downloads/ÇIKTI/Unearthed_S10E05_Rise of Egypt's Sun Kings.English(US).srt")

    def test_clean_gpt54_sun_kings_no_content_shift(self):
        if not (self.SRC.exists() and self.FIN.exists()):
            self.skipTest("Sun Kings kaynak/çıktı dosyaları bu ortamda yok")
        src_map = {i: t for i, ts, t in gui.parse_subtitle(str(self.SRC))}
        blocks = gui.parse_subtitle(str(self.FIN))
        issues = gui.detect_alignment_issues(blocks, src_map)
        shift = [x for x in issues if x["type"] == "content_shift"]
        self.assertEqual(shift, [], f"temiz dosyada content_shift FP: {shift}")


if __name__ == "__main__":
    unittest.main()
