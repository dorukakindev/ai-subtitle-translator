"""Cue hizalama/kayma dedektörü (detect_alignment_issues) — id<->içerik uyuşmazlığı
sınıfı hatayı (S04E12/14/15'te doğrulandı) deterministik olarak yakalar.

Dört sinyal, her biri hatanın farklı tezahürünü kapsar; ve meşru çok-cue'lu cümle
yeniden dağıtımını (S04E07 gibi — Türkçe SOV söz dizimi) KAYMA sanmamalı.
"""
import unittest

import subtitle_translator_gui as gui


def _b(*rows):
    """rows: (idx, tr) -> blocks [(idx, ts, tr)]."""
    return [(str(i), "00:00:01,000 --> 00:00:02,000", t) for i, t in rows]


def _s(**kw):
    return {str(k): v for k, v in kw.items()}


class NumberShiftTest(unittest.TestCase):
    def test_number_displaced_across_sentence_boundary_fires(self):
        # #100 kendi cümlesi (nokta ile biter), #101 ayrı cümle ('$150') ama '150'
        # #100'ün çevirisinde çıkmış → gerçek kayma.
        blocks = _b((100, "Sete 150 dolar istiyoruz."), (101, "Bu çok eğitici."))
        src = _s(**{"100": "YEAH. I WANT BOTH.", "101": "WE'RE ASKING $150 ON THE SET."})
        findings = gui.detect_alignment_issues(blocks, src)
        self.assertTrue(any(f["type"] == "number_shift" and f["idx"] == "101"
                            for f in findings))

    def test_number_moved_within_same_sentence_is_benign(self):
        # #456 nokta ile BİTMEZ (virgül) → #457 ile tek cümle; '15/20' Türkçe söz
        # dizimi için sonraki cue'ya kaymış — meşru, TETİKLEMEMELİ.
        blocks = _b((456, "İnsan soluk borusunda"),
                    (457, "bunlardan yaklaşık 15 ila 20 tane var."))
        src = _s(**{"456": "THE HUMAN TRACHEA HAS ABOUT 15 TO 20 OF THEM,",
                    "457": "WHICH -- THIS LOOKS ABOUT RIGHT."})
        findings = gui.detect_alignment_issues(blocks, src)
        self.assertFalse(any(f["type"] == "number_shift" for f in findings))

    def test_number_present_in_own_cue_no_flag(self):
        blocks = _b((1, "265 dolar."), (2, "Anlaştık."))
        src = _s(**{"1": "$265.", "2": "IT'S A DEAL."})
        self.assertEqual(gui.detect_alignment_issues(blocks, src), [])

    def test_same_number_belongs_to_neighbor_source_is_not_shift(self):
        blocks = _b(
            (656, "Bu 10 günlük proje boyunca hiçbir şey almadı."),
            (657, "Ne sıvı, ne su, ne de yiyecek tüketti."),
            (658, "Bu 10 gün boyunca idrar ya da dışkı çıkarmadı."),
            (659, "Gerçi mesanesinde idrar oluştu."),
        )
        src = _s(**{
            "656": "HE DID NOT TAKE ANYTHING ORALLY, NEITHER FLUID,",
            "657": "NOR WATER, NOR FOOD DURING THESE 10 DAYS.",
            "658": "SECOND, HE DID NOT PASS URINE OR STOOL",
            "659": "DURING THESE 10 DAYS.",
        })
        findings = gui.detect_alignment_issues(blocks, src)
        self.assertFalse(any(f["type"] == "number_shift" for f in findings))


class MissingDialogueTest(unittest.TestCase):
    def test_real_dialogue_absent_from_output_fires(self):
        # #362 kaynakta gerçek replik ama çıktı bloklarında hiç yok (sessiz silme).
        blocks = _b((361, "Ne harika bir oda bu!"), (363, "Hey, Laura."))
        src = _s(**{"361": "OH.", "362": "WHAT A GREAT ROOM THIS IS. WOW!",
                    "363": "HEY, LAURA."})
        findings = gui.detect_alignment_issues(blocks, src)
        self.assertTrue(any(f["type"] == "missing_dialogue" and f["idx"] == "362"
                            for f in findings))

    def test_sfx_only_absent_is_not_flagged(self):
        # SFX-only cue'nun SDH temizliğiyle silinmesi meşru — TETİKLEMEMELİ.
        blocks = _b((10, "Merhaba."), (12, "Nasılsın?"))
        src = _s(**{"10": "HELLO.", "11": "[ LAUGHS ]", "12": "HOW ARE YOU?"})
        findings = gui.detect_alignment_issues(blocks, src)
        self.assertFalse(any(f["type"] == "missing_dialogue" for f in findings))

    def test_html_escaped_speaker_marker_plus_language_tag_is_sdh_only(self):
        blocks = _b((10, "Merhaba."), (12, "Nasılsın?"))
        src = _s(**{
            "10": "HELLO.",
            "11": "&gt;&gt; [non-english speech]",
            "12": "HOW ARE YOU?",
        })
        findings = gui.detect_alignment_issues(blocks, src)
        self.assertFalse(any(f["type"] == "missing_dialogue" for f in findings))

    def test_present_but_empty_translation_fires(self):
        blocks = _b((5, "Bir şey."), (6, ""), (7, "Başka şey."))
        src = _s(**{"5": "SOMETHING.", "6": "WE GOT YOU SOME STUFF.",
                    "7": "ANOTHER THING."})
        findings = gui.detect_alignment_issues(blocks, src)
        self.assertTrue(any(f["type"] == "missing_dialogue" and f["idx"] == "6"
                            for f in findings))


class OutlierClusterTest(unittest.TestCase):
    def test_extreme_low_and_high_adjacent_fires(self):
        # Boş/çok-kısa cue (içerik kaybı) + çok-uzun cue (komşunun içeriğini yutmuş)
        # yan yana → gerçek "içerik akması".
        blocks = _b((491, "Oh."),
                    (492, "Öteki parçanın bütçenizi çok aştığını biliyoruz, "
                          "o yüzden bunu çok daha ucuza almanın yolunu bulduk."))
        src = _s(**{"491": "WE THINK WE FOUND EXACTLY WHAT HE'S LOOKING FOR HERE.",
                    "492": "ALL RIGHT NOW."})
        findings = gui.detect_alignment_issues(blocks, src)
        self.assertTrue(any(f["type"] == "outlier_cluster" for f in findings))

    def test_mild_redistribution_does_not_fire(self):
        # Hafif kısa/uzun oranlar (0.25-1.9) — meşru çok-cue'lu cümle dağıtımı,
        # AŞIRI aykırı yok → TETİKLEMEMELİ.
        blocks = _b((244, "Bu, hani şu"),
                    (245, "açık tabutlu cenazelerde,"),
                    (246, "yüz deforme olmuşsa"),
                    (247, "ölümden sonra yüzü yeniden yapmak için kullanılan protezlere benziyor."))
        src = _s(**{"244": "IT LOOKS LIKE ONE OF THOSE POSTMORTEM PROSTHETICS",
                    "245": "FOR WHEN THEY'RE DOING AN OPEN-CASKET FUNERAL",
                    "246": "AND THE FACE HAS BEEN DEFORMED",
                    "247": "AND THEY TRY TO RECREATE THE FACE POST-MORTEM."})
        findings = gui.detect_alignment_issues(blocks, src)
        self.assertFalse(any(f["type"] == "outlier_cluster" for f in findings))

    def test_extreme_ratios_within_one_complete_sentence_are_benign(self):
        blocks = _b(
            (1043, "Bu görüntü, biatlon"),
            (1044, "şampiyonu bir sporcunun ideal alanını gösteriyor."),
        )
        src = _s(**{
            "1043": "THIS IMAGE SHOWS THE IDEAL FIELD OF AN ATHLETE, BIATHLON",
            "1044": "CHAMPION.",
        })
        findings = gui.detect_alignment_issues(blocks, src)
        self.assertFalse(any(f["type"] == "outlier_cluster" for f in findings))


class AdjacentDuplicateTest(unittest.TestCase):
    def test_same_translation_different_source_fires(self):
        # Explorer 1 #171/#172 gerçek olayı: içerik öne kaymış, aynı Türkçe satır
        # iki farklı kaynak cue'ya yazılmış — number/length/missing hiçbiri yakalamaz.
        blocks = _b((171, "yolları düşünüldüğünde, benzer bir işi yapacak kadar güçlü değildir."),
                    (172, "yolları düşünüldüğünde, benzer bir işi yapacak kadar güçlü değildir."))
        src = _s(**{"171": "THE HUGE SIZE OF THE STONES AND THE DIFFICULT MOUNTAIN",
                    "172": "PATHS THEY TRAVELED OVER."})
        findings = gui.detect_alignment_issues(blocks, src)
        self.assertTrue(any(f["type"] == "adjacent_duplicate" and
                            "171" in f["ids"] and "172" in f["ids"]
                            for f in findings))

    def test_source_also_repeats_is_benign(self):
        # Kaynağın KENDİSİ tekrarlıyorsa (refrain/vurgu) çevirinin de aynı olması
        # meşru — TETİKLEMEMELİ.
        blocks = _b((558, "Bunu oraya koymak istemiyoruz."),
                    (559, "Bunu oraya koymak istemiyoruz."))
        src = _s(**{"558": "WE DON'T WANT THIS SORT OF STUFF IN THERE.",
                    "559": "WE DON'T WANT THIS SORT OF STUFF IN THERE."})
        findings = gui.detect_alignment_issues(blocks, src)
        self.assertFalse(any(f["type"] == "adjacent_duplicate" for f in findings))

    def test_source_shares_long_common_phrase_is_benign(self):
        # Kaynaklar genel olarak farklı ama uzun bir ortak ifade paylaşıyor
        # ('within sight of gobekli tepe') — Göbekli 2 #308/#313 gerçek yanlış-pozitifi.
        blocks = _b((307, "Ve bu, dünyanın tam bu bölgesinde başlıyor, yani,"),
                    (313, "hep Göbekli Tepe'nin görüş alanı içinde başlıyor,"))
        src = _s(**{"307": "AND THIS BEGINS IN THIS VERY AREA OF THE GLOBE, WITHIN SIGHT OF GOBEKLI TEPE.",
                    "313": "ALL BEGIN WITHIN SIGHT OF GOBEKLI TEPE, AND THAT'S NO COINCIDENCE."})
        findings = gui.detect_alignment_issues(blocks, src)
        self.assertFalse(any(f["type"] == "adjacent_duplicate" for f in findings))

    def test_ordinary_distinct_lines_no_findings(self):
        # Sıradan, birbirinden belirgin şekilde farklı ardışık satırlar — TETİKLEMEMELİ.
        blocks = _b((1, "Lima bizi renk ve gürültü cümbüşüyle karşıladı."),
                    (2, "1535'te Francisco Pizarro tarafından kurulan,"),
                    (3, "bu şehir kısa sürede bölgenin başkenti oldu."),
                    (4, "Bugün hâlâ kolonyal mimarisiyle ünlüdür."))
        src = _s(**{"1": "LIMA GREETED US IN A WELTER OF COLOR AND NOISE.",
                    "2": "FOUNDED BY FRANCISCO PIZARRO IN 1535,",
                    "3": "THE CITY QUICKLY BECAME THE REGION'S CAPITAL.",
                    "4": "IT IS STILL FAMOUS TODAY FOR ITS COLONIAL ARCHITECTURE."})
        findings = gui.detect_alignment_issues(blocks, src)
        self.assertFalse(any(f["type"] == "adjacent_duplicate" for f in findings))


class CleanFileTest(unittest.TestCase):
    def test_aligned_file_no_findings(self):
        blocks = _b((1, "Merhaba."), (2, "Nasılsın?"), (3, "İyiyim, teşekkürler."),
                    (4, "Bunu görmek güzel."))
        src = _s(**{"1": "HELLO.", "2": "HOW ARE YOU?", "3": "I'M GOOD, THANKS.",
                    "4": "GOOD TO SEE THIS."})
        self.assertEqual(gui.detect_alignment_issues(blocks, src), [])


class ScanIntegrationTest(unittest.TestCase):
    def test_scan_counts_alignment_findings(self):
        # scan_translation_quality dedektörü çağırıp uyarı sayısına eklemeli.
        blocks = _b((100, "Sete 150 dolar istiyoruz."), (101, "Bu çok eğitici."))
        src = _s(**{"100": "YEAH. I WANT BOTH.", "101": "WE'RE ASKING $150 ON THE SET."})
        logs = []
        w = gui.scan_translation_quality("dummy.srt", blocks,
                                         log_fn=lambda m, lvl=None: logs.append((m, lvl)),
                                         src_clean_map=src)
        self.assertGreaterEqual(w, 1)
        self.assertTrue(any("HİZALAMA" in m for m, _ in logs))


class RangeFormatTest(unittest.TestCase):
    def test_consecutive_ids_grouped(self):
        self.assertEqual(gui._fmt_align_ranges(["362", "368", "369", "400"]),
                         "#362, #368-369, #400")


if __name__ == "__main__":
    unittest.main()
