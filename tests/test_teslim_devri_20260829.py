# -*- coding: utf-8 -*-
"""Teslim 20260828-202947-183643b5 devri (23 film, 29.854 cue) — dört madde.

Brief: `plans/teslim-20260829-kod-bulgulari-brief.md` (commit b91a54c).
Sayılar programın ürettiği hal (`*.pre-opus-20260829.srt`) üzerinden.
"""
import unittest

import subtitle_translator_gui as gui


class CueIdLeakInlineTest(unittest.TestCase):
    """Madde 4 — cue numarası metne sızmış (7 cue).

    Mevcut dedektör "satırın tamamı sayı" ve "sonda sayı" kalıplarını
    tanıyordu; bu sınıf ise `223: biz hiçbir zaman` / `bu 1351: benim
    başıma gelse` biçiminde geliyor ve ikisine de takılmıyordu.

    Ölçüm: arşiv genelinde (2.910 dosya) 23 yeni yakalama, hepsi gerçek.
    İLK sürüm `\\d{1,4}` idi ve numaralı KONUŞMACI ETİKETLERİNİ yakalıyordu
    (`MAN 1: Oh man.` cue #3, `ADAM 2: ...` cue #5 — etiketin sayısı
    ±3 tolerans penceresine düşüyor). En az iki hane şartı onu eledi.
    """

    def test_inline_leak_is_caught(self):
        for cid, text in (
                ("222", "Sana hiç söylemediğimi hatırlıyor musun,\n"
                        "223: biz hiçbir zaman bir takım anahtarı"),
                ("1350", "Sana söyleyeyim, eğer\nbu 1351: benim başıma gelse,"),
                ("388", "Kıpırdayamayan biri nasıl\n389: koca bir yatağı"),
                ("185", "Gün boyu ev işi yapınca,\n186: bir de dans")):
            with self.subTest(cid=cid):
                self.assertEqual(
                    gui._cue_id_leak_ids([(cid, "x", text)]), [cid])

    def test_numbered_speaker_labels_are_not_leaks(self):
        for cid, text in (("3", "MAN 1:\nUptown, Saturday night."),
                          ("5", "ADAM 2: Tam bir hillbilly cenneti\nişte burası."),
                          ("5", "Man 1: Oh man.\nMan 2: I see it.")):
            with self.subTest(cid=cid):
                self.assertEqual(gui._cue_id_leak_ids([(cid, "x", text)]), [])

    def test_clock_and_far_numbers_are_untouched(self):
        for cid, text in (("45", "Saat 12:30 civarı gelirim."),
                          ("45", "1969: bir dönüm noktasıydı."),
                          ("45", "Bölüm 900: sonu."),
                          ("12", "Normal bir cümle.")):
            with self.subTest(text=text):
                self.assertEqual(gui._cue_id_leak_ids([(cid, "x", text)]), [])

    def test_old_shapes_still_caught(self):
        self.assertEqual(
            gui._cue_id_leak_ids(
                [("107", "x", "Sadakati bu kadar yücelten sen,\n108")]),
            ["107"])


class StrayLineInitialETest(unittest.TestCase):
    """Madde 3 — satır başında tek başına `e` (13 cue / 8 dosya).

    Arşivde sınıf brieften GENİŞ çıktı: bazı bulgularda doğru düzeltme
    `ve` değil (`hayal\\n e edebiliyor musun` fazladan `e`,
    `matematikçilerin\\n e linde` bölünmüş sözcük). Bu yüzden yalnız
    işaretlenir. 2.911 dosya / 2.415.378 cue -> 429 tekil bulgu, meşru
    kullanım yok.
    """

    def test_stray_e_is_flagged(self):
        for text in ("Seninle konuşacağım\n e ve beni durduramayacak.",
                     "Bu güzel\n e tuhaf tebeşir nesneler",
                     "huş kabuğu, liken\n e çam kozalağı,",
                     "Indian matematikçilerin\ne linde"):
            with self.subTest(text=text[:32]):
                self.assertEqual(
                    gui._line_initial_stray_e_ids([("1", "x", text)]), ["1"])

    def test_ordinary_text_is_not_flagged(self):
        for text in ("İki satır\nikinci satırı.",
                     "E, ne olmuş yani?",
                     "Ev\nesnasında geldi.",
                     "ve bu böyle\nve şöyle"):
            with self.subTest(text=text[:32]):
                self.assertEqual(
                    gui._line_initial_stray_e_ids([("1", "x", text)]), [])

    def test_it_is_a_hard_error(self):
        confidence, _t, _f = gui._FINDING_CLASSES["stray_line_initial_e_ids"]
        self.assertEqual(confidence, "kesin")
        self.assertTrue(gui._delivery_scan_has_hard_error(
            {"stray_line_initial_e_ids": ["1"]}))


class LineParityTest(unittest.TestCase):
    """Madde 1 — satır sayısı kaynaktan farklı (2.006 cue / %6,7).

    Kalıcı tercih "satır yapısı kaynaktaki gibi kalır" olduğu için sayaç
    tutulur; ama geriye dönük onarım İSTENMİYOR, o yüzden `bilgi` düzeyi:
    dosyayı tamamlanmamış saymaz.
    """

    SRC = [("1", "00:00:01,000 --> 00:00:02,000", "Two lines\nhere."),
           ("2", "00:00:02,000 --> 00:00:03,000", "One line only."),
           ("3", "00:00:03,000 --> 00:00:04,000", "Same shape\nboth sides.")]

    def test_both_directions_are_counted(self):
        out = [("1", "00:00:01,000 --> 00:00:02,000", "Tek satıra indi."),
               ("2", "00:00:02,000 --> 00:00:03,000", "İkiye\nbölündü."),
               ("3", "00:00:03,000 --> 00:00:04,000", "Aynı biçim\niki tarafta.")]
        self.assertEqual(gui._line_parity_mismatch_ids(self.SRC, out),
                         ["1", "2"])

    def test_timestamp_is_the_key_not_the_number(self):
        """Teslim yeniden numaralanmış olabilir."""
        out = [("77", "00:00:01,000 --> 00:00:02,000", "Tek satır.")]
        self.assertEqual(gui._line_parity_mismatch_ids(self.SRC, out), ["77"])

    def test_unmatched_timestamp_is_ignored(self):
        out = [("1", "00:09:09,000 --> 00:09:10,000", "Alakasız.")]
        self.assertEqual(gui._line_parity_mismatch_ids(self.SRC, out), [])

    def test_empty_sides_are_ignored(self):
        out = [("1", "00:00:01,000 --> 00:00:02,000", "   ")]
        self.assertEqual(gui._line_parity_mismatch_ids(self.SRC, out), [])

    def test_it_does_not_fail_the_delivery(self):
        confidence, _t, _f = gui._FINDING_CLASSES["line_parity_mismatch_ids"]
        self.assertEqual(confidence, "bilgi")
        self.assertFalse(gui._delivery_scan_has_hard_error(
            {"line_parity_mismatch_ids": ["1", "2", "3"]}))


class RepeatAlignmentTest(unittest.TestCase):
    """Madde 2 — aynı kaynak dize farklı çevrilmiş (155 grup / 490 cue).

    Guard'sız kural 349 kaynak/teslim çiftinde 250'den fazla cue'yu
    değiştiriyordu ve DOĞRU çeviriyi bozuyordu. Beş guard'la 30 cue /
    19 dosya kalıyor ve hepsi aynı repliğin savrulmuş hâli.
    """

    NARRATOR = "narrator: pradam tsering, listen without distraction."

    def test_drifted_address_is_aligned(self):
        blocks = [("1", "x", "Pradam Tsering,\ndikkatiniz dağılmadan dinleyin."),
                  ("2", "x", "Pradam Tsering,\ndikkatin dağılmadan dinleyin."),
                  ("3", "x", "Pradam Tsering,\ndikkatiniz dağılmadan dinleyin.")]
        src = {c: self.NARRATOR for c, _t, _x in blocks}
        plan = gui._repeat_alignment_plan(blocks, src)
        self.assertEqual(list(plan), ["2"])
        self.assertEqual(plan["2"], blocks[0][2])

    def test_different_word_choice_is_left_alone(self):
        """GUARD 4 — asıl hasar sınıfı: sıklık doğruluk değildir.

        `petrol` = benzin; çoğunluk YANLIŞ çeviriydi.
        """
        source = "so it's not something you'd get free with your petrol."
        blocks = [("1", "x", "Yani benzinin yanında bedava alacağın bir şey değil."),
                  ("2", "x", "Yani petrol alırken bedavaya alacağın bir şey değil."),
                  ("3", "x", "Yani petrol alırken bedavaya alacağın bir şey değil.")]
        self.assertEqual(
            gui._repeat_alignment_plan(blocks, {c: source for c, _t, _x in blocks}),
            {})

    def test_sentence_tail_is_not_overwritten(self):
        """GUARD 3 — kısa üye ötekinin kuyruğu olabilir."""
        source = "has ever been found in britain before."
        blocks = [("1", "x", "bulunmamıştı."),
                  ("2", "x", "daha önce Britanya'da hiç bulunmadı.")]
        self.assertEqual(
            gui._repeat_alignment_plan(blocks, {c: source for c, _t, _x in blocks}),
            {})

    def test_unresolved_member_blocks_the_group(self):
        blocks = [("1", "x", "[ÇEVİRİ EKSİK]"),
                  ("2", "x", "Pradam Tsering,\ndikkatiniz dağılmadan dinleyin.")]
        self.assertEqual(
            gui._repeat_alignment_plan(
                blocks, {c: self.NARRATOR for c, _t, _x in blocks}), {})

    def test_format_shape_must_match(self):
        blocks = [("1", "x", "<i>Pradam Tsering, dikkatiniz dağılmadan dinleyin.</i>"),
                  ("2", "x", "Pradam Tsering, dikkatin dağılmadan dinleyin.")]
        self.assertEqual(
            gui._repeat_alignment_plan(
                blocks, {c: self.NARRATOR for c, _t, _x in blocks}), {})

    def test_incomplete_source_sentence_is_skipped(self):
        """GUARD 5 — cümle iki cue'ya yayılıyorsa ek değiştirilmez."""
        source = "and the man who came here yesterday morning and"
        blocks = [("1", "x", "Dün sabah buraya gelen adamın"),
                  ("2", "x", "Dün sabah buraya gelen adam")]
        self.assertEqual(
            gui._repeat_alignment_plan(blocks, {c: source for c, _t, _x in blocks}),
            {})

    def test_short_sources_are_never_grouped(self):
        """30 karakter eşiği dedektörle aynı."""
        blocks = [("1", "x", "Evet."), ("2", "x", "Tamam.")]
        self.assertEqual(
            gui._repeat_alignment_plan(blocks, {"1": "Yes.", "2": "Yes."}), {})

    def test_apply_only_touches_planned_cues(self):
        blocks = [("1", "x", "bir"), ("2", "x", "iki"), ("3", "x", "üç")]
        yeni, changed = gui._apply_repeat_alignment(blocks, {"2": "İKİ"})
        self.assertEqual(changed, 1)
        self.assertEqual([t for _i, _ts, t in yeni], ["bir", "İKİ", "üç"])

    def test_apply_with_no_plan_is_identity(self):
        blocks = [("1", "x", "bir")]
        yeni, changed = gui._apply_repeat_alignment(blocks, {})
        self.assertEqual((yeni, changed), (blocks, 0))

    def test_grouping_matches_the_detector(self):
        """Aynı gruplama: dedektör bayrak kaldırdıysa plan da bakmalı."""
        blocks = [("1", "x", "Pradam Tsering,\ndikkatiniz dağılmadan dinleyin."),
                  ("2", "x", "Pradam Tsering,\ndikkatin dağılmadan dinleyin.")]
        src = {c: self.NARRATOR for c, _t, _x in blocks}
        self.assertTrue(gui._inconsistent_repeat_ids(blocks, src))
        self.assertTrue(gui._repeat_alignment_plan(blocks, src))


class SrcMapFromCuesTest(unittest.TestCase):
    def test_tuples_and_objects_both_work(self):
        class _Cue:
            def __init__(self, index, text):
                self.index = index
                self.text = text

        self.assertEqual(
            gui._src_map_from_cues([_Cue("1", "Hello.")]), {"1": "Hello."})
        self.assertEqual(
            gui._src_map_from_cues([("2", "ts", "World.")]), {"2": "World."})

    def test_garbage_is_skipped(self):
        self.assertEqual(gui._src_map_from_cues(None), {})
        self.assertEqual(gui._src_map_from_cues([None, 5]), {})


class AllFourFlowsWiredTest(unittest.TestCase):
    """Tekrar hizalaması dört akışta da çağrılmalı."""

    def test_every_flow_calls_the_helper(self):
        import inspect
        source = inspect.getsource(gui)
        self.assertEqual(source.count("App._maybe_align_repeats("), 4)


if __name__ == "__main__":
    unittest.main()
